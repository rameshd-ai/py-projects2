import time
import os
import json
import random
import xml.etree.ElementTree as ET
import re
import html
import copy
from typing import List, Dict, Generator, Any, Tuple, Set

# --- Configuration Constants (UNCHANGED) ---
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'xml'}

# Define the processing steps.
PROCESSING_STEPS: List[Dict[str, Any]] = [
    {"id": "process_xml", "name": "Processing XML and Generating JSON Structures", "delay": 2.5, "error_chance": 0.00}, 
    {"id": "processed", "name": "Processed and Archiving Cleanup", "delay": 1.0, "error_chance": 0.00},
]

# ------------------------------------------------------------------
# 🛠️ XML/HTML Utility Functions (FIXED: extract_meta_info uses targeted regex)
# ------------------------------------------------------------------

def aggressively_unescape_and_clean(content):
    """Repeatedly unescapes HTML entities and cleans residual HTML structure."""
    unescaped = html.unescape(content)
    unescaped = html.unescape(unescaped)
    cleanr = re.compile(r'<(?!strong|/strong)[^>]*?>')
    clean_text = re.sub(cleanr, '\n', unescaped).strip()
    clean_text = clean_text.replace('&nbsp;', ' ').replace('&amp;nbsp;', ' ')
    clean_text = re.sub(r'(\n|\s)+', '\n', clean_text).strip()
    return clean_text

def clean_html(raw_html):
    """Cleans up escaped HTML content for simpler fields like 'description'."""
    cleanr = re.compile(r'<.*?>|&lt;.*?&gt;|&amp;nbsp;|&lt;br&gt;')
    text = raw_html.replace('&amp;', '&').replace('&quot;', '"')
    clean_text = re.sub(cleanr, '\n', text).strip()
    clean_text = re.sub(r'(\n|\s)+', '\n', clean_text).strip()
    return clean_text

def extract_component_names(clean_html_content):
    """Extracts components STRICTLY from text inside <strong> tags."""
    if not clean_html_content: return []
    ordered_components = []
    seen_components = set()
    content_area = re.split(r'PageInfoBlock', clean_html_content, 1)[0] 
    
    strong_tag_pattern = re.compile(r'<strong>(.*?)</strong>', re.IGNORECASE | re.DOTALL)
    
    for match in strong_tag_pattern.finditer(content_area):
        component_text = match.group(1).strip()
        component_text = re.sub(r'[\n\t]', ' ', component_text)
        component_text = re.sub(r'\s+', ' ', component_text)
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
    
    # Define the keys to search for and their corresponding dict keys
    target_keys = {
        "PageTemplateName": "PageTemplateName",
        "Default Title": "DefaultTitle",
        "Default Description": "DefaultDescription"
    }

    # Pattern explanation:
    # (?<=Key:)    - Positive Lookbehind: ensures we start matching only after "Key:"
    # \s* - Matches optional whitespace
    # (.*?)        - Captures the value (non-greedy)
    # (?=<|$)      - Positive Lookahead: ensures we stop before the next HTML tag (<) or the end of the string ($)
    for xml_key, dict_key in target_keys.items():
        # Create a specific regex pattern for the current key
        # Use re.IGNORECASE for robustness, and re.DOTALL to allow matching across lines/tags if necessary
        # The key in the regex is escaped to handle potential characters in "Default Title" etc.
        pattern = re.compile(r'(?<=' + re.escape(xml_key) + r':)\s*(.*?)(?=<|$)', re.IGNORECASE | re.DOTALL)
        
        match = pattern.search(meta_block)
        
        if match:
            value = match.group(1).strip()
            # Clean up residual newlines or extra spaces that might be left by tags
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
        root = ET.fromstring(wrapped_content)
        
        clean_blocks = []
        for child in root:
            block_content = ET.tostring(child, encoding='unicode', method='html')
            clean_blocks.append(block_content)
            
        clean_html_string = "\n---\n".join(clean_blocks).strip()
        
        return content, clean_html_string 
        
    except ET.ParseError:
        clean_html_string = aggressively_unescape_and_clean(content)
        return content, clean_html_string
    except Exception:
        return content, aggressively_unescape_and_clean(content)


# --- Core XML to JSON Functions (UNCHANGED) ---

def build_tree(all_cells: Dict[str, Any], root_ids: Set[str], title: str, link: str):
    sitemap_data = {"title": title, "link": link, "pages": []}
    if not all_cells or not root_ids: return sitemap_data

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
            built_child = recursive_build(child["id"])
            if built_child:
                page["children"].append(built_child)

            if child["id"] in id_to_cell:
                id_to_cell.pop(child["id"])

        return page

    for page in root_pages_list:
        if page["id"] in id_to_cell:
            sitemap_data["pages"].append(recursive_build(page["id"]))
            id_to_cell.pop(page["id"])

    def remove_temp_keys(p):
        p.pop("parent_id", None)
        p.pop("order", None)
        for child in p["children"]: remove_temp_keys(child)

    for page in sitemap_data["pages"]:
        remove_temp_keys(page)

    return sitemap_data


def get_all_descendants(start_id: str, all_cells: Dict[str, Any]) -> Set[str]:
    descendants = set()
    to_visit = [start_id]

    while to_visit:
        current_id = to_visit.pop(0)

        children = [
            cell_id for cell_id, data in all_cells.items()
            if data.get("parent_id") == current_id and cell_id not in descendants
        ]

        for child_id in children:
            descendants.add(child_id)
            to_visit.append(child_id)

    return descendants


def parse_sleekplan_xml(xml_file_path: str) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
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
            "content_blocks": component_content,
            "meta_info": page_meta_info, 
            "children": []
        }
        all_cells[cell_id] = cell_data

        if cell_data["level"] == 'home':
            home_page_id = cell_id

    home_root_ids = {home_page_id} if home_page_id else set()
    
    nav_root_ids = {
        cell_id for cell_id, data in all_cells.items()
        if data["level"] == '1' and data.get("parent_id") is None
    }
    nav_tree_ids = set()
    for root_id in nav_root_ids:
        nav_tree_ids.add(root_id)
        nav_tree_ids.update(get_all_descendants(root_id, all_cells))
        
    all_cells_nav = {cell_id: all_cells[cell_id] for cell_id in nav_tree_ids}
    
    foot_unk_root_ids = {
        cell_id for cell_id, data in all_cells.items()
        if data["level"] in ['foot', 'unknown'] and cell_id not in nav_tree_ids
    }
    util_root_ids = {
        cell_id for cell_id, data in all_cells.items()
        if data["level"] == 'util' and cell_id not in nav_tree_ids
    }

    home_sitemap_data = build_tree(all_cells, home_root_ids, title_text, link_text)
    foot_unknown_sitemap_data = build_tree(all_cells, foot_unk_root_ids, title_text, link_text)
    util_sitemap_data = build_tree(all_cells, util_root_ids, title_text, link_text)
    nav_sitemap_data = build_tree(all_cells_nav, nav_root_ids, title_text, link_text)

    return home_sitemap_data, foot_unknown_sitemap_data, util_sitemap_data, nav_sitemap_data


def create_simplified_page_name_json(home_data, foot_unknown_data, nav_data):
    """
    Creates the SIMPLIFIED JSON using ONLY NAVIGATION data, including components and meta_info.
    """
    simplified_data = {
        "title": nav_data.get("title") or "Untitled Navigation Sitemap",
        "pages": []
    }

    def simplify_page(page_dict):
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


# --- SSE Logic (UNCHANGED) ---

def allowed_file(filename: str) -> bool:
    """Checks if a file extension is allowed."""
    return '.' in filename and \
            filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def format_sse(data: Dict[str, Any], event: str = 'message') -> str:
    """Formats a dictionary into a Server-Sent Event stream string."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"

def generate_progress_stream(filepath: str) -> Generator[str, None, None]:
    step_id = 'initial'
    home_sitemap_data = None
    foot_unknown_sitemap_data = None
    util_sitemap_data = None
    nav_sitemap_data = None

    base_name = os.path.basename(filepath).rsplit('.', 1)[0]
    home_json_file = os.path.join(UPLOAD_FOLDER, f"{base_name}_home_pages.json")
    foot_unk_json_file = os.path.join(UPLOAD_FOLDER, f"{base_name}_footer_unknown_pages.json")
    util_json_file = os.path.join(UPLOAD_FOLDER, f"{base_name}_util_pages.json")
    simplified_json_file = os.path.join(UPLOAD_FOLDER, f"{base_name}_simplified.json")

    try:
        yield format_sse({"status": "start", "message": "Processing started..."}, event='update')

        for step in PROCESSING_STEPS:
            step_id = step["id"]
            step_name = step["name"]
            delay = step["delay"]
            error_chance = step["error_chance"]

            yield format_sse({
                "status": "in_progress",
                "step_id": step_id,
                "message": f"Step **'{step_name}'** is now in progress..."
            }, event='update')

            if step_id == 'process_xml':
                time.sleep(delay / 2) 

                if random.random() < error_chance:
                    raise Exception(f"Simulated failure during: {step_name}")

                try:
                    home_sitemap_data, foot_unknown_sitemap_data, util_sitemap_data, nav_sitemap_data = parse_sleekplan_xml(filepath)
                except ET.ParseError as e:
                    raise Exception(f"XML Parsing Error: The uploaded file may be corrupt or malformed. Error details: {e}")
                except Exception as e:
                    raise Exception(f"An unexpected error occurred during XML transformation: {e}")

                if not nav_sitemap_data["pages"] and not foot_unknown_sitemap_data["pages"] and not util_sitemap_data["pages"]:
                    raise Exception("XML parsing resulted in entirely empty data structures for the desired outputs.")

                with open(home_json_file, 'w', encoding='utf-8') as f:
                    json.dump(home_sitemap_data, f, ensure_ascii=False, indent=4)
                with open(foot_unk_json_file, 'w', encoding='utf-8') as f:
                    json.dump(foot_unknown_sitemap_data, f, ensure_ascii=False, indent=4)
                with open(util_json_file, 'w', encoding='utf-8') as f:
                    json.dump(util_sitemap_data, f, ensure_ascii=False, indent=4)

                simplified_data = create_simplified_page_name_json(
                    home_sitemap_data,
                    foot_unknown_sitemap_data,
                    nav_sitemap_data
                )
                with open(simplified_json_file, 'w', encoding='utf-8') as f:
                    json.dump(simplified_data, f, ensure_ascii=False, indent=4)

                time.sleep(delay / 2)

            elif step_id == 'processed':
                time.sleep(delay)
                if random.random() < error_chance:
                    raise Exception(f"Simulated failure during: {step_name}")

            yield format_sse({
                "status": "done",
                "step_id": step_id,
                "message": f"Step **'{step_name}'** successfully completed."
            }, event='update')

        final_message = f"Processing complete. Four JSON files generated in the `{UPLOAD_FOLDER}` folder. Downloads are not enabled."

        yield format_sse({
            "status": "complete",
            "message": final_message,
        }, event='update')

    except Exception as e:
        yield format_sse({
            "status": "error",
            "message": f"Processing failed: {str(e)}",
            "step_id": step_id
        }, event='update')

    finally:
        if os.path.exists(filepath):
            os.remove(filepath)
        yield format_sse({"status": "close"}, event='update')