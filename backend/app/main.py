import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import create_tables
from app.routers import flights, alerts

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create DB tables on startup
    await create_tables()
    yield


app = FastAPI(
    title="Flight Price Tracker API",
    description="Track flight prices, get ML-powered deal alerts",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(flights.router, prefix="/api")
app.include_router(alerts.router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok", "env": settings.app_env}
