import os
import time
import json
import logging
import uuid
import re
from typing import Dict, Any, List, Tuple, Optional, Union, Set

from apis import (
    GetAllVComponents,
    export_mi_block_component,
    addUpdateRecordsToCMS,
    addUpdateRecordsToCMS_bulk,
    generatecontentHtml,
    GetTemplatePageByName,
    psMappingApi,
    psPublishApi,
    CustomGetComponentAliasByName,
    GetPageCategoryList,
)

# Import the proven inner-page component handler so home uses EXACTLY the same logic
from processing_steps.process_assembly import (
    add_records_for_page,
    createPayloadJson,
    createRecordsPayload,
    sanitize_page_name_for_filesystem,
    generate_page_alias,
)
import zipfile


# ================= BASIC CONFIG (HOMEPAGE-ONLY MODULE) =================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "..", "uploads")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# --- DEBUG LOG FILE FOR HOMEPAGE STEP ---
def get_site_upload_folder(site_id: Optional[int] = None) -> str:
    """Returns the site-specific upload folder path."""
    if site_id is not None:
        site_folder = os.path.join(UPLOAD_FOLDER, str(site_id))
        os.makedirs(site_folder, exist_ok=True)
        return site_folder
    return UPLOAD_FOLDER

def get_home_debug_log_filepath(site_id: Optional[int] = None) -> str:
    """Returns the home debug log file path, site-specific if site_id is provided."""
    site_folder = get_site_upload_folder(site_id)
    return os.path.join(site_folder, "home_debug.log")

HOME_DEBUG_LOG_FILE = get_home_debug_log_filepath()  # Default

# Global variable to store current site_id for home debug logging
_CURRENT_HOME_SITE_ID: Optional[int] = None

def set_current_home_site_id(site_id: Optional[int]) -> None:
    """Sets the current site_id for home debug logging."""
    global _CURRENT_HOME_SITE_ID
    _CURRENT_HOME_SITE_ID = site_id

def append_home_debug_log(section: str, data: Dict[str, Any], site_id: Optional[int] = None) -> None:
    """Safely append structured debug info for the homepage step. Uses site_id if provided, otherwise uses global _CURRENT_HOME_SITE_ID."""
    try:
        log_site_id = site_id if site_id is not None else _CURRENT_HOME_SITE_ID
        log_file = get_home_debug_log_filepath(log_site_id)
        log_folder = os.path.dirname(log_file)
        os.makedirs(log_folder, exist_ok=True)
        entry = {
            "section": section,
            "data": data,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        # Never block execution on debug logging
        pass


def get_config_filepath_home(file_prefix: str) -> str:
    """Constructs the unique config.json filepath based on the prefix (homepage module)."""
    base_prefix = os.path.basename(file_prefix)
    config_filename = f"{base_prefix}_config.json"
    return os.path.join(UPLOAD_FOLDER, config_filename)


def load_settings_home(file_prefix: str) -> Optional[Dict[str, Any]]:
    """Loads the settings/config file based on the unique prefix (homepage module)."""
    filepath = get_config_filepath_home(file_prefix)
    if not os.path.exists(filepath):
        logging.error(f"[HOME] Config file not found at {filepath}")
        return None
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"[HOME] Error loading config file: {e}")
        return None


# ================= HOMEPAGE-SPECIFIC HELPERS =================

HOMEPAGE_STATUS_LOG: List[Dict[str, Any]] = []
HOMEPAGE_TIMING_TRACKER: Dict[str, List[float]] = {}
HOMEPAGE_GUID_TRACKER: Dict[str, str] = {}
HOMEPAGE_PAGES_TO_PUBLISH: List[Dict[str, Any]] = []


def check_component_availability_home(
    component_name: str, component_cache: List[Dict[str, Any]]
) -> Optional[Tuple[int, str, int, str, int, int, int]]:
    """
    Homepage-local variant of check_component_availability.
    Strips bracket info (Block-X,Main-X,Sub-Y) from component name before searching.

    Performs a prefix search up to the first hyphen and returns:
        (vComponentId, alias, componentId, cms_component_name, block_count, main_count, sub_count)
    """
    # Import here to avoid circular dependency
    from processing_steps.process_assembly import parse_component_bracket_info
    
    # Parse bracket info and get clean name
    clean_component_name, block_count, main_count, sub_count = parse_component_bracket_info(component_name)
    
    hyphen_index = clean_component_name.find("-")
    if hyphen_index != -1:
        search_key = clean_component_name[: hyphen_index + 1].strip()
    else:
        search_key = clean_component_name.strip()

    logging.info(f"[HOME] Searching cache for prefix: **{search_key}** (Original: {component_name}, Clean: {clean_component_name}, Block: {block_count}, Main: {main_count}, Sub: {sub_count})")

    for component in component_cache:
        cms_component_name = component.get("name", "")
        if cms_component_name.startswith(search_key):
            vComponentId = component.get("vComponentId")
            component_alias = component.get("alias")
            nested = component.get("component", {})
            component_id = nested.get("componentId")

            if vComponentId is not None and component_alias is not None and component_id is not None:
                logging.info(
                    f"[HOME] [SUCCESS] Component '{component_name}' found in cache as '{cms_component_name}'. Block: {block_count}, Main: {main_count}, Sub: {sub_count}"
                )
                return vComponentId, component_alias, component_id, cms_component_name, block_count, main_count, sub_count

    logging.warning(f"[HOME] [ERROR] Component prefix '{search_key}' not found in the component cache.")
    return None


def _get_home_component_folder(site_id: int, component_id: int, page_name: str = "Home") -> str:
    """Returns the output folder path for a component with page-specific folder structure."""
    mi_block_folder = f"mi-block-ID-{component_id}"
    sanitized_page_name = sanitize_page_name_for_filesystem(page_name)
    output_dir = os.path.join("output", str(site_id), sanitized_page_name)
    save_folder = os.path.join(output_dir, mi_block_folder)
    os.makedirs(save_folder, exist_ok=True)
    return save_folder


def pre_download_home_components(
    components: List[str],
    component_cache: List[Dict[str, Any]],
    api_base_url: str,
    site_id: int,
    api_headers: Dict[str, str],
    page_name: str = "Home",
) -> None:
    """
    Pre-download all home components first, then unzip all, then convert all txt->json.
    Mirrors inner-page behavior but in 3 distinct phases for homepage:
      1) Download all zips
      2) Unzip all
      3) Convert all TXT to JSON
    
    Args:
        page_name: The page name for folder structure (default: "Home")
    """
    # Resolve components to ids/aliases
    resolved: List[Tuple[str, int, int, str]] = []
    for comp in components:
        res = check_component_availability_home(comp, component_cache)
        if res:
            vId, alias, compId, cms_name, block_count, main_count, sub_count = res
            resolved.append((comp, compId, vId, alias))
        else:
            logging.warning(f"[HOME][PRE-DOWNLOAD] Component not found in cache, skipping download: {comp}")

    # Phase 1: Download all
    for comp_name, comp_id, vId, alias in resolved:
        folder = _get_home_component_folder(site_id, comp_id, page_name)
        try:
            logging.info(f"[HOME][PRE-DOWNLOAD] Downloading component {comp_name} (ID {comp_id})")
            response_content, content_disposition = export_mi_block_component(api_base_url, comp_id, site_id, api_headers)
            if response_content:
                if content_disposition and "filename=" in content_disposition:
                    zip_name = content_disposition.split("filename=")[1].strip('"')
                else:
                    zip_name = f"site_{site_id}.zip"
                zip_path = os.path.join(folder, zip_name)
                with open(zip_path, "wb") as f:
                    f.write(response_content)
            else:
                logging.warning(f"[HOME][PRE-DOWNLOAD] Empty content for {comp_name} (ID {comp_id})")
                append_home_debug_log(
                    "pre_download_empty",
                    {"component": comp_name, "componentId": comp_id},
                )
        except Exception as e:
            logging.error(f"[HOME][PRE-DOWNLOAD] Failed to download {comp_name} (ID {comp_id}): {e}")
            append_home_debug_log(
                "pre_download_error",
                {"component": comp_name, "componentId": comp_id, "error": str(e)},
            )

    # Phase 2: Unzip all
    for comp_name, comp_id, _, _ in resolved:
        folder = _get_home_component_folder(site_id, comp_id, page_name)
        for fname in os.listdir(folder):
            if fname.lower().endswith(".zip"):
                zip_path = os.path.join(folder, fname)
                if zipfile.is_zipfile(zip_path):
                    try:
                        with zipfile.ZipFile(zip_path, "r") as zip_ref:
                            zip_ref.extractall(folder)
                        os.remove(zip_path)
                        logging.info(f"[HOME][PRE-DOWNLOAD] Unzipped {fname} for {comp_name} (ID {comp_id})")
                        append_home_debug_log(
                            "pre_download_unzip",
                            {"component": comp_name, "componentId": comp_id, "zip": fname},
                        )
                    except Exception as e:
                        logging.error(f"[HOME][PRE-DOWNLOAD] Failed to unzip {fname} for {comp_name}: {e}")
                        append_home_debug_log(
                            "pre_download_unzip_error",
                            {"component": comp_name, "componentId": comp_id, "zip": fname, "error": str(e)},
                        )
                else:
                    logging.warning(f"[HOME][PRE-DOWNLOAD] Not a zip file: {fname}")

    # Phase 3: Convert all TXT to JSON
    for comp_name, comp_id, _, _ in resolved:
        folder = _get_home_component_folder(site_id, comp_id, page_name)
        txt_count = 0
        converted = 0
        for extracted_file in os.listdir(folder):
            if extracted_file.endswith(".txt"):
                extracted_file_path = os.path.join(folder, extracted_file)
                new_file_path = os.path.splitext(extracted_file_path)[0] + ".json"
                txt_count += 1
                try:
                    with open(extracted_file_path, "r", encoding="utf-8") as txt_file:
                        content = txt_file.read()
                        json_content = json.loads(content)
                    with open(new_file_path, "w", encoding="utf-8") as json_file:
                        json.dump(json_content, json_file, indent=4)
                    time.sleep(0.05)
                    os.remove(extracted_file_path)
                    converted += 1
                    logging.info(f"[HOME][PRE-DOWNLOAD] Converted {extracted_file} -> {os.path.basename(new_file_path)} for {comp_name}")
                except (json.JSONDecodeError, OSError) as e:
                    logging.error(f"[HOME][PRE-DOWNLOAD] Error converting {extracted_file_path}: {e}")
                    append_home_debug_log(
                        "pre_download_convert_error",
                        {"component": comp_name, "componentId": comp_id, "file": extracted_file, "error": str(e)},
                    )
        append_home_debug_log(
            "pre_download_convert_summary",
            {"component": comp_name, "componentId": comp_id, "txt_found": txt_count, "converted": converted},
        )

        # Final presence check
        config_path = os.path.join(folder, "MiBlockComponentConfig.json")
        records_path = os.path.join(folder, "MiBlockComponentRecords.json")
        append_home_debug_log(
            "pre_download_presence",
            {
                "component": comp_name,
                "componentId": comp_id,
                "config_exists": os.path.exists(config_path),
                "records_exists": os.path.exists(records_path),
            },
        )


def ensure_home_component_files(
    comp_name: str,
    comp_id: int,
    api_base_url: str,
    site_id: int,
    api_headers: Dict[str, str],
    page_name: str = "Home",
) -> bool:
    """
    Per-component safeguard: make sure MiBlockComponentConfig.json and
    MiBlockComponentRecords.json exist for this component. If missing,
    attempt download->unzip->txt->json conversion once.
    
    Args:
        page_name: The page name for folder structure (default: "Home")
    """
    folder = _get_home_component_folder(site_id, comp_id, page_name)
    config_path = os.path.join(folder, "MiBlockComponentConfig.json")
    records_path = os.path.join(folder, "MiBlockComponentRecords.json")

    if os.path.exists(config_path) and os.path.exists(records_path):
        return True

    try:
        logging.info(f"[HOME][ENSURE] Files missing for {comp_name} (ID {comp_id}); retrying download.")
        response_content, content_disposition = export_mi_block_component(api_base_url, comp_id, site_id, api_headers)
        if response_content:
            if content_disposition and "filename=" in content_disposition:
                zip_name = content_disposition.split("filename=")[1].strip('"')
            else:
                zip_name = f"site_{site_id}.zip"
            zip_path = os.path.join(folder, zip_name)
            with open(zip_path, "wb") as f:
                f.write(response_content)
            if zipfile.is_zipfile(zip_path):
                with zipfile.ZipFile(zip_path, "r") as zip_ref:
                    zip_ref.extractall(folder)
                os.remove(zip_path)

            # Convert any TXT to JSON
            for extracted_file in os.listdir(folder):
                if extracted_file.endswith(".txt"):
                    extracted_file_path = os.path.join(folder, extracted_file)
                    new_file_path = os.path.splitext(extracted_file_path)[0] + ".json"
                    try:
                        with open(extracted_file_path, "r", encoding="utf-8") as txt_file:
                            content = txt_file.read()
                            json_content = json.loads(content)
                        with open(new_file_path, "w", encoding="utf-8") as json_file:
                            json.dump(json_content, json_file, indent=4)
                        time.sleep(0.05)
                        os.remove(extracted_file_path)
                    except Exception as e:
                        logging.error(f"[HOME][ENSURE] Error converting {extracted_file_path}: {e}")
        else:
            logging.warning(f"[HOME][ENSURE] Export returned empty for {comp_name} (ID {comp_id})")

    except Exception as e:
        logging.error(f"[HOME][ENSURE] Failed to prepare files for {comp_name} (ID {comp_id}): {e}")

    exists = os.path.exists(config_path) and os.path.exists(records_path)
    append_home_debug_log(
        "ensure_presence",
        {
            "component": comp_name,
            "componentId": comp_id,
            "config_exists": os.path.exists(config_path),
            "records_exists": os.path.exists(records_path),
        },
    )
    return exists


def normalize_page_name(name: str) -> str:
    """
    Normalizes a page or category name for robust, case-insensitive, and 
    symbol-agnostic fuzzy matching.

    Steps:
    1. Converts to lowercase.
    2. Strips leading/trailing whitespace.
    3. Removes all non-alphanumeric characters (keeps letters and numbers only).

    Args:
        name (str): The original page or category name string.

    Returns:
        str: The normalized string, suitable for dictionary keys or comparison.
    """
    if not name:
        return ""
    
    # 1. Strip whitespace and convert to lowercase
    normalized = name.strip().lower()
    
    # 2. Remove all characters that are NOT alphanumeric (a-z, 0-9)
    # This turns "Meetings & Events" into "meetingsandevents"
    normalized = re.sub(r'[^a-z0-9]', '', normalized)
    
    return normalized


def add_records_for_home_page(
    page_name: str,
    vComponentId: int,
    componentId: int,
    base_url: str,
    site_id: int,
    headers: Dict[str, str],
    component_alias: str,
) -> str:
    """
    Thin wrapper maintained for API compatibility; homepage now delegates to
    `add_records_for_page` so component export, TXT→JSON conversion,
    hierarchy/tree creation, and record migration are IDENTICAL to inner pages.
    """
    logging.info("[HOME] Delegating add_records_for_home_page to add_records_for_page for identical processing.")
    return add_records_for_page(page_name, vComponentId, componentId, base_url, site_id, headers, component_alias)


def get_header_footer_html_home(
    base_url: str, headers: Dict[str, str], header_footer_comp_name: str
) -> Tuple[Optional[int], Optional[str], Optional[int], str, Optional[str]]:
    """
    Homepage-local helper to fetch header/footer component info and generate HTML.
    """
    if not header_footer_comp_name:
        return None, None, None, "", None

    try:
        vComponentId, component_alias, component_id = CustomGetComponentAliasByName(
            base_url, headers, header_footer_comp_name
        )
        pageSectionGuid = str(uuid.uuid4())
        section_html = generatecontentHtml(1, component_alias, pageSectionGuid)
        return vComponentId, component_alias, component_id, section_html, pageSectionGuid
    except Exception as e:
        logging.error(f"[HOME] Failed to process Header/Footer '{header_footer_comp_name}': {e}")
        return None, None, None, "", None


def pageAction_home(
    base_url: str,
    headers: Dict[str, str],
    final_html: str,
    page_name: str,
    page_template_id: Optional[int],
    DefaultTitle: Optional[str],
    DefaultDescription: Optional[str],
    site_id: int,
    header_footer_details: Dict[str, Any],
    category_id: int = 0,
    page_component_ids: Optional[Set[str]] = None,
    page_component_names: Optional[List[str]] = None,
    component_cache: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Homepage-local variant of pageAction: create page, map MiBlocks, and queue for publish.
    """
    page_content_bytes = final_html.encode("utf-8")
    import base64

    base64_encoded_content = base64.b64encode(page_content_bytes).decode("utf-8")

    # Align payload EXACTLY with main assembly (pageAction) - homepage should be identical to level 1 pages
    payload = {
        "pageId": 0,
        "pageName": page_name,
        "pageAlias": generate_page_alias(page_name),  # Preserve "/" for hierarchical names
        "pageContent": base64_encoded_content,
        "isPageStudioPage": True,
        "pageUpdatedBy": 0,
        "isUniqueMetaContent": True,
        "pageMetaTitle": DefaultTitle,
        "pageMetaDescription": DefaultDescription,
        "pageStopSEO": 1,
        "pageCategoryId": category_id,
        "pageProfileId": 0,
        "tags": "",
    }

    from apis import CreatePage  # Import here to keep this module standalone

    # Ensure template_id is never None (default to 0)
    if page_template_id is None:
        page_template_id = 0
        logging.warning(f"[HOME] Template ID was None, defaulting to 0 for page '{page_name}'")

    logging.info(f"[HOME] Creating page '{page_name}' for site {site_id} (templateId={page_template_id}, categoryId={category_id})")
    # Debug: capture request details
    append_home_debug_log(
        "create_page_request",
        {
            "page_name": page_name,
            "page_template_id": page_template_id,
            "page_category_id": category_id,
            "payload": payload,
            "api_url": f"{base_url}/api/PageApi/SavePage?templateId={page_template_id}&directPublish=true",
        },
    )

    data = CreatePage(base_url, headers, payload, page_template_id)

    # Debug: capture raw response
    append_home_debug_log(
        "create_page_response",
        {
            "page_name": page_name,
            "response_type": str(type(data)),
            "response": data if isinstance(data, dict) else str(data),
        },
    )

    if not isinstance(data, dict):
        logging.error(f"[HOME][ERROR] CreatePage returned non-dict response for '{page_name}': {data}")
        return {"error": True, "details": data}

    # If CreatePage itself returned an error dict, honor it
    if "error" in data:
        logging.error(f"[HOME][ERROR] CreatePage failed for '{page_name}': {data}")
        return data

    page_id = data.get("PageId")
    if not page_id:
        logging.error(f"[HOME][ERROR] 'PageId' missing in CreatePage response for '{page_name}': {data}")
        return {"error": True, "details": data}

    logging.info(f"[HOME][SUCCESS] Page '{page_name}' created successfully with Page ID: {page_id}")

    # Update mapping using the same function as inner pages (exactly like pageAction does)
    logging.info(f"[HOME][TIMING] Starting updatePageMapping for page '{page_name}' (ID: {page_id})")
    start_time = time.time()
    mapping_payload = None
    try:
        from processing_steps.process_assembly import updatePageMapping
        # Pass home_debug_log_callback to also log to home_debug.log
        # Pass page_component_ids, page_component_names, and component_cache to filter mapping to only components for this page
        _, mapping_payload = updatePageMapping(base_url, headers, page_id, site_id, header_footer_details, home_debug_log_callback=append_home_debug_log, page_name=page_name, page_component_ids=page_component_ids, page_component_names=page_component_names, component_cache=component_cache)
        mapping_time = time.time() - start_time
        logging.info(f"[HOME][TIMING] updatePageMapping completed in {mapping_time:.2f} seconds")
        logging.info(f"[HOME][SUCCESS] updatePageMapping completed for page '{page_name}' (ID: {page_id})")
    except Exception as e:
        logging.error(f"[HOME][ERROR] updatePageMapping failed for '{page_name}' (ID: {page_id}): {e}")
        logging.exception("Full traceback:")
        # Even if mapping fails, we still queue the page for potential publish

    HOMEPAGE_PAGES_TO_PUBLISH.append(
        {"page_id": page_id, "page_name": page_name, "header_footer_details": header_footer_details, "mapping_payload": mapping_payload}
    )

    return data


def publish_queued_home_pages(base_url: str, headers: Dict[str, str], site_id: int) -> int:
    """
    Homepage-local variant of publish_queued_pages - uses same logic as inner pages (publishPage).
    """
    if not HOMEPAGE_PAGES_TO_PUBLISH:
        logging.info("[HOME][PUBLISH] No homepage pages queued for publish.")
        append_home_debug_log("publish_queue", {"queued": 0})
        return 0

    append_home_debug_log(
        "publish_queue",
        {
            "queued": len(HOMEPAGE_PAGES_TO_PUBLISH),
            "pages": [
                {"page_id": p.get("page_id"), "page_name": p.get("page_name")} for p in HOMEPAGE_PAGES_TO_PUBLISH
            ],
        },
    )

    success_count = 0
    for entry in HOMEPAGE_PAGES_TO_PUBLISH:
        page_id = entry.get("page_id")
        page_name = entry.get("page_name")
        header_footer_details = entry.get("header_footer_details", {})
        mapping_payload = entry.get("mapping_payload")
        try:
            logging.info(f"[HOME][PUBLISH] Publishing page '{page_name}' (ID: {page_id}) using same logic as inner pages")
            # Use the same publishPage function as inner pages to ensure identical behavior
            # Pass home_debug_log_callback to also log to home_debug.log
            # Pass mapping_payload to check contentEntityType for correct MIBLOCK vs COMPONENT classification
            from processing_steps.process_assembly import publishPage
            publishPage(base_url, headers, page_id, site_id, header_footer_details, home_debug_log_callback=append_home_debug_log, mapping_payload=mapping_payload, page_name=page_name)
            success_count += 1
            append_home_debug_log(
                "publish_success",
                {
                    "page_id": page_id,
                    "page_name": page_name,
                },
            )
        except Exception as e:
            logging.error(f"[HOME][PUBLISH ERROR] Failed to publish page '{page_name}' (ID: {page_id}): {e}")
            logging.exception("Full traceback:")
            append_home_debug_log(
                "publish_error",
                {
                    "page_id": page_id,
                    "page_name": page_name,
                    "error": str(e),
                },
            )

    logging.info(f"[HOME][PUBLISH] Completed publishing of {success_count}/{len(HOMEPAGE_PAGES_TO_PUBLISH)} pages.")
    HOMEPAGE_PAGES_TO_PUBLISH.clear()
    return success_count


def _process_home_page_components(
    page_data: Dict[str, Any],
    component_cache: List[Dict[str, Any]],
    api_base_url: str,
    site_id: int,
    api_headers: Dict[str, str],
) -> None:
    """
    Core homepage processor: processes exactly one page (level 0).
    """
    page_name = page_data.get("page_name", "HOME_PAGE")
    components = page_data.get("components", [])
    meta_info = page_data.get("meta_info", {})

    page_template_name = meta_info.get("PageTemplateName")
    DefaultTitle = meta_info.get("DefaultTitle") or ""
    DefaultDescription = meta_info.get("DefaultDescription") or ""
    Header1 = meta_info.get("Header1")
    Header2 = meta_info.get("Header2")
    Footer1 = meta_info.get("Footer1")
    Footer2 = meta_info.get("Footer2")

    # For home page, default template ID to 0 if not found or not specified
    page_template_id = 0
    if page_template_name:
        try:
            template_info = GetTemplatePageByName(api_base_url, api_headers, page_template_name)
            if template_info and isinstance(template_info, list) and "PageId" in template_info[0]:
                page_template_id = template_info[0]["PageId"]
                logging.info(f"[HOME] Retrieved Page Template ID {page_template_id} for template: {page_template_name}")
            else:
                logging.warning(f"[HOME] Template '{page_template_name}' not found or invalid. Using default template ID 0.")
        except Exception as e:
            logging.error(f"[HOME] Failed to retrieve page template ID for '{page_template_name}': {e}. Using default template ID 0.")
            page_template_id = 0

    # Don't pass module ID for homepage - use 0
    matched_category_id = 0
    logging.info(f"[HOME] Using CategoryId = 0 (no module/category) for homepage")
    append_home_debug_log(
        "category_skipped",
        {
            "page_name": page_name,
            "category_id": matched_category_id,
        },
    )

    page_sections_html: List[str] = []
    # Track component IDs that belong to this page
    page_component_ids: set = set()

    if not components:
        logging.warning("[HOME] Home page has no components to process.")
        return

    # Track component names from simplified.json for this page
    page_component_names: List[str] = page_data.get('components', [])
    
    # Pre-download/unzip/convert all home components in one batch (3-phase)
    pre_download_home_components(components, component_cache, api_base_url, site_id, api_headers, page_name)

    # Process all components
    for component_name in components:
            logging.info(f"[HOME] Processing component '{component_name}' for home page '{page_name}'")

            api_result = check_component_availability_home(component_name, component_cache)
            section_payload = None  # Initialize for each component

            if api_result:
                vComponentId, alias, componentId, cms_component_name, block_count, main_count, sub_count = api_result
                logging.info(
                    f"[HOME][SUCCESS] Component '{component_name}' available as '{cms_component_name}'. "
                    f"Starting content retrieval (inner-page logic: add_records_for_page). Block: {block_count}, Main: {main_count}, Sub: {sub_count}"
                )
                
                # Track this component ID as belonging to this page
                page_component_ids.add(str(componentId))
                
                # Note: block_count, main_count, sub_count are kept in local variables for future use, not saved to logs
                append_home_debug_log(
                    "component_available",
                    {
                        "page_name": page_name,
                        "component": component_name,
                        "cms_component_name": cms_component_name,
                        "vComponentId": vComponentId,
                        "componentId": componentId,
                        "alias": alias,
                    },
                )

                # Ensure required files exist before processing
                files_ok = ensure_home_component_files(component_name, componentId, api_base_url, site_id, api_headers, page_name)
                append_home_debug_log(
                    "component_files_ready",
                    {
                        "page_name": page_name,
                        "component": component_name,
                        "componentId": componentId,
                        "ready": files_ok,
                    },
                )
                if not files_ok:
                    logging.error(f"[HOME] Required files missing for component {component_name} (ID {componentId}); skipping.")
                    continue

                # Proactively (re)generate hierarchy/tree before running add_records_for_page,
                # mirroring inner-page behavior and ensuring files exist even if pre-download skipped something.
                try:
                    createPayloadJson(site_id, componentId)
                    createRecordsPayload(site_id, componentId)
                    append_home_debug_log(
                        "component_hierarchy_tree_created",
                        {"component": component_name, "componentId": componentId},
                    )
                except Exception as e:
                    logging.error(f"[HOME] Failed to create hierarchy/tree for {component_name} (ID {componentId}): {e}")
                    append_home_debug_log(
                        "component_hierarchy_tree_error",
                        {"component": component_name, "componentId": componentId, "error": str(e)},
                    )

                try:
                    start_t = time.time()
                    # Use the exact same component processing pipeline as inner pages
                    section_payload = add_records_for_page(
                        page_name, vComponentId, componentId, api_base_url, site_id, api_headers, alias, main_count, sub_count
                    )
                    elapsed = time.time() - start_t
                    HOMEPAGE_TIMING_TRACKER.setdefault("add_records_for_page(home)", []).append(elapsed)

                    payload_len = len(section_payload) if section_payload else 0
                    append_home_debug_log(
                        "component_section_payload",
                        {
                            "page_name": page_name,
                            "component": component_name,
                            "payload_length": payload_len,
                            "elapsed_seconds": elapsed,
                        },
                    )
                except Exception as e:
                    logging.error(f"[HOME] Content retrieval failed for {page_name}/{component_name}: {e}")
                    append_home_debug_log(
                        "component_error",
                        {
                            "page_name": page_name,
                            "component": component_name,
                            "error": str(e),
                        },
                    )
            else:
                logging.warning(
                    f"[HOME][ERROR] Component '{component_name}' NOT AVAILABLE for home page '{page_name}'. Skipping."
                )
                append_home_debug_log(
                    "component_unavailable",
                    {"page_name": page_name, "component": component_name},
                )

            # Add section_payload to page_sections_html if it exists (outside the api_result check)
            if section_payload is not None:
                page_sections_html.append(section_payload)
                logging.info(f"[HOME] Added section payload for '{component_name}' (length: {len(section_payload)})")
            else:
                append_home_debug_log(
                    "component_section_empty",
                    {"page_name": page_name, "component": component_name},
                )

    all_sections_concatenated = "".join(page_sections_html)
    htmlPrefix = '<div class="box2" id="data_page_content"><div id="pagestudio">'
    htmlPostfix = "</div></div>"

    # Header / Footer
    Header1_vId, Header1_alias, Header1_id, Header1_html, Header1_guid = get_header_footer_html_home(
        api_base_url, api_headers, Header1 or ""
    )
    Header2_vId, Header2_alias, Header2_id, Header2_html, Header2_guid = get_header_footer_html_home(
        api_base_url, api_headers, Header2 or ""
    )
    Footer1_vId, Footer1_alias, Footer1_id, Footer1_html, Footer1_guid = get_header_footer_html_home(
        api_base_url, api_headers, Footer1 or ""
    )
    Footer2_vId, Footer2_alias, Footer2_id, Footer2_html, Footer2_guid = get_header_footer_html_home(
        api_base_url, api_headers, Footer2 or ""
    )

    # Track header/footer component IDs if they exist
    if Header1_id:
        page_component_ids.add(str(Header1_id))
    if Header2_id:
        page_component_ids.add(str(Header2_id))
    if Footer1_id:
        page_component_ids.add(str(Footer1_id))
    if Footer2_id:
        page_component_ids.add(str(Footer2_id))

    header_footer_details: Dict[str, Any] = {
        "Header1": {"name": Header1, "vId": Header1_vId, "alias": Header1_alias, "id": Header1_id, "guid": Header1_guid},
        "Header2": {"name": Header2, "vId": Header2_vId, "alias": Header2_alias, "id": Header2_id, "guid": Header2_guid},
        "Footer1": {"name": Footer1, "vId": Footer1_vId, "alias": Footer1_alias, "id": Footer1_id, "guid": Footer1_guid},
        "Footer2": {"name": Footer2, "vId": Footer2_vId, "alias": Footer2_alias, "id": Footer2_id, "guid": Footer2_guid},
    }

    final_html = (
        htmlPrefix
        + (Header1_html or "")
        + (Header2_html or "")
        + all_sections_concatenated
        + (Footer1_html or "")
        + (Footer2_html or "")
        + htmlPostfix
    )
    
    # Check if we have content (header/footer + body components)
    has_content = page_sections_html and any(
        section and section.strip() for section in page_sections_html if isinstance(section, str)
    ) or (Header1_html or Header2_html or Footer1_html or Footer2_html)
    
    if not has_content:
        logging.error("[HOME] Home page failed: No HTML content assembled. Skipping page creation.")
        return
    
    logging.info("[HOME] Final HTML for Home Page assembled. Calling pageAction_home...")
    pageAction_home(
        api_base_url,
        api_headers,
        final_html,
        page_name,
        page_template_id,
        DefaultTitle,
        DefaultDescription,
        site_id,
        header_footer_details,
        matched_category_id,
        page_component_ids,
        page_component_names,
        component_cache,
    )


def assemble_home_page_templates_home(
    processed_json: Dict[str, Any],
    component_cache: List[Dict[str, Any]],
    api_base_url: str,
    site_id: int,
    api_headers: Dict[str, str],
) -> None:
    """
    Entry for this module: process ONLY the single home page (level 0).
    """
    logging.info("\n========================================================")
    logging.info("[HOME] START: Home Page Template Assembly (Level 0 - Single Page Only)")
    logging.info("========================================================")

    pages = processed_json.get("pages", [])
    if not pages:
        logging.warning("[HOME] No 'pages' list found in the home page JSON. Aborting assembly.")
        return

    home_page = pages[0] if pages else None
    if not home_page:
        logging.warning("[HOME] No home page found in the JSON. Aborting assembly.")
        return

    append_home_debug_log(
        "home_page_start",
        {
            "page_name": home_page.get("page_name"),
            "components": home_page.get("components", []),
        },
    )

    _process_home_page_components(home_page, component_cache, api_base_url, site_id, api_headers)

    logging.info("========================================================")
    logging.info("[HOME] END: Home Page Template Assembly Complete")
    logging.info("========================================================")


def run_homepage_processing_step(
    processed_json: Union[Dict[str, Any], str], *args, **kwargs
) -> Dict[str, Any]:
    """
    Main entry for the homepage-only processing step.

    Expected:
      - `processed_json` or second positional arg contains at least `file_prefix`
      - `<file_prefix>_home_simplified.json` already exists in `uploads`
      - Config `<file_prefix>_config.json` exists and contains API details
    """
    logging.info("========================================================")
    logging.info("[HOME] Started Home Page Assembly Step")

    data_to_process = processed_json
    if len(args) > 1 and isinstance(args[1], dict):
        data_to_process = args[1]

    if not isinstance(data_to_process, dict):
        logging.error("[HOME] Input data pipeline is misconfigured (expected dict). Skipping home page step.")
        append_home_debug_log("init_error", {"reason": "invalid_previous_step_data"})
        return {"status": "error", "reason": "invalid_previous_step_data", "file_prefix": None}

    file_prefix = kwargs.get("file_name") or data_to_process.get("file_prefix")
    if not file_prefix:
        logging.error("[HOME] Missing 'file_prefix' for homepage processing. Skipping home page step.")
        append_home_debug_log("init_error", {"reason": "missing_file_prefix"})
        return {"status": "error", "reason": "missing_file_prefix", "file_prefix": None}

    try:
        settings = load_settings_home(file_prefix)
        if not settings:
            logging.error("[HOME] Could not load user configuration. Skipping homepage assembly.")
            append_home_debug_log("config_error", {"reason": "config_load_failed", "file_prefix": file_prefix})
            return {"status": "error", "reason": "config_load_failed", "file_prefix": file_prefix}

        # Align config keys with main assembly step (process_assembly.py) and add fallbacks
        api_base_url = settings.get("target_site_url")
        raw_token = settings.get("cms_login_token") or settings.get("auth_token")
        site_id = settings.get("site_id") if settings.get("site_id") is not None else settings.get("destination_id")
        
        # Set site_id for home debug logging
        if site_id:
            set_current_home_site_id(site_id)
            logging.info(f"[HOME] Using site_id: {site_id} for file organization")

        append_home_debug_log(
            "config_loaded",
            {
                "file_prefix": file_prefix,
                "api_base_url_present": bool(api_base_url),
                "token_present": bool(raw_token),
                "site_id": site_id,
            },
            site_id=site_id
        )

        if (
            not api_base_url
            or not raw_token
            or not isinstance(raw_token, str)
            or not raw_token.strip()
            or site_id is None
        ):
            logging.error("[HOME] Target URL, CMS Login Token, or 'site_id' missing in configuration. Skipping home page.")
            append_home_debug_log(
                "config_error",
                {
                    "reason": "incomplete_config",
                    "api_base_url_present": bool(api_base_url),
                    "token_present": bool(raw_token),
                    "site_id": site_id,
                },
            )
            return {"status": "error", "reason": "incomplete_config", "file_prefix": file_prefix}

        api_headers = {
            "Content-Type": "application/json",
            "ms_cms_clientapp": "ProgrammingApp",
            "Authorization": f"Bearer {raw_token}",
        }

        # Load home_simplified.json
        home_simplified_file = os.path.join(UPLOAD_FOLDER, f"{file_prefix}_home_simplified.json")
        if not os.path.exists(home_simplified_file):
            logging.warning(f"[HOME] Home page simplified JSON not found: {home_simplified_file}")
            logging.warning("[HOME] Skipping home page assembly and continuing with inner pages pipeline.")
            append_home_debug_log(
                "home_json_missing",
                {"file_prefix": file_prefix, "home_simplified_file": home_simplified_file},
            )
            return {
                "status": "skipped",
                "reason": "home_simplified.json not found",
                "file_prefix": file_prefix,
            }

        append_home_debug_log(
            "home_json_found",
            {"file_prefix": file_prefix, "home_simplified_file": home_simplified_file},
        )

        with open(home_simplified_file, "r", encoding="utf-8") as f:
            home_payload = json.load(f)

        # Build component cache
        logging.info("[HOME] Loading V-Component cache for homepage...")
        vcomponent_cache = GetAllVComponents(api_base_url, api_headers, page_size=1000)
        if not isinstance(vcomponent_cache, list) or not vcomponent_cache:
            logging.warning("[HOME] V-Component cache is empty or invalid. Homepage assembly may fail.")
            append_home_debug_log("vcomponent_cache_warning", {"valid_list": isinstance(vcomponent_cache, list), "len": len(vcomponent_cache) if isinstance(vcomponent_cache, list) else None})

        # Assemble home page
        start_t = time.time()
        assemble_home_page_templates_home(home_payload, vcomponent_cache, api_base_url, site_id, api_headers)
        elapsed = time.time() - start_t
        HOMEPAGE_TIMING_TRACKER.setdefault("assemble_home_page_templates_home", []).append(elapsed)

        # Publish queued home pages (if any)
        published_count = publish_queued_home_pages(api_base_url, api_headers, site_id)

        append_home_debug_log(
            "home_step_complete",
            {
                "file_prefix": file_prefix,
                "elapsed_seconds": elapsed,
                "published_count": published_count,
            },
        )

        return {
            "status": "success",
            "file_prefix": file_prefix,
            "homepage_published_count": published_count,
            "timing": {"assemble_home_page_templates_home": elapsed},
        }

    except Exception as e:
        logging.error(f"[HOME] UNEXPECTED ERROR in homepage step: {e}")
        logging.exception("[HOME] Full traceback:")
        append_home_debug_log("exception", {"file_prefix": file_prefix, "error": str(e)})
        # Do NOT raise - allow pipeline to continue to inner pages
        return {"status": "error", "reason": "exception", "details": str(e), "file_prefix": file_prefix}


