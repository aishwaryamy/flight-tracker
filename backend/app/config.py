from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    amadeus_client_id: str = "test"
    amadeus_client_secret: str = "test"

    database_url: str = "postgresql+asyncpg://postgres:password@db:5432/flighttracker"
    database_url_sync: str = "postgresql://postgres:password@db:5432/flighttracker"

    redis_url: str = "redis://redis:6379/0"

    secret_key: str = "dev-secret-key"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 10080

    sendgrid_api_key: str = ""
    alert_from_email: str = "alerts@flighttracker.app"

    app_env: str = "development"
    frontend_url: str = "http://localhost:5173"

    # Price polling interval in seconds (6 hours)
    poll_interval_seconds: int = 21600

    # ML: minimum searches before suggesting alert
    min_searches_for_prompt: int = 3

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
