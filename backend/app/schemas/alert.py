from datetime import datetime
from pydantic import BaseModel, EmailStr


class AlertOut(BaseModel):
    id: int
    route_id: int
    alert_type: str
    trigger_price: float
    baseline_price: float
    pct_change: float
    email_sent: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AlertHistoryResponse(BaseModel):
    alerts: list[AlertOut]
    total: int
