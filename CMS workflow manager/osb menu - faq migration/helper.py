import os
import json
import uuid
import requests
import copy
import time
import logging
import zipfile
from datetime import datetime
from apis import generate_cms_token,menu_download_api,getComponentInfo,export_mi_block_component,CreateComponentRecord,addUpdateRecordsToCMS
from typing import Dict, Any, List, Tuple
SETTINGS_FILE = "input/settings.json"
from urllib.parse import urlparse

def load_settings():
    """Loads settings from the settings.json file."""
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as f:
                return json.load(f)
        except (IOError, json.JSONDecodeError) as e:
            print(f"Error loading settings file: {e}")
            return {}
    return {}

def load_json_data(file_path: str) -> Dict[str, Any]:
    """Placeholder for safely loading JSON data."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        # LOGGING THE FAILURE HERE IS CRITICAL
        logging.error(f"Failed to load JSON from {file_path}: {e}")
        # MOCKING: Only return mock data if required by the test, otherwise return {}
        if "MiBlockComponentConfig.json" in file_path:
            return {} # If the file fails to load, return an empty but safe dict
        return {}

def login_token_generator():
    """
    Loads site details from settings.json, generates CMS tokens,
    and saves the tokens back to the settings.json file.
    """
    print("Generating login token...")
    settings = load_settings()
    if not settings:
        print("Could not load settings. Aborting token generation.")
        return False
    source_url = settings.get("source_site_url")
    parsed = urlparse(source_url)
    source_url = f"{parsed.scheme}://{parsed.netloc}"

    destination_url = settings.get("destination_site_url")
    source_profile_alias = settings.get("source_profile_alias")
    destination_profile_alias = settings.get("destination_profile_alias")
    if not all([source_url, destination_url, source_profile_alias, destination_profile_alias]):
        print("Error: Incomplete site configuration in settings.json.")
        return False
    token_data_destination = generate_cms_token(destination_url, destination_profile_alias)
    token_data_source = generate_cms_token(source_url, source_profile_alias)
    settings["source_token"] = token_data_source
    settings["destination_token"] = token_data_destination
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings, f, indent=4)
        print("Tokens successfully saved to settings.json.")
        return True
    except IOError as e:
        print(f"Error saving settings file: {e}")
        return False

# ----------------- Updated Payload Mapper Function ----------------- #


def payload_mapper():
    """
    Reads a complex, nested JSON input file and maps it to a simplified
    payload format using a mapping file, including Level 3 (ItemPrices/ItemAddons).
    """
    print("Mapping payload...")
    SETTINGS_FILE = "input/settings.json"
    settings = load_settings()
    source_site_id = settings.get("source_site_id")

    if not source_site_id:
        print("Error: 'source_site_id' not found in settings.")
        return None

    # Load the mapping configuration from the root folder
    mapper = load_json_data("input/field-mapper.json")
    if not mapper:
        print("Could not load mapping data from field-mapper.json. Aborting.")
        return None

    # Construct the file path for the source data
    input_file_path = os.path.join("output", str(source_site_id), "api_response_input.json")

    # Load the source data
    source_data = load_json_data(input_file_path)

    if not source_data:
        print(f"Could not load data from {input_file_path}")
        return None

    mapped_payload = []

    # Iterate through each Menu in the source data
    for source_menu in source_data:
        mapped_menu = {}
        # Dynamically map level 0 fields
        for dest_key, src_key in mapper.get("level 0", {}).items():
            mapped_menu[dest_key] = source_menu.get(src_key)

        mapped_menu["MenuSections"] = []

        # Iterate through each Section within the Menu
        source_sections = source_menu.get("Sections", [])
        for source_section in source_sections:
            mapped_section = {}
            # Dynamically map level 1 fields
            for dest_key, src_key in mapper.get("level 1", {}).items():
                mapped_section[dest_key] = source_section.get(src_key)

            mapped_section["MenuItems"] = []

            # Iterate through each Item within the Section
            source_items = source_section.get("Items", [])
            for source_item in source_items:
                mapped_item = {}
                # Dynamically map level 2 fields
                for dest_key, src_key in mapper.get("level 2", {}).items():
                    mapped_item[dest_key] = source_item.get(src_key)

                # --- NEW LEVEL 3 MAPPING ---

                # 1. Map ItemPrices (New Level 3)
                mapped_item["ItemPrices"] = []
                price_mapper = mapper.get("level 3_prices", {}) # Use a distinct key in the mapper
                source_prices = source_item.get("ItemPrices", [])
                for source_price in source_prices:
                    mapped_price = {}
                    for dest_key, src_key in price_mapper.items():
                        mapped_price[dest_key] = source_price.get(src_key)
                    mapped_item["ItemPrices"].append(mapped_price)

                # 2. Map ItemAddons (New Level 3)
                mapped_item["ItemAddons"] = []
                addon_mapper = mapper.get("level 3_addons", {}) # Use a distinct key in the mapper
                source_addons = source_item.get("ItemAddons", [])
                for source_addon in source_addons:
                    mapped_addon = {}
                    for dest_key, src_key in addon_mapper.items():
                        mapped_addon[dest_key] = source_addon.get(src_key)
                    mapped_item["ItemAddons"].append(mapped_addon)

                # --- END NEW LEVEL 3 MAPPING ---

                # Add the mapped item to the section's list
                mapped_section["MenuItems"].append(mapped_item)

            # Add the mapped section to the menu's list
            mapped_menu["MenuSections"].append(mapped_section)

        # Add the mapped menu to the final payload list
        mapped_payload.append(mapped_menu)

    # Save the mapped payload to a new output file
    output_dir = os.path.join("output", str(source_site_id))
    os.makedirs(output_dir, exist_ok=True) # Ensure directory exists
    output_file_path = os.path.join(output_dir, "api_response_output.json")

    try:
        with open(output_file_path, "w") as f:
            json.dump(mapped_payload, f, indent=4)
        print(f"Payload mapping completed and saved to: {output_file_path}")
        return True
    except IOError as e:
        print(f"Error saving mapped payload to {output_file_path}: {e}")
        return False








def payload_creator():
    """
    Handles the entire payload processing pipeline, by creating a new nested
    JSON structure based on the mapped data and saving the final payload, 
    now including ItemPrices and ItemAddons (Level 3).
    """
    print("Starting final payload creation...")
    settings = load_settings()
    source_site_id = settings.get("source_site_id")

    if not source_site_id:
        print("Error: 'source_site_id' not found in settings. Aborting.")
        return False

    # Load the template file
    template_file_path = "input/payload-input-sample.json"
    template = load_json_data(template_file_path)
    if not template:
        print(f"Could not load template from {template_file_path}. Aborting.")
        return False

    # Load the already mapped data from the previous step
    mapped_data_path = os.path.join("output", str(source_site_id), "api_response_output.json")
    mapped_data = load_json_data(mapped_data_path)
    if not mapped_data:
        print(f"Could not load mapped data from {mapped_data_path}. Aborting.")
        return None

    # --- TEMPLATE EXTRACTION (Updated to include Level 3) ---
    
    # Get the component names from the template
    menu_component_name = template.get("level 0", {}).get("componentName")
    section_component_name = template.get("level 1", {}).get("componentName")
    item_component_name = template.get("level 2", {}).get("componentName")
    
    # New Level 3 Component Names
    price_component_name = template.get("level 3_prices", {}).get("componentName")
    addon_component_name = template.get("level 3_addons", {}).get("componentName")

    # Extract record templates from the payload-input-sample.json file
    menu_template = template.get("level 0", {}).get("recordList", [{}])[0].get("recordJsonString", {})
    section_template = template.get("level 1", {}).get("recordList", [{}])[0].get("recordJsonString", {})
    item_template = template.get("level 2", {}).get("recordList", [{}])[0].get("recordJsonString", {})
    
    # New Level 3 Templates
    price_template = template.get("level 3_prices", {}).get("recordList", [{}])[0].get("recordJsonString", {})
    addon_template = template.get("level 3_addons", {}).get("recordList", [{}])[0].get("recordJsonString", {})
    
    # Initialize final payload structure as a list
    final_payload = []
    
    # --- PROCESSING LOGIC (Updated to include Level 3) ---

    # Process each menu from the mapped data (Level 0)
    for menu_data in mapped_data:
        # ... (Menu creation logic remains the same) ...
        menu_record_id = str(uuid.uuid4())
        
        # Build the payload for the current menu by creating a new dictionary
        menu_record_json = {}
        for key in menu_template:
            menu_record_json[key] = menu_data.get(key, None)

        menu_output = {
            "recordJsonString": menu_record_json,
            "ParentRecordId": "",
            "ParentComponentId": "",
            "MainParentComponentid": "",
            "status":"", 
            "componentName": menu_component_name,
            "MenuSections": []
        }

        # Process each section (Level 1)
        for section_data in menu_data.get("MenuSections", []):
            section_record_id = str(uuid.uuid4())
            
            # Build the payload for the current section
            section_record_json = {}
            for key in section_template:
                section_record_json[key] = section_data.get(key, None)

            section_output = {
                "recordJsonString": section_record_json,
                "ParentRecordId": "",
                "ParentComponentId": "",
                "MainParentComponentid": "",
                "componentName": section_component_name,
                "status":"", 
                "MenuItems": []
            }

            # Process each item (Level 2)
            for item_data in section_data.get("MenuItems", []):
                item_record_id = str(uuid.uuid4()) # Generate UUID for the item
                
                # Build the recordJsonString for the current item
                item_record_json = {}
                for key in item_template:
                    item_record_json[key] = item_data.get(key, None)
                
                # Initialize nested arrays for Level 3 inside the item's recordJsonString
                # NOTE: These arrays are placed INSIDE the recordJsonString, assuming
                # the component structure expects the children arrays here.
                item_record_json["ItemPrices"] = []
                item_record_json["ItemAddons"] = []
                
                # --- PROCESS ITEM PRICES (New Level 3) ---
                for price_data in item_data.get("ItemPrices", []):
                    # Build the recordJsonString for the price option
                    price_record_json = {}
                    for key in price_template:
                        price_record_json[key] = price_data.get(key, None)
                    
                    price_output = {
                        "recordJsonString": price_record_json,
                        "ParentRecordId": "", # Parent is the Item
                        "ParentComponentId": "",
                        "MainParentComponentid": "",
                        "componentName": price_component_name 
                    }
                    item_record_json["ItemPrices"].append(price_output)

                # --- PROCESS ITEM ADDONS (New Level 3) ---
                for addon_data in item_data.get("ItemAddons", []):
                    # Build the recordJsonString for the addon option
                    addon_record_json = {}
                    for key in addon_template:
                        addon_record_json[key] = addon_data.get(key, None)
                    
                    addon_output = {
                        "recordJsonString": addon_record_json,
                        "ParentRecordId": "", # Parent is the Item
                        "ParentComponentId": "",
                        "MainParentComponentid": "",
                        "componentName": addon_component_name 
                    }
                    item_record_json["ItemAddons"].append(addon_output)

                # Final Item Output structure
                item_output = {
                    "recordJsonString": item_record_json,
                    "ParentRecordId": "", # Parent is the Section
                    "ParentComponentId": "",
                    "MainParentComponentid": "",
                    "componentName": item_component_name
                }
                section_output["MenuItems"].append(item_output)
            
            menu_output["MenuSections"].append(section_output)
        
        final_payload.append(menu_output)

    # Save the final payload to a new output file
    output_dir = os.path.join("output", str(source_site_id))
    output_file_path = os.path.join(output_dir, "api_response_final.json")
    
    try:
        os.makedirs(output_dir, exist_ok=True)
        with open(output_file_path, "w") as f:
            json.dump(final_payload, f, indent=4)
        print(f"Final payload created and saved to: {output_file_path}")
        return True
    except IOError as e:
        print(f"Error saving final payload to {output_file_path}: {e}")
        return False




    
# def add_menu_data(payload, token):
#     """
#     Fetches the 'Menu' component, exports it, saves the extracted files, 
#     and creates a ComponentName-to-ComponentId map, saving the map one level up 
#     in the 'output/[site_id]' folder.
#     """
#     settings = load_settings()
    
#     if not settings:
#         print("Settings could not be loaded. Aborting process.")
#         return None
    
#     source_site_id = settings.get("source_site_id")
#     destination_site_url = settings.get("destination_site_url")
#     destination_site_id = settings.get("destination_site_id")
#     destination_token = settings.get("destination_token", {}).get("token")
    
#     headers = {
#         'Content-Type': 'application/json',
#         'ms_cms_clientapp': 'ProgrammingApp',
#         'Authorization': f'Bearer {destination_token}',
#     }
#     print("in here")

#     responseData = getComponentInfo("Menu", destination_site_url, headers)
#     print(responseData)

#     if not responseData or not isinstance(responseData, list) or len(responseData) == 0:
#         print("Invalid response from getComponentInfo.")
#         return None

#     component_id = responseData[0].get('Id')
#     if not component_id:
#         print("Component ID not found in API response.")
#         return None
    
#     print(f"Found component ID: {component_id}")

#     response_content, content_disposition = export_mi_block_component(destination_site_url, component_id, destination_site_id, headers)
    
#     if not response_content:
#         print("Export failed, no content received.")
#         return None
        
#     miBlockId = component_id
#     timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
#     mi_block_folder = f"mi-block-ID-{miBlockId}"
#     output_dir = os.path.join("output", str(source_site_id)) 
#     save_folder = os.path.join(output_dir, mi_block_folder)
#     os.makedirs(save_folder, exist_ok=True)
    
#     filename = (
#         content_disposition.split('filename=')[1].strip('"')
#         if content_disposition and 'filename=' in content_disposition
#         else f"site_{source_site_id}.zip"
#     )
    
#     file_path = os.path.join(save_folder, filename)

#     try:
#         with open(file_path, "wb") as file:
#             file.write(response_content)

#         if zipfile.is_zipfile(file_path):
#             with zipfile.ZipFile(file_path, 'r') as zip_ref:
#                 zip_ref.extractall(save_folder)
#             os.remove(file_path)

#             for extracted_file in os.listdir(save_folder):
#                 extracted_file_path = os.path.join(save_folder, extracted_file)
#                 if extracted_file.endswith('.txt'):
#                     new_file_path = os.path.splitext(extracted_file_path)[0] + '.json'
#                     try:
#                         with open(extracted_file_path, 'r', encoding="utf-8") as txt_file:
#                             content = txt_file.read()
#                             json_content = json.loads(content)
#                             with open(new_file_path, 'w', encoding="utf-8") as json_file:
#                                 json.dump(json_content, json_file, indent=4)
#                             os.remove(extracted_file_path)
#                     except (json.JSONDecodeError, OSError) as e:
#                         logging.error(f"⚠️ Error processing file {extracted_file_path}: {e}")

#         # -----------------------------------------------------------------
#         # 🌟 NEW LOGIC: Create Component Name to ID and ParentId Map with MainParentComponentid
#         # -----------------------------------------------------------------
#         config_file_name = "MiBlockComponentConfig.json"
#         config_file_path = os.path.join(save_folder, config_file_name)
        
#         name_to_id_map = {}
#         main_parent_id = None # Initialize main parent ID
        
#         if os.path.exists(config_file_path):
#             print(f"Reading {config_file_name} to create map...")
#             with open(config_file_path, 'r', encoding='utf-8') as f:
#                 config_data = json.load(f)
            
#             component_list = config_data.get('component', [])

#             # First, find the component with a null ParentId to get the main parent ID
#             for component in component_list:
#                 if component.get('ParentId') is None:
#                     main_parent_id = component.get('ComponentId')
#                     break # Found it, so we can exit the loop
            
#             # Now, iterate again to build the final map with the main parent ID
#             for component in component_list:
#                 name = component.get('ComponentName')
#                 component_id = component.get('ComponentId')
#                 parent_id = component.get('ParentId')
                
#                 if name and component_id is not None:
#                     name_to_id_map[name] = {
#                         "ComponentId": component_id,
#                         "ParentId": parent_id,
#                         "MainParentComponentid": main_parent_id
#                     }
            
#             map_file_path = os.path.join(output_dir, "component_name_id_map.json") 
            
#             with open(map_file_path, 'w', encoding='utf-8') as f:
#                 json.dump(name_to_id_map, f, indent=4)
                
#             print(f"✅ Created component name map and saved to: {map_file_path}")
#         else:
#             logging.warning(f"⚠️ {config_file_name} not found at {config_file_path}. Cannot create component map.")

#         # -----------------------------------------------------------------
        
#         return mi_block_folder

#     except Exception as e:
#         logging.error(f"❌ Unexpected error during file processing: {e}")
#         return None



# def update_payload_with_component_ids(payload_data, component_map, main_parent_id):
#     """
#     Recursively updates the ParentComponentId and MainParentComponentid 
#     in the payload structure using the component name map.
#     (Implementation from previous response)
#     """
#     if isinstance(payload_data, list):
#         return [update_payload_with_component_ids(item, component_map, main_parent_id) for item in payload_data]

#     if isinstance(payload_data, dict):
#         component_name = payload_data.get("componentName")
        
#         payload_data["MainParentComponentid"] = main_parent_id

#         if component_name and component_name in component_map:
#             component_info = component_map[component_name]
            
#             payload_data["ComponentId"] = component_info.get("ComponentId")

#             parent_id_from_map = component_info.get("ParentId")
#             if parent_id_from_map is not None:
#                 payload_data["ParentComponentId"] = parent_id_from_map
#             else:
#                  payload_data["ParentComponentId"] = ""
        
#         for key in ["MenuSections", "MenuItems", "ItemPrices", "ItemAddons"]:
#             if key in payload_data and isinstance(payload_data[key], list):
#                 payload_data[key] = update_payload_with_component_ids(payload_data[key], component_map, main_parent_id)

#     return payload_data



import json

def update_payload_with_component_ids(payload_data, component_map, main_parent_id=None):
    """
    Recursively update ComponentId, ParentComponentId, and MainParentComponentid
    for all components in a Menu payload.
    """
    if isinstance(payload_data, list):
        return [update_payload_with_component_ids(item, component_map, main_parent_id) for item in payload_data]

    if isinstance(payload_data, dict):
        component_name = payload_data.get("componentName")
        
        # --- Update IDs if componentName exists ---
        if component_name:
            # MainParentComponentid should propagate from top-level Menu
            if main_parent_id is not None:
                payload_data["MainParentComponentid"] = main_parent_id
            
            # Update ComponentId and ParentComponentId from map if exists
            if component_name in component_map:
                info = component_map[component_name]
                payload_data["ComponentId"] = info.get("ComponentId", payload_data.get("ComponentId", ""))
                payload_data["ParentComponentId"] = info.get("ParentId", payload_data.get("ParentComponentId", ""))

        # Determine the main_parent_id to pass to children
        new_main_parent_id = payload_data.get("MainParentComponentid", main_parent_id)

        # --- Keys to recurse into ---
        nested_keys = ["MenuSections", "MenuItems", "ItemPrices", "ItemAddons"]
        for key in nested_keys:
            if key in payload_data:
                payload_data[key] = update_payload_with_component_ids(payload_data[key], component_map, new_main_parent_id)

        # --- Recurse into recordJsonString if it's a dict ---
        rjs = payload_data.get("recordJsonString")
        if isinstance(rjs, dict):
            payload_data["recordJsonString"] = update_payload_with_component_ids(rjs, component_map, new_main_parent_id)

    return payload_data



    
# --- End of External Function Definitions ---

# def reset_display_orders(data):
#     """
#     Recursively traverses the menu structure (a list of siblings),
#     sorts each sibling list in ascending order of its existing 'displayorder', 
#     and then resets the 'displayorder' field for each sibling list, starting from 1.

#     :param data: A list of sibling menu components (e.g., all MenuSections for a single Menu).
#     :return: The list with updated display orders.
#     """
#     if not isinstance(data, list) or not data:
#         # Base case: not a list or an empty list, nothing to reorder
#         return data

#     # --- NEW LOGIC: Sort the list of siblings first ---
#     try:
#         # Sort the siblings based on the current 'displayorder' value
#         # We use a lambda function to safely access the 'displayorder'
#         # The key extracts component['recordJsonString']['displayorder'] if it exists,
#         # otherwise, it defaults to a large number to push unorderable items to the end.
#         data.sort(key=lambda component: 
#                   component.get('recordJsonString', {}).get('displayorder', float('inf')))
        
#     except Exception as e:
#         # Handle cases where sorting might fail unexpectedly (e.g., if displayorder is not an int)
#         # You might want to log this error, but continue with re-indexing.
#         print(f"Warning: Failed to sort sibling list. Continuing with existing order. Error: {e}")
#         pass
#     # --------------------------------------------------

#     # 1. Reset displayorder for the current list of components (siblings)
#     for index, component in enumerate(data):
        
#         # The 'displayorder' is located within 'recordJsonString' for the main structural levels
#         if 'recordJsonString' in component and 'displayorder' in component['recordJsonString']:
#             # Resetting displayorder to be 1-based index (1, 2, 3...)
#             # This is where the new, sorted order is assigned.
#             component['recordJsonString']['displayorder'] = index + 1
#         # NOTE: This logic applies to Menu, Menu Section, Menu Item, etc.

#         # 2. Recursively process nested lists (children)

#         # Level 1: Menu Sections (inside Menu)
#         if 'MenuSections' in component and isinstance(component['MenuSections'], list):
#             component['MenuSections'] = reset_display_orders(component['MenuSections'])
        
#         # Level 2: Menu Items (inside Menu Section)
#         if 'MenuItems' in component and isinstance(component['MenuItems'], list):
#             component['MenuItems'] = reset_display_orders(component['MenuItems'])
            
#         # Level 3: Item Prices & Addons (inside Menu Item's recordJsonString)
#         if 'recordJsonString' in component:
#             record_data = component['recordJsonString']
            
#             # Recurse into ItemPrices
#             if 'ItemPrices' in record_data and isinstance(record_data['ItemPrices'], list):
#                     # Price Options and Addons are nested one level deeper in recordJsonString
#                     record_data['ItemPrices'] = reset_display_orders(record_data['ItemPrices'])
            
#             # Recurse into ItemAddons
#             if 'ItemAddons' in record_data and isinstance(record_data['ItemAddons'], list):
#                 record_data['ItemAddons'] = reset_display_orders(record_data['ItemAddons'])
            
#     return data


# --- End of External Function Definitions ---
# --- End of External Function Definitions ---

def reset_display_orders(data):
    """
    Recursively traverses the menu structure (a list of siblings),
    sorts each sibling list, re-indexes the 'displayorder', 
    and sets 'EnableClientEdit': True as a sibling to recordJsonString for every component.

    :param data: A list of sibling menu components (e.g., all MenuSections for a single Menu).
    :return: The list with updated display orders and EnableClientEdit status.
    """
    if not isinstance(data, list) or not data:
        # Base case: not a list or an empty list, nothing to reorder
        return data

    # --- Sorting Logic for the current level (Siblings) ---
    try:
        # Sort the siblings based on the current 'displayorder' value
        data.sort(key=lambda component: 
                  component.get('recordJsonString', {}).get('displayorder', float('inf')))
        
    except Exception as e:
        print(f"Warning: Failed to sort sibling list. Continuing with existing order. Error: {e}")
        pass
    # ------------------------------------------------------

    # 1. Reset displayorder and update EnableClientEdit for the current list of components (siblings)
    for index, component in enumerate(data):
        
        # Check if recordJsonString exists (since the components you are dealing 
        # with are likely data records).
        if 'recordJsonString' in component and isinstance(component['recordJsonString'], dict):
            
            # ----------------------------------------------------------------------
            # ✅ CORRECT LOCATION: Set EnableClientEdit as a sibling to recordJsonString.
            # This is the component dictionary itself (e.g., the item in recordList).
            # ----------------------------------------------------------------------
            component['EnableClientEdit'] = True
            
            # Now handle the displayorder (which is inside recordJsonString)
            record_data = component['recordJsonString']
            
            if 'displayorder' in record_data:
                # Resetting displayorder to be 1-based index (1, 2, 3...)
                record_data['displayorder'] = index + 1
        
        # 2. Recursively process nested lists (children)

        # Level 1: Menu Sections (inside Menu)
        if 'MenuSections' in component and isinstance(component['MenuSections'], list):
            component['MenuSections'] = reset_display_orders(component['MenuSections'])
        
        # Level 2: Menu Items (inside Menu Section)
        if 'MenuItems' in component and isinstance(component['MenuItems'], list):
            component['MenuItems'] = reset_display_orders(component['MenuItems'])
            
        # Level 3: Item Prices & Addons (inside Menu Item's recordJsonString)
        # Note: We must check for recordJsonString *again* here to access the lists inside it.
        if 'recordJsonString' in component:
            record_data = component['recordJsonString']
            
            # Recurse into ItemPrices
            if 'ItemPrices' in record_data and isinstance(record_data['ItemPrices'], list):
                    # Price Options and Addons are nested one level deeper in recordJsonString
                    record_data['ItemPrices'] = reset_display_orders(record_data['ItemPrices'])
            
            # Recurse into ItemAddons (with existing validation/clearing logic)
            if 'ItemAddons' in record_data and isinstance(record_data['ItemAddons'], list):
                
                # Check for null/blank item-add-on-name and clear the list
                addons_list = record_data['ItemAddons']
                should_clear_addons = False
                
                for addon in addons_list:
                    # Safely get the addon name
                    addon_name = addon.get('recordJsonString', {}).get('item-add-on-name')
                    
                    # Check if the name is None or is a string that is blank/empty after stripping whitespace
                    if addon_name is None or (isinstance(addon_name, str) and not addon_name.strip()):
                        should_clear_addons = True
                        break
                
                if should_clear_addons:
                    # If any addon is invalid, clear the entire ItemAddons list
                    record_data['ItemAddons'] = []
                else:
                    # If all addons are valid, proceed with sorting and re-indexing
                    record_data['ItemAddons'] = reset_display_orders(record_data['ItemAddons'])
            
    return data


def update_display_orders_in_payload(file_path):
    """
    Loads the JSON payload, resets all 'displayorder' values recursively 
    starting from 1 for sibling items, and saves the file back.
    
    :param file_path: The path to the api_response_final.json file.
    :return: True if the operation was successful, False otherwise.
    """
    print(f"\n🌟 Starting display order update for: {file_path}...")
    
    data = load_json_data(file_path)
    
    if not data:
        logging.error(f"❌ Failed to load data from {file_path} for display order update.")
        return False

    try:
        # The top-level data is the list of Menu components (Level 0 siblings)
        updated_data = reset_display_orders(data)
        
        # Save the updated data back to the file
        with open(file_path, "w", encoding='utf-8') as f:
            json.dump(updated_data, f, indent=4)
            
        print(f"✅ Display orders successfully updated and saved to {file_path}.")
        return True
        
    except Exception as e:
        logging.error(f"❌ Error during display order update/save: {e}")
        return False




# def preprocess_menu_data(payload, token):
#     """
#     Fetches the 'Menu' component, exports it, saves the extracted files, 
#     creates the component map, and as the last step, updates the 
#     api_response_final.json with component IDs.
#     """
#     settings = load_settings()
    
#     if not settings:
#         print("Settings could not be loaded. Aborting process.")
#         return None
    
#     source_site_id = settings.get("source_site_id")
#     destination_site_url = settings.get("destination_site_url")
#     destination_site_id = settings.get("destination_site_id")
#     destination_token = settings.get("destination_token", {}).get("token")
    
#     headers = {
#         'Content-Type': 'application/json',
#         'ms_cms_clientapp': 'ProgrammingApp',
#         'Authorization': f'Bearer {destination_token}',
#     }
#     print("in here")

#     responseData = getComponentInfo("Menu", destination_site_url, headers)
    
#     if not responseData or not isinstance(responseData, list) or len(responseData) == 0:
#         print("Invalid response from getComponentInfo.")
#         return None

#     component_id = responseData[0].get('Id')
#     if not component_id:
#         print("Component ID not found in API response.")
#         return None
    
#     print(f"Found component ID: {component_id}")

#     # --- Start of the file export/extraction/map creation logic ---
    
#     response_content, content_disposition = export_mi_block_component(
#         destination_site_url, component_id, destination_site_id, headers
#     )
    
#     miBlockId = component_id
#     mi_block_folder = f"mi-block-ID-{miBlockId}"
#     output_dir = os.path.join("output", str(source_site_id)) 
#     save_folder = os.path.join(output_dir, mi_block_folder)
#     payload_file_path = os.path.join(output_dir, "api_response_final.json") 
#     # Ensure folder structure exists
#     os.makedirs(save_folder, exist_ok=True)
    
#     # Wrap the entire file-system manipulation block in a try/except for robustness
#     try:
#         # 1. Save and Unzip the exported file (Skipped if using mock 'None' content)
#         if response_content:
#             filename = (
#                 content_disposition.split('filename=')[1].strip('"')
#                 if content_disposition and 'filename=' in content_disposition
#                 else f"site_{source_site_id}.zip"
#             )
#             file_path = os.path.join(save_folder, filename)

#             with open(file_path, "wb") as file:
#                 file.write(response_content)

#             if zipfile.is_zipfile(file_path):
#                 with zipfile.ZipFile(file_path, 'r') as zip_ref:
#                     zip_ref.extractall(save_folder)
#                 os.remove(file_path)
#         else:
#             logging.info("Skipping file save/unzip as export_mi_block_component returned no content.")

#         time.sleep(15)
#         # 2. Convert .txt files to .json (if they exist)
#         for extracted_file in os.listdir(save_folder):
#             extracted_file_path = os.path.join(save_folder, extracted_file)
#             if extracted_file.endswith('.txt'):
#                 new_file_path = os.path.splitext(extracted_file_path)[0] + '.json'
#                 try:
#                     with open(extracted_file_path, 'r', encoding="utf-8") as txt_file:
#                         content = txt_file.read()
#                         json_content = json.loads(content)
#                         with open(new_file_path, 'w', encoding="utf-8") as json_file:
#                             json.dump(json_content, json_file, indent=4)
#                         os.remove(extracted_file_path)
#                 except (json.JSONDecodeError, OSError) as e:
#                     logging.error(f"⚠️ Error processing file {extracted_file_path}: {e}")

#         time.sleep(40)
#         # 3. Create Component Name to ID and ParentId Map
#         config_file_name = "MiBlockComponentConfig.json"
#         config_file_path = os.path.join(save_folder, config_file_name)
        
#         name_to_id_map = {}
#         main_parent_id = None 
        
#         if os.path.exists(config_file_path):
#             print(f"Reading {config_file_name} to create map...")
#             config_data = load_json_data(config_file_path)
            
#             if config_data:
#                 component_list = config_data.get('component', [])

#                 # Find the main parent ID (ParentId is None)
#                 for component in component_list:
#                     if component.get('ParentId') is None:
#                         parent_id_value = component.get('ParentId')
#                         print(parent_id_value)
#                         break

#                 # Build the final map
#                 for component in component_list:
#                     name = component.get('ComponentName')
#                     component_id_val = component.get('ComponentId')
#                     parent_id = component.get('ParentId')
                    
#                     if name and component_id_val is not None:
#                         name_to_id_map[name] = {
#                             "ComponentId": component_id_val,
#                             "ParentId": parent_id,
#                             "MainParentComponentid": main_parent_id # Store the main ID for easy lookup
#                         }
                
#                 map_file_path = os.path.join(output_dir, "component_name_id_map.json") 
                
#                 with open(map_file_path, 'w', encoding='utf-8') as f:
#                     json.dump(name_to_id_map, f, indent=4)
                    
#                 print(f"✅ Created component name map and saved to: {map_file_path}")

#                 # -----------------------------------------------------------------
#                 # 🆕 NEW STEP: Update Display Orders
#                 # -----------------------------------------------------------------
#                 # Call the new function, passing the path to the just-saved file
#                 update_display_orders_in_payload(payload_file_path)
                
#                 time.sleep(2)
#                 add_menu_data()
#             else:
#                  logging.warning(f"⚠️ Failed to load data from {config_file_name}.")
#         else:
#             logging.warning(f"⚠️ {config_file_name} not found at {config_file_path}. Cannot create component map.")
            
#     except Exception as e:
#         logging.error(f"❌ Unexpected error during file processing: {e}")
#         return None
    
#     # --- End of the file export/extraction/map creation logic ---

#     # -----------------------------------------------------------------
#     # 🌟 FINAL STEP: Load, Update, and Save api_response_final.json 
#     # -----------------------------------------------------------------
#     print("\nStarting final component ID update step...")
    
#     # 1. Load the Component Map
#     map_file_path = os.path.join(output_dir, "component_name_id_map.json")
#     component_map = load_json_data(map_file_path)
    
#     if not component_map:
#         logging.error(f"❌ Cannot update payload: Component map not found at {map_file_path}.")
#         return None 
    
#     # 2. Determine Main Parent ID
#     menu_component_info = component_map.get("Menu", {})
#     MAIN_PARENT_COMPONENT_ID = menu_component_info.get("MainParentComponentid")

#     if not MAIN_PARENT_COMPONENT_ID:
#         logging.error("❌ Cannot update payload: Main 'Menu' ComponentId not found in map.")
#         return None
        
#     # 3. Load the Payload to be updated
#     payload_file_name = "api_response_final.json"
#     # 👇 FIX APPLIED HERE: Using output_dir (one level up) 
#     payload_file_path = os.path.join(output_dir, payload_file_name) 
#     initial_payload = load_json_data(payload_file_path)

#     if not initial_payload:
#         logging.error(f"❌ Cannot update payload: Target file {payload_file_name} not found or invalid at {payload_file_path}.")
#         return None
        
#     # 4. Update the Payload
#     updated_payload = update_payload_with_component_ids(initial_payload, component_map, MAIN_PARENT_COMPONENT_ID)
    
#     # 5. Save the Updated Payload
#     try:
#         # Saving back to the same corrected path
#         with open(payload_file_path, "w", encoding='utf-8') as f:
#             json.dump(updated_payload, f, indent=4)
#         print(f"✅ Successfully updated and saved {payload_file_name} to {payload_file_path}")
        
#         # Return the folder name
#         return mi_block_folder 

#     except IOError as e:
#         logging.error(f"❌ Error saving final updated payload to {payload_file_path}: {e}")
#         return None

def preprocess_menu_data(payload: Dict, token: str) -> str | None:
    """
    Fetches the 'Menu' component, exports it, saves the extracted files, 
    creates the component map, and as the last step, updates the 
    api_response_final.json with component IDs.
    """
    settings = load_settings()
    
    if not settings:
        print("Settings could not be loaded. Aborting process.")
        return None
    
    source_site_id = settings.get("source_site_id")
    destination_site_url = settings.get("destination_site_url")
    destination_site_id = settings.get("destination_site_id")
    destination_token = settings.get("destination_token", {}).get("token")
    
    headers = {
        'Content-Type': 'application/json',
        'ms_cms_clientapp': 'ProgrammingApp',
        'Authorization': f'Bearer {destination_token}',
    }
    print("in here")

    responseData = getComponentInfo("Menu", destination_site_url, headers)
    
    if not responseData or not isinstance(responseData, list) or len(responseData) == 0:
        print("Invalid response from getComponentInfo.")
        return None

    component_id = responseData[0].get('Id')
    if not component_id:
        print("Component ID not found in API response.")
        return None
    
    print(f"Found component ID: {component_id}")

    # --- Start of the file export/extraction/map creation logic ---
    
    response_content, content_disposition = export_mi_block_component(
        destination_site_url, component_id, destination_site_id, headers
    )
  
    miBlockId = component_id
    mi_block_folder = f"mi-block-ID-{miBlockId}"
    output_dir = os.path.join("output", str(source_site_id)) 
    save_folder = os.path.join(output_dir, mi_block_folder)
    payload_file_path = os.path.join(output_dir, "api_response_final.json") 
    os.makedirs(save_folder, exist_ok=True)
    
    try:
        # 1. Save and Unzip the exported file 
        if response_content:
            filename = (
                content_disposition.split('filename=')[1].strip('"')
                if content_disposition and 'filename=' in content_disposition
                else f"site_{source_site_id}.zip"
            )
            file_path = os.path.join(save_folder, filename)

            with open(file_path, "wb") as file:
                file.write(response_content)

            if zipfile.is_zipfile(file_path):
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    zip_ref.extractall(save_folder)
                os.remove(file_path)
        else:
            logging.info("Skipping file save/unzip as export_mi_block_component returned no content.")

        # FIX: Minimized delay to prevent timeouts/watchdog interference.
        time.sleep(1) 
        
        # 2. Convert .txt files to .json (if they exist)
        print("--- DEBUG: Starting .txt to .json conversion loop ---")
        
        for extracted_file in os.listdir(save_folder):
            extracted_file_path = os.path.join(save_folder, extracted_file)
            
            # Use inner try/except for resilience against bad files
            try:
                if extracted_file.endswith('.txt'):
                    new_file_path = os.path.splitext(extracted_file_path)[0] + '.json'
                    
                    with open(extracted_file_path, 'r', encoding="utf-8") as txt_file:
                        content = txt_file.read()
                        
                        # DEBUG: Check for empty files
                        if not content.strip():
                            logging.warning(f"⚠️ Skipping empty file: {extracted_file}")
                            os.remove(extracted_file_path)
                            continue
                            
                        json_content = json.loads(content) # CRASH POINT
                        
                        with open(new_file_path, 'w', encoding="utf-8") as json_file:
                            json.dump(json_content, json_file, indent=4)
                        os.remove(extracted_file_path)
                        
            except json.JSONDecodeError as e:
                # DEBUG: Log the content that failed to parse
                logging.error(f"❌ JSON Decode Error in file: {extracted_file_path}. Error: {e}")
                logging.error(f"❌ Invalid content start (first 100 chars): '{content[:100].replace('\n', ' ')}...'")
                # Skip the bad file to allow the rest of the script to run
                continue 
                
            except OSError as e:
                # Catch OS-level errors
                logging.error(f"⚠️ OS Error processing file {extracted_file_path}: {e}")
                continue
                
        print("--- DEBUG: Finished .txt to .json conversion loop ---")
        
        # FIX: Minimized delay.
        time.sleep(1) 
        
        # 3. Create Component Name to ID and ParentId Map
        config_file_name = "MiBlockComponentConfig.json"
        config_file_path = os.path.join(save_folder, config_file_name)
        
        name_to_id_map = {}
        main_parent_id = None 
        
        if os.path.exists(config_file_path):
            print(f"Reading {config_file_name} to create map...")
            config_data = load_json_data(config_file_path)
            
            if config_data:
                component_list = config_data.get('component', [])

                # Find the main parent ID (ParentId is None, 0, or "")
                for component in component_list:
                    parent_id_value = component.get('ParentId')
                    if parent_id_value is None or parent_id_value == 0 or parent_id_value == "":
                        main_parent_id = component.get('ComponentId')
                        print(f"Main Parent ID found: {main_parent_id}")
                        break 

                # Build the final map
                for component in component_list:
                    name = component.get('ComponentName')
                    component_id_val = component.get('ComponentId')
                    parent_id = component.get('ParentId')
                    
                    if name and component_id_val is not None:
                        name_to_id_map[name] = {
                            "ComponentId": component_id_val,
                            "ParentId": parent_id,
                            "MainParentComponentid": main_parent_id
                        }
                
                map_file_path = os.path.join(output_dir, "component_name_id_map.json") 
                
                with open(map_file_path, 'w', encoding='utf-8') as f:
                    json.dump(name_to_id_map, f, indent=4)
                    
                print(f"✅ Created component name map and saved to: {map_file_path}")

                # -----------------------------------------------------------------
                # 🆕 NEW STEP: Update Display Orders
                # -----------------------------------------------------------------
                update_display_orders_in_payload(payload_file_path)
                
                time.sleep(2)
                add_menu_data()
            else:
                logging.warning(f"⚠️ Failed to load data from {config_file_name}.")
        else:
            logging.warning(f"⚠️ {config_file_name} not found at {config_file_path}. Cannot create component map.")
            
    except Exception as e:
        # Catch-all for any other unhandled errors in the file processing block
        logging.error(f"❌ UNEXPECTED MAJOR ERROR during file processing/mapping: {e}", exc_info=True)
        return None
    
    # --- End of the file export/extraction/map creation logic ---

    # -----------------------------------------------------------------
    # 🌟 FINAL STEP: Load, Update, and Save api_response_final.json 
    # -----------------------------------------------------------------
    print("\nStarting final component ID update step...")
    
    # 1. Load the Component Map
    map_file_path = os.path.join(output_dir, "component_name_id_map.json")
    component_map = load_json_data(map_file_path)
    
    if not component_map:
        logging.error(f"❌ Cannot update payload: Component map not found at {map_file_path}.")
        return None 
    
    # 2. Determine Main Parent ID
    menu_component_info = component_map.get("Menu", {})
    MAIN_PARENT_COMPONENT_ID = menu_component_info.get("MainParentComponentid")

    if not MAIN_PARENT_COMPONENT_ID:
        logging.error("❌ Cannot update payload: Main 'Menu' ComponentId not found in map.")
        return None
        
    # 3. Load the Payload to be updated
    payload_file_name = "api_response_final.json"
    payload_file_path = os.path.join(output_dir, payload_file_name) 
    initial_payload = load_json_data(payload_file_path)

    if not initial_payload:
        logging.error(f"❌ Cannot update payload: Target file {payload_file_name} not found or invalid at {payload_file_path}.")
        return None
        
    # 4. Update the Payload
    updated_payload = update_payload_with_component_ids(initial_payload, component_map, MAIN_PARENT_COMPONENT_ID)
    
    # 5. Save the Updated Payload
    try:
        with open(payload_file_path, "w", encoding='utf-8') as f:
            json.dump(updated_payload, f, indent=4)
        print(f"✅ Successfully updated and saved {payload_file_name} to {payload_file_path}")
        
        return mi_block_folder 

    except IOError as e:
        logging.error(f"❌ Error saving final updated payload to {payload_file_path}: {e}")
        return None











# def preprocess_menu_data(payload, token):
#     """
#     Fetches the 'Menu' component, exports it, saves the extracted files, 
#     creates the component map, and as the last step, updates the 
#     api_response_final.json with component IDs.
#     """
#     settings = load_settings()
    
#     if not settings:
#         print("Settings could not be loaded. Aborting process.")
#         return None
    
#     source_site_id = settings.get("source_site_id")
#     destination_site_url = settings.get("destination_site_url")
#     destination_site_id = settings.get("destination_site_id")
#     destination_token = settings.get("destination_token", {}).get("token")
    
#     headers = {
#         'Content-Type': 'application/json',
#         'ms_cms_clientapp': 'ProgrammingApp',
#         'Authorization': f'Bearer {destination_token}',
#     }
#     print("in here")

#     responseData = getComponentInfo("Menu", destination_site_url, headers)
    
#     if not responseData or not isinstance(responseData, list) or len(responseData) == 0:
#         print("Invalid response from getComponentInfo.")
#         return None

#     component_id = responseData[0].get('Id')
#     if not component_id:
#         print("Component ID not found in API response.")
#         return None
#     print("==============================================================================")
#     print(f"Found component ID: {component_id}")
#     print("==============================================================================")
#     # --- Start of the file export/extraction/map creation logic ---
    
#     response_content, content_disposition = export_mi_block_component(
#         destination_site_url, component_id, destination_site_id, headers
#     )
    
#     miBlockId = component_id
#     mi_block_folder = f"mi-block-ID-{miBlockId}"
#     output_dir = os.path.join("output", str(source_site_id)) 
#     save_folder = os.path.join(output_dir, mi_block_folder)
#     payload_file_path = os.path.join(output_dir, "api_response_final.json") 
#     os.makedirs(save_folder, exist_ok=True)
    
#     try:
#         # 1. Save and Unzip the exported file
#         if response_content:
#             # NOTE: Mocked file handling below may need 'requests' or 'zipfile' actual imports/definitions
#             filename = (
#                 content_disposition.split('filename=')[1].strip('"')
#                 if content_disposition and 'filename=' in content_disposition
#                 else f"site_{source_site_id}.zip"
#             )
#             file_path = os.path.join(save_folder, filename)

#             # Mocking file operations since content is mock b''
#             # with open(file_path, "wb") as file:
#             #     file.write(response_content)

#             # if zipfile.is_zipfile(file_path):
#             #     with zipfile.ZipFile(file_path, 'r') as zip_ref:
#             #         zip_ref.extractall(save_folder)
#             #     os.remove(file_path)
            
#             # Simulated actions for the mock:
#             print(f"Simulating export of {filename} and extraction to {save_folder}")
#             # Assume ComponentRecordsTree.txt and MiBlockComponentConfig.txt are now present
#         else:
#             logging.info("Skipping file save/unzip as export_mi_block_component returned no content.")
        
#         # Give OS a moment to finish file operations after unzipping/deleting the zip.
#         time.sleep(2) 
#         print("djsbdbsdbsjkdbsjdsjdsjd=================================")
#         # 2. Convert .txt files to .json (if they exist)
#         for extracted_file in os.listdir(save_folder):
#             extracted_file_path = os.path.join(save_folder, extracted_file)
#             if extracted_file.endswith('.txt'):
#                 new_file_path = os.path.splitext(extracted_file_path)[0] + '.json'
#                 try:
#                     # Read and process content inside the 'with' block
#                     with open(extracted_file_path, 'r', encoding="utf-8") as txt_file:
#                         content = txt_file.read()
#                         json_content = json.loads(content)
                        
#                     # Write to new file inside its own 'with' block
#                     with open(new_file_path, 'w', encoding="utf-8") as json_file:
#                         json.dump(json_content, json_file, indent=4)
                    
#                     # Add a micro-sleep to help OS release the file handle before deletion
#                     time.sleep(0.05) 
                    
#                     os.remove(extracted_file_path)
#                 except (json.JSONDecodeError, OSError) as e:
#                     # Log the error but continue to the next file
#                     logging.error(f"⚠️ Error processing file {extracted_file_path}: {e}")

#         print("djsbdbsdbsjkdbsjdsjdsjd=================================okjIOixsjdsj")
        
#         # --- REMOVED POLLING LOGIC ---
        
#         # 3. Create Component Name to ID and ParentId Map
#         config_file_name = "MiBlockComponentConfig.json"
#         config_file_path = os.path.join(save_folder, config_file_name)
        
#         name_to_id_map = {}
#         main_parent_id = None 
        
#         print(f"Reading {config_file_name} to create map...")
#         config_data = load_json_data(config_file_path)
        
#         if config_data:
#             component_list = config_data.get('component', [])

#             # Find the main parent ID (ParentId is None, 0, or potentially an empty string)
#             for component in component_list:
#                 parent_id_value = component.get('ParentId')
#                 # We check for None (null), integer 0, or empty string ""
#                 if parent_id_value in [None, 0, ""]: 
#                     main_parent_id = component.get('ComponentId')
#                     break
#             print(main_parent_id)
#             print("=============================================================")
#             # exit() # REMOVED: This explicit exit() has been removed as it halts execution.
            
#             # Build the final map
#             for component in component_list:
#                 name = component.get('ComponentName')
#                 component_id_val = component.get('ComponentId')
#                 parent_id = component.get('ParentId')
                
#                 if name and component_id_val is not None:
#                     name_to_id_map[name] = {
#                         "ComponentId": component_id_val,
#                         "ParentId": parent_id,
#                         "MainParentComponentid": main_parent_id # Store the main ID for easy lookup
#                     }
            
#             map_file_path = os.path.join(output_dir, "component_name_id_map.json") 
            
#             # Mocking file write:
#             # with open(map_file_path, 'w', encoding='utf-8') as f:
#             #     json.dump(name_to_id_map, f, indent=4)
#             print(f"✅ Created component name map and saved to (mocked): {map_file_path}")

#             # -----------------------------------------------------------------
#             # 🆕 NEW STEP: Update Display Orders
#             # -----------------------------------------------------------------
#             update_display_orders_in_payload(payload_file_path)
            
#             time.sleep(2)
#             add_menu_data()
#         else:
#             logging.warning(f"⚠️ Failed to load data from {config_file_name}.")
        
#     except FileNotFoundError as e:
#         logging.error(f"❌ File Polling Failed: {e}")
#         return None
#     except Exception as e:
#         logging.error(f"❌ Unexpected error during file processing: {e}")
#         return None
    
#     # --- End of the file export/extraction/map creation logic ---

#     # -----------------------------------------------------------------
#     # 🌟 FINAL STEP: Load, Update, and Save api_response_final.json 
#     # -----------------------------------------------------------------
#     print("\nStarting final component ID update step...")
    
#     # 1. Load the Component Map
#     map_file_path = os.path.join(output_dir, "component_name_id_map.json")
#     component_map = load_json_data(map_file_path)
    
#     if not component_map:
#         logging.error(f"❌ Cannot update payload: Component map not found at {map_file_path}.")
#         return None 
    
#     # 2. Determine Main Parent ID
#     menu_component_info = component_map.get("Menu", {})
#     MAIN_PARENT_COMPONENT_ID = menu_component_info.get("MainParentComponentid")

#     if not MAIN_PARENT_COMPONENT_ID:
#         logging.error("❌ Cannot update payload: Main 'Menu' ComponentId not found in map.")
#         return None
        
#     # 3. Load the Payload to be updated
#     payload_file_name = "api_response_final.json"
#     payload_file_path = os.path.join(output_dir, payload_file_name) 
#     initial_payload = load_json_data(payload_file_path)

#     if not initial_payload:
#         logging.error(f"❌ Cannot update payload: Target file {payload_file_name} not found or invalid at {payload_file_path}.")
#         return None
        
#     # 4. Update the Payload
#     updated_payload = update_payload_with_component_ids(initial_payload, component_map, MAIN_PARENT_COMPONENT_ID)
    
#     # 5. Save the Updated Payload
#     try:
#         # Mocking file write:
#         # with open(payload_file_path, "w", encoding='utf-8') as f:
#         #     json.dump(updated_payload, f, indent=4)
#         print(f"✅ Successfully updated and saved {payload_file_name} to (mocked) {payload_file_path}")
        
#         return mi_block_folder 

#     except IOError as e:
#         logging.error(f"❌ Error saving final updated payload to {payload_file_path}: {e}")
#         return None
        
def download_and_save_menu_data():
    """
    Downloads menu data from the source URL and saves it to a JSON file
    in the output directory based on the source site ID.
    """
    print("Starting menu data download and save process...")
    settings = load_settings()
    
    if not settings:
        print("Settings could not be loaded. Aborting process.")
        return False
        
    source_site_id = settings.get("source_site_id")
    source_site_url = settings.get("source_site_url")
    
    if not all([source_site_id, source_site_url]):
        print("Error: 'source_site_id' or 'source_site_url' not found in settings.")
        return False
        
    response_data = menu_download_api(source_site_url)
    
    if response_data:
        # Construct the file path dynamically
        output_dir = os.path.join("output", str(source_site_id))
        output_file_path = os.path.join(output_dir, "api_response_input.json")
        
        # Create the output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Save the data to the file
        try:
            with open(output_file_path, "w") as f:
                json.dump(response_data, f, indent=4)
            print(f"Successfully saved menu data to: {output_file_path}")
            return True
        except IOError as e:
            print(f"Error saving file to {output_file_path}: {e}")
            return False
    else:
        print("No data received from API. Aborting save process.")
        return False



# -------------------------------------------------------------------------
# --- DATA EXTRACTION & CLEANING HELPERS (From your prompt and needed for restoration) ---

def process_menu_level_0_only(menu_record):
    """L0 Extractor: Returns L0 payload and L1 MenuSections list."""
    menu_payload = menu_record.copy()
    menu_sections = menu_payload.pop('MenuSections', [])
    return menu_payload, menu_sections

def process_menu_sections_level_1_only(section_list):
    """L1 Extractor: Returns a list containing all L2 MenuItems lists."""
    all_menu_items = []
    for section_record in section_list:
        menu_items = section_record.copy().pop('MenuItems', [])
        all_menu_items.append(menu_items)
    return all_menu_items

def process_menu_items_level_2_only(item_list):
    """L2 Extractor: Returns a list of dictionaries containing raw L3 data (prices/addons)."""
    all_l3_data = []
    for item_record in item_list:
        item_json_string = item_record.copy().get('recordJsonString', {})
        item_prices = item_json_string.get('ItemPrices', [])
        item_addons = item_json_string.get('ItemAddons', [])
        
        all_l3_data.append({
            "item_name": item_json_string.get('item-name', 'Unnamed Item'),
            "item_prices": item_prices,
            "item_addons": item_addons
        })
    return all_l3_data

# -------------------------------------------------------------------------
# --- RESTORED LEVEL 3a PROCESSOR (ItemPrices) ---

def process_item_prices_level_3a_only_standalone(l3_data_list):
    """
    Handles Level 3a: Item Prices. Collects ONLY the price payloads.
    """
    all_prices_payloads = []
    for item_data in l3_data_list:
        item_name = item_data['item_name']
        prices = item_data['item_prices']
        for price_record in prices:
            price_payload = price_record.copy()
            price_payload['source_item_name'] = item_name
            all_prices_payloads.append(price_payload)
    return all_prices_payloads

# -------------------------------------------------------------------------
# --- EXISTING LEVEL 3b PROCESSOR (From your prompt) ---

def process_item_addons_level_3b_only_standalone(l3_data_list):
    """
    Handles Level 3b: Item Addons. Collects ONLY the addon payloads.
    """
    all_addons_payloads = []
    print(f"\n➕ Starting Level 3b Item Addon Processing...")
    for item_data in l3_data_list:
        item_name = item_data['item_name']
        addons = item_data['item_addons']
        for addon_record in addons:
            addon_payload = addon_record.copy()
            addon_payload['source_item_name'] = item_name
            all_addons_payloads.append(addon_payload)
    return all_addons_payloads





# def level0():

#     print("in hereerrerere exit")
#     exit()
#     """
#     Revised: Processes L0, calls the API, saves API response, and updates the original payload 
#     (api_response_final.json) with the new 'recordId', ParentComponentId, and MainParentComponentid 
#     for the child MenuSection records.
#     """
#     settings = load_settings()
#     source_site_id = settings.get("source_site_id")
#     output_dir = os.path.join("output", str(source_site_id))
    
#     # 1. Load the Component ID Map
#     component_map_file = os.path.join(output_dir, "component_name_id_map.json")
#     component_map_data = load_json_data(component_map_file)
    
#     if not component_map_data:
#         print(f"❌ Component map not found at {component_map_file}. Aborting L0.")
#         return False
        
#     # 2. Extract Required Component IDs
#     menu_info = component_map_data.get("Menu", {})
#     menu_section_info = component_map_data.get("Menu Section", {})
    
#     # IDs for the L0 (Menu) record being created
#     l0_component_id = menu_info.get("ComponentId") 
#     l0_main_parent_id = menu_info.get("MainParentComponentid")
    
#     # Component ID for the next level (Menu Section) for updating child payload
#     l1_menu_section_component_id = menu_section_info.get("ComponentId")

#     if not l0_component_id or not l1_menu_section_component_id or not l0_main_parent_id:
#         print("❌ Required Component IDs ('Menu', 'Menu Section', or MainParentComponentid) missing from map. Aborting L0.")
#         return False

#     # Set ParentId for L0 API call (MainParentComponentid for the root item)
#     parent_id = str(l0_main_parent_id) 
    
#     # Load the initial payload (list of records)
#     payload_file_path = os.path.join(output_dir, "api_response_final.json")
#     final_payload = load_json_data(payload_file_path)
#     if not final_payload:
#         print("❌ No payload found.")
#         return False
    
#     print(f"✅ Successfully loaded payload with {len(final_payload)} top-level menu records.")
#     print(f"🔧 Using Menu Component ID: {l0_component_id} and Menu Section Component ID: {l1_menu_section_component_id}")

#     # Safely retrieve destination details
#     destination_site_url = settings.get("destination_site_url")
#     destination_token = settings.get("destination_token", {}).get("token")
    
#     headers = {
#         'Content-Type': 'application/json',
#         'ms_cms_clientapp': 'ProgrammingApp',
#         'Authorization': f'Bearer {destination_token}',
#     }

#     processed_output_level_0 = []
    
#     for i, menu_record in enumerate(final_payload):
#         print(f"\n--- Processing Menu Record {i+1}/{len(final_payload)} ---")
        
#         # 3. Extract and prepare the L0 payload
#         menu_payload, _ = process_menu_level_0_only(menu_record)
        
#         record_data = menu_payload.get("recordJsonString")
#         if isinstance(record_data, dict):
#             record_data = json.dumps(record_data)

#         # Build the API payload using the extracted, static IDs
#         fixed_payload = {
#             "componentName": "Menu",
#             "Scopeid": 5,
#             "ParentId": parent_id, # MainParentComponentid for root L0 record
#             "recordList": [
#                 {
#                     "recordJsonString": record_data,
#                     "ParentRecordId": 0,
#                     "ParentComponentId": parent_id,
#                     "EnableClientEdit": True,
#                     "MainParentComponentid": int(l0_main_parent_id)
#                 }
#             ]
#         }

#         # 4. Send to API and extract new Record ID
#         created_record_id = None
        
#         if destination_site_url and destination_token:
#             responseData = CreateComponentRecord(destination_site_url, headers, fixed_payload)
            
#             status_code = responseData.get('ErrorCode', 'N/A')
#             success_status = responseData.get('Success', 'N/A')
            
#             print(f"📥 API Response Status: {status_code} | Success: {success_status}")
            
#             try:
#                 records_details = responseData.get('componentRecordDetails', {}).get('recordsDetails', [])
#                 if records_details:
#                     created_record_id = records_details[0].get('recordId')
#                     print(f"🔑 **Created Record ID:** {created_record_id}")
#                 else:
#                     print("⚠️ Record ID not found in API response.")
#             except Exception as e:
#                 print(f"❌ Error extracting Record ID: {e}")
#         else:
#             responseData = {"Note": "API call skipped due to missing settings.", "prepared_payload_example": fixed_payload}
            
#         # 5. Save ONLY the API response data
#         processed_output_level_0.append(responseData)
        
#         # --- START: LOGIC TO UPDATE THE ORIGINAL PAYLOAD (for MenuSections) ---
#         if created_record_id is not None:
#             # Update the ParentRecordId and ParentComponentId for child records (MenuSections)
#             if isinstance(menu_record, dict) and 'MenuSections' in menu_record:
#                 for section in menu_record['MenuSections']:
#                     # ParentRecordId is the NEWLY created L0 Record ID
#                     section['ParentRecordId'] = created_record_id 
                    
#                     # ParentComponentId is the ID of the Menu Section component (L1)
#                     section['ParentComponentId'] = str(l1_menu_section_component_id)
                    
#                     # *** NEW UPDATE: Set MainParentComponentid for the child section ***
#                     section['MainParentComponentid'] = l0_main_parent_id 
                    
#                 print(f"🔗 Updated {len(menu_record['MenuSections'])} MenuSection records with ParentRecordId: {created_record_id}, ParentComponentId: {l1_menu_section_component_id}, and MainParentComponentid: {l0_main_parent_id}")
#             else:
#                 # Fallback: add the new ID at the top level for future use
#                 menu_record['NewRecordId_L0'] = created_record_id
#                 menu_record['MainParentComponentid'] = l0_main_parent_id
#                 print(f"🔗 Saved new L0 ID: {created_record_id} and MainParentComponentid: {l0_main_parent_id} to the record.")

#         # --- END: LOGIC ---

#     # 6. Save final output for debugging (API Responses)
#     final_api_output_file_path = os.path.join(output_dir, "final-api-response-L0.json")
#     try:
#         os.makedirs(output_dir, exist_ok=True)
#         with open(final_api_output_file_path, "w", encoding='utf-8') as f:
#             json.dump(processed_output_level_0, f, indent=4)
#         print(f"\n✅ DEBUG SUCCESS: ONLY API Responses for {len(processed_output_level_0)} Level 0 records saved to: {final_api_output_file_path}")
#     except Exception as e:
#         print(f"❌ Error during L0 API response save: {e}")
        
#     # 7. Save the MODIFIED original payload (final_payload) back to the input file
#     try:
#         with open(payload_file_path, "w", encoding='utf-8') as f:
#             json.dump(final_payload, f, indent=4)
#         print(f"💾 SUCCESS: Updated original payload file with new Record IDs: {payload_file_path}")
#         return True
#     except Exception as e:
#         print(f"❌ Error during L0 payload update save: {e}")
#         return False


# def level1():
#     """
#     Revised: Processes L1 (Menu Section), calls the API, extracts new L1 ID, and updates 
#     L2 (Menu Section Item) with the new ParentRecordId, ParentComponentId, and MainParentComponentid.
#     """
#     settings = load_settings()
#     source_site_id = settings.get("source_site_id")
#     output_dir = os.path.join("output", str(source_site_id))
#     payload_file_path = os.path.join(output_dir, "api_response_final.json")
    
#     # 1. Load Component ID Map and Extract IDs
#     component_map_file = os.path.join(output_dir, "component_name_id_map.json")
#     component_map_data = load_json_data(component_map_file)
#     if not component_map_data:
#         print(f"❌ Component map not found at {component_map_file}. Aborting L1.")
#         return False

#     menu_info = component_map_data.get("Menu", {})
#     menu_section_info = component_map_data.get("Menu Section", {})
#     menu_item_info = component_map_data.get("Menu Section Item", {})
    
#     # Static IDs for L1 API payload
#     l0_main_parent_id = menu_info.get("MainParentComponentid") # Should be the Main Menu ID
#     l1_component_id = menu_section_info.get("ComponentId")     # L1 Component ID
    
#     # Static IDs for L2 child update
#     l2_component_id = menu_item_info.get("ComponentId")        # L2 Component ID
    
#     if not all([l0_main_parent_id, l1_component_id, l2_component_id]):
#          print("❌ Required Component IDs for L0, L1, or L2 missing from map. Aborting L1.")
#          return False

#     # Load the modified payload (contains L0 IDs now)
#     final_payload = load_json_data(payload_file_path)
#     if not final_payload: return False
    
#     # Safely retrieve destination details
#     destination_site_url = settings.get("destination_site_url")
#     destination_token = settings.get("destination_token", {}).get("token")
    
#     headers = {
#         'Content-Type': 'application/json',
#         'ms_cms_clientapp': 'ProgrammingApp',
#         'Authorization': f'Bearer {destination_token}',
#     }
    
#     processed_output_level_1 = []
    
#     # Iterate through L0 records to access L1 lists
#     for i, menu_record in enumerate(final_payload):
#         print(f"\n--- Processing L1 Sections for L0 Record {i+1}/{len(final_payload)} ---")
#         _, menu_sections_list = process_menu_level_0_only(menu_record)
        
#         # Iterate through L1 records
#         for j, section_record in enumerate(menu_sections_list):
#             print(f"  -> Processing L1 Section {j+1}/{len(menu_sections_list)}")
            
#             # Use data from the payload (ParentRecordId is L0 ID, componentName is Menu Section)
#             componentName = section_record.get("componentName", "Menu Section") 
#             parent_record_id = section_record.get("ParentRecordId", 0) # L0 Record ID
            
#             # Extract and prepare the L1 payload
#             section_payload = section_record.copy()
#             section_payload.pop('MenuItems', None) # Clean L2 data for L1 API call
            
#             record_data = section_payload.get("recordJsonString")
#             if isinstance(record_data, dict):
#                 record_data = json.dumps(record_data)

#             # Build fixed payload using STATIC component IDs
#             fixed_payload = {
#                 "componentName": componentName,
#                 "Scopeid": 5,
#                 # ParentId for L1 API call is the L0 Component ID
#                 "ParentId": str(menu_info.get("ComponentId", l0_main_parent_id)), 
#                 "recordList": [
#                     {
#                         "recordJsonString": record_data,
#                         "ParentRecordId": parent_record_id, # L0 Record ID
#                         "ParentComponentId": str(menu_info.get("ComponentId", l0_main_parent_id)), # L0 Component ID
#                         "EnableClientEdit": True,
#                         "MainParentComponentid": int(l0_main_parent_id)
#                     }
#                 ]
#             }
            
#             created_record_id = None
#             responseData = None
#             if destination_site_url and destination_token:
#                 api_result = CreateComponentRecord(destination_site_url, headers, fixed_payload)
                
#                 if isinstance(api_result, dict):
#                     responseData = api_result
#                     status_code = responseData.get('ErrorCode', 'N/A')
#                     success_status = responseData.get('Success', 'N/A')
#                     print(f"  📥 API Response Status: {status_code} | Success: {success_status}")
                    
#                     try:
#                         records_details = responseData.get('componentRecordDetails', {}).get('recordsDetails', [])
#                         if records_details:
#                             created_record_id = records_details[0].get('recordId')
#                             print(f"  🔑 **Created L1 Record ID:** {created_record_id}")
#                         else:
#                             print("  ⚠️ L1 Record ID not found in API response structure.")
#                     except Exception as e:
#                         print(f"  ❌ Error extracting L1 Record ID: {e}")
#                 else:
#                     responseData = {"Note": "API call failed (returned non-dict/None).", "status_code": "ERROR_NON_DICT", "original_response": str(api_result)}
#                     print("  ❌ API call failed to return a valid dictionary response.")
#             else:
#                 responseData = {"Note": "API call skipped due to missing settings.", "prepared_payload_example": fixed_payload}
                
#             if responseData:
#                 processed_output_level_1.append(responseData)

#             # --- NEW LOGIC: Update L2 children (Menu Section Item) ---
#             if created_record_id is not None:
#                 # Update the L1 record itself with its new ID for future reference
#                 section_record['NewRecordId_L1'] = created_record_id
                
#                 if 'MenuItems' in section_record and section_record['MenuItems'] is not None:
                    
#                     for item in section_record['MenuItems']:
#                         # ParentRecordId is the NEWLY created L1 Record ID
#                         item['ParentRecordId'] = created_record_id 
                        
#                         # ParentComponentId is the ID of the Menu Item component (L2)
#                         item['ParentComponentId'] = str(l2_component_id)
                        
#                         # MainParentComponentid is always the L0 Main Menu ID
#                         item['MainParentComponentid'] = l0_main_parent_id
                        
#                     print(f"  🔗 Updated {len(section_record['MenuItems'])} MenuItems records with ParentRecordId: {created_record_id}, ParentComponentId: {l2_component_id}, and MainParentComponentid: {l0_main_parent_id}")

#     # 4. Save API Responses
#     final_api_output_file_path = os.path.join(output_dir, "final-api-response-L1.json")
#     try:
#         os.makedirs(output_dir, exist_ok=True)
#         with open(final_api_output_file_path, "w", encoding='utf-8') as f:
#             json.dump(processed_output_level_1, f, indent=4)
#         print(f"\n✅ DEBUG SUCCESS: ONLY API Responses for L1 records saved to: {final_api_output_file_path}")
#     except Exception as e:
#         print(f"❌ Error during L1 API response save: {e}")
        
#     # 5. Save the MODIFIED original payload (final_payload) back to the input file
#     try:
#         with open(payload_file_path, "w", encoding='utf-8') as f:
#             json.dump(final_payload, f, indent=4)
#         print(f"💾 SUCCESS: Updated original payload file with new L1 Record IDs: {payload_file_path}")
#         return True
#     except Exception as e:
#         print(f"❌ Error during L1 payload update save: {e}")
#         return False


# ----------------------------------------------------------------------------------------------------------------------

## 🛠️ Updated `level2` Function


# def level2():
#     """
#     Revised: Processes L2 (Menu Section Item), calls the API, extracts new L2 ID, and updates 
#     L3 (ItemPrices/ItemAddons) with the new ParentRecordId, ParentComponentId, and MainParentComponentid.
#     """
#     settings = load_settings()
#     source_site_id = settings.get("source_site_id")
#     output_dir = os.path.join("output", str(source_site_id))
#     payload_file_path = os.path.join(output_dir, "api_response_final.json")
    
#     # 1. Load Component ID Map and Extract IDs
#     component_map_file = os.path.join(output_dir, "component_name_id_map.json")
#     component_map_data = load_json_data(component_map_file)
#     if not component_map_data:
#         print(f"❌ Component map not found at {component_map_file}. Aborting L2.")
#         return False
        
#     # Static IDs for L2 API payload
#     menu_item_info = component_map_data.get("Menu Section Item", {})
#     l1_component_id = component_map_data.get("Menu Section", {}).get("ComponentId") # L1 Component ID (Parent for L2 API)
#     l0_main_parent_id = component_map_data.get("Menu", {}).get("MainParentComponentid") # Main Menu ID
    
#     # Static IDs for L3 child update
#     l3_price_component_id = component_map_data.get("Menu Section Item Price Options", {}).get("ComponentId")
#     l3_addon_component_id = component_map_data.get("Menu Section Item Addons", {}).get("ComponentId")
    
#     if not all([l1_component_id, l0_main_parent_id, l3_price_component_id, l3_addon_component_id]):
#          print("❌ Required Component IDs for L1, L0, or L3 children missing from map. Aborting L2.")
#          return False

#     # Load the modified payload (contains L1 IDs now)
#     final_payload = load_json_data(payload_file_path)
#     if not final_payload: return False
        
#     # Safely retrieve destination details
#     destination_site_url = settings.get("destination_site_url")
#     destination_token = settings.get("destination_token", {}).get("token")
    
#     headers = {
#         'Content-Type': 'application/json',
#         'ms_cms_clientapp': 'ProgrammingApp',
#         'Authorization': f'Bearer {destination_token}',
#     }

#     processed_output_level_2 = []
#     item_counter = 0

#     for menu_record in final_payload:
#         _, menu_sections_list = process_menu_level_0_only(menu_record)
#         # Assuming process_menu_sections_level_1_only flattens the L2 lists
#         all_item_lists = process_menu_sections_level_1_only(menu_sections_list)
        
#         for item_list in all_item_lists:
#             for item_record in item_list:
#                 item_counter += 1
#                 print(f"\n--- Processing L2 Item {item_counter} ---")

#                 # 1. Extract and prepare the L2 payload
#                 item_payload = item_record.copy()
                
#                 # Retrieve L3 data references *before* deep copying/cleaning
#                 item_json_string_ref = item_record.get('recordJsonString', {})
#                 l3_prices = item_json_string_ref.get('ItemPrices', [])
#                 l3_addons = item_json_string_ref.get('ItemAddons', [])

#                 # Prepare payload for API call (remove L3 data)
#                 payload_json_string = item_json_string_ref.copy()
#                 payload_json_string.pop('ItemPrices', None) # Clean L3
#                 payload_json_string.pop('ItemAddons', None) # Clean L3
                
#                 # Use data from the payload (ParentRecordId is L1 ID)
#                 componentName = item_payload.get("componentName", "Menu Section Item")
#                 parent_record_id = item_payload.get("ParentRecordId", 0) # L1 Record ID
#                 record_data = json.dumps(payload_json_string)
                
#                 # Build fixed payload using STATIC component IDs
#                 fixed_payload = {
#                     "componentName": componentName,
#                     "Scopeid": 5,
#                     # ParentId for L2 API call is the L1 Component ID
#                     "ParentId": str(l1_component_id), 
#                     "recordList": [
#                         {
#                             "recordJsonString": record_data,
#                             "ParentRecordId": parent_record_id, # L1 Record ID
#                             "ParentComponentId": str(l1_component_id), # L1 Component ID
#                             "EnableClientEdit": True,
#                             "MainParentComponentid": int(l0_main_parent_id)
#                         }
#                     ]
#                 }
                
#                 created_record_id = None
#                 responseData = None
                
#                 if destination_site_url and destination_token:
#                     api_result = CreateComponentRecord(destination_site_url, headers, fixed_payload)
                    
#                     if isinstance(api_result, dict):
#                         responseData = api_result
#                         status_code = responseData.get('ErrorCode', 'N/A')
#                         success_status = responseData.get('Success', 'N/A')
#                         print(f"  📥 API Response Status: {status_code} | Success: {success_status}")
                        
#                         try:
#                             records_details = responseData.get('componentRecordDetails', {}).get('recordsDetails', [])
#                             if records_details:
#                                 created_record_id = records_details[0].get('recordId')
#                                 print(f"  🔑 **Created L2 Record ID:** {created_record_id}")
#                             else:
#                                 print("  ⚠️ L2 Record ID not found in API response structure.")
#                         except Exception as e:
#                             print(f"  ❌ Error extracting L2 Record ID: {e}")
#                     else:
#                         responseData = {"Note": "API call failed (returned non-dict/None).", "status_code": "ERROR_NON_DICT", "original_response": str(api_result)}
#                         print("  ❌ API call failed to return a valid dictionary response.")
#                 else:
#                     responseData = {"Note": "API call skipped due to missing settings.", "prepared_payload_example": fixed_payload}
                
#                 # 3. Save ONLY the API response data
#                 if responseData:
#                     processed_output_level_2.append(responseData)

#                 # --- NEW LOGIC: Update L3 children with the new L2 ID (updates the final_payload) ---
#                 if created_record_id is not None:
                    
#                     # Save L2 ID on the item record for future reference
#                     item_record['NewRecordId_L2'] = created_record_id
                    
#                     # Update L3A (ItemPrices)
#                     if l3_prices:
#                         for price in l3_prices:
#                             price['ParentRecordId'] = created_record_id
#                             # ParentComponentId is L3 Price Options component ID
#                             price['ParentComponentId'] = str(l3_price_component_id)
#                             # MainParentComponentid is always the L0 Main Menu ID
#                             price['MainParentComponentid'] = l0_main_parent_id 
#                         print(f"  🔗 Updated {len(l3_prices)} ItemPrices records with ParentRecordId: {created_record_id}")
                    
#                     # Update L3B (ItemAddons)
#                     if l3_addons:
#                         for addon in l3_addons:
#                             addon['ParentRecordId'] = created_record_id
#                             # ParentComponentId is L3 Addons component ID
#                             addon['ParentComponentId'] = str(l3_addon_component_id)
#                             # MainParentComponentid is always the L0 Main Menu ID
#                             addon['MainParentComponentid'] = l0_main_parent_id
#                         print(f"  🔗 Updated {len(l3_addons)} ItemAddons records with ParentRecordId: {created_record_id}")
                        
#     # 4. Save API Responses
#     final_api_output_file_path = os.path.join(output_dir, "final-api-response-L2.json")
#     try:
#         os.makedirs(output_dir, exist_ok=True)
#         with open(final_api_output_file_path, "w", encoding='utf-8') as f:
#             json.dump(processed_output_level_2, f, indent=4)
#         print(f"\n✅ DEBUG SUCCESS: ONLY API Responses for L2 records saved to: {final_api_output_file_path}")
#     except Exception as e:
#         print(f"❌ Error during L2 API response save: {e}")
        
#     # 5. Save the MODIFIED original payload (final_payload) back to the input file
#     try:
#         with open(payload_file_path, "w", encoding='utf-8') as f:
#             json.dump(final_payload, f, indent=4)
#         print(f"💾 SUCCESS: Updated original payload file with new L2 Record IDs: {payload_file_path}")
#         return True
#     except Exception as e:
#         print(f"❌ Error during L2 payload update save: {e}")
#         return False
























def level0():
    settings = load_settings()
    source_site_id = settings.get("source_site_id")
    output_dir = os.path.join("output", str(source_site_id))
    payload_file_path = os.path.join(output_dir, "api_response_final.json")
    component_map_file = os.path.join(output_dir, "component_name_id_map.json")
    component_map_data = load_json_data(component_map_file)
    
    if not component_map_data: return False
        
    menu_info = component_map_data.get("Menu", {})
    l0_component_id = menu_info.get("ComponentId") 
    l0_main_parent_id = menu_info.get("MainParentComponentid")
    l1_menu_section_component_id = component_map_data.get("Menu Section", {}).get("ComponentId")

    if not all([l0_component_id, l1_menu_section_component_id, l0_main_parent_id]): return False
    
    final_payload = load_json_data(payload_file_path)
    if not final_payload: return False
    
    destination_site_url = settings.get("destination_site_url")
    destination_token = settings.get("destination_token", {}).get("token")
    headers = {
        'Content-Type': 'application/json',
        'ms_cms_clientapp': 'ProgrammingApp',
        'Authorization': f'Bearer {destination_token}',
    }

    
    for menu_record in final_payload:
        menu_payload, _ = process_menu_level_0_only(menu_record)
        record_data_dict = menu_payload.get("recordJsonString", {}).copy()
        
        # --- STATUS/DISPLAYORDER LOGIC START ---
        internal_status = record_data_dict.get("status", 1)
        converted_integer_status = 0 if internal_status == 2 else int(internal_status)
        root_status_boolean = (converted_integer_status == 1)
        
        display_order = record_data_dict.get("displayorder", 0) # Capture displayOrder before removal

        # FIX: REMOVE REDUNDANT FIELDS from recordDataJson 
        record_data_dict.pop("status", None)
        record_data_dict.pop("displayorder", None)
        
        record_data = json.dumps(record_data_dict)
        # --- STATUS/DISPLAYORDER LOGIC END ---

        # NEW PAYLOAD STRUCTURE (Single Record)
        single_record_payload = {
            "componentId": int(l0_component_id),
            "recordId": 0,
            "parentRecordId": 0,
            "recordDataJson": record_data, 
            "status": root_status_boolean, 
            "tags": [],
            "displayOrder": display_order, 
            "updatedBy": 0,
        }

        # WRAP PAYLOAD for addUpdateRecordsToCMS
        api_payload = {f"{l0_component_id}_L0": [single_record_payload]}

        created_record_id = None
        if destination_site_url and destination_token:
            success, responseData = addUpdateRecordsToCMS(destination_site_url, headers, api_payload)
            
            if success:
                result_body = responseData.get(0) 
                
                # 🎯 FIX: Handle both integer ID response and dictionary response
                if isinstance(result_body, int) and result_body > 0:
                    created_record_id = result_body
                elif isinstance(result_body, dict) and result_body.get('recordId'):
                    created_record_id = result_body['recordId']
                else:
                    logging.error(f"L0 API call succeeded but returned unexpected body: {result_body}")
            else:
                logging.error(f"L0 API call failed for menu record. Response: {responseData}")
        
        # Update original payload and save L0 ID for L1 children
        if created_record_id is not None and created_record_id > 0:
            if isinstance(menu_record, dict) and 'MenuSections' in menu_record:
                for section in menu_record['MenuSections']:
                    section['ParentRecordId'] = created_record_id 
                    section['ParentComponentId'] = str(l1_menu_section_component_id)
                    section['MainParentComponentid'] = l0_main_parent_id 
            else:
                menu_record['NewRecordId_L0'] = created_record_id
                menu_record['MainParentComponentid'] = l0_main_parent_id

    # Save final payload file (important for L1 and L2)
    try:
        os.makedirs(output_dir, exist_ok=True)
        with open(payload_file_path, "w", encoding='utf-8') as f:
            json.dump(final_payload, f, indent=4)
        return True
    except Exception as e: 
        logging.error(f"Error saving L0 final payload: {e}")
        return False

# ----------------------------------------------------------------------
# LEVEL 1 FUNCTION (Fixed redundant fields + Fixed API response handling)
# ----------------------------------------------------------------------

def level1():
    settings = load_settings()
    source_site_id = settings.get("source_site_id")
    output_dir = os.path.join("output", str(source_site_id))
    payload_file_path = os.path.join(output_dir, "api_response_final.json")
    component_map_file = os.path.join(output_dir, "component_name_id_map.json")
    component_map_data = load_json_data(component_map_file)

    if not component_map_data: return False
    
    menu_info = component_map_data.get("Menu", {})
    l0_main_parent_id = menu_info.get("MainParentComponentid") 
    l1_component_id = component_map_data.get("Menu Section", {}).get("ComponentId") 
    l2_component_id = component_map_data.get("Menu Section Item", {}).get("ComponentId") 
    
    if not all([l0_main_parent_id, l1_component_id, l2_component_id]): return False

    final_payload = load_json_data(payload_file_path)
    if not final_payload: return False
    
    destination_site_url = settings.get("destination_site_url")
    destination_token = settings.get("destination_token", {}).get("token")
    headers = {
        'Content-Type': 'application/json',
        'ms_cms_clientapp': 'ProgrammingApp',
        'Authorization': f'Bearer {destination_token}',
    }
    
    for menu_record in final_payload:
        _, menu_sections_list = process_menu_level_0_only(menu_record) 
        
        for section_record in menu_sections_list:
            
            parent_record_id = section_record.get("ParentRecordId", 0) # L0 Record ID
            if parent_record_id == 0: continue 

            section_record_copy = section_record.copy()
            section_record_copy.pop('MenuItems', None) 
            record_data_dict = section_record_copy.get("recordJsonString", {}).copy()

            # --- STATUS/DISPLAYORDER LOGIC START ---
            internal_status = record_data_dict.get("status", 1)
            converted_integer_status = 0 if internal_status == 2 else int(internal_status)
            root_status_boolean = (converted_integer_status == 1)
            
            display_order = record_data_dict.get("displayorder", 0) # Capture displayOrder before removal

            # FIX: REMOVE REDUNDANT FIELDS from recordDataJson 
            record_data_dict.pop("status", None)
            record_data_dict.pop("displayorder", None)
            
            record_data = json.dumps(record_data_dict)
            # --- STATUS/DISPLAYORDER LOGIC END ---

            # NEW PAYLOAD STRUCTURE (Single Record)
            single_record_payload = {
                "componentId": int(l1_component_id),
                "recordId": 0,
                "parentRecordId": parent_record_id, 
                "recordDataJson": record_data, 
                "status": root_status_boolean,
                "tags": [],
                "displayOrder": display_order, 
                "updatedBy": 0,
            }

            # WRAP PAYLOAD for addUpdateRecordsToCMS
            api_payload = {f"{l1_component_id}_L1": [single_record_payload]}
            
            created_record_id = None
            if destination_site_url and destination_token:
                success, responseData = addUpdateRecordsToCMS(destination_site_url, headers, api_payload)
                
                if success:
                    result_body = responseData.get(0) 
                    
                    # 🎯 FIX: Handle both integer ID response and dictionary response
                    if isinstance(result_body, int) and result_body > 0:
                        created_record_id = result_body
                    elif isinstance(result_body, dict) and result_body.get('recordId'):
                        created_record_id = result_body['recordId']
                    else:
                        logging.error(f"L1 API call succeeded but returned unexpected body: {result_body}")
                else:
                    logging.error(f"L1 API call failed for section record. Response: {responseData}")

            if created_record_id is not None and created_record_id > 0:
                section_record['NewRecordId_L1'] = created_record_id
                if 'MenuItems' in section_record and section_record['MenuItems'] is not None:
                    for item in section_record['MenuItems']:
                        item['ParentRecordId'] = created_record_id
                        item['ParentComponentId'] = str(l2_component_id)
                        item['MainParentComponentid'] = l0_main_parent_id
                        
    # Save final payload file (important for L2)
    try:
        os.makedirs(output_dir, exist_ok=True)
        with open(payload_file_path, "w", encoding='utf-8') as f:
            json.dump(final_payload, f, indent=4)
        return True
    except Exception as e: 
        logging.error(f"Error saving L1 final payload: {e}")
        return False

# ----------------------------------------------------------------------
# LEVEL 2 FUNCTION (Fixed redundant fields + Fixed API response handling)
# ----------------------------------------------------------------------

def level2():
    settings = load_settings()
    source_site_id = settings.get("source_site_id")
    output_dir = os.path.join("output", str(source_site_id))
    payload_file_path = os.path.join(output_dir, "api_response_final.json")
    component_map_file = os.path.join(output_dir, "component_name_id_map.json")
    component_map_data = load_json_data(component_map_file)
    
    if not component_map_data: return False
        
    # Static IDs
    l0_main_parent_id = component_map_data.get("Menu", {}).get("MainParentComponentid")
    l2_component_id = component_map_data.get("Menu Section Item", {}).get("ComponentId")
    l3_price_component_id = component_map_data.get("Menu Section Item Price Options", {}).get("ComponentId")
    l3_addon_component_id = component_map_data.get("Menu Section Item Addons", {}).get("ComponentId")
    
    if not all([l0_main_parent_id, l2_component_id, l3_price_component_id, l3_addon_component_id]): return False

    final_payload = load_json_data(payload_file_path)
    if not final_payload: return False
        
    destination_site_url = settings.get("destination_site_url")
    destination_token = settings.get("destination_token", {}).get("token")
    headers = {
        'Content-Type': 'application/json',
        'ms_cms_clientapp': 'ProgrammingApp',
        'Authorization': f'Bearer {destination_token}',
    }
    
    for menu_record in final_payload:
        _, menu_sections_list = process_menu_level_0_only(menu_record)
        all_item_lists = process_menu_sections_level_1_only(menu_sections_list)
        
        for item_list in all_item_lists:
            for item_record in item_list:
                
                parent_record_id = item_record.get("ParentRecordId", 0) # L1 Record ID
                if parent_record_id == 0: continue

                item_json_string_ref = item_record.get('recordJsonString', {})
                l3_prices = item_json_string_ref.get('ItemPrices', [])
                l3_addons = item_json_string_ref.get('ItemAddons', [])

                payload_json_string = item_json_string_ref.copy()
                payload_json_string.pop('ItemPrices', None) 
                payload_json_string.pop('ItemAddons', None) 
                
                # --- STATUS/DISPLAYORDER LOGIC START ---
                internal_status = payload_json_string.get("status", 1)
                converted_integer_status = 0 if internal_status == 2 else int(internal_status)
                root_status_boolean = (converted_integer_status == 1)
                
                display_order = payload_json_string.get("displayorder", 0) # Capture displayOrder before removal

                # FIX: REMOVE REDUNDANT FIELDS from recordDataJson 
                payload_json_string.pop("status", None)
                payload_json_string.pop("displayorder", None)
                
                record_data = json.dumps(payload_json_string)
                # --- STATUS/DISPLAYORDER LOGIC END ---
                
                # NEW PAYLOAD STRUCTURE (Single Record)
                single_record_payload = {
                    "componentId": int(l2_component_id),
                    "recordId": 0,
                    "parentRecordId": parent_record_id, # L1 Record ID
                    "recordDataJson": record_data, 
                    "status": root_status_boolean,
                    "tags": [],
                    "displayOrder": display_order, 
                    "updatedBy": 0,
                }
                
                # WRAP PAYLOAD for addUpdateRecordsToCMS
                api_payload = {f"{l2_component_id}_L2": [single_record_payload]}

                created_record_id = None
                if destination_site_url and destination_token:
                    success, responseData = addUpdateRecordsToCMS(destination_site_url, headers, api_payload)
                    
                    if success:
                        result_body = responseData.get(0) 
                        
                        # 🎯 FIX: Handle both integer ID response and dictionary response
                        if isinstance(result_body, int) and result_body > 0:
                            created_record_id = result_body
                        elif isinstance(result_body, dict) and result_body.get('recordId'):
                            created_record_id = result_body['recordId']
                        else:
                            logging.error(f"L2 API call succeeded but returned unexpected body: {result_body}")
                    else:
                        logging.error(f"L2 API call failed for item record. Response: {responseData}")
                
                # Update L3 children with the new L2 ID
                if created_record_id is not None and created_record_id > 0:
                    item_record['NewRecordId_L2'] = created_record_id
                    
                    if l3_prices:
                        for price in l3_prices:
                            price['ParentRecordId'] = created_record_id
                            price['ParentComponentId'] = str(l3_price_component_id)
                            price['MainParentComponentid'] = l0_main_parent_id 
                    
                    if l3_addons:
                        for addon in l3_addons:
                            addon['ParentRecordId'] = created_record_id
                            addon['ParentComponentId'] = str(l3_addon_component_id)
                            addon['MainParentComponentid'] = l0_main_parent_id
                        
    # Save final payload file (important for L3)
    try:
        os.makedirs(output_dir, exist_ok=True)
        with open(payload_file_path, "w", encoding='utf-8') as f:
            json.dump(final_payload, f, indent=4)
        return True
    except Exception as e: 
        logging.error(f"Error saving L2 final payload: {e}")
        return False



def safe_int(value, default=0):
    """Safely converts a value (including None or empty string) to an integer.

    Prevents ValueError when int('') is called.
    """
    if value is None:
        return default
    if isinstance(value, str):
        value = value.strip()
        if value == '':
            return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default
    


# def level3a_item_prices():
#     """
#     Revised: Processes L3A (ItemPrices), calls the API for each price record, and saves ONLY the API response JSON.
#     Uses safe_int() to prevent conversion errors on IDs.
#     """
#     settings = load_settings()
#     source_site_id = settings.get("source_site_id")
#     output_dir = os.path.join("output", str(source_site_id))
#     payload_file_path = os.path.join(output_dir, "api_response_final.json")
    
#     final_payload = load_json_data(payload_file_path)
#     if not final_payload: return False
        
#     # Safely retrieve destination details
#     destination_site_url = settings.get("destination_site_url")
#     destination_token = settings.get("destination_token", {}).get("token")
    
#     headers = {
#         'Content-Type': 'application/json',
#         'ms_cms_clientapp': 'ProgrammingApp',
#         'Authorization': f'Bearer {destination_token}',
#     }

#     all_l3_data_for_menu = []
#     processed_output_level_3a = []
    
#     # 1. Collect all L3A raw payloads (which should contain L2 IDs)
#     for menu_record in final_payload:
#         _, menu_sections_list = process_menu_level_0_only(menu_record)
#         all_item_lists = process_menu_sections_level_1_only(menu_sections_list)
        
#         for item_list in all_item_lists:
#             if item_list:
#                 l3_data_from_items = process_menu_items_level_2_only(item_list)
#                 all_l3_data_for_menu.extend(l3_data_from_items)
        
#     # Final processing step to flatten and format ItemPrices
#     final_item_prices_payloads = process_item_prices_level_3a_only_standalone(all_l3_data_for_menu)
#     print(f"\nTotal Level 3a ItemPrices payloads collected: {len(final_item_prices_payloads)}")

#     # 2. Iterate and call API for each L3A record
#     for i, item_price_record in enumerate(final_item_prices_payloads):
#         print(f"\n--- Processing L3A ItemPrice {i+1}/{len(final_item_prices_payloads)} ---")
        
#         # --- FIX APPLIED HERE: Use safe_int() for all component IDs ---
#         componentName = item_price_record.get("componentName", "ItemPrice")
#         parent_record_id = item_price_record.get("ParentRecordId", 0) 
#         ParentComponentId = safe_int(item_price_record.get("ParentComponentId"), 0)
#         MainParentComponentid = safe_int(item_price_record.get("MainParentComponentid"), 0)
        
#         record_data = item_price_record.get("recordJsonString")
#         if isinstance(record_data, dict):
#             record_data = json.dumps(record_data)

#         fixed_payload = {
#             "componentName": componentName,
#             "Scopeid": 5,
#             "ParentId": str(ParentComponentId), # Use the L2 Component ID (string)
#             "recordList": [
#                 {
#                     "recordJsonString": record_data,
#                     "ParentRecordId": parent_record_id,
#                     "ParentComponentId": ParentComponentId, # Use the safe integer value
#                     "MainParentComponentid": MainParentComponentid # Use the safe integer value
#                 }
#             ]
#         }
        
#         responseData = None
#         if destination_site_url and destination_token:
#             api_result = CreateComponentRecord(destination_site_url, headers, fixed_payload)

#             if isinstance(api_result, dict):
#                 responseData = api_result
#                 print("   📥 API Response Status:", responseData.get('status_code', 'N/A'), " | Success:", responseData.get('success', 'N/A'))
#             else:
#                 responseData = {"Note": "API call failed (returned non-dict/None).", "status_code": "ERROR_NON_DICT", "original_response": str(api_result)}
#                 print("   ❌ API call failed to return a valid dictionary response.")
#         else:
#             responseData = {"Note": "API call skipped due to missing settings.", "prepared_payload_example": fixed_payload}

#         # 3. Save ONLY the API response data
#         if responseData:
#             processed_output_level_3a.append(responseData)

#     # 4. Save API Responses
#     final_api_output_file_path = os.path.join(output_dir, "final-api-response-L3A.json")
#     try:
#         os.makedirs(output_dir, exist_ok=True)
#         with open(final_api_output_file_path, "w", encoding='utf-8') as f:
#             json.dump(processed_output_level_3a, f, indent=4)
#         print(f"\n✅ DEBUG SUCCESS: ONLY API Responses for {len(processed_output_level_3a)} L3A records saved to: {final_api_output_file_path}")
#         return True
#     except Exception as e:
#         print(f"❌ Error during L3A save: {e}")
#         return False
    

def level3a_item_prices():
    """
    Revised: Processes L3A (ItemPrices), calls the API for each price record, and saves ONLY the API response JSON.
    Uses safe_int() to prevent conversion errors on IDs.
    """
    settings = load_settings()
    source_site_id = settings.get("source_site_id")
    output_dir = os.path.join("output", str(source_site_id))
    payload_file_path = os.path.join(output_dir, "api_response_final.json")

    final_payload = load_json_data(payload_file_path)
    if not final_payload: return False
        
    # Safely retrieve destination details
    destination_site_url = settings.get("destination_site_url")
    destination_token = settings.get("destination_token", {}).get("token")

    headers = {
        'Content-Type': 'application/json',
        'ms_cms_clientapp': 'ProgrammingApp',
        'Authorization': f'Bearer {destination_token}',
    }

    all_l3_data_for_menu = []
    processed_output_level_3a = []

    # 1. Collect all L3A raw payloads (which should contain L2 IDs)
    for menu_record in final_payload:
        _, menu_sections_list = process_menu_level_0_only(menu_record)
        all_item_lists = process_menu_sections_level_1_only(menu_sections_list)
        
        for item_list in all_item_lists:
            if item_list:
                l3_data_from_items = process_menu_items_level_2_only(item_list)
                all_l3_data_for_menu.extend(l3_data_from_items)
        
    # Final processing step to flatten and format ItemPrices
    final_item_prices_payloads = process_item_prices_level_3a_only_standalone(all_l3_data_for_menu)
    print(f"\nTotal Level 3a ItemPrices payloads collected: {len(final_item_prices_payloads)}")

    # 2. Iterate and call API for each L3A record
    for i, item_price_record in enumerate(final_item_prices_payloads):
        print(f"\n--- Processing L3A ItemPrice {i+1}/{len(final_item_prices_payloads)} ---")
        
        # --- FIX APPLIED HERE: Use safe_int() for all component IDs ---
        componentName = item_price_record.get("componentName", "ItemPrice")
        parent_record_id = item_price_record.get("ParentRecordId", 0) 
        ParentComponentId = safe_int(item_price_record.get("ParentComponentId"), 0)
        MainParentComponentid = safe_int(item_price_record.get("MainParentComponentid"), 0)
        
        record_data = item_price_record.get("recordJsonString")
        if isinstance(record_data, dict):
            record_data = json.dumps(record_data)

        fixed_payload = {
            "componentName": componentName,
            "Scopeid": 5,
            "ParentId": str(ParentComponentId), # Use the L2 Component ID (string)
            "recordList": [
                {
                    "recordJsonString": record_data,
                    "ParentRecordId": parent_record_id,
                    "ParentComponentId": ParentComponentId, # Use the safe integer value
                    "MainParentComponentid": MainParentComponentid # Use the safe integer value
                }
            ]
        }
        
        responseData = None
        if destination_site_url and destination_token:
            api_result = CreateComponentRecord(destination_site_url, headers, fixed_payload)

            if isinstance(api_result, dict):
                responseData = api_result
                
                # --- FIX APPLIED HERE: Use 'ErrorCode' for status and 'Success' (capital S) ---
                status_code = responseData.get('ErrorCode', 'N/A')
                success_status = responseData.get('Success', 'N/A')
                print(f"  📥 API Response Status: {status_code} | Success: {success_status}")
                # --- END FIX ---
                
            else:
                responseData = {"Note": "API call failed (returned non-dict/None).", "status_code": "ERROR_NON_DICT", "original_response": str(api_result)}
                print("  ❌ API call failed to return a valid dictionary response.")
        else:
            responseData = {"Note": "API call skipped due to missing settings.", "prepared_payload_example": fixed_payload}

        # 3. Save ONLY the API response data
        if responseData:
            processed_output_level_3a.append(responseData)

    # 4. Save API Responses
    final_api_output_file_path = os.path.join(output_dir, "final-api-response-L3A.json")
    try:
        os.makedirs(output_dir, exist_ok=True)
        with open(final_api_output_file_path, "w", encoding='utf-8') as f:
            json.dump(processed_output_level_3a, f, indent=4)
        print(f"\n✅ DEBUG SUCCESS: ONLY API Responses for {len(processed_output_level_3a)} L3A records saved to: {final_api_output_file_path}")
        return True
    except Exception as e:
        print(f"❌ Error during L3A save: {e}")
        return False









    
# def level3b_item_addons():
#     """
#     Revised: Processes L3B (ItemAddons), calls the API for each addon record, and saves ONLY the API response JSON.
#     Uses safe_int() to prevent conversion errors on IDs.
#     """
#     settings = load_settings()
#     source_site_id = settings.get("source_site_id")
#     output_dir = os.path.join("output", str(source_site_id))
#     payload_file_path = os.path.join(output_dir, "api_response_final.json")
    
#     final_payload = load_json_data(payload_file_path)

#     if not final_payload:
#         print(f"❌ Failed to load final payload from {payload_file_path}. Aborting.")
#         return False
        
#     print(f"✅ Successfully loaded payload with {len(final_payload)} top-level menu records.")
    
#     # Safely retrieve destination details
#     destination_site_url = settings.get("destination_site_url")
#     destination_token = settings.get("destination_token", {}).get("token")
    
#     headers = {
#         'Content-Type': 'application/json',
#         'ms_cms_clientapp': 'ProgrammingApp',
#         'Authorization': f'Bearer {destination_token}',
#     }
    
#     all_l3_data_for_menu = []
#     processed_output_level_3b = []
    
#     # 1. Collect all L3B raw payloads (which should contain L2 IDs)
#     for menu_record in final_payload:
#         _, menu_sections_list = process_menu_level_0_only(menu_record)
#         all_item_lists = process_menu_sections_level_1_only(menu_sections_list)
        
#         for item_list in all_item_lists:
#             if item_list:
#                 l3_data_from_items = process_menu_items_level_2_only(item_list)
#                 all_l3_data_for_menu.extend(l3_data_from_items)
        
#     # Final processing step to flatten and format ItemAddons
#     final_item_addons_payloads = process_item_addons_level_3b_only_standalone(all_l3_data_for_menu)
#     print(f"\nTotal Level 3b ItemAddons payloads collected: {len(final_item_addons_payloads)}")

#     # 2. Iterate and call API for each L3B record
#     for i, item_addon_record in enumerate(final_item_addons_payloads):
#         print(f"\n--- Processing L3B ItemAddon {i+1}/{len(final_item_addons_payloads)} ---")
        
#         # --- FIX APPLIED HERE: Use safe_int() for all component IDs ---
#         componentName = item_addon_record.get("componentName", "ItemAddon")
#         parent_record_id = item_addon_record.get("ParentRecordId", 0) 
#         ParentComponentId = safe_int(item_addon_record.get("ParentComponentId"), 0)
#         MainParentComponentid = safe_int(item_addon_record.get("MainParentComponentid"), 0)
        
#         record_data = item_addon_record.get("recordJsonString")
#         if isinstance(record_data, dict):
#             record_data = json.dumps(record_data)

#         fixed_payload = {
#             "componentName": componentName,
#             "Scopeid": 5,
#             "ParentId": str(ParentComponentId), # Use the L2 Component ID (string)
#             "recordList": [
#                 {
#                     "recordJsonString": record_data,
#                     "ParentRecordId": parent_record_id,
#                     "ParentComponentId": ParentComponentId, # Use the safe integer value
#                     "MainParentComponentid": MainParentComponentid # Use the safe integer value
#                 }
#             ]
#         }
        
#         responseData = None
#         if destination_site_url and destination_token:
#             api_result = CreateComponentRecord(destination_site_url, headers, fixed_payload)

#             if isinstance(api_result, dict):
#                 responseData = api_result
#                 print("   📥 API Response Status:", responseData.get('status_code', 'N/A'), " | Success:", responseData.get('success', 'N/A'))
#             else:
#                 responseData = {"Note": "API call failed (returned non-dict/None).", "status_code": "ERROR_NON_DICT", "original_response": str(api_result)}
#                 print("   ❌ API call failed to return a valid dictionary response.")
#         else:
#             responseData = {"Note": "API call skipped due to missing settings.", "prepared_payload_example": fixed_payload}

#         # 3. Save ONLY the API response data
#         if responseData:
#             processed_output_level_3b.append(responseData)
        
#     # 4. Save API Responses
#     final_api_output_file_path = os.path.join(output_dir, "final-api-response-L3B.json") 
#     try:
#         os.makedirs(output_dir, exist_ok=True)
#         with open(final_api_output_file_path, "w", encoding='utf-8') as f:
#             json.dump(processed_output_level_3b, f, indent=4)
            
#         print(f"✅ DEBUG SUCCESS: ONLY API Responses for {len(processed_output_level_3b)} L3B records saved to: {final_api_output_file_path}")
#         return True
#     except (IOError, TypeError) as e:
#         print(f"❌ Error saving final processed output to {final_api_output_file_path}: {e}")
#         return False
    

def level3b_item_addons():
    """
    Revised: Processes L3B (ItemAddons), calls the API for each addon record, and saves ONLY the API response JSON.
    Uses safe_int() to prevent conversion errors on IDs.
    """
    settings = load_settings()
    source_site_id = settings.get("source_site_id")
    output_dir = os.path.join("output", str(source_site_id))
    payload_file_path = os.path.join(output_dir, "api_response_final.json")

    final_payload = load_json_data(payload_file_path)

    if not final_payload:
        print(f"❌ Failed to load final payload from {payload_file_path}. Aborting.")
        return False
        
    print(f"✅ Successfully loaded payload with {len(final_payload)} top-level menu records.")

    # Safely retrieve destination details
    destination_site_url = settings.get("destination_site_url")
    destination_token = settings.get("destination_token", {}).get("token")

    headers = {
        'Content-Type': 'application/json',
        'ms_cms_clientapp': 'ProgrammingApp',
        'Authorization': f'Bearer {destination_token}',
    }

    all_l3_data_for_menu = []
    processed_output_level_3b = []

    # 1. Collect all L3B raw payloads (which should contain L2 IDs)
    for menu_record in final_payload:
        _, menu_sections_list = process_menu_level_0_only(menu_record)
        all_item_lists = process_menu_sections_level_1_only(menu_sections_list)
        
        for item_list in all_item_lists:
            if item_list:
                l3_data_from_items = process_menu_items_level_2_only(item_list)
                all_l3_data_for_menu.extend(l3_data_from_items)
        
    # Final processing step to flatten and format ItemAddons
    final_item_addons_payloads = process_item_addons_level_3b_only_standalone(all_l3_data_for_menu)
    print(f"\nTotal Level 3b ItemAddons payloads collected: {len(final_item_addons_payloads)}")

    # 2. Iterate and call API for each L3B record
    for i, item_addon_record in enumerate(final_item_addons_payloads):
        print(f"\n--- Processing L3B ItemAddon {i+1}/{len(final_item_addons_payloads)} ---")
        
        # --- FIX APPLIED HERE: Use safe_int() for all component IDs ---
        componentName = item_addon_record.get("componentName", "ItemAddon")
        parent_record_id = item_addon_record.get("ParentRecordId", 0) 
        ParentComponentId = safe_int(item_addon_record.get("ParentComponentId"), 0)
        MainParentComponentid = safe_int(item_addon_record.get("MainParentComponentid"), 0)
        
        record_data = item_addon_record.get("recordJsonString")
        if isinstance(record_data, dict):
            record_data = json.dumps(record_data)

        fixed_payload = {
            "componentName": componentName,
            "Scopeid": 5,
            "ParentId": str(ParentComponentId), # Use the L2 Component ID (string)
            "recordList": [
                {
                    "recordJsonString": record_data,
                    "ParentRecordId": parent_record_id,
                    "ParentComponentId": ParentComponentId, # Use the safe integer value
                    "MainParentComponentid": MainParentComponentid # Use the safe integer value
                }
            ]
        }
        
        responseData = None
        if destination_site_url and destination_token:
            api_result = CreateComponentRecord(destination_site_url, headers, fixed_payload)

            if isinstance(api_result, dict):
                responseData = api_result
                
                # --- FIX APPLIED HERE: Use 'ErrorCode' for status and 'Success' (capital S) ---
                status_code = responseData.get('ErrorCode', 'N/A')
                success_status = responseData.get('Success', 'N/A')
                print(f"  📥 API Response Status: {status_code} | Success: {success_status}")
                # --- END FIX ---
                
            else:
                responseData = {"Note": "API call failed (returned non-dict/None).", "status_code": "ERROR_NON_DICT", "original_response": str(api_result)}
                print("  ❌ API call failed to return a valid dictionary response.")
        else:
            responseData = {"Note": "API call skipped due to missing settings.", "prepared_payload_example": fixed_payload}

        # 3. Save ONLY the API response data
        if responseData:
            processed_output_level_3b.append(responseData)
            
    # 4. Save API Responses
    final_api_output_file_path = os.path.join(output_dir, "final-api-response-L3B.json") 
    try:
        os.makedirs(output_dir, exist_ok=True)
        with open(final_api_output_file_path, "w", encoding='utf-8') as f:
            json.dump(processed_output_level_3b, f, indent=4)
            
        print(f"✅ DEBUG SUCCESS: ONLY API Responses for {len(processed_output_level_3b)} L3B records saved to: {final_api_output_file_path}")
        return True
    except (IOError, TypeError) as e:
        print(f"❌ Error saving final processed output to {final_api_output_file_path}: {e}")
        return False
# ------------------------------------------------------------------
# --- MASTER CALLER FUNCTION (All levels active) ---
# ------------------------------------------------------------------


def add_menu_data():
    """
    Runs all level-specific orchestration functions sequentially for full debugging.
    Note: Each function will overwrite 'final-api-response.json' unless they are 
    modified to save to unique files (as done here in the restored versions).
    """
    # print("last steop")
    # exit()
    level0()
    print("Level0 clear-------------------------------------------------------------------")

    level1()
    print("Level1 clear-------------------------------------------------------------------")
    level2()
    print("Level2 clear-------------------------------------------------------------------")
    level3a_item_prices()
    print("Level3a clear-------------------------------------------------------------------")
    level3b_item_addons()
    print("Level3b clear-------------------------------------------------------------------")