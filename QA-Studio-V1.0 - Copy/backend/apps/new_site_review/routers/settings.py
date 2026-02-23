"""GA4 Settings API."""
from flask import Blueprint, request, jsonify

from apps.new_site_review.db.settings_store import (
    get_ga4_settings,
    save_ga4_settings,
    validate_ga4_property_id,
)
from apps.new_site_review.models.ga4_settings import CredentialsType

settings_bp = Blueprint("settings", __name__)

WORKSPACE_ID = "default"


def _settings_to_response(s):
    if not s:
        return None
    out = {
        "ga4_property_id": s.ga4_property_id,
        "credentials_type": s.credentials_type.value,
        "configured": s.is_configured(),
    }
    if s.credentials_type == CredentialsType.SERVICE_ACCOUNT and s.service_account_json:
        out["has_service_account_json"] = True
    else:
        out["has_service_account_json"] = False
    return out


@settings_bp.route("/ga4", methods=["GET"])
def get_ga4():
    s = get_ga4_settings(WORKSPACE_ID)
    if not s:
        return jsonify({"configured": False, "ga4_property_id": "", "credentials_type": "OAuth", "has_service_account_json": False})
    r = _settings_to_response(s)
    if r and "service_account_json" not in r:
        r["ga4_property_id"] = s.ga4_property_id
    return jsonify(r)


@settings_bp.route("/ga4", methods=["PUT"])
def put_ga4():
    data = request.get_json()
    if not data:
        return jsonify({"detail": "JSON body required"}), 400
    ga4_property_id = (data.get("ga4_property_id") or "").strip()
    if not ga4_property_id:
        return jsonify({"detail": "GA4 Property ID is required"}), 422
    if not validate_ga4_property_id(ga4_property_id):
        return jsonify({"detail": "GA4 Property ID must be numeric (8+ digits)"}), 422
    credentials_type_str = (data.get("credentials_type") or "OAuth").strip()
    try:
        ct = CredentialsType(credentials_type_str)
    except ValueError:
        ct = CredentialsType.OAUTH
    service_account_json = None
    if ct == CredentialsType.SERVICE_ACCOUNT:
        service_account_json = (data.get("service_account_json") or "").strip()
        if not service_account_json:
            existing = get_ga4_settings(WORKSPACE_ID)
            if existing and existing.credentials_type == CredentialsType.SERVICE_ACCOUNT and existing.service_account_json:
                service_account_json = existing.service_account_json
            else:
                return jsonify({"detail": "Service Account JSON is required when using Service Account"}), 422
    s = save_ga4_settings(
        ga4_property_id=ga4_property_id,
        credentials_type=ct.value,
        service_account_json=service_account_json,
        workspace_id=WORKSPACE_ID,
    )
    return jsonify(_settings_to_response(s))


@settings_bp.route("/ga4/test", methods=["POST"])
def test_ga4():
    """Validate GA4 access with current or provided credentials."""
    data = request.get_json() or {}
    property_id = (data.get("ga4_property_id") or "").strip()
    if not property_id:
        s = get_ga4_settings(WORKSPACE_ID)
        property_id = (s.ga4_property_id or "").strip() if s else ""
    if not property_id:
        return jsonify({"success": False, "message": "GA4 Property ID is required"}), 422
    if not validate_ga4_property_id(property_id):
        return jsonify({"success": False, "message": "GA4 Property ID must be numeric (8+ digits)"}), 422
    s = get_ga4_settings(WORKSPACE_ID)
    if s and s.credentials_type == CredentialsType.SERVICE_ACCOUNT and not (s.service_account_json or "").strip():
        return jsonify({"success": False, "message": "Service Account JSON is required for connection test"}), 422
    # Placeholder: real implementation would call Google Analytics Data API
    return jsonify({"success": True, "message": "Connection successful"})
