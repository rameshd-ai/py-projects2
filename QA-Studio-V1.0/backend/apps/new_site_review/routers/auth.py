"""Google OAuth: login and callback for GSC + GA4 access."""
from flask import Blueprint, redirect, request, jsonify
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from app.config import settings
from apps.new_site_review.db.settings_store import get_oauth_tokens, save_oauth_tokens

auth_bp = Blueprint("auth", __name__)

WORKSPACE_ID = "default"

SCOPES = [
    "https://www.googleapis.com/auth/webmasters.readonly",
    "https://www.googleapis.com/auth/analytics.readonly",
]


def _redirect_uri():
    base = (settings.app_base_url or "").rstrip("/")
    return f"{base}/new-site-review/api/auth/callback"


def _get_flow():
    return Flow.from_client_config(
        {
            "web": {
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [_redirect_uri()],
            }
        },
        scopes=SCOPES,
        redirect_uri=_redirect_uri(),
    )


@auth_bp.route("/login", methods=["GET"])
def login():
    """Redirect to Google sign-in."""
    if not settings.google_client_id or not settings.google_client_secret:
        return jsonify({"detail": "Google OAuth not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET."}), 503
    flow = _get_flow()
    authorization_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        include_granted_scopes="true",
    )
    return redirect(authorization_url)


@auth_bp.route("/callback", methods=["GET"])
def callback():
    """Exchange code for tokens and store refresh_token."""
    if not settings.google_client_id or not settings.google_client_secret:
        return redirect("/new-site-review/?error=oauth_not_configured")
    code = request.args.get("code")
    if not code:
        return redirect("/new-site-review/?error=no_code")
    flow = _get_flow()
    try:
        flow.fetch_token(code=code)
        creds = flow.credentials
        save_oauth_tokens(
            refresh_token=creds.refresh_token or "",
            access_token=creds.token,
            expiry=creds.expiry.isoformat() if creds.expiry else None,
            workspace_id=WORKSPACE_ID,
        )
    except Exception:
        return redirect("/new-site-review/?error=token_exchange_failed")
    return redirect("/new-site-review/?logged_in=1")


@auth_bp.route("/status", methods=["GET"])
def status():
    """Return whether user has valid OAuth (refresh token stored)."""
    tokens = get_oauth_tokens(WORKSPACE_ID)
    has_refresh = bool(tokens and tokens.get("refresh_token"))
    return jsonify({"logged_in": has_refresh})


def get_credentials():
    """Return Google Credentials for API calls; refresh if needed."""
    from datetime import datetime, timezone
    tokens = get_oauth_tokens(WORKSPACE_ID)
    if not tokens or not tokens.get("refresh_token"):
        return None
    expiry = None
    if tokens.get("expiry"):
        try:
            expiry = datetime.fromisoformat(tokens["expiry"].replace("Z", "+00:00"))
        except Exception:
            pass
    creds = Credentials(
        token=tokens.get("access_token"),
        refresh_token=tokens.get("refresh_token"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        scopes=SCOPES,
    )
    if expiry:
        creds.expiry = expiry
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        save_oauth_tokens(
            refresh_token=creds.refresh_token or tokens["refresh_token"],
            access_token=creds.token,
            expiry=creds.expiry.isoformat() if creds.expiry else None,
            workspace_id=WORKSPACE_ID,
        )
    return creds
