"""Flask application entry point."""
import os

from flask import Flask, send_file, send_from_directory

from app.config import settings
from app.routers.projects import projects_bp

# Serve dashboard from backend/static (HTML, CSS, JS)
STATIC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "static"))
INDEX_HTML = os.path.join(STATIC_DIR, "index.html")

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="/static")
app.config["DEBUG"] = settings.debug

# Dashboard first so "/" is always the app
@app.route("/")
def index():
    """Serve the dashboard."""
    if os.path.isfile(INDEX_HTML):
        return send_file(INDEX_HTML, mimetype="text/html")
    return "<h1>QA Studio</h1><p>Dashboard not found. Check backend/static/index.html</p>", 200


@app.route("/project/<project_id>")
def project_page(project_id):
    """Serve the project detail page."""
    project_html = os.path.join(STATIC_DIR, "project.html")
    if os.path.isfile(project_html):
        return send_file(project_html, mimetype="text/html")
    return "<h1>Not found</h1>", 404


@app.route("/project/<project_id>/pillar/<pillar_slug>")
def pillar_page(project_id, pillar_slug):
    """Serve the pillar detail page (full page, not modal)."""
    pillar_html = os.path.join(STATIC_DIR, "pillar.html")
    if os.path.isfile(pillar_html):
        return send_file(pillar_html, mimetype="text/html")
    return "<h1>Not found</h1>", 404


app.register_blueprint(projects_bp, url_prefix="/api/projects")


@app.route("/api/health")
def health():
    """Health check endpoint."""
    return {"status": "ok"}
