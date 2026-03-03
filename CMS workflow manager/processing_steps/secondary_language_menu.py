"""
Secondary Language Menu Processing
Step 0: Export MiBlock for primary language site (destination), unzip, and create component map.
Step 1: Generate CMS tokens for each saved secondary language (sourceUrl + profileAliasId).
Step 2: For each site, download menu data (same API as primary language).
"""
import os
import json
import time
import zipfile
import logging
from typing import Dict, Any, List

from apis import generate_cms_token, menu_download_api, getComponentInfo, export_mi_block_component, get_site_languages
from utils import get_job_folder, load_job_config, save_job_config, ensure_job_folders

logger = logging.getLogger(__name__)


def _load_json_data(file_path: str) -> Dict[str, Any]:
    """Load JSON from file; return {} on error."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Could not load JSON from {file_path}: {e}")
        return {}


def _export_primary_site_miblock(job_id: str, job_config: Dict[str, Any], steps_log: List[Dict[str, str]]) -> bool:
    """
    Export MiBlock component for primary (destination) site: call export API, unzip, convert .txt to .json, create component map.
    Returns True if successful.
    """
    destination_url = (job_config.get("destinationUrl") or "").strip()
    destination_site_id = (job_config.get("destinationSiteId") or job_config.get("destination_site_id") or "").strip()
    destination_token = job_config.get("destination_cms_token")
    if not destination_url or not destination_site_id:
        steps_log.append({"step": 0, "message": "Skipping export: primary site Destination URL or Site ID missing in config."})
        return False
    if not destination_token:
        steps_log.append({"step": 0, "message": "Skipping export: primary site CMS token missing. Run Site Setup first."})
        return False
    try:
        from .html_menu import get_menu_component_names
        component_names = get_menu_component_names()
        root_component_name = component_names.get("level_0", "Menu-new")
    except Exception as e:
        logger.warning(f"Could not get menu component names: {e}")
        root_component_name = "Menu-new"
    headers = {
        "Content-Type": "application/json",
        "ms_cms_clientapp": "ProgrammingApp",
        "Authorization": f"Bearer {destination_token}",
    }
    steps_log.append({"step": 0, "message": f"Fetching component info for '{root_component_name}' on primary site..."})
    response_data = getComponentInfo(root_component_name, destination_url, headers)
    if not response_data or not isinstance(response_data, list) or len(response_data) == 0:
        steps_log.append({"step": 0, "message": "Export skipped: could not get component info for primary site."})
        return False
    component_id = response_data[0].get("Id")
    if not component_id:
        steps_log.append({"step": 0, "message": "Export skipped: component ID not in response."})
        return False
    steps_log.append({"step": 0, "message": f"Calling export API for component ID {component_id} (primary site)..."})
    time.sleep(1)
    response_content, content_disposition = export_mi_block_component(
        destination_url, component_id, destination_site_id, headers
    )
    if not response_content:
        steps_log.append({"step": 0, "message": "Export failed: no content from export API."})
        return False
    output_dir = get_job_folder(job_id)
    mi_block_folder = f"mi-block-ID-{component_id}"
    save_folder = os.path.join(output_dir, mi_block_folder)
    os.makedirs(save_folder, exist_ok=True)
    filename = (
        content_disposition.split("filename=")[1].strip('"')
        if content_disposition and "filename=" in (content_disposition or "")
        else f"menu_export_{job_id}.zip"
    )
    zip_path = os.path.join(save_folder, filename)
    with open(zip_path, "wb") as f:
        f.write(response_content)
    if not zipfile.is_zipfile(zip_path):
        steps_log.append({"step": 0, "message": "Export failed: response is not a zip file."})
        return False
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(save_folder)
    os.remove(zip_path)
    steps_log.append({"step": 0, "message": "Unzipped export; converting .txt to .json..."})
    for name in os.listdir(save_folder):
        path = os.path.join(save_folder, name)
        if not name.endswith(".txt"):
            continue
        try:
            with open(path, "r", encoding="utf-8") as txt_file:
                content = txt_file.read()
            if not content.strip():
                os.remove(path)
                continue
            data = json.loads(content)
            json_path = os.path.splitext(path)[0] + ".json"
            with open(json_path, "w", encoding="utf-8") as json_file:
                json.dump(data, json_file, indent=4)
            os.remove(path)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Error converting {path}: {e}")
    config_path = os.path.join(save_folder, "MiBlockComponentConfig.json")
    if not os.path.exists(config_path):
        steps_log.append({"step": 0, "message": "Export done but MiBlockComponentConfig.json not found."})
        return True
    config_data = _load_json_data(config_path)
    component_list = config_data.get("component", [])
    main_parent_id = None
    for comp in component_list:
        if comp.get("ParentId") in (None, 0, ""):
            main_parent_id = comp.get("ComponentId")
            break
    name_to_id_map = {}
    for comp in component_list:
        name = comp.get("ComponentName")
        cid = comp.get("ComponentId")
        pid = comp.get("ParentId")
        if name and cid is not None:
            name_to_id_map[name] = {"ComponentId": cid, "ParentId": pid, "MainParentComponentid": main_parent_id}
    map_path = os.path.join(output_dir, "menu_component_name_id_map.json")
    with open(map_path, "w", encoding="utf-8") as f:
        json.dump(name_to_id_map, f, indent=4)
    steps_log.append({"step": 0, "message": f"Step 0 done. Primary site export unzipped; component map saved ({len(name_to_id_map)} components)."})
    # Call GetSiteLanguages for primary site and save to job folder
    steps_log.append({"step": 0, "message": "Fetching site languages for primary site..."})
    try:
        languages_list, raw_response = get_site_languages(destination_url, destination_site_id, headers)
        site_languages_path = os.path.join(output_dir, "site_languages.json")
        to_save = raw_response if raw_response is not None else (languages_list if languages_list else None)
        if to_save is not None:
            with open(site_languages_path, "w", encoding="utf-8") as f:
                json.dump(to_save, f, indent=4)
            count = len(languages_list) if isinstance(languages_list, list) else 0
            steps_log.append({"step": 0, "message": f"Site languages saved to site_languages.json ({count} language(s))."})
        else:
            steps_log.append({"step": 0, "message": "GetSiteLanguages failed (no response); check server logs for status/body."})
    except Exception as e:
        logger.exception("GetSiteLanguages failed")
        steps_log.append({"step": 0, "message": f"Could not save site languages: {str(e)}"})
    return True


def run_secondary_language_menu_step(
    job_id: str,
    lang_key: str = None,
    reprocess_only: bool = False,
) -> Dict[str, Any]:
    """
    Runs secondary language processing for the given job.
    - lang_key: optional 'lang1', 'lang2', 'lang3' to process only that language.
    - reprocess_only: if True (and lang_key set), only run Step 3 (update records); skip Step 0, 1, 2.
    Step 0: Export MiBlock for primary (destination) site, unzip, create component map.
    Step 1: Generate login token for each (or selected) secondary language URL.
    Step 2: For each (or selected) site, get menu data and save to job folder.
    Step 3: Update secondary language records with menu data.
    """
    steps_log: List[Dict[str, str]] = []
    job_config = load_job_config(job_id)
    secondary = job_config.get("secondaryLanguage") or {}
    lang_configs = [
        ("lang1", secondary.get("lang1") or {}),
        ("lang2", secondary.get("lang2") or {}),
        ("lang3", secondary.get("lang3") or {}),
    ]
    filled = [
        (key, cfg)
        for key, cfg in lang_configs
        if (cfg.get("sourceUrl") or "").strip()
    ]
    if lang_key:
        filled = [(k, c) for k, c in filled if k == lang_key]
        if not filled:
            return {
                "success": False,
                "error": f"Language '{lang_key}' is not configured (Source URL and Profile Alias ID required).",
                "steps": steps_log,
            }
    elif not filled:
        return {
            "success": False,
            "error": "No secondary language configured. Save at least one language (Source URL, Site ID, Profile Alias ID) in the popup.",
            "steps": steps_log,
        }
    ensure_job_folders(job_id)
    job_folder = get_job_folder(job_id)
    tokens_stored = {}

    if reprocess_only and lang_key:
        # Only Step 3: update records for this language
        steps_log.append({"step": 3, "message": f"Re-processing: updating records for {lang_key} only..."})
        logger.info(f"[{job_id}] Secondary language reprocess only: {lang_key}")
        try:
            from .secondary_language_update import run_secondary_language_update_step
            update_result = run_secondary_language_update_step(job_id, steps_log, lang_key=lang_key)
            updated_count = update_result.get("updated_count", 0)
            if not update_result.get("success"):
                steps_log.append({"step": 3, "message": update_result.get("error", "Update failed")})
                return {"success": False, "error": update_result.get("error"), "steps": steps_log}
            return {
                "success": True,
                "steps": steps_log,
                "updated_count": updated_count,
            }
        except Exception as e:
            logger.exception("Step 3 (reprocess) failed")
            steps_log.append({"step": 3, "message": str(e)})
            return {"success": False, "error": str(e), "steps": steps_log}

    # ---------- Step 0: Export primary site MiBlock, unzip, component map ----------
    steps_log.append({"step": 0, "message": "Exporting MiBlock for primary language site..."})
    logger.info(f"[{job_id}] Secondary language Step 0: Export primary site MiBlock")
    _export_primary_site_miblock(job_id, job_config, steps_log)

    # ---------- Step 1: Generate tokens for (selected) language(s) ----------
    steps_log.append({"step": 1, "message": "Generating CMS tokens for secondary language(s)..."})
    logger.info(f"[{job_id}] Secondary language Step 1: Generating tokens for {len(filled)} language(s)")
    for key, cfg in filled:
        source_url = (cfg.get("sourceUrl") or "").strip()
        profile_alias = (cfg.get("profileAliasId") or "").strip()
        if not source_url or not profile_alias:
            steps_log.append({"step": 1, "message": f"Skipping {key}: missing URL or Profile Alias ID"})
            continue
        try:
            cms_response = generate_cms_token(source_url, profile_alias)
            if cms_response and cms_response.get("token"):
                token = cms_response.get("token")
                tokens_stored[key] = token
                steps_log.append({"step": 1, "message": f"Token generated for {key} ({source_url})"})
                logger.info(f"[{job_id}] Token generated for {key}")
            else:
                steps_log.append({"step": 1, "message": f"Token failed for {key}: no token in response"})
                logger.warning(f"[{job_id}] Token generation failed for {key}")
        except Exception as e:
            steps_log.append({"step": 1, "message": f"Token error for {key}: {str(e)}"})
            logger.exception(f"[{job_id}] Token error for {key}")

    # Persist tokens into config for future use (e.g. API calls that need auth)
    if tokens_stored:
        if "secondaryLanguageTokens" not in job_config:
            job_config["secondaryLanguageTokens"] = {}
        for k, token in tokens_stored.items():
            job_config["secondaryLanguageTokens"][k] = token
        job_config["job_id"] = job_id
        save_job_config(job_id, job_config)
    steps_log.append({"step": 1, "message": f"Step 1 done. Tokens generated: {list(tokens_stored.keys())}"})

    # ---------- Step 2: Download menu data for each site ----------
    steps_log.append({"step": 2, "message": "Downloading menu data for each secondary language site..."})
    logger.info(f"[{job_id}] Secondary language Step 2: Downloading menu data for {len(filled)} site(s)")
    menu_files = []
    for key, cfg in filled:
        source_url = (cfg.get("sourceUrl") or "").strip()
        if not source_url:
            continue
        try:
            response_data = menu_download_api(source_url)
            if response_data is not None:
                out_path = os.path.join(job_folder, f"menu_api_response_input_secondary_{key}.json")
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(response_data, f, indent=4)
                menu_files.append(out_path)
                steps_log.append({"step": 2, "message": f"Menu data saved for {key}: {os.path.basename(out_path)}"})
                logger.info(f"[{job_id}] Menu data saved for {key}")
            else:
                steps_log.append({"step": 2, "message": f"Menu download returned no data for {key}"})
                logger.warning(f"[{job_id}] No menu data for {key}")
        except Exception as e:
            steps_log.append({"step": 2, "message": f"Menu download error for {key}: {str(e)}"})
            logger.exception(f"[{job_id}] Menu download error for {key}")

    steps_log.append({"step": 2, "message": f"Step 2 done. Menu files saved: {len(menu_files)}"})

    # ---------- Step 3: Update secondary language records with menu data ----------
    steps_log.append({"step": 3, "message": "Updating secondary language records with menu data (align by sequence)..."})
    logger.info(f"[{job_id}] Secondary language Step 3: Update records (lang_key={lang_key})")
    updated_count = 0
    try:
        from .secondary_language_update import run_secondary_language_update_step
        update_result = run_secondary_language_update_step(job_id, steps_log, lang_key=lang_key)
        updated_count = update_result.get("updated_count", 0)
        if not update_result.get("success"):
            steps_log.append({"step": 3, "message": f"Update step reported: {update_result.get('error', 'unknown')}"})
    except Exception as e:
        logger.exception("Step 3 failed")
        steps_log.append({"step": 3, "message": f"Update step failed: {str(e)}"})

    return {
        "success": True,
        "steps": steps_log,
        "tokens_generated": list(tokens_stored.keys()),
        "menu_files": [os.path.basename(p) for p in menu_files],
        "updated_count": updated_count,
    }
