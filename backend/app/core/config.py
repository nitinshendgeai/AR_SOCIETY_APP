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

    # Runs the automatic tasks (reminders, alerts) in the background. Off in tests.
    SCHEDULER_ENABLED: bool = True

    # Transactional email (SMTP). While SMTP_HOST is empty, email is off
    # and every EmailService call is a no-op.
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""
    SMTP_USE_TLS: bool = True

    # Notified when a society self-registers (registration details and the
    # default users + temporary passwords created for it).
    ADMIN_NOTIFICATION_EMAIL: str = "admin@duxos.in"

    # Help assistant (docs-grounded, read-only). "disabled" answers from the manuals alone; "mock" is a deterministic
    # test provider. No live provider is wired in yet and no provider credential is read anywhere.
    ASSISTANT_ENABLED: bool = True
    ASSISTANT_PROVIDER: str = "disabled"
    ASSISTANT_PROVIDER_TIMEOUT_SECONDS: float = 15.0
    ASSISTANT_MAX_QUESTION_CHARS: int = 1000
    ASSISTANT_MAX_HISTORY_TURNS: int = 6
    ASSISTANT_MAX_HISTORY_CHARS: int = 600
    ASSISTANT_MAX_ANSWER_CHARS: int = 3000
    ASSISTANT_RATE_LIMIT_PER_MINUTE: int = 20

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
