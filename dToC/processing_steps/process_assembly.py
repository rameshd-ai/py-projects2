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
from apis import GetAllVComponents, export_mi_block_component,addUpdateRecordsToCMS,generatecontentHtml,GetTemplatePageByName,psMappingApi,psPublishApi,GetPageCategoryList,CustomGetComponentAliasByName
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
#                  logging.info(f"    ✅ Component '{component_name}' found in cache as '{cms_component_name}'.")
#                  # Return the CMS name as the 4th element
#                  return (vComponentId, component_alias, component_id, cms_component_name)
    
#     logging.warning(f"    ❌ Component prefix '{search_key}' not found in the component cache.")
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
                logging.info(f"    ✅ Component '{component_name}' found in cache as '{cms_component_name}'.")
                # Return the CMS name as the 4th element
                return (vComponentId, component_alias, component_id, cms_component_name)
    
    logging.warning(f"    ❌ Component prefix '{search_key}' not found in the component cache.")
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
        unclassified_count = sum(1 for r in component_records if r.get("level") == -1)
        if unclassified_count > 0:
            logging.warning(f"Found {unclassified_count} unclassified records (orphaned or circular references)")
            # Set orphaned records to a high level to avoid breaking the structure
            for record in component_records:
                if record.get("level") == -1:
                    record["level"] = 999
        
        # Save the updated records back to the file
        with open(records_file_path, 'w', encoding='utf-8') as f:
            json.dump(records_data, f, indent=4, ensure_ascii=False)
        
        logging.info(f"✅ Successfully added level fields to {len(component_records)} records")
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
        pageSectionGuid = str(uuid.uuid4()) 

        # Call the API function from apis.py
        response_content, content_disposition = export_mi_block_component(base_url, component_id_unpacked, site_id, headers)
        
        miBlockId = component_id_unpacked
        mi_block_folder = f"mi-block-ID-{miBlockId}"
        # Output directory is relative to the current working directory, not UPLOAD_FOLDER
        output_dir = os.path.join("output", str(site_id)) 
        save_folder = os.path.join(output_dir, mi_block_folder)
        # payload_file_path is defined but not used in the provided logic snippet.
        # payload_file_path = os.path.join(output_dir, "api_response_final.json") 
        os.makedirs(save_folder, exist_ok=True)
        
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
            logging.info("🔄 Starting TXT to JSON conversion...")
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
                        logging.info(f"   ✅ Successfully converted: {extracted_file}")
                    except (json.JSONDecodeError, OSError) as e:
                        # Log the error but continue to the next file
                        logging.error(f"⚠️ Error processing file {extracted_file_path}: {e}")
            
            logging.info(f"✅ TXT to JSON conversion complete: {converted_count}/{len(txt_files_found)} files converted successfully")

            # 3. Add level fields to MiBlockComponentRecords.json
            records_file_path = os.path.join(save_folder, "MiBlockComponentRecords.json")
            if os.path.exists(records_file_path):
                try:
                    add_levels_to_records(records_file_path)
                    logging.info(f"✅ Added level fields to records in {records_file_path}")
                except Exception as e:
                    logging.error(f"⚠️ Error adding levels to records: {e}")

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
            logging.error(f"❌ File Polling Failed: {e}")
            raise # Re-raise the error to halt assembly for this component/page

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






def pageAction(base_url, headers,final_html,page_name,page_template_id,DefaultTitle,DefaultDescription,site_id,category_id,header_footer_details):
    # Prepare payload for page creation
    page_content_bytes = final_html.encode("utf-8")
    base64_encoded_content = base64.b64encode(page_content_bytes).decode("utf-8")
    page_name = page_name + "-Demo"
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

    data = CreatePage(base_url, headers, payload,page_template_id)
    # print(data)

    # Access the 'pageId' key and print its value
    page_id = data.get("PageId")

    if page_id is not None:
        print(f"The Page ID is: {page_id}")
    else:
        print("Error: 'pageId' key not found in the returned data.")


    updatePageMapping(base_url, headers,page_id,site_id,header_footer_details)
    publishPage(base_url, headers,page_id,site_id,header_footer_details)

    
    return data



def updatePageMapping(base_url: str, headers: Dict[str, str], page_id: int, site_id: int, header_footer_details: Dict[str, Any]):
    """
    Creates and sends the page mapping payload using data from all
    ComponentRecordsTree.json files found in the migration output folders, 
    AND the explicit header/footer components.
    """

    
    # --- PHASE 1: COLLECT BODY COMPONENT MAPPING DATA ---
    all_mappings: List[Dict[str, Any]] = []
    
    # Construct the base path to search: output/site_id/mi-block-ID-*
    search_path = os.path.join("output", str(site_id), "mi-block-ID-*", "ComponentRecordsTree.json")
    
    # print(f"🔍 Searching for migration files in: {os.path.join('output', str(site_id), 'mi-block-ID-*')}")
    
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
                    # print(f"  ✅ Extracted mapping for alias: {mapping_data['vComponentAlias']}")
                else:
                    print(f"  ⚠️ Skipping file {os.path.basename(os.path.dirname(file_path))}: Missing 'component_alias' or 'sectionGuid'.")

        except Exception as e:
            print(f"  ❌ Error processing file {file_path}: {e}")

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
            print(f"  ✅ Added {hf_key} mapping for alias: {hf_data.get('alias')}")
        elif hf_data.get("name"):
            print(f"  ⚠️ Skipping {hf_key}: Component name '{hf_data.get('name')}' found, but GUID was missing/API failed during fetch.")


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
    
    # print("\n--- 📑 FINAL API PAYLOAD ---")
    # print(json.dumps(new_api_payload, indent=2))
    # print("-----------------------------")

    try:
        # Call the API to update the page mapping
        api_response_data = psMappingApi(base_url, headers, new_api_payload)
        
        # Check for the specific success string (Your original success logic)
        if api_response_data == "Page Content Mappings updated successfully.":
            print(f"\n🚀 **SUCCESS:** Page mapping updated successfully for Page ID {page_id}.")
            print(f"API Response: {api_response_data}")
            
        else:
            # Handle non-success responses that didn't raise an exception
            print(f"\n🛑 **FAILURE:** Failed to update page mapping for Page ID {page_id}.")
            print(f"API Response: {api_response_data}")

    except Exception as e:
        # This block now uses the correct variable name 'e' for the exception
        # and prints the error message directly.
        print(f"\n❌ **CRITICAL API ERROR:** An exception occurred during the API call: {e}")

    return len(new_api_payload)



def publishPage(base_url: str, headers: Dict[str, str], page_id: int, site_id: int, header_footer_details: Dict[str, Any]):
    """
    Constructs the necessary payload to publish all migrated components (MiBlocks, 
    Headers, Footers) and the page itself, then calls the publishing API.
    """
    
    
    # --- PHASE 1: COLLECT MIBLOCK PUBLISHING DATA ---
    publish_payload: List[Dict[str, Any]] = []
    
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
                
                # Simple validation before adding
                if component_id and section_guid:
                    miblock_entry = {
                        "id": component_id,
                        "type": "MIBLOCK",
                        "pageSectionGuid": section_guid
                    }
                    publish_payload.append(miblock_entry)
                    # print(f"  ✅ Added MiBlock {component_id} for publishing.")
                else:
                    print(f"  ⚠️ Skipping file {os.path.basename(os.path.dirname(file_path))}: Missing 'component_id' or 'sectionGuid'.")

        except Exception as e:
            print(f"  ❌ Error processing file {file_path}: {e}")

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
            component_entry = {
                "id": str(component_id),
                "type": "COMPONENT", # Headers/Footers are treated as standard components
                "pageSectionGuid": section_guid
            }
            publish_payload.append(component_entry)
            print(f"  ✅ Added {hf_key} Component ID {component_id} for publishing.")
        elif component_name and component_name != "N/A":
             # This means the component name was in the metadata but fetching its ID/GUID failed earlier
             print(f"  ⚠️ Skipping {hf_key} ('{component_name}'): Component ID or GUID was missing for publishing.")


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
    print(f"\n  ✅ Added Page ID {page_id} for publishing.")
    
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
    
    # print("\n--- 📑 FINAL PUBLISH PAYLOAD ---")
    # print(json.dumps(final_api_payload, indent=2))
    # print("---------------------------------")
    
    # Pass the final DICTIONARY payload to your publishing API function
    try:
        psPublishApi(base_url, headers, site_id, final_api_payload)
    except Exception as e:
        print(f"\n❌ **CRITICAL API ERROR:** An exception occurred during the API call: {e}")

    return len(publish_payload)

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

    print(f"\n📡 Attempting POST to: {api_url}")
    
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
        print(f"❌ HTTP error occurred: {http_err} (Status Code: {status_code})")
        return {"error": "HTTP Error", "details": str(http_err), "status_code": status_code}
    except requests.exceptions.ConnectionError as conn_err:
        print(f"❌ Connection error occurred: {conn_err}")
        return {"error": "Connection Error", "details": str(conn_err)}
    except requests.exceptions.Timeout as timeout_err:
        print(f"❌ Timeout error occurred: {timeout_err}")
        return {"error": "Timeout Error", "details": str(timeout_err)}
    except requests.exceptions.RequestException as req_err:
        print(f"❌ An unexpected request error occurred: {req_err}")
        return {"error": "Request Error", "details": str(req_err)}
    except json.JSONDecodeError:
        print(f"❌ Failed to decode JSON response. Response text: {response.text if 'response' in locals() else 'No response object.'}")
        return {"error": "JSON Decode Error", "details": "Response was not valid JSON"}




def load_records(file_path):
    """MOCK: Loads records from the JSON file."""
    # In a real scenario, this would handle file reading.
    # We mock a simple failure or success.
    if not os.path.exists(file_path):
        return [], {}, True # Mock empty successful load
    
    # Mocking a load where `records` is the main list and other variables are secondary
    with open(file_path, 'r') as f:
        data = json.load(f)
        if isinstance(data, dict) and "records" in data:
             return data["records"], data, False # records_data is the dict wrapper, original_wrapper_is_dict is False
        elif isinstance(data, list):
             return data, data, True # records_data is the list, original_wrapper_is_dict is True
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
    
    if not records_to_migrate:
        print(f"    [INFO] No {level_name} components found ready for migration.")
        return 0

    print(f"    [INFO] Found {len(records_to_migrate)} {level_name} component(s) to process.")
    
    
    # PHASE 2: MIGRATE AND TAG CHILDREN (NEXT LEVEL)
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
            "pageSectionGuid": pageSectionGuid # GUID is still required here for the API call
        }
        api_payload = {"main_record_set": [single_record]}

        # Call the API to create the record
        resp_success, resp_data = addUpdateRecordsToCMS(base_url, headers, api_payload, level)
        
        # --- Extract New Record ID ---
        new_record_id = None
        if resp_success and isinstance(resp_data, dict) and (0 in resp_data or "0" in resp_data):
            new_record_id = (resp_data.get(0) or resp_data.get("0")) + index + 1
        
        if new_record_id:
            migrated_count += 1
            # print(f"    [SUCCESS] CMS Record Created. Old Record ID: {current_record_old_id} -> New RecordId: {new_record_id}")
            
            # A. Update the current record with its own new ID and mark as migrated
            record["isMigrated"] = True
            record["new_record_id"] = new_record_id
            # REMOVED: record["sectionGuid"] = pageSectionGuid
            
            # B. Tag next-level children (N+1)
            updated_children_count = 0
            for child in records:
                # Use the child's 'ParentId' (which links to the current record's 'Id')
                if isinstance(child, dict) and child.get("ParentId") == current_record_old_id:
                    child["parent_new_record_id"] = new_record_id
                    # REMOVED: child["sectionGuid"] = pageSectionGuid 
                    updated_children_count += 1
            
            if updated_children_count > 0:
                print(f"    [TAGGED] Linked {updated_children_count} Level {level+1} record(s) to new parent ID {new_record_id}.")
            
        else:
            print(f"    [WARNING] Failed to update CMS record for {level_name} ID {current_record_old_id}. Response: {resp_data}")

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
                    "pageSectionGuid": pageSectionGuid 
                }

                api_payload = {"main_record_set": [single_record]}

                # Call the API to create the record
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
            
#             logging.info(f"✅ Component '{component_name}' is available. Starting content retrieval for **{page_name}**.")
            
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
#             logging.warning(f"❌ Component '{component_name}' **NOT AVAILABLE** for page **{page_name}**. Skipping.")
        
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
            
#             logging.info(f"✅ Component '{component_name}' is available. Starting content retrieval for **{page_name}**.")
            
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
#             logging.warning(f"❌ Component '{component_name}' **NOT AVAILABLE** for page **{page_name}**. Skipping.")
        
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
            
#             logging.info(f"✅ Component '{component_name}' is available. Starting content retrieval for **{page_name}**.")
            
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
#             logging.warning(f"❌ Component '{component_name}' **NOT AVAILABLE** for page **{page_name}**. Skipping.")
        
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


def _process_page_components(page_data: Dict[str, Any], page_level: int, hierarchy: List[str], component_cache: List[Dict[str, Any]], api_base_url: str, site_id: int, api_headers: Dict[str, str], category_id: int):
    
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
            
            logging.info(f"✅ Component '{component_name}' is available. Starting content retrieval for **{page_name}**.")
            
            status_entry["available"] = True
            status_entry["cms_component_name"] = cms_component_name
            
            # 🛑 CONDITION CHECK REMOVED 🛑
            try:
                logging.info(f"Attempting content retrieval for page: {page_name}")
                # Call function to get section payload (HTML snippet) and add records
                section_payload = add_records_for_page(page_name, vComponentId, componentId, api_base_url, site_id, api_headers, alias)
                status_entry["status"] = "SUCCESS: Content retrieved and records added to assembly queue."
            except Exception as e:
                logging.error(f"Content retrieval failed for {page_name}/{component_name}: {e}")
                status_entry["status"] = f"FAILED: Content retrieval error: {type(e).__name__}"
                status_entry["available"] = False
            
            # Append the payload (either retrieved content or an empty string)
            if section_payload is not None:
                page_sections_html.append(section_payload)
            
        else:
            logging.warning(f"❌ Component '{component_name}' **NOT AVAILABLE** for page **{page_name}**. Skipping.")
        
        ASSEMBLY_STATUS_LOG.append(status_entry)

    # --- FINALIZATION PHASE (NOW APPLIES TO ALL PAGES) ---
    
    # Check if any sections were successfully retrieved and contain data
    if page_sections_html and any(page_sections_html): 
        
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
        # 🌟 STEP 3: Pass the page_template_id to pageAction
        pageAction(api_base_url, api_headers, final_html, page_name, page_template_id, DefaultTitle, DefaultDescription, site_id, category_id,header_footer_details)
            
    else:
        # Adjusted logging for general page failure
        logging.error(f"Page **{page_name}** failed: No final HTML content was successfully retrieved/assembled to proceed to pageAction. Skipping pageAction.")
        return
        
# --- TRAVERSAL FUNCTIONS TO PASS CACHE AND NEW PARAMS ---

def assemble_page_templates_level4(page_data: Dict[str, Any], page_level: int, hierarchy: List[str], component_cache: List[Dict[str, Any]], api_base_url: str, site_id: int, api_headers: Dict[str, str]):
    logging.info(f"\n--- Level {page_level} Page: {page_data.get('page_name')} ---")
    _process_page_components(page_data, page_level, hierarchy, component_cache, api_base_url, site_id, api_headers,category_id = 0)

def assemble_page_templates_level3(page_data: Dict[str, Any], page_level: int, hierarchy: List[str], component_cache: List[Dict[str, Any]], api_base_url: str, site_id: int, api_headers: Dict[str, str],parent_page_name: str):
    logging.info(f"\n--- Level {page_level} Page: {page_data.get('page_name')} ---")
    matched_category_id = 0
    current_page_name = page_data.get('page_name', 'UNKNOWN_PAGE')

    logging.info(f"\n--- Level {page_level} Page: {current_page_name} ---")
    
    # Fetch categories list (already implemented in the provided GetPageCategoryList)
    categories = GetPageCategoryList(api_base_url, api_headers)
    logging.info(f"API categories loaded: {categories}")
    
    # Check for API errors
    if isinstance(categories, dict) and categories.get("error"):
        logging.error(f"❌ Unable to load page categories. Aborting processing for page '{current_page_name}'. Error: {categories.get('details')}")
        return

    # Category Matching Logic
    normalized_page_name = normalize_page_name(parent_page_name)
    
    # Search category ID by normalized name for robust matching
    for cat in categories:
        cat_name = cat.get("CategoryName")
        
        # NOTE: normalize_page_name must be available/imported
        if cat_name and normalize_page_name(cat_name) == normalized_page_name:
            matched_category_id = cat.get("CategoryId", 0)
            logging.info(f"✅ MATCHED Category '{current_page_name}' → CategoryId = {matched_category_id}")
            # Exit loop immediately after finding a match
            break 
    else:
        # This executes only if the loop completes without finding a match (i.e., if 'break' was never hit)
        logging.warning(f"⚠ No matching category found for page '{current_page_name}', using CategoryId = 0")
        # matched_category_id remains 0, as initialized above.
    
    _process_page_components(page_data, page_level, hierarchy, component_cache, api_base_url, site_id, api_headers,matched_category_id)
    
    new_hierarchy = hierarchy + [current_page_name]
    new_level = page_level + 1
    for sub_page_data in page_data.get("sub_pages", []):
        assemble_page_templates_level4(sub_page_data, new_level, new_hierarchy, component_cache, api_base_url, site_id, api_headers)


def assemble_page_templates_level2(
    page_data: Dict[str, Any], 
    page_level: int, 
    hierarchy: List[str], 
    component_cache: List[Dict[str, Any]], 
    api_base_url: str, 
    site_id: int, 
    api_headers: Dict[str, str],
    parent_page_name: str
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
        logging.error(f"❌ Unable to load page categories. Aborting processing for page '{current_page_name}'. Error: {categories.get('details')}")
        return

    # Category Matching Logic
    normalized_page_name = normalize_page_name(parent_page_name)
    
    # Search category ID by normalized name for robust matching
    for cat in categories:
        cat_name = cat.get("CategoryName")
        
        # NOTE: normalize_page_name must be available/imported
        if cat_name and normalize_page_name(cat_name) == normalized_page_name:
            matched_category_id = cat.get("CategoryId", 0)
            logging.info(f"✅ MATCHED Category '{current_page_name}' → CategoryId = {matched_category_id}")
            # Exit loop immediately after finding a match
            break 
    else:
        # This executes only if the loop completes without finding a match (i.e., if 'break' was never hit)
        logging.warning(f"⚠ No matching category found for page '{current_page_name}', using CategoryId = 0")
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
        category_id=matched_category_id # <-- CORRECTED
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
            parent_page_name
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
        print(current_page_name)
        if current_page_name == "Our Property":
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
                category_id  # passing resolved category id
            )

            next_level = initial_level + 1
            new_hierarchy = initial_hierarchy + [current_page_name]
            parent_page_name = current_page_name
            # Go to sub-pages (level2)
            for sub_page_data in top_level_page.get("sub_pages", []):
                assemble_page_templates_level2(sub_page_data, next_level, new_hierarchy, component_cache, api_base_url, site_id, api_headers,parent_page_name)
        else:
            pass

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
                
                logging.info(f"✅ All components JSON response saved to: {components_output_filepath}")
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
                                logging.info(f"✅ Found matching component: '{comp_name}' or '{comp_component_name}'")
                                break
                        
                        if matching_component:
                            # Get componentId from component.componentId or miBlockId
                            component_id = matching_component.get('component', {}).get('componentId') or \
                                          matching_component.get('miBlockId') or \
                                          matching_component.get('blockId')
                            
                            if component_id:
                                downloaded_component_id = component_id  # Store for later use
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
                                    mi_block_folder = f"mi-block-ID-{component_id}"
                                    output_dir = os.path.join("output", str(site_id))
                                    save_folder = os.path.join(output_dir, mi_block_folder)
                                    os.makedirs(save_folder, exist_ok=True)
                                    
                                    # Save the zip file
                                    filename = (
                                        content_disposition.split('filename=')[1].strip('"')
                                        if content_disposition and 'filename=' in content_disposition
                                        else f"component_{component_id}.zip"
                                    )
                                    file_path = os.path.join(save_folder, filename)
                                    
                                    logging.info(f"Saving zip file to: {file_path}")
                                    print(f"💾 Saving zip file...")
                                    with open(file_path, "wb") as file:
                                        file.write(response_content)

                                    if zipfile.is_zipfile(file_path):
                                        with zipfile.ZipFile(file_path, 'r') as zip_ref:
                                            zip_ref.extractall(save_folder)
                                        os.remove(file_path)
                                    else:
                                        print(f"  [WARNING] Exported file {filename} is not a zip file.")
                                    
                                    file_size = len(response_content)
                                    logging.info(f"✅ Zip file saved successfully! Size: {file_size} bytes")
                                    print(f"✅ Zip file saved successfully!")
                                    print(f"   File: {filename}")
                                    print(f"   Size: {file_size} bytes")
                                    print(f"   Location: {file_path}")
                                    print(f"{'='*80}\n")
                                else:
                                    logging.warning(f"⚠️ Component export returned no content for component ID: {component_id}")
                                    print(f"⚠️ Component export returned no content")

                                    
                                time.sleep(2) 
                                
                                # 2. Convert .txt files to .json (if they exist)
                                logging.info("🔄 Starting TXT to JSON conversion...")
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
                                            logging.info(f"   ✅ Successfully converted: {extracted_file}")
                                        except (json.JSONDecodeError, OSError) as e:
                                            # Log the error but continue to the next file
                                            logging.error(f"⚠️ Error processing file {extracted_file_path}: {e}")
                                
                                logging.info(f"✅ TXT to JSON conversion complete: {converted_count}/{len(txt_files_found)} files converted successfully")

                                # 3. Add level fields to MiBlockComponentRecords.json
                                records_file_path = os.path.join(save_folder, "MiBlockComponentRecords.json")
                                if os.path.exists(records_file_path):
                                    try:
                                        add_levels_to_records(records_file_path)
                                        logging.info(f"✅ Added level fields to records in {records_file_path}")
                                    except Exception as e:
                                        logging.error(f"⚠️ Error adding levels to records: {e}")

                                
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




                            else:
                                logging.warning(f"⚠️ Component ID not found in matching component data")
                        else:
                            logging.warning(f"⚠️ No matching component found for '{menu_component_name}'")
                            print(f"\n⚠️  No matching component found for '{menu_component_name}'")




                    except Exception as export_error:
                        logging.error(f"❌ Error during component download: {export_error}")
                        logging.exception("Full traceback:")
                        # Continue execution even if download fails
            else:
                logging.warning(f"⚠️ API response was not a list or was empty. Response type: {type(all_components_response)}")
        except Exception as e:
            logging.error(f"❌ Error fetching/saving components: {e}")
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
        
        logging.info(f"✅ Menu navigation JSON saved to: {output_filepath}")
        print(f"Created new JSON file: {output_filename}")
        
        # 5. Map pages to records if component was downloaded
        if downloaded_component_id:
            logging.info(f"Starting page-to-record mapping for component ID: {downloaded_component_id}")
            if map_pages_to_records(file_prefix, site_id, downloaded_component_id):
                # 6. Create payloads for both matched and unmatched records
                logging.info("Creating payloads for matched records (update)...")
                create_save_miblock_records_payload(file_prefix, downloaded_component_id, site_id)
                
                logging.info("Creating payloads for unmatched records (create new)...")
                create_new_records_payload(file_prefix, downloaded_component_id, site_id)
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
                                logging.info(f"  ✅ Match found! Record ID: {record.get('Id')}")
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
                
                # Add extracted name and link as top-level keys for easy access
                if name_key and name_value is not None:
                    matched_record_with_page_info[name_key] = name_value
                    logging.debug(f"  Added top-level key '{name_key}' = '{name_value}'")
                
                if link_key and link_value is not None:
                    matched_record_with_page_info[link_key] = link_value
                    logging.debug(f"  Added top-level key '{link_key}' = '{link_value}'")
                
                # Add to the collection
                all_matched_records.append(matched_record_with_page_info)
                
                logging.info(f"✅ Matched '{page_name}' (level {page_level}) → added to collection")
                page_node["matchFound"] = True
            else:
                logging.warning(f"❌ No match found for '{page_name}' (level {page_level})")
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
            
            logging.info(f"✅ Saved {len(all_matched_records)} matched records to {output_filename}")
        else:
            logging.warning("No matched records found to save")
        
        # 7. Save updated menu_navigation.json with matchFound status
        with open(menu_nav_file, 'w', encoding='utf-8') as f:
            json.dump(menu_nav_data, f, indent=4, ensure_ascii=False)
        
        logging.info(f"✅ Updated menu_navigation.json with matchFound status")
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


def create_new_records_payload(file_prefix: str, component_id: int, site_id: int) -> bool:
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
        
        # Read MiBlockComponentRecords.json to get ComponentId mapping
        records_folder = os.path.join("output", str(site_id), f"mi-block-ID-{component_id}")
        records_file = os.path.join(records_folder, "MiBlockComponentRecords.json")
        
        main_parent_component_id = component_id  # Level 1
        child_component_id = component_id  # Level 2, default to main if not found
        
        if os.path.exists(records_file):
            with open(records_file, 'r', encoding='utf-8') as f:
                records_data = json.load(f)
            
            component_records = records_data.get("componentRecords", [])
            for record in component_records:
                rec_main_parent_id = record.get("MainParentComponentId")
                rec_component_id = record.get("ComponentId")
                
                # Find child ComponentId (different from MainParentComponentId)
                if rec_main_parent_id and rec_component_id and rec_component_id != rec_main_parent_id:
                    main_parent_component_id = rec_main_parent_id  # Level 1
                    child_component_id = rec_component_id  # Level 2
                    break
            
            logging.info(f"Level 1 ComponentId: {main_parent_component_id}, Level 2 ComponentId: {child_component_id}")
        else:
            logging.warning(f"Records file not found: {records_file}. Using main component_id for all levels.")
        
        new_records = []
        
        def collect_unmatched(page_node, parent_id=0, display_order=0):
            if not page_node.get("matchFound", False):
                page_name = page_node.get("page_name", "")
                level = page_node.get("level", 0)
                
                # Level 1 uses main parent, Level 2+ uses child component
                if level == 1:
                    record_component_id = main_parent_component_id
                else:
                    record_component_id = child_component_id
                
                record_data = {
                    f"{page_name.lower().replace(' ', '-')}-name": page_name,
                    f"{page_name.lower().replace(' ', '-')}-link": f"/{page_name.lower().replace(' ', '-')}"
                }
                
                new_record = {
                    "componentId": record_component_id,
                    "recordId": 0,
                    "parentRecordId": parent_id,
                    "recordDataJson": json.dumps(record_data),
                    "status": True,
                    "tags": [],
                    "displayOrder": display_order,
                    "updatedBy": 0,
                    "page_name": page_name,
                    "level": level
                }
                new_records.append(new_record)
            
            for idx, sub_page in enumerate(page_node.get("sub_pages", [])):
                collect_unmatched(sub_page, 0, idx)
        
        for idx, page in enumerate(menu_nav_data.get("pages", [])):
            collect_unmatched(page, 0, idx)
        
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
            
            logging.info(f"✅ Created new records payload: {output_filename} ({len(new_records)} records)")
            return True
        else:
            logging.info("No unmatched records to create")
            return False
    
    except Exception as e:
        logging.error(f"Error creating new records payload: {e}")
        logging.exception("Full traceback:")
        return False


def create_save_miblock_records_payload(file_prefix: str, component_id: int, site_id: int) -> bool:
    """
    Creates payloads for saveMiBlockRecords API from matched_records.json.
    These payloads are for updating existing records.
    
    Args:
        file_prefix: The file prefix for matched_records.json
        component_id: The component ID to use in the payload
        site_id: The site ID (for logging)
        
    Returns:
        bool: True if successful, False otherwise
    """
    logging.info("========================================================")
    logging.info("START: Creating SaveMiBlockRecords Payload (Matched)")
    logging.info("========================================================")
    
    try:
        # 1. Read matched_records.json
        matched_records_file = os.path.join(UPLOAD_FOLDER, f"{file_prefix}_matched_records.json")
        if not os.path.exists(matched_records_file):
            logging.error(f"Matched records file not found: {matched_records_file}")
            logging.info("Skipping matched records payload creation")
            return False
        
        with open(matched_records_file, 'r', encoding='utf-8') as f:
            matched_data = json.load(f)
        
        matched_records = matched_data.get("matched_records", [])
        if not matched_records:
            logging.warning("No matched records found to create payload")
            return False
        
        # 2. Transform records into API payload format
        api_payloads = []
        
        for record in matched_records:
            # Extract required fields
            record_id = record.get("Id", 0)
            parent_id = record.get("ParentId", 0)
            record_json_string = record.get("RecordJsonString", "")
            status = record.get("Status", True)
            display_order = record.get("DisplayOrder", 0)
            updated_by = record.get("UpdatedBy", 0)
            
            # Get tags if available
            tags = record.get("tags", [])
            if not isinstance(tags, list):
                tags = []
            
            # Create API payload record
            api_record = {
                "componentId": component_id,
                "recordId": record_id,  # Use existing ID for updates
                "parentRecordId": parent_id,
                "recordDataJson": record_json_string,
                "status": status,
                "tags": tags,
                "displayOrder": display_order,
                "updatedBy": updated_by,
                # Note: pageSectionGuid is not included as it's typically for new records
                # If needed for updates, it should be extracted from the original record
            }
            
            api_payloads.append(api_record)
        
        # 3. Group payloads by record set (if needed)
        # For now, we'll create a simple structure with all records
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
        
        logging.info(f"✅ Created matched records payload: {output_filename}")
        logging.info(f"   Total matched records in payload: {len(api_payloads)}")
        logging.info("END: Creating SaveMiBlockRecords Payload (Matched) Complete")
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


# ================= Main Entry Function (Uses Dynamic Config) =================

def run_assembly_processing_step(processed_json: Union[Dict[str, Any], str], *args, **kwargs) -> Dict[str, Any]:
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
        vcomponent_cache = GetAllVComponents(api_base_url, api_headers, page_size=1000)
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

    # --- 5. Assembly Execution (PASSES CACHE and NEW PARAMS) ---
    # assemble_page_templates_level1(full_payload, vcomponent_cache, api_base_url, site_id, api_headers)

    # --- 5.5. Update Menu Navigation ---
    update_menu_navigation(file_prefix, api_base_url, site_id, api_headers)

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