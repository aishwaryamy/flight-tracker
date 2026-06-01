import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.config import get_settings
from app.models.flight import SearchHistory, TrackedRoute, PriceSnapshot
from app.schemas.flight import (
    FlightSearchRequest, FlightSearchResponse, FlightOffer,
    TrackRouteRequest, TrackRouteResponse,
    PriceHistoryResponse, PricePoint,
)
from app.services.amadeus import search_flights
from app.services.ml_engine import get_predictor, get_anomaly_detector

router = APIRouter(prefix="/flights", tags=["flights"])
logger = logging.getLogger(__name__)
settings = get_settings()


@router.post("/search", response_model=FlightSearchResponse)
async def search(req: FlightSearchRequest, db: AsyncSession = Depends(get_db)):
    """
    Search for flights. Records the search for pattern detection.
    Returns ML-enriched offers + smart tracking prompt when needed.
    """
    # 1. Fetch live offers from Amadeus
    try:
        offers = await search_flights(
            req.origin, req.destination, req.departure_date,
            req.return_date, req.passengers,
        )
    except Exception as e:
        logger.error(f"Amadeus error: {e}")
        raise HTTPException(502, "Could not fetch flight prices. Try again shortly.")

    # 2. Record the search
    history = SearchHistory(
        session_id=req.session_id,
        origin=req.origin,
        destination=req.destination,
        departure_date=req.departure_date,
        return_date=req.return_date,
        passengers=req.passengers,
    )
    db.add(history)
    await db.flush()

    # 3. Count searches for this route in last 7 days
    since = datetime.utcnow() - timedelta(days=7)
    count_result = await db.execute(
        select(func.count()).where(
            SearchHistory.session_id == req.session_id,
            SearchHistory.origin == req.origin,
            SearchHistory.destination == req.destination,
            SearchHistory.searched_at >= since,
        )
    )
    search_count = count_result.scalar() or 0

    # 4. ML enrichment — enrich each offer with vs-avg context
    predictor = get_predictor()
    detector = get_anomaly_detector()

    # Get recent snapshots for this route for anomaly context
    route = await db.execute(
        select(TrackedRoute).where(
            TrackedRoute.origin == req.origin,
            TrackedRoute.destination == req.destination,
            TrackedRoute.is_active == True,
        ).limit(1)
    )
    tracked = route.scalar_one_or_none()
    historical_prices: list[float] = []

    if tracked:
        snap_result = await db.execute(
            select(PriceSnapshot.price)
            .where(PriceSnapshot.route_id == tracked.id)
            .order_by(PriceSnapshot.captured_at.desc())
            .limit(30)
        )
        historical_prices = list(snap_result.scalars().all())

    enriched_offers: list[FlightOffer] = []
    for offer in offers:
        enhanced = offer.model_copy()

        # Price vs 30-day average
        if historical_prices:
            avg = sum(historical_prices) / len(historical_prices)
            enhanced.price_vs_avg = round((offer.price - avg) / avg * 100, 1)

            # Anomaly detection
            anomaly = detector.detect(historical_prices, offer.price)
            enhanced.is_good_deal = (
                anomaly["is_anomaly"] and anomaly["direction"] == "low"
            )

        # Predicted price range
        pred = predictor.predict_range(
            req.origin, req.destination, req.departure_date,
            offer.airline, offer.stops, offer.duration_minutes,
        )
        if pred:
            enhanced.predicted_low = pred["low"]
            enhanced.predicted_high = pred["high"]

        enriched_offers.append(enhanced)

    return FlightSearchResponse(
        offers=enriched_offers,
        search_count=search_count,
        show_track_prompt=search_count >= settings.min_searches_for_prompt,
        route_key=f"{req.origin}-{req.destination}",
    )


@router.post("/track", response_model=TrackRouteResponse)
async def track_route(req: TrackRouteRequest, db: AsyncSession = Depends(get_db)):
    """Start tracking a route for price alerts."""
    # Check if already tracked
    existing = await db.execute(
        select(TrackedRoute).where(
            TrackedRoute.session_id == req.session_id,
            TrackedRoute.origin == req.origin,
            TrackedRoute.destination == req.destination,
            TrackedRoute.is_active == True,
        )
    )
    route = existing.scalar_one_or_none()

    if route:
        if req.alert_email and not route.alert_email:
            route.alert_email = req.alert_email
        return TrackRouteResponse(
            route_id=route.id,
            origin=route.origin,
            destination=route.destination,
            message="Already tracking this route.",
        )

    route = TrackedRoute(
        session_id=req.session_id,
        origin=req.origin,
        destination=req.destination,
        alert_email=req.alert_email,
        target_price=req.target_price,
    )
    db.add(route)
    await db.flush()

    # Kick off an immediate price poll
    from app.tasks.price_poll import poll_single_route
    poll_single_route.delay(route.id)

    return TrackRouteResponse(
        route_id=route.id,
        origin=route.origin,
        destination=route.destination,
        message=f"Now tracking {req.origin}→{req.destination}. We'll alert you on price drops.",
    )


@router.get("/track/{session_id}", response_model=list[TrackRouteResponse])
async def list_tracked(session_id: str, db: AsyncSession = Depends(get_db)):
    """List all routes tracked in this session (dashboard data)."""
    result = await db.execute(
        select(TrackedRoute).where(
            TrackedRoute.session_id == session_id,
            TrackedRoute.is_active == True,
        )
    )
    routes = result.scalars().all()
    return [
        TrackRouteResponse(
            route_id=r.id, origin=r.origin,
            destination=r.destination, message=""
        )
        for r in routes
    ]


@router.delete("/track/{route_id}")
async def untrack_route(route_id: int, db: AsyncSession = Depends(get_db)):
    route = await db.get(TrackedRoute, route_id)
    if not route:
        raise HTTPException(404, "Route not found")
    route.is_active = False
    return {"message": "Route untracked"}


@router.get("/history/{origin}/{destination}", response_model=PriceHistoryResponse)
async def price_history(
    origin: str,
    destination: str,
    days: int = Query(default=30, ge=7, le=90),
    db: AsyncSession = Depends(get_db),
):
    """Return price history for a route — used by the chart on route detail page."""
    since = datetime.utcnow() - timedelta(days=days)

    route_result = await db.execute(
        select(TrackedRoute).where(
            TrackedRoute.origin == origin.upper(),
            TrackedRoute.destination == destination.upper(),
            TrackedRoute.is_active == True,
        ).limit(1)
    )
    route = route_result.scalar_one_or_none()
    if not route:
        raise HTTPException(404, "No tracking data for this route yet.")

    snaps_result = await db.execute(
        select(PriceSnapshot)
        .where(
            PriceSnapshot.route_id == route.id,
            PriceSnapshot.captured_at >= since,
        )
        .order_by(PriceSnapshot.captured_at.asc())
    )
    snaps = snaps_result.scalars().all()

    if not snaps:
        raise HTTPException(404, "No price snapshots yet for this route.")

    history = [
        PricePoint(
            date=s.captured_at.strftime("%Y-%m-%d"),
            price=s.price,
            airline=s.airline,
        )
        for s in snaps
    ]
    prices = [s.price for s in snaps]

    return PriceHistoryResponse(
        origin=origin.upper(),
        destination=destination.upper(),
        history=history,
        avg_30d=round(sum(prices) / len(prices), 2),
        min_30d=round(min(prices), 2),
        max_30d=round(max(prices), 2),
        current_price=prices[-1] if prices else None,
    )
