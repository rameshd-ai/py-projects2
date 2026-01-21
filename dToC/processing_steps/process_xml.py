import time
import os
import json
import xml.etree.ElementTree as ET
import re
import html
import copy
import sys
from typing import List, Dict, Any, Tuple, Set, Optional

# Import UPLOAD_FOLDER from the top-level config
from config import UPLOAD_FOLDER

# ------------------------------------------------------------------
# [TOOL] CONFIG UTILITY FUNCTIONS (Added for file persistence)
# ------------------------------------------------------------------

def get_config_filepath(file_prefix: str) -> str:
    """
    Constructs the unique config file path using the file_prefix (unique token) 
    to ensure non-collision with other processed files.
    
    This function strictly uses the provided file_prefix (the UUID token) and 
    the mandatory suffix '_config.json'.
    """
    # Combines the unique file_prefix/token with the required suffix.
    return os.path.join(UPLOAD_FOLDER, f"{file_prefix}_config.json")

def load_settings(file_prefix: str) -> Dict[str, Any] | None:
    """Loads the settings/config file based on the unique prefix (token) for persistence."""
    filepath = get_config_filepath(file_prefix)
    
    # If the file doesn't exist yet, return an empty dict to start fresh
    if not os.path.exists(filepath):
        return {} 
    try:
        with open(filepath, "r", encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"XML Processor: Error loading persistence config file ({filepath}): {e}", file=sys.stderr)
        return None

def save_settings(file_prefix: str, settings: Dict[str, Any]) -> bool:
    """Saves the updated settings/config file using the unique prefix (token)."""
    filepath = get_config_filepath(file_prefix)
    try:
        # Ensure the upload directory exists
        os.makedirs(os.path.dirname(filepath), exist_ok=True) 
        with open(filepath, "w", encoding='utf-8') as f:
            json.dump(settings, f, indent=4)
        return True
    except IOError as e:
        print(f"XML Processor: Error saving settings file ({filepath}): {e}", file=sys.stderr)
        return False


# ------------------------------------------------------------------
# [TOOL] XML/HTML Utility Functions (MOVED from original config_and_logic.py)
# ------------------------------------------------------------------

def aggressively_unescape_and_clean(content):
    """Repeatedly unescapes HTML entities and cleans residual HTML structure."""
    unescaped = html.unescape(content)
    unescaped = html.unescape(unescaped)
    # Allows <strong> tags but removes all other tags
    cleanr = re.compile(r'<(?!strong|/strong)[^>]*?>')
    clean_text = re.sub(cleanr, '\n', unescaped).strip()
    clean_text = clean_text.replace('&nbsp;', ' ').replace('&amp;nbsp;', ' ')
    # Normalize multiple newlines/spaces to a single newline
    clean_text = re.sub(r'(\n|\s)+', '\n', clean_text).strip()
    return clean_text

def clean_html(raw_html):
    """Cleans up escaped HTML content for simpler fields like 'description'."""
    # Matches <tag>, &lt;tag&gt;, &amp;nbsp;, &lt;br&gt;
    cleanr = re.compile(r'<.*?>|&lt;.*?&gt;|&amp;nbsp;|&lt;br&gt;')
    # First, handle &amp; and &quot; specifically
    text = raw_html.replace('&amp;', '&').replace('&quot;', '"')
    clean_text = re.sub(cleanr, '\n', text).strip()
    clean_text = re.sub(r'(\n|\s)+', '\n', clean_text).strip()
    return clean_text

def extract_component_names(clean_html_content):
    """Extracts components STRICTLY from text inside <strong> tags."""
    if not clean_html_content: return []
    ordered_components = []
    seen_components = set()
    # Only search content BEFORE the 'PageInfoBlock' marker if present
    content_area = re.split(r'PageInfoBlock', clean_html_content, 1)[0] 
    
    strong_tag_pattern = re.compile(r'<strong>(.*?)</strong>', re.IGNORECASE | re.DOTALL)
    
    for match in strong_tag_pattern.finditer(content_area):
        component_text = match.group(1).strip()
        component_text = re.sub(r'[\n\t]', ' ', component_text)
        component_text = re.sub(r'\s+', ' ', component_text)
        # Final cleanup to remove any residual tags or entities within the strong tags
        final_component = re.sub(r'<[^>]+>|&nbsp;', '', component_text).strip()
        if final_component and final_component not in seen_components:
            ordered_components.append(final_component)
            seen_components.add(final_component)
    return ordered_components


# def extract_meta_info(raw_html_content: str) -> Dict[str, Any]:
#     """
#     Extracts PageTemplateName, DefaultTitle, and DefaultDescription using targeted regex 
#     on the triple-unescaped block following 'PageInfoBlock'.
#     """
#     meta_info: Dict[str, Any] = {}
#     if not raw_html_content:
#         return meta_info

#     # Triple-unescape for highly escaped content
#     unescaped_content = html.unescape(raw_html_content)
#     unescaped_content = html.unescape(unescaped_content)
#     unescaped_content = html.unescape(unescaped_content)
    
#     # Split the content at the marker
#     parts = unescaped_content.split('PageInfoBlock', 1)
#     if len(parts) < 2:
#         return meta_info

#     meta_block = parts[1]
    
#     target_keys = {
#         "PageTemplateName": "PageTemplateName",
#         "Default Title": "DefaultTitle",
#         "Default Description": "DefaultDescription",
#         "Header1":"Header1",
#         "Header2":"Header2",
#         "Footer1":"Footer1",
#         "Footer2":"Footer2"
#     }

#     for xml_key, dict_key in target_keys.items():
#         # Regex to find text following the key until the next key or end of block
#         pattern = re.compile(r'(?<=' + re.escape(xml_key) + r':)\s*(.*?)(?=<|$)', re.IGNORECASE | re.DOTALL)
        
#         match = pattern.search(meta_block)
        
#         if match:
#             value = match.group(1).strip()
#             # Normalize whitespace
#             value = re.sub(r'[\r\n\s]+', ' ', value).strip() 
            
#             if value:
#                 meta_info[dict_key] = value
                
#     return meta_info



def extract_meta_info(raw_html_content: str) -> Dict[str, Any]:
    """
    Extracts PageTemplateName, DefaultTitle, and DefaultDescription using targeted regex 
    on the triple-unescaped block following 'PageInfoBlock'.
    
    If a key is found, it is added to the dictionary. If the value is blank, 
    the dictionary value will be an empty string ("").
    """
    meta_info: Dict[str, Any] = {}
    if not raw_html_content:
        return meta_info

    # Triple-unescape for highly escaped content
    unescaped_content = html.unescape(raw_html_content)
    unescaped_content = html.unescape(unescaped_content)
    unescaped_content = html.unescape(unescaped_content)
    
    # Split the content at the marker
    parts = unescaped_content.split('PageInfoBlock', 1)
    if len(parts) < 2:
        # PageInfoBlock marker not found, but we still need to ensure ShowInNavigation exists in meta_info
        # Try to extract ShowInNavigation from the full content
        meta_block = unescaped_content
    else:
        meta_block = parts[1]
    
    # Debug: Check if ShowInNavigation exists in meta_block
    if 'ShowInNavigation' in meta_block:
        print(f"[DEBUG] ShowInNavigation found in meta_block (length: {len(meta_block)})")
    else:
        print(f"[DEBUG] ShowInNavigation NOT found in meta_block. Checking full content...")
        if 'ShowInNavigation' in unescaped_content:
            print(f"[DEBUG] ShowInNavigation found in full unescaped_content, but not in meta_block after split")
    
    target_keys = {
        "PageTemplateName": "PageTemplateName",
        "Default Title": "DefaultTitle",
        "Default Description": "DefaultDescription",
        "Header1":"Header1",
        "Header2":"Header2",
        "Footer1":"Footer1",
        "Footer2":"Footer2",
        "ShowInNavigation": "ShowInNavigation"  # Extract ShowInNavigation (appears after Footer2)
    }

    for xml_key, dict_key in target_keys.items():
        # Handle multiple formats:
        # Format 1: Standard format: "FieldName: Value"
        # Format 2: HTML span format: "FieldName</span><span ...>: Value</span>"
        # Format 3: HTML span format with escaped entities: "FieldName&lt;/span&gt;&lt;span ...&gt;: Value&lt;/span&gt;"
        
        # Pattern 1: Standard format: "FieldName: Value" (no HTML tags)
        # Updated to handle newlines/spaces between fields
        # Note: Using non-lookbehind pattern to avoid fixed-width requirement
        pattern1 = re.compile(re.escape(xml_key) + r'\s*:\s*([^\n<]+?)(?=\s*(?:PageTemplateName|Default\s+Title|Default\s+Description|Header1|Header2|Footer1|Footer2|ShowInNavigation)\s*:|<|$)', re.IGNORECASE | re.DOTALL)
        
        # Pattern 2: HTML span format: "FieldName</span><span ...>: Value</span>"
        # Matches FieldName, optional closing/opening tags, colon, then value until closing tag
        pattern2 = re.compile(re.escape(xml_key) + r'(?:</span>|<[^>]*>)*\s*:\s*([^<]+?)(?=</span>|<(?:span|/span|div|/div|p|/p)|$)', re.IGNORECASE | re.DOTALL)
        
        # Pattern 2b: Value inside span tag: "FieldName: <span ...>Value</span>"
        # This handles cases like "PageTemplateName: <span data-teams="true">Base Layout Page - Without Banner</span>"
        pattern2b = re.compile(re.escape(xml_key) + r'\s*:\s*<[^>]*>([^<]+?)</(?:span|div|p)>', re.IGNORECASE | re.DOTALL)
        
        # Pattern 3: More flexible - handles escaped HTML entities and complex span structures
        # Matches FieldName followed by any HTML/escaped content, colon, then value
        pattern3 = re.compile(re.escape(xml_key) + r'(?:&lt;/span&gt;|</span>|&lt;[^&]+&gt;|<[^>]*>)*\s*:\s*([^<&]+?)(?=&lt;/span&gt;|</span>|&lt;[^&]+&gt;|<(?:span|/span|div|/div|p|/p)|$)', re.IGNORECASE | re.DOTALL)
        
        # Pattern 4: Very permissive - for ShowInNavigation in complex nested spans
        # Matches FieldName, any characters (including tags), colon, then captures value
        pattern4 = re.compile(re.escape(xml_key) + r'[^:]*:\s*([A-Za-z]+)', re.IGNORECASE)
        
        # Pattern 5: Special case for ShowInNavigation where field name and value are in separate spans
        # Format: <span>ShowInNavigation</span><span>: Yes</span>
        # Also handles case where there's whitespace/newlines between Footer2 and ShowInNavigation
        if xml_key == "ShowInNavigation":
            # Very simple pattern: ShowInNavigation, then ANY characters (including all HTML, newlines, spaces), then :, then capture Yes/No
            # This handles ALL cases:
            # - Footer2: ShowInNavigation: Yes (space after colon)
            # - Footer2:ShowInNavigation: Yes (no space)
            # - Footer2:\nShowInNavigation: Yes (newline)
            # - Footer2:</p><p>ShowInNavigation: Yes (separate paragraphs)
            # The pattern [\s\S]*? matches any character (including spaces, newlines, HTML tags)
            # The \s* after : makes space after colon optional
            pattern5 = re.compile(re.escape(xml_key) + r'[\s\S]*?:\s*([A-Za-z]+)', re.IGNORECASE)
            print(f"[DEBUG] Searching for ShowInNavigation in meta_block (length: {len(meta_block)}, first 500 chars: {meta_block[:500]})")
        else:
            pattern5 = None
        
        # Check pattern2b FIRST (for span-wrapped values) before pattern1 (which might match empty string)
        match = pattern2b.search(meta_block) or pattern1.search(meta_block) or pattern2.search(meta_block) or pattern3.search(meta_block) or pattern4.search(meta_block) or (pattern5.search(meta_block) if pattern5 else None)
        
        if xml_key == "ShowInNavigation" and not match:
            print(f"[DEBUG] ShowInNavigation NOT matched. Tried all patterns. meta_block contains 'ShowInNavigation': {'ShowInNavigation' in meta_block}")
        
        if match:
            # Get the captured value and strip leading/trailing whitespace
            value = match.group(1).strip()
            
            # Skip if value is empty (pattern1 might match empty string when < comes immediately after colon)
            if not value:
                match = None
            else:
                # Remove any remaining HTML tags from the value
                value = re.sub(r'<[^>]+>', '', value)
                
                # Normalize internal whitespace (replace newlines/tabs/spaces with a single space)
                value = re.sub(r'[\r\n\s]+', ' ', value).strip()
                
                # Additional unescape for ShowInNavigation to handle any HTML entities
                if dict_key == "ShowInNavigation":
                    value = html.unescape(value)
                    value = value.strip()
                
                # [PROCESSING] CHANGE: Now we add the key to the dictionary if the marker was found.
                # The value will be "" if it was blank in the source.
                meta_info[dict_key] = value
                # Debug logging for ShowInNavigation
                if dict_key == "ShowInNavigation":
                    print(f"[DEBUG XML Extraction] Extracted ShowInNavigation: '{value}'")
    
    # Always ensure ShowInNavigation exists in meta_info (even if empty)
    # This ensures it appears in the JSON output
    if "ShowInNavigation" not in meta_info:
        meta_info["ShowInNavigation"] = ""
        print(f"[DEBUG XML Extraction] ShowInNavigation not found, defaulting to empty string")
    
    # Debug: Print all keys in meta_info to verify
    print(f"[DEBUG XML Extraction] Final meta_info keys: {list(meta_info.keys())}, ShowInNavigation='{meta_info.get('ShowInNavigation', 'NOT FOUND')}'")
                
    return meta_info

def force_to_clean_html(content: str) -> Tuple[str, str]:
    """
    Normalizes complex escaped HTML fragments into a clean HTML string 
    suitable for component regex, using ElementTree for robustness.
    """
    unescaped = html.unescape(content)
    unescaped = html.unescape(unescaped)
    
    wrapped_content = f"<dummy>{unescaped}</dummy>"
    
    try:
        # Try to parse as valid XML/HTML fragment
        root = ET.fromstring(wrapped_content)
        
        clean_blocks = []
        for child in root:
            # Use ET.tostring to serialize back to clean HTML/XML string
            block_content = ET.tostring(child, encoding='unicode', method='html')
            clean_blocks.append(block_content)
            
        clean_html_string = "\n---\n".join(clean_blocks).strip()
        
        return content, clean_html_string 
        
    except ET.ParseError:
        # Fallback to aggressive regex cleaning if XML parsing fails
        clean_html_string = aggressively_unescape_and_clean(content)
        return content, clean_html_string
    except Exception:
        # General fallback
        return content, aggressively_unescape_and_clean(content)


# --- Core XML to JSON Functions ---

def get_all_descendants(start_id: str, all_cells: Dict[str, Any]) -> Set[str]:
    """Recursively finds all descendant IDs for a given start ID."""
    descendants = set()
    to_visit = [start_id]

    while to_visit:
        current_id = to_visit.pop(0)

        # Find direct children
        children = [
            cell_id for cell_id, data in all_cells.items()
            if data.get("parent_id") == current_id and cell_id not in descendants
        ]

        for child_id in children:
            descendants.add(child_id)
            to_visit.append(child_id)

    return descendants


def build_tree(all_cells: Dict[str, Any], root_ids: Set[str], title: str, link: str):
    """Builds a nested page structure (sitemap) from a flat dictionary of cells."""
    sitemap_data = {"title": title, "link": link, "pages": []}
    if not all_cells or not root_ids: return sitemap_data

    # Use a copy to allow safe popping of visited nodes
    id_to_cell = copy.deepcopy(all_cells)

    root_pages_list = sorted(
        [data for cell_id, data in id_to_cell.items() if cell_id in root_ids],
        key=lambda x: x["order"]
    )

    def recursive_build(page_id):
        if page_id not in id_to_cell:
            return None

        page = id_to_cell[page_id]

        children = [data for data in id_to_cell.values() if data.get("parent_id") == page_id]
        children_sorted = sorted(children, key=lambda x: x["order"])

        for child in children_sorted:
            # Recursively build children
            built_child = recursive_build(child["id"])
            if built_child:
                page["children"].append(built_child)

            # Mark child as visited by popping it from the temporary map
            if child["id"] in id_to_cell:
                id_to_cell.pop(child["id"])

        return page

    for page in root_pages_list:
        if page["id"] in id_to_cell:
            sitemap_data["pages"].append(recursive_build(page["id"]))
            id_to_cell.pop(page["id"]) # Mark root as visited

    def remove_temp_keys(p):
        """Clean up temporary keys before final JSON output."""
        p.pop("parent_id", None)
        p.pop("order", None)
        for child in p["children"]: remove_temp_keys(child)

    for page in sitemap_data["pages"]:
        remove_temp_keys(page)

    return sitemap_data


def parse_sleekplan_xml(xml_file_path: str) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    """
    Parses the XML file and returns four distinct, structured sitemap data dictionaries.
    """
    if not os.path.exists(xml_file_path):
        empty_data = {"title": "Untitled Sitemap", "link": None, "pages": []}
        return empty_data, empty_data, empty_data, empty_data

    try:
        tree = ET.parse(xml_file_path)
        root = tree.getroot()
    except Exception as e:
        raise e

    title_text = root.find('title').text.replace('&amp;', '&').replace('&', 'and') if root.find('title') is not None else "Untitled Sitemap"
    link_text = root.find('link').text if root.find('link') is not None else None

    all_cells = {}; cells_element = root.find('.//cells')
    if cells_element is None:
        empty_data = {"title": title_text, "link": link_text, "pages": []}
        return empty_data, empty_data, empty_data, empty_data

    home_page_id = None

    for cell in cells_element.findall('cell'):
        cell_id = cell.get('id')
        cell_level = cell.find('level').text if cell.find('level') is not None else 'unknown'

        raw_content_full = ""
        clean_html_blocks = []

        # Aggregate content from all 'wysiwyg' blocks
        for contents in cell.findall('.//contents/body/wysiwyg'):
            content = contents.find('content')
            if content is not None and content.text:
                
                original_content, clean_html_block = force_to_clean_html(content.text)
                
                raw_content_full += original_content 
                clean_html_blocks.append(clean_html_block)

        desc = cell.find('desc')
        desc_text = desc.text if desc is not None and desc.text else ""
        clean_desc = clean_html(desc_text)
        
        page_meta_info = extract_meta_info(raw_content_full)
        
        component_content = "\n---\n".join(clean_html_blocks).strip()

        cell_data = {
            "id": cell_id,
            "text": cell.find('text').text.replace('&amp;', '&').replace('&', 'and') if cell.find('text') is not None else "Untitled",
            "order": int(cell.find('order').text) if cell.find('order') is not None else 9999,
            "level": cell_level,
            "parent_id": cell.find('parent').text if cell.find('parent') is not None else None,
            "description": clean_desc,
            "content_blocks": component_content, # The raw blocks of (potentially cleaned) HTML content
            "meta_info": page_meta_info, 
            "children": [] # Will be populated by build_tree
        }
        all_cells[cell_id] = cell_data

        if cell_data["level"] == 'home':
            home_page_id = cell_id

    # --- Identify Root IDs for the four distinct maps ---
    
    # 1. Home Map
    home_root_ids = {home_page_id} if home_page_id else set()
    
    # 2. Nav Map (Level 1 pages with no parent, and their descendants)
    nav_root_ids = {
        cell_id for cell_id, data in all_cells.items()
        if data["level"] == '1' and data.get("parent_id") is None
    }
    nav_tree_ids = set()
    for root_id in nav_root_ids:
        nav_tree_ids.add(root_id)
        nav_tree_ids.update(get_all_descendants(root_id, all_cells))
        
    all_cells_nav = {cell_id: all_cells[cell_id] for cell_id in nav_tree_ids}
    
    # 3. Footer/Unknown Map (Level 'foot' or 'unknown', not part of Nav tree)
    foot_unk_root_ids = {
        cell_id for cell_id, data in all_cells.items()
        if data["level"] in ['foot', 'unknown'] and cell_id not in nav_tree_ids
    }
    
    # 4. Utility Map (Level 'util', not part of Nav tree)
    util_root_ids = {
        cell_id for cell_id, data in all_cells.items()
        if data["level"] == 'util' and cell_id not in nav_tree_ids
    }

    # --- Build the four maps ---
    home_sitemap_data = build_tree(all_cells, home_root_ids, title_text, link_text)
    foot_unknown_sitemap_data = build_tree(all_cells, foot_unk_root_ids, title_text, link_text)
    util_sitemap_data = build_tree(all_cells, util_root_ids, title_text, link_text)
    nav_sitemap_data = build_tree(all_cells_nav, nav_root_ids, title_text, link_text)

    return home_sitemap_data, foot_unknown_sitemap_data, util_sitemap_data, nav_sitemap_data


def extract_menu_properties_from_util_pages(util_data: Dict[str, Any]) -> Tuple[Optional[str], Optional[int], Dict[str, Any]]:
    """
    Extracts menu component name, menu level, and custom properties from the automation guide in util pages.
    
    Returns:
        Tuple of (menu_component_name, menu_level, level_1_custom_properties)
    """
    menu_component_name = None
    menu_level = None
    level_1_custom_properties = {}
    
    # Search for automation guide in util pages
    for page in util_data.get('pages', []):
        page_name = page.get('text', '')
        if "automation guide" in page_name.strip().lower():
            content_source = page.get('content_blocks', '') or page.get('description', '')
            
            # Normalize whitespace and newlines first - this is critical for JSON parsing
            # The description field often has newlines between every character/word
            content_source = re.sub(r'\n+', ' ', content_source)  # Replace newlines with spaces
            content_source = re.sub(r'\s+', ' ', content_source)  # Normalize multiple spaces to single space
            
            # Unescape HTML entities multiple times
            decoded_content = html.unescape(content_source)
            decoded_content = html.unescape(decoded_content)
            decoded_content = html.unescape(decoded_content)
            
            print(f"[XML Processor] Searching for menu properties in automation guide...")
            print(f"[XML Processor] Content preview: {decoded_content[:300]}...")
            
            # Try to find mainMenu JSON pattern
            # Look for the pattern - we need to match the entire array, handling nested brackets
            # First, find where mainMenu starts
            main_menu_start_pattern = r'["\']?mainMenu["\']?\s*:\s*\['
            start_match = re.search(main_menu_start_pattern, decoded_content, re.IGNORECASE)
            json_match = None
            
            if start_match:
                # Found the start, now find the matching closing bracket
                start_pos = start_match.end() - 1  # Position of opening [
                bracket_count = 0
                end_pos = start_pos
                
                for i in range(start_pos, len(decoded_content)):
                    if decoded_content[i] == '[':
                        bracket_count += 1
                    elif decoded_content[i] == ']':
                        bracket_count -= 1
                        if bracket_count == 0:
                            end_pos = i
                            break
                
                # Extract the full array content
                if bracket_count == 0 and end_pos > start_pos:
                    array_content_full = decoded_content[start_pos+1:end_pos]
                    # Create a mock match object for compatibility
                    class MockMatch:
                        def __init__(self, content):
                            self._content = content
                        def group(self, idx):
                            return self._content if idx == 1 else None
                    json_match = MockMatch(array_content_full)
            
            if json_match:
                try:
                    array_content = json_match.group(1)
                    # Clean up HTML tags and entities
                    array_content = re.sub(r'<[^>]+>', '', array_content)
                    array_content = re.sub(r'<br\s*/?>', '', array_content, flags=re.IGNORECASE)
                    # Normalize whitespace but preserve JSON structure
                    array_content = re.sub(r'\s+', ' ', array_content).strip()
                    
                    # Fix extra spaces inside quotes: " enable-dropdown[] " -> "enable-dropdown[]"
                    # This regex finds quoted strings and removes leading/trailing spaces inside the quotes
                    array_content = re.sub(r'"\s+([^"]+?)\s+"', r'"\1"', array_content)
                    
                    json_obj_str = '{"mainMenu": [' + array_content + ']}'
                    print(f"[XML Processor] Attempting to parse JSON: {json_obj_str[:200]}...")  # Debug output
                    try:
                        parsed_json = json.loads(json_obj_str)
                        if 'mainMenu' in parsed_json and isinstance(parsed_json['mainMenu'], list) and len(parsed_json['mainMenu']) > 0:
                            menu_item = parsed_json['mainMenu'][0]
                            menu_component_name = menu_item.get('componentName', '').strip()
                            menu_level = menu_item.get('menuLevel')
                            
                            # Extract custom properties dynamically from XML
                            if 'enable-dropdown[]' in menu_item:
                                level_1_custom_properties['enable-dropdown[]'] = menu_item['enable-dropdown[]'] if isinstance(menu_item['enable-dropdown[]'], list) else [menu_item['enable-dropdown[]']]
                            
                            if 'enable-menu-item-in-left[]' in menu_item:
                                level_1_custom_properties['enable-menu-item-in-left[]'] = menu_item['enable-menu-item-in-left[]'] if isinstance(menu_item['enable-menu-item-in-left[]'], list) else [menu_item['enable-menu-item-in-left[]']]
                            
                            if 'enable-menu-item-in-right[]' in menu_item:
                                level_1_custom_properties['enable-menu-item-in-right[]'] = menu_item['enable-menu-item-in-right[]'] if isinstance(menu_item['enable-menu-item-in-right[]'], list) else [menu_item['enable-menu-item-in-right[]']]
                            
                            if menu_component_name:
                                print(f"[XML Processor] Found menu component: {menu_component_name}, menuLevel: {menu_level}")
                                if level_1_custom_properties:
                                    print(f"[XML Processor] Extracted custom properties from XML: {level_1_custom_properties}")
                                break
                    except json.JSONDecodeError:
                        # Try regex fallback
                        component_name_match = re.search(r'["\']componentName["\']\s*:\s*["\']([^"\']+)["\']', array_content, re.IGNORECASE)
                        if component_name_match:
                            menu_component_name = component_name_match.group(1).strip()
                        
                        menu_level_match = re.search(r'["\']menuLevel["\']\s*:\s*(\d+)', array_content, re.IGNORECASE)
                        if menu_level_match:
                            try:
                                menu_level = int(menu_level_match.group(1))
                            except ValueError:
                                pass
                        
                        # Try to extract custom properties using regex with more flexible patterns
                        # Handle variations like: "enable-dropdown[]":["Yes"] or "enable-dropdown[]": ["Yes"] or 'enable-dropdown[]': ['Yes']
                        dropdown_match = re.search(r'["\']enable-dropdown\s*\[\s*\]["\']?\s*:\s*\[([^\]]+)\]', array_content, re.IGNORECASE)
                        if dropdown_match:
                            values = [v.strip().strip('"\'') for v in dropdown_match.group(1).split(',')]
                            level_1_custom_properties['enable-dropdown[]'] = [v for v in values if v]  # Filter empty values
                            print(f"[XML Processor] Extracted enable-dropdown[]: {level_1_custom_properties['enable-dropdown[]']}")
                        
                        left_match = re.search(r'["\']enable-menu-item-in-left\s*\[\s*\]["\']?\s*:\s*\[([^\]]+)\]', array_content, re.IGNORECASE)
                        if left_match:
                            values = [v.strip().strip('"\'') for v in left_match.group(1).split(',')]
                            level_1_custom_properties['enable-menu-item-in-left[]'] = [v for v in values if v]
                            print(f"[XML Processor] Extracted enable-menu-item-in-left[]: {level_1_custom_properties['enable-menu-item-in-left[]']}")
                        
                        right_match = re.search(r'["\']enable-menu-item-in-right\s*\[\s*\]["\']?\s*:\s*\[([^\]]+)\]', array_content, re.IGNORECASE)
                        if right_match:
                            values = [v.strip().strip('"\'') for v in right_match.group(1).split(',')]
                            level_1_custom_properties['enable-menu-item-in-right[]'] = [v for v in values if v]
                            print(f"[XML Processor] Extracted enable-menu-item-in-right[]: {level_1_custom_properties['enable-menu-item-in-right[]']}")
                        
                        if menu_component_name:
                            if level_1_custom_properties:
                                print(f"[XML Processor] Extracted custom properties from XML (regex): {level_1_custom_properties}")
                            break
                except Exception as e:
                    print(f"[XML Processor] Error parsing menu JSON: {e}", file=sys.stderr)
            else:
                print(f"[XML Processor] No mainMenu JSON pattern found in automation guide content")
            
            # Fallback: Try simple pattern for menu component name
            main_menu_pattern = r'Main\s*Menu:\s*(.+)$'
            match = re.search(main_menu_pattern, decoded_content, re.IGNORECASE | re.DOTALL)
            if match:
                menu_component_name = match.group(1).strip()
                menu_component_name = re.sub(r'[\n\r]+', ' ', menu_component_name)
                menu_component_name = re.sub(r'\s+', ' ', menu_component_name).strip()
                break
    
    # Use defaults if not found
    if not menu_component_name:
        menu_component_name = "Main Menu"
        print("[XML Processor] Menu component name not found in automation guide. Using default: 'Main Menu'")
    
    if menu_level is None:
        menu_level = 0
    
    if not level_1_custom_properties:
        print("[XML Processor] No custom properties found in XML - will use empty dict")
    
    return menu_component_name, menu_level, level_1_custom_properties


def create_simplified_page_name_json(home_data, foot_unknown_data, nav_data):
    """
    Creates a simplified JSON focused on page names and extracted components from the navigation map.
    """
    simplified_data = {
        "title": nav_data.get("title") or "Untitled Navigation Sitemap",
        "pages": []
    }

    def simplify_page(page_dict):
        # Extract components using the dedicated function
        components = extract_component_names(page_dict.get("content_blocks", ""))

        simplified_page = {
            "page_name": page_dict["text"],
            "components": components,
            "meta_info": page_dict.get("meta_info", {}),
            "sub_pages": []
        }

        for child in page_dict["children"]:
            simplified_page["sub_pages"].append(simplify_page(child))

        return simplified_page

    all_pages_combined = nav_data["pages"]

    for page in all_pages_combined:
        simplified_data["pages"].append(simplify_page(page))

    return simplified_data


def create_home_simplified_page_name_json(home_data: dict) -> dict:
    """
    Creates a simplified JSON structure specifically for the home page.
    This extracts only the home page from home_data and sets it as level 0.
    """
    simplified_data = {
        "title": home_data.get("title") or "Home Page",
        "pages": []
    }

    def simplify_home_page(page_dict):
        """Simplifies a single home page entry."""
        # Extract components using the dedicated function
        components = extract_component_names(page_dict.get("content_blocks", ""))

        simplified_page = {
            "page_name": page_dict.get("text", "Home Page"),
            "level": 0,  # Home page is always level 0
            "components": components,
            "meta_info": page_dict.get("meta_info", {}),
            "sub_pages": []  # Home page sub-pages are handled separately in inner pages
        }

        return simplified_page

    # Process only the first page from home_data (should be the home page)
    home_pages = home_data.get("pages", [])
    if home_pages:
        # Take the first page as the home page
        home_page = home_pages[0]
        simplified_data["pages"].append(simplify_home_page(home_page))
    else:
        # If no pages found, create a default home page structure
        print("[XML Processor] WARNING: No pages found in home_data, creating default home page structure")
        simplified_data["pages"].append({
            "page_name": "Home Page",
            "level": 0,
            "components": [],
            "meta_info": {},
            "sub_pages": []
        })

    return simplified_data


# ------------------------------------------------------------------
# 🏃 Main Step Function (Name MUST match the 'module' key in config.py)
# ------------------------------------------------------------------

def run_xml_processing_step(filepath: str, step_config: dict, previous_step_data: dict = None) -> dict:
    """
    Executes the XML parsing, data structuring, JSON file generation, and saves the file_prefix 
    and output filenames to the persistent config for subsequent steps.
    """
    time.sleep(step_config["delay"] / 2)

    # --- Setup File Paths ---
    
    # 1. Get the full basename (e.g., 'UUID_OriginalFilename.xml')
    full_basename_with_ext = os.path.basename(filepath)
    
    # 2. Remove the extension (e.g., 'UUID_OriginalFilename')
    full_basename = full_basename_with_ext.rsplit('.', 1)[0]

    # 3. Extract only the UUID part (the unique token) before the first underscore.
    # This ensures that the generated config and JSON files only use the short UUID 
    # as the prefix, as requested.
    file_prefix = full_basename.split('_', 1)[0]
    
    # Fallback in case of unexpected format (e.g., no underscore)
    if not file_prefix:
        file_prefix = full_basename
    
    # All output files now use the simplified, UUID-only file_prefix
    home_json_file = os.path.join(UPLOAD_FOLDER, f"{file_prefix}_home_pages.json")
    foot_unk_json_file = os.path.join(UPLOAD_FOLDER, f"{file_prefix}_footer_unknown_pages.json")
    util_json_file = os.path.join(UPLOAD_FOLDER, f"{file_prefix}_util_pages.json")
    simplified_json_file = os.path.join(UPLOAD_FOLDER, f"{file_prefix}_simplified.json")
    home_simplified_json_file = os.path.join(UPLOAD_FOLDER, f"{file_prefix}_home_simplified.json")
    
    # --- Execute Core Logic ---
    try:
        # Call the core parsing function
        home_sitemap_data, foot_unknown_sitemap_data, util_sitemap_data, nav_sitemap_data = parse_sleekplan_xml(filepath)

        if not nav_sitemap_data["pages"] and not foot_unknown_sitemap_data["pages"] and not util_sitemap_data["pages"]:
            # If all maps are empty, raise an error
            raise Exception("XML parsing resulted in entirely empty data structures. Please check the XML content.")

        # Save all generated JSON files
        with open(home_json_file, 'w', encoding='utf-8') as f:
            json.dump(home_sitemap_data, f, ensure_ascii=False, indent=4)
        with open(foot_unk_json_file, 'w', encoding='utf-8') as f:
            json.dump(foot_unknown_sitemap_data, f, ensure_ascii=False, indent=4)
        with open(util_json_file, 'w', encoding='utf-8') as f:
            json.dump(util_sitemap_data, f, ensure_ascii=False, indent=4)

        # Create and save the simplified data for inner pages
        simplified_data = create_simplified_page_name_json(
            home_sitemap_data, foot_unknown_sitemap_data, nav_sitemap_data
        )
        with open(simplified_json_file, 'w', encoding='utf-8') as f:
            json.dump(simplified_data, f, ensure_ascii=False, indent=4)
        
        # Create and save the simplified data specifically for the home page
        home_simplified_data = create_home_simplified_page_name_json(home_sitemap_data)
        with open(home_simplified_json_file, 'w', encoding='utf-8') as f:
            json.dump(home_simplified_data, f, ensure_ascii=False, indent=4)
        print(f"[XML Processor] Created home page simplified JSON: {os.path.basename(home_simplified_json_file)}")
            
        # --- Extract menu properties from util pages and prepare for config ---
        menu_component_name, menu_level, level_1_custom_properties = extract_menu_properties_from_util_pages(util_sitemap_data)
        
        print(f"[XML Processor] Menu properties extracted:")
        print(f"  - Component Name: {menu_component_name}")
        print(f"  - Menu Level: {menu_level}")
        print(f"  - Custom Properties: {level_1_custom_properties if level_1_custom_properties else 'None (empty dict)'}")
            
        # --- Prepare output file list ---
        output_filenames_list = [
            os.path.basename(home_json_file),
            os.path.basename(foot_unk_json_file),
            os.path.basename(util_json_file),
            os.path.basename(simplified_json_file),
        ]
            
        # --- Save file_prefix, output filenames, and menu properties to Config for future steps ---
        settings = load_settings(file_prefix)
        if settings is None:
            raise RuntimeError("Failed to initialize or load config storage during XML processing.")

        settings["file_prefix"] = file_prefix 
        settings["output_json_filenames"] = output_filenames_list
        settings["menu_component_name"] = menu_component_name
        settings["menu_level"] = menu_level
        settings["level_1_custom_properties"] = level_1_custom_properties if level_1_custom_properties else {}
        
        if not save_settings(file_prefix, settings):
            raise IOError("Failed to save the file_prefix, output filenames, and menu properties to the configuration file.")
        
        print(f"[XML Processor] Configuration file updated successfully with menu properties")


    except ET.ParseError as e:
        # Catch XML-specific errors
        raise Exception(f"XML Parsing Error: The uploaded file may be corrupt or malformed. Details: {e}")
    except Exception as e:
        # Catch any other runtime errors
        raise Exception(f"An unexpected error occurred during XML transformation: {e}")

    time.sleep(step_config["delay"] / 2) 

    # Return the file names for the final download list AND the file_prefix for the next step
    return {
        "output_files": output_filenames_list, # Return the same list of basenames
        "message": "Successfully generated 4 JSON output files and updated the configuration.",
        "file_prefix": file_prefix # MANDATORY return for next step's previous_step_data
    }