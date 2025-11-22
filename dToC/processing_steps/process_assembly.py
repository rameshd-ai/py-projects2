# File: processing_steps/process_assembly.py
import time
import logging
import json
import os
import csv 
from typing import Dict, Any, List, Union

# ================= CONFIG/PLACEHOLDER (MUST BE REAL PATH IN PRODUCTION) =================
# NOTE: In a production environment, UPLOAD_FOLDER should be imported from your main config file.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, '..', 'uploads')
# ======================================================================================

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- 1. GLOBAL STATUS TRACKER ---
ASSEMBLY_STATUS_LOG: List[Dict[str, Any]] = [] 

# ================= Helper Functions (Unchanged) =================
def check_component_availability(component_name: str) -> bool:
    available_components = {
        "M1-Inside Hero", "L1-Image Intro", "L29-Timeline", "M2-No image Hero",
        "L18-Contact Us Map", "L17-Bullet Points Snippet", "L20-Form With Image",
        "L23-Contact Info", "L2-Content Only Intro"
    }
    return component_name in available_components

def add_records_for_page(page_name: str):
    logging.info(f"     a) Adding records/metadata for page: {page_name}")
    time.sleep(0.01)

def add_component_to_page(page_name: str, component_name: str):
    logging.info(f"     b) Adding component '{component_name}' to page: {page_name}")
    time.sleep(0.01)

def do_mapping(page_name: str, component_name: str):
    logging.info(f"     c) Performing data mapping for {component_name} on {page_name}")
    time.sleep(0.01)

def publish_page_immediately(page_name: str):
    logging.info(f"     d) Marking page {page_name} for immediate publishing.")
    time.sleep(0.01)

# ================= Core Processing Logic and Traversal (MODIFIED) =================

def _process_page_components(page_data: Dict[str, Any], page_level: int, hierarchy: List[str]):
    page_name = page_data.get('page_name', 'UNKNOWN_PAGE')
    components = page_data.get('components', [])

    if not components:
        # 🎯 FIX: Explicitly log a status entry for pages with no components
        status_entry = {
            "page": page_name,
            "component": "N/A",
            "level": page_level,
            "hierarchy": " > ".join(hierarchy + [page_name]),
            "available": False, 
            "status": "SKIPPED: Page had no components defined."
        }
        ASSEMBLY_STATUS_LOG.append(status_entry)
        logging.warning(f"Page **{page_name}** (Level {page_level}) has no components to process. Logged as skipped.")
        return

    for component_name in components:
        status_entry = {
            "page": page_name,
            "component": component_name,
            "level": page_level,
            "hierarchy": " > ".join(hierarchy + [page_name]),
            "available": False, 
            "status": "SKIPPED: Component not available."
        }
        
        if check_component_availability(component_name):
            logging.info(f"✅ Component '{component_name}' is available. Starting assembly for **{page_name}**.")
            
            status_entry["available"] = True
            status_entry["status"] = "SUCCESS: Assembled and marked for publishing."
            
            add_records_for_page(page_name)
            add_component_to_page(page_name, component_name)
            do_mapping(page_name, component_name)
            publish_page_immediately(page_name)
            
        else:
            logging.warning(f"❌ Component '{component_name}' **NOT AVAILABLE** for page **{page_name}**. Skipping assembly.")
        
        ASSEMBLY_STATUS_LOG.append(status_entry)

def assemble_page_templates_level4(page_data: Dict[str, Any], page_level: int, hierarchy: List[str]):
    logging.info(f"\n--- Level {page_level} Page: {page_data.get('page_name')} ---")
    _process_page_components(page_data, page_level, hierarchy)

def assemble_page_templates_level3(page_data: Dict[str, Any], page_level: int, hierarchy: List[str]):
    logging.info(f"\n--- Level {page_level} Page: {page_data.get('page_name')} ---")
    _process_page_components(page_data, page_level, hierarchy)
    
    current_page_name = page_data.get('page_name', 'UNKNOWN_PAGE')
    new_hierarchy = hierarchy + [current_page_name]
    new_level = page_level + 1
    
    for sub_page_data in page_data.get("sub_pages", []):
        assemble_page_templates_level4(sub_page_data, new_level, new_hierarchy)

def assemble_page_templates_level2(page_data: Dict[str, Any], page_level: int, hierarchy: List[str]):
    logging.info(f"\n--- Level {page_level} Page: {page_data.get('page_name')} ---")
    _process_page_components(page_data, page_level, hierarchy)
    
    current_page_name = page_data.get('page_name', 'UNKNOWN_PAGE')
    new_hierarchy = hierarchy + [current_page_name]
    new_level = page_level + 1
    
    for sub_page_data in page_data.get("sub_pages", []):
        assemble_page_templates_level3(sub_page_data, new_level, new_hierarchy)

def assemble_page_templates_level1(processed_json: Dict[str, Any]):
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
        _process_page_components(top_level_page, initial_level, initial_hierarchy)
        
        next_level = initial_level + 1
        new_hierarchy = initial_hierarchy + [current_page_name]
        
        for sub_page_data in top_level_page.get("sub_pages", []):
            # assemble_page_templates_level2(sub_page_data, next_level, new_hierarchy)
            pass

    logging.info("\n========================================================")
    logging.info("END: Component-Based Template Assembly Traversal Complete")
    logging.info("========================================================")


# ================= Main Entry Function (SAVES CSV) =================

def run_assembly_processing_step(processed_json: Union[Dict[str, Any], str], *args, **kwargs) -> Dict[str, Any]:
    
    # --- 🛑 DEBUGGING START 🛑 ---
    print("\n" + "="*80)
    logging.info("DEBUG: Incoming Parameters for run_assembly_processing_step")
    logging.info(f"DEBUG: Original Type of processed_json: {type(processed_json)}")
    content_preview = str(processed_json)[:100]
    if isinstance(processed_json, dict):
        content_preview = f"Keys: {list(processed_json.keys())}"
    logging.info(f"DEBUG: Content of processed_json: {content_preview}")
    logging.info(f"DEBUG: Content of *args: {args}")
    logging.info(f"DEBUG: Content of **kwargs: {kwargs}")
    print("="*80 + "\n")
    # --- 🛑 DEBUGGING END ---
    
    logging.info("Starting Assembling CMS Pages and Publishing...")
    
    # --- 1. REASSIGNMENT FIX (Handling the misconfigured pipeline) ---
    data_to_process = processed_json
    if len(args) > 1 and isinstance(args[1], dict):
        data_to_process = args[1]
    
    # --- 2. FINAL VALIDATION ---
    if not isinstance(data_to_process, dict):
        logging.error(f"FATAL ERROR: Could not extract data dictionary. Final type was: {type(data_to_process)}.")
        raise TypeError("Input data pipeline is misconfigured; expected dictionary not found in processed_json or args[1].")
        
    # --- 3. RETRIEVE FILE PREFIX ---
    file_prefix = kwargs.get("file_name") or data_to_process.get("file_prefix") 
    
    if not file_prefix:
        logging.error("File prefix not found in data. Cannot retrieve file.")
        raise ValueError("Processing aborted: Missing file identifier ('file_prefix').")

    # --- 4. CONSTRUCT FILENAME AND READ FILE (Claim Check) ---
    FILE_SUFFIX = "_simplified.json"
    full_filename = f"{file_prefix}{FILE_SUFFIX}"
    file_path = os.path.join(UPLOAD_FOLDER, full_filename)

    print("============================================================================")
    logging.info(f"Successfully extracted file prefix: **{file_prefix}**")
    logging.info(f"Attempting to read full payload from: **{file_path}**")
    print("============================================================================")
    
    full_payload: Dict[str, Any] = {}
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            full_payload = json.load(f)
        
        logging.info(f"Successfully loaded full JSON payload (Keys: {list(full_payload.keys())[:3]}...)")

    except FileNotFoundError:
        logging.error(f"Required file not found: {file_path}")
        raise FileNotFoundError(f"Processing aborted: Could not find file {full_filename} in uploads.")
    except json.JSONDecodeError as e:
        logging.error(f"Error decoding JSON from file {full_filename}: {e}")
        raise
    
    # --- 5. Assembly Execution ---
    assemble_page_templates_level1(full_payload)

    # --- 6. SAVE THE STATUS FILE AS CSV ---
    # Define the output file details
    STATUS_SUFFIX = "_assembly_report.csv" 
    status_filename = f"{file_prefix}{STATUS_SUFFIX}"
    status_file_path = os.path.join(UPLOAD_FOLDER, status_filename)
    
    # Define CSV fields based on ASSEMBLY_STATUS_LOG structure
    fieldnames = ["page", "component", "level", "hierarchy", "available", "status"]
    
    try:
        with open(status_file_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            # Write the header row
            writer.writeheader()
            
            # Write the data rows
            writer.writerows(ASSEMBLY_STATUS_LOG)
        
        logging.info(f"✅ Status report successfully saved as CSV to: {status_file_path}")
        
    except IOError as e:
        logging.error(f"Failed to write CSV status file {status_filename}: {e}")

    # --- 7. Prepare Final Output (for pipeline continuation/return) ---
    final_output = {
        "assembly_status": "SUCCESS: Pages and components processed.",
        "file_prefix": file_prefix, 
        "title": full_payload.get("title", "N/A"), 
        "pages_checked_count": data_to_process.get("pages_checked_count"),
        "report_filename": status_filename, 
    }

    # Clear the log for the next pipeline run
    ASSEMBLY_STATUS_LOG.clear() 
    
    # --- 8. Return result for the next step (e.g., cleanup) ---
    return final_output