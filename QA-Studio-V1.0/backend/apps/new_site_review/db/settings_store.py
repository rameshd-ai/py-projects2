"""GA4 and OAuth settings storage (per workspace)."""
import json
import re
from pathlib import Path

from apps.new_site_review.models.ga4_settings import GA4Settings

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
    return GA4Settings(ga4_property_id=ws.get("ga4_property_id", ""))


def save_ga4_settings(
    ga4_property_id: str,
    workspace_id: str = "default",
) -> GA4Settings:
    data = _load_raw()
    if "workspaces" not in data:
        data["workspaces"] = {}
    ws = data["workspaces"].get(workspace_id, {})
    ws["ga4_property_id"] = (ga4_property_id or "").strip()
    data["workspaces"][workspace_id] = ws
    _save_raw(data)
    return get_ga4_settings(workspace_id)


def get_oauth_tokens(workspace_id: str = "default") -> dict | None:
    """Return { refresh_token, access_token?, expiry? } or None."""
    data = _load_raw()
    ws = data.get("workspaces", {}).get(workspace_id)
    if not ws or not ws.get("oauth_refresh_token"):
        return None
    return {
        "refresh_token": ws.get("oauth_refresh_token"),
        "access_token": ws.get("oauth_access_token"),
        "expiry": ws.get("oauth_expiry"),
    }


def save_oauth_tokens(
    refresh_token: str,
    access_token: str | None = None,
    expiry: str | None = None,
    workspace_id: str = "default",
) -> None:
    data = _load_raw()
    if "workspaces" not in data:
        data["workspaces"] = {}
    ws = data["workspaces"].get(workspace_id, {})
    ws["oauth_refresh_token"] = refresh_token or ""
    if access_token is not None:
        ws["oauth_access_token"] = access_token
    if expiry is not None:
        ws["oauth_expiry"] = expiry
    data["workspaces"][workspace_id] = ws
    _save_raw(data)


def validate_ga4_property_id(property_id: str) -> bool:
    return bool(property_id and _GA4_PROPERTY_ID_RE.match(property_id.strip()))
