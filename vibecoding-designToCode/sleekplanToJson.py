import xml.etree.ElementTree as ET
import json
import os
import re
import html 

# --- Core Utility ---

def aggressively_unescape_and_clean(content):
    """
    Repeatedly unescapes HTML entities to get back to standard HTML tags 
    and then cleans residual HTML structure. This is used to prepare content_blocks.
    """
    unescaped = html.unescape(content)
    unescaped = html.unescape(unescaped)
    
    # Remove structural tags but keep bold/strong tags
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
    """
    FIXED: Extracts components STRICTLY from text inside <strong> tags, 
    and REMOVES the special case for "History/Story".
    """
    if not clean_html_content:
        return []
    
    ordered_components = []
    seen_components = set()
    
    # Regex to find all text inside <strong> tags
    strong_tag_pattern = re.compile(r'<strong>(.*?)</strong>', re.IGNORECASE | re.DOTALL)

    # Find all matches in the content to preserve sequence
    for match in strong_tag_pattern.finditer(clean_html_content):
        component_text = match.group(1).strip()
        
        # 1. Replace ALL internal newlines and tabs with a single space.
        component_text = re.sub(r'[\n\t]', ' ', component_text)
        # 2. Normalize multiple spaces into a single space.
        component_text = re.sub(r'\s+', ' ', component_text)
        
        # Final cleanup for residual HTML/space characters
        final_component = re.sub(r'<[^>]+>|&nbsp;', '', component_text).strip()
        
        # Check if the final component name is not empty and not already seen
        if final_component and final_component not in seen_components:
            ordered_components.append(final_component)
            seen_components.add(final_component)

    # 🛑 HISTORY/STORY SPECIAL CASE REMOVED 🛑
    # Only components found inside <strong> tags are included.

    return ordered_components


# --- 1. Function to create the FULL, DETAILED JSON (Excluding 'util') ---

def parse_sleekplan_xml_excluding_util(xml_file_path):
    if not os.path.exists(xml_file_path): return None
    try: tree = ET.parse(xml_file_path); root = tree.getroot()
    except Exception as e: print(f"Error parsing XML: {e}"); return None

    title_element = root.find('title')
    sitemap_data = {"title": title_element.text.replace('&amp;', '&') if title_element is not None else "Untitled Sitemap", "link": root.find('link').text if root.find('link') is not None else None, "pages": []}
    
    all_cells = {}; cells_element = root.find('.//cells') 
    if cells_element is None: return sitemap_data

    for cell in cells_element.findall('cell'):
        cell_id = cell.get('id')
        cell_level = cell.find('level').text if cell.find('level') is not None else 'unknown'
        if cell_level == 'util': continue 
            
        content_list_cleaned = [] 

        for contents in cell.findall('.//contents/body/wysiwyg'):
            content = contents.find('content')
            if content is not None and content.text:
                cleaned_content = aggressively_unescape_and_clean(content.text)
                content_list_cleaned.append(cleaned_content) 
        
        desc = cell.find('desc'); 
        clean_desc = clean_html(desc.text) if desc is not None and desc.text else None
        
        all_cells[cell_id] = {
            "id": cell_id, 
            "text": cell.find('text').text.replace('&amp;', '&') if cell.find('text') is not None else "Untitled", 
            "order": int(cell.find('order').text) if cell.find('order') is not None else 9999, 
            "level": cell_level, 
            "parent_id": cell.find('parent').text if cell.find('parent') is not None else None, 
            "description": clean_desc, 
            "content_blocks": "\n---\n".join(content_list_cleaned).strip(), 
            "children": []
        }
        
    valid_parent_ids = set(all_cells.keys()); home_page = None; main_nav_pages = []; footer_pages = [] 
    
    for cell_id, data in all_cells.items():
        is_root_level = data["parent_id"] is None or data["parent_id"] not in valid_parent_ids
        if is_root_level:
            if data["level"] == 'home': home_page = data
            elif data["level"] == '1': main_nav_pages.append(data)
            elif data["level"] in ['foot', 'unknown']: footer_pages.append(data)
            
    main_nav_sorted = sorted(main_nav_pages, key=lambda x: x["order"]); footer_sorted = sorted(footer_pages, key=lambda x: x["order"])
    id_to_cell = {cell_id: data for cell_id, data in all_cells.items()}

    def build_tree(page_id):
        page = id_to_cell[page_id]
        children = [data for data in all_cells.values() if data["parent_id"] == page_id]
        children_sorted = sorted(children, key=lambda x: x["order"])
        for child in children_sorted: page["children"].append(build_tree(child["id"]))
        return page

    if home_page: sitemap_data["pages"].append(build_tree(home_page["id"]))
    for page in main_nav_sorted: sitemap_data["pages"].append(build_tree(page["id"]))
    for page in footer_sorted: sitemap_data["pages"].append(build_tree(page["id"]))

    def remove_temp_keys(p):
        p.pop("parent_id", None)
        p.pop("order", None)
        for child in p["children"]:
            remove_temp_keys(child)

    for page in sitemap_data["pages"]:
        remove_temp_keys(page)

    return sitemap_data

# --- 2. Function to create the SIMPLIFIED, PAGE NAME JSON (with Components) ---

def create_simplified_page_name_json(full_sitemap_data_copy):
    """
    Takes the full sitemap dictionary and recursively simplifies it, 
    using 'content_blocks' (now clean HTML) for component extraction.
    """
    simplified_data = {
        "title": full_sitemap_data_copy["title"],
        "pages": []
    }
    
    def simplify_page(page_dict):
        components = extract_component_names(page_dict.get("content_blocks", ""))
        
        simplified_page = {
            "page_name": page_dict["text"],
            "components": components, 
            "sub_pages": []
        }
        
        for child in page_dict["children"]:
            simplified_page["sub_pages"].append(simplify_page(child))
            
        return simplified_page
    
    for page in full_sitemap_data_copy["pages"]:
        simplified_data["pages"].append(simplify_page(page))
        
    return simplified_data

# --- USAGE / MAIN EXECUTION ---

xml_file = 'sleekplan_sitemap.xml'
full_json_file = 'sitemap_excluding_util_output.json'
simplified_json_file = 'sitemap_page_names_components_only.json' 

print(f"Starting sitemap processing for two JSON files from '{xml_file}'...")

# 1. Generate the full, hierarchical data with clean HTML in content_blocks
full_sitemap_data_raw = parse_sleekplan_xml_excluding_util(xml_file)

if full_sitemap_data_raw:
    # 2. Save the full JSON (sitemap_excluding_util_output.json)
    full_output_for_saving = json.loads(json.dumps(full_sitemap_data_raw)) 

    with open(full_json_file, 'w', encoding='utf-8') as f:
        json.dump(full_output_for_saving, f, ensure_ascii=False, indent=4)
        
    print(f"\n✅ Step 1: Successfully generated Full Detail JSON with CLEAN HTML in 'content_blocks': '{full_json_file}'")

    # 3. Generate the simplified page names and components JSON 
    simplified_data = create_simplified_page_name_json(json.loads(json.dumps(full_sitemap_data_raw)))

    # 4. Save the simplified JSON (sitemap_page_names_components_only.json)
    with open(simplified_json_file, 'w', encoding='utf-8') as f:
        json.dump(simplified_data, f, ensure_ascii=False, indent=4)
        
    print(f"✅ Step 2: Successfully generated Simplified JSON (page names + components) using the clean content: '{simplified_json_file}'")

else:
    print("\n❌ JSON generation failed. Could not process XML file.")