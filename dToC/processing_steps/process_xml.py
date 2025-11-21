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
# 🛠️ CONFIG UTILITY FUNCTIONS (Added for file persistence)
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
# 🛠️ XML/HTML Utility Functions (MOVED from original config_and_logic.py)
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


def extract_meta_info(raw_html_content: str) -> Dict[str, Any]:
    """
    Extracts PageTemplateName, DefaultTitle, and DefaultDescription using targeted regex 
    on the triple-unescaped block following 'PageInfoBlock'.
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
        return meta_info

    meta_block = parts[1]
    
    target_keys = {
        "PageTemplateName": "PageTemplateName",
        "Default Title": "DefaultTitle",
        "Default Description": "DefaultDescription"
    }

    for xml_key, dict_key in target_keys.items():
        # Regex to find text following the key until the next key or end of block
        pattern = re.compile(r'(?<=' + re.escape(xml_key) + r':)\s*(.*?)(?=<|$)', re.IGNORECASE | re.DOTALL)
        
        match = pattern.search(meta_block)
        
        if match:
            value = match.group(1).strip()
            # Normalize whitespace
            value = re.sub(r'[\r\n\s]+', ' ', value).strip() 
            
            if value:
                meta_info[dict_key] = value
                
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

    title_text = root.find('title').text.replace('&amp;', '&') if root.find('title') is not None else "Untitled Sitemap"
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
            "text": cell.find('text').text.replace('&amp;', '&') if cell.find('text') is not None else "Untitled",
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

        # Create and save the simplified data
        simplified_data = create_simplified_page_name_json(
            home_sitemap_data, foot_unknown_sitemap_data, nav_sitemap_data
        )
        with open(simplified_json_file, 'w', encoding='utf-8') as f:
            json.dump(simplified_data, f, ensure_ascii=False, indent=4)
            
        # --- Prepare output file list ---
        output_filenames_list = [
            os.path.basename(home_json_file),
            os.path.basename(foot_unk_json_file),
            os.path.basename(util_json_file),
            os.path.basename(simplified_json_file),
        ]
            
        # --- Save file_prefix (the unique token) and all output filenames to Config for future steps ---
        settings = load_settings(file_prefix)
        if settings is None:
            raise RuntimeError("Failed to initialize or load config storage during XML processing.")

        settings["file_prefix"] = file_prefix 
        settings["output_json_filenames"] = output_filenames_list # <-- Added all output filenames
        
        if not save_settings(file_prefix, settings):
            raise IOError("Failed to save the file_prefix and output filenames to the configuration file.")


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