"""
Login Token Generator - Reusable function for CMS authentication.

Uses apis.generate_cms_token to generate JWT tokens for any CMS URL.
Use this from the Flask app, CLI, or when asked to generate a token.

Usage:
    # Programmatic - generate and save (same function used everywhere):
    from helper_functions.login_token import generate_and_save_token

    result = generate_and_save_token(cms_url="https://...", profile_alias="123.45")

    # CLI:
    python -m helper_functions.login_token https://example.cms.com 123.45

    # Or just get token/headers (no save):
    from helper_functions.login_token import login_and_get_token, get_auth_headers
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional

# Add parent directory for apis import
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from apis import generate_cms_token

logger = logging.getLogger(__name__)

OUTPUT_FOLDER = os.environ.get("CMS_OUTPUT_FOLDER", "output")
TOKEN_FILENAME = "login_token.json"


def login_and_get_token(cms_url: str, profile_alias: str = "default") -> Optional[dict]:
    """
    Login to CMS and generate authentication token.

    Args:
        cms_url: Base URL of the CMS instance (e.g., https://example.cms.milestoneinternet.info)
        profile_alias: Profile alias for token generation

    Returns:
        dict: Token response from API, or None if failed.
    """
    return generate_cms_token(cms_url.rstrip("/"), profile_alias)


def extract_token(token_response: dict) -> Optional[str]:
    """
    Extract token string from API response (supports multiple key names).

    Args:
        token_response: Raw response from token API

    Returns:
        str: Token string, or None if not found.
    """
    if not token_response:
        return None
    return (
        token_response.get("token")
        or token_response.get("Token")
        or token_response.get("access_token")
        or token_response.get("AccessToken")
        or token_response.get("cmsToken")
        or token_response.get("CMSToken")
    )


def get_auth_headers(token_data: dict) -> dict:
    """
    Build authorization headers from token response for use in CMS API calls.

    Args:
        token_data: Response from login_and_get_token(). Expects a "token" key or similar.

    Returns:
        dict: Headers with Authorization and Content-Type for API requests.
    """
    if not token_data:
        return {"Content-Type": "application/json"}

    token = extract_token(token_data)

    if not token:
        logger.warning("Token data did not contain expected token field.")
        token = token_data if isinstance(token_data, str) else ""

    return {
        "Authorization": f"Bearer {token}" if token else "",
        "Content-Type": "application/json",
    }


def login_and_get_headers(cms_url: str, profile_alias: str = "default") -> Optional[dict]:
    """
    Convenience: Login and return ready-to-use auth headers in one call.

    Args:
        cms_url: Base URL of the CMS instance
        profile_alias: Profile alias for token generation

    Returns:
        dict: Headers for CMS API calls, or None if login failed.
    """
    token_data = login_and_get_token(cms_url=cms_url, profile_alias=profile_alias)
    if not token_data:
        return None
    return get_auth_headers(token_data)


def generate_and_save_token(
    cms_url: str,
    profile_alias: str = "default",
    output_folder: Optional[str] = None,
) -> Optional[dict]:
    """
    Generate token and save to output folder.
    Use this from Flask app, CLI, or when asked to generate a token.

    Args:
        cms_url: Base URL of the CMS instance
        profile_alias: Profile alias for token generation
        output_folder: Override output folder (default: OUTPUT_FOLDER env or "output")

    Returns:
        dict: {"filepath": str, "site_url": str, "profile_alias": str, "token": str, "headers": dict}
              or None if generation failed.
    """
    cms_url = cms_url.rstrip("/")
    if not cms_url.startswith(("http://", "https://")):
        cms_url = "https://" + cms_url

    token_response = login_and_get_token(cms_url, profile_alias)
    if not token_response:
        logger.error("Token generation failed")
        return None

    token = extract_token(token_response)
    if not token:
        logger.error("Could not extract token from response")
        return None

    base = Path(__file__).resolve().parent.parent
    folder = Path(output_folder) if output_folder else base / OUTPUT_FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    filepath = folder / TOKEN_FILENAME

    entry = {
        "site_url": cms_url,
        "profile_alias": profile_alias,
        "token": token,
        "api_response": token_response,
        "headers": {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    }

    # Load existing or start fresh
    if filepath.exists():
        try:
            with open(filepath) as f:
                all_data = json.load(f)
        except (json.JSONDecodeError, IOError):
            all_data = {"sites": []}
    else:
        all_data = {"sites": []}

    sites = all_data.setdefault("sites", [])

    # Update existing entry or append
    for i, s in enumerate(sites):
        if s.get("site_url") == cms_url and s.get("profile_alias") == profile_alias:
            sites[i] = entry
            break
    else:
        sites.append(entry)

    with open(filepath, "w") as f:
        json.dump(all_data, f, indent=2)

    entry["filepath"] = str(filepath)
    return entry


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) < 2:
        print("Usage: python -m helper_functions.login_token <cms_url> [profile_alias]")
        print("Example: python -m helper_functions.login_token https://example.cms.com 123.45")
        sys.exit(1)
    url = sys.argv[1]
    alias = sys.argv[2] if len(sys.argv) > 2 else "default"
    result = generate_and_save_token(url, alias)
    if result:
        print(f"Token saved to {result['filepath']}")
    else:
        print("Token generation failed")
        sys.exit(1)
