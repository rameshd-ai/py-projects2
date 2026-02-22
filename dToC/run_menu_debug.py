#!/usr/bin/env python3
"""
Debug script: Run menu navigation step using existing JSON files.
Uses file_prefix from uploads folder and invokes run_menu_navigation_step.
"""
import os
import sys
import traceback

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# File prefix from existing files in uploads/
FILE_PREFIX = "67c67b2c-8ccf-42fe-b28c-4023ec977a03"
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")


def main():
    xml_path = os.path.join(UPLOAD_FOLDER, f"{FILE_PREFIX}_terranea_2026_1.0_5.xml")
    if not os.path.exists(xml_path):
        # Try first .xml in uploads
        for f in os.listdir(UPLOAD_FOLDER):
            if f.startswith(FILE_PREFIX) and f.endswith(".xml"):
                xml_path = os.path.join(UPLOAD_FOLDER, f)
                break
        else:
            print(f"ERROR: No XML file found for prefix {FILE_PREFIX}")
            return 1

    step_config = {
        "id": "process_menu_navigation",
        "name": "Processing Menu Navigation and Records",
        "module": "run_menu_navigation_step",
        "delay": 2.0,
        "error_chance": 0.00
    }
    previous_step_data = {"file_prefix": FILE_PREFIX}

    print("=" * 60)
    print("DEBUG: Running Menu Navigation Step")
    print("=" * 60)
    print(f"  XML path: {xml_path}")
    print(f"  File prefix: {FILE_PREFIX}")
    print(f"  Config exists: {os.path.exists(os.path.join(UPLOAD_FOLDER, f'{FILE_PREFIX}_config.json'))}")
    print(f"  Simplified exists: {os.path.exists(os.path.join(UPLOAD_FOLDER, f'{FILE_PREFIX}_simplified.json'))}")
    print(f"  Menu nav exists: {os.path.exists(os.path.join(UPLOAD_FOLDER, f'{FILE_PREFIX}_menu_navigation.json'))}")
    print("=" * 60)

    try:
        from processing_steps.process_menu_navigation import run_menu_navigation_step
        result = run_menu_navigation_step(xml_path, step_config, previous_step_data)
        print("\n" + "=" * 60)
        print("SUCCESS - Menu step completed")
        print(f"Result keys: {list(result.keys()) if isinstance(result, dict) else type(result)}")
        print("=" * 60)
        return 0
    except Exception as e:
        print("\n" + "=" * 60)
        print("ERROR - Menu step failed")
        print(f"  {type(e).__name__}: {e}")
        print("=" * 60)
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
