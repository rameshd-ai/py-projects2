# Process Modules

Each process handles a specific workflow step for the CMS-AI-agent.

## Process List

| # | Module | Description |
|---|--------|-------------|
| 01 | `process_01_download_cms_data.py` | Download CMS data: GetSiteVComponents for all sites, or full data (pages, VComponents, etc.) for one site |

---

## Process 01: Download CMS Data for Training

**File**: `process_01_download_cms_data.py`

**Purpose**: Download CMS data for AI training. For each site in `login_token.json`, fetches GetSiteVComponents and saves to `output/{site_slug}/GetSiteVComponents.json`. Also supports full download (pages, VComponents, templates, categories) for one site when site_id is provided.

**Process functions**:
- `fetch_vcomponents_for_all_sites(output_folder?)` - Fetch GetSiteVComponents for all sites in login_token.json
- `download_cms_data_for_training(site_url, site_id, profile_alias?, output_folder?, include_page_details?)` - Full download for one site

**CLI Usage**:
```bash
# Fetch GetSiteVComponents for all sites in login_token.json
python -m process.process_01_download_cms_data --all

# Full download for one site (requires site_id)
python -m process.process_01_download_cms_data <site_url> <site_id> [profile_alias]
python -m process.process_01_download_cms_data https://example.cms.milestoneinternet.info 16277
```

**Output**:
- `output/{site_slug}/GetSiteVComponents.json` - VComponents response (site_url, TotalRecords, vComponents)
- `output/cms_training_data_<site_slug>.json` - Full training data (pages, vcomponents, template_pages, page_categories)
