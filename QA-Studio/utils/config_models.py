"""
Pydantic models for test configuration validation.
"""
from typing import List, Optional, Literal
from pydantic import BaseModel, HttpUrl, Field, field_validator


class DeviceProfile(BaseModel):
    """Device/viewport configuration."""
    name: str
    viewport_width: int
    viewport_height: int
    user_agent: Optional[str] = None


class SEOConfig(BaseModel):
    """SEO validation rules."""
    max_h1_count: int = Field(default=1, ge=0, description="Maximum allowed H1 tags per page")
    min_meta_length: int = Field(default=120, ge=0, description="Minimum meta description length")
    max_meta_length: int = Field(default=160, ge=0, description="Maximum meta description length")
    require_alt_tags: bool = Field(default=True, description="Require alt text on all images")
    require_schema: bool = Field(default=False, description="Require Schema.org JSON-LD")


class TestRunConfig(BaseModel):
    """Main test run configuration."""
    base_url: HttpUrl = Field(..., description="Base URL to test")
    sitemap_url: Optional[HttpUrl] = Field(default=None, description="Sitemap URL (defaults to {base_url}/sitemap.xml)")
    browsers: List[Literal["chromium", "firefox", "webkit"]] = Field(default_factory=lambda: ["chromium"], description="Browsers to test")
    devices: List[str] = Field(default_factory=lambda: ["desktop"], description="Device profiles to test")
    pillars: List[int] = Field(..., min_length=1, max_length=6, description="Test pillars to execute (1-6)")
    seo_config: Optional[SEOConfig] = Field(default_factory=SEOConfig, description="SEO validation rules")
    
    @field_validator('sitemap_url', mode='before')
    @classmethod
    def default_sitemap_url(cls, v, info):
        """Set default sitemap URL if not provided."""
        if v is None and 'base_url' in info.data:
            base = str(info.data['base_url']).rstrip('/')
            return f"{base}/sitemap.xml"
        return v
    
    @field_validator('devices')
    @classmethod
    def validate_devices(cls, v):
        """Validate device names."""
        valid_devices = ["desktop", "tablet", "mobile"]
        for device in v:
            if device not in valid_devices:
                raise ValueError(f"Invalid device: {device}. Must be one of {valid_devices}")
        return v
    
    @field_validator('pillars')
    @classmethod
    def validate_pillars(cls, v):
        """Validate pillar numbers."""
        for pillar in v:
            if not (1 <= pillar <= 6):
                raise ValueError(f"Invalid pillar: {pillar}. Must be between 1 and 6")
        return sorted(set(v))  # Remove duplicates and sort


# Predefined device profiles
DEVICE_PROFILES = {
    "desktop": DeviceProfile(
        name="desktop",
        viewport_width=1920,
        viewport_height=1080,
        user_agent=None
    ),
    "tablet": DeviceProfile(
        name="tablet",
        viewport_width=768,
        viewport_height=1024,
        user_agent=None
    ),
    "mobile": DeviceProfile(
        name="mobile",
        viewport_width=375,
        viewport_height=667,
        user_agent=None
    )
}
