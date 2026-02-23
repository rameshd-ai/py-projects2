"""Flask application entry point — launcher at / and app blueprints."""
import os

from flask import Flask, send_file

from app.config import settings
from apps.qa_studio.routes import qa_studio_bp
from apps.new_site_review.routes import new_site_review_bp

STATIC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "static"))
LAUNCHER_HTML = os.path.join(STATIC_DIR, "launcher.html")

app = Flask(__name__)
app.config["DEBUG"] = settings.debug

# Root: app chooser
@app.route("/")
def index():
    """Serve the app launcher (choose QA Studio or other apps)."""
    if os.path.isfile(LAUNCHER_HTML):
        return send_file(LAUNCHER_HTML, mimetype="text/html")
    return "<h1>Backend</h1><p><a href=\"/qa-studio/\">QA Studio</a></p>", 200

app.register_blueprint(qa_studio_bp)
app.register_blueprint(new_site_review_bp)
