"""
Application Configuration
Loads settings from environment variables
"""
from pydantic_settings import BaseSettings
from pydantic import Field, validator
from typing import List
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # App Info
    app_name: str = Field(default="Figma to MiBlock Component Generator")
    app_version: str = Field(default="1.0.0")
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)
    debug: bool = Field(default=False)
    environment: str = Field(default="development")
    
    # Database
    database_host: str = Field(default="localhost")
    database_port: int = Field(default=5432)
    database_name: str = Field(default="miblock_components")
    database_user: str = Field(default="postgres")
    database_password: str = Field(default="")
    database_url: str = Field(default="")
    
    @validator("database_url", pre=True, always=True)
    def assemble_db_url(cls, v, values):
        if v:
            return v
        return (
            f"postgresql://{values.get('database_user')}:"
            f"{values.get('database_password')}@"
            f"{values.get('database_host')}:"
            f"{values.get('database_port')}/"
            f"{values.get('database_name')}"
        )
    
    # Cache (In-Memory)
    cache_ttl: int = Field(default=3600)
    
    # Figma API
    figma_api_token: str = Field(default="")
    figma_api_base_url: str = Field(default="https://api.figma.com/v1")
    
    # CMS API
    cms_api_base_url: str = Field(default="")
    cms_api_key: str = Field(default="")
    cms_api_secret: str = Field(default="")
    
    # Anthropic Claude API
    anthropic_api_key: str = Field(default="")
    anthropic_model: str = Field(default="claude-3-5-sonnet-20241022")
    anthropic_max_tokens: int = Field(default=4096)
    anthropic_temperature: float = Field(default=0.7)
    
    # OpenAI (for CLIP)
    openai_api_key: str = Field(default="")
    
    # Image Processing Thresholds
    image_similarity_threshold: float = Field(default=0.85)
    ssim_threshold: float = Field(default=0.85)
    perceptual_hash_threshold: int = Field(default=5)
    clip_similarity_threshold: float = Field(default=0.90)
    
    # HTML Generation
    html_max_retries: int = Field(default=3)
    html_validation_timeout: int = Field(default=30)
    
    # Component Library
    library_refresh_mode: str = Field(default="incremental")
    components_per_batch: int = Field(default=10)
    max_library_components: int = Field(default=1000)
    
    # Storage
    upload_dir: str = Field(default="./storage/uploads")
    screenshots_dir: str = Field(default="./storage/screenshots")
    results_dir: str = Field(default="./storage/results")
    temp_dir: str = Field(default="./storage/temp")
    max_upload_size: int = Field(default=10485760)  # 10MB
    
    # Logging
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="json")
    log_file: str = Field(default="./logs/app.log")
    
    # Security
    secret_key: str = Field(default="change-this-secret-key-in-production")
    cors_origins: str = Field(default="http://localhost:3000,http://localhost:8000")
    
    @validator("cors_origins", pre=True)
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v
    
    # Rate Limiting
    figma_rate_limit: int = Field(default=60)
    cms_rate_limit: int = Field(default=100)
    claude_rate_limit: int = Field(default=50)
    
    # Agent Configuration
    agent_timeout: int = Field(default=300)
    max_concurrent_agents: int = Field(default=3)
    
    # WebSocket
    ws_heartbeat_interval: int = Field(default=30)
    ws_max_connections: int = Field(default=100)
    
    # Feature Flags
    enable_caching: bool = Field(default=True)
    enable_websocket: bool = Field(default=True)
    enable_metrics: bool = Field(default=True)
    enable_debug_mode: bool = Field(default=False)
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()


# Ensure storage directories exist
def ensure_directories():
    """Create necessary directories if they don't exist"""
    directories = [
        settings.upload_dir,
        settings.screenshots_dir,
        settings.results_dir,
        settings.temp_dir,
        os.path.dirname(settings.log_file),
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)


# Call on import
ensure_directories()


