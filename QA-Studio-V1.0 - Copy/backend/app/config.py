"""Application configuration."""
import os


class Settings:
    """App settings from environment with defaults."""

    app_name: str = os.environ.get("APP_NAME", "QA Studio")
    debug: bool = os.environ.get("FLASK_DEBUG", "false").lower() in ("1", "true", "yes")
    cors_origins: str = os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")


settings = Settings()
