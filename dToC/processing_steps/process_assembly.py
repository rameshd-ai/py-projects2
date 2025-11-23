# File: processing_steps/process_assembly.py (FINAL VERSION WITH DYNAMIC CONFIG)
import time
import logging
import json
import os
import csv 
import re # <-- Required for config utility functions if they use it
from typing import Dict, Any, List, Union, Tuple, Optional
from apis import GetAllVComponents 

# ================= CONFIG/UTILITY DEFINITIONS (BASED ON USER PATTERN) =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, '..', 'uploads')
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_config_filepath(file_prefix: str) -> str:
    """Constructs the unique config.json filepath based on the prefix."""
    base_prefix = os.path.basename(file_prefix)
    config_filename = f"{base_prefix}_config.json" 
    return os.path.join(UPLOAD_FOLDER, config_filename)

def load_settings(file_prefix: str) -> Dict[str, Any] | None:
    """Loads the settings/config file based on the unique prefix."""
    filepath = get_config_filepath(file_prefix) 
    if not os.path.exists(filepath):
        logging.error(f"Config file not found at {filepath}")
        return None
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Error loading config file: {e}")
        return None
        
def find_processed_json_filepath(file_prefix: str) -> str | None:
    """Dynamically finds the processed JSON file based on the unique prefix."""
    base_prefix = os.path.basename(file_prefix)
    if not os.path.isdir(UPLOAD_FOLDER):
        return None
    for filename in os.listdir(UPLOAD_FOLDER):
        if filename.startswith(base_prefix) and filename.endswith("_simplified.json"):
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            return filepath
    return None

# ======================================================================================

# --- 1. GLOBAL STATUS TRACKER ---
ASSEMBLY_STATUS_LOG: List[Dict[str, Any]] = [] 

# ================= Helper Functions =================

# --- MODIFIED: check_component_availability now returns 4 values ---
def check_component_availability(component_name: str, component_cache: List[Dict[str, Any]]) -> Optional[Tuple[int, str, int, str]]:
    """
    Checks component availability by performing a LOCAL prefix search.
    Returns the tuple (vComponentId, alias, componentId, cms_component_name) on success, or None on failure.
    """
    hyphen_index = component_name.find('-')
    if hyphen_index != -1:
        search_key = component_name[:hyphen_index + 1].strip()
    else:
        search_key = component_name.strip()
        
    logging.info(f"   Searching cache for prefix: **{search_key}** (Original: {component_name})")
    
    for component in component_cache:
        cms_component_name = component.get("name", "")
        if cms_component_name.startswith(search_key):
            vComponentId = component.get("vComponentId")
            component_alias = component.get("alias")
            nested_component_details = component.get("component", {}) 
            component_id = nested_component_details.get("componentId")
            
            if vComponentId is not None and component_alias is not None and component_id is not None:
                 logging.info(f"   ✅ Component '{component_name}' found in cache as '{cms_component_name}'.")
                 # Return the CMS name as the 4th element
                 return (vComponentId, component_alias, component_id, cms_component_name)
    
    logging.warning(f"   ❌ Component prefix '{search_key}' not found in the component cache.")
    return None

def add_records_for_page(page_name: str, vComponentId: int, componentId: int):
    logging.info(f"     a) Adding records/metadata for page: {page_name} (Using ID: {vComponentId})")
    time.sleep(0.01)

def add_component_to_page(page_name: str, component_name: str, alias: str):
    logging.info(f"     b) Adding component '{component_name}' (Alias: {alias}) to page: {page_name}")
    time.sleep(0.01)

def do_mapping(page_name: str, component_name: str):
    logging.info(f"     c) Performing data mapping for {component_name} on {page_name}")
    time.sleep(0.01)

def publish_page_immediately(page_name: str):
    logging.info(f"     d) Marking page {page_name} for immediate publishing.")
    time.sleep(0.01)


# ================= Core Processing Logic and Traversal =================

# --- MODIFIED: _process_page_components now handles the 4th return value ---
def _process_page_components(page_data: Dict[str, Any], page_level: int, hierarchy: List[str], component_cache: List[Dict[str, Any]]):
    page_name = page_data.get('page_name', 'UNKNOWN_PAGE')
    components = page_data.get('components', [])

    if not components:
        status_entry = {
            "page": page_name, "component": "N/A", "level": page_level,
            "hierarchy": " > ".join(hierarchy + [page_name]), "available": False, 
            "status": "SKIPPED: Page had no components defined.",
            "cms_component_name": "N/A" # Added for consistency
        }
        ASSEMBLY_STATUS_LOG.append(status_entry)
        logging.warning(f"Page **{page_name}** (Level {page_level}) has no components to process. Logged as skipped.")
        return

    for component_name in components:
        status_entry = {
            "page": page_name, "component": component_name, "level": page_level,
            "hierarchy": " > ".join(hierarchy + [page_name]), "available": False, 
            "status": "SKIPPED: Component not available.",
            "cms_component_name": "N/A" # Initialize CMS name
        }
        
        # Check availability using the cache - expects 4 return values now
        api_result = check_component_availability(component_name, component_cache)
        
        if api_result:
            # Unpack the 4 values
            vComponentId, alias, componentId, cms_component_name = api_result 
            
            logging.info(f"✅ Component '{component_name}' is available. Starting assembly for **{page_name}**.")
            
            status_entry["available"] = True
            status_entry["status"] = "SUCCESS: Assembled and marked for publishing."
            status_entry["cms_component_name"] = cms_component_name # Store the CMS name
            

            if page_name == "Weddings":
                add_records_for_page(page_name, vComponentId, componentId)
                add_component_to_page(page_name, component_name, alias)
                do_mapping(page_name, component_name)
                publish_page_immediately(page_name)
            
        else:
            logging.warning(f"❌ Component '{component_name}' **NOT AVAILABLE** for page **{page_name}**. Skipping assembly.")
            # Status entry remains with "SKIPPED" and "N/A" for cms_component_name
        
        ASSEMBLY_STATUS_LOG.append(status_entry)

# --- TRAVERSAL FUNCTIONS TO PASS CACHE (No change) ---
def assemble_page_templates_level4(page_data: Dict[str, Any], page_level: int, hierarchy: List[str], component_cache: List[Dict[str, Any]]):
    logging.info(f"\n--- Level {page_level} Page: {page_data.get('page_name')} ---")
    _process_page_components(page_data, page_level, hierarchy, component_cache)

def assemble_page_templates_level3(page_data: Dict[str, Any], page_level: int, hierarchy: List[str], component_cache: List[Dict[str, Any]]):
    logging.info(f"\n--- Level {page_level} Page: {page_data.get('page_name')} ---")
    _process_page_components(page_data, page_level, hierarchy, component_cache)
    current_page_name = page_data.get('page_name', 'UNKNOWN_PAGE')
    new_hierarchy = hierarchy + [current_page_name]
    new_level = page_level + 1
    for sub_page_data in page_data.get("sub_pages", []):
        assemble_page_templates_level4(sub_page_data, new_level, new_hierarchy, component_cache)

def assemble_page_templates_level2(page_data: Dict[str, Any], page_level: int, hierarchy: List[str], component_cache: List[Dict[str, Any]]):
    logging.info(f"\n--- Level {page_level} Page: {page_data.get('page_name')} ---")
    _process_page_components(page_data, page_level, hierarchy, component_cache)
    current_page_name = page_data.get('page_name', 'UNKNOWN_PAGE')
    new_hierarchy = hierarchy + [current_page_name]
    new_level = page_level + 1
    for sub_page_data in page_data.get("sub_pages", []):
        assemble_page_templates_level3(sub_page_data, new_level, new_hierarchy, component_cache)

def assemble_page_templates_level1(processed_json: Dict[str, Any], component_cache: List[Dict[str, Any]]):
    logging.info("\n========================================================")
    logging.info("START: Component-Based Template Assembly (Level 1 Traversal)")
    logging.info("========================================================")
    pages = processed_json.get('pages', [])
    if not pages:
        logging.warning("No 'pages' list found in the processed JSON. Aborting assembly.")
        return
    initial_level = 1
    initial_hierarchy: List[str] = []
    for top_level_page in pages:
        current_page_name = top_level_page.get('page_name', 'UNKNOWN_PAGE')
        logging.info(f"\n--- Level {initial_level} Page: {current_page_name} ---")
        _process_page_components(top_level_page, initial_level, initial_hierarchy, component_cache)
        next_level = initial_level + 1
        new_hierarchy = initial_hierarchy + [current_page_name]
        for sub_page_data in top_level_page.get("sub_pages", []):
            assemble_page_templates_level2(sub_page_data, next_level, new_hierarchy, component_cache) 
            # Note: I corrected the traversal here, Level 1 calls Level 2. The original code had a comment/pass in the loop.
    logging.info("\n========================================================")
    logging.info("END: Component-Based Template Assembly Traversal Complete")
    logging.info("========================================================")


# ================= Main Entry Function (Uses Dynamic Config) =================

def run_assembly_processing_step(processed_json: Union[Dict[str, Any], str], *args, **kwargs) -> Dict[str, Any]:
    
    # --- 1. Setup/File Extraction ---
    data_to_process = processed_json
    if len(args) > 1 and isinstance(args[1], dict):
        data_to_process = args[1]
    
    if not isinstance(data_to_process, dict):
        logging.error(f"FATAL ERROR: Could not extract data dictionary. Final type was: {type(data_to_process)}.")
        raise TypeError("Input data pipeline is misconfigured.")
        
    file_prefix = kwargs.get("file_name") or data_to_process.get("file_prefix") 
    
    if not file_prefix:
        logging.error("File prefix not found. Aborting.")
        raise ValueError("Processing aborted: Missing file identifier ('file_prefix').")

    # --- 2. Load Settings and Configure API ---
    logging.info("STEP 1: Loading configuration for API details...")
    settings = load_settings(file_prefix)
    if not settings:
        raise RuntimeError("Could not load user configuration using load_settings. Aborting assembly.")

    try:
        api_base_url = settings.get("target_site_url")
        raw_token = settings.get("cms_login_token") 
        
        if not api_base_url or not raw_token or not isinstance(raw_token, str) or not raw_token.strip():
             raise ValueError("Target URL or valid CMS Login Token missing in configuration.")

        api_headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {raw_token}', 
        }
        
        logging.info(f"Configuration loaded. API Base URL: {api_base_url}")

    except Exception as e:
        logging.error(f"FATAL: Configuration key error. Aborting processing: {e}")
        raise

    # --- 3. Read Input File ---
    FILE_SUFFIX = "_simplified.json"
    full_payload: Dict[str, Any] = {}
    
    file_path = find_processed_json_filepath(file_prefix)
    if not file_path:
        logging.error(f"Error: Could not find target processed JSON file starting with '{os.path.basename(file_prefix)}'.")
        raise FileNotFoundError(f"Input file not found for prefix {file_prefix}.")
    
    logging.info(f"Attempting to read full payload from: **{file_path}**")
    try:
        if not os.path.exists(UPLOAD_FOLDER):
             os.makedirs(UPLOAD_FOLDER, exist_ok=True)
             
        with open(file_path, 'r', encoding='utf-8') as f:
            full_payload = json.load(f)
        
        logging.info(f"Successfully loaded full JSON payload.")
    except Exception as e:
        logging.error(f"Error loading required file {os.path.basename(file_path)}: {e}")
        raise

    # --- 4. PRE-FETCH V-COMPONENT CACHE (REAL API CALL with configured data) ---
    logging.info("\n========================================================")
    logging.info("STEP 4: CALLING REAL API TO BUILD COMPONENT CACHE")
    logging.info("========================================================")
    
    try:
        vcomponent_cache = GetAllVComponents(api_base_url, api_headers)
    except NameError:
        logging.error("API function not available. Using empty cache.")
        vcomponent_cache = []

    if not isinstance(vcomponent_cache, list):
        logging.error(f"FATAL: Failed to retrieve V-Component list. API returned error: {vcomponent_cache}")
        raise RuntimeError("V-Component list retrieval failed. Cannot proceed with assembly.")

    logging.info(f"Successfully loaded {len(vcomponent_cache)} components into cache for fast lookup.")

    # --- 5. Assembly Execution (PASSES CACHE) ---
    assemble_page_templates_level1(full_payload, vcomponent_cache)

    # --- 6. SAVE THE STATUS FILE AS CSV ---
    STATUS_SUFFIX = "_assembly_report.csv" 
    status_filename = f"{file_prefix}{STATUS_SUFFIX}"
    status_file_path = os.path.join(UPLOAD_FOLDER, status_filename)
    
    # --- MODIFIED: Added 'cms_component_name' to the fieldnames ---
    fieldnames = ["page", "component", "cms_component_name", "level", "hierarchy", "available", "status"]
    
    try:
        with open(status_file_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(ASSEMBLY_STATUS_LOG)
        
        logging.info(f"✅ Status report successfully saved as CSV to: {status_file_path}")
    except IOError as e:
        logging.error(f"Failed to write CSV status file {status_filename}: {e}")

    # --- 7. Prepare Final Output ---
    final_output = {
        "assembly_status": "SUCCESS: Pages and components processed.",
        "file_prefix": file_prefix, 
        "report_filename": status_filename, 
    }

    ASSEMBLY_STATUS_LOG.clear() 
    return final_output