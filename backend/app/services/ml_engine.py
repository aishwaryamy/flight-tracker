"""
ML Engine for flight price prediction and anomaly detection.

Components:
  1. Feature engineering — extract route/temporal/historical features
  2. XGBoost regressor — predict price range for a route on a given date
  3. IQR-based anomaly detector — flag statistically unusual prices
  4. MLflow integration — log experiments and register models
"""

import os
import pickle
import logging
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelEncoder
from xgboost import XGBRegressor
try:
    import mlflow
    import mlflow.xgboost
    MLFLOW_AVAILABLE = True
except Exception:
    MLFLOW_AVAILABLE = False

logger = logging.getLogger(__name__)

MODEL_DIR = Path("/app/ml_models")
MODEL_DIR.mkdir(parents=True, exist_ok=True)

MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")


# ---------------------------------------------------------------------------
# 1. Feature engineering
# ---------------------------------------------------------------------------

def make_features(
    origin: str,
    destination: str,
    departure_date: str,
    airline: str,
    stops: int,
    duration_minutes: int,
    capture_date: str | None = None,
) -> pd.DataFrame:
    """Convert raw fields into a feature vector for the model."""
    dep = datetime.strptime(departure_date, "%Y-%m-%d")
    cap = datetime.strptime(capture_date, "%Y-%m-%d") if capture_date else datetime.utcnow()

    days_to_departure = (dep - cap).days
    days_to_departure = max(0, days_to_departure)

    # Route distance proxy: use a simple lookup; real app would use geopy
    route_key = f"{origin}-{destination}"
    route_distance_proxy = _route_distance(origin, destination)

    return pd.DataFrame([{
        "days_to_departure": days_to_departure,
        "departure_dow": dep.weekday(),          # 0=Mon … 6=Sun
        "departure_month": dep.month,
        "is_weekend_dep": int(dep.weekday() >= 5),
        "stops": stops,
        "duration_minutes": duration_minutes,
        "route_distance_proxy": route_distance_proxy,
        "origin_hub": int(origin in {"JFK", "LAX", "ORD", "LHR", "CDG", "DXB"}),
        "dest_hub": int(destination in {"JFK", "LAX", "ORD", "LHR", "CDG", "DXB"}),
        "airline_code": _encode_airline(airline),
    }])


def _route_distance(origin: str, dest: str) -> float:
    """Rough distance proxy based on known routes (km)."""
    known = {
        frozenset(["JFK", "LHR"]): 5570,
        frozenset(["JFK", "CDG"]): 5830,
        frozenset(["LAX", "NRT"]): 8760,
        frozenset(["ORD", "LHR"]): 6350,
        frozenset(["JFK", "MIA"]): 1750,
        frozenset(["LAX", "JFK"]): 3970,
        frozenset(["SFO", "LHR"]): 8620,
    }
    return known.get(frozenset([origin, dest]), 5000.0)


def _encode_airline(airline: str) -> int:
    legacy = {"AA": 1, "DL": 2, "UA": 3, "BA": 4, "LH": 5, "AF": 6}
    return legacy.get(airline, 0)


# ---------------------------------------------------------------------------
# 2. XGBoost model
# ---------------------------------------------------------------------------

class PricePredictor:
    def __init__(self):
        self.model: XGBRegressor | None = None
        self.feature_names: list[str] = [
            "days_to_departure", "departure_dow", "departure_month",
            "is_weekend_dep", "stops", "duration_minutes",
            "route_distance_proxy", "origin_hub", "dest_hub", "airline_code",
        ]

    def train(self, df: pd.DataFrame, target_col: str = "price") -> dict:
        """
        Train on a DataFrame of historical prices.
        df must contain all self.feature_names columns plus target_col.
        Returns a dict of eval metrics.
        """
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import mean_absolute_error, r2_score

        X = df[self.feature_names]
        y = df[target_col]

        X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42)

        self.model = XGBRegressor(
            n_estimators=300,
            learning_rate=0.05,
            max_depth=5,
            subsample=0.8,
            colsample_bytree=0.8,
            objective="reg:squarederror",
            random_state=42,
            early_stopping_rounds=20,
            eval_metric="mae",
        )
        self.model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            verbose=False,
        )

        preds = self.model.predict(X_val)
        metrics = {
            "mae": float(mean_absolute_error(y_val, preds)),
            "r2": float(r2_score(y_val, preds)),
            "n_train": len(X_train),
            "n_val": len(X_val),
        }
        logger.info(f"XGBoost trained — MAE: {metrics['mae']:.2f}, R²: {metrics['r2']:.3f}")
        return metrics

    def predict_range(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        airline: str = "AA",
        stops: int = 0,
        duration_minutes: int = 480,
    ) -> dict:
        """Return predicted price +/- confidence interval."""
        if self.model is None:
            return {}

        X = make_features(origin, destination, departure_date, airline, stops, duration_minutes)
        pred = float(self.model.predict(X[self.feature_names])[0])

        # Simple ±15% confidence band — tighten with actual quantile regression if you have data
        return {
            "predicted": round(pred, 2),
            "low": round(pred * 0.85, 2),
            "high": round(pred * 1.15, 2),
        }

    def feature_importance(self) -> dict:
        if self.model is None:
            return {}
        scores = self.model.feature_importances_
        return dict(sorted(
            zip(self.feature_names, scores.tolist()),
            key=lambda x: -x[1],
        ))

    def save(self, path: str = str(MODEL_DIR / "price_model.pkl")):
        with open(path, "wb") as f:
            pickle.dump(self.model, f)
        logger.info(f"Model saved → {path}")

    def load(self, path: str = str(MODEL_DIR / "price_model.pkl")) -> bool:
        if not Path(path).exists():
            return False
        with open(path, "rb") as f:
            self.model = pickle.load(f)
        logger.info(f"Model loaded ← {path}")
        return True


# ---------------------------------------------------------------------------
# 3. Anomaly detection
# ---------------------------------------------------------------------------

class AnomalyDetector:
    """
    IQR + Z-score hybrid for detecting unusual prices on a route.
    Designed for small data (30–90 price points per route).
    """

    def __init__(self, iqr_multiplier: float = 1.5, z_threshold: float = 2.0):
        self.iqr_multiplier = iqr_multiplier
        self.z_threshold = z_threshold

    def detect(self, prices: list[float], candidate: float) -> dict:
        """
        Check if candidate price is anomalously low (a deal).

        Returns:
            is_anomaly: bool
            direction: "low" | "high" | "normal"
            severity: 0–1 float
            z_score: float
            iqr_low_fence: float
        """
        if len(prices) < 5:
            return {"is_anomaly": False, "direction": "normal", "severity": 0.0,
                    "z_score": 0.0, "iqr_low_fence": None}

        arr = np.array(prices, dtype=float)
        q1, q3 = np.percentile(arr, [25, 75])
        iqr = q3 - q1
        low_fence = q1 - self.iqr_multiplier * iqr
        high_fence = q3 + self.iqr_multiplier * iqr

        mean, std = arr.mean(), arr.std()
        z_score = (candidate - mean) / (std + 1e-9)

        is_low = candidate < low_fence or z_score < -self.z_threshold
        is_high = candidate > high_fence or z_score > self.z_threshold

        if is_low:
            # Severity 0–1 proportional to how far below the low fence
            depth = (low_fence - candidate) / (iqr + 1e-9)
            severity = float(min(1.0, depth / 2))
            return {
                "is_anomaly": True, "direction": "low",
                "severity": round(severity, 3), "z_score": round(z_score, 3),
                "iqr_low_fence": round(low_fence, 2),
            }
        if is_high:
            depth = (candidate - high_fence) / (iqr + 1e-9)
            severity = float(min(1.0, depth / 2))
            return {
                "is_anomaly": True, "direction": "high",
                "severity": round(severity, 3), "z_score": round(z_score, 3),
                "iqr_low_fence": round(low_fence, 2),
            }

        return {"is_anomaly": False, "direction": "normal", "severity": 0.0,
                "z_score": round(z_score, 3), "iqr_low_fence": round(low_fence, 2)}

    def summarize_route(self, prices: list[float]) -> dict:
        """Return stats for the price history card."""
        if not prices:
            return {}
        arr = np.array(prices, dtype=float)
        return {
            "mean": round(float(arr.mean()), 2),
            "min": round(float(arr.min()), 2),
            "max": round(float(arr.max()), 2),
            "std": round(float(arr.std()), 2),
            "p25": round(float(np.percentile(arr, 25)), 2),
            "p75": round(float(np.percentile(arr, 75)), 2),
        }


# ---------------------------------------------------------------------------
# 4. MLflow training run
# ---------------------------------------------------------------------------

def train_and_log(df: pd.DataFrame, experiment_name: str = "flight-price-prediction"):
    """Full training run with MLflow tracking."""
    try:
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    except Exception:
        logger.warning("MLflow server unreachable — logging locally")

    mlflow.set_experiment(experiment_name)

    with mlflow.start_run():
        predictor = PricePredictor()
        metrics = predictor.train(df)

        mlflow.log_params({
            "n_estimators": 300,
            "learning_rate": 0.05,
            "max_depth": 5,
            "early_stopping_rounds": 20,
        })
        mlflow.log_metrics(metrics)

        importance = predictor.feature_importance()
        for feat, score in importance.items():
            mlflow.log_metric(f"fi_{feat}", score)

        mlflow.xgboost.log_model(predictor.model, "xgb_price_model")
        predictor.save()

        logger.info(f"MLflow run complete — metrics: {metrics}")
        return predictor, metrics


# ---------------------------------------------------------------------------
# Singleton instances (loaded once per worker process)
# ---------------------------------------------------------------------------

_predictor = PricePredictor()
_predictor.load()  # no-op if no saved model yet

anomaly_detector = AnomalyDetector()


def get_predictor() -> PricePredictor:
    return _predictor


def get_anomaly_detector() -> AnomalyDetector:
    return anomaly_detector
