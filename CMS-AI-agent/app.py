"""
Flask UI for CMS-AI-agent.

Enter CMS base URL to generate token or download training data.
"""

import atexit
import logging
import json
import os
import re
import signal
import shutil
import subprocess
import sys
from pathlib import Path

# Track background download process so it's killed when server stops
_download_proc = None


def _kill_download_proc():
    """Kill background download process (and its children) when server stops."""
    global _download_proc
    if _download_proc and _download_proc.poll() is None:
        try:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(_download_proc.pid)],
                    capture_output=True,
                    timeout=5,
                )
            else:
                _download_proc.terminate()
                try:
                    _download_proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    _download_proc.kill()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            try:
                _download_proc.kill()
            except Exception:
                pass
        _download_proc = None

# Ensure project root is in path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from flask import Flask, jsonify, render_template, request, redirect, url_for, flash

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key-change-in-production")


@app.route("/")
def index():
    """Home page with AI agent description."""
    return render_template("index.html")


PROJECT_ROOT = Path(__file__).resolve().parent
TRAINING_DIR = PROJECT_ROOT / "output" / "training"
PROGRESS_FILE = TRAINING_DIR / "download_progress.json"
LAST_SITES_FILE = TRAINING_DIR / "last_sites.json"
DOWNLOAD_SUMMARY_FILE = TRAINING_DIR / "download_summary.json"

# Ensure training folder exists as soon as app loads (so all training paths use it)
TRAINING_DIR.mkdir(parents=True, exist_ok=True)


def _site_url_to_slug(site_url: str) -> str:
    """Same slug logic as process: safe folder name from site URL."""
    if not site_url or not isinstance(site_url, str):
        return ""
    slug = re.sub(r"^https?://", "", site_url.strip().rstrip("/"))
    slug = re.sub(r"[^\w\-.]", "_", slug)
    return slug.strip("_")[:80] or "cms_data"


def _load_last_sites():
    """Load last submitted site details for pre-fill."""
    if not LAST_SITES_FILE.exists():
        return []
    try:
        with open(LAST_SITES_FILE) as f:
            data = json.load(f)
        return data.get("sites", [])
    except (json.JSONDecodeError, IOError):
        return []


def _save_last_sites(sites: list):
    """Save site details for pre-fill on refresh."""
    TRAINING_DIR.mkdir(parents=True, exist_ok=True)
    with open(LAST_SITES_FILE, "w") as f:
        json.dump({"sites": sites}, f, indent=2)


@app.route("/api/download-progress")
def download_progress():
    """Return current download progress and last completed summary for UI polling."""
    data = {"status": "idle"}
    if PROGRESS_FILE.exists():
        try:
            with open(PROGRESS_FILE) as f:
                data = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    # Include last completed summary (persists after refresh)
    if DOWNLOAD_SUMMARY_FILE.exists():
        try:
            with open(DOWNLOAD_SUMMARY_FILE) as f:
                data["last_completed"] = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return jsonify(data)


@app.route("/training")
def training():
    """Training page with CMS URL form."""
    step = request.args.get("step", type=int, default=1)
    last_sites = _load_last_sites()
    return render_template("training.html", initial_step=step, last_sites=last_sites)


@app.route("/submit", methods=["POST"])
def submit():
    """Generate tokens for each site and save to output folder."""
    cms_urls = request.form.getlist("cms_url")
    profile_aliases = request.form.getlist("profile_alias")

    sites = []
    for i in range(len(cms_urls)):
        url = (cms_urls[i] or "").strip().rstrip("/")
        alias = (profile_aliases[i] if i < len(profile_aliases) else "").strip() or "default"
        if url:
            if not url.startswith(("http://", "https://")):
                url = "https://" + url
            sites.append((url, alias))

    if not sites:
        flash("Please enter at least one CMS URL.", "error")
        return redirect(url_for("training"))

    # Persist site details for pre-fill on refresh
    _save_last_sites([{"cms_url": u, "profile_alias": a} for u, a in sites])

    from helper_functions.login_token import generate_and_save_token

    TRAINING_DIR.mkdir(parents=True, exist_ok=True)
    training_dir_str = str(TRAINING_DIR.resolve())
    success_count = 0
    errors = []
    for cms_url, profile_alias in sites:
        try:
            result = generate_and_save_token(cms_url, profile_alias, output_folder=training_dir_str)
            if result:
                success_count += 1
            else:
                errors.append(cms_url)
        except Exception:
            errors.append(cms_url)

    if success_count > 0 and not errors:
        flash("Tokens saved", "success")
    elif errors and success_count == 0:
        flash("Token generation failed", "error")
    elif errors:
        flash("Some tokens failed", "error")

    # Fetch GetSiteVComponents and VComponent pages (HTML + PNG) for each site
    if success_count > 0:
        try:
            from process.process_01_download_cms_data import fetch_vcomponents_for_all_sites

            vcomp_results = fetch_vcomponents_for_all_sites(output_folder=training_dir_str)
            vcomp_ok = sum(1 for r in vcomp_results if "count" in r)
            if vcomp_ok == len(vcomp_results):
                flash("Components fetched", "success")
            elif vcomp_ok > 0:
                flash("Components partially fetched", "error")
            else:
                flash("Components fetch failed", "error")

            # Fetch HTML and PNG for each VComponent (run via poetry to ensure Playwright is available)
            global _download_proc
            if _download_proc is not None and _download_proc.poll() is None:
                flash("Download already running", "error")
                return redirect(url_for("training", step=2))
            log_file = TRAINING_DIR / "download_pages.log"
            TRAINING_DIR.mkdir(parents=True, exist_ok=True)
            progress_file = str(PROGRESS_FILE)
            PROGRESS_FILE.write_text(json.dumps({"status": "starting", "site_url": "", "current": 0, "total": 0, "fetched": 0, "failed": 0}))
            output_dir = str(TRAINING_DIR.resolve())
            _download_proc = subprocess.Popen(
                ["poetry", "run", "python", "-m", "process.process_01_download_cms_data", "--pages", "--output-dir", output_dir, "--progress-file", progress_file],
                cwd=str(PROJECT_ROOT),
                stdout=open(log_file, "w"),
                stderr=subprocess.STDOUT,
            )
            flash("Download started", "success")
            return redirect(url_for("training", step=2))
        except Exception as e:
            flash("Download failed", "error")

    return redirect(url_for("training"))


@app.route("/api/delete-site", methods=["POST"])
def api_delete_site():
    """Delete one site's folder under output/training (by CMS URL). Called when user removes a site from Step 1."""
    data = request.get_json(silent=True) or {}
    cms_url = (data.get("cms_url") or request.form.get("cms_url") or "").strip().rstrip("/")
    if not cms_url:
        return jsonify({"ok": False, "error": "cms_url required"}), 400
    if not cms_url.startswith(("http://", "https://")):
        cms_url = "https://" + cms_url
    slug = _site_url_to_slug(cms_url)
    if not slug:
        return jsonify({"ok": False, "error": "invalid url"}), 400
    # Try output/training/<slug> first, then legacy output/<slug>
    site_folder = TRAINING_DIR / slug
    if not site_folder.is_dir():
        site_folder = PROJECT_ROOT / "output" / slug
    deleted_folder = False
    if site_folder.is_dir():
        try:
            shutil.rmtree(site_folder)
            deleted_folder = True
        except OSError as e:
            return jsonify({"ok": False, "error": str(e)}), 500
    # Remove this site from login_token.json so tokens stay in sync
    token_file = TRAINING_DIR / "login_token.json"
    if token_file.exists():
        try:
            with open(token_file) as f:
                token_data = json.load(f)
            sites = token_data.get("sites", [])
            norm = cms_url.lower().rstrip("/")
            token_data["sites"] = [s for s in sites if (s.get("site_url") or "").strip().rstrip("/").lower() != norm]
            with open(token_file, "w") as f:
                json.dump(token_data, f, indent=2)
        except (json.JSONDecodeError, IOError):
            pass
    # Remove this site from last_sites.json so it doesn't reappear on refresh
    if LAST_SITES_FILE.exists():
        try:
            with open(LAST_SITES_FILE) as f:
                last_data = json.load(f)
            last_sites = last_data.get("sites", [])
            norm = cms_url.lower().rstrip("/")
            last_data["sites"] = [s for s in last_sites if (s.get("cms_url") or "").strip().rstrip("/").lower() != norm]
            with open(LAST_SITES_FILE, "w") as f:
                json.dump(last_data, f, indent=2)
        except (json.JSONDecodeError, IOError):
            pass
    # Clear progress and summary so Step 2 shows Idle (no stale data from deleted site)
    for p in (PROGRESS_FILE, DOWNLOAD_SUMMARY_FILE):
        if p.exists():
            try:
                p.unlink()
            except OSError:
                pass
    return jsonify({"ok": True, "deleted": deleted_folder})


@app.route("/delete-downloaded", methods=["POST"])
def delete_downloaded():
    """Delete entire site folders under output/training (all downloaded data per site)."""
    deleted_sites = 0
    if TRAINING_DIR.exists():
        for path in TRAINING_DIR.iterdir():
            if path.is_dir():
                try:
                    shutil.rmtree(path)
                    deleted_sites += 1
                except OSError:
                    pass
    # Clear progress and summary so UI shows Idle
    for p in (PROGRESS_FILE, DOWNLOAD_SUMMARY_FILE):
        if p.exists():
            try:
                p.unlink()
            except OSError:
                pass
    flash(f"Deleted {deleted_sites} site folder(s)", "success")
    return redirect(url_for("training", step=2))


@app.route("/cancel-download", methods=["POST"])
def cancel_download():
    """Stop the running download process."""
    _kill_download_proc()
    flash("Download stopped", "success")
    return redirect(url_for("training", step=2))


@app.route("/retry-download", methods=["POST"])
def retry_download():
    """Retry downloading only failed VComponents (missing HTML or PNG)."""
    global _download_proc
    if _download_proc is not None and _download_proc.poll() is None:
        flash("Download already running", "error")
        return redirect(url_for("training", step=2))
    log_file = TRAINING_DIR / "download_pages.log"
    TRAINING_DIR.mkdir(parents=True, exist_ok=True)
    progress_file = str(PROGRESS_FILE)
    PROGRESS_FILE.write_text(json.dumps({"status": "starting", "site_url": "", "current": 0, "total": 0, "fetched": 0, "failed": 0}))

    output_dir = str(TRAINING_DIR.resolve())
    _download_proc = subprocess.Popen(
        ["poetry", "run", "python", "-m", "process.process_01_download_cms_data", "--pages", "--retry-failed", "--output-dir", output_dir, "--progress-file", progress_file],
        cwd=str(PROJECT_ROOT),
        stdout=open(log_file, "w"),
        stderr=subprocess.STDOUT,
    )
    flash("Retrying failed downloads", "success")
    return redirect(url_for("training", step=2))


def _signal_handler(signum, frame):
    """Kill download subprocess on Ctrl+C / SIGTERM so terminal exits cleanly."""
    _kill_download_proc()
    sys.exit(0)


try:
    signal.signal(signal.SIGINT, _signal_handler)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _signal_handler)
except (ValueError, OSError):
    pass  # May fail in non-main thread


def _check_playwright():
    """Verify Playwright is available (used for VComponent HTML/PNG download)."""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
    except Exception as e:
        print(f"[WARN] Playwright check failed: {e}")
        print("       VComponent pages (HTML+PNG) will fail. Run: poetry run python -m playwright install chromium")


if __name__ == "__main__":
    _check_playwright()
    # Suppress 200 logs for /api/download-progress to reduce terminal spam from polling
    class _SuppressProgressPollFilter(logging.Filter):
        def filter(self, record):
            msg = str(getattr(record, "msg", ""))
            return "download-progress" not in msg or "200" not in msg
    logging.getLogger("werkzeug").addFilter(_SuppressProgressPollFilter())
    # use_reloader=False so atexit runs when server stops (kills background download)
    app.run(debug=True, port=5000, use_reloader=False)
