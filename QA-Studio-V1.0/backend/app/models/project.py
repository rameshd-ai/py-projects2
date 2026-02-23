"""Project domain model."""
from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4


class ProjectPhase(str, Enum):
    """Project QA phase."""

    LIVE = "Live"
    TEST_LINK = "Test Link"
    DEVELOPMENT = "Development"


class Project:
    """Project entity."""

    def __init__(
        self,
        name: str,
        domain_url: str,
        phase: ProjectPhase = ProjectPhase.TEST_LINK,
        qa_score: int | None = None,
        last_run: datetime | None = None,
        id: UUID | None = None,
    ):
        self.id = id or uuid4()
        self.name = name
        self.domain_url = domain_url
        self.phase = phase
        self.qa_score = qa_score if qa_score is not None else 0
        self.last_run = last_run or datetime.utcnow()
