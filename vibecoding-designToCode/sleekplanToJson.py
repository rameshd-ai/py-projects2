import xml.etree.ElementTree as ET
import json
import os
import re

def clean_html(raw_html):
    """
    Cleans up the escaped HTML content within the <content> tags by removing
    HTML tags and decoding common entities.
    """
    # Pattern to match HTML tags and escaped entities like &lt;p&gt;
    cleanr = re.compile(r'<.*?>|&lt;.*?&gt;|&amp;nbsp;|&lt;br&gt;')
    
    # Unescape common HTML entities (&amp; to &, &quot; to ")
    text = raw_html.replace('&amp;', '&').replace('&quot;', '"')
    
    # Remove HTML tags and entities, replacing them with a newline
    clean_text = re.sub(cleanr, '\n', text).strip()
    
    # Replace multiple newlines/spaces with a single newline for clean formatting
    clean_text = re.sub(r'(\n|\s)+', '\n', clean_text).strip()
    
    return clean_text

def parse_sleekplan_xml_excluding_util(xml_file_path):
    """
    Reads a Sleekplan XML file and converts its cells into a hierarchical JSON structure,
    excluding only pages where level="util". Home, Main Nav (Level 1), and Footer (foot) 
    pages are included and strictly ordered.
    """
    if not os.path.exists(xml_file_path):
        print(f"Error: XML file not found at '{xml_file_path}'")
        return None

    try:
        tree = ET.parse(xml_file_path)
        root = tree.getroot()
    except Exception as e:
        print(f"Error parsing XML file: {e}")
        return None

    title_element = root.find('title')
    sitemap_data = {
        "title": title_element.text.replace('&amp;', '&') if title_element is not None else "Untitled Sitemap",
        "link": root.find('link').text if root.find('link') is not None else None,
        "pages": []
    }
    
    # 1. Extract all cell data into a flat dictionary
    all_cells = {}
    
    cells_element = root.find('.//cells') 
    if cells_element is None:
        print("Warning: Could not find the <cells> element in the XML.")
        return sitemap_data

    for cell in cells_element.findall('cell'):
        cell_id = cell.get('id')
        
        # We skip any cell that is level="util" immediately
        if cell.find('level').text == 'util':
            continue 
            
        # Extract and clean content blocks
        content_list = []
        for contents in cell.findall('.//contents/body/wysiwyg'):
            content = contents.find('content')
            if content is not None and content.text:
                content_list.append(clean_html(content.text))
        
        # Clean up the <desc> tag if present
        desc = cell.find('desc')
        clean_desc = clean_html(desc.text) if desc is not None and desc.text else None
        
        all_cells[cell_id] = {
            "id": cell_id,
            "text": cell.find('text').text.replace('&amp;', '&') if cell.find('text') is not None else "Untitled",
            "order": int(cell.find('order').text) if cell.find('order') is not None else 9999,
            "level": cell.find('level').text if cell.find('level') is not None else 'unknown',
            "parent_id": cell.find('parent').text if cell.find('parent') is not None else None,
            "description": clean_desc,
            "content_blocks": "\n---\n".join(content_list).strip(),
            "children": []
        }
        
    # 2. Identify and sort top-level pages
    
    valid_parent_ids = set(all_cells.keys())
    
    home_page = None
    main_nav_pages = [] 
    footer_pages = [] 
    
    for cell_id, data in all_cells.items():
        is_root_level = data["parent_id"] is None or data["parent_id"] not in valid_parent_ids

        if is_root_level:
            if data["level"] == 'home':
                home_page = data
            elif data["level"] == '1':
                main_nav_pages.append(data)
            elif data["level"] in ['foot', 'unknown']: # Only 'util' is excluded
                footer_pages.append(data)
            
    # Sort the main navigation pages by <order>
    main_nav_sorted = sorted(main_nav_pages, key=lambda x: x["order"])
    
    # Sort the footer pages by <order>
    footer_sorted = sorted(footer_pages, key=lambda x: x["order"])
    
    # 3. Define the recursive tree builder (unchanged)
    id_to_cell = {cell_id: data for cell_id, data in all_cells.items()}

    def build_tree(page_id):
        """Recursively finds and attaches children, sorted by <order>."""
        page = id_to_cell[page_id]
        
        # Children are only pages whose parent_id is the current page_id AND 
        # that were not excluded during the initial parsing (i.e., not level='util')
        children = [data for data in all_cells.values() if data["parent_id"] == page_id]
        children_sorted = sorted(children, key=lambda x: x["order"])
        
        for child in children_sorted:
            page["children"].append(build_tree(child["id"]))
            
        return page

    # 4. Final Construction: Build and combine the trees in strict order
    
    # A. Add Home Page FIRST (Level: home)
    if home_page:
        sitemap_data["pages"].append(build_tree(home_page["id"]))

    # B. Add Main Navigation pages (Level: 1)
    for page in main_nav_sorted:
        sitemap_data["pages"].append(build_tree(page["id"]))
        
    # C. Add Footer pages (Level: foot)
    for page in footer_sorted:
        sitemap_data["pages"].append(build_tree(page["id"]))

    # Remove temporary attributes (order and parent_id)
    for page in sitemap_data["pages"]:
        def clean_page(p):
            p.pop("parent_id", None)
            p.pop("order", None)
            for child in p["children"]:
                clean_page(child)
        clean_page(page)

    return sitemap_data

# --- USAGE ---
xml_file = '394279 nationwide hotel conference center 3.0.xml'
json_file = 'sitemap_excluding_util_output.json'

sitemap_json_data = parse_sleekplan_xml_excluding_util(xml_file)

if sitemap_json_data:
    # Save the resulting JSON to a file
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(sitemap_json_data, f, ensure_ascii=False, indent=4)
        
    print(f"\n✅ Successfully generated hierarchical JSON file, excluding only utility pages: '{json_file}'")
else:
    print("\n❌ JSON generation failed. Please check the XML file path and structure.")