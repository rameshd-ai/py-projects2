# File: processing_steps/process_assembly.py (FINAL VERSION WITH DYNAMIC CONFIG)
import time
import logging
import json
import os
import base64
import csv 
import re 
import glob
import requests
import uuid # <-- Required for generating pageSectionGuid
import zipfile # <-- Required for handling exported component files
import html # <-- Required for HTML entity decoding
from typing import Dict, Any, List, Union, Tuple, Optional
# Assuming apis.py now contains: GetAllVComponents, export_mi_block_component
from apis import GetAllVComponents, export_mi_block_component,addUpdateRecordsToCMS,addUpdateRecordsToCMS_bulk,generatecontentHtml,GetTemplatePageByName,psMappingApi,psPublishApi,GetPageCategoryList,CustomGetComponentAliasByName
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
    """
    DYNAMically finds the processed JSON file for INNER PAGES based on the unique prefix.

    IMPORTANT:
        - Must return ONLY the main `<prefix>_simplified.json`
        - MUST NOT return `<prefix>_home_simplified.json`
    """
    base_prefix = os.path.basename(file_prefix)
    if not os.path.isdir(UPLOAD_FOLDER):
        return None

    chosen_path: Optional[str] = None
    for filename in os.listdir(UPLOAD_FOLDER):
        # We only want "<prefix>_simplified.json", not "<prefix>_home_simplified.json"
        if (
            filename.startswith(base_prefix)
            and filename.endswith("_simplified.json")
            and not filename.endswith("_home_simplified.json")
        ):
            chosen_path = os.path.join(UPLOAD_FOLDER, filename)
            break

    if chosen_path:
        append_debug_log(
            "find_processed_json_filepath",
            {"file_prefix": file_prefix, "chosen_file": chosen_path},
        )
    else:
        append_debug_log(
            "find_processed_json_filepath",
            {"file_prefix": file_prefix, "chosen_file": None},
        )

    return chosen_path

# ======================================================================================

# --- 1. GLOBAL STATUS TRACKER ---
ASSEMBLY_STATUS_LOG: List[Dict[str, Any]] = [] 

# --- 2. GLOBAL TIMING TRACKER ---
TIMING_TRACKER: Dict[str, List[float]] = {}  # Function name -> list of execution times

# --- 3. GLOBAL GUID TRACKER (for verification) ---
COMPONENT_GUID_TRACKER: Dict[str, str] = {}  # component_id -> pageSectionGuid (for verification)

# --- 4. GLOBAL PAGE PUBLISH QUEUE ---
# Each entry: {"page_id": int, "page_name": str, "header_footer_details": Dict[str, Any]}
PAGES_TO_PUBLISH: List[Dict[str, Any]] = []

# --- 5. DEBUG LOG FILE (for deep investigation) ---
DEBUG_LOG_FILE = os.path.join(UPLOAD_FOLDER, "assembly_debug.log")

def append_debug_log(section: str, data: Dict[str, Any]) -> None:
    """
    Writes structured debug information to a separate log file.
    This is used only for deep debugging (e.g., page/component flows).
    """
    try:
        os.makedirs(UPLOAD_FOLDER, exist_ok=True)
        entry = {
            "section": section,
            "data": data,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        with open(DEBUG_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        # Never let debug logging break the main flow
        pass

# ================= Helper Functions =================

# --- MODIFIED: check_component_availability now returns 4 values ---
# def check_component_availability(component_name: str, component_cache: List[Dict[str, Any]]) -> Optional[Tuple[int, str, int, str]]:
#     """
#     Checks component availability by performing a LOCAL prefix search.
#     Returns the tuple (vComponentId, alias, componentId, cms_component_name) on success, or None on failure.
#     """
#     hyphen_index = component_name.find('-')
#     if hyphen_index != -1:
#         search_key = component_name[:hyphen_index + 1].strip()
#     else:
#         search_key = component_name.strip()
        
#     logging.info(f"    Searching cache for prefix: **{search_key}** (Original: {component_name})")
    
#     for component in component_cache:
#         cms_component_name = component.get("name", "")
#         if cms_component_name.startswith(search_key):
#             vComponentId = component.get("vComponentId")
#             component_alias = component.get("alias")
#             nested_component_details = component.get("component", {}) 
#             component_id = nested_component_details.get("componentId")
            
#             if vComponentId is not None and component_alias is not None and component_id is not None:
#                  logging.info(f"    [SUCCESS] Component '{component_name}' found in cache as '{cms_component_name}'.")
#                  # Return the CMS name as the 4th element
#                  return (vComponentId, component_alias, component_id, cms_component_name)
    
#     logging.warning(f"    [ERROR] Component prefix '{search_key}' not found in the component cache.")
#     return None




def check_component_availability(component_name: str, component_cache: List[Dict[str, Any]]) -> Optional[Tuple[int, str, int, str]]:
    """
    Checks component availability by performing a LOCAL prefix search up to the first hyphen.
    Returns the tuple (vComponentId, alias, componentId, cms_component_name) on success, or None on failure.
    """
    hyphen_index = component_name.find('-')
    
    # 1. Determine the search key: The component code up to AND including the first hyphen.
    if hyphen_index != -1:
        # Example: 'L10-2 Column Snippet' -> 'L10-'
        search_key = component_name[:hyphen_index + 1].strip()
    else:
        # If no hyphen (e.g., 'Gallery'), use the whole name.
        search_key = component_name.strip()
        
    logging.info(f"    Searching cache for prefix: **{search_key}** (Original: {component_name})")
    
    for component in component_cache:
        cms_component_name = component.get("name", "")
        
        # 2. Perform the prefix match against the CMS component name.
        # This will match 'L10-2 Column Snippet' (cache) against 'L10-' (search_key).
        if cms_component_name.startswith(search_key):
            
            # Additional check: If the search key is only the prefix (ends in '-'), 
            # we must ensure the cache name isn't identical to the search key 
            # (unless that's a valid component name).
            # We assume if it matches the prefix, it is the correct component family.
            
            vComponentId = component.get("vComponentId")
            component_alias = component.get("alias")
            nested_component_details = component.get("component", {}) 
            component_id = nested_component_details.get("componentId")
            
            if vComponentId is not None and component_alias is not None and component_id is not None:
                logging.info(f"    [SUCCESS] Component '{component_name}' found in cache as '{cms_component_name}'.")
                # Return the CMS name as the 4th element
                return (vComponentId, component_alias, component_id, cms_component_name)
    
    logging.warning(f"    [ERROR] Component prefix '{search_key}' not found in the component cache.")
    return None


def add_levels_to_records(records_file_path: str) -> bool:
    """
    Adds 'level' field to each record in MiBlockComponentRecords.json based on ParentId hierarchy.
    
    Logic:
    - Records with ParentId = 0 (or null) are root records -> level = 0
    - Records whose ParentId matches another record's Id are children -> level = parent_level + 1
    - Continues recursively for deeper levels
    
    Args:
        records_file_path: Path to the MiBlockComponentRecords.json file
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Read the records file
        with open(records_file_path, 'r', encoding='utf-8') as f:
            records_data = json.load(f)
        
        component_records = records_data.get("componentRecords", [])
        if not component_records:
            logging.warning(f"No componentRecords found in {records_file_path}")
            return False
        
        # Create a map of Id -> record for quick lookup
        records_map = {}
        for record in component_records:
            record_id = record.get("Id")
            if record_id is not None:
                records_map[record_id] = record
                # Initialize level to -1 (unknown)
                record["level"] = -1
        
        # First pass: Set level 0 for root records (ParentId = 0 or null)
        for record in component_records:
            parent_id = record.get("ParentId")
            if parent_id is None or parent_id == 0:
                record["level"] = 0
        
        # Iterative pass: Resolve child levels
        max_depth = len(component_records)  # Safety limit
        current_level = 0
        
        while current_level < max_depth:
            changes_made = False
            next_level = current_level + 1
            
            # Find all records with unknown level (-1) and check if their parent has current_level
            for record in component_records:
                if record.get("level") == -1:  # Only process unclassified records
                    parent_id = record.get("ParentId")
                    
                    # Check if parent exists and has the current level
                    if parent_id and parent_id in records_map:
                        parent_record = records_map[parent_id]
                        if parent_record.get("level") == current_level:
                            record["level"] = next_level
                            changes_made = True
            
            if not changes_made:
                break  # No more levels to resolve
            
            current_level = next_level
        
        # Check for any remaining unclassified records (orphaned records)
        # Try to resolve via ParentComponentId; fallback to level 1 to avoid 999
        orphaned_records = [r for r in component_records if r.get("level") == -1]
        if orphaned_records:
            logging.warning(f"Found {len(orphaned_records)} unclassified records (orphaned or circular references). Attempting fix via ParentComponentId.")

            # Map ComponentId -> first record with a resolved level for that component
            component_level_map: Dict[Any, int] = {}
            for rec in component_records:
                comp_id = rec.get("ComponentId")
                if comp_id is not None and rec.get("level", -1) >= 0 and comp_id not in component_level_map:
                    component_level_map[comp_id] = rec.get("level")

            fixed_count = 0
            for record in orphaned_records:
                parent_component_id = record.get("ParentComponentId")
                if parent_component_id in component_level_map:
                    record["level"] = component_level_map[parent_component_id] + 1
                    fixed_count += 1

            still_orphaned = [r for r in component_records if r.get("level") == -1]
            if still_orphaned:
                logging.warning(f"{len(still_orphaned)} records still orphaned after ParentComponentId pass; setting them to level 1 (fallback).")
                for record in still_orphaned:
                    record["level"] = 1

            logging.info(f"[LEVEL FIX] Orphaned resolved via ParentComponentId: {fixed_count}, fallback-to-level1: {len(still_orphaned)}")
        
        # Save the updated records back to the file
        with open(records_file_path, 'w', encoding='utf-8') as f:
            json.dump(records_data, f, indent=4, ensure_ascii=False)
        
        logging.info(f"[SUCCESS] Successfully added level fields to {len(component_records)} records")
        return True
        
    except FileNotFoundError:
        logging.error(f"Records file not found: {records_file_path}")
        return False
    except json.JSONDecodeError as e:
        logging.error(f"JSON decode error in {records_file_path}: {e}")
        return False
    except Exception as e:
        logging.error(f"Error adding levels to records: {e}")
        logging.exception("Full traceback:")
        return False


# --- MODIFIED: add_records_for_page now contains the complex file processing logic ---
def add_records_for_page(page_name: str, vComponentId: int, componentId: int, base_url: str, site_id: int, headers: Dict[str, str], component_alias: str):
    """
    Adds records/metadata for the page and performs component export/file processing.
    
    The logic simulates unpacking a result tuple to execute file export and polling.
    
    NOTE: `vComponentId`, `componentId`, and `component_alias` are now passed directly
    from the calling function (`_process_page_components`).
    """
    logging.info(f"    a) Adding records/metadata for page: {page_name} (Using ID: {vComponentId})")
    time.sleep(0.01)

    # Use the passed parameters to structure the required logic block
    vComponentId_dummy, component_alias_dummy, component_id = vComponentId, component_alias, componentId
    alias_result: Optional[Tuple[int, str, int]] = (vComponentId_dummy, component_alias_dummy, component_id) 
    
    if isinstance(alias_result, tuple):
        # Success: Unpack the alias (index 0) and ID (index 1)
        vComponentId_unpacked, component_alias_unpacked, component_id_unpacked = alias_result
        
        # print(f"  [INFO] Component ID: {component_id_unpacked}")
        # print(f"  [INFO] Component component_alias: {component_alias_unpacked}")
        # Generate unique pageSectionGuid for each component
        pageSectionGuid = str(uuid.uuid4()) 

        # Verify uniqueness: Check if this component already has a GUID (shouldn't happen, but verify)
        component_key = f"{component_id_unpacked}_{page_name}"
        if component_key in COMPONENT_GUID_TRACKER:
            existing_guid = COMPONENT_GUID_TRACKER[component_key]
            if existing_guid != pageSectionGuid:
                logging.warning(f"[GUID WARNING] Component '{component_alias_unpacked}' (ID: {component_id_unpacked}) on page '{page_name}' already has a different GUID: {existing_guid}")
            else:
                logging.info(f"[GUID] Component '{component_alias_unpacked}' (ID: {component_id_unpacked}) reusing existing GUID: {pageSectionGuid}")
        else:
            COMPONENT_GUID_TRACKER[component_key] = pageSectionGuid
            logging.info(f"[GUID] Generated unique pageSectionGuid for component '{component_alias_unpacked}' (ID: {component_id_unpacked}) on page '{page_name}': {pageSectionGuid}") 
        
        miBlockId = component_id_unpacked
        mi_block_folder = f"mi-block-ID-{miBlockId}"
        # Output directory is relative to the current working directory, not UPLOAD_FOLDER
        output_dir = os.path.join("output", str(site_id)) 
        save_folder = os.path.join(output_dir, mi_block_folder)
        os.makedirs(save_folder, exist_ok=True)
        
        # Check if component is already downloaded
        records_file_path = os.path.join(save_folder, "MiBlockComponentRecords.json")
        config_file_path = os.path.join(save_folder, "MiBlockComponentConfig.json")
        component_already_downloaded = os.path.exists(records_file_path) and os.path.exists(config_file_path)
        
        # Initialize variables to avoid NameError
        response_content = None
        content_disposition = None
        
        if component_already_downloaded:
            logging.info(f"Component ID {component_id_unpacked} already downloaded. Skipping download and unzip.")
            print(f"  [INFO] Component already exists at: {save_folder}")
        else:
            # Call the API function from apis.py
            response_content, content_disposition = export_mi_block_component(base_url, component_id_unpacked, site_id, headers)
        
        try:
            # 1. Save and Unzip the exported file
            if response_content:
                filename = (
                    content_disposition.split('filename=')[1].strip('"')
                    if content_disposition and 'filename=' in content_disposition
                    else f"site_{site_id}.zip"
                )
                file_path = os.path.join(save_folder, filename)

                with open(file_path, "wb") as file:
                    file.write(response_content)

                if zipfile.is_zipfile(file_path):
                    with zipfile.ZipFile(file_path, 'r') as zip_ref:
                        zip_ref.extractall(save_folder)
                    os.remove(file_path)
                else:
                    print(f"  [WARNING] Exported file {filename} is not a zip file.")
            else:
                logging.info("Skipping file save/unzip as export_mi_block_component returned no content.")
            
            # Give OS a moment to finish file operations after unzipping/deleting the zip.
            time.sleep(2) 

            # 2. Convert .txt files to .json (if they exist)
            logging.info("[PROCESSING] Starting TXT to JSON conversion...")
            txt_files_found = [f for f in os.listdir(save_folder) if f.endswith('.txt')]
            logging.info(f"   Found {len(txt_files_found)} .txt files to convert: {txt_files_found}")
            
            converted_count = 0
            for extracted_file in os.listdir(save_folder):
                extracted_file_path = os.path.join(save_folder, extracted_file)
                if extracted_file.endswith('.txt'):
                    new_file_path = os.path.splitext(extracted_file_path)[0] + '.json'
                    try:
                        logging.info(f"   Converting: {extracted_file} -> {os.path.basename(new_file_path)}")
                        # Read and process content inside the 'with' block
                        with open(extracted_file_path, 'r', encoding="utf-8") as txt_file:
                            content = txt_file.read()
                            json_content = json.loads(content)
                        
                        # Write to new file inside its own 'with' block
                        with open(new_file_path, 'w', encoding="utf-8") as json_file:
                            json.dump(json_content, json_file, indent=4)
                        
                        # Add a micro-sleep to help OS release the file handle before deletion
                        time.sleep(0.05) 
                        
                        os.remove(extracted_file_path)
                        converted_count += 1
                        logging.info(f"   [SUCCESS] Successfully converted: {extracted_file}")
                    except (json.JSONDecodeError, OSError) as e:
                        # Log the error but continue to the next file
                        logging.error(f"[ERROR] Error processing file {extracted_file_path}: {e}")
            
            logging.info(f"[SUCCESS] TXT to JSON conversion complete: {converted_count}/{len(txt_files_found)} files converted successfully")

            # --- POLLING LOGIC to wait for MiBlockComponentConfig.json to be accessible ---
            config_file_name = "MiBlockComponentConfig.json"
            config_file_path = os.path.join(save_folder, config_file_name)
            
            MAX_WAIT_SECONDS = 120 # 2 minutes max wait
            POLL_INTERVAL = 5      # Check every 5 seconds
            start_time = time.time()
            file_ready = False

            # print(f"Waiting up to {MAX_WAIT_SECONDS} seconds for {config_file_name} to be available...")

            while time.time() - start_time < MAX_WAIT_SECONDS:
                if os.path.exists(config_file_path):
                    # Try to open the file to check if it's locked
                    try:
                        with open(config_file_path, 'r') as f:
                            f.read(1) # Read a byte to confirm accessibility
                        file_ready = True
                        break
                    except IOError:
                        print(f"File {config_file_name} exists but is locked. Retrying in {POLL_INTERVAL}s...")
                else:
                    print(f"File {config_file_name} not found yet. Retrying in {POLL_INTERVAL}s...")
                
                time.sleep(POLL_INTERVAL)

            if not file_ready:
                raise FileNotFoundError(f"🚨 Timeout: Required configuration file {config_file_name} was not generated or released within {MAX_WAIT_SECONDS} seconds.")
            # --- END POLLING LOGIC ---
        
        except FileNotFoundError as e:
            logging.error(f"[ERROR] File Polling Failed: {e}")
            raise # Re-raise the error to halt assembly for this component/page
        
        # 3. Add level fields to MiBlockComponentRecords.json (for both downloaded and existing components)
        records_file_path = os.path.join(save_folder, "MiBlockComponentRecords.json")
        if os.path.exists(records_file_path):
            try:
                add_levels_to_records(records_file_path)
                logging.info(f"[SUCCESS] Added level fields to records in {records_file_path}")
            except Exception as e:
                logging.error(f"[ERROR] Error adding levels to records: {e}")

        createPayloadJson(site_id,miBlockId) #this is only to create ComponentHierarchy.json 
        createRecordsPayload(site_id,miBlockId) #this will fetch and create a single set of records for dummy data creates file ComponentRecordsTree.json
        #this is to add records of all levels
        mainComp(save_folder,component_id,pageSectionGuid,base_url,headers,component_alias,vComponentId)
        migrate_next_level_components(save_folder, pageSectionGuid, base_url, headers, level=1)
        migrate_next_level_components(save_folder, pageSectionGuid, base_url, headers, level=2)
        migrate_next_level_components(save_folder, pageSectionGuid, base_url, headers, level=3)

        # 2. Use the component_alias (string) for HTML generation
        section_payload = generatecontentHtml(1, component_alias, pageSectionGuid)
        
    else:
        # Failure: alias_result is an error dictionary
        print(f"  [FAILURE] Component '{component}' Error: {alias_result.get('details')}")

    return section_payload


def add_component_to_page(page_name: str, component_name: str, alias: str):
    logging.info(f"    b) Adding component '{component_name}' (Alias: {alias}) to page: {page_name}")
    time.sleep(0.01)

def do_mapping(page_name: str, component_name: str):
    logging.info(f"    c) Performing data mapping for {component_name} on {page_name}")
    time.sleep(0.01)

def publish_page_immediately(page_name: str):
    logging.info(f"    d) Marking page {page_name} for immediate publishing.")
    time.sleep(0.01)






def pageAction(base_url, headers,final_html,page_name,page_template_id,DefaultTitle,DefaultDescription,site_id,category_id,header_footer_details, page_component_ids: Optional[set] = None, page_component_names: Optional[List[str]] = None, component_cache: Optional[List[Dict[str, Any]]] = None):
    # Prepare payload for page creation
    page_content_bytes = final_html.encode("utf-8")
    base64_encoded_content = base64.b64encode(page_content_bytes).decode("utf-8")
    # page_name = page_name + "-Demo"
    payload = {
        "pageId": 0,
        "pageName": page_name,
        "pageAlias": page_name.lower().replace(' ', '-'),
        "pageContent": base64_encoded_content,
        "isPageStudioPage": True,
        "pageUpdatedBy": 0,
        "isUniqueMetaContent": True,
        "pageMetaTitle": DefaultTitle,
        "pageMetaDescription": DefaultDescription,
        "pageStopSEO": 1,
        "pageCategoryId": category_id,
        "pageProfileId": 0,
        "tags": ""
        }
    print(f"New page payload ready for '{page_name}'.")
    print(f"New page payload ready for '{payload}'.")
    print("before")
    print(page_template_id)

    logging.info(f"[TIMING] Starting CreatePage for page '{page_name}'...")
    create_start_time = time.time()
    data = CreatePage(base_url, headers, payload,page_template_id)
    create_time = time.time() - create_start_time
    logging.info(f"[TIMING] CreatePage completed in {create_time:.2f} seconds")
    
    # Track timing
    if "CreatePage" not in TIMING_TRACKER:
        TIMING_TRACKER["CreatePage"] = []
    TIMING_TRACKER["CreatePage"].append(create_time)
    
    # Check if CreatePage returned an error
    if isinstance(data, dict) and "error" in data:
        error_msg = data.get("details", "Unknown error")
        status_code = data.get("status_code", "N/A")
        logging.error(f"[ERROR] Page creation failed for '{page_name}': {error_msg} (Status: {status_code})")
        logging.error(f"[ERROR] Skipping page '{page_name}' - cannot proceed without PageId")
        return data  # Return early, don't proceed with mapping/publishing

    # Access the 'pageId' key and print its value
    page_id = data.get("PageId")

    if page_id is not None:
        logging.info(f"[SUCCESS] Page '{page_name}' created successfully with Page ID: {page_id}")
        print(f"The Page ID is: {page_id}")
    else:
        logging.error(f"[ERROR] 'PageId' key not found in the returned data for page '{page_name}'")
        logging.error(f"[ERROR] Response data: {data}")
        print("Error: 'pageId' key not found in the returned data.")
        return data  # Return early, don't proceed with mapping/publishing

    # Add delay before mapping to avoid API blocking
    logging.info(f"[TIMING] Starting updatePageMapping for page '{page_name}' (ID: {page_id})")
    start_time = time.time()
    mapping_payload = None
    try:
        _, mapping_payload = updatePageMapping(base_url, headers,page_id,site_id,header_footer_details, page_component_ids=page_component_ids, page_component_names=page_component_names, component_cache=component_cache)
        mapping_time = time.time() - start_time
        logging.info(f"[TIMING] updatePageMapping completed in {mapping_time:.2f} seconds")
        
        # Track timing
        if "updatePageMapping" not in TIMING_TRACKER:
            TIMING_TRACKER["updatePageMapping"] = []
        TIMING_TRACKER["updatePageMapping"].append(mapping_time)
    except Exception as e:
        logging.error(f"[ERROR] updatePageMapping failed for page '{page_name}' (ID: {page_id}): {e}")
        logging.exception("Full traceback:")
        # Even if mapping fails, we still queue the page for potential publish
    
    # Instead of publishing immediately, queue this page for publish at the end
    try:
        PAGES_TO_PUBLISH.append({
            "page_id": page_id,
            "page_name": page_name,
            "header_footer_details": header_footer_details,
            "mapping_payload": mapping_payload
        })
        logging.info(f"[PUBLISH QUEUE] Queued page '{page_name}' (ID: {page_id}) for publish at end of assembly.")
    except Exception as e:
        logging.error(f"[ERROR] Failed to queue page '{page_name}' (ID: {page_id}) for publish: {e}")
        logging.exception("Full traceback:")
    
    # No immediate publish here; publish will be handled in a separate final step
    return data



def updatePageMapping(base_url: str, headers: Dict[str, str], page_id: int, site_id: int, header_footer_details: Dict[str, Any], home_debug_log_callback=None, page_component_ids: Optional[set] = None, page_component_names: Optional[List[str]] = None, component_cache: Optional[List[Dict[str, Any]]] = None):
    """
    Creates and sends the page mapping payload using data from all
    ComponentRecordsTree.json files found in the migration output folders, 
    AND the explicit header/footer components.
    
    Args:
        home_debug_log_callback: Optional callback function to log payload to home_debug.log
        page_component_ids: Optional set of component IDs that belong to this page (for filtering)
        page_component_names: Optional list of component names from simplified.json (for filtering)
        component_cache: Optional component cache to look up component IDs by name
    """
    
    # Build a set of valid component IDs from component names if provided
    valid_component_ids_from_names: set = set()
    if page_component_names and component_cache:
        from processing_steps.process_assembly import check_component_availability
        for comp_name in page_component_names:
            api_result = check_component_availability(comp_name, component_cache)
            if api_result:
                _, _, componentId, _ = api_result
                component_id_str = str(componentId)
                valid_component_ids_from_names.add(component_id_str)
                logging.info(f"[MAPPING] Found component '{comp_name}' -> ID: {component_id_str}")
            else:
                logging.warning(f"[MAPPING] Component '{comp_name}' not found in component_cache")
        logging.info(f"[MAPPING] Built component ID set from {len(page_component_names)} component names: {len(valid_component_ids_from_names)} IDs found: {sorted(valid_component_ids_from_names)}")
    
    # Combine both sets if both are provided
    if page_component_ids:
        valid_component_ids_from_names.update(page_component_ids)
    
    # Use the combined set for filtering
    final_valid_component_ids = valid_component_ids_from_names if valid_component_ids_from_names else page_component_ids

    
    # --- PHASE 1: COLLECT BODY COMPONENT MAPPING DATA ---
    all_mappings: List[Dict[str, Any]] = []
    
    # Construct the base path to search: output/site_id/mi-block-ID-*
    search_path = os.path.join("output", str(site_id), "mi-block-ID-*", "ComponentRecordsTree.json")
    
    # print(f"[INFO] Searching for migration files in: {os.path.join('output', str(site_id), 'mi-block-ID-*')}")
    
    # Use glob to find all matching ComponentRecordsTree.json files
    for file_path in glob.glob(search_path):
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                records = data.get("componentRecordsTree", [])

            # Find the main component record where ParentId is 0
            main_component_record = next(
                (r for r in records if isinstance(r, dict) and r.get("ParentId") == 0),
                None
            )

            if main_component_record:
                # Extract component ID from folder name or record
                component_id_from_file = None
                folder_name = os.path.basename(os.path.dirname(file_path))
                if folder_name.startswith("mi-block-ID-"):
                    component_id_from_file = folder_name.replace("mi-block-ID-", "")
                
                # CRITICAL: Only include components that belong to THIS page
                if final_valid_component_ids and component_id_from_file:
                    if component_id_from_file not in final_valid_component_ids:
                        # This component doesn't belong to this page, skip it
                        logging.info(f"[MAPPING] Skipping component {component_id_from_file}: Not in valid_component_ids set. Valid IDs: {sorted(final_valid_component_ids)}")
                        continue
                    else:
                        logging.info(f"[MAPPING] Including component {component_id_from_file} in mapping (found in valid_component_ids)")
                
                # Extract the required fields from the main component record
                mapping_data = {
                    "pageId": page_id,
                    "vComponentAlias": main_component_record.get("component_alias"),
                    "vComponentId": main_component_record.get("vComponentId", ""), 
                    "contentEntityType": 2, # Fixed value (for body components)
                    "pageSectionGuid": main_component_record.get("sectionGuid")
                }
                
                # Simple validation before adding
                if mapping_data["vComponentAlias"] and mapping_data["pageSectionGuid"]:
                    all_mappings.append(mapping_data)
                    logging.info(f"[MAPPING] Added mapping for component {component_id_from_file}: alias={mapping_data['vComponentAlias'][:20]}..., sectionGuid={mapping_data['pageSectionGuid']}")
                else:
                    logging.warning(f"[MAPPING] Skipping component {component_id_from_file}: Missing 'component_alias' ({mapping_data['vComponentAlias']}) or 'sectionGuid' ({mapping_data['pageSectionGuid']})")

        except Exception as e:
            print(f"  [ERROR] Error processing file {file_path}: {e}")

    if not all_mappings:
        print("\n[INFO] No valid BODY component mappings were found. Proceeding with headers/footers only if available.")
    else:
        print(f"\n[INFO] Successfully collected {len(all_mappings)} body component mappings.")

    # --- PHASE 2: ADD HEADER/FOOTER MAPPING DATA ---
    
    # Helper to append header/footer data if it exists
    def add_hf_mapping(hf_key: str, content_type: int):
        hf_data = header_footer_details.get(hf_key)
        
        # Check if the component name was present in the page metadata AND
        # we successfully fetched a GUID for it (meaning the API call was made and succeeded)
        if hf_data and hf_data.get("name") and hf_data.get("guid"):
            mapping_data = {
                "pageId": page_id,
                "vComponentAlias": hf_data.get("alias"),
                "vComponentId": hf_data.get("vId", ""), 
                "contentEntityType": content_type,
                "pageSectionGuid": hf_data.get("guid")
            }
            all_mappings.append(mapping_data)
            print(f"  [SUCCESS] Added {hf_key} mapping for alias: {hf_data.get('alias')}")
        elif hf_data.get("name"):
            print(f"  [WARNING] Skipping {hf_key}: Component name '{hf_data.get('name')}' found, but GUID was missing/API failed during fetch.")


    # Content Entity Types: 1=Header/Prefix, 3=Footer/Suffix
    
    add_hf_mapping("Header1", 2) 
    
    add_hf_mapping("Header2", 2) 
    
    add_hf_mapping("Footer1", 2) 
    
    add_hf_mapping("Footer2", 2) 
    
    
    # --- PHASE 3: CONSTRUCT API PAYLOAD AND CALL API ---

    if not all_mappings:
        print("\n[INFO] No valid component mappings (body, header, or footer) were found. Aborting mapping update.")
        return 0

    new_api_payload = all_mappings
    
    # Log the complete mapping payload for debugging (console + debug log)
    logging.info(f"\n--- 📑 MAPPING API PAYLOAD (Page ID: {page_id}) ---")
    payload_str = json.dumps(new_api_payload, indent=2)
    logging.info(payload_str)
    logging.info("---------------------------------------------")
    # Also save to debug log file for easy access
    append_debug_log("mapping_payload", {"page_id": page_id, "payload": new_api_payload})
    
    # If homepage callback provided, also log to home_debug.log
    if home_debug_log_callback:
        home_debug_log_callback("mapping_payload", {"page_id": page_id, "payload": new_api_payload})

    try:
        # Add small delay before mapping API to avoid rate limiting
        time.sleep(1)
        # Call the API to update the page mapping
        logging.info(f"[TIMING] Calling psMappingApi with {len(new_api_payload)} mappings...")
        mapping_api_start = time.time()
        api_response_data = psMappingApi(base_url, headers, new_api_payload)
        mapping_api_time = time.time() - mapping_api_start
        logging.info(f"[TIMING] psMappingApi completed in {mapping_api_time:.2f} seconds")
        
        # Track timing
        if "psMappingApi" not in TIMING_TRACKER:
            TIMING_TRACKER["psMappingApi"] = []
        TIMING_TRACKER["psMappingApi"].append(mapping_api_time)
        
        # Check for 500 error response
        if isinstance(api_response_data, dict) and api_response_data.get("status_code") == 500:
            logging.error(f"[ERROR] 500 Internal Server Error during page mapping for Page ID {page_id}")
            logging.warning(f"[WARNING] Retrying mapping after 5 second delay...")
            time.sleep(5)
            # Retry once
            try:
                api_response_data = psMappingApi(base_url, headers, new_api_payload)
                if api_response_data == "Page Content Mappings updated successfully.":
                    logging.info(f"[SUCCESS] Page mapping retry successful for Page ID {page_id}")
                else:
                    logging.error(f"[ERROR] Page mapping retry failed for Page ID {page_id}")
            except Exception as retry_err:
                logging.error(f"[ERROR] Page mapping retry exception: {retry_err}")
        
        # Check for the specific success string (Your original success logic)
        if api_response_data == "Page Content Mappings updated successfully.":
            print(f"\n[SUCCESS] Page mapping updated successfully for Page ID {page_id}.")
            print(f"API Response: {api_response_data}")
            
        else:
            # Handle non-success responses that didn't raise an exception
            print(f"\n🛑 **FAILURE:** Failed to update page mapping for Page ID {page_id}.")
            print(f"API Response: {api_response_data}")

    except Exception as e:
        # This block now uses the correct variable name 'e' for the exception
        # and prints the error message directly.
        print(f"\n[ERROR] **CRITICAL API ERROR:** An exception occurred during the API call: {e}")

    return len(new_api_payload), new_api_payload  # Return both count and payload



def publishPage(base_url: str, headers: Dict[str, str], page_id: int, site_id: int, header_footer_details: Dict[str, Any], home_debug_log_callback=None, mapping_payload: Optional[List[Dict[str, Any]]] = None):
    """
    Constructs the necessary payload to publish all migrated components (MiBlocks, 
    Headers, Footers) and the page itself, then calls the publishing API.
    
    Args:
        home_debug_log_callback: Optional callback function to log payload to home_debug.log
        mapping_payload: Optional mapping payload from updatePageMapping to check contentEntityType
    """
    
    # --- PHASE 0: BUILD MAPPING LOOKUP FROM MAPPING PAYLOAD ---
    # Create a lookup: sectionGuid -> contentEntityType
    # This helps us determine if components should be MIBLOCK based on contentEntityType: 2
    # Also create a set of valid sectionGuids for this page (to filter components)
    section_guid_to_content_type: Dict[str, int] = {}
    valid_section_guids_for_page: set = set()  # Only components with these sectionGuids belong to this page
    if mapping_payload:
        for mapping_entry in mapping_payload:
            section_guid = mapping_entry.get("pageSectionGuid")
            content_entity_type = mapping_entry.get("contentEntityType")
            if section_guid and content_entity_type is not None:
                section_guid_to_content_type[section_guid] = content_entity_type
                valid_section_guids_for_page.add(section_guid)  # Track valid sectionGuids for this page
    
    # --- PHASE 0.5: BUILD MAPPING LOOKUP FROM COMPONENTRECORDSTREE FILES ---
    # Create a lookup: sectionGuid -> (componentId, should_be_miblock)
    # This helps us determine if components should be MIBLOCK even if they're in header_footer_details
    section_guid_to_component: Dict[str, Tuple[str, bool]] = {}
    search_path_mapping = os.path.join("output", str(site_id), "mi-block-ID-*", "ComponentRecordsTree.json")
    for file_path in glob.glob(search_path_mapping):
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                records = data.get("componentRecordsTree", [])
                main_component_record = next(
                    (r for r in records if isinstance(r, dict) and r.get("ParentId") == 0),
                    None
                )
                if main_component_record:
                    component_id = str(main_component_record.get("ComponentId"))
                    section_guid = main_component_record.get("sectionGuid")
                    if component_id and section_guid:
                        section_guid_to_component[section_guid] = (component_id, True)  # True = should be MIBLOCK
        except Exception:
            pass  # Ignore errors in lookup construction
    
    # --- PHASE 1: COLLECT MIBLOCK PUBLISHING DATA ---
    publish_payload: List[Dict[str, Any]] = []
    # Track which component IDs we've already added (to avoid duplicates)
    added_component_ids: set = set()
    # Track which section GUIDs we've already added as MIBLOCK
    added_section_guids: set = set()
    
    # Construct the base path to search: output/site_id/mi-block-ID-*
    search_path = os.path.join("output", str(site_id), "mi-block-ID-*", "ComponentRecordsTree.json")
    
    # Use glob to find all matching ComponentRecordsTree.json files
    for file_path in glob.glob(search_path):
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                records = data.get("componentRecordsTree", [])

            # Find the main component record where ParentId is 0
            main_component_record = next(
                (r for r in records if isinstance(r, dict) and r.get("ParentId") == 0),
                None
            )

            if main_component_record:
                # Extract the required fields (ComponentId and sectionGuid)
                component_id = str(main_component_record.get("ComponentId"))
                section_guid = main_component_record.get("sectionGuid")
                
                # CRITICAL: Only add components that are mapped to THIS page
                # Check if this sectionGuid is in the mapping payload for this page
                if component_id and section_guid:
                    # If mapping_payload exists, only include components that are mapped to this page
                    if mapping_payload and valid_section_guids_for_page:
                        if section_guid not in valid_section_guids_for_page:
                            # This component belongs to a different page, skip it
                            logging.warning(f"[PUBLISH] Skipping component {component_id} (sectionGuid: {section_guid}): Not found in mapping payload for page {page_id}. This may cause publish failure if component is in page HTML.")
                            continue
                    
                    miblock_entry = {
                        "id": component_id,
                        "type": "MIBLOCK",
                        "pageSectionGuid": section_guid
                    }
                    publish_payload.append(miblock_entry)
                    added_component_ids.add(component_id)  # Track that we added this component
                    added_section_guids.add(section_guid)  # Track section GUID as MIBLOCK
                    # print(f"  [SUCCESS] Added MiBlock {component_id} for publishing.")
                else:
                    print(f"  [WARNING] Skipping file {os.path.basename(os.path.dirname(file_path))}: Missing 'component_id' or 'sectionGuid'.")

        except Exception as e:
            print(f"  [ERROR] Error processing file {file_path}: {e}")
    
    # --- PHASE 1.5: ADD MISSING MIBLOCKS (components with folders but no ComponentRecordsTree.json) ---
    # Some components might have output folders but missing ComponentRecordsTree.json
    # Check all mi-block-ID-* folders and add any missing ones as MIBLOCK
    # NOTE: This phase is now mostly redundant since we filter by mapping payload in Phase 1
    # But keeping it for edge cases where ComponentRecordsTree.json is missing
    output_base = os.path.join("output", str(site_id))
    if os.path.exists(output_base):
        for folder_name in os.listdir(output_base):
            if folder_name.startswith("mi-block-ID-"):
                try:
                    # Extract component ID from folder name (e.g., "mi-block-ID-542061" -> "542061")
                    component_id_from_folder = folder_name.replace("mi-block-ID-", "")
                    # Check if we already added this component
                    if component_id_from_folder not in added_component_ids:
                        # Check if ComponentRecordsTree.json exists
                        tree_file = os.path.join(output_base, folder_name, "ComponentRecordsTree.json")
                        if not os.path.exists(tree_file):
                            # Component folder exists but no ComponentRecordsTree.json
                            # Try to find sectionGuid from other files or use a default approach
                            # For now, we'll skip these and handle them in header/footer section
                            # if they have sectionGuid from header_footer_details
                            logging.warning(f"[WARNING] Component {component_id_from_folder} has folder but no ComponentRecordsTree.json")
                except Exception as e:
                    logging.warning(f"[WARNING] Error processing folder {folder_name}: {e}")

    # --- PHASE 2: ADD HEADER/FOOTER PUBLISHING DATA ---
    
    def add_hf_publish_entry(hf_key: str):
        """Adds a component to the publish payload if data is valid."""
        hf_data = header_footer_details.get(hf_key)
        
        # We need the Component ID (id) and the unique Page Section GUID (guid)
        component_id = hf_data.get("id") if hf_data else None
        section_guid = hf_data.get("guid") if hf_data else None
        component_name = hf_data.get("name") if hf_data else "N/A"

        # Check if we successfully retrieved both ID and GUID when processing the page metadata
        if component_id and section_guid:
            component_id_str = str(component_id)
            
            # IMPORTANT: Check if this component has a mi-block-ID-* folder in output
            # If it does, it's a body component and should be MIBLOCK, not COMPONENT
            component_folder = os.path.join("output", str(site_id), f"mi-block-ID-{component_id_str}")
            if os.path.exists(component_folder):
                # This component has an output folder, so it's a body component (MIBLOCK)
                # Check if we already added it
                if component_id_str in added_component_ids or section_guid in added_section_guids:
                    print(f"  [INFO] Skipping {hf_key} Component ID {component_id_str}: Already added as MIBLOCK (has output folder).")
                    return
                else:
                    # Component folder exists but wasn't added as MIBLOCK (missing ComponentRecordsTree.json)
                    # Add it as MIBLOCK instead of COMPONENT
                    miblock_entry = {
                        "id": component_id_str,
                        "type": "MIBLOCK",
                        "pageSectionGuid": section_guid
                    }
                    publish_payload.append(miblock_entry)
                    added_component_ids.add(component_id_str)
                    added_section_guids.add(section_guid)
                    print(f"  [SUCCESS] Added Component ID {component_id_str} as MIBLOCK (has output folder but missing ComponentRecordsTree.json).")
                    return
            
            # IMPORTANT: Check if this sectionGuid should be MIBLOCK based on mapping payload (contentEntityType: 2)
            # This is the PRIMARY check - if contentEntityType is 2, it's a body component and should be MIBLOCK
            if section_guid in section_guid_to_content_type:
                content_entity_type = section_guid_to_content_type[section_guid]
                if content_entity_type == 2:  # Body component
                    # Check if we already added it
                    if component_id_str in added_component_ids or section_guid in added_section_guids:
                        print(f"  [INFO] Skipping {hf_key} Component ID {component_id_str}: Already added as MIBLOCK (contentEntityType: 2).")
                        return
                    else:
                        # This component has contentEntityType: 2, so it's a body component (MIBLOCK)
                        miblock_entry = {
                            "id": component_id_str,
                            "type": "MIBLOCK",
                            "pageSectionGuid": section_guid
                        }
                        publish_payload.append(miblock_entry)
                        added_component_ids.add(component_id_str)
                        added_section_guids.add(section_guid)
                        print(f"  [SUCCESS] Added {hf_key} Component ID {component_id_str} as MIBLOCK (contentEntityType: 2 in mapping payload).")
                        return
            
            # IMPORTANT: Check if this sectionGuid should be MIBLOCK (from ComponentRecordsTree.json)
            # If the sectionGuid is in our lookup, it means this is a body component, not a header/footer
            if section_guid in section_guid_to_component:
                mapped_component_id, should_be_miblock = section_guid_to_component[section_guid]
                # If it should be MIBLOCK, check if we already added it
                if should_be_miblock:
                    if mapped_component_id in added_component_ids or section_guid in added_section_guids:
                        print(f"  [INFO] Skipping {hf_key} Component ID {component_id_str}: Already added as MIBLOCK (sectionGuid: {section_guid}).")
                        return
                    else:
                        # This component should be MIBLOCK but wasn't found in ComponentRecordsTree.json
                        # Add it as MIBLOCK instead of COMPONENT
                        miblock_entry = {
                            "id": mapped_component_id if mapped_component_id == component_id_str else component_id_str,
                            "type": "MIBLOCK",
                            "pageSectionGuid": section_guid
                        }
                        publish_payload.append(miblock_entry)
                        added_component_ids.add(mapped_component_id if mapped_component_id == component_id_str else component_id_str)
                        added_section_guids.add(section_guid)
                        print(f"  [SUCCESS] Added {hf_key} Component ID {component_id_str} as MIBLOCK (was in mapping as body component).")
                        return
            
            # IMPORTANT: If this component was already added as MIBLOCK, skip it
            # (to avoid duplicates and ensure body components are MIBLOCK, not COMPONENT)
            if component_id_str in added_component_ids or section_guid in added_section_guids:
                print(f"  [INFO] Skipping {hf_key} Component ID {component_id_str}: Already added as MIBLOCK.")
                return
            
            # Only add as COMPONENT if it's truly a header/footer (no output folder, not in mapping as body component)
            # Headers/Footers are treated as standard components
            component_entry = {
                "id": component_id_str,
                "type": "COMPONENT", # Headers/Footers are treated as standard components
                "pageSectionGuid": section_guid
            }
            publish_payload.append(component_entry)
            added_component_ids.add(component_id_str)  # Track that we added this component
            print(f"  [SUCCESS] Added {hf_key} Component ID {component_id_str} for publishing.")
        elif component_name and component_name != "N/A":
             # This means the component name was in the metadata but fetching its ID/GUID failed earlier
             print(f"  [WARNING] Skipping {hf_key} ('{component_name}'): Component ID or GUID was missing for publishing.")


    print("\n--- Collecting Header/Footer Publish Data ---")
    add_hf_publish_entry("Header1")
    add_hf_publish_entry("Header2")
    add_hf_publish_entry("Footer1")
    add_hf_publish_entry("Footer2")


    # --- PHASE 3: ADD PAGE PUBLISHING DATA ---
    # Add the mandatory entry for the page itself
    page_entry = {
        "id": str(page_id),
        "type": "PAGE"
    }
    publish_payload.append(page_entry)
    print(f"\n  [SUCCESS] Added Page ID {page_id} for publishing.")
    
    if not publish_payload:
        print("\n[INFO] No content was collected for publishing.")
        return 0
        
    print(f"\n[INFO] Collected total of {len(publish_payload)} items for publishing.")

    # --- PHASE 4: CONSTRUCT FINAL DICTIONARY PAYLOAD AND EXECUTE API CALL ---
    
    # Construct the final dictionary payload as per the API's requirement
    final_api_payload = {
        "publishData": publish_payload,
        "syncPageForTranslationRequest": None
    }
    
    # Log the complete publish payload for debugging (console + debug log)
    logging.info(f"\n--- 📑 PUBLISH API PAYLOAD (Page ID: {page_id}) ---")
    payload_str = json.dumps(final_api_payload, indent=2)
    logging.info(payload_str)
    logging.info("---------------------------------------------")
    # Also save to debug log file for easy access
    append_debug_log("publish_payload", {"page_id": page_id, "payload": final_api_payload})
    
    # If homepage callback provided, also log to home_debug.log
    if home_debug_log_callback:
        home_debug_log_callback("publish_payload", {"page_id": page_id, "payload": final_api_payload})
    
    # Pass the final DICTIONARY payload to your publishing API function
    # Add delay before API call to avoid blocking (publish API can get rate-limited)
    logging.info(f"[TIMING] Waiting 2 seconds before calling psPublishApi to avoid rate limiting...")
    time.sleep(2)
    
    try:
        logging.info(f"[TIMING] Calling psPublishApi with {len(publish_payload)} items...")
        api_start_time = time.time()
        api_result = psPublishApi(base_url, headers, site_id, final_api_payload)
        api_time = time.time() - api_start_time
        logging.info(f"[TIMING] psPublishApi completed in {api_time:.2f} seconds")
        
        # Track timing
        if "psPublishApi" not in TIMING_TRACKER:
            TIMING_TRACKER["psPublishApi"] = []
        TIMING_TRACKER["psPublishApi"].append(api_time)
        
        # Check for 500 error and retry
        if isinstance(api_result, dict) and api_result.get("status_code") == 500:
            logging.error(f"[ERROR] 500 Internal Server Error during publish for Page ID {page_id}")
            logging.warning(f"[WARNING] Retrying publish after 5 second delay...")
            time.sleep(5)
            # Retry once
            try:
                api_result = psPublishApi(base_url, headers, site_id, final_api_payload)
                if isinstance(api_result, dict) and api_result.get("status") == "error":
                    logging.error(f"[ERROR] Publish retry failed for Page ID {page_id}")
                else:
                    logging.info(f"[SUCCESS] Publish retry successful for Page ID {page_id}")
            except Exception as retry_err:
                logging.error(f"[ERROR] Publish retry exception: {retry_err}")
                
    except Exception as e:
        logging.error(f"\n[ERROR] **CRITICAL API ERROR:** An exception occurred during the API call: {e}")
        logging.exception("Full traceback:")

    return len(publish_payload)


def publish_queued_pages(base_url: str, headers: Dict[str, str], site_id: int) -> int:
    """
    Publishes all pages that were queued during assembly.
    This function is called once at the end of the assembly step to avoid
    calling publish APIs in the middle of the main page loop.
    """
    if not PAGES_TO_PUBLISH:
        logging.info("[PUBLISH] No pages queued for publish. Skipping final publish step.")
        return 0
    
    logging.info("\n========================================================")
    logging.info("STEP 6: PUBLISHING QUEUED PAGES")
    logging.info("========================================================")
    
    total_pages = len(PAGES_TO_PUBLISH)
    success_count = 0
    
    for idx, entry in enumerate(PAGES_TO_PUBLISH, 1):
        page_id = entry.get("page_id")
        page_name = entry.get("page_name", f"Page-{page_id}")
        header_footer_details = entry.get("header_footer_details", {})
        mapping_payload = entry.get("mapping_payload")
        
        if not page_id:
            logging.warning(f"[PUBLISH] Skipping queued entry {idx}/{total_pages}: missing page_id.")
            continue
        
        # Add delay before publish to avoid API blocking (publish API can get blocked)
        logging.info(f"[TIMING] Waiting 3 seconds before publish of queued page '{page_name}' (ID: {page_id}) to avoid API blocking...")
        time.sleep(3)
        
        logging.info(f"[TIMING] Starting publishPage for queued page '{page_name}' (ID: {page_id}) [{idx}/{total_pages}]")
        start_time = time.time()
        try:
            publishPage(base_url, headers, page_id, site_id, header_footer_details, mapping_payload=mapping_payload)
            publish_time = time.time() - start_time
            logging.info(f"[TIMING] publishPage for '{page_name}' completed in {publish_time:.2f} seconds")
            
            # Track timing
            if "publishPage" not in TIMING_TRACKER:
                TIMING_TRACKER["publishPage"] = []
            TIMING_TRACKER["publishPage"].append(publish_time)
            
            success_count += 1
        except Exception as e:
            logging.error(f"[ERROR] publishPage failed for queued page '{page_name}' (ID: {page_id}): {e}")
            logging.exception("Full traceback:")
    
    logging.info(f"[PUBLISH] Queued publish complete: {success_count}/{total_pages} pages processed.")
    return success_count

def CreatePage(base_url, headers, payload,template_id):
    """
    Sends a POST request to create (save) a page using the MiBlock API.
    Endpoint: /api/PageApi/SavePage?templateId={id}&directPublish={bool}

    Args:
        base_url (str): The root URL for the API (e.g., "https://example.com").
        headers (dict): HTTP headers, typically including Authorization and Content-Type.
        payload (dict): The data payload for the page record to be created/saved.
        template_id (int): The ID of the template to use for the new page.
        direct_publish (bool): Whether to publish the page immediately after saving.

    Returns:
        dict: The JSON response body from the API call, or an error dictionary.
    """
    # Convert bool to lowercase string for URL parameter, as is common in Web APIs
    direct_publish = True
    direct_publish_str = str(direct_publish).lower()
    
    # 1. Construct the final API endpoint URL with query parameters
    api_url = f"{base_url}/api/PageApi/SavePage?templateId={template_id}&directPublish={direct_publish_str}"

    print(f"\n[API] Attempting POST to: {api_url}")
    
    try:
        # 2. Send the POST request with the JSON payload
        response = requests.post(
            api_url,
            headers=headers,
            json=payload,  # 'json=payload' automatically sets Content-Type to application/json
            timeout=10     # Set a timeout for the request
        )
        
        # 3. Raise an exception for bad status codes (4xx or 5xx)
        response.raise_for_status()

        # 4. Return the successful JSON response content
        return response.json()

    except requests.exceptions.HTTPError as http_err:
        # Check if response object exists and has status code
        status_code = response.status_code if 'response' in locals() else 'N/A'
        print(f"[ERROR] HTTP error occurred: {http_err} (Status Code: {status_code})")
        return {"error": "HTTP Error", "details": str(http_err), "status_code": status_code}
    except requests.exceptions.ConnectionError as conn_err:
        print(f"[ERROR] Connection error occurred: {conn_err}")
        return {"error": "Connection Error", "details": str(conn_err)}
    except requests.exceptions.Timeout as timeout_err:
        print(f"[ERROR] Timeout error occurred: {timeout_err}")
        return {"error": "Timeout Error", "details": str(timeout_err)}
    except requests.exceptions.RequestException as req_err:
        print(f"[ERROR] An unexpected request error occurred: {req_err}")
        return {"error": "Request Error", "details": str(req_err)}
    except json.JSONDecodeError:
        print(f"[ERROR] Failed to decode JSON response. Response text: {response.text if 'response' in locals() else 'No response object.'}")
        return {"error": "JSON Decode Error", "details": "Response was not valid JSON"}




def load_records(file_path):
    """Loads records from the JSON file. Returns (records_list, full_data, is_dict_wrapper)"""
    if not os.path.exists(file_path):
        return [], {}, False
    
    with open(file_path, 'r') as f:
        data = json.load(f)
        if isinstance(data, dict):
            # Check for both "records" and "componentRecordsTree" keys
            if "records" in data:
                return data["records"], data, True  # Dict wrapper, flag is True
            elif "componentRecordsTree" in data:
                return data["componentRecordsTree"], data, True  # Dict wrapper, flag is True  
            else:
                return [], data, True
        elif isinstance(data, list):
             return data, data, False  # Plain list, flag is False
        else:
             return [], data, False

def migrate_next_level_components(save_folder, pageSectionGuid, base_url, headers, level):
    """
    Generalized function to migrate components at any level (N > 0).
    It processes records that have a 'parent_new_record_id' and are not 'isMigrated'.
    Tags the next level of children (N+1) with the new parent ID only.
    (Section GUID tagging logic has been removed.)
    """
    records_file_path = os.path.join(save_folder, "ComponentRecordsTree.json")
    level_name = f"Level {level}"
    print(f"\n[INFO] Starting {level_name} Component migration process...")
    
    try:
        records, records_data, original_wrapper_is_dict = load_records(records_file_path)
    except Exception as e:
        print(f"    [ERROR] File processing failed: {e}. Skipping.")
        return 0

    migrated_count = 0
    
    # PHASE 1: IDENTIFY RECORDS FOR MIGRATION
    records_to_migrate = [
        r for r in records 
        if isinstance(r, dict) and 
           r.get("parent_new_record_id") is not None and 
           not r.get("isMigrated")
    ]
    
    # PHASE 1.5: Record limit check removed - CMS limits have been increased
    # All components can now migrate their records without limit restrictions
    
    if not records_to_migrate:
        print(f"    [INFO] No {level_name} components found ready for migration.")
        return 0
    
    print(f"    [INFO] Found {len(records_to_migrate)} {level_name} component(s) to process.")
    
    # PHASE 2: COLLECT ALL RECORDS FOR BULK PROCESSING
    records_payload_list = []
    record_index_map = {}  # Map record index to record object for later processing
    
    for index, record in enumerate(records_to_migrate): 
        
        old_component_id = record.get("ComponentId") 
        current_record_old_id = record.get("Id") # Unique old record ID
        new_parent_id = record.get("parent_new_record_id") 
            
        # print(f"    [START] Migrating {level_name} Record ID: {current_record_old_id} (Parent New ID: {new_parent_id})")
        
        # --- API Payload Construction ---
        migrated_record_data = record.get("RecordJsonString")
        try:
            recordDataJson_str = migrated_record_data if isinstance(migrated_record_data, str) else json.dumps(migrated_record_data)
        except TypeError:
            print(f"    [ERROR] RecordJsonString for ID {current_record_old_id} is invalid for JSON serialization. Skipping record.")
            continue

        tags_value = record.get("tags", [])
        if not isinstance(tags_value, list): tags_value = []

        single_record = {
            "componentId": old_component_id, 
            "recordId": 0, 
            "parentRecordId": new_parent_id, 
            "recordDataJson": recordDataJson_str, 
            "status": record.get("Status", True), 
            "tags": tags_value,
            "displayOrder": record.get("DisplayOrder", 0), 
            "updatedBy": record.get("UpdatedBy", 0),
            "pageSectionGuid": pageSectionGuid  # Unique GUID per component instance (same as main component for this component)
        }
        
        # Store record and its metadata for bulk processing
        records_payload_list.append(single_record)
        record_index_map[index] = {
            "record": record,
            "old_id": current_record_old_id,
            "index": index
        }
    
    # PHASE 3: BULK PROCESS ALL RECORDS AT THIS LEVEL
    if records_payload_list:
        logging.info(f"[BULK] Processing {len(records_payload_list)} {level_name} records in bulk...")
        resp_success, resp_data = addUpdateRecordsToCMS_bulk(base_url, headers, records_payload_list)
        
        if resp_success and isinstance(resp_data, dict):
            # PHASE 4: UPDATE RECORDS WITH NEW IDs AND TAG CHILDREN
            for index, record_info in record_index_map.items():
                record = record_info["record"]
                current_record_old_id = record_info["old_id"]
                record_index = record_info["index"]
                
                # Get the new record ID from response (using index as key)
                new_record_id = resp_data.get(record_index) or resp_data.get(str(record_index))
        
                if new_record_id:
                    migrated_count += 1
                    
                    # A. Update the current record with its own new ID and mark as migrated
                    record["isMigrated"] = True
                    record["new_record_id"] = new_record_id
                    
                    # B. Tag next-level children (N+1)
                    updated_children_count = 0
                    for child in records:
                        # Use the child's 'ParentId' (which links to the current record's 'Id')
                        if isinstance(child, dict) and child.get("ParentId") == current_record_old_id:
                            child["parent_new_record_id"] = new_record_id
                            updated_children_count += 1
                    
                    if updated_children_count > 0:
                        print(f"    [TAGGED] Linked {updated_children_count} Level {level+1} record(s) to new parent ID {new_record_id}.")
                else:
                    print(f"    [WARNING] Failed to get new record ID for {level_name} record ID {current_record_old_id}.")
        else:
            logging.error(f"[BULK] Failed to process {level_name} records in bulk: {resp_data}")
            # Fallback to individual processing if bulk fails
            logging.warning(f"[FALLBACK] Attempting individual record processing for {level_name}...")
            for index, record_info in record_index_map.items():
                record = record_info["record"]
                current_record_old_id = record_info["old_id"]
                single_record = records_payload_list[index]
                api_payload = {"main_record_set": [single_record]}
                resp_success, resp_data = addUpdateRecordsToCMS(base_url, headers, api_payload)
                
                new_record_id = None
                if resp_success and isinstance(resp_data, dict) and (0 in resp_data or "0" in resp_data):
                    new_record_id = resp_data.get(0) or resp_data.get("0")
                
                if new_record_id:
                    migrated_count += 1
                    record["isMigrated"] = True
                    record["new_record_id"] = new_record_id
                    
                    # Tag children
                    for child in records:
                        if isinstance(child, dict) and child.get("ParentId") == current_record_old_id:
                            child["parent_new_record_id"] = new_record_id

    # PHASE 5: WRITE UPDATES BACK TO FILE (Persistence)
    if migrated_count > 0:
        try:
            with open(records_file_path, 'w', encoding='utf-8') as wf:
                if original_wrapper_is_dict:
                    # Write back into the original dictionary structure
                    records_data["componentRecordsTree"] = records
                    json.dump(records_data, wf, indent=4)
                else:
                    # Write back as a list
                    json.dump(records, wf, indent=4)
            print(f"    [SUCCESS] Persisted {migrated_count} migrated {level_name} record(s) to {records_file_path}.")
        except Exception as e:
            print(f"    [ERROR] Failed to persist changes to file: {e}")
    
    return migrated_count


def mainComp(save_folder, component_id, pageSectionGuid, base_url, headers,component_alias,vComponentId):
    """
    Finds and migrates the 'MainComponent' record, updates its child records 
    in memory, and persists all changes back to the JSON file.
    """
    records_file_path = os.path.join(save_folder, "ComponentRecordsTree.json")
    # print(f"  [INFO] Searching for MainComponent records in {records_file_path}...")
    
    main_component_old_id = None
    main_component_new_id = None
    records = []
    
    try:
        # --- File Reading ---
        with open(records_file_path, 'r', encoding='utf-8') as rf:
            records_data = json.load(rf)
        
        # Determine if the root is a list or a dictionary wrapper
        original_wrapper_is_dict = False
        if isinstance(records_data, dict) and "componentRecordsTree" in records_data:
            records = records_data["componentRecordsTree"]
            original_wrapper_is_dict = True
        elif isinstance(records_data, list):
            records = records_data
        
        if not isinstance(records, list):
            print("  [ERROR] Extracted component records content is not a list. Skipping.")
            return

        # --- PHASE 1: FIND AND MIGRATE MAIN COMPONENT ---
        found_main_components = False
        
        for record in records:
            if isinstance(record, dict) and record.get("recordType") == "MainComponent":
                
                main_component_old_id = record.get("ComponentId") 
                # print(f"  [FOUND] MainComponent ID: {main_component_old_id}")
                found_main_components = True
                
                # --- API Payload Construction ---
                migrated_record_data = record.get("RecordJsonString")
                try:
                    recordDataJson_str = migrated_record_data if isinstance(migrated_record_data, str) else json.dumps(migrated_record_data)
                except TypeError:
                    print(f"  [ERROR] RecordJsonString for ID {main_component_old_id} is invalid for JSON serialization.")
                    continue

                tags_value = record.get("tags", [])
                if not isinstance(tags_value, list): tags_value = []

                single_record = {
                    "componentId": component_id, "recordId": 0, "parentRecordId": 0, 
                    "recordDataJson": recordDataJson_str, 
                    "status": record.get("Status", True), "tags": tags_value,
                    "displayOrder": record.get("DisplayOrder", 0), 
                    "updatedBy": record.get("UpdatedBy", 0),
                    "pageSectionGuid": pageSectionGuid  # Unique GUID per component instance
                }
                logging.debug(f"[GUID] MainComponent record using pageSectionGuid: {pageSectionGuid} for component {component_id} (alias: {component_alias})")

                api_payload = {"main_record_set": [single_record]}

                # Call the API to create the record (using bulk API for potential future batching)
                # NOTE: The implementation above will return True, {0: 2981622}
                resp_success, resp_data = addUpdateRecordsToCMS(base_url, headers, api_payload)
                
                # --- Extract New Record ID ---
                main_component_new_id = None
                if resp_success and isinstance(resp_data, dict):
                    if 0 in resp_data: main_component_new_id = resp_data[0] # Checks for integer key 0
                    elif "0" in resp_data: main_component_new_id = resp_data["0"] # Checks for string key "0"

                if main_component_new_id:
                    print(f"  [SUCCESS] CMS Record Created. Old ComponentId: {main_component_old_id} -> New RecordId: {main_component_new_id}")
                    
                    # *** CRITICAL FIX: Update properties in the in-memory record ***
                    record["isMigrated"] = True
                    record["sectionGuid"] = pageSectionGuid
                    record["component_alias"] = component_alias
                    record["vComponentId"] = vComponentId
                    
                    break 
                else:
                    print(f"  [WARNING] Failed to update CMS record for MainComponent ID {main_component_old_id}. Response: {resp_data}")
                    
        if not found_main_components:
            print("  [INFO] No MainComponent records found in the component tree file.")
            return

        # --- PHASE 2: UPDATE CHILD RECORDS WITH NEW PARENT ID (In Memory) ---
        if main_component_new_id:
            updated_children_count = 0
            
            for record in records:
                # Check if the record is a child of the migrated MainComponent
                if isinstance(record, dict) and record.get("ParentComponentId") == main_component_old_id:
                    # *** CRITICAL FIX: Link the child record to the new parent ID ***
                    record["parent_new_record_id"] = main_component_new_id
                    updated_children_count += 1

            if updated_children_count > 0:
                print(f"  [INFO] Successfully linked {updated_children_count} child records to new parent ID {main_component_new_id} in memory.")
            else:
                print("  [INFO] No child records found for the migrated MainComponent.")
        else:
            print("  [WARNING] MainComponent migration failed, skipping child record updates.")

        # --- PHASE 3: WRITE UPDATES BACK TO FILE (Persistence Fix) ---
        with open(records_file_path, 'w', encoding='utf-8') as wf:
            if original_wrapper_is_dict:
                 # Write back into the original dictionary structure
                 records_data["componentRecordsTree"] = records
                 json.dump(records_data, wf, indent=4)
            else:
                 # Write back as a list
                 json.dump(records, wf, indent=4)
        print(f"  [SUCCESS] All migration metadata and child links persisted to {records_file_path}.")

    except FileNotFoundError:
        print(f"  [WARNING] ComponentRecordsTree.json not found at {records_file_path}. Skipping processing.")
    except json.JSONDecodeError:
        print(f"  [ERROR] Failed to decode JSON from {records_file_path}. Skipping processing.")
    except Exception as e:
        print(f"  [FATAL ERROR] Unexpected error while processing component records: {e}")



def createPayloadJson(site_id, component_id):
    """
    Reads the MiBlockComponentConfig.json for a given component_id,
    determines the component hierarchy based on ParentId, and creates 
    a new JSON file with component ID, type (level), and name in the
    'output/{site_id}/mi-block-ID-{component_id}' folder.

    Args:
        site_id (int/str): The ID of the site, used as part of the folder path.
        component_id (int/str): The ID of the component (used to construct the folder path).
        
    Returns:
        bool: True if the operation was successful, False otherwise.
    """
    component_id_str = str(component_id)
    site_id_str = str(site_id)
    
    # Construct the folder path: output/site_id/mi-block-ID-component_id
    folder_path = os.path.join("output", site_id_str, f"mi-block-ID-{component_id_str}")
    
    input_file_path = os.path.join(folder_path, "MiBlockComponentConfig.json")
    output_file_name = "ComponentHierarchy.json"
    output_file_path = os.path.join(folder_path, output_file_name)

    try:
        # 1. Read and parse MiBlockComponentConfig.json
        # print(f"Reading configuration from: {input_file_path}")
        with open(input_file_path, 'r') as f:
            config_data = json.load(f)

        components = config_data.get("component", [])
        
        if not components:
            print("Warning: 'component' list is empty in the config file. Writing empty hierarchy file.")
            
            # Ensure the output directory exists even if we write an empty list
            os.makedirs(folder_path, exist_ok=True)
            with open(output_file_path, 'w') as f:
                json.dump([], f, indent=4)
            return True

        # 2. Map Component IDs to their properties and initialize levels
        component_map = {}
        for comp in components:
            comp_id = comp.get("ComponentId")
            parent_id = comp.get("ParentId")
            
            if comp_id is not None:
                component_map[comp_id] = {
                    "ComponentName": comp.get("ComponentName"),
                    "ParentId": parent_id,
                    "Level": -1 # Unknown initially
                }

        # 3. Determine the hierarchy (level)
        
        # First pass: Set Level 0 (Root) components (ParentId is None/null)
        for details in component_map.values():
            if details["ParentId"] is None:
                details["Level"] = 0
        
        # Iterative pass: Resolve child levels (Level 1, 2, ...)
        max_depth = len(components)
        level = 0
        
        while level < max_depth:
            changes_made = False
            next_level = level + 1
            
            for details in component_map.values():
                if details["Level"] == -1: # Only look at unclassified components
                    parent_id = details["ParentId"]
                    
                    # Check if the parent exists AND has the current level
                    if parent_id in component_map and component_map[parent_id]["Level"] == level:
                        details["Level"] = next_level
                        changes_made = True
            
            if not changes_made:
                break # Hierarchy is fully resolved
            
            level += 1
            
        # 4. Construct the final output payload
        output_payload = []
        for comp_id, details in component_map.items():
            comp_level = details["Level"]
            
            # Define the component type based on its calculated level
            if comp_level == 0:
                component_type = "MainComponent"
            elif comp_level > 0:
                component_type = f"Level{comp_level}Child"
            else:
                component_type = "Unlinked/Error"

            output_payload.append({
                "componentId": comp_id,
                "type": component_type,
                "componentName": details["ComponentName"]
            })

        # 5. Write the output payload to a new JSON file
        # print(f"Writing component hierarchy to: {output_file_path}")
        
        # Ensure the output directory exists
        os.makedirs(folder_path, exist_ok=True)
        
        with open(output_file_path, 'w') as f:
            json.dump(output_payload, f, indent=4)
        
        # print("Successfully determined component hierarchy and saved.")
        return True

    except FileNotFoundError:
        print(f"Error: Input file not found at {input_file_path}. Ensure the site and component IDs are correct.")
        return False
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {input_file_path}. Check the file format.")
        return False
    except Exception as e:
        print(f"An unexpected error occurred during processing: {e}")
        return False
    


def _read_json_file(file_path: str) -> Optional[Dict[str, Any]]:
    """Helper function to safely read and parse a JSON file."""
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: Required file not found at {file_path}.")
        return None
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {file_path}. Check the file format.")
        return None
    except Exception as e:
        print(f"An unexpected error occurred while reading {file_path}: {e}")
        return None



def createRecordsPayload(site_id, component_id):
    """
    Finds the root record for the given component_id, recursively collects
    all descendant records, and adds the 'recordType' based on ComponentHierarchy.json.
    """
    component_id_int = int(component_id)
    site_id_str = str(site_id)
    
    # 1. Define Paths
    folder_path = os.path.join("output", site_id_str, f"mi-block-ID-{str(component_id)}")
    
    # Input files
    records_input_path = os.path.join(folder_path, "MiBlockComponentRecords.json")
    hierarchy_input_path = os.path.join(folder_path, "ComponentHierarchy.json") # New path
    
    # Output file
    output_file_name = "ComponentRecordsTree.json"
    output_file_path = os.path.join(folder_path, output_file_name)

    # 2. Load Data and Create Type Map
    records_data = _read_json_file(records_input_path)
    hierarchy_data = _read_json_file(hierarchy_input_path)

    if records_data is None or hierarchy_data is None:
        return False
        
    if not isinstance(hierarchy_data, list):
        print("Error: ComponentHierarchy.json is required and must contain a list of components.")
        return False

    # Create map: { componentId (int): type (str) }
    type_map = {int(item["componentId"]): item["type"] for item in hierarchy_data}

    all_records: List[Dict[str, Any]] = records_data.get("componentRecords", [])
    
    if not all_records:
        print("Warning: 'componentRecords' list is empty. Writing empty records tree file.")
        os.makedirs(folder_path, exist_ok=True)
        with open(output_file_path, 'w') as f:
            json.dump({"componentRecordsTree": []}, f, indent=4)
        return True

    # Helper to add recordType
    def enrich_record(record: Dict[str, Any], type_map: Dict[int, str]) -> Dict[str, Any]:
        comp_id = record.get("ComponentId")
        # Get type from map, default to "UnknownType" if not found
        record_type = type_map.get(comp_id, "UnknownType") 
        
        # Create a copy and add the new key
        enriched_record = record.copy() 
        enriched_record["recordType"] = record_type
        return enriched_record
    
    # 3. Find the single Root Record
    root_record = next(
        (
            record for record in all_records
            if record.get("ComponentId") == component_id_int and record.get("ParentId") == 0
        ),
        None
    )

    if root_record is None:
        print(f"Error: Could not find a root record (ComponentId={component_id_int}, ParentId=0).")
        return False

    # 4. Prepare data structure for quick lookup (Record ID -> List of Children)
    children_map: Dict[int, List[Dict[str, Any]]] = {}
    for record in all_records:
        parent_id = record.get("ParentId")
        if parent_id is not None and parent_id != 0:
            if parent_id not in children_map:
                children_map[parent_id] = []
            children_map[parent_id].append(record)

    # 5. Recursive function to collect the entire tree in sequence (Depth-First Search)
    # Start with the enriched root record
    records_tree: List[Dict[str, Any]] = [enrich_record(root_record, type_map)]
    
    def collect_descendants(parent_id: int):
        """Recursively finds and appends children in a depth-first manner."""
        children = children_map.get(parent_id, [])
        
        # Sort children by DisplayOrder or Id to maintain sequence
        children.sort(key=lambda x: x.get("DisplayOrder", x.get("Id")))
        
        for child in children:
            # Enrich the child record before adding it to the final tree
            records_tree.append(enrich_record(child, type_map)) 
            # Recurse for deeper levels
            collect_descendants(child["Id"])

    # Start the collection from the root record's Id
    collect_descendants(root_record["Id"])

    # 6. Write the output payload
    # print(f"Found {len(records_tree)} records in the hierarchy. Writing to: {output_file_path}")
    
    os.makedirs(folder_path, exist_ok=True)
    with open(output_file_path, 'w') as f:
        # Save the list of records in sequence under the key 'componentRecordsTree'
        json.dump({"componentRecordsTree": records_tree}, f, indent=4)
    
    print("Successfully collected and saved component records tree with recordType.")
    return True


























# ================= Core Processing Logic and Traversal =================

# def _process_page_components(page_data: Dict[str, Any], page_level: int, hierarchy: List[str], component_cache: List[Dict[str, Any]], api_base_url: str, site_id: int, api_headers: Dict[str, str], category_id: int):
    
#     page_name = page_data.get('page_name', 'UNKNOWN_PAGE')
#     components = page_data.get('components', [])
#     meta_info = page_data.get('meta_info', {}) 
    
#     # 🌟 STEP 1: Get Template Name and Fetch Template ID
#     page_template_name = meta_info.get("PageTemplateName")
#     DefaultTitle = meta_info.get("DefaultTitle")
#     DefaultDescription = meta_info.get("DefaultDescription")
#     page_template_id = None
    
#     if page_template_name:
#         try:
#             # 🌟 STEP 2: Call API to get the Template ID
#             template_info = GetTemplatePageByName(api_base_url, api_headers, page_template_name)
#             if template_info and isinstance(template_info, list) and 'PageId' in template_info[0]:
#                 page_template_id = template_info[0]['PageId'] 
            
#             logging.info(f"Retrieved Page Template ID {page_template_id} for template: {page_template_name}")
#         except Exception as e:
#             logging.error(f"Failed to retrieve page template ID for '{page_template_name}': {e}")
#             pass
    
#     if page_template_id is None:
#         logging.warning(f"Could not determine Page Template ID for page: {page_name}. Proceeding without it (or defaulting).")


#     # Initialize a list to hold the HTML sections for this page
#     page_sections_html = []

#     if not components:
#         status_entry = {
#             "page": page_name, "component": "N/A", "level": page_level,
#             "hierarchy": " > ".join(hierarchy + [page_name]), "available": False, 
#             "status": "SKIPPED: Page had no components defined.",
#             "cms_component_name": "N/A"
#         }
#         ASSEMBLY_STATUS_LOG.append(status_entry) 
#         logging.warning(f"Page **{page_name}** (Level {page_level}) has no components to process. Logged as skipped.")
#         return

#     # --- ACCUMULATION PHASE: Component Loop (Removed 'Weddings' Condition) ---
#     for component_name in components:
#         status_entry = {
#             "page": page_name, "component": component_name, "level": page_level,
#             "hierarchy": " > ".join(hierarchy + [page_name]), "available": False, 
#             "status": "SKIPPED: Component not available.",
#             "cms_component_name": "N/A"
#         }
        
#         api_result = check_component_availability(component_name, component_cache)
#         section_payload = None
        
#         if api_result:
#             vComponentId, alias, componentId, cms_component_name = api_result 
            
#             logging.info(f"[SUCCESS] Component '{component_name}' is available. Starting content retrieval for **{page_name}**.")
            
#             status_entry["available"] = True
#             status_entry["cms_component_name"] = cms_component_name
            
#             # CONDITION REMOVED: Now executes content retrieval for ALL pages
#             try:
#                 # Call function to get section payload (HTML snippet)
#                 section_payload = add_records_for_page(page_name, vComponentId, componentId, api_base_url, site_id, api_headers, alias)
#                 status_entry["status"] = "SUCCESS: Content retrieved and added to assembly queue."
#             except Exception as e:
#                 logging.error(f"Content retrieval failed for {page_name}/{component_name}: {e}")
#                 status_entry["status"] = f"FAILED: Content retrieval error: {type(e).__name__}"
#                 status_entry["available"] = False

#             # Append the payload (either retrieved content or an empty string)
#             if section_payload is not None:
#                 page_sections_html.append(section_payload)
            
#         else:
#             logging.warning(f"[ERROR] Component '{component_name}' **NOT AVAILABLE** for page **{page_name}**. Skipping.")
        
#         ASSEMBLY_STATUS_LOG.append(status_entry)

#     # --- FINALIZATION PHASE (Executed once per page - Removed 'Weddings' Condition) ---
    
#     # Check if any sections were successfully retrieved and contain data
#     if page_sections_html and any(page_sections_html): 
        
#         # Concatenate all component HTML sections in order
#         all_sections_concatenated = "".join(page_sections_html)
        
#         # Define HTML wrappers
#         htmlPrefix = '<div class="box2" id="data_page_content"><div id="pagestudio">'
#         htmlPostfix = "</div></div>"
        
#         # Add the prefix and postfix wrappers
#         final_html = htmlPrefix + all_sections_concatenated + htmlPostfix
        
#         # 📢 DEBUG PRINT STATEMENT REMAINS (use logging.info for production) 📢
#         logging.info("\n--- FINAL ASSEMBLED HTML PAYLOAD ---")
#         logging.info(final_html)
#         logging.info("--------------------------------------\n")
        
#         # CONDITION REMOVED: Now calls pageAction for ALL pages with content
#         logging.info(f"Final assembly complete for **{page_name}**. Calling pageAction for publishing.")
#         # 🌟 STEP 3: Pass the page_template_id to pageAction
#         pageAction(api_base_url, api_headers, final_html, page_name, page_template_id, DefaultTitle, DefaultDescription, site_id, category_id)
        
#     else:
#         # CONDITION REMOVED: Now logs uniformly
#         logging.error(f"Page **{page_name}** failed: No final HTML content was successfully retrieved to assemble the page. Skipping pageAction.")
#         return



# def _process_page_components(page_data: Dict[str, Any], page_level: int, hierarchy: List[str], component_cache: List[Dict[str, Any]], api_base_url: str, site_id: int, api_headers: Dict[str, str], category_id: int):
    
#     page_name = page_data.get('page_name', 'UNKNOWN_PAGE')
#     components = page_data.get('components', [])
#     meta_info = page_data.get('meta_info', {}) 
    
#     # 🌟 STEP 1: Get Template Name and Fetch Template ID
#     page_template_name = meta_info.get("PageTemplateName")
#     DefaultTitle = meta_info.get("DefaultTitle")
#     DefaultDescription = meta_info.get("DefaultDescription")
#     Header1 = meta_info.get("Header1")
#     Header2 = meta_info.get("Header2")
#     Footer1 = meta_info.get("Footer1")
#     Footer2 = meta_info.get("Footer2")
    
#     page_template_id = None
    
#     if page_template_name:
#         try:
#             # 🌟 STEP 2: Call API to get the Template ID
#             template_info = GetTemplatePageByName(api_base_url, api_headers, page_template_name)
#             if template_info and isinstance(template_info, list) and 'PageId' in template_info[0]:
#                 page_template_id = template_info[0]['PageId'] 
            
#             logging.info(f"Retrieved Page Template ID {page_template_id} for template: {page_template_name}")
#         except Exception as e:
#             logging.error(f"Failed to retrieve page template ID for '{page_template_name}': {e}")
#             pass
    
#     if page_template_id is None:
#         logging.warning(f"Could not determine Page Template ID for page: {page_name}. Proceeding without it (or defaulting).")


#     # Initialize a list to hold the HTML sections for this page
#     page_sections_html = []

#     if not components:
#         status_entry = {
#             "page": page_name, "component": "N/A", "level": page_level,
#             "hierarchy": " > ".join(hierarchy + [page_name]), "available": False, 
#             "status": "SKIPPED: Page had no components defined.",
#             "cms_component_name": "N/A"
#         }
#         ASSEMBLY_STATUS_LOG.append(status_entry) 
#         logging.warning(f"Page **{page_name}** (Level {page_level}) has no components to process. Logged as skipped.")
#         return

#     # --- ACCUMULATION PHASE: Component Loop (WEDDINGS CONDITION RESTORED) ---
#     for component_name in components:
#         status_entry = {
#             "page": page_name, "component": component_name, "level": page_level,
#             "hierarchy": " > ".join(hierarchy + [page_name]), "available": False, 
#             "status": "SKIPPED: Component not available.",
#             "cms_component_name": "N/A"
#         }
        
#         api_result = check_component_availability(component_name, component_cache)
#         section_payload = None
        
#         if api_result:
#             vComponentId, alias, componentId, cms_component_name = api_result 
            
#             logging.info(f"[SUCCESS] Component '{component_name}' is available. Starting content retrieval for **{page_name}**.")
            
#             status_entry["available"] = True
#             status_entry["cms_component_name"] = cms_component_name
            
#             # 🛑 RESTORED WEDDINGS CONDITION 🛑
#             if page_name == "Meetings and Events":
#                 try:
#                     print("inside meetni")
#                     # Call function to get section payload (HTML snippet) - ONLY FOR WEDDINGS
#                     section_payload = add_records_for_page(page_name, vComponentId, componentId, api_base_url, site_id, api_headers, alias)
#                     status_entry["status"] = "SUCCESS: Content retrieved and added to assembly queue."
#                 except Exception as e:
#                     logging.error(f"Content retrieval failed for {page_name}/{component_name}: {e}")
#                     status_entry["status"] = f"FAILED: Content retrieval error: {type(e).__name__}"
#                     status_entry["available"] = False
#             else:
#                 # Data retrieval/record adding is skipped for non-Weddings pages
#                 logging.info(f"Skipping record addition for non-Weddings page: {page_name}/{component_name}.")
#                 status_entry["status"] = "SUCCESS: Component available, data retrieval skipped (non-Weddings page)."
#                 section_payload = "" # Append empty string to page sections list
            
#             # Append the payload (either retrieved content or an empty string)
#             if section_payload is not None:
#                 page_sections_html.append(section_payload)
            
#         else:
#             logging.warning(f"[ERROR] Component '{component_name}' **NOT AVAILABLE** for page **{page_name}**. Skipping.")
        
#         ASSEMBLY_STATUS_LOG.append(status_entry)

#     # --- FINALIZATION PHASE (WEDDINGS CONDITION RESTORED) ---
    
#     # Check if any sections were successfully retrieved and contain data
#     if page_sections_html and any(page_sections_html): 
        
#         # Concatenate all component HTML sections in order
#         all_sections_concatenated = "".join(page_sections_html)
        
#         # Define HTML wrappers
#         htmlPrefix = '<div class="box2" id="data_page_content"><div id="pagestudio">'
#         htmlPostfix = "</div></div>"
        
#         Header1_vComponentId,Header1_component_alias, Header1_component_id,Header1_section_html = getHeaderFooter_html(api_base_url, api_headers,Header1)
#         Header2_vComponentId,Header2_component_alias, Header2_component_id,Header2_section_html = getHeaderFooter_html(api_base_url, api_headers,Header2)
#         Footer1_vComponentId,Footer1_component_alias, Footer1_component_id,Footer1_section_html = getHeaderFooter_html(api_base_url, api_headers,Footer1)
#         Footer2_vComponentId,Footer2_component_alias, Footer2_component_id,Footer2_section_html = getHeaderFooter_html(api_base_url, api_headers,Footer2)




#         # Add the prefix and postfix wrappers
#         final_html = htmlPrefix + Header1_section_html+ Header2_section_html+ all_sections_concatenated +Footer1_section_html+ Footer2_section_html+ htmlPostfix
        
#         logging.info("\n--- FINAL ASSEMBLED HTML PAYLOAD ---")
#         logging.info(final_html)
#         logging.info("--------------------------------------\n")
        
#         # 🛑 RESTORED WEDDINGS CONDITION for pageAction 🛑
#         if page_name == "Meetings and Events":
#             logging.info(f"Final assembly complete for **{page_name}**. Calling pageAction for publishing.")
#             # 🌟 STEP 3: Pass the page_template_id to pageAction
#             pageAction(api_base_url, api_headers, final_html, page_name, page_template_id, DefaultTitle, DefaultDescription, site_id, category_id,Header1,Header2,Footer1,Footer2)
#         else:
#             logging.info(f"Final assembly complete for **{page_name}** but skipping pageAction (non-Weddings page).")
            
#     else:
#         # Conditional logging for pages that fail to retrieve content
#         if page_name == "Meetings and Events":
#             logging.error(f"Page **{page_name}** failed: No final HTML content was successfully retrieved to assemble the page. Skipping pageAction.")
#         else:
#             logging.info(f"Page **{page_name}** (non-Weddings) completed component checks but assembled an empty page, as expected.")
#         return


# def getHeaderFooter_html(base_url, headers,headerFooterCompName):
#     vComponentId,component_alias, component_id = CustomGetComponentAliasByName(base_url, headers, headerFooterCompName)
#     pageSectionGuid = str(uuid.uuid4()) 
#     section_html  = generatecontentHtml(1, component_alias, pageSectionGuid)
#     return vComponentId,component_alias, component_id,section_html





# --- ASSUMED EXTERNAL DEPENDENCIES ---
# Ensure these functions/variables are imported/defined in your environment:
# from your_apis import GetTemplatePageByName, check_component_availability, pageAction, CustomGetComponentAliasByName
# from your_utils import generatecontentHtml 
# from your_globals import ASSEMBLY_STATUS_LOG 

# --- Helper Function for Headers/Footers ---
def getHeaderFooter_html(base_url: str, headers: Dict[str, str], headerFooterCompName: str) -> Tuple[Optional[str], Optional[str], Optional[int], str, Optional[str]]:
    """
    Fetches the necessary IDs and generates the HTML structure for a given 
    Header or Footer component name.
    
    Returns:
        vComponentId, component_alias, component_id, section_html, pageSectionGuid
    """
    try:
        # Assuming CustomGetComponentAliasByName returns vComponentId, alias, component_id
        vComponentId, component_alias, component_id = CustomGetComponentAliasByName(base_url, headers, headerFooterCompName)
        
        pageSectionGuid = str(uuid.uuid4()) 
        # Assuming generatecontentHtml generates the structural HTML snippet
        section_html  = generatecontentHtml(1, component_alias, pageSectionGuid)
        
        logging.info(f"Successfully fetched details for Header/Footer: {headerFooterCompName}")
        return vComponentId, component_alias, component_id, section_html, pageSectionGuid
        
    except Exception as e:
        logging.error(f"Failed to process Header/Footer component '{headerFooterCompName}': {e}")
        # 🛑 FIX: Ensure 5 values are returned on failure (the fifth is None for the GUID).
        return None, None, None, "", None 

# --- Corrected _process_page_components ---

# def _process_page_components(page_data: Dict[str, Any], page_level: int, hierarchy: List[str], component_cache: List[Dict[str, Any]], api_base_url: str, site_id: int, api_headers: Dict[str, str], category_id: int):
    
#     page_name = page_data.get('page_name', 'UNKNOWN_PAGE')
#     components = page_data.get('components', [])
#     meta_info = page_data.get('meta_info', {}) 
    
#     # 🌟 STEP 1: Extract Metadata
#     page_template_name = meta_info.get("PageTemplateName")
#     DefaultTitle = meta_info.get("DefaultTitle")
#     DefaultDescription = meta_info.get("DefaultDescription")
#     Header1 = meta_info.get("Header1")
#     Header2 = meta_info.get("Header2")
#     Footer1 = meta_info.get("Footer1")
#     Footer2 = meta_info.get("Footer2")
    
#     page_template_id = None
    
#     if page_template_name:
#         try:
#             # 🌟 STEP 2: Call API to get the Template ID
#             template_info = GetTemplatePageByName(api_base_url, api_headers, page_template_name)
#             if template_info and isinstance(template_info, list) and 'PageId' in template_info[0]:
#                 page_template_id = template_info[0]['PageId'] 
            
#             logging.info(f"Retrieved Page Template ID {page_template_id} for template: {page_template_name}")
#         except Exception as e:
#             logging.error(f"Failed to retrieve page template ID for '{page_template_name}': {e}")
#             pass
    
#     if page_template_id is None:
#         logging.warning(f"Could not determine Page Template ID for page: {page_name}. Proceeding without it (or defaulting).")


#     # Initialize a list to hold the HTML sections for this page
#     page_sections_html = []

#     if not components:
#         status_entry = {
#             "page": page_name, "component": "N/A", "level": page_level,
#             "hierarchy": " > ".join(hierarchy + [page_name]), "available": False, 
#             "status": "SKIPPED: Page had no components defined.",
#             "cms_component_name": "N/A"
#         }
#         ASSEMBLY_STATUS_LOG.append(status_entry) 
#         logging.warning(f"Page **{page_name}** (Level {page_level}) has no components to process. Logged as skipped.")
#         return

#     # --- ACCUMULATION PHASE: Component Loop ---
#     for component_name in components:
#         status_entry = {
#             "page": page_name, "component": component_name, "level": page_level,
#             "hierarchy": " > ".join(hierarchy + [page_name]), "available": False, 
#             "status": "SKIPPED: Component not available.",
#             "cms_component_name": "N/A"
#         }
        
#         api_result = check_component_availability(component_name, component_cache)
#         section_payload = None
        
#         if api_result:
#             vComponentId, alias, componentId, cms_component_name = api_result 
            
#             logging.info(f"[SUCCESS] Component '{component_name}' is available. Starting content retrieval for **{page_name}**.")
            
#             status_entry["available"] = True
#             status_entry["cms_component_name"] = cms_component_name
            
#             # 🛑 CONDITION CHECK: Only process content retrieval for "Meetings and Events" 🛑
#             if page_name == "Meetings and Events":
#                 try:
#                     logging.info("inside Meetings and Events content retrieval")
#                     # Call function to get section payload (HTML snippet)
#                     section_payload = add_records_for_page(page_name, vComponentId, componentId, api_base_url, site_id, api_headers, alias)
#                     status_entry["status"] = "SUCCESS: Content retrieved and added to assembly queue."
#                 except Exception as e:
#                     logging.error(f"Content retrieval failed for {page_name}/{component_name}: {e}")
#                     status_entry["status"] = f"FAILED: Content retrieval error: {type(e).__name__}"
#                     status_entry["available"] = False
#             else:
#                 # Data retrieval/record adding is skipped for non-targeted pages
#                 logging.info(f"Skipping record addition for non-targeted page: {page_name}/{component_name}.")
#                 status_entry["status"] = "SUCCESS: Component available, data retrieval skipped (non-targeted page)."
#                 section_payload = "" # Append empty string
            
#             # Append the payload (either retrieved content or an empty string)
#             if section_payload is not None:
#                 page_sections_html.append(section_payload)
            
#         else:
#             logging.warning(f"[ERROR] Component '{component_name}' **NOT AVAILABLE** for page **{page_name}**. Skipping.")
        
#         ASSEMBLY_STATUS_LOG.append(status_entry)

#     # --- FINALIZATION PHASE (with conditional Headers/Footers) ---
    
#     # Check if any sections were successfully retrieved and contain data
#     if page_sections_html and any(page_sections_html): 
        
#         # Concatenate all component HTML sections in order
#         all_sections_concatenated = "".join(page_sections_html)
        
#         # Define HTML wrappers
#         htmlPrefix = '<div class="box2" id="data_page_content"><div id="pagestudio">'
#         htmlPostfix = "</div></div>"
        
#         # --- Helper to conditionally fetch H/F ---
#         def _fetch_optional_component(name: Optional[str]) -> Tuple[Optional[str], Optional[str], Optional[int], str, Optional[str]]:
#             # Returns empty values if name is None or empty string
#             if not name:
#                 # 🛑 FIX APPLIED HERE: Now returns 5 values 🛑
#                 return None, None, None, "", None 
#             # Otherwise, call the API function
#             return getHeaderFooter_html(api_base_url, api_headers, name)

#         # Conditionally fetch Header and Footer components
#         # If the meta_info value (e.g., Header2) is None or "", the API call is skipped.
#         Header1_vComponentId, Header1_component_alias, Header1_component_id, Header1_section_html,Header1_pageSectionGuid = _fetch_optional_component(Header1)
#         Header2_vComponentId, Header2_component_alias, Header2_component_id, Header2_section_html,Header2_pageSectionGuid = _fetch_optional_component(Header2)
#         Footer1_vComponentId, Footer1_component_alias, Footer1_component_id, Footer1_section_html,Footer1_pageSectionGuid = _fetch_optional_component(Footer1)
#         Footer2_vComponentId, Footer2_component_alias, Footer2_component_id, Footer2_section_html,Footer2_pageSectionGuid = _fetch_optional_component(Footer2)
        
#         header_footer_details = {
#             "Header1": {
#                 "name": Header1, "vId": Header1_vComponentId, "alias": Header1_component_alias, 
#                 "id": Header1_component_id, "html": Header1_section_html, "guid": Header1_pageSectionGuid
#             },
#             "Header2": {
#                 "name": Header2, "vId": Header2_vComponentId, "alias": Header2_component_alias, 
#                 "id": Header2_component_id, "html": Header2_section_html, "guid": Header2_pageSectionGuid
#             },
#             "Footer1": {
#                 "name": Footer1, "vId": Footer1_vComponentId, "alias": Footer1_component_alias, 
#                 "id": Footer1_component_id, "html": Footer1_section_html, "guid": Footer1_pageSectionGuid
#             },
#             "Footer2": {
#                 "name": Footer2, "vId": Footer2_vComponentId, "alias": Footer2_component_alias, 
#                 "id": Footer2_component_id, "html": Footer2_section_html, "guid": Footer2_pageSectionGuid
#             },
#         }

#         # Build the final HTML, concatenating potentially empty header/footer strings
#         final_html = htmlPrefix \
#                    + Header1_section_html \
#                    + Header2_section_html \
#                    + all_sections_concatenated \
#                    + Footer1_section_html \
#                    + Footer2_section_html \
#                    + htmlPostfix
        
#         logging.info("\n--- FINAL ASSEMBLED HTML PAYLOAD ---")
#         logging.info(final_html)
#         logging.info("--------------------------------------\n")
        
#         # 🛑 CONDITION CHECK: Only publish "Meetings and Events" 🛑
#         if page_name == "Meetings and Events":
#             logging.info(f"Final assembly complete for **{page_name}**. Calling pageAction for publishing.")
#             # 🌟 STEP 3: Pass the page_template_id to pageAction
#             pageAction(api_base_url, api_headers, final_html, page_name, page_template_id, DefaultTitle, DefaultDescription, site_id, category_id,header_footer_details)
#         else:
#             logging.info(f"Final assembly complete for **{page_name}** but skipping pageAction (non-targeted page).")
            
#     else:
#         # Conditional logging for pages that fail to retrieve content
#         if page_name == "Meetings and Events":
#             logging.error(f"Page **{page_name}** failed: No final HTML content was successfully retrieved to assemble the page. Skipping pageAction.")
#         else:
#             logging.info(f"Page **{page_name}** (non-targeted) completed component checks but assembled an empty page, as expected.")
#         return


def _process_page_components(page_data: Dict[str, Any], page_level: int, hierarchy: List[str], component_cache: List[Dict[str, Any]], api_base_url: str, site_id: int, api_headers: Dict[str, str], category_id: int, component_cache_for_mapping: Optional[List[Dict[str, Any]]] = None):
    
    page_name = page_data.get('page_name', 'UNKNOWN_PAGE')
    components = page_data.get('components', [])
    meta_info = page_data.get('meta_info', {}) 
    
    # 🌟 STEP 1: Extract Metadata
    page_template_name = meta_info.get("PageTemplateName")
    DefaultTitle = meta_info.get("DefaultTitle")
    DefaultDescription = meta_info.get("DefaultDescription")
    Header1 = meta_info.get("Header1")
    Header2 = meta_info.get("Header2")
    Footer1 = meta_info.get("Footer1")
    Footer2 = meta_info.get("Footer2")
    
    page_template_id = None
    
    if page_template_name:
        try:
            # 🌟 STEP 2: Call API to get the Template ID
            template_info = GetTemplatePageByName(api_base_url, api_headers, page_template_name)
            if template_info and isinstance(template_info, list) and 'PageId' in template_info[0]:
                page_template_id = template_info[0]['PageId'] 
            
            logging.info(f"Retrieved Page Template ID {page_template_id} for template: {page_template_name}")
        except Exception as e:
            logging.error(f"Failed to retrieve page template ID for '{page_template_name}': {e}")
            pass
    
    if page_template_id is None:
        logging.warning(f"Could not determine Page Template ID for page: {page_name}. Proceeding without it (or defaulting).")


    # Initialize a list to hold the HTML sections for this page
    page_sections_html = []
    # Track component IDs that belong to this page
    page_component_ids: set = set()

    if not components:
        status_entry = {
            "page": page_name, "component": "N/A", "level": page_level,
            "hierarchy": " > ".join(hierarchy + [page_name]), "available": False, 
            "status": "SKIPPED: Page had no components defined.",
            "cms_component_name": "N/A"
        }
        ASSEMBLY_STATUS_LOG.append(status_entry) 
        logging.warning(f"Page **{page_name}** (Level {page_level}) has no components to process. Logged as skipped.")
        return

    # --- ACCUMULATION PHASE: Component Loop (NOW APPLIES TO ALL PAGES) ---
    # IMPORTANT: Process components in the exact order they appear in simplified.json
    # Do NOT sort or reorder - maintain sequence as defined in JSON
    for component_name in components:
        status_entry = {
            "page": page_name, "component": component_name, "level": page_level,
            "hierarchy": " > ".join(hierarchy + [page_name]), "available": False, 
            "status": "SKIPPED: Component not available.",
            "cms_component_name": "N/A"
        }
        
        api_result = check_component_availability(component_name, component_cache)
        section_payload = None
        
        if api_result:
            vComponentId, alias, componentId, cms_component_name = api_result 
            
            logging.info(f"[SUCCESS] Component '{component_name}' is available. Starting content retrieval for **{page_name}**.")
            
            status_entry["available"] = True
            status_entry["cms_component_name"] = cms_component_name
            
            # Track this component ID as belonging to this page
            page_component_ids.add(str(componentId))
            
            # 🛑 CONDITION CHECK REMOVED 🛑
            try:
                logging.info(f"Attempting content retrieval for page: {page_name}")
                logging.info(f"[TIMING] Starting add_records_for_page for '{page_name}' with component '{component_name}'...")
                records_start_time = time.time()
                # Call function to get section payload (HTML snippet) and add records
                section_payload = add_records_for_page(page_name, vComponentId, componentId, api_base_url, site_id, api_headers, alias)
                records_time = time.time() - records_start_time
                logging.info(f"[TIMING] add_records_for_page completed in {records_time:.2f} seconds")
                
                # Track timing
                if "add_records_for_page" not in TIMING_TRACKER:
                    TIMING_TRACKER["add_records_for_page"] = []
                TIMING_TRACKER["add_records_for_page"].append(records_time)
                status_entry["status"] = "SUCCESS: Content retrieved and records added to assembly queue."
            except Exception as e:
                logging.error(f"Content retrieval failed for {page_name}/{component_name}: {e}")
                status_entry["status"] = f"FAILED: Content retrieval error: {type(e).__name__}"
                status_entry["available"] = False
            
            # Append the payload (either retrieved content or an empty string)
            if section_payload is not None:
                page_sections_html.append(section_payload)
            
        else:
            logging.warning(f"[ERROR] Component '{component_name}' **NOT AVAILABLE** for page **{page_name}**. Skipping.")
        
        ASSEMBLY_STATUS_LOG.append(status_entry)

    # --- FINALIZATION PHASE (NOW APPLIES TO ALL PAGES) ---
    
    # Check if any sections were successfully retrieved and contain data
    # Also check if sections contain non-empty strings (not just empty strings)
    has_content = page_sections_html and any(section and section.strip() for section in page_sections_html if section)
    
    logging.info(f"[DEBUG] Page '{page_name}': page_sections_html count={len(page_sections_html) if page_sections_html else 0}, has_content={has_content}")
    
    if has_content: 
        
        # Concatenate all component HTML sections in order
        all_sections_concatenated = "".join(page_sections_html)
        
        # Define HTML wrappers
        htmlPrefix = '<div class="box2" id="data_page_content"><div id="pagestudio">'
        htmlPostfix = "</div></div>"
        
        # --- Helper to conditionally fetch H/F ---
        def _fetch_optional_component(name: Optional[str]) -> Tuple[Optional[str], Optional[str], Optional[int], str, Optional[str]]:
            # Returns empty values if name is None or empty string
            if not name:
                return None, None, None, "", None 
            # Otherwise, call the API function
            return getHeaderFooter_html(api_base_url, api_headers, name)

        # Conditionally fetch Header and Footer components
        # If the meta_info value (e.g., Header2) is None or "", the API call is skipped.
        Header1_vComponentId, Header1_component_alias, Header1_component_id, Header1_section_html,Header1_pageSectionGuid = _fetch_optional_component(Header1)
        Header2_vComponentId, Header2_component_alias, Header2_component_id, Header2_section_html,Header2_pageSectionGuid = _fetch_optional_component(Header2)
        Footer1_vComponentId, Footer1_component_alias, Footer1_component_id, Footer1_section_html,Footer1_pageSectionGuid = _fetch_optional_component(Footer1)
        Footer2_vComponentId, Footer2_component_alias, Footer2_component_id, Footer2_section_html,Footer2_pageSectionGuid = _fetch_optional_component(Footer2)
        
        # Track header/footer component IDs if they exist
        if Header1_component_id:
            page_component_ids.add(str(Header1_component_id))
        if Header2_component_id:
            page_component_ids.add(str(Header2_component_id))
        if Footer1_component_id:
            page_component_ids.add(str(Footer1_component_id))
        if Footer2_component_id:
            page_component_ids.add(str(Footer2_component_id))
        
        header_footer_details = {
            "Header1": {
                "name": Header1, "vId": Header1_vComponentId, "alias": Header1_component_alias, 
                "id": Header1_component_id, "html": Header1_section_html, "guid": Header1_pageSectionGuid
            },
            "Header2": {
                "name": Header2, "vId": Header2_vComponentId, "alias": Header2_component_alias, 
                "id": Header2_component_id, "html": Header2_section_html, "guid": Header2_pageSectionGuid
            },
            "Footer1": {
                "name": Footer1, "vId": Footer1_vComponentId, "alias": Footer1_component_alias, 
                "id": Footer1_component_id, "html": Footer1_section_html, "guid": Footer1_pageSectionGuid
            },
            "Footer2": {
                "name": Footer2, "vId": Footer2_vComponentId, "alias": Footer2_component_alias, 
                "id": Footer2_component_id, "html": Footer2_section_html, "guid": Footer2_pageSectionGuid
            },
        }

        # Build the final HTML, concatenating potentially empty header/footer strings
        final_html = htmlPrefix \
                   + Header1_section_html \
                   + Header2_section_html \
                   + all_sections_concatenated \
                   + Footer1_section_html \
                   + Footer2_section_html \
                   + htmlPostfix
        
        logging.info("\n--- FINAL ASSEMBLED HTML PAYLOAD ---")
        logging.info(final_html)
        logging.info("--------------------------------------\n")
        
        # 🛑 CONDITION CHECK REMOVED 🛑
        logging.info(f"Final assembly complete for **{page_name}**. Calling pageAction for publishing.")
        # 🌟 STEP 3: Pass the page_template_id, page_component_ids, and component names from simplified.json to pageAction
        page_component_names = components  # Component names from simplified.json
        try:
            result = pageAction(api_base_url, api_headers, final_html, page_name, page_template_id, DefaultTitle, DefaultDescription, site_id, category_id,header_footer_details, page_component_ids, page_component_names, component_cache_for_mapping or component_cache)
            
            # Check if pageAction returned an error
            if isinstance(result, dict) and "error" in result:
                logging.error(f"[ERROR] pageAction returned error for page '{page_name}': {result.get('details', 'Unknown error')}")
            else:
                page_id = result.get("PageId") if isinstance(result, dict) else None
                if page_id:
                    logging.info(f"[SUCCESS] Page '{page_name}' processed successfully (PageId: {page_id})")
                else:
                    logging.warning(f"[WARNING] pageAction completed for '{page_name}' but PageId not found in response")
        except Exception as e:
            logging.error(f"[ERROR] pageAction failed for page '{page_name}': {e}")
            logging.exception("Full traceback:")
            # Continue processing other pages even if this one fails
            
    else:
        # Adjusted logging for general page failure
        logging.error(f"Page **{page_name}** failed: No final HTML content was successfully retrieved/assembled to proceed to pageAction. Skipping pageAction.")
        logging.warning(f"[SKIP] Page '{page_name}' will not be created - no HTML content available")
        logging.info(f"[DEBUG] page_sections_html length: {len(page_sections_html) if page_sections_html else 0}")
        return
        
# --- TRAVERSAL FUNCTIONS TO PASS CACHE AND NEW PARAMS ---

def assemble_page_templates_level4(page_data: Dict[str, Any], page_level: int, hierarchy: List[str], component_cache: List[Dict[str, Any]], api_base_url: str, site_id: int, api_headers: Dict[str, str], component_cache_for_mapping: Optional[List[Dict[str, Any]]] = None):
    logging.info(f"\n--- Level {page_level} Page: {page_data.get('page_name')} ---")
    _process_page_components(page_data, page_level, hierarchy, component_cache, api_base_url, site_id, api_headers, category_id=0, component_cache_for_mapping=component_cache_for_mapping or component_cache)

def assemble_page_templates_level3(page_data: Dict[str, Any], page_level: int, hierarchy: List[str], component_cache: List[Dict[str, Any]], api_base_url: str, site_id: int, api_headers: Dict[str, str], parent_page_name: str, component_cache_for_mapping: Optional[List[Dict[str, Any]]] = None):
    logging.info(f"\n--- Level {page_level} Page: {page_data.get('page_name')} ---")
    matched_category_id = 0
    current_page_name = page_data.get('page_name', 'UNKNOWN_PAGE')

    logging.info(f"\n--- Level {page_level} Page: {current_page_name} ---")
    
    # Fetch categories list (already implemented in the provided GetPageCategoryList)
    categories = GetPageCategoryList(api_base_url, api_headers)
    logging.info(f"API categories loaded: {categories}")
    
    # Check for API errors
    if isinstance(categories, dict) and categories.get("error"):
        logging.error(f"[ERROR] Unable to load page categories. Aborting processing for page '{current_page_name}'. Error: {categories.get('details')}")
        return

    # Category Matching Logic
    normalized_page_name = normalize_page_name(parent_page_name)
    
    # Search category ID by normalized name for robust matching
    for cat in categories:
        cat_name = cat.get("CategoryName")
        
        # NOTE: normalize_page_name must be available/imported
        if cat_name and normalize_page_name(cat_name) == normalized_page_name:
            matched_category_id = cat.get("CategoryId", 0)
            logging.info(f"[SUCCESS] MATCHED Category '{current_page_name}' → CategoryId = {matched_category_id}")
            # Exit loop immediately after finding a match
            break 
    else:
        # This executes only if the loop completes without finding a match (i.e., if 'break' was never hit)
        logging.warning(f"[WARNING] No matching category found for page '{current_page_name}', using CategoryId = 0")
        # matched_category_id remains 0, as initialized above.
    
    _process_page_components(page_data, page_level, hierarchy, component_cache, api_base_url, site_id, api_headers, matched_category_id, component_cache_for_mapping=component_cache_for_mapping or component_cache)
    
    new_hierarchy = hierarchy + [current_page_name]
    new_level = page_level + 1
    for sub_page_data in page_data.get("sub_pages", []):
        assemble_page_templates_level4(sub_page_data, new_level, new_hierarchy, component_cache, api_base_url, site_id, api_headers, component_cache_for_mapping=component_cache_for_mapping or component_cache)


def assemble_page_templates_level2(
    page_data: Dict[str, Any], 
    page_level: int, 
    hierarchy: List[str], 
    component_cache: List[Dict[str, Any]], 
    api_base_url: str, 
    site_id: int, 
    api_headers: Dict[str, str],
    parent_page_name: str,
    component_cache_for_mapping: Optional[List[Dict[str, Any]]] = None
):
    # Initialize the ID variable at the start. Default to 0 if no match is found.
    matched_category_id = 0
    current_page_name = page_data.get('page_name', 'UNKNOWN_PAGE')

    logging.info(f"\n--- Level {page_level} Page: {current_page_name} ---")
    
    # Fetch categories list (already implemented in the provided GetPageCategoryList)
    categories = GetPageCategoryList(api_base_url, api_headers)
    logging.info(f"API categories loaded: {categories}")
    
    # Check for API errors
    if isinstance(categories, dict) and categories.get("error"):
        logging.error(f"[ERROR] Unable to load page categories. Aborting processing for page '{current_page_name}'. Error: {categories.get('details')}")
        return

    # Category Matching Logic
    normalized_page_name = normalize_page_name(parent_page_name)
    
    # Search category ID by normalized name for robust matching
    for cat in categories:
        cat_name = cat.get("CategoryName")
        
        # NOTE: normalize_page_name must be available/imported
        if cat_name and normalize_page_name(cat_name) == normalized_page_name:
            matched_category_id = cat.get("CategoryId", 0)
            logging.info(f"[SUCCESS] MATCHED Category '{current_page_name}' → CategoryId = {matched_category_id}")
            # Exit loop immediately after finding a match
            break 
    else:
        # This executes only if the loop completes without finding a match (i.e., if 'break' was never hit)
        logging.warning(f"[WARNING] No matching category found for page '{current_page_name}', using CategoryId = 0")
        # matched_category_id remains 0, as initialized above.

    # The variable 'matched_category_id' now holds the correct ID (or 0 if none was found).
    _process_page_components(
        page_data, 
        page_level, 
        hierarchy, 
        component_cache, 
        api_base_url, 
        site_id, 
        api_headers,
        category_id=matched_category_id, # <-- CORRECTED
        component_cache_for_mapping=component_cache_for_mapping or component_cache
    )
    
    # --- Recursive Call Setup ---
    new_hierarchy = hierarchy + [current_page_name]
    new_level = page_level + 1
    parent_page_name = current_page_name
    for sub_page_data in page_data.get("sub_pages", []):
        assemble_page_templates_level3(
            sub_page_data, 
            new_level, 
            new_hierarchy, 
            component_cache, 
            api_base_url, 
            site_id, 
            api_headers,
            parent_page_name,
            component_cache_for_mapping=component_cache_for_mapping or component_cache
        )

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
# def assemble_page_templates_level1(processed_json: Dict[str, Any], component_cache: List[Dict[str, Any]], api_base_url: str, site_id: int, api_headers: Dict[str, str]):
#     logging.info("\n========================================================")
#     logging.info("START: Component-Based Template Assembly (Level 1 Traversal)")
#     logging.info("========================================================")
#     pages = processed_json.get('pages', [])
#     if not pages:
#         logging.warning("No 'pages' list found in the processed JSON. Aborting assembly.")
#         return
#     initial_level = 1
#     initial_hierarchy: List[str] = []
#     for top_level_page in pages:
#         current_page_name = top_level_page.get('page_name', 'UNKNOWN_PAGE')
#         if current_page_name == "Weddings":
#             logging.info(f"\n--- Level {initial_level} Page: {current_page_name} ---")
#             alldata = GetPageCategoryList(api_base_url, api_headers)
#             category_id = 0
#             _process_page_components(top_level_page, initial_level, initial_hierarchy, component_cache, api_base_url, site_id, api_headers,category_id)
#             next_level = initial_level + 1
#             new_hierarchy = initial_hierarchy + [current_page_name]
#             for sub_page_data in top_level_page.get("sub_pages", []):
#                 assemble_page_templates_level2(sub_page_data, next_level, new_hierarchy, component_cache, api_base_url, site_id, api_headers) 
#                 pass
#     logging.info("\n========================================================")
#     logging.info("END: Component-Based Template Assembly Traversal Complete")
#     logging.info("========================================================")


def assemble_page_templates_level1(processed_json: Dict[str, Any], component_cache: List[Dict[str, Any]], api_base_url: str, site_id: int, api_headers: Dict[str, str]):
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

        # Debug log into separate file so we can see exactly which pages/components are being processed
        append_debug_log(
            "level1_page_start",
            {
                "page_name": current_page_name,
                "components": top_level_page.get("components", []),
                "source": "_simplified.json",
            },
        )

        print(current_page_name)
        logging.info(f"\n--- Level {initial_level} Page: {current_page_name} ---")

        # Default category ID
        category_id = 0

        # Call processor for page
        _process_page_components(
            top_level_page,
            initial_level,
            initial_hierarchy,
            component_cache,
            api_base_url,
            site_id,
            api_headers,
            category_id,  # passing resolved category id
            component_cache_for_mapping=component_cache  # Pass component cache for mapping
        )

        next_level = initial_level + 1
        new_hierarchy = initial_hierarchy + [current_page_name]
        parent_page_name = current_page_name
        # Go to sub-pages (level2)
        # IMPORTANT: Process sub_pages in the exact order they appear in simplified.json
        # Do NOT sort or reorder - maintain sequence as defined in JSON
        for sub_page_data in top_level_page.get("sub_pages", []):
            assemble_page_templates_level2(sub_page_data, next_level, new_hierarchy, component_cache, api_base_url, site_id, api_headers, parent_page_name, component_cache_for_mapping=component_cache)
        # else:
        #     pass

    logging.info("\n========================================================")
    logging.info("END: Component-Based Template Assembly Traversal Complete")
    logging.info("========================================================")



def update_menu_navigation(file_prefix: str, api_base_url: str, site_id: int, api_headers: Dict[str, str]):
    """
    Updates menu navigation by:
    1. Reading _util_pages.json to extract menu component name from Automation Guide
    2. Calling API to get all components and saving the response
    3. Reading _simplified.json to extract page tree structure
    4. Filtering pages where meta_info is not blank
    5. Creating and saving menu_navigation.json file
    """
    logging.info("========================================================")
    logging.info("START: Menu Navigation Update")
    logging.info("========================================================")
    
    try:
        # 1. Read _util_pages.json and extract menu component name from Automation Guide
        util_pages_file = os.path.join(UPLOAD_FOLDER, f"{file_prefix}_util_pages.json")
        
        if not os.path.exists(util_pages_file):
            logging.error(f"File not found: {util_pages_file}")
            raise FileNotFoundError(f"Could not find {util_pages_file}")
        
        with open(util_pages_file, 'r', encoding='utf-8') as f:
            util_pages_data = json.load(f)
        
        menu_component_name = None
        menu_level = None
        downloaded_component_id = None
        for page in util_pages_data.get('pages', []):
            page_name = page.get('text', page.get('page_name', ''))
            if "automation guide" in page_name.strip().lower():
                # Extract menu component name and menuLevel from description/content
                # New format: JSON embedded in description with HTML entities
                content_source = page.get('content_blocks', '') or page.get('description', '')
                
                # Decode HTML entities multiple times to handle nested encoding
                decoded_content = html.unescape(content_source)
                decoded_content = html.unescape(decoded_content)
                decoded_content = html.unescape(decoded_content)
                
                # Try to extract JSON from the content
                # Look for "mainMenu" JSON structure: "mainMenu": [{...}]
                # Pattern matches: "mainMenu": [...] or 'mainMenu': [...] or mainMenu: [...]
                main_menu_json_pattern = r'["\']?mainMenu["\']?\s*:\s*\[(.*?)\]'
                json_match = re.search(main_menu_json_pattern, decoded_content, re.IGNORECASE | re.DOTALL)
                
                if json_match:
                    try:
                        # Extract the array content
                        array_content = json_match.group(1)
                        
                        # Clean up HTML tags and line breaks from array content
                        array_content = re.sub(r'<[^>]+>', '', array_content)  # Remove HTML tags
                        array_content = re.sub(r'<br\s*/?>', '', array_content, flags=re.IGNORECASE)  # Remove <br> tags
                        array_content = re.sub(r'\s+', ' ', array_content)  # Normalize whitespace
                        
                        # Try to parse as full JSON object to get both componentName and menuLevel
                        json_obj_str = '{"mainMenu": [' + array_content + ']}'
                        try:
                            parsed_json = json.loads(json_obj_str)
                            if 'mainMenu' in parsed_json and isinstance(parsed_json['mainMenu'], list) and len(parsed_json['mainMenu']) > 0:
                                menu_item = parsed_json['mainMenu'][0]
                                menu_component_name = menu_item.get('componentName', '').strip()
                                menu_level = menu_item.get('menuLevel')
                                
                                if menu_component_name:
                                    logging.info(f"Found menu component name from parsed JSON: {menu_component_name}, menuLevel: {menu_level}")
                                    break
                        except json.JSONDecodeError:
                            # Fallback: Extract componentName and menuLevel using regex if JSON parsing fails
                            component_name_match = re.search(r'["\']componentName["\']\s*:\s*["\']([^"\']+)["\']', array_content, re.IGNORECASE)
                            if component_name_match:
                                menu_component_name = component_name_match.group(1).strip()
                                logging.info(f"Found menu component name from JSON: {menu_component_name}")
                            
                            # Extract menuLevel
                            menu_level_match = re.search(r'["\']menuLevel["\']\s*:\s*(\d+)', array_content, re.IGNORECASE)
                            if menu_level_match:
                                try:
                                    menu_level = int(menu_level_match.group(1))
                                    logging.info(f"Found menuLevel: {menu_level}")
                                except ValueError:
                                    pass
                            
                            if menu_component_name:
                                break
                    except Exception as e:
                        logging.warning(f"Error parsing JSON from Automation Guide: {e}")
                
                # Fallback: Look for "Main Menu: ComponentName" pattern (old format)
                main_menu_pattern = r'Main\s*Menu:\s*(.+)$'
                match = re.search(main_menu_pattern, decoded_content, re.IGNORECASE | re.DOTALL)
                if match:
                    # Extract and clean up the component name (remove newlines, normalize whitespace)
                    menu_component_name = match.group(1).strip()
                    # Replace newlines with spaces and normalize multiple spaces
                    menu_component_name = re.sub(r'[\n\r]+', ' ', menu_component_name)
                    menu_component_name = re.sub(r'\s+', ' ', menu_component_name).strip()
                    logging.info(f"Found menu component name (old format): {menu_component_name}")
                    break
        
        if not menu_component_name:
            logging.warning("Menu component name not found in Automation Guide. Using default.")
            menu_component_name = "Main Menu"
        
        # 2. Read _simplified.json and extract page tree structure
        simplified_file = os.path.join(UPLOAD_FOLDER, f"{file_prefix}_simplified.json")
        
        if not os.path.exists(simplified_file):
            logging.error(f"File not found: {simplified_file}")
            raise FileNotFoundError(f"Could not find {simplified_file}")
        
        with open(simplified_file, 'r', encoding='utf-8') as f:
            simplified_data = json.load(f)
        
        # Determine starting level based on menuLevel
        # If menuLevel is 0, pages start from level 0, otherwise start from level 1
        starting_level = 0 if menu_level == 0 else 1
        
        def extract_page_tree(page_node, level=None):
            """Recursively extract page_name, level, and sub_pages maintaining tree structure.
            Only includes pages where meta_info is not blank/empty.
            
            Args:
                page_node: The page node from simplified.json
                level: The current depth level (uses starting_level for top-level pages)
            """
            # Use starting_level if level is not provided (first call)
            if level is None:
                level = starting_level
                
            page_name = page_node.get("page_name", "")
            
            # Check if meta_info exists and is not empty
            meta_info = page_node.get("meta_info", {})
            if not meta_info or meta_info == {}:
                # Skip pages with empty meta_info
                return None
            
            page_tree = {
                "page_name": page_name,
                "level": level
            }
            
            # Recursively process sub_pages and filter out None values (pages with empty meta_info)
            sub_pages = page_node.get("sub_pages", [])
            if sub_pages:
                processed_sub_pages = [extract_page_tree(sub_page, level + 1) for sub_page in sub_pages]
                valid_sub_pages = [sp for sp in processed_sub_pages if sp is not None]
                
                # Only add sub_pages key if there are valid sub_pages
                if valid_sub_pages:
                    page_tree["sub_pages"] = valid_sub_pages
            
            return page_tree
        
        # Extract pages tree from simplified.json - only pages with non-empty meta_info
        pages_tree = []
        pages_list_simplified = simplified_data.get('pages', [])
        
        for page in pages_list_simplified:
            page_tree = extract_page_tree(page)
            # Only add pages that have non-empty meta_info
            if page_tree is not None:
                pages_tree.append(page_tree)
        
        logging.info(f"Extracted {len(pages_tree)} main pages with their sub-pages")
        
        # 2.5. Call API to get all components and save the response
        try:
            logging.info("Calling API to fetch all components...")
            all_components_response = GetAllVComponents(api_base_url, api_headers, page_size=1000)
            
            if all_components_response and isinstance(all_components_response, list):
                # Save the full component list response to a JSON file for debugging
                components_output_filename = f"{file_prefix}_all_components_response.json"
                components_output_filepath = os.path.join(UPLOAD_FOLDER, components_output_filename)
                
                components_data_to_save = {
                    "total_components": len(all_components_response),
                    "components": all_components_response
                }
                
                with open(components_output_filepath, 'w', encoding='utf-8') as f:
                    json.dump(components_data_to_save, f, indent=4, ensure_ascii=False)
                
                logging.info(f"[SUCCESS] All components JSON response saved to: {components_output_filepath}")
                logging.info(f"   Total components saved: {len(all_components_response)}")
                print(f"Saved all components response to: {components_output_filename} ({len(all_components_response)} components)")
                
                # 2.6. Search for matching component and download zip if found
                if menu_component_name:
                    try:
                        logging.info(f"Searching for component matching '{menu_component_name}'...")
                        
                        # Normalize the search name for flexible matching
                        def normalize_component_name(name: str) -> str:
                            """Normalize component name for comparison (remove spaces, hyphens, underscores, case-insensitive)"""
                            if not name:
                                return ""
                            return re.sub(r'[\s\-_]+', '', name).lower()
                        
                        normalized_search_name = normalize_component_name(menu_component_name)
                        matching_component = None
                        
                        # Search through all components
                        for comp in all_components_response:
                            comp_name = comp.get('name', '')
                            comp_component_name = comp.get('component', {}).get('componentName', '')
                            
                            # Check both 'name' and 'component.componentName' fields
                            if (comp_name and normalize_component_name(comp_name) == normalized_search_name) or \
                               (comp_component_name and normalize_component_name(comp_component_name) == normalized_search_name):
                                matching_component = comp
                                logging.info(f"[SUCCESS] Found matching component: '{comp_name}' or '{comp_component_name}'")
                                break
                        
                        if matching_component:
                            # Get componentId from component.componentId or miBlockId
                            component_id = matching_component.get('component', {}).get('componentId') or \
                                          matching_component.get('miBlockId') or \
                                          matching_component.get('blockId')
                            
                            if component_id:
                                downloaded_component_id = component_id  # Store for later use
                                
                                # Check if component is already downloaded
                                mi_block_folder = f"mi-block-ID-{component_id}"
                                output_dir = os.path.join("output", str(site_id))
                                save_folder = os.path.join(output_dir, mi_block_folder)
                                records_file_path = os.path.join(save_folder, "MiBlockComponentRecords.json")
                                config_file_path = os.path.join(save_folder, "MiBlockComponentConfig.json")
                                component_already_downloaded = os.path.exists(records_file_path) and os.path.exists(config_file_path)
                                
                                if component_already_downloaded:
                                    logging.info(f"Component ID {component_id} already downloaded. Skipping download and unzip.")
                                    print(f"\n{'='*80}")
                                    print(f"Component already exists: {menu_component_name} (ID: {component_id})")
                                    print(f"Location: {save_folder}")
                                    print(f"{'='*80}\n")
                                else:
                                    logging.info(f"Downloading component with ID: {component_id}")
                                    print(f"\n{'='*80}")
                                    print(f"Downloading component: {menu_component_name} (ID: {component_id})")
                                    print(f"{'='*80}\n")
                                    
                                    # Call export API to download zip
                                    response_content, content_disposition = export_mi_block_component(
                                        api_base_url, component_id, site_id, api_headers
                                    )
                                    
                                    if response_content:
                                        # Set up export folder structure
                                        os.makedirs(save_folder, exist_ok=True)
                                        
                                        # Save the zip file
                                        filename = (
                                            content_disposition.split('filename=')[1].strip('"')
                                            if content_disposition and 'filename=' in content_disposition
                                            else f"component_{component_id}.zip"
                                        )
                                        file_path = os.path.join(save_folder, filename)
                                        
                                        logging.info(f"Saving zip file to: {file_path}")
                                        print(f"[SAVE] Saving zip file...")
                                        with open(file_path, "wb") as file:
                                            file.write(response_content)

                                        if zipfile.is_zipfile(file_path):
                                            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                                                zip_ref.extractall(save_folder)
                                            os.remove(file_path)
                                        else:
                                            print(f"  [WARNING] Exported file {filename} is not a zip file.")
                                        
                                        file_size = len(response_content)
                                        logging.info(f"[SUCCESS] Zip file saved successfully! Size: {file_size} bytes")
                                        print(f"[SUCCESS] Zip file saved successfully!")
                                        print(f"   File: {filename}")
                                        print(f"   Size: {file_size} bytes")
                                        print(f"   Location: {file_path}")
                                        print(f"{'='*80}\n")
                                    else:
                                        logging.warning(f"[WARNING] Component export returned no content for component ID: {component_id}")
                                        print(f"[WARNING] Component export returned no content")

                                # 2. Convert .txt files to .json (if they exist) - only if component was downloaded
                                if not component_already_downloaded:
                                    logging.info("[PROCESSING] Starting TXT to JSON conversion...")
                                    txt_files_found = [f for f in os.listdir(save_folder) if f.endswith('.txt')]
                                    logging.info(f"   Found {len(txt_files_found)} .txt files to convert: {txt_files_found}")
                                    
                                    converted_count = 0
                                    for extracted_file in os.listdir(save_folder):
                                        extracted_file_path = os.path.join(save_folder, extracted_file)
                                        if extracted_file.endswith('.txt'):
                                            new_file_path = os.path.splitext(extracted_file_path)[0] + '.json'
                                            try:
                                                logging.info(f"   Converting: {extracted_file} -> {os.path.basename(new_file_path)}")
                                                # Read and process content inside the 'with' block
                                                with open(extracted_file_path, 'r', encoding="utf-8") as txt_file:
                                                    content = txt_file.read()
                                                    json_content = json.loads(content)
                                                
                                                # Write to new file inside its own 'with' block
                                                with open(new_file_path, 'w', encoding="utf-8") as json_file:
                                                    json.dump(json_content, json_file, indent=4)
                                                
                                                # Add a micro-sleep to help OS release the file handle before deletion
                                                time.sleep(0.05) 
                                                
                                                os.remove(extracted_file_path)
                                                converted_count += 1
                                                logging.info(f"   [SUCCESS] Successfully converted: {extracted_file}")
                                            except (json.JSONDecodeError, OSError) as e:
                                                # Log the error but continue to the next file
                                                logging.error(f"[ERROR] Error processing file {extracted_file_path}: {e}")
                                
                                logging.info(f"[SUCCESS] TXT to JSON conversion complete: {converted_count}/{len(txt_files_found)} files converted successfully")

                                # 3. Add level fields to MiBlockComponentRecords.json
                                records_file_path = os.path.join(save_folder, "MiBlockComponentRecords.json")
                                if os.path.exists(records_file_path):
                                    try:
                                        add_levels_to_records(records_file_path)
                                        logging.info(f"[SUCCESS] Added level fields to records in {records_file_path}")
                                    except Exception as e:
                                        logging.error(f"[ERROR] Error adding levels to records: {e}")

                                
                                # --- POLLING LOGIC to wait for MiBlockComponentConfig.json to be accessible ---
                                config_file_name = "MiBlockComponentConfig.json"
                                config_file_path = os.path.join(save_folder, config_file_name)
                                
                                MAX_WAIT_SECONDS = 120 # 2 minutes max wait
                                POLL_INTERVAL = 5      # Check every 5 seconds
                                start_time = time.time()
                                file_ready = False

                                # print(f"Waiting up to {MAX_WAIT_SECONDS} seconds for {config_file_name} to be available...")

                                while time.time() - start_time < MAX_WAIT_SECONDS:
                                    if os.path.exists(config_file_path):
                                        # Try to open the file to check if it's locked
                                        try:
                                            with open(config_file_path, 'r') as f:
                                                f.read(1) # Read a byte to confirm accessibility
                                            file_ready = True
                                            break
                                        except IOError:
                                            print(f"File {config_file_name} exists but is locked. Retrying in {POLL_INTERVAL}s...")
                                    else:
                                        print(f"File {config_file_name} not found yet. Retrying in {POLL_INTERVAL}s...")
                                    
                                    time.sleep(POLL_INTERVAL)

                                if not file_ready:
                                    raise FileNotFoundError(f"🚨 Timeout: Required configuration file {config_file_name} was not generated or released within {MAX_WAIT_SECONDS} seconds.")
                                # --- END POLLING LOGIC ---
                                
                                # Continue with processing regardless of whether component was downloaded or already existed
                                # 3. Add level fields to MiBlockComponentRecords.json (if not already done)
                                records_file_path = os.path.join(save_folder, "MiBlockComponentRecords.json")
                                if os.path.exists(records_file_path):
                                    try:
                                        add_levels_to_records(records_file_path)
                                        logging.info(f"[SUCCESS] Added level fields to records in {records_file_path}")
                                    except Exception as e:
                                        logging.error(f"[ERROR] Error adding levels to records: {e}")




                            else:
                                logging.warning(f"[WARNING] Component ID not found in matching component data")
                        else:
                            logging.warning(f"[WARNING] No matching component found for '{menu_component_name}'")
                            print(f"\n[WARNING]  No matching component found for '{menu_component_name}'")




                    except Exception as export_error:
                        logging.error(f"[ERROR] Error during component download: {export_error}")
                        logging.exception("Full traceback:")
                        # Continue execution even if download fails
            else:
                logging.warning(f"[WARNING] API response was not a list or was empty. Response type: {type(all_components_response)}")
        except Exception as e:
            logging.error(f"[ERROR] Error fetching/saving components: {e}")
            # Continue execution even if component fetch fails
        
        # 3. Create new JSON structure
        menu_navigation_data = {
            "menu_component_name": menu_component_name,
            "menuLevel": menu_level,
            "pages": pages_tree
        }
        
        # 4. Save the new JSON file
        output_filename = f"{file_prefix}_menu_navigation.json"
        output_filepath = os.path.join(UPLOAD_FOLDER, output_filename)
        
        with open(output_filepath, 'w', encoding='utf-8') as f:
            json.dump(menu_navigation_data, f, indent=4, ensure_ascii=False)
        
        logging.info(f"[SUCCESS] Menu navigation JSON saved to: {output_filepath}")
        print(f"Created new JSON file: {output_filename}")
        
        # 5. Map pages to records if component was downloaded
        if downloaded_component_id:
            logging.info(f"Starting page-to-record mapping for component ID: {downloaded_component_id}")
            if map_pages_to_records(file_prefix, site_id, downloaded_component_id):
                # 6. Create payloads for both matched and unmatched records
                logging.info("Creating payloads for matched records (update)...")
                create_save_miblock_records_payload(file_prefix, downloaded_component_id, site_id, api_base_url, api_headers)
                
                logging.info("Creating payloads for unmatched records (create new)...")
                create_new_records_payload(file_prefix, downloaded_component_id, site_id, api_base_url, api_headers)
        else:
            logging.warning("Component ID not found for page-to-record mapping. Skipping.")
        
    except FileNotFoundError as e:
        logging.error(f"File not found: {e}")
        raise
    except json.JSONDecodeError as e:
        logging.error(f"JSON decode error: {e}")
        raise
    except Exception as e:
        logging.error(f"Error processing menu navigation: {e}")
        raise
    
    logging.info("END: Menu Navigation Update Complete")
    logging.info("========================================================")


def map_pages_to_records(file_prefix: str, site_id: int, component_id: int) -> bool:
    """
    Maps page names from menu_navigation.json to records in MiBlockComponentRecords.json
    based on menuLevel.
    
    Logic:
    - If menuLevel = 0:
      * Level 0 pages → search in records with level = 0
      * Level 1 pages → search in records with level = 1
    - If menuLevel = 1:
      * Level 0 pages → search in records with level = 1
      * Level 1 pages → search in records with level = 2
    
    For each page, searches RecordJsonString for keys ending with '-name' and matches
    the value with page_name. If match found, saves the entire record to a new JSON file.
    If no match, updates menu_navigation.json with matchFound: false.
    
    Args:
        file_prefix: The file prefix for menu_navigation.json
        site_id: The site ID to locate the records folder
        component_id: The component ID to locate the records folder
        
    Returns:
        bool: True if successful, False otherwise
    """
    logging.info("========================================================")
    logging.info("START: Mapping Pages to Records")
    logging.info("========================================================")
    
    try:
        # 1. Read menu_navigation.json
        menu_nav_file = os.path.join(UPLOAD_FOLDER, f"{file_prefix}_menu_navigation.json")
        if not os.path.exists(menu_nav_file):
            logging.error(f"Menu navigation file not found: {menu_nav_file}")
            return False
        
        with open(menu_nav_file, 'r', encoding='utf-8') as f:
            menu_nav_data = json.load(f)
        
        menu_level = menu_nav_data.get("menuLevel")
        if menu_level is None:
            logging.warning("menuLevel not found in menu_navigation.json. Skipping mapping.")
            return False
        
        # 2. Locate MiBlockComponentRecords.json
        records_folder = os.path.join("output", str(site_id), f"mi-block-ID-{component_id}")
        records_file = os.path.join(records_folder, "MiBlockComponentRecords.json")
        
        if not os.path.exists(records_file):
            logging.error(f"Records file not found: {records_file}")
            return False
        
        with open(records_file, 'r', encoding='utf-8') as f:
            records_data = json.load(f)
        
        component_records = records_data.get("componentRecords", [])
        if not component_records:
            logging.warning("No componentRecords found in MiBlockComponentRecords.json")
            return False
        
        # 3. Helper function to normalize strings for comparison
        def normalize_string_for_matching(text: str) -> str:
            """Normalizes strings for comparison by handling special characters and HTML entities."""
            if not text:
                return ""
            
            # Convert to string and strip
            normalized = str(text).strip()
            
            # Decode HTML entities (like &amp; -> &)
            normalized = html.unescape(normalized)
            
            # Replace common variations
            normalized = normalized.replace('&', ' and ')  # Replace & with " and "
            normalized = normalized.replace('&amp;', ' and ')  # Replace &amp; with " and "
            normalized = normalized.replace('&nbsp;', ' ')  # Replace &nbsp; with space
            
            # Normalize whitespace (multiple spaces to single space)
            normalized = re.sub(r'\s+', ' ', normalized)
            
            # Convert to lowercase for case-insensitive comparison
            normalized = normalized.lower()
            
            # Remove leading/trailing spaces
            normalized = normalized.strip()
            
            return normalized
        
        # 4. Helper function to extract name values from RecordJsonString
        def extract_name_from_record(record_json_string: str) -> Optional[str]:
            """Extracts value from any key ending with '-name' in RecordJsonString."""
            try:
                # Parse the JSON string
                record_json = json.loads(record_json_string)
                
                # Find keys ending with '-name'
                for key, value in record_json.items():
                    if key.endswith('-name') and value:
                        # Return the first non-empty value found
                        name_value = str(value).strip()
                        logging.debug(f"Found key '{key}' with value '{name_value}'")
                        return name_value
                
                return None
            except (json.JSONDecodeError, Exception) as e:
                logging.warning(f"Error parsing RecordJsonString: {e}")
                logging.debug(f"RecordJsonString content (first 200 chars): {record_json_string[:200]}")
                return None
        
        # 4. Helper function to generate URL-friendly slug from page name
        def generate_url_slug(page_name: str) -> str:
            """Converts page name to URL-friendly slug."""
            if not page_name:
                return ""
            
            # Replace & with and
            slug = page_name.replace('&', 'and')
            slug = slug.replace('&amp;', 'and')
            
            # Convert to lowercase
            slug = slug.lower()
            
            # Replace spaces and special characters with hyphens
            slug = re.sub(r'[^\w\s-]', '', slug)  # Remove special chars except hyphens
            slug = re.sub(r'[-\s]+', '-', slug)  # Replace spaces and multiple hyphens with single hyphen
            slug = slug.strip('-')  # Remove leading/trailing hyphens
            
            return slug
        
        # 5. Helper function to update link in RecordJsonString and extract name/link values
        def update_record_link(record_json_string: str, page_name: str, parent_page_name: Optional[str] = None) -> Tuple[str, Optional[str], Optional[str]]:
            """
            Updates the link field (ending with -link) in RecordJsonString with page name.
            Also extracts the -name and -link values for easy access.
            
            Returns:
                Tuple of (updated_json_string, name_key, name_value, link_key, link_value)
            """
            try:
                # Parse the JSON string
                record_json = json.loads(record_json_string)
                
                # Find keys ending with -name and -link
                name_key = None
                name_value = None
                link_key = None
                link_value = None
                
                for key in record_json.keys():
                    if key.endswith('-name'):
                        name_key = key
                        name_value = record_json.get(key)
                    elif key.endswith('-link'):
                        link_key = key
                        link_value = record_json.get(key)
                
                if link_key:
                    # Generate URL slug from page name
                    page_slug = generate_url_slug(page_name)
                    
                    # Build the link path
                    if parent_page_name:
                        # For sub-pages, include parent in path
                        parent_slug = generate_url_slug(parent_page_name)
                        link_path = f"{parent_slug}/{page_slug}"
                    else:
                        # For top-level pages, just use the page slug
                        link_path = page_slug
                    
                    # Update the link with %%strpath%% prefix
                    new_link = f"%%strpath%%{link_path}"
                    record_json[link_key] = new_link
                    link_value = new_link  # Update the extracted value
                    
                    logging.info(f"  Updated link '{link_key}' to '{new_link}'")
                    
                    # Convert back to JSON string
                    updated_json_string = json.dumps(record_json, ensure_ascii=False)
                    return updated_json_string, name_key, name_value, link_key, link_value
                else:
                    logging.warning(f"  No '-link' key found in RecordJsonString")
                    return record_json_string, name_key, name_value, None, None
                    
            except (json.JSONDecodeError, Exception) as e:
                logging.warning(f"Error updating link in RecordJsonString: {e}")
                return record_json_string, None, None, None, None
        
        # 6. Collect all matched records in a list
        all_matched_records = []
        
        # Helper function to recursively process pages
        def process_page(page_node: Dict[str, Any], page_level: int, records_level: int, parent_page_name: Optional[str] = None) -> bool:
            """Process a single page and its sub_pages recursively."""
            page_name = page_node.get("page_name", "").strip()
            if not page_name:
                return False
            
            logging.info(f"Searching for page '{page_name}' (page_level={page_level}) in records with level={records_level}")
            
            # Find matching record in records with the specified level
            matched_record = None
            records_checked = 0
            for record in component_records:
                record_level = record.get("level")
                if record_level == records_level:
                    records_checked += 1
                    record_json_string = record.get("RecordJsonString", "")
                    if record_json_string:
                        extracted_name = extract_name_from_record(record_json_string)
                        if extracted_name:
                            # Normalize both strings for comparison
                            normalized_extracted = normalize_string_for_matching(extracted_name)
                            normalized_page = normalize_string_for_matching(page_name)
                            
                            logging.debug(f"  Comparing '{extracted_name}' (normalized: '{normalized_extracted}') with '{page_name}' (normalized: '{normalized_page}')")
                            if normalized_extracted == normalized_page:
                                matched_record = record
                                logging.info(f"  [SUCCESS] Match found! Record ID: {record.get('Id')}")
                                break
                        else:
                            logging.debug(f"  No '-name' key found in record ID: {record.get('Id')}")
            
            logging.info(f"Checked {records_checked} records at level {records_level} for page '{page_name}'")
            
            if matched_record:
                # Update the link in RecordJsonString before saving and extract name/link values
                original_record_json_string = matched_record.get("RecordJsonString", "")
                updated_record_json_string, name_key, name_value, link_key, link_value = update_record_link(
                    original_record_json_string, page_name, parent_page_name
                )
                
                # Create a copy of the matched record with updated link
                matched_record_with_page_info = matched_record.copy()
                matched_record_with_page_info["RecordJsonString"] = updated_record_json_string
                matched_record_with_page_info["matched_page_name"] = page_name
                matched_record_with_page_info["matched_page_level"] = page_level
                matched_record_with_page_info["matched_records_level"] = records_level
                matched_record_with_page_info["parent_page_name"] = parent_page_name
                
                # Get page status from page_node (based on ShowInNavigation: Yes/No)
                # If not present, use existing record status
                page_status = page_node.get("page_status")
                if page_status is not None:
                    matched_record_with_page_info["page_status"] = page_status
                    logging.debug(f"  Page '{page_name}' status from ShowInNavigation: {page_status}")
                
                # Add extracted name and link as top-level keys for easy access
                if name_key and name_value is not None:
                    matched_record_with_page_info[name_key] = name_value
                    logging.debug(f"  Added top-level key '{name_key}' = '{name_value}'")
                
                if link_key and link_value is not None:
                    matched_record_with_page_info[link_key] = link_value
                    logging.debug(f"  Added top-level key '{link_key}' = '{link_value}'")
                
                # Add to the collection
                all_matched_records.append(matched_record_with_page_info)
                
                logging.info(f"[SUCCESS] Matched '{page_name}' (level {page_level}) → added to collection")
                page_node["matchFound"] = True
            else:
                logging.warning(f"[ERROR] No match found for '{page_name}' (level {page_level})")
                page_node["matchFound"] = False
            
            # Process sub_pages recursively (pass current page_name as parent)
            sub_pages = page_node.get("sub_pages", [])
            if sub_pages:
                # Determine the records level for sub_pages based on menuLevel
                if menu_level == 0:
                    # Sub-pages search in records level = sub_page_level
                    for sub_page in sub_pages:
                        sub_page_level = sub_page.get("level", page_level + 1)
                        sub_records_level = sub_page_level
                        process_page(sub_page, sub_page_level, sub_records_level, page_name)
                elif menu_level == 1:
                    # Sub-pages of level 1 pages search in records level 2
                    # But if parent is level 0, sub-pages (level 1) search in level 1
                    for sub_page in sub_pages:
                        sub_page_level = sub_page.get("level", page_level + 1)
                        if page_level == 0 and sub_page_level == 1:
                            sub_records_level = 1  # Level 1 sub-pages of level 0 parent search in level 1
                        elif page_level == 1 and sub_page_level == 2:
                            sub_records_level = 2  # Level 2 sub-pages of level 1 parent search in level 2
                        else:
                            sub_records_level = sub_page_level
                        process_page(sub_page, sub_page_level, sub_records_level, page_name)
                else:
                    # Default: increment records level
                    for sub_page in sub_pages:
                        sub_page_level = sub_page.get("level", page_level + 1)
                        sub_records_level = records_level + 1
                        process_page(sub_page, sub_page_level, sub_records_level, page_name)
            
            return matched_record is not None
        
        # 7. Process all pages based on menuLevel
        pages = menu_nav_data.get("pages", [])
        logging.info(f"Processing {len(pages)} pages with menuLevel={menu_level}")
        
        for page in pages:
            page_level = page.get("level", 0)
            
            # Determine records level based on menuLevel
            # If menuLevel = 0: level 0 pages → records level 0, level 1 pages → records level 1
            # If menuLevel = 1: level 0 pages → records level 1, level 1 pages → records level 1
            if menu_level == 0:
                # Level 0 pages search in records level 0, level 1 pages search in records level 1
                records_level = page_level
            elif menu_level == 1:
                # Level 0 pages search in records level 1
                # Level 1 pages also search in records level 1 (not level 2)
                if page_level == 0:
                    records_level = 1
                elif page_level == 1:
                    records_level = 1  # Level 1 pages search in level 1 records when menuLevel = 1
                else:
                    # For level 2+ pages, search in records with level = page_level
                    records_level = page_level
            else:
                # Default: use page_level as records_level
                records_level = page_level
                logging.warning(f"Unknown menuLevel {menu_level}, using default mapping")
            
            logging.info(f"Page '{page.get('page_name')}' (level {page_level}) → searching in records level {records_level}")
            process_page(page, page_level, records_level, None)  # Top-level pages have no parent
        
        # 6. Save all matched records to a single JSON file
        if all_matched_records:
            output_filename = f"{file_prefix}_matched_records.json"
            output_filepath = os.path.join(UPLOAD_FOLDER, output_filename)
            
            matched_records_data = {
                "total_matched": len(all_matched_records),
                "menuLevel": menu_level,
                "component_id": component_id,
                "matched_records": all_matched_records
            }
            
            with open(output_filepath, 'w', encoding='utf-8') as f:
                json.dump(matched_records_data, f, indent=4, ensure_ascii=False)
            
            logging.info(f"[SUCCESS] Saved {len(all_matched_records)} matched records to {output_filename}")
        else:
            logging.warning("No matched records found to save")
        
        # 7. Save updated menu_navigation.json with matchFound status
        with open(menu_nav_file, 'w', encoding='utf-8') as f:
            json.dump(menu_nav_data, f, indent=4, ensure_ascii=False)
        
        logging.info(f"[SUCCESS] Updated menu_navigation.json with matchFound status")
        logging.info("END: Mapping Pages to Records Complete")
        logging.info("========================================================")
        return True
        
    except FileNotFoundError as e:
        logging.error(f"File not found: {e}")
        return False
    except json.JSONDecodeError as e:
        logging.error(f"JSON decode error: {e}")
        return False
    except Exception as e:
        logging.error(f"Error mapping pages to records: {e}")
        logging.exception("Full traceback:")
        return False


def call_update_miblock_records_api(api_base_url: str, api_headers: Dict[str, str], records: List[Dict[str, Any]], file_prefix: str, payload_filename: str) -> Dict[str, int]:
    """
    Updates existing records in CMS using their actual record IDs.
    Uses bulk processing for better performance.
    """
    logging.info(f"Calling API to UPDATE {len(records)} existing records using bulk processing...")
    
    payload_filepath = os.path.join(UPLOAD_FOLDER, payload_filename)
    
    # Prepare all records for bulk API call
    records_payload_list = []
    record_index_map = {}  # Map index to record for response mapping
    
    for idx, record in enumerate(records):
        page_name = record.get("matched_page_name", f"Record {idx}")
        record_id = record.get("recordId", 0)
        
        api_record = {
            "componentId": record["componentId"],
            "recordId": record["recordId"],
            "parentRecordId": record["parentRecordId"],
            "recordDataJson": record["recordDataJson"],
            "status": record["status"],
            "tags": record["tags"],
            "displayOrder": record["displayOrder"],
            "updatedBy": record["updatedBy"]
        }
        
        records_payload_list.append(api_record)
        record_index_map[idx] = {
            "record": record,
            "page_name": page_name,
            "original_record_id": record_id
        }
    
    # Use bulk API to process all records in parallel
    logging.info(f"[BULK] Processing {len(records_payload_list)} menu records in bulk...")
    resp_success, resp_data = addUpdateRecordsToCMS_bulk(api_base_url, api_headers, records_payload_list)
    
    updated_records = {}
    
    if resp_success and isinstance(resp_data, dict):
        # Map responses back to records
        for idx, record_info in record_index_map.items():
            record = record_info["record"]
            page_name = record_info["page_name"]
            original_record_id = record_info["original_record_id"]
            
            # Get the new record ID from response (using original recordId as key, or index)
            result_id = resp_data.get(original_record_id) or resp_data.get(idx) or resp_data.get(str(idx))
            
            if result_id:
                updated_records[page_name] = result_id
                record["updated_recordId"] = result_id
                logging.debug(f"    [SUCCESS] Updated '{page_name}'. Result ID: {result_id}")
            else:
                logging.warning(f"    [WARNING] No result ID returned for '{page_name}' (recordId={original_record_id})")
    else:
        logging.error(f"[BULK] Failed to process menu records in bulk: {resp_data}")
        # Fallback to individual processing if bulk fails
        logging.warning(f"[FALLBACK] Attempting individual record processing...")
        api_url = f"{api_base_url}/ccadmin/cms/api/PageApi/SaveMiblockRecord?isDraft=false"
        
        for idx, record_info in record_index_map.items():
            record = record_info["record"]
            page_name = record_info["page_name"]
            original_record_id = record_info["original_record_id"]
            api_record = records_payload_list[idx]
            
            try:
                logging.info(f"  [UPDATE {idx+1}/{len(records)}] '{page_name}' (recordId={original_record_id})")
                response = requests.post(api_url, headers=api_headers, json=api_record, timeout=30)
                response.raise_for_status()
                
                result = response.json()
                result_id = result.get("result")
                
                if result_id:
                    updated_records[page_name] = result_id
                    record["updated_recordId"] = result_id
                    logging.info(f"    [SUCCESS] Updated. Result ID: {result_id}")
                else:
                    logging.warning(f"    [WARNING] No result ID returned: {result}")
            except Exception as e:
                logging.error(f"    [ERROR] Failed to update '{page_name}': {e}")
    
    # Save updated payload
    with open(payload_filepath, 'r', encoding='utf-8') as f:
        payload_data = json.load(f)
    
    for rec in payload_data.get("records", []):
        rec_page = rec.get("matched_page_name")
        if rec_page in updated_records:
            rec["updated_recordId"] = updated_records[rec_page]
    
    with open(payload_filepath, 'w', encoding='utf-8') as f:
        json.dump(payload_data, f, indent=4, ensure_ascii=False)
    
    logging.info(f"[SUCCESS] Successfully updated {len(updated_records)}/{len(records)} records in CMS")
    return updated_records


def call_save_miblock_records_api(api_base_url: str, api_headers: Dict[str, str], records: List[Dict[str, Any]], file_prefix: str, payload_filename: str) -> Dict[str, int]:
    """
    Saves records level by level, updating payload file after each parent is saved.
    """
    logging.info(f"Calling API to save {len(records)} records in sequential order...")
    
    api_url = f"{api_base_url}/ccadmin/cms/api/PageApi/SaveMiblockRecord?isDraft=false"
    payload_filepath = os.path.join(UPLOAD_FOLDER, payload_filename)
    
    # Group records by parent-child
    # IMPORTANT: Maintain order from simplified.json - only sort by level, then preserve original order within each level
    # Sort by level first to ensure parents come before children, but maintain displayOrder within each level
    records_sorted = sorted(records, key=lambda r: (
        r.get("level") or r.get("matched_page_level", 0),  # Primary: level
        r.get("displayOrder", 999)  # Secondary: displayOrder to maintain menu sequence
    ))
    
    parent_child_groups = {}
    record_order = []
    
    # First pass: Identify all level 1 records (parents)
    level_1_count = 0
    level_2_plus_count = 0
    
    for r in records_sorted:
        rec_level = r.get("level") or r.get("matched_page_level", 0)
        page_name = r.get("page_name") or r.get("matched_page_name", "")
        
        if rec_level == 1:
            level_1_count += 1
            if page_name not in parent_child_groups:
                parent_child_groups[page_name] = {"parent": r, "children": []}
                record_order.append(page_name)
                logging.debug(f"Created parent group for level 1: '{page_name}'")
        elif rec_level >= 2:
            level_2_plus_count += 1
    
    logging.info(f"Found {level_1_count} level 1 records and {level_2_plus_count} level 2+ records")
    
    # Second pass: Add level 2+ records to their parent groups
    # Also handle orphaned children (parent is matched, so not in new_records)
    orphaned_children = []
    
    for r in records_sorted:
        rec_level = r.get("level") or r.get("matched_page_level", 0)
        page_name = r.get("page_name") or r.get("matched_page_name", "")
        parent_name = r.get("parent_page_name")
        
        if rec_level >= 2:
            if not parent_name:
                logging.warning(f"Level {rec_level} record '{page_name}' has no parent_page_name - skipping grouping")
                continue
            
            if parent_name in parent_child_groups:
                parent_child_groups[parent_name]["children"].append(r)
                # Sort children by displayOrder to maintain sequence from simplified.json
                parent_child_groups[parent_name]["children"].sort(key=lambda c: c.get("displayOrder", 999))
                logging.info(f"[SUCCESS] Added level {rec_level} record '{page_name}' to parent group '{parent_name}' (displayOrder: {r.get('displayOrder', 0)})")
            else:
                # Parent is matched (not in new_records), child needs to be saved separately
                # We'll need to get the parent's record ID from matched_records
                orphaned_children.append(r)
                logging.info(f"[WARNING] Level {rec_level} record '{page_name}' has matched parent '{parent_name}' - will save as orphaned child")
    
    # Save orphaned children (children whose parents are matched)
    if orphaned_children:
        logging.info(f"Found {len(orphaned_children)} orphaned children (parents are matched)")
        # Read matched_records to get parent IDs
        matched_records_file = os.path.join(UPLOAD_FOLDER, f"{file_prefix}_matched_records.json")
        parent_id_map = {}
        
        if os.path.exists(matched_records_file):
            with open(matched_records_file, 'r', encoding='utf-8') as f:
                matched_data = json.load(f)
            
            for matched_rec in matched_data.get("matched_records", []):
                matched_page_name = matched_rec.get("matched_page_name", "")
                matched_record_id = matched_rec.get("Id")
                if matched_page_name and matched_record_id:
                    parent_id_map[matched_page_name] = matched_record_id
        
        # Save orphaned children with their matched parent IDs
        for orphan in orphaned_children:
            orphan_name = orphan.get("page_name") or orphan.get("matched_page_name", "")
            orphan_parent_name = orphan.get("parent_page_name")
            
            if orphan_parent_name in parent_id_map:
                orphan["parentRecordId"] = parent_id_map[orphan_parent_name]
                logging.info(f"Setting parentRecordId for '{orphan_name}' to matched parent ID: {parent_id_map[orphan_parent_name]}")
            
            # Save orphaned child directly
            orphan_api_record = {
                "componentId": orphan["componentId"],
                "recordId": orphan["recordId"],
                "parentRecordId": orphan["parentRecordId"],
                "recordDataJson": orphan["recordDataJson"],
                "status": orphan["status"],
                "tags": orphan["tags"],
                "displayOrder": orphan["displayOrder"],
                "updatedBy": orphan["updatedBy"]
            }
            
            try:
                logging.info(f"  [Orphaned Child] Saving '{orphan_name}' (parent={orphan['parentRecordId']})")
                orphan_resp = requests.post(api_url, headers=api_headers, json=orphan_api_record, timeout=30)
                orphan_resp.raise_for_status()
                
                orphan_result = orphan_resp.json()
                new_orphan_id = orphan_result.get("result")
                
                if new_orphan_id:
                    saved_records[orphan_name] = new_orphan_id
                    orphan["new_recordId"] = new_orphan_id
                    logging.info(f"    [SUCCESS] Orphaned Child ID: {new_orphan_id}")
                    
                    # Update file
                    with open(payload_filepath, 'r', encoding='utf-8') as f:
                        payload_data = json.load(f)
                    
                    for file_rec in payload_data.get("records", []):
                        file_page = file_rec.get("page_name") or file_rec.get("matched_page_name")
                        if file_page == orphan_name:
                            file_rec["new_recordId"] = new_orphan_id
                            file_rec["parentRecordId"] = orphan["parentRecordId"]
                    
                    with open(payload_filepath, 'w', encoding='utf-8') as f:
                        json.dump(payload_data, f, indent=4, ensure_ascii=False)
                else:
                    logging.error(f"    [ERROR] No result ID for orphaned child")
            except Exception as e:
                logging.error(f"    [ERROR] Failed to save orphaned child '{orphan_name}': {e}")
    
    logging.info(f"Grouped into {len(parent_child_groups)} parent-child groups")
    total_children = sum(len(group["children"]) for group in parent_child_groups.values())
    logging.info(f"Total children records: {total_children}")
    
    saved_records = {}
    
    # Process each group: parent → children (sequential, preserves hierarchy)
    for group_idx, group_name in enumerate(record_order):
        group = parent_child_groups[group_name]
        parent_rec = group["parent"]
        children = group["children"]
        
        if not parent_rec:
            logging.warning(f"Group {group_idx+1} '{group_name}' has no parent, skipping")
            continue
        
        logging.info(f"\n[Group {group_idx+1}/{len(record_order)}] '{group_name}': 1 parent + {len(children)} children")
        
        # STEP 1: Save parent
        api_record = {
            "componentId": parent_rec["componentId"],
            "recordId": parent_rec["recordId"],
            "parentRecordId": parent_rec["parentRecordId"],
            "recordDataJson": parent_rec["recordDataJson"],
            "status": parent_rec["status"],
            "tags": parent_rec["tags"],
            "displayOrder": parent_rec["displayOrder"],
            "updatedBy": parent_rec["updatedBy"]
        }
        
        try:
            logging.info(f"  [Parent] Saving '{group_name}'")
            response = requests.post(api_url, headers=api_headers, json=api_record, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            new_parent_id = result.get("result")
            
            if not new_parent_id:
                logging.error(f"    [ERROR] No result ID")
                continue
            
            saved_records[group_name] = new_parent_id
            parent_rec["new_recordId"] = new_parent_id
            logging.info(f"    [SUCCESS] Parent ID: {new_parent_id}")
            
            # STEP 2: Update children parentRecordId immediately
            for child in children:
                child["parentRecordId"] = new_parent_id
            
            # STEP 3: Update file
            with open(payload_filepath, 'r', encoding='utf-8') as f:
                payload_data = json.load(f)
            
            for file_rec in payload_data.get("records", []):
                file_page = file_rec.get("page_name") or file_rec.get("matched_page_name")
                if file_page == group_name:
                    file_rec["new_recordId"] = new_parent_id
                file_parent = file_rec.get("parent_page_name")
                if file_parent == group_name:
                    file_rec["parentRecordId"] = new_parent_id
            
            with open(payload_filepath, 'w', encoding='utf-8') as f:
                json.dump(payload_data, f, indent=4, ensure_ascii=False)
            
            logging.info(f"    → Updated {len(children)} children parentRecordId → {new_parent_id}")
            
            # STEP 4: Save children
            for child_idx, child in enumerate(children):
                child_name = child.get("page_name") or child.get("matched_page_name")
                
                child_api_record = {
                    "componentId": child["componentId"],
                    "recordId": child["recordId"],
                    "parentRecordId": child["parentRecordId"],
                    "recordDataJson": child["recordDataJson"],
                    "status": child["status"],
                    "tags": child["tags"],
                    "displayOrder": child["displayOrder"],
                    "updatedBy": child["updatedBy"]
                }
                
                try:
                    logging.info(f"  [Child {child_idx+1}] Saving '{child_name}' (parent={child['parentRecordId']})")
                    child_resp = requests.post(api_url, headers=api_headers, json=child_api_record, timeout=30)
                    child_resp.raise_for_status()
                    
                    child_result = child_resp.json()
                    new_child_id = child_result.get("result")
                    
                    if new_child_id:
                        saved_records[child_name] = new_child_id
                        child["new_recordId"] = new_child_id
                        logging.info(f"    [SUCCESS] Child ID: {new_child_id}")
                        
                        # Update file
                        with open(payload_filepath, 'r', encoding='utf-8') as f:
                            payload_data = json.load(f)
                        
                        for file_rec in payload_data.get("records", []):
                            file_page = file_rec.get("page_name") or file_rec.get("matched_page_name")
                            if file_page == child_name:
                                file_rec["new_recordId"] = new_child_id
                        
                        with open(payload_filepath, 'w', encoding='utf-8') as f:
                            json.dump(payload_data, f, indent=4, ensure_ascii=False)
                    else:
                        logging.error(f"    [ERROR] No result ID")
                except Exception as e:
                    logging.error(f"    [ERROR] Failed to save child '{child_name}': {e}")
        
        except Exception as e:
            logging.error(f"  [ERROR] Failed to save parent '{group_name}': {e}")
    
    logging.info(f"\n[SUCCESS] Successfully saved all {len(saved_records)} records to CMS")
    logging.info(f"[SUCCESS] Payload file continuously updated: {payload_filename}")
    
    return saved_records


def create_new_records_payload(file_prefix: str, component_id: int, site_id: int, api_base_url: str = None, api_headers: Dict[str, str] = None) -> bool:
    """
    Creates payloads for creating new records from menu_navigation.json where matchFound=False.
    """
    logging.info("========================================================")
    logging.info("START: Creating New Records Payload (Unmatched Pages)")
    logging.info("========================================================")
    
    try:
        menu_nav_file = os.path.join(UPLOAD_FOLDER, f"{file_prefix}_menu_navigation.json")
        if not os.path.exists(menu_nav_file):
            logging.error(f"Menu navigation file not found: {menu_nav_file}")
            return False
        
        with open(menu_nav_file, 'r', encoding='utf-8') as f:
            menu_nav_data = json.load(f)
        
        # Get menuLevel to adjust component mapping
        menu_level = menu_nav_data.get("menuLevel", 1)
        logging.info(f"Menu Level from navigation: {menu_level}")
        
        # Read MiBlockComponentRecords.json to get ComponentId mapping
        records_folder = os.path.join("output", str(site_id), f"mi-block-ID-{component_id}")
        records_file = os.path.join(records_folder, "MiBlockComponentRecords.json")
        
        main_parent_component_id = component_id
        level_1_component_id = component_id
        level_2_component_id = component_id
        parent_record_id_for_level_1 = 0  # Id of level 0 record
        parent_record_id_for_level_2 = 0  # Id of level 1 record
        
        if os.path.exists(records_file):
            with open(records_file, 'r', encoding='utf-8') as f:
                records_data = json.load(f)
            
            component_records = records_data.get("componentRecords", [])
            
            # Find the ORIGINAL level 0 record (ComponentId=542061, ParentId=0)
            # Don't rely on computed level field, use ComponentId and ParentId
            level_0_found = False
            for record in component_records:
                rec_component_id = record.get("ComponentId")
                rec_parent_id = record.get("ParentId")
                rec_id = record.get("Id")
                
                # The container record has ComponentId=542061 and ParentId=0
                if rec_component_id == component_id and rec_parent_id == 0:
                    main_parent_component_id = rec_component_id
                    parent_record_id_for_level_1 = rec_id if rec_id else 0
                    level_0_found = True
                    logging.info(f"Found level 0 container record: Id={rec_id}, ComponentId={rec_component_id}")
                    break
            
            if not level_0_found:
                logging.warning(f"No level 0 record found (ComponentId={component_id}, ParentId=0)")
            
            # Find child components
            child_components = set()
            for record in component_records:
                rec_component_id = record.get("ComponentId")
                rec_main_parent = record.get("MainParentComponentId")
                
                if rec_component_id and rec_main_parent and rec_component_id != rec_main_parent:
                    child_components.add(rec_component_id)
            
            child_components_list = sorted(list(child_components))
            logging.info(f"Found {len(child_components_list)} child components: {child_components_list}")
            
            if len(child_components_list) >= 1:
                level_1_component_id = child_components_list[0]  # 542062 for level 1
            else:
                logging.warning(f"No child components found, using main parent for level 1")
                level_1_component_id = main_parent_component_id
            
            if len(child_components_list) >= 2:
                level_2_component_id = child_components_list[1]  # 542063 for level 2
            elif len(child_components_list) >= 1:
                level_2_component_id = child_components_list[0]  # Fallback if only 1 child
            else:
                level_2_component_id = main_parent_component_id
            
            # Get ParentId for level 2 from any record with level_1_component_id
            for record in component_records:
                if record.get("ComponentId") == level_1_component_id:
                    parent_record_id_for_level_2 = record.get("ParentId", 0)
                    break
            
            logging.info(f"Level 0 (Container): ComponentId={main_parent_component_id}, RecordId={parent_record_id_for_level_1}")
            logging.info(f"Level 1: ComponentId={level_1_component_id}, ParentId={parent_record_id_for_level_1}")
            logging.info(f"Level 2: ComponentId={level_2_component_id}, ParentId={parent_record_id_for_level_2}")
        else:
            logging.warning(f"Records file not found: {records_file}. Using main component_id for all levels.")
        
        # Read MiBlockComponentConfig.json to get property alias names for each component level
        config_file = os.path.join(records_folder, "MiBlockComponentConfig.json")
        component_property_aliases = {}  # ComponentId -> {name_key, link_key}
        
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            definitions = config_data.get("componentDefinition", [])
            logging.info(f"Found {len(definitions)} componentDefinitions in config")
            
            for definition in definitions:
                comp_id = definition.get("ComponentId")
                property_alias = definition.get("PropertyAliasName", "")
                
                if comp_id and property_alias:
                    if comp_id not in component_property_aliases:
                        component_property_aliases[comp_id] = {}
                    
                    # Look for properties ending with -name or -link
                    # Match any property ending with -name (menu-item-name, sub-navigation-item-name, etc.)
                    if property_alias.endswith("-name"):
                        component_property_aliases[comp_id]["name_key"] = property_alias
                        logging.debug(f"Found name key for ComponentId {comp_id}: {property_alias}")
                    # Match any property ending with -link (menu-item-link, sub-navigation-item-link, etc.)
                    elif property_alias.endswith("-link"):
                        component_property_aliases[comp_id]["link_key"] = property_alias
                        logging.debug(f"Found link key for ComponentId {comp_id}: {property_alias}")
            
            logging.info(f"Property aliases mapping by ComponentId: {component_property_aliases}")
        else:
            logging.warning(f"Config file not found: {config_file}. Using default property names.")
        
        # Read matched_records.json to get page_name -> record Id mapping
        matched_records_file = os.path.join(UPLOAD_FOLDER, f"{file_prefix}_matched_records.json")
        page_name_to_record_id = {}
        
        if os.path.exists(matched_records_file):
            with open(matched_records_file, 'r', encoding='utf-8') as f:
                matched_data = json.load(f)
            
            matched_records = matched_data.get("matched_records", [])
            for record in matched_records:
                matched_page_name = record.get("matched_page_name", "")
                record_id = record.get("Id")
                if matched_page_name and record_id:
                    page_name_to_record_id[matched_page_name] = record_id
            
            logging.info(f"Found {len(page_name_to_record_id)} matched pages for parent record lookup")
        
        new_records = []
        
        def collect_unmatched(page_node, parent_page_name=None, display_order=0, parent_record_id_override=None):
            page_name = page_node.get("page_name", "")
            level = page_node.get("level", 0)
            is_matched = page_node.get("matchFound", False)
            
            if not is_matched:
                # Determine ComponentId based on level
                if menu_level == 0:
                    if level == 0:
                        record_component_id = main_parent_component_id
                    elif level == 1:
                        record_component_id = level_1_component_id
                    else:
                        record_component_id = level_2_component_id
                elif menu_level == 1:
                    if level == 1:
                        record_component_id = level_1_component_id
                    else:
                        record_component_id = level_2_component_id
                else:
                    record_component_id = level_1_component_id if level <= 1 else level_2_component_id
                
                # Set parentRecordId - Only for level 1, level 2 will be 0 (updated after level 1 is saved)
                if level == 1:
                    parent_record_id = parent_record_id_for_level_1
                else:
                    parent_record_id = 0  # Will be updated after parent is saved
                
                # Get property aliases for this component
                property_aliases = component_property_aliases.get(record_component_id, {})
                
                # Debug logging
                if not property_aliases:
                    logging.warning(f"No property aliases found for ComponentId {record_component_id}. Available ComponentIds: {list(component_property_aliases.keys())}")
                
                # Get the actual property alias names from config, with fallback
                if "name_key" in property_aliases and "link_key" in property_aliases:
                    name_key = property_aliases["name_key"]
                    link_key = property_aliases["link_key"]
                    logging.debug(f"Using config keys for ComponentId {record_component_id}: name='{name_key}', link='{link_key}'")
                else:
                    # Fallback: use default naming pattern
                    name_key = f"{page_name.lower().replace(' ', '-')}-name"
                    link_key = f"{page_name.lower().replace(' ', '-')}-link"
                    logging.warning(f"Using fallback keys for ComponentId {record_component_id}: name='{name_key}', link='{link_key}'")
                
                # Format the name value - just the page name for all levels
                name_value = page_name
                
                # Generate link value
                page_slug = page_name.lower().replace(' ', '-').replace('&', 'and')
                if level == 1:
                    link_value = f"%%strpath%%{page_slug}"
                else:
                    # Level 2+: include parent in path
                    if parent_page_name:
                        parent_slug = parent_page_name.lower().replace(' ', '-').replace('&', 'and')
                        link_value = f"%%strpath%%{parent_slug}/{page_slug}"
                    else:
                        link_value = f"%%strpath%%{page_slug}"
                
                record_data = {
                    "Id": "##Id##",
                    "ParentId": "##ParentId##",
                    name_key: name_value,
                    link_key: link_value
                }
                
                # Determine parentComponentId based on level
                if level == 1:
                    parent_component_id = main_parent_component_id  # Level 1 parent is main container
                else:
                    parent_component_id = level_1_component_id  # Level 2 parent is level 1 component
                
                # Get page status from page_node (based on ShowInNavigation: Yes/No)
                # Default to True if not specified
                page_status = page_node.get("page_status", True)
                logging.debug(f"Page '{page_name}' status: {page_status}")
                
                new_record = {
                    "componentId": record_component_id,
                    "recordId": 0,
                    "parentRecordId": parent_record_id,
                    "parentComponentId": parent_component_id,
                    "recordDataJson": json.dumps(record_data),
                    "status": page_status,  # Use page_status from ShowInNavigation
                    "tags": [],
                    "displayOrder": display_order,
                    "updatedBy": 0,
                    "page_name": page_name,
                    "parent_page_name": parent_page_name,
                    "level": level
                }
                new_records.append(new_record)
            
            # Process sub_pages - pass parent info even if parent is matched
            current_page_name = page_node.get("page_name", "")
            
            # If current page is matched, get its record ID for sub-pages
            parent_override = None
            if is_matched and current_page_name in page_name_to_record_id:
                parent_override = page_name_to_record_id[current_page_name]
                logging.debug(f"Parent '{current_page_name}' is matched (Id={parent_override}), will use for sub-pages")
            
            for idx, sub_page in enumerate(page_node.get("sub_pages", [])):
                collect_unmatched(sub_page, current_page_name, idx, parent_override)
        
        for idx, page in enumerate(menu_nav_data.get("pages", [])):
            collect_unmatched(page, None, idx)
        
        if new_records:
            output_filename = f"{file_prefix}_new_records_payload.json"
            output_filepath = os.path.join(UPLOAD_FOLDER, output_filename)
            
            payload = {
                "componentId": component_id,
                "siteId": site_id,
                "total_records": len(new_records),
                "records": new_records
            }
            
            with open(output_filepath, 'w', encoding='utf-8') as f:
                json.dump(payload, f, indent=4, ensure_ascii=False)
            
            logging.info(f"[SUCCESS] Created new records payload: {output_filename} ({len(new_records)} records)")
            
            # Call API to save records if api_base_url and api_headers provided
            if api_base_url and api_headers:
                logging.info("Calling API to save new records to CMS...")
                call_save_miblock_records_api(api_base_url, api_headers, new_records, file_prefix, output_filename)
            else:
                logging.warning("API credentials not provided, skipping API call")
            
            return True
        else:
            logging.info("No unmatched records to create")
            return False
    
    except Exception as e:
        logging.error(f"Error creating new records payload: {e}")
        logging.exception("Full traceback:")
        return False


def create_save_miblock_records_payload(file_prefix: str, component_id: int, site_id: int, api_base_url: str = None, api_headers: Dict[str, str] = None) -> bool:
    """
    Creates payloads for UPDATING existing matched records in CMS.
    Uses actual record IDs for update operation.
    
    Args:
        file_prefix: The file prefix for matched_records.json
        component_id: The component ID to use in the payload
        site_id: The site ID (for logging)
        api_base_url: API base URL for calling update API
        api_headers: Headers for authentication
        
    Returns:
        bool: True if successful, False otherwise
    """
    logging.info("========================================================")
    logging.info("START: Creating SaveMiBlockRecords Payload (UPDATE Matched)")
    logging.info("========================================================")
    
    try:
        # 1. Read matched_records.json
        matched_records_file = os.path.join(UPLOAD_FOLDER, f"{file_prefix}_matched_records.json")
        if not os.path.exists(matched_records_file):
            logging.error(f"Matched records file not found: {matched_records_file}")
            logging.info("Skipping matched records update")
            return False
        
        with open(matched_records_file, 'r', encoding='utf-8') as f:
            matched_data = json.load(f)
        
        matched_records = matched_data.get("matched_records", [])
        if not matched_records:
            logging.warning("No matched records found to create payload")
            return False
        
        # 2. Read ComponentId mapping and property aliases
        records_folder = os.path.join("output", str(site_id), f"mi-block-ID-{component_id}")
        config_file = os.path.join(records_folder, "MiBlockComponentConfig.json")
        records_file = os.path.join(records_folder, "MiBlockComponentRecords.json")
        
        # Get correct ComponentIds for each level
        level_1_component_id = component_id
        level_2_component_id = component_id
        
        if os.path.exists(records_file):
            with open(records_file, 'r', encoding='utf-8') as f:
                records_data = json.load(f)
            
            component_records = records_data.get("componentRecords", [])
            
            # Find container
            for record in component_records:
                if record.get("ComponentId") == component_id and record.get("ParentId") == 0:
                    main_parent_component_id = component_id
                    break
            
            # Find child components
            child_components = set()
            for record in component_records:
                rec_component_id = record.get("ComponentId")
                rec_main_parent = record.get("MainParentComponentId")
                
                if rec_component_id and rec_main_parent and rec_component_id != rec_main_parent:
                    child_components.add(rec_component_id)
            
            child_components_list = sorted(list(child_components))
            logging.info(f"Found {len(child_components_list)} child components: {child_components_list}")
            
            if len(child_components_list) >= 1:
                level_1_component_id = child_components_list[0]  # 542062 for level 1
            else:
                logging.warning(f"No child components found, using main parent for level 1")
                level_1_component_id = main_parent_component_id
            
            if len(child_components_list) >= 2:
                level_2_component_id = child_components_list[1]  # 542063 for level 2
            elif len(child_components_list) >= 1:
                level_2_component_id = child_components_list[0]
            else:
                level_2_component_id = main_parent_component_id
        
        component_property_aliases = {}
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            definitions = config_data.get("componentDefinition", [])
            for definition in definitions:
                comp_id = definition.get("ComponentId")
                property_alias = definition.get("PropertyAliasName", "")
                
                if comp_id and property_alias:
                    if comp_id not in component_property_aliases:
                        component_property_aliases[comp_id] = {}
                    
                    if property_alias.endswith("-name"):
                        component_property_aliases[comp_id]["name_key"] = property_alias
                    elif property_alias.endswith("-link"):
                        component_property_aliases[comp_id]["link_key"] = property_alias
        
        logging.info(f"Matched records: Main={main_parent_component_id}, Level 1 ComponentId={level_1_component_id}, Level 2 ComponentId={level_2_component_id}")
        
        # 3. Transform records into API payload format
        api_payloads = []
        
        # Get level 0 container record Id for level 1 parentRecordId
        level_0_record_id = 0
        if os.path.exists(records_file):
            with open(records_file, 'r', encoding='utf-8') as f:
                all_records_data = json.load(f)
            
            all_component_records = all_records_data.get("componentRecords", [])
            for rec in all_component_records:
                if rec.get("ComponentId") == component_id and rec.get("ParentId") == 0:
                    level_0_record_id = rec.get("Id", 0)
                    logging.info(f"Found level 0 container record Id: {level_0_record_id}")
                    break
        
        for record in matched_records:
            # Extract required fields
            original_record_id = record.get("Id", 0)
            original_parent_id = record.get("ParentId", 0)
            record_json_string = record.get("RecordJsonString", "")
            
            # Get status from page_status (from ShowInNavigation) if available, otherwise use existing Status
            page_status = record.get("page_status")
            if page_status is not None:
                status = page_status
                logging.debug(f"Using page_status from ShowInNavigation for '{record.get('matched_page_name')}': {status}")
            else:
                status = record.get("Status", True)
                logging.debug(f"Using existing Status for '{record.get('matched_page_name')}': {status}")
            
            display_order = record.get("DisplayOrder", 0)
            updated_by = record.get("UpdatedBy", 0)
            matched_page_level = record.get("matched_page_level", 1)
            matched_page_name = record.get("matched_page_name", "")
            original_component_id = record.get("ComponentId")
            
            # Determine correct ComponentId and ParentId based on level
            if matched_page_level == 1:
                correct_component_id = level_1_component_id
                correct_parent_id = level_0_record_id  # Level 1 parent is level 0 container
            else:  # level 2+
                correct_component_id = level_2_component_id
                correct_parent_id = 0  # Will be updated after level 1 is saved
            
            # Get tags if available
            tags = record.get("tags", [])
            if not isinstance(tags, list):
                tags = []
            
            # Fix keys in recordDataJson based on correct ComponentId
            try:
                record_data = json.loads(record_json_string)
                
                # Get correct property aliases for the CORRECTED ComponentId
                correct_aliases = component_property_aliases.get(correct_component_id, {})
                correct_name_key = correct_aliases.get("name_key")
                correct_link_key = correct_aliases.get("link_key")
                
                # Find current keys and values
                name_value = None
                link_value = None
                keys_to_remove = []
                
                for key, value in record_data.items():
                    if key.endswith("-name") and key not in ["Id", "ParentId"]:
                        keys_to_remove.append(key)
                        name_value = value
                    elif key.endswith("-link"):
                        keys_to_remove.append(key)
                        link_value = value
                
                # Remove all old keys
                for key in keys_to_remove:
                    del record_data[key]
                
                # Add correct keys
                if correct_name_key and name_value:
                    record_data[correct_name_key] = name_value
                    logging.debug(f"Set key: {correct_name_key} = {name_value}")
                
                if correct_link_key and link_value:
                    record_data[correct_link_key] = link_value
                    logging.debug(f"Set key: {correct_link_key} = {link_value}")
                
                record_json_string = json.dumps(record_data, ensure_ascii=False)
            except Exception as e:
                logging.warning(f"Error fixing keys in record {original_record_id}: {e}")
            
            # Determine parentComponentId based on level
            if matched_page_level == 1:
                parent_component_id = main_parent_component_id  # Level 1 parent is main container
            else:
                parent_component_id = level_1_component_id  # Level 2 parent is level 1 component
            
            # Create API payload record for UPDATE
            api_record = {
                "componentId": correct_component_id,  # Use corrected ComponentId
                "recordId": original_record_id,  # Use actual record ID for UPDATE operation
                "parentRecordId": correct_parent_id,  # Use corrected parentRecordId
                "parentComponentId": parent_component_id,  # Parent component ID based on level
                "recordDataJson": record_json_string,
                "status": status,
                "tags": tags,
                "displayOrder": display_order,
                "updatedBy": updated_by,
                "matched_page_name": matched_page_name,  # Keep for reference
                "matched_page_level": matched_page_level,  # Keep for reference
                "parent_page_name": record.get("parent_page_name")  # Keep for API processing
            }
            
            api_payloads.append(api_record)
        
        # 3. Create final payload with all records
        final_payload = {
            "componentId": component_id,
            "siteId": site_id,
            "total_records": len(api_payloads),
            "records": api_payloads
        }
        
        # 4. Save payload to separate file
        output_filename = f"{file_prefix}_save_miblock_records_payload.json"
        output_filepath = os.path.join(UPLOAD_FOLDER, output_filename)
        
        with open(output_filepath, 'w', encoding='utf-8') as f:
            json.dump(final_payload, f, indent=4, ensure_ascii=False)
        
        logging.info(f"[SUCCESS] Created matched records payload: {output_filename}")
        logging.info(f"   Total matched records in payload: {len(api_payloads)}")
        
        # Call API to UPDATE matched records if credentials provided
        if api_base_url and api_headers:
            logging.info("Calling API to UPDATE matched records in CMS...")
            
            # Sort by level first, then by displayOrder to maintain menu sequence from simplified.json
            api_payloads.sort(key=lambda r: (
                r.get("matched_page_level", 0),  # Primary: level
                r.get("displayOrder", 999)  # Secondary: displayOrder to maintain menu sequence
            ))
            
            # Call update API (uses existing record IDs)
            call_update_miblock_records_api(api_base_url, api_headers, api_payloads, file_prefix, output_filename)
        else:
            logging.warning("API credentials not provided, skipping API call for matched records")
        
        logging.info("END: Creating SaveMiBlockRecords Payload (UPDATE Matched) Complete")
        logging.info("========================================================")
        return True
        
    except FileNotFoundError as e:
        logging.error(f"File not found: {e}")
        return False
    except json.JSONDecodeError as e:
        logging.error(f"JSON decode error: {e}")
        return False
    except Exception as e:
        logging.error(f"Error creating saveMiBlockRecords payload: {e}")
        logging.exception("Full traceback:")
        return False
        
    except FileNotFoundError as e:
        logging.error(f"File not found: {e}")
        return False
    except json.JSONDecodeError as e:
        logging.error(f"JSON decode error: {e}")
        return False
    except Exception as e:
        logging.error(f"Error mapping pages to records: {e}")
        logging.exception("Full traceback:")
        return False


# ================= Pre-download All Components Function =================

def collect_all_component_ids(processed_json: Dict[str, Any], component_cache: List[Dict[str, Any]]) -> List[Tuple[int, str, str]]:
    """
    Collects all unique component IDs that will be needed during assembly.
    Returns a list of tuples: (componentId, component_name, cms_component_name)
    """
    component_ids = set()  # Use set to avoid duplicates
    component_info_list = []
    
    def traverse_pages(page_node: Dict[str, Any]):
        """Recursively traverse all pages to collect component names."""
        components = page_node.get('components', [])
        for component_name in components:
            # Check if component is available in cache
            api_result = check_component_availability(component_name, component_cache)
            if api_result:
                vComponentId, alias, componentId, cms_component_name = api_result
                # Add to set if not already present
                if componentId not in component_ids:
                    component_ids.add(componentId)
                    component_info_list.append((componentId, component_name, cms_component_name))
        
        # Recursively process sub_pages
        for sub_page in page_node.get('sub_pages', []):
            traverse_pages(sub_page)
    
    # Traverse all top-level pages
    pages = processed_json.get('pages', [])
    for page in pages:
        traverse_pages(page)
    
    logging.info(f"Collected {len(component_info_list)} unique components to pre-download")
    return component_info_list


def pre_download_all_components(
    processed_json: Dict[str, Any],
    component_cache: List[Dict[str, Any]],
    api_base_url: str,
    site_id: int,
    api_headers: Dict[str, str]
) -> Dict[int, bool]:
    """
    Pre-downloads all components that will be needed during assembly.
    Downloads all components, then unzips all, then converts all TXT to JSON.
    
    Returns:
        Dict mapping componentId -> success status (True/False)
    """
    logging.info("\n========================================================")
    logging.info("PRE-DOWNLOAD: Collecting all component IDs...")
    logging.info("========================================================")
    
    # Step 1: Collect all component IDs
    component_info_list = collect_all_component_ids(processed_json, component_cache)
    
    if not component_info_list:
        logging.info("No components found to pre-download.")
        return {}
    
    logging.info(f"\nFound {len(component_info_list)} unique components to download:")
    for comp_id, comp_name, cms_name in component_info_list:
        logging.info(f"  - {comp_name} (ID: {comp_id}, CMS: {cms_name})")
    
    # Step 2: Download all components (override if already exists)
    logging.info("\n========================================================")
    logging.info("PRE-DOWNLOAD: Phase 1 - Downloading all components...")
    logging.info("========================================================")
    
    download_results = {}  # componentId -> (success, save_folder)
    output_dir = os.path.join("output", str(site_id))
    
    for idx, (component_id, component_name, cms_component_name) in enumerate(component_info_list, 1):
        mi_block_folder = f"mi-block-ID-{component_id}"
        save_folder = os.path.join(output_dir, mi_block_folder)
        os.makedirs(save_folder, exist_ok=True)
        
        try:
            logging.info(f"[{idx}/{len(component_info_list)}] Downloading component {component_id} ({component_name})...")
            response_content, content_disposition = export_mi_block_component(
                api_base_url, component_id, site_id, api_headers
            )
            
            if response_content:
                os.makedirs(save_folder, exist_ok=True)
                
                filename = (
                    content_disposition.split('filename=')[1].strip('"')
                    if content_disposition and 'filename=' in content_disposition
                    else f"component_{component_id}.zip"
                )
                file_path = os.path.join(save_folder, filename)
                
                # Save zip file
                with open(file_path, "wb") as file:
                    file.write(response_content)
                
                download_results[component_id] = (True, save_folder)
                logging.info(f"  [SUCCESS] Downloaded {component_id} ({len(response_content)} bytes)")
            else:
                download_results[component_id] = (False, save_folder)
                logging.warning(f"  [WARNING] No content returned for component {component_id}")
        except Exception as e:
            download_results[component_id] = (False, save_folder)
            logging.error(f"  [ERROR] Failed to download component {component_id}: {e}")
    
    # Step 3: Unzip all downloaded components
    logging.info("\n========================================================")
    logging.info("PRE-DOWNLOAD: Phase 2 - Unzipping all components...")
    logging.info("========================================================")
    
    for idx, (component_id, component_name, cms_component_name) in enumerate(component_info_list, 1):
        success, save_folder = download_results.get(component_id, (False, None))
        if not success or not save_folder:
            continue
        
        # Find zip file in save_folder
        zip_files = [f for f in os.listdir(save_folder) if f.endswith('.zip')] if os.path.exists(save_folder) else []
        
        for zip_file in zip_files:
            zip_path = os.path.join(save_folder, zip_file)
            try:
                if zipfile.is_zipfile(zip_path):
                    logging.info(f"[{idx}/{len(component_info_list)}] Unzipping {component_id} ({component_name})...")
                    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                        zip_ref.extractall(save_folder)
                    os.remove(zip_path)
                    logging.info(f"  [SUCCESS] Unzipped {component_id}")
                else:
                    logging.warning(f"  [WARNING] {zip_file} is not a valid zip file")
            except Exception as e:
                logging.error(f"  [ERROR] Failed to unzip {component_id}: {e}")
    
    # Give OS time to finish file operations
    time.sleep(2)
    
    # Step 4: Convert all TXT files to JSON
    logging.info("\n========================================================")
    logging.info("PRE-DOWNLOAD: Phase 3 - Converting TXT to JSON...")
    logging.info("========================================================")
    
    total_converted = 0
    for idx, (component_id, component_name, cms_component_name) in enumerate(component_info_list, 1):
        success, save_folder = download_results.get(component_id, (False, None))
        if not success or not save_folder or not os.path.exists(save_folder):
            continue
        
        txt_files = [f for f in os.listdir(save_folder) if f.endswith('.txt')]
        if not txt_files:
            continue
        
        logging.info(f"[{idx}/{len(component_info_list)}] Converting TXT files for {component_id} ({component_name})...")
        converted_count = 0
        
        for txt_file in txt_files:
            txt_path = os.path.join(save_folder, txt_file)
            json_path = os.path.splitext(txt_path)[0] + '.json'
            
            try:
                with open(txt_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    json_content = json.loads(content)
                
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(json_content, f, indent=4)
                
                os.remove(txt_path)
                converted_count += 1
                total_converted += 1
            except Exception as e:
                logging.error(f"  [ERROR] Failed to convert {txt_file} for {component_id}: {e}")
        
        if converted_count > 0:
            logging.info(f"  [SUCCESS] Converted {converted_count} file(s) for {component_id}")
    
    logging.info(f"\n[SUCCESS] Total files converted: {total_converted}")
    
    # Step 5: Add level fields to all MiBlockComponentRecords.json files
    logging.info("\n========================================================")
    logging.info("PRE-DOWNLOAD: Phase 4 - Adding level fields to records...")
    logging.info("========================================================")
    
    for idx, (component_id, component_name, cms_component_name) in enumerate(component_info_list, 1):
        success, save_folder = download_results.get(component_id, (False, None))
        if not success or not save_folder:
            continue
        
        records_file_path = os.path.join(save_folder, "MiBlockComponentRecords.json")
        if os.path.exists(records_file_path):
            try:
                add_levels_to_records(records_file_path)
                logging.info(f"[{idx}/{len(component_info_list)}] [SUCCESS] Added level fields for {component_id}")
            except Exception as e:
                logging.error(f"[{idx}/{len(component_info_list)}] [ERROR] Failed to add levels for {component_id}: {e}")
    
    # Step 6: Verify config files are accessible (quick check, no polling needed after unzip)
    logging.info("\n========================================================")
    logging.info("PRE-DOWNLOAD: Phase 5 - Verifying config files are accessible...")
    logging.info("========================================================")
    
    for idx, (component_id, component_name, cms_component_name) in enumerate(component_info_list, 1):
        success, save_folder = download_results.get(component_id, (False, None))
        if not success or not save_folder:
            continue
        
        config_file_path = os.path.join(save_folder, "MiBlockComponentConfig.json")
        
        # Quick check - files should already be ready after unzip
        if os.path.exists(config_file_path):
            try:
                # Try to open and read a byte to verify accessibility
                with open(config_file_path, 'r') as f:
                    f.read(1)
                logging.info(f"[{idx}/{len(component_info_list)}] [SUCCESS] Config file accessible for {component_id}")
            except IOError as e:
                logging.warning(f"[{idx}/{len(component_info_list)}] [WARNING] Config file locked for {component_id}: {e}")
        else:
            logging.warning(f"[{idx}/{len(component_info_list)}] [WARNING] Config file not found for {component_id}")
    
    # Return success status for each component
    result_status = {comp_id: success for comp_id, (success, _) in download_results.items()}
    
    logging.info("\n========================================================")
    logging.info(f"PRE-DOWNLOAD: Complete! {sum(1 for s in result_status.values() if s)}/{len(result_status)} components ready")
    logging.info("========================================================")
    
    return result_status


# ================= Main Entry Function (Uses Dynamic Config) =================

def run_assembly_processing_step(processed_json: Union[Dict[str, Any], str], *args, **kwargs) -> Dict[str, Any]:
    """
    Main assembly step.

    Responsibilities:
    - Load dynamic configuration and API details for the current file prefix.
    - Load the processed page tree (pages, components, menu info) from previous steps.
    - Pre-download all required components (MiBlocks), unzip, convert TXT→JSON, and add level metadata.
    - Assemble HTML for each page by stitching all component sections plus headers/footers.
    - Create pages in CMS, update page–MiBlock mappings, and queue pages for final publish.
    - At the end, publish all queued pages, write an assembly status CSV, and emit timing statistics.

    Returns:
    - Dict with high-level assembly status, file_prefix, report filename, and timing summary.
    """
    logging.info("========================================================")
    logging.info("Started Assembly")
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
        # --- NEW PARAMETER EXTRACTION ---
        site_id = settings.get("site_id") 

        if not api_base_url or not raw_token or not isinstance(raw_token, str) or not raw_token.strip() or site_id is None:
             raise ValueError("Target URL, valid CMS Login Token, or 'site_id' missing in configuration.")

        api_headers = {
            'Content-Type': 'application/json',
            'ms_cms_clientapp': 'ProgrammingApp',
            'Authorization': f'Bearer {raw_token}', 
        }
        
        logging.info(f"Configuration loaded. API Base URL: {api_base_url}, Destination ID: {site_id}")

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
    append_debug_log(
        "assembly_start",
        {
            "file_prefix": file_prefix,
            "simplified_json_path": file_path,
        },
    )
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
    
    # The import check is removed since it's confirmed to be in apis.py
    try:
        logging.info("[TIMING] Starting GetAllVComponents...")
        cache_start_time = time.time()
        vcomponent_cache = GetAllVComponents(api_base_url, api_headers, page_size=1000)
        cache_time = time.time() - cache_start_time
        logging.info(f"[TIMING] GetAllVComponents completed in {cache_time:.2f} seconds")
        
        # Track timing
        if "GetAllVComponents" not in TIMING_TRACKER:
            TIMING_TRACKER["GetAllVComponents"] = []
        TIMING_TRACKER["GetAllVComponents"].append(cache_time)
    except Exception as e:
        logging.error(f"FATAL: Exception during V-Component list retrieval: {e}")
        logging.exception("Full exception traceback:")
        raise RuntimeError(f"V-Component list retrieval failed. Cannot proceed with assembly. Error: {str(e)}")


    if not isinstance(vcomponent_cache, list):
        error_details = ""
        if isinstance(vcomponent_cache, dict):
            error_details = f" Error details: {json.dumps(vcomponent_cache, indent=2)}"
        elif vcomponent_cache is None:
            error_details = " API returned None"
        logging.error(f"FATAL: Failed to retrieve V-Component list. API returned non-list response: {type(vcomponent_cache)}{error_details}")
        logging.error(f"API Base URL: {api_base_url}")
        logging.error(f"Site ID: {site_id}")
        raise RuntimeError(f"V-Component list retrieval failed. API returned: {vcomponent_cache}. Cannot proceed with assembly.")

    if len(vcomponent_cache) == 0:
        logging.warning("WARNING: V-Component list is empty. This may indicate an API issue or no components available.")

    logging.info(f"Successfully loaded {len(vcomponent_cache)} components into cache for fast lookup.")

    # --- 4.5. PRE-DOWNLOAD ALL COMPONENTS (NEW OPTIMIZATION) ---
    logging.info("\n========================================================")
    logging.info("STEP 4.5: PRE-DOWNLOADING ALL COMPONENTS")
    logging.info("========================================================")
    
    try:
        logging.info("[TIMING] Starting pre_download_all_components...")
        pre_download_start_time = time.time()
        pre_download_results = pre_download_all_components(
            full_payload,
            vcomponent_cache,
            api_base_url,
            site_id,
            api_headers
        )
        pre_download_time = time.time() - pre_download_start_time
        logging.info(f"[TIMING] pre_download_all_components completed in {pre_download_time:.2f} seconds")
        
        # Track timing
        if "pre_download_all_components" not in TIMING_TRACKER:
            TIMING_TRACKER["pre_download_all_components"] = []
        TIMING_TRACKER["pre_download_all_components"].append(pre_download_time)
        
        successful_downloads = sum(1 for success in pre_download_results.values() if success)
        logging.info(f"Pre-download complete: {successful_downloads}/{len(pre_download_results)} components ready")
    except Exception as e:
        logging.error(f"Error during pre-download phase: {e}")
        logging.warning("Continuing with assembly - components will be downloaded on-demand if needed")
        logging.exception("Full traceback:")

    # --- 5. Assembly Execution (PASSES CACHE and NEW PARAMS) ---
    logging.info("[TIMING] Starting assemble_page_templates_level1...")
    assembly_start_time = time.time()
    assemble_page_templates_level1(full_payload, vcomponent_cache, api_base_url, site_id, api_headers)
    assembly_time = time.time() - assembly_start_time
    logging.info(f"[TIMING] assemble_page_templates_level1 completed in {assembly_time:.2f} seconds")
    
    # Track timing
    if "assemble_page_templates_level1" not in TIMING_TRACKER:
        TIMING_TRACKER["assemble_page_templates_level1"] = []
    TIMING_TRACKER["assemble_page_templates_level1"].append(assembly_time)
    
    # Menu navigation is now a separate processing step before this one

    # --- 5.5. FINAL PAGE PUBLISH (DEFERRED) ---
    try:
        logging.info("\n========================================================")
        logging.info("STEP 5.5: PUBLISHING ALL QUEUED PAGES")
        logging.info("========================================================")
        published_count = publish_queued_pages(api_base_url, api_headers, site_id)
        logging.info(f"[PUBLISH] Completed publishing of {published_count} queued pages.")
    except Exception as e:
        logging.error(f"[ERROR] Deferred publish step failed: {e}")
        logging.exception("Full traceback:")

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
        
        logging.info(f"[SUCCESS] Status report successfully saved as CSV to: {status_file_path}")
    except IOError as e:
        logging.error(f"Failed to write CSV status file {status_filename}: {e}")

    # --- 7. Print Timing Summary ---
    timing_summary = []
    if TIMING_TRACKER:
        logging.info("\n" + "="*80)
        logging.info("TIMING SUMMARY - Function Performance Analysis")
        logging.info("="*80)
        
        # Calculate statistics for each function
        for func_name, times in TIMING_TRACKER.items():
            if times:
                total_time = sum(times)
                avg_time = total_time / len(times)
                max_time = max(times)
                min_time = min(times)
                timing_summary.append({
                    "function": func_name,
                    "count": len(times),
                    "total_seconds": total_time,
                    "total_minutes": total_time / 60.0,
                    "average_seconds": avg_time,
                    "average_minutes": avg_time / 60.0,
                    "max_seconds": max_time,
                    "max_minutes": max_time / 60.0,
                    "min_seconds": min_time,
                    "min_minutes": min_time / 60.0
                })
        
        # Sort by total time (descending) to show slowest functions first
        timing_summary.sort(key=lambda x: x["total_seconds"], reverse=True)
        
        logging.info(f"{'Function':<35} {'Count':<8} {'Total (min)':<15} {'Avg (min)':<15} {'Max (min)':<15} {'Min (min)':<15}")
        logging.info("-"*100)
        
        for stat in timing_summary:
            logging.info(f"{stat['function']:<35} {stat['count']:<8} {stat['total_minutes']:<15.2f} {stat['average_minutes']:<15.2f} {stat['max_minutes']:<15.2f} {stat['min_minutes']:<15.2f}")
        
        # Identify the slowest function
        if timing_summary:
            slowest = timing_summary[0]
            logging.info(f"\n[SLOWEST FUNCTION] {slowest['function']}: Total={slowest['total_minutes']:.2f} min ({slowest['total_seconds']:.2f}s), Avg={slowest['average_minutes']:.2f} min, Called {slowest['count']} times")
        
        logging.info("="*80 + "\n")
        
        # Save timing summary to JSON file for easy analysis
        try:
            timing_file = os.path.join(UPLOAD_FOLDER, f"{file_prefix}_timing_summary.json")
            with open(timing_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "file_prefix": file_prefix,
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "timing_summary": timing_summary
                }, f, indent=4, ensure_ascii=False)
            logging.info(f"[SUCCESS] Timing summary saved to: {timing_file}")
        except Exception as e:
            logging.error(f"[ERROR] Failed to save timing summary: {e}")
    
    # --- 8. Prepare Final Output ---
    final_output = {
        "assembly_status": "SUCCESS: Pages and components processed.",
        "file_prefix": file_prefix, 
        "report_filename": status_filename, 
        "timing_summary": timing_summary
    }

    ASSEMBLY_STATUS_LOG.clear() 
    TIMING_TRACKER.clear()  # Clear for next run
    return final_output