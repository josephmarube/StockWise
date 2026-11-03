"""Application settings, loaded from environment variables (see .env.example)."""
import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


class Settings:
    def __init__(self) -> None:
        self.database_url: str = os.getenv(
            "DATABASE_URL", "mysql+pymysql://stockwise:stockwise@localhost:3306/stockwise"
        )
        self.jwt_secret: str = os.getenv("JWT_SECRET", "change-me-in-production")
        self.jwt_algorithm: str = "HS256"
        self.jwt_expire_minutes: int = int(os.getenv("JWT_EXPIRE_MINUTES", "480"))
        self.cors_origins: list[str] = [
            o.strip()
            for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
            if o.strip()
        ]
        # Business-local timezone used for report date ranges and CSV timestamps.
        self.business_timezone: str = os.getenv("BUSINESS_TIMEZONE", "Africa/Nairobi")
        self.bootstrap_admin_email: str | None = os.getenv("BOOTSTRAP_ADMIN_EMAIL")
        self.bootstrap_admin_password: str | None = os.getenv("BOOTSTRAP_ADMIN_PASSWORD")


@lru_cache
def get_settings() -> Settings:
    return Settings()
