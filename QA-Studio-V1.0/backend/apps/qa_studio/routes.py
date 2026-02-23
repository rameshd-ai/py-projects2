"""QA Studio blueprint: dashboard, project, pillar pages and API."""
import os

from flask import Blueprint, send_file

from apps.qa_studio.routers.projects import projects_bp
from apps.qa_studio.routers.accessibility import accessibility_bp
from apps.qa_studio.routers.responsiveness import responsiveness_bp
from apps.qa_studio.routers.content_quality import content_quality_bp

# Static and HTML under this package
_THIS_DIR = os.path.abspath(os.path.dirname(__file__))
STATIC_DIR = os.path.join(_THIS_DIR, "static")
INDEX_HTML = os.path.join(STATIC_DIR, "index.html")
PROJECT_HTML = os.path.join(STATIC_DIR, "project.html")
PILLAR_HTML = os.path.join(STATIC_DIR, "pillar.html")

qa_studio_bp = Blueprint(
    "qa_studio",
    __name__,
    url_prefix="/qa-studio",
    static_folder=STATIC_DIR,
    static_url_path="/static",
)


@qa_studio_bp.route("/")
def index():
    """QA Studio dashboard."""
    if os.path.isfile(INDEX_HTML):
        return send_file(INDEX_HTML, mimetype="text/html")
    return "<h1>QA Studio</h1><p>Dashboard not found.</p>", 200


@qa_studio_bp.route("/project/<project_id>")
def project_page(project_id):
    """Project detail page."""
    if os.path.isfile(PROJECT_HTML):
        return send_file(PROJECT_HTML, mimetype="text/html")
    return "<h1>Not found</h1>", 404


@qa_studio_bp.route("/project/<project_id>/pillar/<pillar_slug>")
def pillar_page(project_id, pillar_slug):
    """Pillar detail page."""
    if os.path.isfile(PILLAR_HTML):
        return send_file(PILLAR_HTML, mimetype="text/html")
    return "<h1>Not found</h1>", 404


# API under same prefix
qa_studio_bp.register_blueprint(projects_bp, url_prefix="/api/projects")
qa_studio_bp.register_blueprint(accessibility_bp, url_prefix="/api/accessibility")
qa_studio_bp.register_blueprint(responsiveness_bp, url_prefix="/api/responsiveness")
qa_studio_bp.register_blueprint(content_quality_bp, url_prefix="/api/content-quality")


@qa_studio_bp.route("/api/health")
def health():
    return {"status": "ok", "app": "QA Studio"}
