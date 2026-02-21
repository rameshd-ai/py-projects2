"""Sites API for New Site Review."""
from datetime import datetime
from uuid import UUID

from flask import Blueprint, request, jsonify

from apps.new_site_review.db.settings_store import get_ga4_settings
from apps.new_site_review.db.store import site_store
from apps.new_site_review.models.site import SiteType

sites_bp = Blueprint("sites", __name__)


def _to_response(site):
    out = {
        "id": str(site.id),
        "name": site.name,
        "live_url": site.live_url,
        "site_type": site.site_type.value,
    }
    if getattr(site, "last_scan_at", None):
        out["last_scan_at"] = site.last_scan_at.isoformat()
    if getattr(site, "scan_status", None):
        out["scan_status"] = site.scan_status
    if getattr(site, "ga4_results", None):
        out["ga4_results"] = site.ga4_results
    return out


@sites_bp.route("", methods=["GET"])
def list_sites():
    sites = site_store.list_all()
    return jsonify([_to_response(s) for s in sites])


@sites_bp.route("/<site_id>", methods=["GET"])
def get_site(site_id):
    try:
        uid = UUID(site_id)
    except ValueError:
        return jsonify({"detail": "Invalid site id"}), 400
    site = site_store.get(uid)
    if not site:
        return jsonify({"detail": "Site not found"}), 404
    return jsonify(_to_response(site))


@sites_bp.route("", methods=["POST"])
def create_site():
    data = request.get_json()
    if not data:
        return jsonify({"detail": "JSON body required"}), 400
    name = (data.get("name") or "").strip()
    live_url = (data.get("live_url") or "").strip()
    if not name or not live_url:
        return jsonify({"detail": "name and live_url required"}), 422
    site_type_str = (data.get("site_type") or "External").strip()
    try:
        site_type = SiteType(site_type_str)
    except ValueError:
        site_type = SiteType.EXTERNAL
    site = site_store.create(name=name, live_url=live_url, site_type=site_type)
    return jsonify(_to_response(site)), 201


@sites_bp.route("/<site_id>", methods=["PATCH"])
def update_site(site_id):
    try:
        uid = UUID(site_id)
    except ValueError:
        return jsonify({"detail": "Invalid site id"}), 400
    site = site_store.get(uid)
    if not site:
        return jsonify({"detail": "Site not found"}), 404
    data = request.get_json()
    if not data:
        return jsonify({"detail": "JSON body required"}), 400
    updates = {}
    if "name" in data and data["name"] is not None:
        updates["name"] = str(data["name"]).strip()
    if "live_url" in data and data["live_url"] is not None:
        updates["live_url"] = str(data["live_url"]).strip()
    if "site_type" in data and data["site_type"] is not None:
        try:
            updates["site_type"] = SiteType(str(data["site_type"]).strip())
        except ValueError:
            pass
    if not updates:
        return jsonify(_to_response(site))
    updated = site_store.update(uid, **updates)
    return jsonify(_to_response(updated))


@sites_bp.route("/<site_id>", methods=["DELETE"])
def delete_site(site_id):
    try:
        uid = UUID(site_id)
    except ValueError:
        return jsonify({"detail": "Invalid site id"}), 400
    if not site_store.delete(uid):
        return jsonify({"detail": "Site not found"}), 404
    return "", 204


def _mock_ga4_fetch(site):
    """Placeholder: return mock GA4 metrics. Replace with real Google Analytics Data API call."""
    return {
        "sessions": 1250,
        "users": 890,
        "page_views": 4200,
        "events": 8100,
    }


@sites_bp.route("/<site_id>/run", methods=["POST"])
def run_site_scan(site_id):
    try:
        uid = UUID(site_id)
    except ValueError:
        return jsonify({"detail": "Invalid site id"}), 400
    site = site_store.get(uid)
    if not site:
        return jsonify({"detail": "Site not found"}), 404
    ga4 = get_ga4_settings()
    if not ga4 or not ga4.is_configured():
        return jsonify({"detail": "GA4 settings not configured. Open Settings to configure."}), 422
    site_store.update(uid, scan_status="running")
    try:
        metrics = _mock_ga4_fetch(site)
        site_store.update(
            uid,
            scan_status="success",
            last_scan_at=datetime.utcnow(),
            ga4_results=metrics,
        )
        site = site_store.get(uid)
        return jsonify(_to_response(site))
    except Exception as e:
        site_store.update(uid, scan_status="failed")
        return jsonify({"detail": str(e)}), 500
