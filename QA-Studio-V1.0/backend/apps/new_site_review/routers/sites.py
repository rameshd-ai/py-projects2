"""Sites API for New Site Review."""
from datetime import datetime
from uuid import UUID

from flask import Blueprint, request, jsonify

from app.config import settings
from apps.new_site_review.db.settings_store import get_ga4_settings
from apps.new_site_review.db.store import site_store
from apps.new_site_review.models.site import SiteType
from apps.new_site_review.routers.auth import get_credentials
from apps.new_site_review.services.export_service import build_export

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
    if getattr(site, "export_download_url", None):
        out["export_download_url"] = site.export_download_url
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


def _login_url():
    base = (settings.app_base_url or "").rstrip("/")
    return f"{base}/new-site-review/api/auth/login"


@sites_bp.route("/<site_id>/run", methods=["POST"])
def run_site_scan(site_id):
    """Export site to Excel (GSC + GA4 + crawl). Requires OAuth login."""
    try:
        uid = UUID(site_id)
    except ValueError:
        return jsonify({"detail": "Invalid site id"}), 400
    site = site_store.get(uid)
    if not site:
        return jsonify({"detail": "Site not found"}), 404
    ga4 = get_ga4_settings()
    if not ga4 or not ga4.is_configured():
        return jsonify({"detail": "GA4 Property ID not configured. Open Settings and enter your GA4 Property ID."}), 422
    creds = get_credentials()
    if not creds:
        return jsonify({
            "detail": "Sign in with Google to export data.",
            "login_required": True,
            "login_url": _login_url(),
        }), 401
    site_store.update(uid, scan_status="running")
    try:
        filename, download_path = build_export(
            site_id=site_id,
            site_name=site.name,
            live_url=site.live_url,
        )
        site_store.update(
            uid,
            scan_status="success",
            last_scan_at=datetime.utcnow(),
            ga4_results={"export": filename},
            export_download_url=download_path,
        )
        site = site_store.get(uid)
        return jsonify({
            **_to_response(site),
            "download_url": download_path,
            "filename": filename,
        })
    except RuntimeError as e:
        msg = str(e)
        if "Not logged in" in msg or "Sign in" in msg:
            site_store.update(uid, scan_status="failed")
            return jsonify({
                "detail": msg,
                "login_required": True,
                "login_url": _login_url(),
            }), 401
        site_store.update(uid, scan_status="failed")
        return jsonify({"detail": msg}), 500
    except Exception as e:
        site_store.update(uid, scan_status="failed")
        return jsonify({"detail": str(e)}), 500
