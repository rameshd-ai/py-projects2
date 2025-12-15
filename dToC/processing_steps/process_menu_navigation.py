import logging
import json
import os
import re
import html
import time
import zipfile
import sys
from typing import Dict, Any, Union, Optional, List

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import required functions from other modules
from apis import GetAllVComponents, export_mi_block_component

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, '..', 'uploads')
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Global custom properties for level 1 records
# Set these to apply custom properties, or set to None/empty dict to skip
LEVEL_1_CUSTOM_PROPERTIES = {
    "enable-dropdown[]": ["Yes"],
    "enable-menu-item-in-left[]": ["Yes"],
    "enable-menu-item-in-right[]": ["Yes"]
}

def get_config_filepath(file_prefix: str) -> str:
    base_prefix = os.path.basename(file_prefix)
    config_filename = f"{base_prefix}_config.json"
    return os.path.join(UPLOAD_FOLDER, config_filename)

def load_settings(file_prefix: str) -> Dict[str, Any] | None:
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


def fix_parent_record_ids_for_sub_records(file_prefix: str) -> bool:
    """
    Fixes parentRecordId for level 2+ records by mapping them to their parent's recordId.
    This must be called before calling the update API for sub-records.
    
    Args:
        file_prefix: The file prefix for the payload file
        
    Returns:
        bool: True if successful, False otherwise
    """
    matched_records_file = os.path.join(UPLOAD_FOLDER, f"{file_prefix}_save_miblock_records_payload.json")
    
    if not os.path.exists(matched_records_file):
        logging.warning(f"Payload file not found: {matched_records_file}")
        return False
    
    try:
        # Read the payload file
        with open(matched_records_file, 'r', encoding='utf-8') as f:
            matched_data = json.load(f)
        
        records = matched_data.get("records", [])
        if not records:
            logging.warning("No records found in payload file")
            return False
        
        # Step 1: Build parent name to recordId map for level 1 records
        parent_name_to_id_map = {}
        level_1_count = 0
        level_2_plus_count = 0
        
        for record in records:
            rec_level = record.get("matched_page_level", 0)
            page_name = record.get("matched_page_name", "")
            record_id = record.get("recordId", 0)
            
            if rec_level == 1:
                level_1_count += 1
                if page_name and record_id:
                    parent_name_to_id_map[page_name] = record_id
                    logging.info(f"✅ Mapped parent '{page_name}' → recordId {record_id}")
                else:
                    logging.warning(f"⚠️ Level 1 record missing page_name or recordId: page_name='{page_name}', recordId={record_id}")
            elif rec_level >= 2:
                level_2_plus_count += 1
        
        logging.info(f"Found {level_1_count} level 1 records and {level_2_plus_count} level 2+ records")
        logging.info(f"Created parent name-to-ID map with {len(parent_name_to_id_map)} level 1 parents: {list(parent_name_to_id_map.keys())}")
        
        if not parent_name_to_id_map:
            logging.error("❌ No level 1 parents found in payload - cannot fix parentRecordId for sub-records")
            return False
        
        # Step 2: Fix parentRecordId for level 2+ records
        parent_id_updated_count = 0
        for record in records:
            rec_level = record.get("matched_page_level", 0)
            
            if rec_level >= 2:
                page_name = record.get("matched_page_name", "")
                parent_page_name = record.get("parent_page_name", "")
                current_parent_id = record.get("parentRecordId", 0)
                
                logging.info(f"Processing level {rec_level} record: '{page_name}' (parent_page_name='{parent_page_name}', current_parentRecordId={current_parent_id})")
                
                if not parent_page_name:
                    logging.warning(f"⚠️ Level {rec_level} record '{page_name}' has no parent_page_name - skipping")
                    continue
                
                if parent_page_name in parent_name_to_id_map:
                    parent_record_id = parent_name_to_id_map[parent_page_name]
                    
                    if current_parent_id != parent_record_id:
                        record["parentRecordId"] = parent_record_id
                        parent_id_updated_count += 1
                        logging.info(f"✅ Fixed parentRecordId for '{page_name}' (level {rec_level}): {current_parent_id} → {parent_record_id} (parent: '{parent_page_name}')")
                    else:
                        logging.info(f"✓ ParentRecordId already correct for '{page_name}': {parent_record_id}")
                else:
                    logging.error(f"❌ Parent '{parent_page_name}' not found in map for '{page_name}'!")
                    logging.error(f"   Available parents in map: {list(parent_name_to_id_map.keys())}")
                    logging.error(f"   Record details: matched_page_name='{page_name}', parent_page_name='{parent_page_name}', recordId={record.get('recordId')}")
        
        # Step 3: Save updated payload file
        logging.info(f"Total updates needed: {parent_id_updated_count} out of {level_2_plus_count} level 2+ records")
        
        if parent_id_updated_count > 0:
            with open(matched_records_file, 'w', encoding='utf-8') as f:
                json.dump(matched_data, f, indent=4, ensure_ascii=False)
            logging.info(f"✅ Fixed {parent_id_updated_count} parentRecordId values for level 2+ records and saved to file")
            logging.info(f"📁 File saved: {matched_records_file}")
            
            
            return True
        else:
            logging.warning("⚠️ No parentRecordId values were updated - all may already be correct or there's a mapping issue")
            # Still exit for debugging
            logging.info("🛑 DEBUG: Exiting to check why no updates were made.")
           
            return True
            
    except Exception as e:
        logging.error(f"Error fixing parent record IDs: {e}")
        logging.exception("Full traceback:")
        return False


def run_menu_navigation_step(
    input_filepath: str,
    step_config: Dict[str, Any],
    previous_step_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Main entry point for menu navigation processing step.
    """
    file_prefix = previous_step_data.get('file_prefix')
    
    if not file_prefix:
        raise ValueError("Menu Navigation failed: Missing file prefix")
    
    logging.info("========================================================")
    logging.info("START: Menu Navigation Processing Step")
    logging.info("========================================================")
    
    # Load settings
    settings = load_settings(file_prefix)
    if not settings:
        raise RuntimeError("Could not load configuration for menu navigation")
    
    api_base_url = settings.get("target_site_url")
    raw_token = settings.get("cms_login_token")
    site_id = settings.get("site_id")
    
    if not api_base_url or not raw_token or site_id is None:
        raise ValueError("Missing required configuration for menu navigation")
    
    api_headers = {
        'Content-Type': 'application/json',
        'ms_cms_clientapp': 'ProgrammingApp',
        'Authorization': f'Bearer {raw_token}',
    }
    
    logging.info(f"Configuration loaded. API Base URL: {api_base_url}, Site ID: {site_id}")
    
    try:
        # 1. Read _util_pages.json and extract menu component name
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
                content_source = page.get('content_blocks', '') or page.get('description', '')
                
                decoded_content = html.unescape(content_source)
                decoded_content = html.unescape(decoded_content)
                decoded_content = html.unescape(decoded_content)
                
                main_menu_json_pattern = r'["\']?mainMenu["\']?\s*:\s*\[(.*?)\]'
                json_match = re.search(main_menu_json_pattern, decoded_content, re.IGNORECASE | re.DOTALL)
                
                if json_match:
                    try:
                        array_content = json_match.group(1)
                        array_content = re.sub(r'<[^>]+>', '', array_content)
                        array_content = re.sub(r'<br\s*/?>', '', array_content, flags=re.IGNORECASE)
                        array_content = re.sub(r'\s+', ' ', array_content)
                        
                        json_obj_str = '{"mainMenu": [' + array_content + ']}'
                        try:
                            parsed_json = json.loads(json_obj_str)
                            if 'mainMenu' in parsed_json and isinstance(parsed_json['mainMenu'], list) and len(parsed_json['mainMenu']) > 0:
                                menu_item = parsed_json['mainMenu'][0]
                                menu_component_name = menu_item.get('componentName', '').strip()
                                menu_level = menu_item.get('menuLevel')
                                
                                if menu_component_name:
                                    logging.info(f"Found menu component: {menu_component_name}, menuLevel: {menu_level}")
                                    break
                        except json.JSONDecodeError:
                            component_name_match = re.search(r'["\']componentName["\']\s*:\s*["\']([^"\']+)["\']', array_content, re.IGNORECASE)
                            if component_name_match:
                                menu_component_name = component_name_match.group(1).strip()
                            
                            menu_level_match = re.search(r'["\']menuLevel["\']\s*:\s*(\d+)', array_content, re.IGNORECASE)
                            if menu_level_match:
                                try:
                                    menu_level = int(menu_level_match.group(1))
                                except ValueError:
                                    pass
                            
                            if menu_component_name:
                                break
                    except Exception as e:
                        logging.warning(f"Error parsing JSON: {e}")
                
                main_menu_pattern = r'Main\s*Menu:\s*(.+)$'
                match = re.search(main_menu_pattern, decoded_content, re.IGNORECASE | re.DOTALL)
                if match:
                    menu_component_name = match.group(1).strip()
                    menu_component_name = re.sub(r'[\n\r]+', ' ', menu_component_name)
                    menu_component_name = re.sub(r'\s+', ' ', menu_component_name).strip()
                    break
        
        if not menu_component_name:
            logging.warning("Menu component name not found. Using default.")
            menu_component_name = "Main Menu"
        
        # 2. Read _simplified.json
        simplified_file = os.path.join(UPLOAD_FOLDER, f"{file_prefix}_simplified.json")
        
        if not os.path.exists(simplified_file):
            raise FileNotFoundError(f"Could not find {simplified_file}")
        
        with open(simplified_file, 'r', encoding='utf-8') as f:
            simplified_data = json.load(f)
        
        starting_level = 0 if menu_level == 0 else 1
        
        def extract_page_tree(page_node, level=None):
            if level is None:
                level = starting_level
            
            page_name = page_node.get("page_name", "")
            meta_info = page_node.get("meta_info", {})
            
            if not meta_info or meta_info == {}:
                return None
            
            page_tree = {
                "page_name": page_name,
                "level": level
            }
            
            sub_pages = page_node.get("sub_pages", [])
            if sub_pages:
                processed_sub_pages = [extract_page_tree(sub_page, level + 1) for sub_page in sub_pages]
                valid_sub_pages = [sp for sp in processed_sub_pages if sp is not None]
                
                if valid_sub_pages:
                    page_tree["sub_pages"] = valid_sub_pages
            
            return page_tree
        
        pages_tree = []
        for page in simplified_data.get('pages', []):
            page_tree = extract_page_tree(page)
            if page_tree is not None:
                pages_tree.append(page_tree)
        
        logging.info(f"Extracted {len(pages_tree)} main pages")
        
        # 3. Fetch components and download menu component
        all_components_response = GetAllVComponents(api_base_url, api_headers, page_size=1000)
        
        if all_components_response and isinstance(all_components_response, list):
            components_output_filename = f"{file_prefix}_all_components_response.json"
            components_output_filepath = os.path.join(UPLOAD_FOLDER, components_output_filename)
            
            with open(components_output_filepath, 'w', encoding='utf-8') as f:
                json.dump({"total_components": len(all_components_response), "components": all_components_response}, f, indent=4, ensure_ascii=False)
            
            logging.info(f"✅ Components saved: {len(all_components_response)}")
            
            if menu_component_name:
                def normalize_component_name(name: str) -> str:
                    if not name:
                        return ""
                    return re.sub(r'[\s\-_]+', '', name).lower()
                
                normalized_search_name = normalize_component_name(menu_component_name)
                matching_component = None
                
                for comp in all_components_response:
                    comp_name = comp.get('name', '')
                    comp_component_name = comp.get('component', {}).get('componentName', '')
                    
                    if (comp_name and normalize_component_name(comp_name) == normalized_search_name) or \
                       (comp_component_name and normalize_component_name(comp_component_name) == normalized_search_name):
                        matching_component = comp
                        logging.info(f"✅ Found matching component: '{comp_name}'")
                        break
                
                if matching_component:
                    component_id = matching_component.get('component', {}).get('componentId') or \
                                  matching_component.get('miBlockId') or \
                                  matching_component.get('blockId')
                    
                    if component_id:
                        downloaded_component_id = component_id
                        logging.info(f"Downloading component ID: {component_id}")
                        
                        response_content, content_disposition = export_mi_block_component(
                            api_base_url, component_id, site_id, api_headers
                        )
                        
                        if response_content:
                            mi_block_folder = f"mi-block-ID-{component_id}"
                            output_dir = os.path.join("output", str(site_id))
                            save_folder = os.path.join(output_dir, mi_block_folder)
                            os.makedirs(save_folder, exist_ok=True)
                            
                            filename = (
                                content_disposition.split('filename=')[1].strip('"')
                                if content_disposition and 'filename=' in content_disposition
                                else f"component_{component_id}.zip"
                            )
                            file_path = os.path.join(save_folder, filename)
                            
                            with open(file_path, "wb") as file:
                                file.write(response_content)
                            
                            file_size = len(response_content)
                            
                            if zipfile.is_zipfile(file_path):
                                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                                    zip_ref.extractall(save_folder)
                                os.remove(file_path)
                            
                            logging.info(f"✅ Zip extracted: {file_size} bytes")
                            
                            time.sleep(2)
                            
                            # Convert txt to json
                            logging.info("🔄 Converting TXT to JSON...")
                            txt_files_found = [f for f in os.listdir(save_folder) if f.endswith('.txt')]
                            
                            for extracted_file in os.listdir(save_folder):
                                extracted_file_path = os.path.join(save_folder, extracted_file)
                                if extracted_file.endswith('.txt'):
                                    new_file_path = os.path.splitext(extracted_file_path)[0] + '.json'
                                    try:
                                        with open(extracted_file_path, 'r', encoding="utf-8") as txt_file:
                                            content = txt_file.read()
                                            json_content = json.loads(content)
                                        
                                        with open(new_file_path, 'w', encoding="utf-8") as json_file:
                                            json.dump(json_content, json_file, indent=4)
                                        
                                        time.sleep(0.05)
                                        os.remove(extracted_file_path)
                                    except (json.JSONDecodeError, OSError) as e:
                                        logging.error(f"⚠️ Error: {e}")
                            
                            logging.info(f"✅ TXT to JSON complete")
                            
                            # Add level fields
                            records_file_path = os.path.join(save_folder, "MiBlockComponentRecords.json")
                            if os.path.exists(records_file_path):
                                from process_assembly import add_levels_to_records
                                add_levels_to_records(records_file_path)
                                logging.info(f"✅ Added level fields")
        
        # 4. Create menu_navigation.json
        menu_navigation_data = {
            "menu_component_name": menu_component_name,
            "menuLevel": menu_level,
            "pages": pages_tree
        }
        
        output_filename = f"{file_prefix}_menu_navigation.json"
        output_filepath = os.path.join(UPLOAD_FOLDER, output_filename)
        
        with open(output_filepath, 'w', encoding='utf-8') as f:
            json.dump(menu_navigation_data, f, indent=4, ensure_ascii=False)
        
        logging.info(f"✅ Menu navigation JSON saved: {output_filename}")
        
        # 5. Map pages to records and create payloads
        if downloaded_component_id:
            from process_assembly import map_pages_to_records, create_save_miblock_records_payload, create_new_records_payload, call_save_miblock_records_api, call_update_miblock_records_api
            if map_pages_to_records(file_prefix, site_id, downloaded_component_id):
                # Create payloads first (skip API calls by passing None)
                create_save_miblock_records_payload(file_prefix, downloaded_component_id, site_id, None, None)
                create_new_records_payload(file_prefix, downloaded_component_id, site_id, None, None)
                
                # 6. Update level 1 links based on sub-pages presence
                # Read menu_navigation.json to check which level 1 pages have sub_pages
                menu_nav_file = os.path.join(UPLOAD_FOLDER, f"{file_prefix}_menu_navigation.json")
                level_1_pages_with_subpages = set()
                
                if os.path.exists(menu_nav_file):
                    with open(menu_nav_file, 'r', encoding='utf-8') as f:
                        menu_nav_data = json.load(f)
                    
                    def collect_level_1_with_subpages(pages_list):
                        """Recursively collect level 1 page names that have sub_pages"""
                        for page in pages_list:
                            page_level = page.get("level", 0)
                            page_name = page.get("page_name", "")
                            sub_pages = page.get("sub_pages", [])
                            
                            if page_level == 1 and sub_pages:
                                level_1_pages_with_subpages.add(page_name)
                                logging.debug(f"Level 1 page '{page_name}' has {len(sub_pages)} sub-pages")
                            
                            # Recursively check sub_pages
                            if sub_pages:
                                collect_level_1_with_subpages(sub_pages)
                    
                    collect_level_1_with_subpages(menu_nav_data.get("pages", []))
                    logging.info(f"Found {len(level_1_pages_with_subpages)} level 1 pages with sub-pages: {list(level_1_pages_with_subpages)}")
                
                # 7. Apply custom properties and update links for level 1 records in payloads if configured
                if LEVEL_1_CUSTOM_PROPERTIES:
                    logging.info("Applying custom properties to level 1 records in payloads...")
                    
                    # Update new_records_payload.json
                    new_records_file = os.path.join(UPLOAD_FOLDER, f"{file_prefix}_new_records_payload.json")
                    if os.path.exists(new_records_file):
                        with open(new_records_file, 'r', encoding='utf-8') as f:
                            new_data = json.load(f)
                        
                        # Collect all level 1 records first
                        level_1_records = []
                        for record in new_data.get("records", []):
                            rec_level = record.get("level", 0)
                            if rec_level == 1:
                                level_1_records.append(record)
                        
                        # Split level 1 records in half: first half for left, second half for right
                        # For odd numbers, the larger half goes to left (e.g., 7 items = 4 left, 3 right)
                        total_level_1 = len(level_1_records)
                        split_point = (total_level_1 + 1) // 2  # Round up - larger half to left, smaller half to right
                        left_records = level_1_records[:split_point]
                        right_records = level_1_records[split_point:]
                        
                        logging.info(f"Found {total_level_1} level 1 new records: {len(left_records)} for left, {len(right_records)} for right")
                        
                        updated_count = 0
                        link_updated_count = 0
                        for record in new_data.get("records", []):
                            rec_level = record.get("level", 0)
                            page_name = record.get("page_name", "")
                            
                            if rec_level == 1:
                                try:
                                    record_json_string = record.get("recordDataJson", "{}")
                                    record_data = json.loads(record_json_string)
                                    
                                    # Determine if page has sub-pages
                                    has_subpages = page_name in level_1_pages_with_subpages
                                    
                                    # Add custom properties, but adjust enable-dropdown based on sub-pages
                                    custom_props = LEVEL_1_CUSTOM_PROPERTIES.copy()
                                    if not has_subpages:
                                        # No sub-pages, set enable-dropdown to No
                                        custom_props["enable-dropdown[]"] = ["No"]
                                    
                                    # Determine if this record should be in left or right
                                    is_left = record in left_records
                                    if is_left:
                                        custom_props["enable-menu-item-in-left[]"] = ["Yes"]
                                        custom_props["enable-menu-item-in-right[]"] = ["No"]
                                    else:
                                        custom_props["enable-menu-item-in-left[]"] = ["No"]
                                        custom_props["enable-menu-item-in-right[]"] = ["Yes"]
                                    
                                    record_data.update(custom_props)
                                    
                                    # Update link if page has sub-pages
                                    # Find the link key (ending with -link)
                                    link_key = None
                                    for key in record_data.keys():
                                        if key.endswith("-link") and key != "Id" and key != "ParentId":
                                            link_key = key
                                            break
                                    
                                    if link_key:
                                        if has_subpages:
                                            # Has sub-pages, set to javascript:;
                                            record_data[link_key] = "javascript:;"
                                            link_updated_count += 1
                                            logging.debug(f"Updated link for '{page_name}' to javascript:; (has sub-pages)")
                                        # If no sub-pages, keep the existing link value
                                    
                                    record["recordDataJson"] = json.dumps(record_data, ensure_ascii=False)
                                    updated_count += 1
                                    logging.debug(f"Updated level 1 record: {page_name} (has_subpages={has_subpages}, is_left={is_left})")
                                except Exception as e:
                                    logging.error(f"Error updating new record: {e}")
                        
                        if updated_count > 0:
                            with open(new_records_file, 'w', encoding='utf-8') as f:
                                json.dump(new_data, f, indent=4, ensure_ascii=False)
                            logging.info(f"✅ Updated {updated_count} level 1 records in new_records_payload.json")
                            if link_updated_count > 0:
                                logging.info(f"   → Updated {link_updated_count} links to javascript:; (pages with sub-pages)")
                            
                            # Call API with updated records
                            if api_base_url and api_headers:
                                logging.info("Calling API to save new records with custom properties...")
                                call_save_miblock_records_api(api_base_url, api_headers, new_data.get("records", []), file_prefix, f"{file_prefix}_new_records_payload.json")
                    
                    # Update save_miblock_records_payload.json
                    matched_records_file = os.path.join(UPLOAD_FOLDER, f"{file_prefix}_save_miblock_records_payload.json")
                    if os.path.exists(matched_records_file):
                        with open(matched_records_file, 'r', encoding='utf-8') as f:
                            matched_data = json.load(f)
                        
                        # Collect all level 1 records first
                        level_1_records = []
                        for record in matched_data.get("records", []):
                            rec_level = record.get("matched_page_level", 0)
                            if rec_level == 1:
                                level_1_records.append(record)
                        
                        # Split level 1 records in half: first half for left, second half for right
                        # For odd numbers, the larger half goes to left (e.g., 7 items = 4 left, 3 right)
                        total_level_1 = len(level_1_records)
                        split_point = (total_level_1 + 1) // 2  # Round up - larger half to left, smaller half to right
                        left_records = level_1_records[:split_point]
                        right_records = level_1_records[split_point:]
                        
                        logging.info(f"Found {total_level_1} level 1 matched records: {len(left_records)} for left, {len(right_records)} for right")
                        
                        updated_count = 0
                        link_updated_count = 0
                        for record in matched_data.get("records", []):
                            rec_level = record.get("matched_page_level", 0)
                            page_name = record.get("matched_page_name", "")
                            
                            if rec_level == 1:
                                try:
                                    record_json_string = record.get("recordDataJson", "{}")
                                    record_data = json.loads(record_json_string)
                                    
                                    # Determine if page has sub-pages
                                    has_subpages = page_name in level_1_pages_with_subpages
                                    
                                    # Add custom properties, but adjust enable-dropdown based on sub-pages
                                    custom_props = LEVEL_1_CUSTOM_PROPERTIES.copy()
                                    if not has_subpages:
                                        # No sub-pages, set enable-dropdown to No
                                        custom_props["enable-dropdown[]"] = ["No"]
                                    
                                    # Determine if this record should be in left or right
                                    is_left = record in left_records
                                    if is_left:
                                        custom_props["enable-menu-item-in-left[]"] = ["Yes"]
                                        custom_props["enable-menu-item-in-right[]"] = ["No"]
                                    else:
                                        custom_props["enable-menu-item-in-left[]"] = ["No"]
                                        custom_props["enable-menu-item-in-right[]"] = ["Yes"]
                                    
                                    record_data.update(custom_props)
                                    
                                    # Update link if page has sub-pages
                                    # Find the link key (ending with -link)
                                    link_key = None
                                    for key in record_data.keys():
                                        if key.endswith("-link") and key != "Id" and key != "ParentId":
                                            link_key = key
                                            break
                                    
                                    if link_key:
                                        if has_subpages:
                                            # Has sub-pages, set to javascript:;
                                            record_data[link_key] = "javascript:;"
                                            link_updated_count += 1
                                            logging.debug(f"Updated link for '{page_name}' to javascript:; (has sub-pages)")
                                        # If no sub-pages, keep the existing link value
                                    
                                    record["recordDataJson"] = json.dumps(record_data, ensure_ascii=False)
                                    updated_count += 1
                                    logging.debug(f"Updated level 1 matched record: {page_name} (has_subpages={has_subpages}, is_left={is_left})")
                                except Exception as e:
                                    logging.error(f"Error updating matched record: {e}")
                        
                        if updated_count > 0:
                            with open(matched_records_file, 'w', encoding='utf-8') as f:
                                json.dump(matched_data, f, indent=4, ensure_ascii=False)
                            logging.info(f"✅ Updated {updated_count} level 1 records in save_miblock_records_payload.json")
                            if link_updated_count > 0:
                                logging.info(f"   → Updated {link_updated_count} links to javascript:; (pages with sub-pages)")
                            
                            # Call API with updated records
                            if api_base_url and api_headers:
                                # Fix parentRecordId for sub-records before calling update API
                                logging.info("Fixing parentRecordId for sub-records before update API call...")
                                fix_parent_record_ids_for_sub_records(file_prefix)
                                
                                logging.info("Calling API to update matched records with custom properties...")
                                # Read updated file after parentRecordId fix
                                with open(matched_records_file, 'r', encoding='utf-8') as f:
                                    matched_data = json.load(f)
                                # Sort by level to ensure level 1 is updated before level 2
                                matched_records = matched_data.get("records", [])
                                matched_records.sort(key=lambda r: r.get("matched_page_level", 0))
                                call_update_miblock_records_api(api_base_url, api_headers, matched_records, file_prefix, f"{file_prefix}_save_miblock_records_payload.json")
                else:
                    # No custom properties, but still update links for level 1 pages with sub-pages
                    logging.info("Updating links for level 1 pages with sub-pages...")
                    
                    # Update new_records_payload.json
                    new_records_file = os.path.join(UPLOAD_FOLDER, f"{file_prefix}_new_records_payload.json")
                    if os.path.exists(new_records_file):
                        with open(new_records_file, 'r', encoding='utf-8') as f:
                            new_data = json.load(f)
                        
                        link_updated_count = 0
                        for record in new_data.get("records", []):
                            rec_level = record.get("level", 0)
                            page_name = record.get("page_name", "")
                            
                            if rec_level == 1 and page_name in level_1_pages_with_subpages:
                                try:
                                    record_json_string = record.get("recordDataJson", "{}")
                                    record_data = json.loads(record_json_string)
                                    
                                    # Find the link key (ending with -link)
                                    link_key = None
                                    for key in record_data.keys():
                                        if key.endswith("-link") and key != "Id" and key != "ParentId":
                                            link_key = key
                                            break
                                    
                                    if link_key:
                                        record_data[link_key] = "javascript:;"
                                        record["recordDataJson"] = json.dumps(record_data, ensure_ascii=False)
                                        link_updated_count += 1
                                        logging.debug(f"Updated link for '{page_name}' to javascript:;")
                                except Exception as e:
                                    logging.error(f"Error updating link for new record: {e}")
                        
                        if link_updated_count > 0:
                            with open(new_records_file, 'w', encoding='utf-8') as f:
                                json.dump(new_data, f, indent=4, ensure_ascii=False)
                            logging.info(f"✅ Updated {link_updated_count} links in new_records_payload.json")
                    
                    # Update save_miblock_records_payload.json
                    matched_records_file = os.path.join(UPLOAD_FOLDER, f"{file_prefix}_save_miblock_records_payload.json")
                    if os.path.exists(matched_records_file):
                        with open(matched_records_file, 'r', encoding='utf-8') as f:
                            matched_data = json.load(f)
                        
                        link_updated_count = 0
                        for record in matched_data.get("records", []):
                            rec_level = record.get("matched_page_level", 0)
                            page_name = record.get("matched_page_name", "")
                            
                            if rec_level == 1 and page_name in level_1_pages_with_subpages:
                                try:
                                    record_json_string = record.get("recordDataJson", "{}")
                                    record_data = json.loads(record_json_string)
                                    
                                    # Find the link key (ending with -link)
                                    link_key = None
                                    for key in record_data.keys():
                                        if key.endswith("-link") and key != "Id" and key != "ParentId":
                                            link_key = key
                                            break
                                    
                                    if link_key:
                                        record_data[link_key] = "javascript:;"
                                        record["recordDataJson"] = json.dumps(record_data, ensure_ascii=False)
                                        link_updated_count += 1
                                        logging.debug(f"Updated link for '{page_name}' to javascript:;")
                                except Exception as e:
                                    logging.error(f"Error updating link for matched record: {e}")
                        
                        if link_updated_count > 0:
                            with open(matched_records_file, 'w', encoding='utf-8') as f:
                                json.dump(matched_data, f, indent=4, ensure_ascii=False)
                            logging.info(f"✅ Updated {link_updated_count} links in save_miblock_records_payload.json")
                    
                    # Call API normally with existing payloads
                    if api_base_url and api_headers:
                        # Read and call API for new records
                        if os.path.exists(new_records_file):
                            with open(new_records_file, 'r', encoding='utf-8') as f:
                                new_data = json.load(f)
                            call_save_miblock_records_api(api_base_url, api_headers, new_data.get("records", []), file_prefix, f"{file_prefix}_new_records_payload.json")
                        
                        # Fix parentRecordId for sub-records before calling update API
                        if os.path.exists(matched_records_file):
                            logging.info("Fixing parentRecordId for sub-records before update API call...")
                            fix_parent_record_ids_for_sub_records(file_prefix)
                            
                            # Read updated file after parentRecordId fix
                            with open(matched_records_file, 'r', encoding='utf-8') as f:
                                matched_data = json.load(f)
                            matched_records = matched_data.get("records", [])
                            matched_records.sort(key=lambda r: r.get("matched_page_level", 0))
                            call_update_miblock_records_api(api_base_url, api_headers, matched_records, file_prefix, f"{file_prefix}_save_miblock_records_payload.json")
        
        logging.info("END: Menu Navigation Processing Complete")
        logging.info("========================================================")

        return {
            "menu_navigation_created": True,
            "file_prefix": file_prefix,
            "downloaded_component_id": downloaded_component_id
        }
        
    except Exception as e:
        logging.error(f"Error in menu navigation: {e}")
        raise

