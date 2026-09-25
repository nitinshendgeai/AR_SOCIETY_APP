from pydantic_settings import BaseSettings
from typing import List, Optional
from functools import lru_cache


class Settings(BaseSettings):
    # App
    APP_NAME: str = "AR Society ERP"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = "development"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "postgresql://user:password@localhost:5432/ar_society_db"

    # JWT
    SECRET_KEY: str = "change-me-in-production-use-strong-random-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS
    ALLOWED_ORIGINS: List[str] = ["*"]

    # Push notifications (Firebase Cloud Messaging). The service account's
    # JSON key, pasted whole; push is off while it's empty.
    FIREBASE_SERVICE_ACCOUNT_JSON: str = ""
    # Where a tapped web notification opens (the Flutter web app).
    WEB_APP_URL: str = "https://society.duxos.in"

    # Superadmin seed
    SUPERADMIN_EMAIL: Optional[str] = None
    SUPERADMIN_PASSWORD: Optional[str] = None

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
