"""Local file storage for New Site Review sites."""
import json
from datetime import datetime
from pathlib import Path
from uuid import UUID

from apps.new_site_review.models.site import Site, SiteType

_DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"
_STORE_PATH = _DATA_DIR / "new_site_review.json"


def _site_to_dict(s):
    out = {
        "id": str(s.id),
        "name": s.name,
        "live_url": s.live_url,
        "site_type": s.site_type.value,
    }
    if getattr(s, "last_scan_at", None):
        out["last_scan_at"] = s.last_scan_at.isoformat()
    if getattr(s, "scan_status", None):
        out["scan_status"] = s.scan_status
    if getattr(s, "ga4_results", None):
        out["ga4_results"] = s.ga4_results
    return out


def _dict_to_site(d):
    last_scan_at = None
    if d.get("last_scan_at"):
        try:
            last_scan_at = datetime.fromisoformat(d["last_scan_at"].replace("Z", "+00:00"))
        except Exception:
            pass
    return Site(
        id=UUID(d["id"]),
        name=d["name"],
        live_url=d["live_url"],
        site_type=SiteType(d.get("site_type", "External")),
        last_scan_at=last_scan_at,
        scan_status=d.get("scan_status"),
        ga4_results=d.get("ga4_results"),
    )


def _load():
    if not _STORE_PATH.exists():
        return {}
    raw = _STORE_PATH.read_text(encoding="utf-8")
    data = json.loads(raw)
    return {UUID(item["id"]): _dict_to_site(item) for item in data.get("sites", [])}


def _save(sites):
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    data = {"sites": [_site_to_dict(s) for s in sites.values()]}
    _STORE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


class SiteStore:
    def __init__(self):
        self._sites = _load()

    def _persist(self):
        _save(self._sites)

    def list_all(self):
        return sorted(self._sites.values(), key=lambda s: s.name.lower())

    def get(self, id):
        return self._sites.get(id)

    def create(self, name, live_url, site_type=SiteType.EXTERNAL):
        site = Site(name=name, live_url=live_url, site_type=site_type)
        self._sites[site.id] = site
        self._persist()
        return site

    def update(self, id, **kwargs):
        site = self._sites.get(id)
        if not site:
            return None
        if "site_type" in kwargs and isinstance(kwargs["site_type"], str):
            kwargs["site_type"] = SiteType(kwargs["site_type"])
        for key, value in kwargs.items():
            if value is not None and hasattr(site, key):
                setattr(site, key, value)
        self._persist()
        return site

    def delete(self, id):
        if id in self._sites:
            del self._sites[id]
            self._persist()
            return True
        return False


site_store = SiteStore()
