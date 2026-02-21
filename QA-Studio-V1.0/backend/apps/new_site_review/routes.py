"""New Site Review blueprint: dashboard and API."""
import os

from flask import Blueprint, send_file

from apps.new_site_review.routers.sites import sites_bp
from apps.new_site_review.routers.settings import settings_bp

_THIS_DIR = os.path.abspath(os.path.dirname(__file__))
STATIC_DIR = os.path.join(_THIS_DIR, "static")
INDEX_HTML = os.path.join(STATIC_DIR, "index.html")

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


@new_site_review_bp.route("/api/health")
def health():
    return {"status": "ok", "app": "New Site Review"}
