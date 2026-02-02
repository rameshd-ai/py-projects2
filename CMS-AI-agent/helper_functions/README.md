# Helper Functions

Reusable utilities used by processes. These are not processes themselves but building blocks.

## Module: login_token

**File**: `login_token.py`

Token generation and auth header utilities for CMS API authentication.

**Primary function** (use this when generating tokens - same for app, CLI, or AI):
- `generate_and_save_token(cms_url, profile_alias, output_folder?)` - Generate token and save to `output/login_token.json`. All URLs are stored in one file; existing entries are updated by site_url + profile_alias. Returns dict with filepath, token, headers or None.

**Other functions**:
- `login_and_get_token(cms_url, profile_alias)` - Generate CMS token (raw API response)
- `extract_token(token_response)` - Extract token string from API response
- `get_auth_headers(token_data)` - Build Authorization headers from token
- `login_and_get_headers(cms_url, profile_alias)` - One-step: login + return headers

**Usage** (programmatic):
```python
from helper_functions.login_token import generate_and_save_token

result = generate_and_save_token(
    cms_url="https://example.cms.milestoneinternet.info",
    profile_alias="123.45"
)
if result:
    print(f"Token saved to {result['filepath']}")
```

**Usage** (CLI - when asked to generate a token):
```bash
python -m helper_functions.login_token https://example.cms.com 123.45
```

## Module: vcomponent_page

**File**: `vcomponent_page.py`

URL generation, HTML fetch, and screenshot for VComponent preview pages.

**Functions**:
- `generate_vcomponent_url(base_url, vcomponent_id)` - Build preview URL with cache-busting
- `fetch_vcomponent_html_and_screenshot(url, output_dir, vcomponent_id, extra_headers?)` - Use Playwright to fetch HTML and PNG

**Usage**:
```python
from helper_functions.vcomponent_page import generate_vcomponent_url, fetch_vcomponent_html_and_screenshot

url = generate_vcomponent_url("https://example.cms.com", vcomponent_id=21016536)
result = fetch_vcomponent_html_and_screenshot(url, Path("output/site/vcomponents"), 21016536, extra_headers=headers)
# Saves {vcomponent_id}.html and {vcomponent_id}.png
```
