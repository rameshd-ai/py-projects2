"""Project API schemas."""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from apps.qa_studio.models.project import ProjectPhase


class ProjectCreate(BaseModel):
    """Payload for creating a project."""

    name: str | None = Field(None, max_length=255)
    domain_url: str = Field(..., min_length=1)
    phase: ProjectPhase = ProjectPhase.TEST_LINK


class ProjectUpdate(BaseModel):
    """Payload for updating a project (partial)."""

    name: str | None = Field(None, min_length=1, max_length=255)
    domain_url: str | None = None
    phase: ProjectPhase | None = None
    qa_score: int | None = Field(None, ge=0, le=100)


class ProjectResponse(BaseModel):
    """Project as returned by the API."""

    id: UUID
    name: str
    domain_url: str
    phase: ProjectPhase
    qa_score: int
    last_run: datetime

    model_config = {"from_attributes": True}
