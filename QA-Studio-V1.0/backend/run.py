"""Run the Flask app (use this if 'flask' CLI is not found)."""
from app.main import app

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8001, debug=False, use_reloader=False)
