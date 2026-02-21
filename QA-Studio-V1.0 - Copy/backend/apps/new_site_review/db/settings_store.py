"""GA4 settings storage (per workspace)."""
import json
import re
from pathlib import Path

from apps.new_site_review.models.ga4_settings import GA4Settings, CredentialsType

_DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"
_STORE_PATH = _DATA_DIR / "new_site_review_ga4_settings.json"

# GA4 Property ID is numeric, typically 9+ digits
_GA4_PROPERTY_ID_RE = re.compile(r"^\d{8,}$")


def _load_raw() -> dict:
    if not _STORE_PATH.exists():
        return {}
    raw = _STORE_PATH.read_text(encoding="utf-8")
    return json.loads(raw)


def _save_raw(data: dict) -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    _STORE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def get_ga4_settings(workspace_id: str = "default") -> GA4Settings | None:
    data = _load_raw()
    ws = data.get("workspaces", {}).get(workspace_id)
    if not ws or not ws.get("ga4_property_id"):
        return None
    return GA4Settings(
        ga4_property_id=ws.get("ga4_property_id", ""),
        credentials_type=CredentialsType(ws.get("credentials_type", "OAuth")),
        service_account_json=ws.get("service_account_json") or None,
    )


def save_ga4_settings(
    ga4_property_id: str,
    credentials_type: str,
    service_account_json: str | None = None,
    workspace_id: str = "default",
) -> GA4Settings:
    data = _load_raw()
    if "workspaces" not in data:
        data["workspaces"] = {}
    data["workspaces"][workspace_id] = {
        "ga4_property_id": (ga4_property_id or "").strip(),
        "credentials_type": (credentials_type or "OAuth").strip(),
        "service_account_json": (service_account_json or "").strip() or None,
    }
    _save_raw(data)
    return get_ga4_settings(workspace_id)


def validate_ga4_property_id(property_id: str) -> bool:
    return bool(property_id and _GA4_PROPERTY_ID_RE.match(property_id.strip()))
