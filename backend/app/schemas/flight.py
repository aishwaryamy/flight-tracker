from datetime import datetime
from pydantic import BaseModel, field_validator


class FlightSearchRequest(BaseModel):
    origin: str
    destination: str
    departure_date: str  # YYYY-MM-DD
    return_date: str | None = None
    passengers: int = 1
    session_id: str

    @field_validator("origin", "destination")
    @classmethod
    def uppercase_iata(cls, v: str) -> str:
        return v.upper().strip()


class FlightOffer(BaseModel):
    id: str
    airline: str
    airline_name: str
    price: float
    currency: str
    stops: int
    duration_minutes: int
    departure_at: str
    arrival_at: str
    origin: str
    destination: str

    # ML-enriched fields
    price_vs_avg: float | None = None   # % above/below 30-day avg
    is_good_deal: bool = False
    predicted_low: float | None = None
    predicted_high: float | None = None


class FlightSearchResponse(BaseModel):
    offers: list[FlightOffer]
    search_count: int         # how many times this route was searched
    show_track_prompt: bool   # True when search_count >= threshold
    route_key: str            # "JFK-LHR"


class TrackRouteRequest(BaseModel):
    origin: str
    destination: str
    session_id: str
    alert_email: str | None = None
    target_price: float | None = None


class TrackRouteResponse(BaseModel):
    route_id: int
    origin: str
    destination: str
    message: str


class PricePoint(BaseModel):
    date: str
    price: float
    airline: str


class PriceHistoryResponse(BaseModel):
    origin: str
    destination: str
    history: list[PricePoint]
    avg_30d: float
    min_30d: float
    max_30d: float
    current_price: float | None = None


class SearchCountResponse(BaseModel):
    origin: str
    destination: str
    count: int
    show_track_prompt: bool
