"""
Pydantic models for test run results and reporting.
"""
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime
from pydantic import BaseModel, Field


class ErrorEntry(BaseModel):
    """Individual error entry."""
    type: str = Field(..., description="Error type (e.g., '404', 'console_error', 'visual_diff')")
    message: str = Field(..., description="Error message")
    url: Optional[str] = Field(default=None, description="URL where error occurred")
    timestamp: datetime = Field(default_factory=datetime.now, description="When error occurred")
    stack_trace: Optional[str] = Field(default=None, description="Stack trace if available")


class PillarResult(BaseModel):
    """Results for a single test pillar."""
    pillar_name: str = Field(..., description="Name of the pillar (e.g., 'ui_responsiveness')")
    pillar_number: int = Field(..., description="Pillar number (1-6)")
    status: Literal["pending", "running", "success", "failed", "warning"] = Field(default="pending")
    errors: List[ErrorEntry] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    metrics: Dict[str, Any] = Field(default_factory=dict, description="Pillar-specific metrics")
    duration: Optional[float] = Field(default=None, description="Execution duration in seconds")


class RunSummary(BaseModel):
    """Overall test run summary."""
    run_id: str = Field(..., description="Unique run identifier (YYYYMMDD_HHMMSS)")
    timestamp: datetime = Field(default_factory=datetime.now)
    status: Literal["pending", "running", "completed", "failed", "cancelled"] = Field(default="pending")
    duration: Optional[float] = Field(default=None, description="Total run duration in seconds")
    config_snapshot: Dict[str, Any] = Field(..., description="Snapshot of TestRunConfig used")
    pillar_results: List[PillarResult] = Field(default_factory=list)
    total_errors: int = Field(default=0)
    total_warnings: int = Field(default=0)
