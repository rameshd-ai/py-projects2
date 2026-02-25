"""Application configuration."""
import os


class Settings:
    """App settings from environment with defaults."""

    app_name: str = os.environ.get("APP_NAME", "QA Studio")
    debug: bool = os.environ.get("FLASK_DEBUG", "false").lower() in ("1", "true", "yes")
    cors_origins: str = os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    google_client_id: str = os.environ.get("GOOGLE_CLIENT_ID", "")
    google_client_secret: str = os.environ.get("GOOGLE_CLIENT_SECRET", "")
    app_base_url: str = os.environ.get("APP_BASE_URL", "http://localhost:8001")


settings = Settings()
