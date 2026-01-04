import json
import os
import re
import sys
from datetime import datetime
from typing import Dict, Any, List, Union

# IMPORTANT: These must be correctly defined in 'apis' and 'config'
# Assuming these imports are available in your environment
from apis import GetPageCategoryList, save_module_category
from config import UPLOAD_FOLDER

# --- DEBUG LOG FILE FOR MODULE PROCESSING STEP ---
MODULE_DEBUG_LOG_FILE = os.path.join(UPLOAD_FOLDER, "module_debug.log")

def append_module_debug_log(section: str, data: Dict[str, Any]) -> None:
    """
    Writes structured debug information to module_debug.log file.
    Uses JSON format with timestamp for easy parsing.
    """
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = {
            "timestamp": timestamp,
            "section": section,
            "data": data
        }
        with open(MODULE_DEBUG_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    except Exception:
        # Never block execution on debug logging
        pass 

# --- UTILITY FUNCTION FOR FUZZY MATCHING ---
def normalize_page_name(name: str) -> str:
    """
    Normalizes a page or category name for robust comparison.
    Converts to lowercase, strips whitespace, and removes all non-alphanumeric characters.
    """
    if not name:
        return ""
    normalized = name.strip().lower()
    normalized = re.sub(r'[^a-z0-9]', '', normalized)
    return normalized

def get_config_filepath(file_prefix: str) -> str:
    """
    Constructs the unique config.json filepath based on the prefix.
    It relies on the 'file_prefix' being the unique ID + the original filename slug.
    We ensure the unique ID is extracted if a full path is mistakenly passed.
    """
    base_prefix = os.path.basename(file_prefix)
    config_filename = f"{base_prefix}_config.json"
    return os.path.join(UPLOAD_FOLDER, config_filename)

def load_settings(file_prefix: str) -> Dict[str, Any] | None:
    """Loads the settings/config file based on the unique prefix."""
    # Note: get_config_filepath handles the path/basename extraction for us
    filepath = get_config_filepath(file_prefix) 
    if not os.path.exists(filepath):
        print(f"Module Processor: Config file not found at {filepath}")
        return None
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Module Processor: Error loading config file: {e}")
        return None

# --- UTILITY FUNCTION TO DYNAMICALLY FIND THE PROCESSED JSON FILE (KEY FIX HERE) ---
def find_processed_json_filepath(file_prefix: str) -> str | None:
    """
    Dynamically finds the processed JSON file based on the unique prefix, 
    even if the prefix argument contains path information.
    Excludes _home_simplified.json to avoid loading the home page file.
    """
    # FIX: Use os.path.basename to reliably isolate the unique ID component
    base_prefix = os.path.basename(file_prefix)

    # print(f"Module Processor: Searching UPLOAD_FOLDER ('{UPLOAD_FOLDER}') for file starting with '{base_prefix}' and ending with '_simplified.json'.")
    
    if not os.path.isdir(UPLOAD_FOLDER):
        print(f"FATAL ERROR: UPLOAD_FOLDER path does not exist or is not a directory: {UPLOAD_FOLDER}")
        return None
        
    for filename in os.listdir(UPLOAD_FOLDER):
        # Use the isolated base_prefix for matching
        # Exclude _home_simplified.json to avoid confusion
        if filename.startswith(base_prefix) and filename.endswith("_simplified.json") and not filename.endswith("_home_simplified.json"):
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            # print(f"Module Processor: [SUCCESS] Match found: {filename}")
            return filepath
            
    # print(f"Module Processor: [ERROR] No processed JSON file found matching the criteria for prefix '{base_prefix}'.")
    return None

# --- UTILITY FUNCTION TO SAVE PROCESSED JSON (Uses dynamic path) ---
def save_processed_json(file_prefix: str, data: Dict[str, Any]) -> bool:
    """Saves the processed JSON data back to its dynamically located file."""
    # find_processed_json_filepath now handles the robust prefix extraction
    filepath = find_processed_json_filepath(file_prefix)
    
    if not filepath:
        print(f"Module Processor: Error saving. Could not find target processed JSON file starting with '{os.path.basename(file_prefix)}'. Cannot save.")
        return False

    try:
        with open(filepath, "w") as f:
            json.dump(data, f, indent=4)
        # print(f"[SUCCESS] Successfully saved updated processed JSON to {filepath}")
        return True
    except Exception as e:
        print(f"Module Processor: Error saving processed JSON file: {e}")
        return False

# --- PLACEHOLDER FUNCTION FOR CATEGORY CREATION ---
def createCategory(page_name: str, site_id: Union[str, int], base_url: str, headers: Dict[str, str]) -> Union[int, None]:
    """
    Creates a new module category using the CMS API when a match is not found.
    
    Args:
        page_name (str): The name of the page/category to create
        site_id (Union[str, int]): The site ID
        base_url (str): The base URL for the API
        headers (Dict[str, str]): The authorization headers
        
    Returns:
        Union[int, None]: The created CategoryId if successful, None otherwise
    """
    print(f"\n[INFO] Creating new category for Page Name: '{page_name}' (Site ID: {site_id})...")
    append_module_debug_log("category_creation_attempt", {"page_name": page_name, "site_id": site_id})
    
    # Generate category alias from page name
    category_alias = page_name.lower().replace(' ', '-').replace('_', '-')
    category_alias = re.sub(r'[^a-z0-9-]', '', category_alias)
    
    # Generate module identifier
    module_identifier = f"MODULE_{category_alias.upper().replace('-', '_')}"
    
    payload = {
        "ModuleCategory": {
            "CategoryId": 0,
            "ParentCategory": 0,
            "CategoryName": page_name,
            "CategoryAlias": category_alias,
            "ResourceTypeID": 1,
            "ResourceTypeIdForMultipleImages": 0,
            "categorystatus": 1,
            "MilestoneModuleCategoryID": 0,
            "ModuleIdentifier": module_identifier,
            "ShowSnippets": 0,
            "TopNavigationFormatId": 0,
            "ModuleOrder": 1,
            "SchemaBusinessTypeDetailID": 0,
            "IsEnableRedirection": False,
            "RedirectionURL": "",
            "SiteId": int(site_id) if isinstance(site_id, str) else site_id
        }
    }
    
    print(f"[DEBUG] API Payload to be sent:")
    print(f"  - CategoryName: '{payload['ModuleCategory']['CategoryName']}'")
    print(f"  - CategoryAlias: '{payload['ModuleCategory']['CategoryAlias']}'")
    print(f"  - ModuleIdentifier: '{payload['ModuleCategory']['ModuleIdentifier']}'")
    print(f"  - SiteId: {payload['ModuleCategory']['SiteId']}")
    print(f"  - CategoryId: {payload['ModuleCategory']['CategoryId']} (0 = new category)")
    append_module_debug_log("category_creation_payload", {"page_name": page_name, "payload": payload})
    
    try:
        response = save_module_category(base_url, headers, payload)
        print(f"[DEBUG] API Response for category creation: {response}")
        append_module_debug_log("category_creation_response", {"page_name": page_name, "response": response})
        
        if response:
            category_id = None
            if isinstance(response, dict):
                # Try different response structures
                if 'ModuleCategory' in response and 'CategoryId' in response['ModuleCategory']:
                    category_id = response['ModuleCategory']['CategoryId']
                elif 'CategoryId' in response:
                    category_id = response['CategoryId']
                elif 'result' in response:
                    result = response['result']
                    if isinstance(result, dict) and 'CategoryId' in result:
                        category_id = result['CategoryId']
                    elif isinstance(result, (int, str)):
                        category_id = int(result)
            
            if category_id and category_id > 0:
                print(f"[SUCCESS] Created new category '{page_name}' with CategoryId: {category_id}")
                append_module_debug_log("category_creation_success", {"page_name": page_name, "category_id": category_id})
                return category_id
            else:
                print(f"[WARNING] Category creation API call succeeded but CategoryId not found in response: {response}")
                append_module_debug_log("category_creation_warning", {"page_name": page_name, "response": response, "reason": "CategoryId not found"})
                return None
        else:
            print(f"[ERROR] Failed to create category '{page_name}': API returned None")
            append_module_debug_log("category_creation_failure", {"page_name": page_name, "response": response, "reason": "API returned None"})
            return None
    
    except Exception as e:
        print(f"[ERROR] Exception occurred while creating category '{page_name}': {e}")
        append_module_debug_log("category_creation_exception", {"page_name": page_name, "error": str(e)})
        return None


# --- MODIFIED FUNCTION: Load the JSON result from the XML processing step ---
def load_processed_json(file_prefix: str) -> Dict[str, Any] | None:
    """
    Loads the JSON file generated by the process_xml step.
    If the file is not found, it returns None.
    """
    # 1. Dynamically find the file
    filepath = find_processed_json_filepath(file_prefix)
    
    # 2. Check if the file exists. If not, return None immediately.
    if not filepath or not os.path.exists(filepath):
        return None

    # 3. Load the actual file
    try:
        print(f"Module Processor: Loading actual processed JSON from: {filepath}")
        with open(filepath, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Module Processor: Error loading processed JSON file at {filepath}: {e}")
        return None

    
def run_module_processing_step(
    input_filepath: str, 
    step_config: Dict[str, Any], 
    previous_step_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    The main execution function for the module processing step.
    """
    # 1. Get the unique file prefix from the previous step's data
    file_prefix = previous_step_data.get('file_prefix')
    if not file_prefix:
        raise ValueError("Module Processing failed: Missing unique file prefix.")

    # 2. Load settings to get the target URL, Site ID, and token
    settings = load_settings(file_prefix)
    if not settings:
        raise RuntimeError("Could not load user configuration. Aborting module processing.")

    target_url = settings.get("target_site_url")
    site_id = settings.get("site_id")
    
    # --- FIX START: Correctly retrieve the raw token string ---
    # The user-provided config uses 'cms_login_token' for the raw string.
    raw_token = settings.get("cms_login_token") 
    
    if not target_url or not raw_token or not site_id:
        # Updated error message to reflect the correct key
        raise ValueError("Error: Target URL, Site ID, or **CMS Login Token** missing in configuration. Cannot fetch modules.")
    
    # Validation: Ensure the token is a non-empty string as expected from the config file.
    if not isinstance(raw_token, str) or not raw_token.strip():
        raise TypeError(f"Expected 'cms_login_token' to be a non-empty string, but received {type(raw_token)}.")

    # --- FIX END ---
    
    # 4. Construct the required headers
    headers = {
        'Content-Type': 'application/json',
        'ms_cms_clientapp': 'ProgrammingApp',
        # Use the raw_token string directly
        'Authorization': f'Bearer {raw_token}',
    }
    
    # --- Logic: Load and extract ALL target page names from BOTH JSON files ---
    # Load inner pages
    inner_pages_json = load_processed_json(file_prefix)
    
    # Load home page
    base_prefix = os.path.basename(file_prefix)
    home_simplified_filepath = os.path.join(UPLOAD_FOLDER, f"{base_prefix}_home_simplified.json")
    home_json = None
    if os.path.exists(home_simplified_filepath):
        try:
            with open(home_simplified_filepath, "r", encoding="utf-8") as f:
                home_json = json.load(f)
            print(f"Module Processor: Loaded home page JSON from: {home_simplified_filepath}")
        except Exception as e:
            print(f"Module Processor: Warning - Could not load home page JSON: {e}")
    
    # Merge both JSONs into one
    processed_json = {"title": "", "pages": []}
    
    if home_json and 'pages' in home_json and isinstance(home_json['pages'], list):
        processed_json['pages'].extend(home_json['pages'])
        print(f"[DEBUG] Added {len(home_json['pages'])} page(s) from home JSON")
    
    if inner_pages_json and 'pages' in inner_pages_json and isinstance(inner_pages_json['pages'], list):
        processed_json['pages'].extend(inner_pages_json['pages'])
        print(f"[DEBUG] Added {len(inner_pages_json['pages'])} page(s) from inner pages JSON")
    
    # If both JSON files are missing (an upstream error)
    if not processed_json['pages']:
        raise RuntimeError(f"Processing failed: Could not load any pages from JSON files for prefix '{base_prefix}'. Check the previous XML processing step.")

    # Extract ALL pages from the merged pages array
    all_page_names: List[str] = [] 
    
    if 'pages' in processed_json and isinstance(processed_json['pages'], list):
        for page in processed_json['pages']:
            if 'page_name' in page:
                all_page_names.append(page['page_name'])
        
        print(f"\n[DEBUG] Extracted {len(all_page_names)} page(s) from processed JSON:")
        for idx, page_name in enumerate(all_page_names, 1):
            print(f"  {idx}. '{page_name}'")
    else:
        print("[WARNING] Processed JSON structure is missing the 'pages' list. Aborting category check.")
        append_module_debug_log("error", {"reason": "missing_pages_array"})
        return {
            "modules_fetched_count": 0,
            "file_prefix": file_prefix
        }
            
    if not processed_json['pages']:
        print("Skipping category check as no pages were found to process.")
        append_module_debug_log("error", {"reason": "empty_pages_array"})
        return {
            "modules_fetched_count": 0,
            "file_prefix": file_prefix
        }

    # print(f"Module Processor: Attempting to fetch modules from {target_url}...")
    
    # Log initialization
    append_module_debug_log("module_processing_start", {
        "file_prefix": file_prefix,
        "target_url": target_url,
        "site_id": site_id,
        "total_pages_to_check": len(all_page_names),
        "page_names": all_page_names
    })
    
    # 5. Call the API to get the category list
    api_result: Union[List[Dict[str, Any]], Dict[str, Any]] = GetPageCategoryList(target_url, headers)
    
    # --- CRITICAL: Robust Error Handling for API Result ---
    if not isinstance(api_result, list):
        # If it's not a list, we assume it's the error dictionary (or corrupted data)
        if isinstance(api_result, dict) and 'error' in api_result:
            error_type = api_result.get('error', 'Unknown Error')
            details = api_result.get('details', 'No details provided.')
            status_code = api_result.get('status_code', 'N/A')
            
            append_module_debug_log("api_error", {
                "error_type": error_type,
                "details": details,
                "status_code": status_code
            })
            
            raise RuntimeError(f"API Call to GetPageCategoryList Failed (Status: {status_code}). Error: {error_type}. Details: {details}")
        else:
            # Handle the case where the data is not a list OR an expected error dictionary
            append_module_debug_log("api_error", {
                "error": "unexpected_data_type",
                "received_type": str(type(api_result))
            })
            raise RuntimeError(f"API returned an unexpected data type ({type(api_result)}). Expected List or Error Dict.")

    module_list = api_result
    append_module_debug_log("api_success", {
        "total_modules_fetched": len(module_list),
        "modules": [{"CategoryId": m.get('CategoryId'), "CategoryName": m.get('CategoryName')} for m in module_list]
    })
    
    # 6. Logic: Search for ALL page names in the retrieved modules and map the results
    # print("\n--- Category Matching and ID Retrieval Process ---")
    
    # Create a dictionary for efficient fuzzy lookup: normalized_name -> category_object (with ID)
    normalized_category_map: Dict[str, Dict[str, Any]] = {}
    for module in module_list:
        category_name = module.get('CategoryName')
        category_id = module.get('CategoryId')
        if category_name and category_id is not None:
            normalized_name = normalize_page_name(category_name)
            normalized_category_map[normalized_name] = {
                'CategoryId': category_id,
                'CategoryName': category_name
            }

    pages_updated = 0
    matched_pages = []
    not_matched_pages = []
    
    # Iterate directly over the page objects in the processed_json so we can modify them
    print(f"\n[DEBUG] Starting to iterate through {len(processed_json['pages'])} page(s) in processed_json...")
    
    for idx, page in enumerate(processed_json['pages'], 1):
        page_name = page.get('page_name')
        if not page_name:
            print(f"[DEBUG] Page #{idx}: Skipping - no 'page_name' field")
            continue

        normalized_page_name = normalize_page_name(page_name)
        print(f"[DEBUG] Processing page #{idx}: '{page_name}' (Normalized: '{normalized_page_name}')")
        
        # print(f"\n[INFO] Checking Page Name: '{page_name}' (Normalized: '{normalized_page_name}')")

        # Look up category info using the normalized name
        category_info = normalized_category_map.get(normalized_page_name)

        # If exact match not found, try partial matching (e.g., "meetingsandevents" contains "meetings")
        if not category_info:
            for normalized_cat_name, cat_info in normalized_category_map.items():
                # Check if the page name contains the category name or vice versa
                if normalized_cat_name in normalized_page_name or normalized_page_name in normalized_cat_name:
                    # Prefer shorter match (category name should be shorter)
                    if len(normalized_cat_name) <= len(normalized_page_name):
                        category_info = cat_info
                        print(f"[DEBUG] Partial match found: '{page_name}' contains category '{cat_info['CategoryName']}'")
                        append_module_debug_log("partial_match_found", {
                            "page_name": page_name,
                            "normalized_page_name": normalized_page_name,
                            "matched_category_name": cat_info['CategoryName'],
                            "matched_category_id": cat_info['CategoryId']
                        })
                        break

        if category_info:
            # MATCH FOUND: Extract ID and update the page object
            category_id = category_info['CategoryId']
            category_name_api = category_info['CategoryName']

            # CRITICAL: This updates the page object in the main processed_json dict
            page['category_info'] = {
                'CategoryId': category_id,
                'CategoryName': category_name_api,
                'match_type': 'fuzzy_name_match'
            }
            pages_updated += 1
            matched_pages.append({
                'page_name': page_name,
                'category_id': category_id,
                'category_name': category_name_api
            })
            
            append_module_debug_log("page_match_found", {
                "page_name": page_name,
                "normalized_page_name": normalized_page_name,
                "category_id": category_id,
                "category_name": category_name_api
            })
            
            # print("[SUCCESS] match found") 
            # print(f"[SUCCESS] FOUND: Page '{page_name}' matches Category ID {category_id} ('{category_name_api}'). Category ID attached to page object.")
        else:
            not_matched_pages.append(page_name)
            print(f"[ERROR] NOT FOUND: Page '{page_name}' does not match an existing Category.")
            
            append_module_debug_log("page_match_not_found", {
                "page_name": page_name,
                "normalized_page_name": normalized_page_name
            })
            
            # Call the creation function if no match is found
            created_category_id = createCategory(page_name, site_id, target_url, headers)
            
            # If category was successfully created, update the page with the new category info
            if created_category_id:
                page['category_info'] = {
                    'CategoryId': created_category_id,
                    'CategoryName': page_name,
                    'match_type': 'newly_created'
                }
                pages_updated += 1
                matched_pages.append({
                    'page_name': page_name,
                    'category_id': created_category_id,
                    'category_name': page_name
                })
                # Remove from not_matched list since we created it
                not_matched_pages.remove(page_name)
        
    # 7. Final step: Save the updated JSON data back to disk
    if pages_updated > 0 and processed_json:
        print(f"\n[INFO] Updating JSON files with {pages_updated} new category ID(s)...")
        
        # Separate home pages from inner pages and save to respective files
        home_pages = [p for p in processed_json['pages'] if p.get('level') == 0 or p.get('page_name') == 'Home Page']
        inner_pages = [p for p in processed_json['pages'] if p.get('level') != 0 and p.get('page_name') != 'Home Page']
        
        # Save inner pages to main simplified JSON
        if inner_pages:
            inner_json = {'title': processed_json.get('title', ''), 'pages': inner_pages}
            save_processed_json(file_prefix, inner_json)
        
        # Save home pages to home simplified JSON
        if home_pages:
            base_prefix = os.path.basename(file_prefix)
            home_simplified_filepath = os.path.join(UPLOAD_FOLDER, f"{base_prefix}_home_simplified.json")
            home_json = {'title': processed_json.get('title', ''), 'pages': home_pages}
            try:
                with open(home_simplified_filepath, "w", encoding="utf-8") as f:
                    json.dump(home_json, f, indent=4, ensure_ascii=False)
                print(f"[DEBUG] Saved home page JSON to: {home_simplified_filepath}")
            except Exception as e:
                print(f"[ERROR] Could not save home page JSON: {e}")
    elif processed_json:
        print("No new category information was added to the processed JSON, skipping save.")

    print(f"\n--- API Fetch Results ---")
    print(f"Total items fetched: {len(module_list)}")
    print("--------------------------\n")
    
    # Log summary to debug file
    append_module_debug_log("matching_summary", {
        "matched_pages": matched_pages,
        "not_matched_pages": not_matched_pages,
        "total_matched": len(matched_pages),
        "total_not_matched": len(not_matched_pages),
        "total_pages_checked": len(all_page_names)
    })
    
    # Print separate lists for matched and not matched pages
    print(f"\n=== MATCH FOUND IN CATEGORY ===")
    if matched_pages:
        print(f"Total: {len(matched_pages)} page(s)")
        for idx, match in enumerate(matched_pages, 1):
            print(f"  {idx}. '{match['page_name']}' -> Category ID: {match['category_id']} ('{match['category_name']}')")
    else:
        print("  No pages matched existing categories.")
    
    print(f"\n=== MATCH NOT FOUND IN CATEGORY ===")
    if not_matched_pages:
        print(f"Total: {len(not_matched_pages)} page(s)")
        for idx, page_name in enumerate(not_matched_pages, 1):
            print(f"  {idx}. '{page_name}'")
    else:
        print("  All pages matched existing categories.")
    
    print("=" * 40 + "\n")
    print(f"[DEBUG] Module processing debug log saved to: {MODULE_DEBUG_LOG_FILE}\n")
    
    print("\n[INFO] Site module processing completed. Continuing to next step...")
    
    return {
        "modules_fetched_count": len(module_list),
        "pages_checked_count": len(all_page_names),
        "pages_updated_with_category_id": pages_updated,
        "file_prefix": file_prefix # Continue propagating the prefix
    }