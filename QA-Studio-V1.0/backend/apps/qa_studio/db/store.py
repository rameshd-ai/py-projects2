"""Local file storage for projects (no database)."""
import json
from datetime import datetime
from pathlib import Path
from uuid import UUID

from apps.qa_studio.models.project import Project, ProjectPhase

# backend/data/projects.json (store is in apps/qa_studio/db/, so backend is 4 levels up)
_DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"
_STORE_PATH = _DATA_DIR / "projects.json"

def _project_to_dict(p: Project) -> dict:
    return {
        "id": str(p.id),
        "name": p.name,
        "domain_url": p.domain_url,
        "phase": p.phase.value,
        "qa_score": p.qa_score,
        "last_run": p.last_run.isoformat(),
    }


def _dict_to_project(d: dict) -> Project:
    return Project(
        id=UUID(d["id"]),
        name=d["name"],
        domain_url=d["domain_url"],
        phase=ProjectPhase(d["phase"]),
        qa_score=d.get("qa_score", 0),
        last_run=datetime.fromisoformat(d["last_run"]),
    )


def _load() -> dict[UUID, Project]:
    if not _STORE_PATH.exists():
        return {}
    raw = _STORE_PATH.read_text(encoding="utf-8")
    data = json.loads(raw)
    return {UUID(item["id"]): _dict_to_project(item) for item in data.get("projects", [])}


def _save(projects: dict[UUID, Project]) -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    data = {"projects": [_project_to_dict(p) for p in projects.values()]}
    _STORE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


class ProjectStore:
    """Store projects in a local JSON file (no database)."""

    def __init__(self) -> None:
        self._projects: dict[UUID, Project] = _load()

    def _persist(self) -> None:
        _save(self._projects)

    def list_all(self, phase: ProjectPhase | None = None) -> list[Project]:
        items = list(self._projects.values())
        if phase is not None:
            items = [p for p in items if p.phase == phase]
        return sorted(items, key=lambda p: p.last_run, reverse=True)

    def get(self, id: UUID) -> Project | None:
        return self._projects.get(id)

    def create(self, name: str, domain_url: str, phase: ProjectPhase) -> Project:
        project = Project(name=name, domain_url=domain_url, phase=phase)
        self._projects[project.id] = project
        self._persist()
        return project

    def update(self, id: UUID, **kwargs) -> Project | None:
        project = self._projects.get(id)
        if not project:
            return None
        for key, value in kwargs.items():
            if value is not None and hasattr(project, key):
                setattr(project, key, value)
        self._persist()
        return project

    def delete(self, id: UUID) -> bool:
        if id in self._projects:
            del self._projects[id]
            self._persist()
            return True
        return False


project_store = ProjectStore()
