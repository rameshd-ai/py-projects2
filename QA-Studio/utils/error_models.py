"""
Error classification and response models.
"""
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field
from .report_models import ErrorEntry


class ErrorResponse(BaseModel):
    """Error response for a test phase/pillar."""
    phase: str = Field(..., description="Phase name (e.g., 'ui_responsiveness', 'site_structure')")
    status: Literal["pending", "running", "success", "failed", "warning"] = Field(default="pending")
    message: str = Field(..., description="Human-readable summary")
    errors: List[ErrorEntry] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    metrics: Dict[str, Any] = Field(default_factory=dict, description="Phase-specific metrics")
