"""Accessibility scan API (Playwright + axe-core)."""
from flask import Blueprint, request, jsonify

from apps.qa_studio.db.scan_history import save_ada_scan, load_ada_scan
from apps.qa_studio.services.accessibility import (
    run_accessibility_scan,
    report_to_dict,
)
from apps.qa_studio.services.sitemap import fetch_sitemap_urls

accessibility_bp = Blueprint("accessibility", __name__)


@accessibility_bp.route("/sitemap-urls", methods=["GET"])
def get_sitemap_urls():
    """
    Fetch sitemap from url/sitemap.xml and return list of URLs.
    Query: ?url=https://example.com
    """
    url = (request.args.get("url") or "").strip()
    if not url:
        return jsonify({"detail": "url query param required"}), 422
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    urls, err = fetch_sitemap_urls(url)
    if err:
        return jsonify({"urls": [], "error": err}), 200
    return jsonify({"urls": urls, "error": ""})


@accessibility_bp.route("/scan", methods=["POST"])
def scan_url():
    """
    Run accessibility scan on a given URL.
    Body: { "url": "https://example.com" }
    Returns detailed axe-core report (violations, passes, incomplete, summary).
    """
    data = request.get_json()
    if not data:
        return jsonify({"detail": "JSON body required"}), 400
    url = (data.get("url") or "").strip()
    if not url:
        return jsonify({"detail": "url is required"}), 422
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        report = run_accessibility_scan(url)
        return jsonify(report_to_dict(report))
    except Exception as e:
        return jsonify(
            {"detail": str(e), "success": False, "url": url}
        ), 500


@accessibility_bp.route("/load-report", methods=["GET"])
def load_report():
    """
    Load saved ADA scan results for a project.
    Query: ?project_id=...
    """
    project_id = (request.args.get("project_id") or "").strip()
    if not project_id:
        return jsonify({"detail": "project_id query param required"}), 422
    data = load_ada_scan(project_id)
    if not data:
        return jsonify({"urls": [], "results": {}, "aggregate": {}, "sitemap_source": ""}), 200
    return jsonify({
        "urls": data.get("urls", []),
        "results": data.get("results", {}),
        "aggregate": data.get("aggregate", {}),
        "sitemap_source": data.get("sitemap_source", ""),
        "timestamp": data.get("timestamp", ""),
    })


@accessibility_bp.route("/save-report", methods=["POST"])
def save_report():
    """
    Save ADA scan results to project history (overwrites on each run).
    Body: { project_id, urls, results, aggregate, sitemap_source }
    """
    data = request.get_json()
    if not data:
        return jsonify({"detail": "JSON body required"}), 400
    project_id = (data.get("project_id") or "").strip()
    if not project_id:
        return jsonify({"detail": "project_id is required"}), 422
    try:
        save_ada_scan(project_id, {
            "urls": data.get("urls", []),
            "results": data.get("results", {}),
            "aggregate": data.get("aggregate", {}),
            "sitemap_source": data.get("sitemap_source", ""),
        })
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"detail": str(e), "ok": False}), 500
