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
from typing import Dict, Any, List, Union, Tuple, Optional
# Assuming apis.py now contains: GetAllVComponents, export_mi_block_component
from apis import GetAllVComponents, export_mi_block_component,addUpdateRecordsToCMS,generatecontentHtml,GetTemplatePageByName,psMappingApi,psPublishApi,GetPageCategoryList
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
        
        print(f"  [INFO] Component ID: {component_id_unpacked}")
        print(f"  [INFO] Component component_alias: {component_alias_unpacked}")
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
            for extracted_file in os.listdir(save_folder):
                extracted_file_path = os.path.join(save_folder, extracted_file)
                if extracted_file.endswith('.txt'):
                    new_file_path = os.path.splitext(extracted_file_path)[0] + '.json'
                    try:
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
                    except (json.JSONDecodeError, OSError) as e:
                        # Log the error but continue to the next file
                        logging.error(f"⚠️ Error processing file {extracted_file_path}: {e}")

            # --- POLLING LOGIC to wait for MiBlockComponentConfig.json to be accessible ---
            config_file_name = "MiBlockComponentConfig.json"
            config_file_path = os.path.join(save_folder, config_file_name)
            
            MAX_WAIT_SECONDS = 120 # 2 minutes max wait
            POLL_INTERVAL = 5      # Check every 5 seconds
            start_time = time.time()
            file_ready = False

            print(f"Waiting up to {MAX_WAIT_SECONDS} seconds for {config_file_name} to be available...")

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






def pageAction(base_url, headers,final_html,page_name,page_template_id,DefaultTitle,DefaultDescription,site_id):
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
        "pageCategoryId": 0,
        "pageProfileId": 0,
        "tags": ""
        }
    print(f"New page payload ready for '{page_name}'.")
    data = CreatePage(base_url, headers, payload,page_template_id)
    print(data)

    # Access the 'pageId' key and print its value
    page_id = data.get("PageId")

    if page_id is not None:
        print(f"The Page ID is: {page_id}")
    else:
        print("Error: 'pageId' key not found in the returned data.")


    updatePageMapping(base_url, headers,page_id,site_id)
    publishPage(base_url, headers,page_id,site_id)

    
    return data



def updatePageMapping(base_url: str, headers: Dict[str, str], page_id: int,site_id: int):
    """
    Creates and sends the page mapping payload using data from all
    ComponentRecordsTree.json files found in the migration output folders.
    """

    
    # --- PHASE 1: COLLECT MAPPING DATA ---
    all_mappings: List[Dict[str, Any]] = []
    
    # Construct the base path to search: output/site_id/mi-block-ID-*
    search_path = os.path.join("output", site_id, "mi-block-ID-*", "ComponentRecordsTree.json")
    
    print(f"🔍 Searching for migration files in: {os.path.join('output', site_id, 'mi-block-ID-*')}")
    
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
                    "contentEntityType": 2, # Fixed value
                    "pageSectionGuid": main_component_record.get("sectionGuid")
                }
                
                # Simple validation before adding
                if mapping_data["vComponentAlias"] and mapping_data["pageSectionGuid"]:
                    all_mappings.append(mapping_data)
                    print(f"  ✅ Extracted mapping for alias: {mapping_data['vComponentAlias']}")
                else:
                    print(f"  ⚠️ Skipping file {os.path.basename(os.path.dirname(file_path))}: Missing 'component_alias' or 'sectionGuid'.")

        except Exception as e:
            print(f"  ❌ Error processing file {file_path}: {e}")

    if not all_mappings:
        print("\n[INFO] No valid component mappings were found. Aborting mapping update.")
        return 0
        
    print(f"\n[INFO] Successfully collected {len(all_mappings)} mappings.")

    # --- PHASE 2: CONSTRUCT API PAYLOAD ---
    new_api_payload = all_mappings
    
    # --- PHASE 3: PRINT PAYLOAD AND CALL API ---
    
    print("\n--- 📑 FINAL API PAYLOAD ---")
    print(json.dumps(new_api_payload, indent=2))
    print("-----------------------------")

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
        # Note: We don't set 'resp_success = False' here, as that variable is unused in this fixed block.

    return len(new_api_payload)



def publishPage(base_url: str, headers: Dict[str, str], page_id: int,site_id: int):
    """
    Constructs the necessary payload to publish all migrated components and the page itself,
    then calls the publishing API.
    """
    
    
    # --- PHASE 1: COLLECT MIBLOCK PUBLISHING DATA ---
    publish_payload: List[Dict[str, Any]] = []
    
    # Construct the base path to search: output/site_id/mi-block-ID-*
    search_path = os.path.join("output", site_id, "mi-block-ID-*", "ComponentRecordsTree.json")
    
    print(f"🔍 Searching for migrated component data in: {os.path.join('output', site_id, 'mi-block-ID-*')}")
    
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
                # NOTE: Using ComponentId as "id" and assuming it is the correct ID to publish.
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
                    print(f"  ✅ Added MiBlock {component_id} for publishing.")
                else:
                    print(f"  ⚠️ Skipping file {os.path.basename(os.path.dirname(file_path))}: Missing 'component_id' or 'sectionGuid'.")

        except Exception as e:
            print(f"  ❌ Error processing file {file_path}: {e}")

    # --- PHASE 2: ADD PAGE PUBLISHING DATA ---
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

    # --- PHASE 3: CONSTRUCT FINAL DICTIONARY PAYLOAD AND EXECUTE API CALL ---
    
    # Construct the final dictionary payload as per the API's requirement
    final_api_payload = {
        "publishData": publish_payload,
        "syncPageForTranslationRequest": None
    }
    
    print("\n--- 📑 FINAL PUBLISH PAYLOAD ---")
    print(json.dumps(final_api_payload, indent=2))
    print("---------------------------------")
    
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
            
        print(f"    [START] Migrating {level_name} Record ID: {current_record_old_id} (Parent New ID: {new_parent_id})")
        
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
            print(f"    [SUCCESS] CMS Record Created. Old Record ID: {current_record_old_id} -> New RecordId: {new_record_id}")
            
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
    print(f"  [INFO] Searching for MainComponent records in {records_file_path}...")
    
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
                print(f"  [FOUND] MainComponent ID: {main_component_old_id}")
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
        print(f"Reading configuration from: {input_file_path}")
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
        print(f"Writing component hierarchy to: {output_file_path}")
        
        # Ensure the output directory exists
        os.makedirs(folder_path, exist_ok=True)
        
        with open(output_file_path, 'w') as f:
            json.dump(output_payload, f, indent=4)
        
        print("Successfully determined component hierarchy and saved.")
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
    print(f"Found {len(records_tree)} records in the hierarchy. Writing to: {output_file_path}")
    
    os.makedirs(folder_path, exist_ok=True)
    with open(output_file_path, 'w') as f:
        # Save the list of records in sequence under the key 'componentRecordsTree'
        json.dump({"componentRecordsTree": records_tree}, f, indent=4)
    
    print("Successfully collected and saved component records tree with recordType.")
    return True


























# ================= Core Processing Logic and Traversal =================
def _process_page_components(page_data: Dict[str, Any], page_level: int, hierarchy: List[str], component_cache: List[Dict[str, Any]], api_base_url: str, site_id: int, api_headers: Dict[str, str],category_id: int):
    page_name = page_data.get('page_name', 'UNKNOWN_PAGE')
    components = page_data.get('components', [])
    meta_info = page_data.get('meta_info', {}) # Extract meta_info
    
    # 🌟 STEP 1: Get Template Name and Fetch Template ID
    page_template_name = meta_info.get("PageTemplateName")
    DefaultTitle = meta_info.get("DefaultTitle")
    DefaultDescription = meta_info.get("DefaultDescription")
    page_template_id = None
    
    if page_template_name:
        try:
            # 🌟 STEP 2: Call API to get the Template ID (Need to define get_page_template_id)
            # Assuming get_page_template_id is available in the current scope
            # Placeholder call:
            template_info = GetTemplatePageByName(api_base_url, api_headers, page_template_name)
            if template_info and isinstance(template_info, list) and 'PageId' in template_info[0]:
                page_template_id = template_info[0]['PageId'] # Should be 418607
            else:
                # Handle error: log or raise exception
                page_template_id = None

                
            logging.info(f"Retrieved Page Template ID {page_template_id} for template: {page_template_name}")
        except Exception as e:
            logging.error(f"Failed to retrieve page template ID for '{page_template_name}': {e}")
            # Decide if you want to fail the page here or proceed with a default/None ID
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

    # --- ACCUMULATION PHASE: Component Loop ---
    for component_name in components:
        status_entry = {
            "page": page_name, "component": component_name, "level": page_level,
            "hierarchy": " > ".join(hierarchy + [page_name]), "available": False, 
            "status": "SKIPPED: Component not available.",
            "cms_component_name": "N/A"
        }
        
        api_result = check_component_availability(component_name, component_cache)
        
        if api_result:
            vComponentId, alias, componentId, cms_component_name = api_result 
            
            logging.info(f"✅ Component '{component_name}' is available. Starting content retrieval for **{page_name}**.")
            
            status_entry["available"] = True
            status_entry["cms_component_name"] = cms_component_name
            section_payload = None  # Initialize payload
            
            # CONDITION: Only call add_records_for_page for the 'Weddings' page
            if page_name == "Weddings":
                try:
                    # Call function to get section payload (HTML snippet)
                    section_payload = add_records_for_page(page_name, vComponentId, componentId, api_base_url, site_id, api_headers, alias)
                    status_entry["status"] = "SUCCESS: Content retrieved and added to assembly queue."
                except Exception as e:
                    logging.error(f"Content retrieval failed for {page_name}/{component_name}: {e}")
                    status_entry["status"] = f"FAILED: Content retrieval error: {type(e).__name__}"
                    status_entry["available"] = False
            else:
                # Data retrieval/record adding is skipped for non-Weddings pages
                logging.info(f"Skipping record addition for non-Weddings page: {page_name}/{component_name}.")
                status_entry["status"] = "SUCCESS: Component available, data retrieval skipped (non-Weddings page)."
                section_payload = "" # Append empty string
            
            # Append the payload (either retrieved content or an empty string)
            if section_payload is not None:
                page_sections_html.append(section_payload)
            
        else:
            logging.warning(f"❌ Component '{component_name}' **NOT AVAILABLE** for page **{page_name}**. Skipping.")
        
        ASSEMBLY_STATUS_LOG.append(status_entry)

    # --- FINALIZATION PHASE (Executed once per page) ---
    
    # Check if any sections were successfully retrieved
    if page_sections_html and any(page_sections_html): 
        
        # Concatenate all component HTML sections in order
        all_sections_concatenated = "".join(page_sections_html)
        
        # Define HTML wrappers
        htmlPrefix = '<div class="box2" id="data_page_content"><div id="pagestudio">'
        htmlPostfix = "</div></div>"
        
        # Add the prefix and postfix wrappers
        final_html = htmlPrefix + all_sections_concatenated + htmlPostfix
        
        # 📢 ADDED PRINT STATEMENT HERE 📢
        print("\n--- FINAL ASSEMBLED HTML PAYLOAD ---")
        print(final_html)
        print("--------------------------------------\n")
        
        # Apply the conditional execution for the "Weddings" page
        if page_name == "Weddings":
            logging.info(f"Final assembly complete for **{page_name}**. Calling pageAction for publishing.")
            # 🌟 STEP 3: Pass the page_template_id to pageAction
            pageAction(api_base_url, api_headers, final_html, page_name, page_template_id,DefaultTitle,DefaultDescription,site_id)
        else:
             logging.info(f"Final assembly complete for **{page_name}** but skipping pageAction (non-Weddings page).")
    else:
        if page_name == "Weddings":
             logging.error(f"Page **{page_name}** failed: No final HTML content was successfully retrieved to assemble the page.")
        else:
             logging.info(f"Page **{page_name}** (non-Weddings) completed component checks but assembled an empty page, as expected.")
        return


# --- TRAVERSAL FUNCTIONS TO PASS CACHE AND NEW PARAMS ---

def assemble_page_templates_level4(page_data: Dict[str, Any], page_level: int, hierarchy: List[str], component_cache: List[Dict[str, Any]], api_base_url: str, site_id: int, api_headers: Dict[str, str]):
    logging.info(f"\n--- Level {page_level} Page: {page_data.get('page_name')} ---")
    _process_page_components(page_data, page_level, hierarchy, component_cache, api_base_url, site_id, api_headers,category_id = 0)

def assemble_page_templates_level3(page_data: Dict[str, Any], page_level: int, hierarchy: List[str], component_cache: List[Dict[str, Any]], api_base_url: str, site_id: int, api_headers: Dict[str, str]):
    logging.info(f"\n--- Level {page_level} Page: {page_data.get('page_name')} ---")
    _process_page_components(page_data, page_level, hierarchy, component_cache, api_base_url, site_id, api_headers,category_id = 0)
    current_page_name = page_data.get('page_name', 'UNKNOWN_PAGE')
    new_hierarchy = hierarchy + [current_page_name]
    new_level = page_level + 1
    for sub_page_data in page_data.get("sub_pages", []):
        assemble_page_templates_level4(sub_page_data, new_level, new_hierarchy, component_cache, api_base_url, site_id, api_headers)

def assemble_page_templates_level2(page_data: Dict[str, Any], page_level: int, hierarchy: List[str], component_cache: List[Dict[str, Any]], api_base_url: str, site_id: int, api_headers: Dict[str, str]):
    logging.info(f"\n--- Level {page_level} Page: {page_data.get('page_name')} ---")
    _process_page_components(page_data, page_level, hierarchy, component_cache, api_base_url, site_id, api_headers,category_id = 0)
    current_page_name = page_data.get('page_name', 'UNKNOWN_PAGE')
    new_hierarchy = hierarchy + [current_page_name]
    new_level = page_level + 1
    for sub_page_data in page_data.get("sub_pages", []):
        assemble_page_templates_level3(sub_page_data, new_level, new_hierarchy, component_cache, api_base_url, site_id, api_headers)

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
        if current_page_name == "Weddings":
            logging.info(f"\n--- Level {initial_level} Page: {current_page_name} ---")
            alldata = GetPageCategoryList(api_base_url, api_headers)
            category_id = 0
            _process_page_components(top_level_page, initial_level, initial_hierarchy, component_cache, api_base_url, site_id, api_headers,category_id)
            next_level = initial_level + 1
            new_hierarchy = initial_hierarchy + [current_page_name]
            for sub_page_data in top_level_page.get("sub_pages", []):
                assemble_page_templates_level2(sub_page_data, next_level, new_hierarchy, component_cache, api_base_url, site_id, api_headers) 
                pass
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
        vcomponent_cache = GetAllVComponents(api_base_url, api_headers)
    except Exception as e:
        logging.error(f"FATAL: Failed to retrieve V-Component list: {e}")
        raise RuntimeError("V-Component list retrieval failed. Cannot proceed with assembly.")


    if not isinstance(vcomponent_cache, list):
        logging.error(f"FATAL: Failed to retrieve V-Component list. API returned error: {vcomponent_cache}")
        raise RuntimeError("V-Component list retrieval failed. Cannot proceed with assembly.")

    logging.info(f"Successfully loaded {len(vcomponent_cache)} components into cache for fast lookup.")

    # --- 5. Assembly Execution (PASSES CACHE and NEW PARAMS) ---
    assemble_page_templates_level1(full_payload, vcomponent_cache, api_base_url, site_id, api_headers)

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