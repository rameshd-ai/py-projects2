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
import html
import re
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


def get_menu_component_names() -> Dict[str, str]:
    """Load component names from payload template (single source of truth)."""
    template = load_json_data(MENU_PAYLOAD_TEMPLATE)
    return {
        "level_0": (template.get("level 0", {}).get("componentName") or "Menu-new"),
        "level_1": (template.get("level 1", {}).get("componentName") or "Menu-new Section"),
        "level_2": (template.get("level 2", {}).get("componentName") or "Menu-new Section Item"),
    }


def load_json_data(file_path: str) -> Dict[str, Any]:
    """Safely load JSON data from file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load JSON from {file_path}: {e}")
        return {}


def clean_text(text: Any) -> Any:
    """
    Clean text by removing HTML entities, special characters, and normalizing whitespace.
    Handles strings, returns other types as-is.
    """
    if not isinstance(text, str):
        return text
    
    if not text:
        return text
    
    # Decode HTML entities (e.g., &nbsp; -> space, &amp; -> &)
    cleaned = html.unescape(text)
    
    # Remove HTML tags if any remain
    cleaned = re.sub(r'<[^>]+>', '', cleaned)
    
    # Replace semicolons with space, but KEEP pipes (|) as they are used as separators in item names
    cleaned = re.sub(r';+', ' ', cleaned)
    
    # Replace multiple spaces/newlines/tabs with single space
    cleaned = re.sub(r'[\s]+', ' ', cleaned)
    
    # Strip leading/trailing whitespace
    cleaned = cleaned.strip()
    
    return cleaned


def download_and_save_menu_data(job_id: str, source_url: str) -> bool:
    """
    Downloads menu data from the source URL and saves it to job folder
    """
    logger.info(f"Starting menu data download for job {job_id} from {source_url}")
    
    ensure_job_folders(job_id)
    output_dir = get_job_folder(job_id)
    output_file_path = os.path.join(output_dir, "menu_api_response_input.json")
    
    response_data = menu_download_api(source_url)
    
    # Log the response data details
    logger.info(f"API Response Data Type: {type(response_data)}")
    logger.info(f"API Response Data: {response_data}")
    print(f"[DEBUG] API Response Data Type: {type(response_data)}")
    print(f"[DEBUG] API Response Data: {response_data}")
    
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
        logger.error("No data received from menu API - response_data is None or empty")
        print("[ERROR] No data received from menu API - response_data is None or empty")
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
    
    # Fields that should NOT be cleaned (numeric/status fields)
    numeric_fields = {'displayorder', 'status', 'MenuOrder', 'SectionOrder', 'ItemOrder', 'MenuStatusId', 'SectionStatus', 'ItemStatus'}
    
    # Image fields that should be converted from null to [] (empty array)
    # Only actual image fields, NOT alt-text fields
    def is_image_field(field_name: str) -> bool:
        """Check if a field is an image field (excludes alt-text fields)"""
        if not field_name:
            return False
        field_lower = field_name.lower()
        # Must contain "image" but NOT "alt-text" or "alttext"
        if 'image' in field_lower:
            # Exclude alt-text fields
            if 'alt-text' in field_lower or 'alttext' in field_lower or 'alt_text' in field_lower:
                return False
            return True
        return False
    
    def convert_null_to_empty_array(value: Any, field_name: str) -> Any:
        """Convert null to [] for image fields (not alt-text), otherwise return value as-is"""
        if is_image_field(field_name) and value is None:
            return []
        return value
    
    # Helper: get value for level_2 dest_key from source_item (handles flat addon/price loop fields)
    def get_level2_value(source_item: Dict, dest_key: str, src_key: str):
        # item-price-option-N or item-price-option-N-description: from ItemPrices[N-1]
        m = re.match(r"item-price-option-(\d+)(-description)?$", dest_key)
        if m:
            idx = int(m.group(1))
            prices = source_item.get("ItemPrices", [])
            if idx <= len(prices):
                p = prices[idx - 1]
                if m.group(2):
                    return p.get("PriceDescription") or p.get(src_key)
                return p.get("Price") or p.get(src_key)
            return ""
        # item-add-on-N-name, item-add-on-N-price, item-add-on-N-price-notes: from ItemAddons[N-1]
        m = re.match(r"item-add-on-(\d+)-(name|price|price-notes)$", dest_key)
        if m:
            idx = int(m.group(1))
            sub = m.group(2)
            addons = source_item.get("ItemAddons", [])
            if idx <= len(addons):
                a = addons[idx - 1]
                if sub == "name":
                    return a.get("Name") or a.get(src_key)
                if sub == "price":
                    return a.get("Price") or a.get(src_key)
                return a.get("PriceNotes", "") or ""
            return ""
        # Direct field from source item
        return source_item.get(src_key)

    # Iterate through each Menu in the source data
    for source_menu in source_data:
        mapped_menu = {}
        # Map level 0 fields (mapper key: level_0)
        for dest_key, src_key in mapper.get("level_0", {}).items():
            value = source_menu.get(src_key)
            value = convert_null_to_empty_array(value, dest_key)
            if dest_key in numeric_fields or src_key in numeric_fields:
                mapped_menu[dest_key] = value
            else:
                mapped_menu[dest_key] = clean_text(value)
        
        mapped_menu["MenuSections"] = []
        
        source_sections = source_menu.get("Sections", [])
        for source_section in source_sections:
            mapped_section = {}
            # Map level 1 fields (mapper key: level_1)
            for dest_key, src_key in mapper.get("level_1", {}).items():
                value = source_section.get(src_key)
                value = convert_null_to_empty_array(value, dest_key)
                if dest_key in numeric_fields or src_key in numeric_fields:
                    mapped_section[dest_key] = value
                else:
                    mapped_section[dest_key] = clean_text(value)
            
            mapped_section["MenuItems"] = []
            source_items = source_section.get("Items", [])
            for source_item in source_items:
                mapped_item = {}
                # Map level 2 fields (mapper key: level_2); addons/prices flattened into numbered fields
                for dest_key, src_key in mapper.get("level_2", {}).items():
                    value = get_level2_value(source_item, dest_key, src_key)
                    value = convert_null_to_empty_array(value, dest_key)
                    if dest_key in numeric_fields or (isinstance(src_key, str) and src_key in numeric_fields):
                        mapped_item[dest_key] = value
                    else:
                        mapped_item[dest_key] = clean_text(value) if value is not None else ""
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


def apply_cascading_status(final_payload: List[Dict]) -> List[Dict]:
    """
    Apply cascading status logic:
    - If a Menu (Level 0) is inactive, all its Sections and Items become inactive
    - If a Section (Level 1) is inactive, all its Items become inactive
    
    Status values: 1 = active, 0 = inactive, 2 = inactive (both map to 0)
    """
    logger.info("Applying cascading status logic")
    cascaded_count = 0
    
    for menu in final_payload:
        menu_status = menu.get('recordJsonString', {}).get('status', 1)
        menu_is_inactive = (menu_status == 0 or menu_status == 2)
        
        if menu_is_inactive:
            logger.info(f"Menu '{menu.get('recordJsonString', {}).get('menu-title', 'Unknown')}' is inactive - cascading to all children")
        
        for section in menu.get('MenuSections', []):
            section_status = section.get('recordJsonString', {}).get('status', 1)
            section_is_inactive = (section_status == 0 or section_status == 2)
            
            # If parent menu is inactive, make this section inactive too
            if menu_is_inactive and not section_is_inactive:
                section['recordJsonString']['status'] = 0
                section_is_inactive = True
                cascaded_count += 1
                logger.debug(f"  Section '{section.get('recordJsonString', {}).get('section-name', 'Unknown')}' set to inactive (parent menu inactive)")
            
            # Now check items
            for item in section.get('MenuItems', []):
                item_status = item.get('recordJsonString', {}).get('status', 1)
                item_is_inactive = (item_status == 0 or item_status == 2)
                
                # If parent menu OR parent section is inactive, make this item inactive
                if (menu_is_inactive or section_is_inactive) and not item_is_inactive:
                    item['recordJsonString']['status'] = 0
                    cascaded_count += 1
                    logger.debug(f"    Item '{item.get('recordJsonString', {}).get('item-name', 'Unknown')}' set to inactive (parent inactive)")
    
    if cascaded_count > 0:
        logger.info(f"Cascaded inactive status to {cascaded_count} child record(s)")
        print(f"[STATUS CASCADE] Set {cascaded_count} child record(s) to inactive based on parent status", flush=True)
    else:
        logger.info("No status cascading needed - all active records have active parents")
    
    return final_payload


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
    
    # Extract component names and templates (only level 0, 1, 2; addons/prices are flat in level_2)
    menu_component_name = template.get("level 0", {}).get("componentName")
    section_component_name = template.get("level 1", {}).get("componentName")
    item_component_name = template.get("level 2", {}).get("componentName")
    
    menu_template = template.get("level 0", {}).get("recordList", [{}])[0].get("recordJsonString", {})
    section_template = template.get("level 1", {}).get("recordList", [{}])[0].get("recordJsonString", {})
    item_template = template.get("level 2", {}).get("recordList", [{}])[0].get("recordJsonString", {})
    
    final_payload = []
    
    # Helper function to convert null to [] for image fields (not alt-text)
    def is_image_field(field_name: str) -> bool:
        """Check if a field is an image field (excludes alt-text fields)"""
        if not field_name:
            return False
        field_lower = field_name.lower()
        # Must contain "image" but NOT "alt-text" or "alttext"
        if 'image' in field_lower:
            # Exclude alt-text fields
            if 'alt-text' in field_lower or 'alttext' in field_lower or 'alt_text' in field_lower:
                return False
            return True
        return False
    
    def convert_null_to_empty_array(value: Any, field_name: str) -> Any:
        """Convert null to [] for image fields (not alt-text), otherwise return value as-is"""
        if is_image_field(field_name) and value is None:
            return []
        return value
    
    # Process each menu
    for menu_data in mapped_data:
        menu_record_json = {}
        for key in menu_template:
            value = menu_data.get(key, None)
            value = convert_null_to_empty_array(value, key)
            menu_record_json[key] = value
        
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
                value = section_data.get(key, None)
                value = convert_null_to_empty_array(value, key)
                section_record_json[key] = value
            
            section_output = {
                "recordJsonString": section_record_json,
                "ParentRecordId": "",
                "ParentComponentId": "",
                "MainParentComponentid": "",
                "componentName": section_component_name,
                "status": "",
                "MenuItems": []
            }
            
            # Process items (level_2 is flat: addons/prices are item-add-on-1-name, item-price-option-1, etc.)
            for item_data in section_data.get("MenuItems", []):
                item_record_json = {}
                for key in item_template:
                    value = item_data.get(key, None)
                    value = convert_null_to_empty_array(value, key)
                    item_record_json[key] = value
                
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
    
    # Apply cascading status logic (inactive parents cascade to children)
    final_payload = apply_cascading_status(final_payload)
    
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
    
    # Get component info (component name from payload template)
    component_names = get_menu_component_names()
    root_component_name = component_names["level_0"]
    responseData = getComponentInfo(root_component_name, destination_url, headers)
    
    if not responseData or not isinstance(responseData, list) or len(responseData) == 0:
        logger.error("Invalid response from getComponentInfo")
        return None
    
    component_id = responseData[0].get('Id')
    if not component_id:
        logger.error("Component ID not found in API response")
        return None
    
    logger.info(f"Found {root_component_name} component ID: {component_id}")
    
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
                
                # Update display orders - reset to start from 1 while preserving original order
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
    """Recursively reset display orders starting from 1, preserving original order"""
    if isinstance(data, list):
        # Sort by original displayorder to maintain the correct sequence
        # Items without displayorder will be sorted to the end
        def get_display_order(item):
            if isinstance(item, dict):
                record_data = item.get('recordJsonString', {})
                if isinstance(record_data, dict):
                    display_order = record_data.get('displayorder')
                    if display_order is not None:
                        try:
                            return int(display_order)
                        except (ValueError, TypeError):
                            pass
            return float('inf')  # Put items without displayorder at the end
        
        # Sort by original displayorder
        sorted_data = sorted(data, key=get_display_order)
        
        # Now reset display orders sequentially starting from 1
        for idx, item in enumerate(sorted_data, 1):
            if isinstance(item, dict):
                record_data = item.get('recordJsonString', {})
                if isinstance(record_data, dict):
                    record_data['displayorder'] = idx
                
                # Recurse into MenuSections
                if 'MenuSections' in item:
                    item['MenuSections'] = reset_display_orders(item['MenuSections'])
                
                # Recurse into MenuItems (level_2 is flat; no nested ItemPrices/ItemAddons)
                if 'MenuItems' in item:
                    item['MenuItems'] = reset_display_orders(item['MenuItems'])
        
        return sorted_data
    
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
    
    # Extract component IDs from map (names from payload template)
    component_names = get_menu_component_names()
    menu_info = component_map_data.get(component_names["level_0"], {})
    l0_component_id = menu_info.get("ComponentId")
    l0_main_parent_id = menu_info.get("MainParentComponentid")
    l1_component_id = component_map_data.get(component_names["level_1"], {}).get("ComponentId")
    l2_component_id = component_map_data.get(component_names["level_2"], {}).get("ComponentId")
    
    if not all([l0_component_id, l0_main_parent_id, l1_component_id, l2_component_id]):
        error_msg = "Missing required component IDs in component map"
        print(f"\n[ERROR] {error_msg}", flush=True)
        _names = get_menu_component_names()
        print(f"[DEBUG] Component IDs found:", flush=True)
        print(f"  L0 ({_names['level_0']}): {l0_component_id}", flush=True)
        print(f"  L0 Main Parent: {l0_main_parent_id}", flush=True)
        print(f"  L1 ({_names['level_1']}): {l1_component_id}", flush=True)
        print(f"  L2 ({_names['level_2']}): {l2_component_id}", flush=True)
        logger.error(error_msg)
        return False
    
    print(f"\n[OK] All component IDs found. Starting API calls (L0, L1, L2 only)...", flush=True)
    print(f"  L0 Component ID: {l0_component_id}", flush=True)
    print(f"  L1 Component ID: {l1_component_id}", flush=True)
    print(f"  L2 Component ID: {l2_component_id}", flush=True)
    
    # ========== LEVEL 0: Process Menus ==========
    _l0_name = get_menu_component_names()["level_0"]
    print("\n" + "="*80, flush=True)
    print(f"[LEVEL 0] PROCESSING {_l0_name.upper()} RECORDS (BATCH MODE)", flush=True)
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
    _l1_name = get_menu_component_names()["level_1"]
    print("\n" + "="*80, flush=True)
    print(f"[LEVEL 1] PROCESSING {_l1_name.upper()} RECORDS (BATCH MODE)", flush=True)
    print("="*80, flush=True)
    logger.info("Processing Level 1: %s records...", _l1_name)
    
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
                    # Update both the section_record in l1_section_mapping AND the corresponding section in final_payload
                    section_record['NewRecordId_L1'] = created_record_id
                    if 'MenuItems' in section_record and section_record['MenuItems'] is not None:
                        for item in section_record['MenuItems']:
                            item['ParentRecordId'] = created_record_id
                            item['ParentComponentId'] = str(l2_component_id)
                            item['MainParentComponentid'] = l0_main_parent_id
                    
                    # Also update the corresponding section in final_payload to ensure changes persist
                    # Find the section in final_payload by matching the section name
                    section_name_in_mapping = section_record.get('recordJsonString', {}).get('section-name', '')
                    for menu_record in final_payload:
                        for section in menu_record.get('MenuSections', []):
                            section_name_in_final = section.get('recordJsonString', {}).get('section-name', '')
                            if section_name_in_final == section_name_in_mapping:
                                section['NewRecordId_L1'] = created_record_id
                                if 'MenuItems' in section and section['MenuItems'] is not None:
                                    for item in section['MenuItems']:
                                        item['ParentRecordId'] = created_record_id
                                        item['ParentComponentId'] = str(l2_component_id)
                                        item['MainParentComponentid'] = l0_main_parent_id
                                break
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
    _l2_name = get_menu_component_names()["level_2"]
    print("\n" + "="*80, flush=True)
    print(f"[LEVEL 2] PROCESSING {_l2_name.upper()} RECORDS (BATCH MODE)", flush=True)
    print("="*80, flush=True)
    logger.info("Processing Level 2: %s records...", _l2_name)
    
    # Collect all Level 2 records first
    l2_records = []
    l2_item_mapping = []  # Track which item_record each payload belongs to
    
    for menu_record in final_payload:
        _, menu_sections_list = process_menu_level_0_only(menu_record)
        all_item_lists = process_menu_sections_level_1_only(menu_sections_list)
        
        skipped_items = []
        for item_list in all_item_lists:
            for item_record in item_list:
                parent_record_id = item_record.get("ParentRecordId", 0)
                # Check for both 0 and empty string (empty string is falsy but not equal to 0)
                if not parent_record_id or parent_record_id == 0 or parent_record_id == "":
                    item_name = item_record.get('recordJsonString', {}).get('item-name', 'Unknown')
                    skipped_items.append(item_name)
                    logger.warning(f"Skipping item '{item_name}' - ParentRecordId is {parent_record_id} (parent section may not have been created)")
                    print(f"[WARNING] Skipping item '{item_name}' - ParentRecordId is '{parent_record_id}'. Parent section may have failed to create.", flush=True)
                    continue
                
                # Ensure ParentRecordId is an integer
                try:
                    parent_record_id = int(parent_record_id)
                except (ValueError, TypeError):
                    item_name = item_record.get('recordJsonString', {}).get('item-name', 'Unknown')
                    skipped_items.append(item_name)
                    logger.warning(f"Skipping item '{item_name}' - ParentRecordId '{parent_record_id}' cannot be converted to integer")
                    print(f"[WARNING] Skipping item '{item_name}' - ParentRecordId '{parent_record_id}' is not a valid integer.", flush=True)
                    continue
                
                item_json_string_ref = item_record.get('recordJsonString', {})
                # level_2 is flat (no nested ItemPrices/ItemAddons)
                payload_json_string = item_json_string_ref.copy()
                
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
                l2_item_mapping.append(item_record)
    
    # Report skipped items
    if skipped_items:
        print(f"\n[WARNING] {len(skipped_items)} item(s) were skipped due to missing parent section:", flush=True)
        for item_name in skipped_items:
            print(f"  - {item_name}", flush=True)
        logger.warning(f"Skipped {len(skipped_items)} items due to missing ParentRecordId: {skipped_items}")
    
    # Send all Level 2 records in batches
    if l2_records:
        print(f"[BATCH] Sending {len(l2_records)} Level 2 records in batches...", flush=True)
        api_payload = {f"{l2_component_id}_L2": l2_records}
        success, responseData = addUpdateRecordsToCMS(destination_url, headers, api_payload, batch_size=10)
        
        if success:
            # Map responses back to item records (responseData is now a list indexed by order)
            for idx, item_record in enumerate(l2_item_mapping):
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
                    item_record['NewRecordId_L2'] = created_record_id
                else:
                    logger.warning(f"L2 Item {idx+1} API call succeeded but couldn't extract record ID. Response: {created_record_id}, Type: {type(created_record_id)}")
                    print(f"[WARNING] L2 Item {idx+1} - Invalid record ID: {created_record_id}", flush=True)
        else:
            # Check if we got partial success (some records succeeded)
            if isinstance(responseData, list):
                success_count = sum(1 for r in responseData if r is not None and isinstance(r, int) and r > 0)
                if success_count > 0:
                    logger.warning(f"L2 batch API call partially failed. {success_count}/{len(l2_item_mapping)} records succeeded")
                    print(f"[WARNING] L2 batch API call partially failed. {success_count}/{len(l2_item_mapping)} records succeeded. Continuing...", flush=True)
                    # Continue processing with successful records
                else:
                    logger.error(f"L2 batch API call failed completely. Response: {responseData}")
                    print(f"[ERROR] L2 batch API call failed completely. Response: {responseData}", flush=True)
                    return False
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
    
    logger.info("All menu levels processing completed successfully (L0, L1, L2 only; addons/prices are flat in level_2)")
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

