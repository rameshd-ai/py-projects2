"""
Step 4: Dine Menu Migration
Handles menu data migration from source to destination site
Note: Menu data is migrated to destination site, so uses destination URL and token
"""
import os
import json
import uuid
import time
import logging
import zipfile
from typing import Dict, Any, List, Tuple
from urllib.parse import urlparse

from apis import (
    menu_download_api, getComponentInfo, export_mi_block_component,
    CreateComponentRecord, addUpdateRecordsToCMS
)
from utils import get_job_folder, get_job_output_folder, ensure_job_folders
from config import BASE_DIR

logger = logging.getLogger(__name__)

# Resource file paths
RESOURCE_DIR = os.path.join(BASE_DIR, "resource")
MENU_FIELD_MAPPER = os.path.join(RESOURCE_DIR, "menu_field_mapper.json")
MENU_PAYLOAD_TEMPLATE = os.path.join(RESOURCE_DIR, "menu_payload_template.json")


def load_json_data(file_path: str) -> Dict[str, Any]:
    """Safely load JSON data from file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load JSON from {file_path}: {e}")
        return {}


def download_and_save_menu_data(job_id: str, source_url: str) -> bool:
    """
    Downloads menu data from the source URL and saves it to job folder
    """
    logger.info(f"Starting menu data download for job {job_id} from {source_url}")
    
    ensure_job_folders(job_id)
    output_dir = get_job_folder(job_id)
    output_file_path = os.path.join(output_dir, "menu_api_response_input.json")
    
    response_data = menu_download_api(source_url)
    
    if response_data:
        try:
            with open(output_file_path, "w", encoding='utf-8') as f:
                json.dump(response_data, f, indent=4)
            logger.info(f"Successfully saved menu data to: {output_file_path}")
            return True
        except IOError as e:
            logger.error(f"Error saving file to {output_file_path}: {e}")
            return False
    else:
        logger.error("No data received from menu API")
        return False


def payload_mapper(job_id: str) -> bool:
    """
    Maps menu data using field mapper and saves mapped payload
    """
    logger.info(f"Mapping menu payload for job {job_id}")
    
    # Load mapper
    mapper = load_json_data(MENU_FIELD_MAPPER)
    if not mapper:
        logger.error(f"Could not load mapping data from {MENU_FIELD_MAPPER}")
        return False
    
    # Load source data
    input_file_path = os.path.join(get_job_folder(job_id), "menu_api_response_input.json")
    source_data = load_json_data(input_file_path)
    
    if not source_data:
        logger.error(f"Could not load data from {input_file_path}")
        return False
    
    mapped_payload = []
    
    # Iterate through each Menu in the source data
    for source_menu in source_data:
        mapped_menu = {}
        # Map level 0 fields
        for dest_key, src_key in mapper.get("level 0", {}).items():
            mapped_menu[dest_key] = source_menu.get(src_key)
        
        mapped_menu["MenuSections"] = []
        
        # Iterate through each Section within the Menu
        source_sections = source_menu.get("Sections", [])
        for source_section in source_sections:
            mapped_section = {}
            # Map level 1 fields
            for dest_key, src_key in mapper.get("level 1", {}).items():
                mapped_section[dest_key] = source_section.get(src_key)
            
            mapped_section["MenuItems"] = []
            
            # Iterate through each Item within the Section
            source_items = source_section.get("Items", [])
            for source_item in source_items:
                mapped_item = {}
                # Map level 2 fields
                for dest_key, src_key in mapper.get("level 2", {}).items():
                    mapped_item[dest_key] = source_item.get(src_key)
                
                # Map Level 3: ItemPrices
                mapped_item["ItemPrices"] = []
                price_mapper = mapper.get("level 3_prices", {})
                source_prices = source_item.get("ItemPrices", [])
                for source_price in source_prices:
                    mapped_price = {}
                    for dest_key, src_key in price_mapper.items():
                        mapped_price[dest_key] = source_price.get(src_key)
                    mapped_item["ItemPrices"].append(mapped_price)
                
                # Map Level 3: ItemAddons
                mapped_item["ItemAddons"] = []
                addon_mapper = mapper.get("level 3_addons", {})
                source_addons = source_item.get("ItemAddons", [])
                for source_addon in source_addons:
                    mapped_addon = {}
                    for dest_key, src_key in addon_mapper.items():
                        mapped_addon[dest_key] = source_addon.get(src_key)
                    mapped_item["ItemAddons"].append(mapped_addon)
                
                mapped_section["MenuItems"].append(mapped_item)
            
            mapped_menu["MenuSections"].append(mapped_section)
        
        mapped_payload.append(mapped_menu)
    
    # Save mapped payload
    output_file_path = os.path.join(get_job_folder(job_id), "menu_api_response_output.json")
    try:
        with open(output_file_path, "w", encoding='utf-8') as f:
            json.dump(mapped_payload, f, indent=4)
        logger.info(f"Payload mapping completed and saved to: {output_file_path}")
        return True
    except IOError as e:
        logger.error(f"Error saving mapped payload: {e}")
        return False


def payload_creator(job_id: str) -> bool:
    """
    Creates final payload structure using template
    """
    logger.info(f"Creating final menu payload for job {job_id}")
    
    # Load template
    template = load_json_data(MENU_PAYLOAD_TEMPLATE)
    if not template:
        logger.error(f"Could not load template from {MENU_PAYLOAD_TEMPLATE}")
        return False
    
    # Load mapped data
    mapped_data_path = os.path.join(get_job_folder(job_id), "menu_api_response_output.json")
    mapped_data = load_json_data(mapped_data_path)
    if not mapped_data:
        logger.error(f"Could not load mapped data from {mapped_data_path}")
        return False
    
    # Extract component names and templates
    menu_component_name = template.get("level 0", {}).get("componentName")
    section_component_name = template.get("level 1", {}).get("componentName")
    item_component_name = template.get("level 2", {}).get("componentName")
    price_component_name = template.get("level 3_prices", {}).get("componentName")
    addon_component_name = template.get("level 3_addons", {}).get("componentName")
    
    menu_template = template.get("level 0", {}).get("recordList", [{}])[0].get("recordJsonString", {})
    section_template = template.get("level 1", {}).get("recordList", [{}])[0].get("recordJsonString", {})
    item_template = template.get("level 2", {}).get("recordList", [{}])[0].get("recordJsonString", {})
    price_template = template.get("level 3_prices", {}).get("recordList", [{}])[0].get("recordJsonString", {})
    addon_template = template.get("level 3_addons", {}).get("recordList", [{}])[0].get("recordJsonString", {})
    
    final_payload = []
    
    # Process each menu
    for menu_data in mapped_data:
        menu_record_json = {}
        for key in menu_template:
            menu_record_json[key] = menu_data.get(key, None)
        
        menu_output = {
            "recordJsonString": menu_record_json,
            "ParentRecordId": "",
            "ParentComponentId": "",
            "MainParentComponentid": "",
            "status": "",
            "componentName": menu_component_name,
            "MenuSections": []
        }
        
        # Process sections
        for section_data in menu_data.get("MenuSections", []):
            section_record_json = {}
            for key in section_template:
                section_record_json[key] = section_data.get(key, None)
            
            section_output = {
                "recordJsonString": section_record_json,
                "ParentRecordId": "",
                "ParentComponentId": "",
                "MainParentComponentid": "",
                "componentName": section_component_name,
                "status": "",
                "MenuItems": []
            }
            
            # Process items
            for item_data in section_data.get("MenuItems", []):
                item_record_json = {}
                for key in item_template:
                    item_record_json[key] = item_data.get(key, None)
                
                item_record_json["ItemPrices"] = []
                item_record_json["ItemAddons"] = []
                
                # Process prices
                for price_data in item_data.get("ItemPrices", []):
                    price_record_json = {}
                    for key in price_template:
                        price_record_json[key] = price_data.get(key, None)
                    
                    price_output = {
                        "recordJsonString": price_record_json,
                        "ParentRecordId": "",
                        "ParentComponentId": "",
                        "MainParentComponentid": "",
                        "componentName": price_component_name
                    }
                    item_record_json["ItemPrices"].append(price_output)
                
                # Process addons
                for addon_data in item_data.get("ItemAddons", []):
                    addon_record_json = {}
                    for key in addon_template:
                        addon_record_json[key] = addon_data.get(key, None)
                    
                    addon_output = {
                        "recordJsonString": addon_record_json,
                        "ParentRecordId": "",
                        "ParentComponentId": "",
                        "MainParentComponentid": "",
                        "componentName": addon_component_name
                    }
                    item_record_json["ItemAddons"].append(addon_output)
                
                item_output = {
                    "recordJsonString": item_record_json,
                    "ParentRecordId": "",
                    "ParentComponentId": "",
                    "MainParentComponentid": "",
                    "componentName": item_component_name
                }
                section_output["MenuItems"].append(item_output)
            
            menu_output["MenuSections"].append(section_output)
        
        final_payload.append(menu_output)
    
    # Save final payload
    output_file_path = os.path.join(get_job_folder(job_id), "menu_api_response_final.json")
    try:
        ensure_job_folders(job_id)
        with open(output_file_path, "w", encoding='utf-8') as f:
            json.dump(final_payload, f, indent=4)
        logger.info(f"Final payload created and saved to: {output_file_path}")
        return True
    except IOError as e:
        logger.error(f"Error saving final payload: {e}")
        return False


def preprocess_menu_data(job_id: str, destination_url: str, destination_site_id: str, destination_token: str) -> str:
    """
    Exports Menu component, creates component map, and updates payload with component IDs
    Returns the mi-block folder name if successful, None otherwise
    """
    logger.info(f"Preprocessing menu data for job {job_id}")
    
    headers = {
        'Content-Type': 'application/json',
        'ms_cms_clientapp': 'ProgrammingApp',
        'Authorization': f'Bearer {destination_token}',
    }
    
    # Get component info
    responseData = getComponentInfo("Menu", destination_url, headers)
    
    if not responseData or not isinstance(responseData, list) or len(responseData) == 0:
        logger.error("Invalid response from getComponentInfo")
        return None
    
    component_id = responseData[0].get('Id')
    if not component_id:
        logger.error("Component ID not found in API response")
        return None
    
    logger.info(f"Found Menu component ID: {component_id}")
    
    # Export component
    response_content, content_disposition = export_mi_block_component(
        destination_url, component_id, destination_site_id, headers
    )
    
    miBlockId = component_id
    mi_block_folder = f"mi-block-ID-{miBlockId}"
    output_dir = get_job_folder(job_id)
    save_folder = os.path.join(output_dir, mi_block_folder)
    payload_file_path = os.path.join(output_dir, "menu_api_response_final.json")
    os.makedirs(save_folder, exist_ok=True)
    
    try:
        # Save and unzip exported file
        if response_content:
            filename = (
                content_disposition.split('filename=')[1].strip('"')
                if content_disposition and 'filename=' in content_disposition
                else f"menu_export_{job_id}.zip"
            )
            file_path = os.path.join(save_folder, filename)
            
            with open(file_path, "wb") as file:
                file.write(response_content)
            
            if zipfile.is_zipfile(file_path):
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    zip_ref.extractall(save_folder)
                os.remove(file_path)
        
        time.sleep(1)
        
        # Convert .txt files to .json
        for extracted_file in os.listdir(save_folder):
            extracted_file_path = os.path.join(save_folder, extracted_file)
            try:
                if extracted_file.endswith('.txt'):
                    new_file_path = os.path.splitext(extracted_file_path)[0] + '.json'
                    with open(extracted_file_path, 'r', encoding="utf-8") as txt_file:
                        content = txt_file.read()
                        if not content.strip():
                            os.remove(extracted_file_path)
                            continue
                        json_content = json.loads(content)
                        with open(new_file_path, 'w', encoding="utf-8") as json_file:
                            json.dump(json_content, json_file, indent=4)
                        os.remove(extracted_file_path)
            except (json.JSONDecodeError, OSError) as e:
                logger.error(f"Error processing file {extracted_file_path}: {e}")
                continue
        
        time.sleep(1)
        
        # Create component map
        config_file_name = "MiBlockComponentConfig.json"
        config_file_path = os.path.join(save_folder, config_file_name)
        
        name_to_id_map = {}
        main_parent_id = None
        
        if os.path.exists(config_file_path):
            config_data = load_json_data(config_file_path)
            if config_data:
                component_list = config_data.get('component', [])
                
                # Find main parent ID
                for component in component_list:
                    parent_id_value = component.get('ParentId')
                    if parent_id_value is None or parent_id_value == 0 or parent_id_value == "":
                        main_parent_id = component.get('ComponentId')
                        break
                
                # Build map
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
                
                map_file_path = os.path.join(output_dir, "menu_component_name_id_map.json")
                with open(map_file_path, 'w', encoding='utf-8') as f:
                    json.dump(name_to_id_map, f, indent=4)
                
                logger.info(f"Created component name map: {map_file_path}")
                
                # Update display orders
                update_display_orders_in_payload(payload_file_path)
                
                return mi_block_folder
    except Exception as e:
        logger.error(f"Error during file processing: {e}", exc_info=True)
        return None
    
    return None


def update_display_orders_in_payload(file_path: str) -> bool:
    """Updates display orders in payload file"""
    data = load_json_data(file_path)
    if not data:
        return False
    
    try:
        updated_data = reset_display_orders(data)
        with open(file_path, "w", encoding='utf-8') as f:
            json.dump(updated_data, f, indent=4)
        logger.info(f"Display orders updated in {file_path}")
        return True
    except Exception as e:
        logger.error(f"Error updating display orders: {e}")
        return False


def reset_display_orders(data: List[Dict]) -> List[Dict]:
    """Recursively reset display orders starting from 1"""
    if isinstance(data, list):
        for idx, item in enumerate(data, 1):
            if isinstance(item, dict):
                record_data = item.get('recordJsonString', {})
                if isinstance(record_data, dict):
                    record_data['displayorder'] = idx
                
                # Recurse into MenuSections
                if 'MenuSections' in item:
                    item['MenuSections'] = reset_display_orders(item['MenuSections'])
                
                # Recurse into MenuItems
                if 'MenuItems' in item:
                    item['MenuItems'] = reset_display_orders(item['MenuItems'])
                
                # Recurse into ItemPrices and ItemAddons
                if isinstance(record_data, dict):
                    if 'ItemPrices' in record_data:
                        record_data['ItemPrices'] = reset_display_orders(record_data['ItemPrices'])
                    if 'ItemAddons' in record_data:
                        record_data['ItemAddons'] = reset_display_orders(record_data['ItemAddons'])
    
    return data


# Helper functions for extracting menu data at each level
def process_menu_level_0_only(menu_record: Dict) -> Tuple[Dict, List]:
    """L0 Extractor: Returns L0 payload and L1 MenuSections list."""
    menu_payload = menu_record.copy()
    menu_sections = menu_payload.pop('MenuSections', [])
    return menu_payload, menu_sections

def process_menu_sections_level_1_only(section_list: List) -> List:
    """L1 Extractor: Returns a list containing all L2 MenuItems lists."""
    all_menu_items = []
    for section_record in section_list:
        menu_items = section_record.copy().pop('MenuItems', [])
        all_menu_items.append(menu_items)
    return all_menu_items

def process_menu_items_level_2_only(item_list: List) -> List:
    """L2 Extractor: Returns a list of dictionaries containing raw L3 data (prices/addons)."""
    all_l3_data = []
    for item_record in item_list:
        item_json_string = item_record.copy().get('recordJsonString', {})
        item_prices = item_json_string.get('ItemPrices', [])
        item_addons = item_json_string.get('ItemAddons', [])
        
        all_l3_data.append({
            "item_name": item_json_string.get('item-name', 'Unnamed Item'),
            "item_prices": item_prices,
            "item_addons": item_addons,
            "item_record": item_record  # Keep reference to item record for ParentRecordId
        })
    return all_l3_data

def process_item_prices_level_3a_only_standalone(l3_data_list: List) -> List:
    """Handles Level 3a: Item Prices. Collects ONLY the price payloads."""
    all_prices_payloads = []
    for item_data in l3_data_list:
        item_name = item_data.get('item_name', 'Unnamed Item')
        prices = item_data.get('item_prices', [])
        item_record = item_data.get('item_record', {})
        for price_record in prices:
            price_payload = price_record.copy()
            price_payload['source_item_name'] = item_name
            price_payload['item_record_ref'] = item_record  # Keep reference for ParentRecordId
            all_prices_payloads.append(price_payload)
    return all_prices_payloads

def process_item_addons_level_3b_only_standalone(l3_data_list: List) -> List:
    """Handles Level 3b: Item Addons. Collects ONLY the addon payloads."""
    all_addons_payloads = []
    for item_data in l3_data_list:
        item_name = item_data.get('item_name', 'Unnamed Item')
        addons = item_data.get('item_addons', [])
        item_record = item_data.get('item_record', {})
        for addon_record in addons:
            addon_payload = addon_record.copy()
            addon_payload['source_item_name'] = item_name
            addon_payload['item_record_ref'] = item_record  # Keep reference for ParentRecordId
            all_addons_payloads.append(addon_payload)
    return all_addons_payloads

def safe_int(value: Any, default: int = 0) -> int:
    """Safely converts a value (including None or empty string) to an integer."""
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


def process_menu_levels(job_id: str, destination_url: str, destination_site_id: str, destination_token: str) -> bool:
    """
    Processes all menu levels (0, 1, 2, 3a, 3b) and creates records in destination
    Based on reference implementation from osb menu - faq migration
    """
    print("\n" + "="*80, flush=True)
    print(f"[MENU PROCESSING] STARTING MENU LEVEL PROCESSING", flush=True)
    print("="*80, flush=True)
    print(f"Job ID: {job_id}", flush=True)
    print(f"Destination URL: {destination_url}", flush=True)
    print(f"Destination Site ID: {destination_site_id}", flush=True)
    print(f"Has Token: {bool(destination_token)}", flush=True)
    print("="*80, flush=True)
    logger.info(f"Processing menu levels for job {job_id}")
    
    # Load component map
    component_map_file = os.path.join(get_job_folder(job_id), "menu_component_name_id_map.json")
    print(f"\n[LOAD] Loading component map from: {component_map_file}", flush=True)
    component_map_data = load_json_data(component_map_file)
    if not component_map_data:
        error_msg = f"Component map not found at {component_map_file}"
        print(f"[ERROR] {error_msg}", flush=True)
        logger.error(error_msg)
        return False
    print(f"[OK] Component map loaded successfully", flush=True)
    
    # Load final payload
    payload_file_path = os.path.join(get_job_folder(job_id), "menu_api_response_final.json")
    print(f"\n[LOAD] Loading final payload from: {payload_file_path}", flush=True)
    final_payload = load_json_data(payload_file_path)
    if not final_payload:
        error_msg = f"Final payload not found at {payload_file_path}"
        print(f"[ERROR] {error_msg}", flush=True)
        logger.error(error_msg)
        return False
    print(f"[OK] Final payload loaded successfully. Menu records: {len(final_payload)}", flush=True)
    
    headers = {
        'Content-Type': 'application/json',
        'ms_cms_clientapp': 'ProgrammingApp',
        'Authorization': f'Bearer {destination_token}',
    }
    
    # Extract component IDs from map
    menu_info = component_map_data.get("Menu", {})
    l0_component_id = menu_info.get("ComponentId")
    l0_main_parent_id = menu_info.get("MainParentComponentid")
    l1_component_id = component_map_data.get("Menu Section", {}).get("ComponentId")
    l2_component_id = component_map_data.get("Menu Section Item", {}).get("ComponentId")
    l3_price_component_id = component_map_data.get("Menu Section Item Price Options", {}).get("ComponentId")
    l3_addon_component_id = component_map_data.get("Menu Section Item Addons", {}).get("ComponentId")
    
    if not all([l0_component_id, l0_main_parent_id, l1_component_id, l2_component_id, l3_price_component_id, l3_addon_component_id]):
        error_msg = "Missing required component IDs in component map"
        print(f"\n[ERROR] {error_msg}", flush=True)
        print(f"[DEBUG] Component IDs found:", flush=True)
        print(f"  L0 (Menu): {l0_component_id}", flush=True)
        print(f"  L0 Main Parent: {l0_main_parent_id}", flush=True)
        print(f"  L1 (Section): {l1_component_id}", flush=True)
        print(f"  L2 (Item): {l2_component_id}", flush=True)
        print(f"  L3a (Price): {l3_price_component_id}", flush=True)
        print(f"  L3b (Addon): {l3_addon_component_id}", flush=True)
        logger.error(error_msg)
        return False
    
    print(f"\n[OK] All component IDs found. Starting API calls...", flush=True)
    print(f"  L0 Component ID: {l0_component_id}", flush=True)
    print(f"  L1 Component ID: {l1_component_id}", flush=True)
    print(f"  L2 Component ID: {l2_component_id}", flush=True)
    print(f"  L3a Component ID: {l3_price_component_id}", flush=True)
    print(f"  L3b Component ID: {l3_addon_component_id}", flush=True)
    
    # ========== LEVEL 0: Process Menus ==========
    print("\n" + "="*80, flush=True)
    print(f"[LEVEL 0] PROCESSING MENU RECORDS (BATCH MODE)", flush=True)
    print("="*80, flush=True)
    logger.info("Processing Level 0: Menu records...")
    
    # Collect all Level 0 records first
    l0_records = []
    l0_menu_mapping = []  # Track which menu_record each payload belongs to
    
    for idx, menu_record in enumerate(final_payload):
        menu_payload, _ = process_menu_level_0_only(menu_record)
        record_data_dict = menu_payload.get("recordJsonString", {}).copy()
        
        # Status/DisplayOrder logic
        internal_status = record_data_dict.get("status", 1)
        converted_integer_status = 0 if internal_status == 2 else int(internal_status)
        root_status_boolean = (converted_integer_status == 1)
        display_order = record_data_dict.get("displayorder", 0)
        
        # Remove redundant fields
        record_data_dict.pop("status", None)
        record_data_dict.pop("displayorder", None)
        record_data = json.dumps(record_data_dict)
        
        # Build API payload
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
        l0_records.append(single_record_payload)
        l0_menu_mapping.append((idx, menu_record))
    
    # Send all Level 0 records in batches
    if l0_records:
        print(f"[BATCH] Sending {len(l0_records)} Level 0 records in batches...", flush=True)
        api_payload = {f"{l0_component_id}_L0": l0_records}
        success, responseData = addUpdateRecordsToCMS(destination_url, headers, api_payload, batch_size=10)
        
        if success:
            # Map responses back to menu records (responseData is now a list indexed by order)
            for idx, (menu_idx, menu_record) in enumerate(l0_menu_mapping):
                created_record_id = None
                
                # Get response by index (responses are in same order as requests)
                if isinstance(responseData, list) and idx < len(responseData):
                    created_record_id = responseData[idx]
                elif isinstance(responseData, dict):
                    # Fallback: try to get by index key
                    created_record_id = responseData.get(idx) or responseData.get(str(idx))
                
                # Validate the record ID
                if created_record_id and isinstance(created_record_id, int) and created_record_id > 0:
                    print(f"[SUCCESS] Level 0 Menu {idx+1} created with Record ID: {created_record_id}", flush=True)
                    logger.info(f"Level 0 Menu {idx+1} created successfully with Record ID: {created_record_id}")
                    
                    # Update payload with created ID for children
                    if isinstance(menu_record, dict) and 'MenuSections' in menu_record:
                        for section in menu_record['MenuSections']:
                            section['ParentRecordId'] = created_record_id
                            section['ParentComponentId'] = str(l1_component_id)
                            section['MainParentComponentid'] = l0_main_parent_id
                else:
                    logger.warning(f"L0 Menu {idx+1} API call succeeded but couldn't extract record ID. Response: {created_record_id}, Type: {type(created_record_id)}")
                    print(f"[WARNING] L0 Menu {idx+1} - Invalid record ID: {created_record_id}", flush=True)
        else:
            logger.error(f"L0 batch API call failed. Response: {responseData}")
            print(f"[ERROR] L0 batch API call failed. Response: {responseData}", flush=True)
            return False
    
    # Save updated payload
    try:
        with open(payload_file_path, "w", encoding='utf-8') as f:
            json.dump(final_payload, f, indent=4)
        logger.info("Level 0 processing completed and payload saved")
    except Exception as e:
        logger.error(f"Error saving L0 final payload: {e}")
        return False
    
    time.sleep(1)
    
    # ========== LEVEL 1: Process Sections ==========
    print("\n" + "="*80, flush=True)
    print(f"[LEVEL 1] PROCESSING MENU SECTION RECORDS (BATCH MODE)", flush=True)
    print("="*80, flush=True)
    logger.info("Processing Level 1: Menu Section records...")
    
    # Collect all Level 1 records first
    l1_records = []
    l1_section_mapping = []  # Track which section_record each payload belongs to
    
    for menu_record in final_payload:
        _, menu_sections_list = process_menu_level_0_only(menu_record)
        
        for section_record in menu_sections_list:
            parent_record_id = section_record.get("ParentRecordId", 0)
            if parent_record_id == 0:
                continue
            
            section_record_copy = section_record.copy()
            section_record_copy.pop('MenuItems', None)
            record_data_dict = section_record_copy.get("recordJsonString", {}).copy()
            
            # Status/DisplayOrder logic
            internal_status = record_data_dict.get("status", 1)
            converted_integer_status = 0 if internal_status == 2 else int(internal_status)
            root_status_boolean = (converted_integer_status == 1)
            display_order = record_data_dict.get("displayorder", 0)
            
            # Remove redundant fields
            record_data_dict.pop("status", None)
            record_data_dict.pop("displayorder", None)
            record_data = json.dumps(record_data_dict)
            
            # Build API payload
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
            l1_records.append(single_record_payload)
            l1_section_mapping.append(section_record)
    
    # Send all Level 1 records in batches
    if l1_records:
        print(f"[BATCH] Sending {len(l1_records)} Level 1 records in batches...", flush=True)
        api_payload = {f"{l1_component_id}_L1": l1_records}
        success, responseData = addUpdateRecordsToCMS(destination_url, headers, api_payload, batch_size=10)
        
        if success:
            # Map responses back to section records (responseData is now a list indexed by order)
            for idx, section_record in enumerate(l1_section_mapping):
                created_record_id = None
                
                # Get response by index (responses are in same order as requests)
                if isinstance(responseData, list) and idx < len(responseData):
                    created_record_id = responseData[idx]
                elif isinstance(responseData, dict):
                    # Fallback: try to get by index key
                    created_record_id = responseData.get(idx) or responseData.get(str(idx))
                
                # Validate the record ID
                if created_record_id and isinstance(created_record_id, int) and created_record_id > 0:
                    print(f"[SUCCESS] Level 1 Section {idx+1} created with Record ID: {created_record_id}", flush=True)
                    logger.info(f"Level 1 Section {idx+1} created successfully with Record ID: {created_record_id}")
                    
                    # Update payload with created ID for children
                    section_record['NewRecordId_L1'] = created_record_id
                    if 'MenuItems' in section_record and section_record['MenuItems'] is not None:
                        for item in section_record['MenuItems']:
                            item['ParentRecordId'] = created_record_id
                            item['ParentComponentId'] = str(l2_component_id)
                            item['MainParentComponentid'] = l0_main_parent_id
                else:
                    logger.warning(f"L1 Section {idx+1} API call succeeded but couldn't extract record ID. Response: {created_record_id}, Type: {type(created_record_id)}")
                    print(f"[WARNING] L1 Section {idx+1} - Invalid record ID: {created_record_id}", flush=True)
        else:
            logger.error(f"L1 batch API call failed. Response: {responseData}")
            print(f"[ERROR] L1 batch API call failed. Response: {responseData}", flush=True)
            return False
    
    # Save updated payload
    try:
        with open(payload_file_path, "w", encoding='utf-8') as f:
            json.dump(final_payload, f, indent=4)
        logger.info("Level 1 processing completed and payload saved")
    except Exception as e:
        logger.error(f"Error saving L1 final payload: {e}")
        return False
    
    time.sleep(1)
    
    # ========== LEVEL 2: Process Items ==========
    print("\n" + "="*80, flush=True)
    print(f"[LEVEL 2] PROCESSING MENU ITEM RECORDS (BATCH MODE)", flush=True)
    print("="*80, flush=True)
    logger.info("Processing Level 2: Menu Item records...")
    
    # Collect all Level 2 records first
    l2_records = []
    l2_item_mapping = []  # Track which item_record each payload belongs to
    
    for menu_record in final_payload:
        _, menu_sections_list = process_menu_level_0_only(menu_record)
        all_item_lists = process_menu_sections_level_1_only(menu_sections_list)
        
        for item_list in all_item_lists:
            for item_record in item_list:
                parent_record_id = item_record.get("ParentRecordId", 0)
                if parent_record_id == 0:
                    continue
                
                item_json_string_ref = item_record.get('recordJsonString', {})
                l3_prices = item_json_string_ref.get('ItemPrices', [])
                l3_addons = item_json_string_ref.get('ItemAddons', [])
                
                payload_json_string = item_json_string_ref.copy()
                payload_json_string.pop('ItemPrices', None)
                payload_json_string.pop('ItemAddons', None)
                
                # Status/DisplayOrder logic
                internal_status = payload_json_string.get("status", 1)
                converted_integer_status = 0 if internal_status == 2 else int(internal_status)
                root_status_boolean = (converted_integer_status == 1)
                display_order = payload_json_string.get("displayorder", 0)
                
                # Remove redundant fields
                payload_json_string.pop("status", None)
                payload_json_string.pop("displayorder", None)
                record_data = json.dumps(payload_json_string)
                
                # Build API payload
                single_record_payload = {
                    "componentId": int(l2_component_id),
                    "recordId": 0,
                    "parentRecordId": parent_record_id,
                    "recordDataJson": record_data,
                    "status": root_status_boolean,
                    "tags": [],
                    "displayOrder": display_order,
                    "updatedBy": 0,
                }
                l2_records.append(single_record_payload)
                l2_item_mapping.append((item_record, l3_prices, l3_addons))
    
    # Send all Level 2 records in batches
    if l2_records:
        print(f"[BATCH] Sending {len(l2_records)} Level 2 records in batches...", flush=True)
        api_payload = {f"{l2_component_id}_L2": l2_records}
        success, responseData = addUpdateRecordsToCMS(destination_url, headers, api_payload, batch_size=10)
        
        if success:
            # Map responses back to item records (responseData is now a list indexed by order)
            for idx, (item_record, l3_prices, l3_addons) in enumerate(l2_item_mapping):
                created_record_id = None
                
                # Get response by index (responses are in same order as requests)
                if isinstance(responseData, list) and idx < len(responseData):
                    created_record_id = responseData[idx]
                elif isinstance(responseData, dict):
                    # Fallback: try to get by index key
                    created_record_id = responseData.get(idx) or responseData.get(str(idx))
                
                # Validate the record ID
                if created_record_id and isinstance(created_record_id, int) and created_record_id > 0:
                    print(f"[SUCCESS] Level 2 Item {idx+1} created with Record ID: {created_record_id}", flush=True)
                    logger.info(f"Level 2 Item {idx+1} created successfully with Record ID: {created_record_id}")
                    
                    # Update L3 children with the new L2 ID
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
                else:
                    logger.warning(f"L2 Item {idx+1} API call succeeded but couldn't extract record ID. Response: {created_record_id}, Type: {type(created_record_id)}")
                    print(f"[WARNING] L2 Item {idx+1} - Invalid record ID: {created_record_id}", flush=True)
        else:
            logger.error(f"L2 batch API call failed. Response: {responseData}")
            print(f"[ERROR] L2 batch API call failed. Response: {responseData}", flush=True)
            return False
    
    # Save updated payload
    try:
        with open(payload_file_path, "w", encoding='utf-8') as f:
            json.dump(final_payload, f, indent=4)
        logger.info("Level 2 processing completed and payload saved")
    except Exception as e:
        logger.error(f"Error saving L2 final payload: {e}")
        return False
    
    time.sleep(1)
    
    # ========== LEVEL 3a: Process Item Prices ==========
    logger.info("Processing Level 3a: Item Price records...")
    all_l3_data_for_menu = []
    processed_output_level_3a = []
    
    # Collect all L3a raw payloads
    for menu_record in final_payload:
        _, menu_sections_list = process_menu_level_0_only(menu_record)
        all_item_lists = process_menu_sections_level_1_only(menu_sections_list)
        
        for item_list in all_item_lists:
            if item_list:
                l3_data_from_items = process_menu_items_level_2_only(item_list)
                all_l3_data_for_menu.extend(l3_data_from_items)
    
    # Final processing step to flatten and format ItemPrices
    final_item_prices_payloads = process_item_prices_level_3a_only_standalone(all_l3_data_for_menu)
    logger.info(f"Total Level 3a ItemPrices payloads collected: {len(final_item_prices_payloads)}")
    
    # Iterate and call API for each L3a record
    for i, item_price_record in enumerate(final_item_prices_payloads):
        logger.info(f"Processing L3A ItemPrice {i+1}/{len(final_item_prices_payloads)}")
        
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
            "ParentId": str(ParentComponentId),
            "recordList": [
                {
                    "recordJsonString": record_data,
                    "ParentRecordId": parent_record_id,
                    "ParentComponentId": ParentComponentId,
                    "MainParentComponentid": MainParentComponentid
                }
            ]
        }
        
        responseData = None
        print(f"[API] Calling CreateComponentRecord for Level 3a (Price) {i+1}/{len(final_item_prices_payloads)}...", flush=True)
        logger.info(f"Calling CreateComponentRecord for Level 3a price record, Parent Record ID: {parent_record_id}")
        api_result = CreateComponentRecord(destination_url, headers, fixed_payload)
        
        if isinstance(api_result, dict):
            responseData = api_result
            status_code = responseData.get('ErrorCode', 'N/A')
            success_status = responseData.get('Success', 'N/A')
            logger.info(f"L3A API Response Status: {status_code} | Success: {success_status}")
            print(f"[SUCCESS] Level 3a Price API call completed. Status: {status_code}, Success: {success_status}", flush=True)
        else:
            responseData = {"Note": "API call failed (returned non-dict/None).", "status_code": "ERROR_NON_DICT", "original_response": str(api_result)}
            logger.error("L3A API call failed to return a valid dictionary response.")
            print(f"[ERROR] L3A API call failed. Response: {api_result}", flush=True)
        
        if responseData:
            processed_output_level_3a.append(responseData)
    
    # Save API Responses
    final_api_output_file_path = os.path.join(get_job_folder(job_id), "final-api-response-L3A.json")
    try:
        with open(final_api_output_file_path, "w", encoding='utf-8') as f:
            json.dump(processed_output_level_3a, f, indent=4)
        logger.info(f"Level 3a API responses saved: {len(processed_output_level_3a)} records")
    except Exception as e:
        logger.error(f"Error saving L3A responses: {e}")
        return False
    
    time.sleep(1)
    
    # ========== LEVEL 3b: Process Item Addons ==========
    logger.info("Processing Level 3b: Item Addon records...")
    all_l3_data_for_menu = []
    processed_output_level_3b = []
    
    # Collect all L3b raw payloads
    for menu_record in final_payload:
        _, menu_sections_list = process_menu_level_0_only(menu_record)
        all_item_lists = process_menu_sections_level_1_only(menu_sections_list)
        
        for item_list in all_item_lists:
            if item_list:
                l3_data_from_items = process_menu_items_level_2_only(item_list)
                all_l3_data_for_menu.extend(l3_data_from_items)
    
    # Final processing step to flatten and format ItemAddons
    final_item_addons_payloads = process_item_addons_level_3b_only_standalone(all_l3_data_for_menu)
    logger.info(f"Total Level 3b ItemAddons payloads collected: {len(final_item_addons_payloads)}")
    
    # Iterate and call API for each L3b record
    for i, item_addon_record in enumerate(final_item_addons_payloads):
        logger.info(f"Processing L3B ItemAddon {i+1}/{len(final_item_addons_payloads)}")
        
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
            "ParentId": str(ParentComponentId),
            "recordList": [
                {
                    "recordJsonString": record_data,
                    "ParentRecordId": parent_record_id,
                    "ParentComponentId": ParentComponentId,
                    "MainParentComponentid": MainParentComponentid
                }
            ]
        }
        
        responseData = None
        print(f"[API] Calling CreateComponentRecord for Level 3b (Addon) {i+1}/{len(final_item_addons_payloads)}...", flush=True)
        logger.info(f"Calling CreateComponentRecord for Level 3b addon record, Parent Record ID: {parent_record_id}")
        api_result = CreateComponentRecord(destination_url, headers, fixed_payload)
        
        if isinstance(api_result, dict):
            responseData = api_result
            status_code = responseData.get('ErrorCode', 'N/A')
            success_status = responseData.get('Success', 'N/A')
            logger.info(f"L3B API Response Status: {status_code} | Success: {success_status}")
            print(f"[SUCCESS] Level 3b Addon API call completed. Status: {status_code}, Success: {success_status}", flush=True)
        else:
            responseData = {"Note": "API call failed (returned non-dict/None).", "status_code": "ERROR_NON_DICT", "original_response": str(api_result)}
            logger.error("L3B API call failed to return a valid dictionary response.")
            print(f"[ERROR] L3B API call failed. Response: {api_result}", flush=True)
        
        if responseData:
            processed_output_level_3b.append(responseData)
    
    # Save API Responses
    final_api_output_file_path = os.path.join(get_job_folder(job_id), "final-api-response-L3B.json")
    try:
        with open(final_api_output_file_path, "w", encoding='utf-8') as f:
            json.dump(processed_output_level_3b, f, indent=4)
        logger.info(f"Level 3b API responses saved: {len(processed_output_level_3b)} records")
    except Exception as e:
        logger.error(f"Error saving L3B responses: {e}")
        return False
    
    logger.info("All menu levels processing completed successfully")
    return True


def run_html_menu_step(job_id: str, step_config: Dict, workflow_context: Dict) -> Dict[str, Any]:
    """
    Step 4: Dine Menu Migration
    Migrates menu data from source to destination site
    Note: Uses destination site URL and token as menu data is moved to destination
    """
    print("\n" + "="*80, flush=True)
    print(f"[MENU STEP] run_html_menu_step CALLED", flush=True)
    print("="*80, flush=True)
    logger.info(f"Starting Dine Menu migration for job {job_id}")
    
    job_config = workflow_context.get("job_config", {})
    print(f"[DEBUG] job_config keys: {list(job_config.keys())}", flush=True)
    print(f"[DEBUG] htmlMenu enabled: {job_config.get('htmlMenu', False)}", flush=True)
    
    # Check if Dine Menu is enabled
    if not job_config.get("htmlMenu", False):
        print("[WARNING] Dine Menu is not enabled in job_config. Skipping migration.", flush=True)
        return {
            "menu_migration_enabled": False,
            "message": "Dine Menu migration skipped (not enabled)"
        }
    
    # Get source and destination info
    source_url = job_config.get("sourceUrl", "").strip()
    destination_url = job_config.get("destinationUrl", "").strip()
    destination_site_id = job_config.get("destinationSiteId", "").strip()
    
    print(f"[DEBUG] Source URL: {source_url}", flush=True)
    print(f"[DEBUG] Destination URL: {destination_url}", flush=True)
    print(f"[DEBUG] Destination Site ID: {destination_site_id}", flush=True)
    
    # Get destination token from site_setup step or job_config
    site_setup = workflow_context.get("site_setup", {})
    print(f"[DEBUG] site_setup keys: {list(site_setup.keys()) if site_setup else 'None'}", flush=True)
    destination_token = site_setup.get("destination_cms_token") or job_config.get("destination_cms_token")
    print(f"[DEBUG] Destination token exists: {bool(destination_token)}", flush=True)
    
    # If token is in job_config but not in site_setup, create site_setup entry for consistency
    if not site_setup and destination_token:
        site_setup = {"destination_cms_token": destination_token, "site_created": True}
        workflow_context["site_setup"] = site_setup
        print(f"[DEBUG] Created site_setup entry from job_config", flush=True)
    
    if not destination_token:
        error_msg = "Destination CMS token is required for menu migration"
        print(f"[ERROR] {error_msg}", flush=True)
        raise ValueError(error_msg)
    
    if not all([source_url, destination_url, destination_site_id]):
        error_msg = "Source URL, Destination URL, and Destination Site ID are required"
        print(f"[ERROR] {error_msg}", flush=True)
        raise ValueError(error_msg)
    
    ensure_job_folders(job_id)
    
    print("\n" + "="*80, flush=True)
    print(f"[DINE MENU] STARTING MENU MIGRATION PROCESS", flush=True)
    print("="*80, flush=True)
    print(f"Job ID: {job_id}", flush=True)
    print(f"Source URL: {source_url}", flush=True)
    print(f"Destination URL: {destination_url}", flush=True)
    print(f"Destination Site ID: {destination_site_id}", flush=True)
    print("="*80, flush=True)
    
    try:
        # Step 1: Download menu data from source
        print("\n[STEP 1] Downloading menu data from source...", flush=True)
        logger.info("Step 1: Downloading menu data from source...")
        if not download_and_save_menu_data(job_id, source_url):
            raise Exception("Failed to download menu data from source")
        print("[OK] Step 1 completed: Menu data downloaded", flush=True)
        
        # Step 2: Map payload using field mapper
        print("\n[STEP 2] Mapping menu payload (saving mapper files)...", flush=True)
        logger.info("Step 2: Mapping menu payload...")
        if not payload_mapper(job_id):
            raise Exception("Failed to map menu payload")
        print("[OK] Step 2 completed: Payload mapped and saved", flush=True)
        
        # Step 3: Create final payload using template
        print("\n[STEP 3] Creating final menu payload...", flush=True)
        logger.info("Step 3: Creating final menu payload...")
        if not payload_creator(job_id):
            raise Exception("Failed to create final menu payload")
        print("[OK] Step 3 completed: Final payload created", flush=True)
        
        # Step 4: Preprocess (export component, create map)
        print("\n[STEP 4] Preprocessing menu data (exporting component)...", flush=True)
        logger.info("Step 4: Preprocessing menu data (exporting component)...")
        mi_block_folder = preprocess_menu_data(job_id, destination_url, destination_site_id, destination_token)
        if not mi_block_folder:
            raise Exception("Failed to preprocess menu data")
        print("[OK] Step 4 completed: Component exported and map created", flush=True)
        
        # Step 5: Process menu levels and create records (THIS IS WHERE APIs ARE CALLED)
        print("\n" + "="*80, flush=True)
        print(f"[STEP 5] PROCESSING MENU LEVELS AND CALLING APIs", flush=True)
        print("="*80, flush=True)
        print("[IMPORTANT] This step will call APIs to create menu records in destination site", flush=True)
        logger.info("Step 5: Processing menu levels...")
        if not process_menu_levels(job_id, destination_url, destination_site_id, destination_token):
            raise Exception("Failed to process menu levels")
        print("\n[OK] Step 5 completed: All menu levels processed and APIs called", flush=True)
        
        return {
            "menu_migration_enabled": True,
            "menu_migrated": True,
            "mi_block_folder": mi_block_folder,
            "message": "Dine Menu migration completed successfully"
        }
        
    except Exception as e:
        logger.error(f"Menu migration failed: {e}", exc_info=True)
        raise Exception(f"Menu migration failed: {str(e)}")

