"""Save accessibility scan results to project history (within qa_studio app data folder)."""
import json
from datetime import datetime
from pathlib import Path
from uuid import UUID

# backend/data/qa_studio/history/{project_id}/ada_scan.json
_BASE_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "data"
    / "qa_studio"
    / "history"
)


def _project_history_dir(project_id: str | UUID) -> Path:
    """Get project history directory (within respective app folder)."""
    pid = str(project_id)
    return _BASE_DIR / pid


def save_ada_scan(project_id: str | UUID, data: dict) -> None:
    """
    Save ADA accessibility scan results. Overwrites on each run.
    """
    dir_path = _project_history_dir(project_id)
    dir_path.mkdir(parents=True, exist_ok=True)
    file_path = dir_path / "ada_scan.json"
    payload = {
        "project_id": str(project_id),
        "timestamp": datetime.utcnow().isoformat() + "Z",
        **data,
    }
    file_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_ada_scan(project_id: str | UUID) -> dict | None:
    """Load latest ADA scan for project, or None if none saved."""
    file_path = _project_history_dir(project_id) / "ada_scan.json"
    if not file_path.exists():
        return None
    raw = file_path.read_text(encoding="utf-8")
    return json.loads(raw)


def save_responsiveness_scan(project_id: str | UUID, data: dict) -> None:
    """Save Responsiveness scan results. Overwrites on each run."""
    dir_path = _project_history_dir(project_id)
    dir_path.mkdir(parents=True, exist_ok=True)
    file_path = dir_path / "responsiveness_scan.json"
    payload = {
        "project_id": str(project_id),
        "timestamp": datetime.utcnow().isoformat() + "Z",
        **data,
    }
    file_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_responsiveness_scan(project_id: str | UUID) -> dict | None:
    """Load latest Responsiveness scan for project, or None if none saved."""
    file_path = _project_history_dir(project_id) / "responsiveness_scan.json"
    if not file_path.exists():
        return None
    raw = file_path.read_text(encoding="utf-8")
    return json.loads(raw)


def save_content_quality_scan(project_id: str | UUID, data: dict) -> None:
    """Save Content Quality scan results. Overwrites on each run."""
    dir_path = _project_history_dir(project_id)
    dir_path.mkdir(parents=True, exist_ok=True)
    file_path = dir_path / "content_quality_scan.json"
    payload = {
        "project_id": str(project_id),
        "timestamp": datetime.utcnow().isoformat() + "Z",
        **data,
    }
    file_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_content_quality_scan(project_id: str | UUID) -> dict | None:
    """Load latest Content Quality scan for project, or None if none saved."""
    file_path = _project_history_dir(project_id) / "content_quality_scan.json"
    if not file_path.exists():
        return None
    raw = file_path.read_text(encoding="utf-8")
    return json.loads(raw)
