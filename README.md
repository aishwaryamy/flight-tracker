**Live demo:** https://flight-track-production-e984.up.railway.app

# ✈ Flight Price Tracker

A full-stack ML-powered flight price tracker. Monitors prices via the Amadeus API, flags deals using XGBoost + anomaly detection, and proactively suggests tracking routes based on your search behavior.

**Portfolio highlights:** FastAPI · React 18 + TypeScript · XGBoost · Celery · Redis · MLflow · PostgreSQL · Docker Compose

---

## Architecture

```
User → React (Recharts) → FastAPI (Pydantic v2) → Amadeus API
                              ↓               ↓
                         ML Engine        Celery Workers → Redis
                        (XGBoost +             ↓
                      anomaly detect)     PostgreSQL
                              ↓
                       Alert System (SendGrid)
                              
MLflow (experiment tracking, standalone)
```

---

## Quick start

### 1. Prerequisites
- Docker + Docker Compose
- Amadeus API keys (free at [developers.amadeus.com](https://developers.amadeus.com))
- SendGrid API key (free tier, optional — for email alerts)

### 2. Clone and configure

```bash
git clone <your-repo>
cd flight-tracker

cp backend/.env.example backend/.env
# Edit backend/.env and add your Amadeus + SendGrid keys
```

### 3. Start everything

```bash
docker compose up --build
```

This starts:
| Service | URL |
|---------|-----|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| API docs | http://localhost:8000/docs |
| MLflow UI | http://localhost:5000 |

### 4. Seed demo data (optional but recommended)

In a second terminal, once the stack is up:

```bash
docker compose exec backend python /app/../scripts/seed_demo_data.py
```

This generates 60 days of realistic price history for 3 routes (JFK→LHR, LAX→NRT, ORD→CDG) and trains the initial XGBoost model.

---

## Development (without Docker)

### Backend

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# You need a local Postgres + Redis running, then:
cp .env.example .env  # edit DATABASE_URL / REDIS_URL to point to localhost

uvicorn app.main:app --reload
```

### Celery worker (separate terminal)

```bash
cd backend
source venv/bin/activate
celery -A app.tasks.celery_app worker --loglevel=info
```

### Celery beat (separate terminal)

```bash
cd backend
source venv/bin/activate
celery -A app.tasks.celery_app beat --loglevel=info
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

---

## Project structure

```
flight-tracker/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app + lifespan
│   │   ├── config.py            # Pydantic settings
│   │   ├── database.py          # Async SQLAlchemy setup
│   │   ├── models/
│   │   │   ├── flight.py        # User, SearchHistory, TrackedRoute, PriceSnapshot
│   │   │   └── alert.py         # Alert model
│   │   ├── schemas/
│   │   │   ├── flight.py        # Pydantic v2 request/response schemas
│   │   │   └── alert.py
│   │   ├── routers/
│   │   │   ├── flights.py       # /search /track /history endpoints
│   │   │   └── alerts.py        # /alerts/history endpoint
│   │   ├── services/
│   │   │   ├── amadeus.py       # Amadeus API client
│   │   │   ├── ml_engine.py     # XGBoost + anomaly detection + MLflow
│   │   │   └── alert_service.py # SendGrid email sender
│   │   └── tasks/
│   │       ├── celery_app.py    # Celery config + beat schedule
│   │       └── price_poll.py    # poll_all_routes, poll_single_route, retrain_model
│   └── requirements.txt
│
├── frontend/
│   └── src/
│       ├── api/client.ts        # Axios client + TypeScript types
│       ├── hooks/useSessionId.ts
│       ├── components/
│       │   ├── Navbar.tsx
│       │   ├── FlightCard.tsx
│       │   ├── PriceChart.tsx   # Recharts with good-price-zone shading
│       │   └── TrackPromptBanner.tsx  # Smart ML-driven tracking prompt
│       └── pages/
│           ├── Search.tsx       # Landing + search results
│           ├── RouteDetail.tsx  # Price history chart
│           ├── Dashboard.tsx    # Tracked routes grid
│           └── Alerts.tsx       # Alert history timeline
│
├── scripts/
│   └── seed_demo_data.py        # Generates synthetic price history + trains model
│
└── docker-compose.yml
```

---

## ML engine details

**Feature engineering** (`ml_engine.py::make_features`)
- Days to departure, departure day-of-week, departure month, weekend flag
- Stops, flight duration, route distance proxy
- Origin/destination hub flag, airline encoding

**XGBoost regressor**
- 300 estimators, learning rate 0.05, max depth 5
- Early stopping on validation MAE
- Predicts a price point + ±15% confidence band
- Auto-retrains daily at 3 AM UTC via Celery beat

**Anomaly detection** (IQR + Z-score hybrid)
- Designed for small data (5–90 price points per route)
- IQR fence: Q1 - 1.5×IQR
- Z-score threshold: < -2.0
- Returns severity score 0–1, direction (low/high/normal)
- Fires alert when severity > 0 + direction == "low"

**MLflow tracking**
- Logs params, MAE, R², feature importances per training run
- Registers model artifacts under `xgb_price_model`
- View at http://localhost:5000

---

## Key design decision: implicit vs explicit alerts

The app detects when you've searched the same route 3+ times in a week and surfaces an in-app prompt — *"Want us to track this?"* — rather than silently sending emails. This:
- Keeps consent as the gate for external notifications (CAN-SPAM / GDPR)
- Feels like AI magic (the app noticed your behavior) without being creepy
- Makes a stronger portfolio story — shows product ethics thinking

---

## Deploying to Railway (free tier)

```bash
# Install Railway CLI
npm install -g @railway/cli
railway login

# Create project
railway init

# Add services (Postgres + Redis are one-click in Railway dashboard)
# Then deploy:
railway up
```

Set these env vars in the Railway dashboard:
- `AMADEUS_CLIENT_ID` / `AMADEUS_CLIENT_SECRET`
- `SENDGRID_API_KEY`
- `DATABASE_URL` / `REDIS_URL` (auto-filled by Railway plugins)

---

## API reference

Full interactive docs at http://localhost:8000/docs

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/flights/search` | Search + ML-enrich flight offers |
| POST | `/api/flights/track` | Start tracking a route |
| GET | `/api/flights/track/{session_id}` | List tracked routes |
| DELETE | `/api/flights/track/{route_id}` | Stop tracking |
| GET | `/api/flights/history/{origin}/{destination}` | Price history |
| GET | `/api/alerts/history/{session_id}` | Alert history |
