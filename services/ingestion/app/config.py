import os
from dataclasses import dataclass


@dataclass
class Settings:
    postgres_host: str = os.getenv("POSTGRES_HOST", "db")
    postgres_port: int = int(os.getenv("POSTGRES_PORT", "5432"))
    postgres_user: str = os.getenv("POSTGRES_USER", "postgres")
    postgres_password: str = os.getenv("POSTGRES_PASSWORD", "postgres")
    postgres_db: str = os.getenv("POSTGRES_DB", "trading")

    redis_host: str = os.getenv("REDIS_HOST", "redis")
    redis_port: int = int(os.getenv("REDIS_PORT", "6379"))

    alpha_vantage_api_key: str | None = os.getenv("ALPHA_VANTAGE_API_KEY")

    timezone: str = os.getenv("TIMEZONE", "UTC")
    symbols: list[str] = tuple(s.strip() for s in os.getenv("SYMBOLS", "AAPL").split(","))


settings = Settings()
