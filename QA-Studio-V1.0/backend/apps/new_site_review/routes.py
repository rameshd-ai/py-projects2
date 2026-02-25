"""New Site Review blueprint: dashboard and API."""
import os
from pathlib import Path

from flask import Blueprint, send_file, abort

from apps.new_site_review.routers.sites import sites_bp
from apps.new_site_review.routers.settings import settings_bp
from apps.new_site_review.routers.auth import auth_bp

_THIS_DIR = os.path.abspath(os.path.dirname(__file__))
STATIC_DIR = os.path.join(_THIS_DIR, "static")
INDEX_HTML = os.path.join(_THIS_DIR, "static", "index.html")
_EXPORTS_DIR = Path(_THIS_DIR).resolve().parent.parent.parent / "data" / "exports"

new_site_review_bp = Blueprint(
    "new_site_review",
    __name__,
    url_prefix="/new-site-review",
    static_folder=STATIC_DIR,
    static_url_path="/static",
)


@new_site_review_bp.route("/")
def index():
    if os.path.isfile(INDEX_HTML):
        return send_file(INDEX_HTML, mimetype="text/html")
    return "<h1>New Site Review</h1><p>Dashboard not found.</p>", 200


new_site_review_bp.register_blueprint(sites_bp, url_prefix="/api/sites")
new_site_review_bp.register_blueprint(settings_bp, url_prefix="/api/settings")
new_site_review_bp.register_blueprint(auth_bp, url_prefix="/api/auth")


@new_site_review_bp.route("/downloads/<path:filename>", methods=["GET"])
def download_export(filename):
    """Serve exported Excel file. Filename must be safe (no path traversal)."""
    if ".." in filename or "/" in filename or "\\" in filename:
        abort(404)
    path = _EXPORTS_DIR / filename
    if not path.is_file():
        abort(404)
    return send_file(path, as_attachment=True, download_name=filename)


@new_site_review_bp.route("/api/health")
def health():
    return {"status": "ok", "app": "New Site Review"}
