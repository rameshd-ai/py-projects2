#!/usr/bin/env python3
"""
Quick script to fetch and display available page categories from the API.
This helps identify what category "Home Page" should match to.
"""
import json
import sys
import os

# Add parent directory to path to import apis
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from apis import GetPageCategoryList

def normalize_page_name(name: str) -> str:
    """Normalize page name for matching (same as in process_assembly.py)"""
    import re
    if not name:
        return ""
    normalized = name.strip().lower()
    normalized = re.sub(r'[^a-z0-9]', '', normalized)
    return normalized

def main():
    # Try to load config from the most recent upload
    uploads_dir = os.path.join(os.path.dirname(__file__), "uploads")
    config_files = [f for f in os.listdir(uploads_dir) if f.endswith("_config.json")]
    
    if not config_files:
        print("No config files found. Please run the main processing first.")
        return
    
    # Get the most recent config file
    latest_config = sorted(config_files)[-1]
    config_path = os.path.join(uploads_dir, latest_config)
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    api_base_url = config.get("api_base_url")
    token = config.get("token")
    
    if not api_base_url or not token:
        print("Config file missing api_base_url or token")
        return
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    print(f"\n{'='*80}")
    print("Fetching Page Categories from API...")
    print(f"{'='*80}\n")
    
    categories = GetPageCategoryList(api_base_url, headers)
    
    if isinstance(categories, dict) and categories.get("error"):
        print(f"ERROR: {categories.get('details')}")
        return
    
    print(f"Found {len(categories)} categories:\n")
    
    # Show all categories
    for i, cat in enumerate(categories, 1):
        cat_id = cat.get("CategoryId", "N/A")
        cat_name = cat.get("CategoryName", "N/A")
        normalized = normalize_page_name(cat_name)
        print(f"{i:3d}. ID: {cat_id:6s} | Name: {cat_name:40s} | Normalized: {normalized}")
    
    # Check for "Home Page" match
    print(f"\n{'='*80}")
    print("Checking for 'Home Page' match...")
    print(f"{'='*80}\n")
    
    home_page_normalized = normalize_page_name("Home Page")
    print(f"Normalized 'Home Page': '{home_page_normalized}'\n")
    
    matches = []
    for cat in categories:
        cat_name = cat.get("CategoryName", "")
        if cat_name and normalize_page_name(cat_name) == home_page_normalized:
            matches.append(cat)
            print(f"✓ MATCH FOUND!")
            print(f"  Category ID: {cat.get('CategoryId')}")
            print(f"  Category Name: {cat_name}")
            print(f"  Normalized: {normalize_page_name(cat_name)}\n")
    
    if not matches:
        print("✗ No exact match found for 'Home Page'")
        print("\nSimilar category names (for reference):")
        similar = []
        for cat in categories:
            cat_name = cat.get("CategoryName", "")
            if cat_name and ("home" in cat_name.lower() or "page" in cat_name.lower()):
                similar.append(cat)
        
        if similar:
            for cat in similar[:10]:  # Show first 10 similar
                print(f"  - {cat.get('CategoryName')} (ID: {cat.get('CategoryId')})")
        else:
            print("  (No similar category names found)")
    
    print(f"\n{'='*80}\n")

if __name__ == "__main__":
    main()

