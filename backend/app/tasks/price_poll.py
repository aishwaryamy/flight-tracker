import asyncio
import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.tasks.celery_app import celery_app
from app.config import get_settings
from app.models.flight import TrackedRoute, PriceSnapshot
from app.models.alert import Alert
from app.services.ml_engine import get_anomaly_detector, get_predictor, train_and_log
from app.services.alert_service import send_price_alert

settings = get_settings()
logger = logging.getLogger(__name__)


def _get_sync_db():
    """Synchronous DB session for Celery tasks."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    engine = create_engine(settings.database_url_sync)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


@celery_app.task(name="app.tasks.price_poll.poll_all_routes", bind=True, max_retries=3)
def poll_all_routes(self):
    """Fetch latest prices for all active tracked routes."""
    logger.info("Starting price poll for all active routes")
    db = _get_sync_db()
    try:
        routes = db.execute(
            select(TrackedRoute).where(TrackedRoute.is_active == True)
        ).scalars().all()

        logger.info(f"Polling {len(routes)} active routes")
        for route in routes:
            try:
                poll_single_route.delay(route.id)
            except Exception as e:
                logger.error(f"Failed to queue poll for route {route.id}: {e}")
    finally:
        db.close()


@celery_app.task(name="app.tasks.price_poll.poll_single_route", bind=True, max_retries=3)
def poll_single_route(self, route_id: int):
    """Poll and store prices for one route, then run anomaly detection."""
    from app.services.amadeus import search_flights
    import asyncio

    db = _get_sync_db()
    try:
        route = db.get(TrackedRoute, route_id)
        if not route or not route.is_active:
            return

        # Use next available departure date (14 days from now as default)
        departure_date = (datetime.utcnow() + timedelta(days=14)).strftime("%Y-%m-%d")

        # Run async Amadeus call in sync Celery context
        offers = asyncio.run(
            search_flights(route.origin, route.destination, departure_date)
        )
        if not offers:
            logger.warning(f"No offers returned for route {route_id}")
            return

        cheapest = offers[0]

        # Save snapshot
        snapshot = PriceSnapshot(
            route_id=route.id,
            price=cheapest.price,
            currency=cheapest.currency,
            airline=cheapest.airline,
            stops=cheapest.stops,
            duration_minutes=cheapest.duration_minutes,
            departure_date=departure_date,
        )
        db.add(snapshot)
        db.commit()

        # Run anomaly detection against last 30 snapshots
        recent = db.execute(
            select(PriceSnapshot.price)
            .where(PriceSnapshot.route_id == route_id)
            .order_by(PriceSnapshot.captured_at.desc())
            .limit(30)
        ).scalars().all()

        if len(recent) >= 5:
            detector = get_anomaly_detector()
            result = detector.detect(list(recent[1:]), cheapest.price)  # exclude current

            if result["is_anomaly"] and result["direction"] == "low":
                baseline = sum(recent[1:]) / len(recent[1:])
                pct_change = (cheapest.price - baseline) / baseline * 100

                alert = Alert(
                    route_id=route.id,
                    alert_type="anomaly" if result["severity"] > 0.5 else "price_drop",
                    trigger_price=cheapest.price,
                    baseline_price=round(baseline, 2),
                    pct_change=round(pct_change, 2),
                )
                db.add(alert)
                db.commit()
                db.refresh(alert)

                # Send email if route has an alert email
                if route.alert_email:
                    asyncio.run(send_price_alert(
                        to_email=route.alert_email,
                        origin=route.origin,
                        destination=route.destination,
                        trigger_price=cheapest.price,
                        baseline_price=baseline,
                        pct_change=pct_change,
                    ))
                    # Mark email as sent
                    alert.email_sent = True
                    alert.sent_at = datetime.utcnow()
                    db.commit()

                logger.info(
                    f"Alert created for route {route_id}: "
                    f"{route.origin}→{route.destination} "
                    f"${cheapest.price} ({pct_change:.1f}%)"
                )

    except Exception as exc:
        logger.error(f"Error polling route {route_id}: {exc}")
        raise self.retry(exc=exc, countdown=300)
    finally:
        db.close()


@celery_app.task(name="app.tasks.price_poll.retrain_model")
def retrain_model():
    """
    Retrain the XGBoost model on accumulated price snapshots.
    Runs daily at 3 AM UTC.
    """
    import pandas as pd
    from app.services.ml_engine import make_features

    db = _get_sync_db()
    try:
        rows = db.execute(
            select(
                PriceSnapshot.price,
                PriceSnapshot.airline,
                PriceSnapshot.stops,
                PriceSnapshot.duration_minutes,
                PriceSnapshot.departure_date,
                PriceSnapshot.captured_at,
                TrackedRoute.origin,
                TrackedRoute.destination,
            )
            .join(TrackedRoute, PriceSnapshot.route_id == TrackedRoute.id)
            .where(PriceSnapshot.captured_at >= datetime.utcnow() - timedelta(days=90))
        ).all()

        if len(rows) < 50:
            logger.info(f"Not enough data for retraining ({len(rows)} rows, need 50)")
            return

        records = []
        for row in rows:
            feat = make_features(
                origin=row.origin,
                destination=row.destination,
                departure_date=row.departure_date,
                airline=row.airline,
                stops=row.stops,
                duration_minutes=row.duration_minutes,
                capture_date=row.captured_at.strftime("%Y-%m-%d"),
            )
            feat["price"] = row.price
            records.append(feat)

        df = pd.concat(records, ignore_index=True)
        _, metrics = train_and_log(df)
        logger.info(f"Model retrained — MAE: {metrics['mae']:.2f}")

    finally:
        db.close()
