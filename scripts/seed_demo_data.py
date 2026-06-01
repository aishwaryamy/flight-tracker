#!/usr/bin/env python3
"""
Seed the database with realistic-looking price history for demo purposes.
Run: python scripts/seed_demo_data.py

Generates 60 days of price snapshots for 3 popular routes with:
  - Realistic price fluctuation (higher on weekends + holidays, lower midweek)
  - A few injected "deals" to trigger anomaly detection
  - MLflow training data (retrains the model)
"""

import sys
import os
import random
import math
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import pandas as pd

DATABASE_URL = os.getenv("DATABASE_URL_SYNC", "postgresql://postgres:password@localhost:5432/flighttracker")

engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

from app.models.flight import TrackedRoute, PriceSnapshot, Base
from app.database import Base as AppBase

Base.metadata.create_all(engine)

ROUTES = [
    {"origin": "JFK", "destination": "LHR", "base_price": 520, "airline": "BA"},
    {"origin": "LAX", "destination": "NRT", "base_price": 780, "airline": "NH"},
    {"origin": "ORD", "destination": "CDG", "base_price": 480, "airline": "AF"},
]

DEAL_DAYS = {5, 18, 35, 42}  # Inject deals on these day offsets


def generate_price(base: float, day_offset: int, is_deal: bool = False) -> float:
    """Generate a realistic price with day-of-week and seasonal effects."""
    date = datetime.utcnow() - timedelta(days=60 - day_offset)
    dow = date.weekday()

    # Weekend markup (Fri/Sat/Sun)
    weekend_mult = 1.12 if dow >= 4 else 1.0

    # Mild random noise ±8%
    noise = 1 + random.uniform(-0.08, 0.08)

    # Sine wave for seasonal variation (monthly cycle)
    seasonal = 1 + 0.05 * math.sin(day_offset / 30 * 2 * math.pi)

    price = base * weekend_mult * noise * seasonal

    if is_deal:
        price *= random.uniform(0.68, 0.78)  # 22–32% below normal

    return round(price, 2)


def seed():
    db = Session()
    try:
        print("Seeding demo data…")

        all_features = []

        for route_def in ROUTES:
            # Create tracked route with a dummy session
            route = TrackedRoute(
                session_id="demo-seed-session",
                origin=route_def["origin"],
                destination=route_def["destination"],
                alert_email=None,
                is_active=True,
            )
            db.add(route)
            db.flush()

            prices_added = []
            for day in range(60):
                is_deal = day in DEAL_DAYS
                price = generate_price(route_def["base_price"], day, is_deal)
                captured_at = datetime.utcnow() - timedelta(days=60 - day)
                dep_date = (captured_at + timedelta(days=14)).strftime("%Y-%m-%d")

                snap = PriceSnapshot(
                    route_id=route.id,
                    price=price,
                    currency="USD",
                    airline=route_def["airline"],
                    stops=0,
                    duration_minutes=450 + random.randint(-30, 60),
                    departure_date=dep_date,
                    captured_at=captured_at,
                )
                db.add(snap)
                prices_added.append(price)

                all_features.append({
                    "origin": route_def["origin"],
                    "destination": route_def["destination"],
                    "airline": route_def["airline"],
                    "departure_date": dep_date,
                    "capture_date": captured_at.strftime("%Y-%m-%d"),
                    "stops": 0,
                    "duration_minutes": snap.duration_minutes,
                    "price": price,
                })

            print(f"  {route_def['origin']}→{route_def['destination']}: "
                  f"60 snapshots, avg ${sum(prices_added)/len(prices_added):.0f}")

        db.commit()
        print(f"\nTotal snapshots seeded: {len(all_features)}")

        # Retrain model on seeded data
        try:
            from app.services.ml_engine import make_features, train_and_log
            rows = []
            for f in all_features:
                feat = make_features(
                    f["origin"], f["destination"], f["departure_date"],
                    f["airline"], f["stops"], f["duration_minutes"], f["capture_date"]
                )
                feat["price"] = f["price"]
                rows.append(feat)

            df = pd.concat(rows, ignore_index=True)
            predictor, metrics = train_and_log(df)
            print(f"\nModel trained — MAE: ${metrics['mae']:.2f}, R²: {metrics['r2']:.3f}")
        except Exception as e:
            print(f"\nModel training skipped: {e}")

        print("\nDone! Open http://localhost:5173 and search JFK→LHR to see data.")

    finally:
        db.close()


if __name__ == "__main__":
    seed()
