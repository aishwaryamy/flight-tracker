from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models.alert import Alert
from app.models.flight import TrackedRoute
from app.schemas.alert import AlertOut, AlertHistoryResponse

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("/history/{session_id}", response_model=AlertHistoryResponse)
async def alert_history(
    session_id: str,
    limit: int = Query(default=50, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Return all alerts fired for routes tracked by this session."""
    route_ids_result = await db.execute(
        select(TrackedRoute.id).where(TrackedRoute.session_id == session_id)
    )
    route_ids = [r for r in route_ids_result.scalars().all()]

    if not route_ids:
        return AlertHistoryResponse(alerts=[], total=0)

    alerts_result = await db.execute(
        select(Alert)
        .where(Alert.route_id.in_(route_ids))
        .order_by(Alert.created_at.desc())
        .limit(limit)
    )
    alerts = alerts_result.scalars().all()

    count_result = await db.execute(
        select(func.count()).where(Alert.route_id.in_(route_ids))
    )
    total = count_result.scalar() or 0

    return AlertHistoryResponse(
        alerts=[AlertOut.model_validate(a) for a in alerts],
        total=total,
    )
