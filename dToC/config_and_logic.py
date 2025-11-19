import time
import os
import json
import random
import xml.etree.ElementTree as ET
import re
import html
import copy
from typing import List, Dict, Generator, Any, Tuple, Set

# --- Configuration Constants ---
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'xml'}

# Define the processing steps. (Updated to guarantee success for the final step)
PROCESSING_STEPS: List[Dict[str, Any]] = [
    # Consolidated all complex parsing, saving, and the original validation/transform steps here
    # Retained small error chance for the main processing block
    {"id": "process_xml", "name": "Processing XML and Generating JSON Structures", "delay": 2.5, "error_chance": 0.05},
    # Final step - SET error_chance to 0.00 to guarantee success for archiving/cleanup
    {"id": "processed", "name": "Processed and Archiving Cleanup", "delay": 1.0, "error_chance": 0.00},
]

# --- XML/HTML Utility Functions ---

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
    strong_tag_pattern = re.compile(r'<strong>(.*?)</strong>', re.IGNORECASE | re.DOTALL)
    for match in strong_tag_pattern.finditer(clean_html_content):
        component_text = match.group(1).strip()
        component_text = re.sub(r'[\n\t]', ' ', component_text)
        component_text = re.sub(r'\s+', ' ', component_text)
        final_component = re.sub(r'<[^>]+>|&nbsp;', '', component_text).strip()
        if final_component and final_component not in seen_components:
            ordered_components.append(final_component)
            seen_components.add(final_component)
    return ordered_components


# --- Core XML to JSON Functions (No change) ---

def build_tree(all_cells: Dict[str, Any], root_ids: Set[str], title: str, link: str):
    """
    Builds a hierarchical tree from the full set of cells, filtering only by a set of root IDs.
    The recursion handles all subsequent levels regardless of their 'level' value.
    """
    sitemap_data = {"title": title, "link": link, "pages": []}
    if not all_cells or not root_ids: return sitemap_data

    # Use a copy of the cells we will manipulate (by popping out used children)
    id_to_cell = copy.deepcopy(all_cells)

    # Identify the actual root pages we care about based on the root_ids set
    # Ensure roots exist and are in the current id_to_cell map
    root_pages_list = sorted(
        [data for cell_id, data in id_to_cell.items() if cell_id in root_ids],
        key=lambda x: x["order"]
    )

    # 2. Define the recursive builder
    def recursive_build(page_id):
        # Retrieve the page from the dictionary. If it was removed by its parent, we stop.
        if page_id not in id_to_cell:
            # This should ideally not happen if the root pages are correctly identified
            # and only children are being removed, but is a safeguard.
            return None

        page = id_to_cell[page_id]

        # Find children from the current id_to_cell map (which contains all remaining cells)
        children = [data for data in id_to_cell.values() if data.get("parent_id") == page_id]
        children_sorted = sorted(children, key=lambda x: x["order"])

        for child in children_sorted:
            # Recursively build children and attach
            built_child = recursive_build(child["id"])
            if built_child:
                page["children"].append(built_child)

            # Crucial: remove the child from the map after it's attached (whether successful or not)
            # This is essential to prevent infinite loops or double-counting in shared/unfiltered maps.
            if child["id"] in id_to_cell:
                id_to_cell.pop(child["id"])

        return page

    # 3. Build the tree starting from the roots
    for page in root_pages_list:
        if page["id"] in id_to_cell:
            sitemap_data["pages"].append(recursive_build(page["id"]))
            # Ensure root is popped after processing
            id_to_cell.pop(page["id"])

    # 4. Clean up temporary keys on the resulting output pages
    def remove_temp_keys(p):
        p.pop("parent_id", None)
        p.pop("order", None)
        for child in p["children"]: remove_temp_keys(child)

    for page in sitemap_data["pages"]:
        remove_temp_keys(page)

    return sitemap_data


def get_all_descendants(start_id: str, all_cells: Dict[str, Any]) -> Set[str]:
    """Recursively finds all descendant IDs for a given start ID."""
    descendants = set()
    to_visit = [start_id]

    while to_visit:
        current_id = to_visit.pop(0)

        # Find immediate children of current_id
        children = [
            cell_id for cell_id, data in all_cells.items()
            if data.get("parent_id") == current_id and cell_id not in descendants
        ]

        for child_id in children:
            descendants.add(child_id)
            to_visit.append(child_id)

    return descendants


def parse_sleekplan_xml(xml_file_path: str) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    """
    Parses XML and returns four separate sitemap dictionaries, ensuring the navigation map
    is correctly built using Level 1 pages as roots when the 'home' page is missing.
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

    # 1. Gather all cells
    all_cells = {}; cells_element = root.find('.//cells')
    if cells_element is None:
        empty_data = {"title": title_text, "link": link_text, "pages": []}
        return empty_data, empty_data, empty_data, empty_data

    # Identify the Home Page ID
    home_page_id = None

    for cell in cells_element.findall('cell'):
        cell_id = cell.get('id')
        cell_level = cell.find('level').text if cell.find('level') is not None else 'unknown'

        content_list_cleaned = []
        for contents in cell.findall('.//contents/body/wysiwyg'):
            content = contents.find('content')
            if content is not None and content.text:
                cleaned_content = aggressively_unescape_and_clean(content.text)
                content_list_cleaned.append(cleaned_content)

        desc = cell.find('desc')
        desc_text = desc.text if desc is not None and desc.text else ""
        clean_desc = clean_html(desc_text)

        cell_data = {
            "id": cell_id,
            "text": cell.find('text').text.replace('&amp;', '&') if cell.find('text') is not None else "Untitled",
            "order": int(cell.find('order').text) if cell.find('order') is not None else 9999,
            "level": cell_level,
            "parent_id": cell.find('parent').text if cell.find('parent') is not None else None,
            "description": clean_desc,
            "content_blocks": "\n---\n".join(content_list_cleaned).strip(),
            "children": []
        }
        all_cells[cell_id] = cell_data

        # Find the Home Page by its designated level 'home'
        if cell_data["level"] == 'home':
            home_page_id = cell_id

    # 2. Determine Root IDs for each map

    # Home Page root
    home_root_ids = {home_page_id} if home_page_id else set()

    # Navigation roots are the top-level Level 1 pages
    nav_root_ids = {
        cell_id for cell_id, data in all_cells.items()
        if data["level"] == '1' and data.get("parent_id") is None
    }

    # Determine all IDs that belong to the Navigation Tree (roots + descendants)
    nav_tree_ids = set()
    for root_id in nav_root_ids:
        nav_tree_ids.add(root_id)
        nav_tree_ids.update(get_all_descendants(root_id, all_cells))

    # Create a filtered cell dictionary for the Navigation Tree
    all_cells_nav = {cell_id: all_cells[cell_id] for cell_id in nav_tree_ids}

    # Other map root IDs (pages that are not part of the main navigation tree)
    foot_unk_root_ids = {
        cell_id for cell_id, data in all_cells.items()
        if data["level"] in ['foot', 'unknown'] and cell_id not in nav_tree_ids
    }
    util_root_ids = {
        cell_id for cell_id, data in all_cells.items()
        if data["level"] == 'util' and cell_id not in nav_tree_ids
    }


    # 3. Construct the separate outputs using the build_tree with specific root IDs

    home_sitemap_data = build_tree(all_cells, home_root_ids, title_text, link_text)
    foot_unknown_sitemap_data = build_tree(all_cells, foot_unk_root_ids, title_text, link_text)
    util_sitemap_data = build_tree(all_cells, util_root_ids, title_text, link_text)

    # Use the filtered all_cells_nav for the Navigation tree
    nav_sitemap_data = build_tree(all_cells_nav, nav_root_ids, title_text, link_text)

    return home_sitemap_data, foot_unknown_sitemap_data, util_sitemap_data, nav_sitemap_data


def create_simplified_page_name_json(home_data, foot_unknown_data, nav_data):
    """
    Creates the SIMPLIFIED JSON using ONLY NAVIGATION (Level 1 roots) data.
    """
    simplified_data = {
        "title": nav_data.get("title") or "Untitled Navigation Sitemap",
        "pages": []
    }

    def simplify_page(page_dict):
        # Rely on content_blocks being copied during the build_tree process
        components = extract_component_names(page_dict.get("content_blocks", ""))

        simplified_page = {
            "page_name": page_dict["text"],
            "components": components,
            "sub_pages": []
        }

        for child in page_dict["children"]:
            simplified_page["sub_pages"].append(simplify_page(child))

        return simplified_page

    # Only include the top-level pages found in the nav_data (Level 1 roots and their children)
    all_pages_combined = nav_data["pages"]

    # Process the combined list
    for page in all_pages_combined:
        simplified_data["pages"].append(simplify_page(page))

    return simplified_data


# --- Helper and SSE Logic (MODIFIED) ---

def allowed_file(filename: str) -> bool:
    """Checks if a file extension is allowed."""
    return '.' in filename and \
            filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def format_sse(data: Dict[str, Any], event: str = 'message') -> str:
    """Formats a dictionary into a Server-Sent Event stream string."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"

def generate_progress_stream(filepath: str) -> Generator[str, None, None]:
    """
    Generator function that runs the XML processing and yields SSE progress updates.
    (MODIFIED to use only two main steps, with guaranteed final success.)
    """
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
                time.sleep(delay / 2) # Simulate some initial work

                if random.random() < error_chance:
                    raise Exception(f"Simulated failure during: {step_name}")

                # 1. XML Transformation (formerly 'transform' step)
                try:
                    home_sitemap_data, foot_unknown_sitemap_data, util_sitemap_data, nav_sitemap_data = parse_sleekplan_xml(filepath)
                except ET.ParseError as e:
                    raise Exception(f"XML Parsing Error: The uploaded file may be corrupt or malformed. Error details: {e}")
                except Exception as e:
                    raise Exception(f"An unexpected error occurred during XML transformation: {e}")

                if not nav_sitemap_data["pages"] and not foot_unknown_sitemap_data["pages"] and not util_sitemap_data["pages"]:
                    raise Exception("XML parsing resulted in entirely empty data structures for the desired outputs.")

                # 2. JSON Saving (formerly 'save_home', 'save_foot_unk', 'save_util', 'save_simple' steps)
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

                time.sleep(delay / 2) # Simulate final saving time

            elif step_id == 'processed':
                time.sleep(delay)
                # ERROR CHANCE IS NOW 0.00, so this block will not trigger a failure.
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
            # The original XML file is still cleaned up.
            os.remove(filepath)
        yield format_sse({"status": "close"}, event='update')