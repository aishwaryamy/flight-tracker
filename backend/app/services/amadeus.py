import httpx
import time
import random
import logging
from datetime import datetime
from app.config import get_settings
from app.schemas.flight import FlightOffer

logger = logging.getLogger(__name__)
settings = get_settings()

AMADEUS_BASE = "https://test.api.amadeus.com"  # switch to api.amadeus.com for production
_token_cache: dict = {"token": None, "expires_at": 0}

# ---------------------------------------------------------------------------
# Mock data — used when AMADEUS_CLIENT_ID is not configured (demo / portfolio)
# ---------------------------------------------------------------------------

_MOCK_ROUTES: dict[str, dict] = {
    "JFK-LHR": {"base": 520, "airlines": [("BA", "British Airways"), ("VS", "Virgin Atlantic"), ("AA", "American")], "dur": 435},
    "LAX-NRT": {"base": 780, "airlines": [("NH", "ANA"), ("JL", "JAL"), ("UA", "United")], "dur": 660},
    "ORD-CDG": {"base": 480, "airlines": [("AF", "Air France"), ("UA", "United"), ("LH", "Lufthansa")], "dur": 520},
    "JFK-CDG": {"base": 510, "airlines": [("AF", "Air France"), ("DL", "Delta"), ("AA", "American")], "dur": 445},
    "LAX-LHR": {"base": 630, "airlines": [("BA", "British Airways"), ("AA", "American"), ("VS", "Virgin Atlantic")], "dur": 595},
}

def _mock_offers(origin: str, destination: str, departure_date: str) -> list[FlightOffer]:
    """Generate realistic-looking mock flight offers for demo/portfolio use."""
    key = f"{origin}-{destination}"
    route = _MOCK_ROUTES.get(key) or _MOCK_ROUTES.get(f"{destination}-{origin}")
    if not route:
        # Generic fallback for any unknown route
        route = {"base": 400 + random.randint(0, 400), "airlines": [("AA", "American"), ("UA", "United")], "dur": 300 + random.randint(0, 300)}

    dep = datetime.strptime(departure_date, "%Y-%m-%d")
    # Weekend + days-out pricing effect
    weekend_mult = 1.12 if dep.weekday() >= 4 else 1.0

    offers = []
    for i, (code, name) in enumerate(route["airlines"]):
        price_mult = 1.0 + i * 0.07 + random.uniform(-0.06, 0.06)
        price = round(route["base"] * weekend_mult * price_mult, 2)
        dep_hour = 8 + i * 4
        arr_hour = dep_hour + route["dur"] // 60
        stops = 0 if i == 0 else (1 if i == 1 else random.randint(1, 2))
        dur = route["dur"] + stops * 90 + random.randint(-20, 20)

        dep_str = f"{departure_date}T{dep_hour:02d}:00:00"
        arr_day = departure_date  # simplified — real app would handle overnight
        arr_str = f"{arr_day}T{arr_hour % 24:02d}:{random.randint(0,5)*10:02d}:00"

        offers.append(FlightOffer(
            id=f"mock-{code}-{i}",
            airline=code,
            airline_name=name,
            price=price,
            currency="USD",
            stops=stops,
            duration_minutes=dur,
            departure_at=dep_str,
            arrival_at=arr_str,
            origin=origin,
            destination=destination,
        ))

    return sorted(offers, key=lambda o: o.price)

def _is_mock_mode() -> bool:
    return settings.amadeus_client_id in ("", "test", "your_amadeus_client_id")

AIRLINE_NAMES = {
    "AA": "American", "DL": "Delta", "UA": "United", "BA": "British Airways",
    "LH": "Lufthansa", "AF": "Air France", "EK": "Emirates", "QR": "Qatar Airways",
    "SQ": "Singapore", "CX": "Cathay Pacific", "VS": "Virgin Atlantic",
    "IB": "Iberia", "KL": "KLM", "TK": "Turkish", "NH": "ANA", "JL": "JAL",
}


async def _get_token() -> str:
    now = time.time()
    if _token_cache["token"] and _token_cache["expires_at"] > now + 60:
        return _token_cache["token"]

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{AMADEUS_BASE}/v1/security/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "client_id": settings.amadeus_client_id,
                "client_secret": settings.amadeus_client_secret,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        _token_cache["token"] = data["access_token"]
        _token_cache["expires_at"] = now + data["expires_in"]
        return _token_cache["token"]


def _parse_duration(iso_duration: str) -> int:
    """Convert PT2H30M → 150 minutes."""
    import re
    h = int(m := re.search(r"(\d+)H", iso_duration)) and int(m.group(1)) if re.search(r"(\d+)H", iso_duration) else 0
    mins = int(re.search(r"(\d+)M", iso_duration).group(1)) if re.search(r"(\d+)M", iso_duration) else 0
    return h * 60 + mins


def _parse_offers(data: dict) -> list[FlightOffer]:
    offers = []
    for item in data.get("data", []):
        try:
            price = float(item["price"]["grandTotal"])
            currency = item["price"]["currency"]
            itinerary = item["itineraries"][0]
            segments = itinerary["segments"]
            stops = len(segments) - 1
            first_seg = segments[0]
            last_seg = segments[-1]
            airline = first_seg["carrierCode"]
            duration_min = _parse_duration(itinerary["duration"])

            offers.append(FlightOffer(
                id=item["id"],
                airline=airline,
                airline_name=AIRLINE_NAMES.get(airline, airline),
                price=price,
                currency=currency,
                stops=stops,
                duration_minutes=duration_min,
                departure_at=first_seg["departure"]["at"],
                arrival_at=last_seg["arrival"]["at"],
                origin=first_seg["departure"]["iataCode"],
                destination=last_seg["arrival"]["iataCode"],
            ))
        except (KeyError, ValueError) as e:
            logger.warning(f"Skipping malformed offer: {e}")
    return sorted(offers, key=lambda o: o.price)


async def search_flights(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: str | None = None,
    passengers: int = 1,
) -> list[FlightOffer]:
    token = await _get_token()
    params = {
        "originLocationCode": origin,
        "destinationLocationCode": destination,
        "departureDate": departure_date,
        "adults": passengers,
        "currencyCode": "USD",
        "max": 10,
    }
    if return_date:
        params["returnDate"] = return_date

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{AMADEUS_BASE}/v2/shopping/flight-offers",
            headers={"Authorization": f"Bearer {token}"},
            params=params,
        )
        resp.raise_for_status()
        return _parse_offers(resp.json())

# ---------------------------------------------------------------------------
# PATCHED search_flights with mock mode — replaces original function above
# Amadeus self-service shutdown July 2026; use mock mode for portfolio demos.
# To use a real API: set AMADEUS_CLIENT_ID in .env (SkyLink API is the recommended
# free replacement — sign up at skylinkapi.com for 1,000 req/month free).
# ---------------------------------------------------------------------------
_original_search_flights = search_flights

async def search_flights(  # type: ignore[no-redef]
    origin: str,
    destination: str,
    departure_date: str,
    return_date: str | None = None,
    passengers: int = 1,
) -> list[FlightOffer]:
    if _is_mock_mode():
        logger.info(f"Mock mode active — returning demo offers for {origin}→{destination}")
        return _mock_offers(origin, destination, departure_date)
    return await _original_search_flights(origin, destination, departure_date, return_date, passengers)
