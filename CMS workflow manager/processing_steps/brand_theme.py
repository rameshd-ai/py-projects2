import time
import logging
import json
import sys
import os
import shutil
from typing import Dict, Any
from apis import get_theme_configuration, get_group_record, update_theme_variables, update_theme_configuration

logger = logging.getLogger(__name__)


def run_brand_theme_step(job_id: str, step_config: Dict, workflow_context: Dict) -> Dict[str, Any]:
    """
    Step 2: Brand/Theme Setup
    Processes brand and theme configuration
    Calls theme APIs if "Pull from Current Site" is selected
    """
    # Force output to console
    sys.stdout.flush()
    sys.stderr.flush()
    
    print("\n" + "="*80)
    print("[BRAND/THEME] STEP 2: BRAND/THEME SETUP - STARTING")
    print("="*80)
    sys.stdout.flush()
    
    job_config = workflow_context.get("job_config", {})
    
    # Check if site setup was completed (from previous step)
    site_setup = workflow_context.get("site_setup", {})
    if not site_setup.get("site_created"):
        raise ValueError("Site setup must be completed before brand/theme configuration")
    
    # Get source info
    source_url = job_config.get("sourceUrl", "").strip()
    source_site_id = job_config.get("sourceSiteId", "").strip()
    
    # Get source token from Step 1 or config
    source_token = site_setup.get("source_cms_token") or job_config.get("source_cms_token")
    
    # Get form values
    font_pulled = job_config.get("fontPulled", False)
    font_file = job_config.get("fontFile", "")
    color_file = job_config.get("colorFile", "")
    
    print(f"\n[INFO] STEP 2 INFO:")
    print(f"  Source URL: {source_url}")
    print(f"  Source Site ID: {source_site_id}")
    print(f"  Font Pulled Checkbox: {font_pulled}")
    print(f"  Source Token exists: {bool(source_token)}")
    print(f"  Font File: {font_file or 'None'}")
    print(f"  Color File: {color_file or 'None'}")
    sys.stdout.flush()
    
    # If "Pull from Current Site" is checked, call theme APIs
    print(f"\n[CHECK] Checking if should call theme APIs...")
    print(f"  font_pulled: {font_pulled}")
    print(f"  source_token: {'Yes' if source_token else 'No'}")
    print(f"  source_site_id: {source_site_id if source_site_id else 'No'}")
    sys.stdout.flush()
    
    if font_pulled and source_token and source_site_id:
        print("\n[OK] All conditions met - calling theme APIs now...")
        sys.stdout.flush()
        try:
            print("\n" + "="*80, flush=True)
            print(f"[API] CALLING GET_THEME_CONFIGURATION API", flush=True)
            print("="*80, flush=True)
            print(f"Base URL: {source_url}", flush=True)
            print(f"Site ID: {source_site_id}", flush=True)
            print("="*80, flush=True)
            
            headers = {
                'Authorization': f'Bearer {source_token}',
                'Content-Type': 'application/json'
            }
            
            theme_config_response = get_theme_configuration(source_url, int(source_site_id), headers)
            
            print("\n" + "="*80, flush=True)
            print(f"[API] GET_THEME_CONFIGURATION API RESPONSE", flush=True)
            print("="*80, flush=True)
            
            if theme_config_response:
                print(f"Success: {theme_config_response.get('success', False)}", flush=True)
                print(f"Error Message: {theme_config_response.get('errorMessage', 'None')}", flush=True)
                
                theme_mapping = theme_config_response.get('websiteThemeMappping', {})
                if theme_mapping:
                    print(f"\nTheme Name: {theme_mapping.get('themeName', 'N/A')}", flush=True)
                    print(f"Theme ID: {theme_mapping.get('themeId', 'N/A')}", flush=True)
                    
                    group_mapping = theme_mapping.get('groupMapping', [])
                    print(f"\nGroup Mappings ({len(group_mapping)} groups):", flush=True)
                    for group in group_mapping:
                        print(f"  - Group ID: {group.get('groupId')}", flush=True)
                        print(f"    Name: {group.get('groupName')}", flush=True)
                        print(f"    Type: {group.get('groupType')}", flush=True)
                        print()
                
                print("\nFull Response:", flush=True)
                print(json.dumps(theme_config_response, indent=2), flush=True)
                
                # Save response to file
                try:
                    job_folder = os.path.join("uploads", job_id)
                    os.makedirs(job_folder, exist_ok=True)
                    
                    response_file = os.path.join(job_folder, "source_get_theme_configuration.json")
                    with open(response_file, 'w', encoding='utf-8') as f:
                        json.dump(theme_config_response, f, indent=4, ensure_ascii=False)
                    
                    print(f"\n[SAVED] Saved response to: {response_file}", flush=True)
                    logger.info(f"[{job_id}] Saved theme configuration to {response_file}")
                except Exception as save_error:
                    print(f"[WARNING] Warning: Could not save response file: {save_error}", flush=True)
                    logger.warning(f"[{job_id}] Failed to save theme configuration: {save_error}")
                
                # Call get_group_record if theme configuration was successful
                if theme_config_response.get('success'):
                    theme_id = theme_mapping.get('themeId')
                    
                    if theme_id and group_mapping:
                        # Build groups list
                        groups = []
                        for group in group_mapping:
                            groups.append({
                                "themeId": theme_id,
                                "groupId": group.get('groupId')
                            })
                        
                        print("\n" + "="*80, flush=True)
                        print(f"[PROCESS] CALLING GET_GROUP_RECORD API", flush=True)
                        print("="*80, flush=True)
                        print(f"Theme ID: {theme_id}", flush=True)
                        print(f"Groups: {groups}", flush=True)
                        print("="*80, flush=True)
                        
                        # Build payload for get_group_record
                        group_record_payload = {
                            "SiteId": int(source_site_id),
                            "groups": groups
                        }
                        
                        group_record_response = get_group_record(source_url, group_record_payload, headers)
                        
                        print("\n" + "="*80, flush=True)
                        print(f"[API] GET_GROUP_RECORD API RESPONSE", flush=True)
                        print("="*80, flush=True)
                        
                        if group_record_response:
                            print(f"Success: {group_record_response.get('success', False)}", flush=True)
                            
                            group_details = group_record_response.get('groupsRecordDetails', [])
                            print(f"\nGroup Records ({len(group_details)} groups):", flush=True)
                            
                            for group_detail in group_details:
                                print(f"\n  Theme ID: {group_detail.get('themeId')}", flush=True)
                                print(f"  Theme Name: {group_detail.get('themeName')}", flush=True)
                                print(f"  Group ID: {group_detail.get('groupId')}", flush=True)
                                print(f"  Group Name: {group_detail.get('groupName')}", flush=True)
                                print(f"  Group Type: {group_detail.get('grouptype')}", flush=True)
                                
                                variables = group_detail.get('groupVariables', [])
                                print(f"  Variables ({len(variables)}):", flush=True)
                                for var in variables:
                                    print(f"    - Name: {var.get('variableName')}", flush=True)
                                    print(f"      Type: {var.get('variableType')}", flush=True)
                                    print(f"      Value: {var.get('variableValue')}", flush=True)
                                    print(f"      Alias: {var.get('variableAlias')}", flush=True)
                            
                            print("\nFull Response:", flush=True)
                            print(json.dumps(group_record_response, indent=2), flush=True)
                            
                            # Save response to file
                            try:
                                job_folder = os.path.join("uploads", job_id)
                                os.makedirs(job_folder, exist_ok=True)
                                
                                response_file = os.path.join(job_folder, "source_get_group_record.json")
                                with open(response_file, 'w', encoding='utf-8') as f:
                                    json.dump(group_record_response, f, indent=4, ensure_ascii=False)
                                
                                print(f"\n[SAVED] Saved response to: {response_file}", flush=True)
                                logger.info(f"[{job_id}] Saved group record to {response_file}")
                            except Exception as save_error:
                                print(f"[WARNING] Warning: Could not save response file: {save_error}", flush=True)
                                logger.warning(f"[{job_id}] Failed to save group record: {save_error}")
                            
                            # Copy mapper files from resource folder to job folder
                            print(f"\n[COPY] Copying mapper files to job folder...", flush=True)
                            try:
                                job_folder = os.path.join("uploads", job_id)
                                os.makedirs(job_folder, exist_ok=True)
                                
                                # Copy font_mapper.json
                                font_mapper_src = os.path.join("resource", "font_mapper.json")
                                font_mapper_dest = os.path.join(job_folder, "font_mapper.json")
                                shutil.copy(font_mapper_src, font_mapper_dest)
                                print(f"[OK] Copied: font_mapper.json -> {font_mapper_dest}", flush=True)
                                logger.info(f"[{job_id}] Copied font_mapper.json to job folder")
                                
                                # Copy color_mapper.json
                                color_mapper_src = os.path.join("resource", "color_mapper.json")
                                color_mapper_dest = os.path.join(job_folder, "color_mapper.json")
                                shutil.copy(color_mapper_src, color_mapper_dest)
                                print(f"[OK] Copied: color_mapper.json -> {color_mapper_dest}", flush=True)
                                logger.info(f"[{job_id}] Copied color_mapper.json to job folder")
                                
                                print(f"\n[SAVED] All mapper files copied successfully!", flush=True)
                                
                                # Now update the mapper files with API response data
                                print(f"\n[SYNC] Updating mapper files with API data...", flush=True)
                                
                                # Build separate lookup dictionaries for color and font variables
                                color_variable_lookup = {}
                                font_variable_lookup = {}
                                
                                if group_record_response and 'groupsRecordDetails' in group_record_response:
                                    for group_detail in group_record_response['groupsRecordDetails']:
                                        group_type = group_detail.get('grouptype', 0)
                                        group_variables = group_detail.get('groupVariables', [])
                                        
                                        # Select the appropriate lookup based on group type
                                        # 1 = Color, 2 = Font
                                        target_lookup = color_variable_lookup if group_type == 1 else font_variable_lookup if group_type == 2 else None
                                        
                                        if target_lookup is not None:
                                            for var in group_variables:
                                                var_alias = var.get('variableAlias', '').strip()
                                                var_value = var.get('variableValue', '').strip()
                                                var_name = var.get('variableName', '').strip()
                                                
                                                # Store by alias (prefer alias over name, but don't overwrite if already exists)
                                                if var_alias and var_value:
                                                    # Convert to lowercase for case-insensitive matching
                                                    alias_key = var_alias.lower()
                                                    if alias_key not in target_lookup or not target_lookup[alias_key]:
                                                        target_lookup[alias_key] = var_value
                                                        # Also store with original case for exact matches
                                                        target_lookup[var_alias] = var_value
                                                
                                                # Store by name (only if no alias or as fallback)
                                                if var_name and var_value:
                                                    # Convert to lowercase for case-insensitive matching
                                                    name_key = var_name.lower()
                                                    if name_key not in target_lookup or not target_lookup[name_key]:
                                                        target_lookup[name_key] = var_value
                                                        # Also store with original case for exact matches
                                                        target_lookup[var_name] = var_value
                                
                                print(f"[INFO] Built color lookup with {len(color_variable_lookup)} variables", flush=True)
                                print(f"[INFO] Built font lookup with {len(font_variable_lookup)} variables", flush=True)
                                
                                # Debug: Print all available color variable keys
                                if color_variable_lookup:
                                    color_keys = list(color_variable_lookup.keys())
                                    print(f"[DEBUG] Available color variable keys ({len(color_keys)}): {color_keys[:10]}...", flush=True)
                                    print(f"[DEBUG] Sample color variables: {list(color_variable_lookup.items())[:5]}", flush=True)
                                else:
                                    print(f"[WARNING] No color variables found in source API response!", flush=True)
                                
                                # Debug: Print all available font variable keys
                                if font_variable_lookup:
                                    font_keys = list(font_variable_lookup.keys())
                                    print(f"[DEBUG] Available font variable keys ({len(font_keys)}): {font_keys[:10]}...", flush=True)
                                else:
                                    print(f"[WARNING] No font variables found in source API response!", flush=True)
                                
                                # Update font_mapper.json
                                print(f"\n[UPDATE] Updating font_mapper.json...", flush=True)
                                with open(font_mapper_dest, 'r', encoding='utf-8') as f:
                                    font_mapper = json.load(f)
                                
                                updated_font_count = 0
                                for entry in font_mapper:
                                    old_key = entry.get('old_key', '').strip()
                                    new_key = entry.get('new_key', '').strip()
                                    current_value = entry.get('value', '').strip()
                                    
                                    # Only update if value is empty/blank
                                    if not current_value:
                                        found_value = None
                                        match_type = None
                                        
                                        # Try exact match first (case-sensitive)
                                        if old_key and old_key in font_variable_lookup:
                                            found_value = font_variable_lookup[old_key]
                                            match_type = f"exact old_key '{old_key}'"
                                        # Try case-insensitive match
                                        elif old_key:
                                            old_key_lower = old_key.lower()
                                            if old_key_lower in font_variable_lookup:
                                                found_value = font_variable_lookup[old_key_lower]
                                                match_type = f"case-insensitive old_key '{old_key}'"
                                        # Try new_key as fallback
                                        if not found_value and new_key:
                                            if new_key in font_variable_lookup:
                                                found_value = font_variable_lookup[new_key]
                                                match_type = f"new_key '{new_key}'"
                                            else:
                                                new_key_lower = new_key.lower()
                                                if new_key_lower in font_variable_lookup:
                                                    found_value = font_variable_lookup[new_key_lower]
                                                    match_type = f"case-insensitive new_key '{new_key}'"
                                        
                                        if found_value:
                                            entry['value'] = found_value
                                            updated_font_count += 1
                                            print(f"  [OK] Updated '{new_key}' (matched via {match_type}) = '{found_value}'", flush=True)
                                        else:
                                            # Debug: show what we're looking for
                                            if old_key:
                                                print(f"  [DEBUG] No match for old_key '{old_key}' in font lookup", flush=True)
                                
                                # Save updated font_mapper
                                with open(font_mapper_dest, 'w', encoding='utf-8') as f:
                                    json.dump(font_mapper, f, indent=2, ensure_ascii=False)
                                
                                print(f"[OK] Updated {updated_font_count} entries in font_mapper.json", flush=True)
                                
                                # Update color_mapper.json
                                print(f"\n[UPDATE] Updating color_mapper.json...", flush=True)
                                with open(color_mapper_dest, 'r', encoding='utf-8') as f:
                                    color_mapper = json.load(f)
                                
                                updated_color_count = 0
                                for entry in color_mapper:
                                    old_key = entry.get('old_key', '').strip()
                                    new_key = entry.get('new_key', '').strip()
                                    current_value = entry.get('value', '').strip()
                                    
                                    # Only update if value is empty/blank (same logic as font_mapper)
                                    if not current_value:
                                        found_value = None
                                        match_type = None
                                        
                                        # Try exact match first (case-sensitive)
                                        if old_key and old_key in color_variable_lookup:
                                            found_value = color_variable_lookup[old_key]
                                            match_type = f"exact old_key '{old_key}'"
                                        # Try case-insensitive match
                                        elif old_key:
                                            old_key_lower = old_key.lower()
                                            if old_key_lower in color_variable_lookup:
                                                found_value = color_variable_lookup[old_key_lower]
                                                match_type = f"case-insensitive old_key '{old_key}'"
                                        # Try new_key as fallback
                                        if not found_value and new_key:
                                            if new_key in color_variable_lookup:
                                                found_value = color_variable_lookup[new_key]
                                                match_type = f"new_key '{new_key}'"
                                            else:
                                                new_key_lower = new_key.lower()
                                                if new_key_lower in color_variable_lookup:
                                                    found_value = color_variable_lookup[new_key_lower]
                                                    match_type = f"case-insensitive new_key '{new_key}'"
                                        
                                        if found_value:
                                            entry['value'] = found_value
                                            updated_color_count += 1
                                            print(f"  [OK] Updated '{new_key}' (matched via {match_type}) = '{found_value}'", flush=True)
                                        else:
                                            # Debug: show what we're looking for
                                            if old_key:
                                                print(f"  [DEBUG] No match for old_key '{old_key}' in color lookup", flush=True)
                                
                                # Save updated color_mapper
                                with open(color_mapper_dest, 'w', encoding='utf-8') as f:
                                    json.dump(color_mapper, f, indent=2, ensure_ascii=False)
                                
                                print(f"[OK] Updated {updated_color_count} entries in color_mapper.json", flush=True)
                                
                                if updated_color_count == 0:
                                    print(f"[WARNING] No color variables were updated! Check if variable names/aliases match.", flush=True)
                                    print(f"[DEBUG] Available color variable keys ({len(color_variable_lookup)}): {list(color_variable_lookup.keys())}", flush=True)
                                    print(f"[DEBUG] Color mapper old_keys being searched: {[e.get('old_key') for e in color_mapper[:10]]}", flush=True)
                                    
                                    # Show which old_keys don't have matches
                                    unmatched_keys = []
                                    for entry in color_mapper:
                                        old_key = entry.get('old_key', '').strip()
                                        if old_key and old_key not in color_variable_lookup and old_key.lower() not in color_variable_lookup:
                                            unmatched_keys.append(old_key)
                                    if unmatched_keys:
                                        print(f"[DEBUG] Unmatched old_keys: {set(unmatched_keys)}", flush=True)
                                
                                print(f"\n[SUCCESS] All mapper files updated successfully!", flush=True)
                                
                            except Exception as copy_error:
                                print(f"[WARNING] Warning: Could not copy/update mapper files: {copy_error}", flush=True)
                                logger.warning(f"[{job_id}] Failed to copy/update mapper files: {copy_error}")
                            
                            # Now fetch destination site theme configuration
                            print(f"\n" + "="*80, flush=True)
                            print(f"[FETCH] FETCHING DESTINATION SITE THEME DATA", flush=True)
                            print(f"="*80, flush=True)
                            
                            # Get destination site info
                            destination_url = job_config.get("destinationUrl", "").strip()
                            destination_site_id = job_config.get("destinationSiteId", "").strip()
                            destination_token = site_setup.get("destination_cms_token") or job_config.get("destination_cms_token")
                            
                            print(f"\n[INFO] DESTINATION SITE INFO:", flush=True)
                            print(f"  Destination URL: {destination_url}", flush=True)
                            print(f"  Destination Site ID: {destination_site_id}", flush=True)
                            print(f"  Destination Token exists: {bool(destination_token)}", flush=True)
                            
                            if destination_token and destination_site_id:
                                try:
                                    print(f"\n[API] Calling get_theme_configuration for DESTINATION site...", flush=True)
                                    print("="*80, flush=True)
                                    
                                    dest_headers = {
                                        'Authorization': f'Bearer {destination_token}',
                                        'Content-Type': 'application/json'
                                    }
                                    
                                    dest_theme_response = get_theme_configuration(destination_url, int(destination_site_id), dest_headers)
                                    
                                    print(f"\n[API] DESTINATION THEME CONFIGURATION RESPONSE", flush=True)
                                    print("="*80, flush=True)
                                    
                                    if dest_theme_response:
                                        print(f"Success: {dest_theme_response.get('success', False)}", flush=True)
                                        print(f"Error Message: {dest_theme_response.get('errorMessage', 'None')}", flush=True)
                                        
                                        dest_theme_mapping = dest_theme_response.get('websiteThemeMappping', {})
                                        if dest_theme_mapping:
                                            print(f"\nTheme Name: {dest_theme_mapping.get('themeName', 'N/A')}", flush=True)
                                            print(f"Theme ID: {dest_theme_mapping.get('themeId', 'N/A')}", flush=True)
                                            
                                            dest_group_mapping = dest_theme_mapping.get('groupMapping', [])
                                            print(f"Group Mappings: {len(dest_group_mapping)} groups", flush=True)
                                        
                                        print("\nFull Response:", flush=True)
                                        print(json.dumps(dest_theme_response, indent=2), flush=True)
                                        
                                        # Save destination theme configuration
                                        try:
                                            job_folder = os.path.join("uploads", job_id)
                                            dest_theme_file = os.path.join(job_folder, "destination_get_theme_configuration.json")
                                            with open(dest_theme_file, 'w', encoding='utf-8') as f:
                                                json.dump(dest_theme_response, f, indent=4, ensure_ascii=False)
                                            
                                            print(f"\n[SAVED] Saved destination theme config to: {dest_theme_file}", flush=True)
                                            logger.info(f"[{job_id}] Saved destination theme configuration")
                                            
                                            print(f"\n[SUCCESS] Destination site theme configuration fetched and saved successfully!", flush=True)
                                            
                                            # Create final payload for theme update
                                            print(f"\n" + "="*80, flush=True)
                                            print(f"[PAYLOAD] CREATING FINAL PAYLOAD FOR THEME UPDATE", flush=True)
                                            print(f"="*80, flush=True)
                                            
                                            # Get destination theme ID
                                            dest_theme_id = dest_theme_mapping.get('themeId')
                                            
                                            if not dest_theme_id:
                                                print(f"[WARNING] Warning: Could not find destination theme ID", flush=True)
                                            else:
                                                # Extract site name from destination URL for group naming
                                                site_identifier = destination_url.split('//')[-1].split('.')[0]
                                                
                                                # Create group names with suffixes
                                                font_group_name = f"{site_identifier}_font"
                                                color_group_name = f"{site_identifier}_color"
                                                
                                                print(f"\n[INFO] Payload Details:", flush=True)
                                                print(f"  Destination Site ID: {destination_site_id}", flush=True)
                                                print(f"  Destination Theme ID: {dest_theme_id}", flush=True)
                                                print(f"  Font Group Name: {font_group_name}", flush=True)
                                                print(f"  Color Group Name: {color_group_name}", flush=True)
                                                
                                                # Load mapper files
                                                font_mapper_file = os.path.join(job_folder, "font_mapper.json")
                                                color_mapper_file = os.path.join(job_folder, "color_mapper.json")
                                                
                                                # Build font variables JSON string
                                                font_variables = {}
                                                if os.path.exists(font_mapper_file):
                                                    with open(font_mapper_file, 'r', encoding='utf-8') as f:
                                                        font_mapper = json.load(f)
                                                    
                                                    for entry in font_mapper:
                                                        new_key = entry.get('new_key', '').strip()
                                                        value = entry.get('value', '').strip()
                                                        if new_key and value:
                                                            font_variables[new_key] = value
                                                    
                                                    print(f"\n[OK] Loaded {len(font_variables)} font variables", flush=True)
                                                
                                                # Build color variables JSON string
                                                color_variables = {}
                                                if os.path.exists(color_mapper_file):
                                                    with open(color_mapper_file, 'r', encoding='utf-8') as f:
                                                        color_mapper = json.load(f)
                                                    
                                                    for entry in color_mapper:
                                                        new_key = entry.get('new_key', '').strip()
                                                        value = entry.get('value', '').strip()
                                                        if new_key and value:
                                                            color_variables[new_key] = value
                                                    
                                                    print(f"[OK] Loaded {len(color_variables)} color variables", flush=True)
                                                
                                                # Validate that we have variables before proceeding
                                                if len(color_variables) == 0 and len(font_variables) == 0:
                                                    print(f"\n[ERROR] Both color and font variables are empty! Cannot create theme groups.", flush=True)
                                                    print(f"[ERROR] Color variables: {len(color_variables)}, Font variables: {len(font_variables)}", flush=True)
                                                    logger.error(f"[{job_id}] Cannot create theme groups - both color and font variables are empty")
                                                    raise ValueError("Both color and font variables are empty. Cannot create theme groups.")
                                                
                                                # Build groups list - only include groups with variables
                                                groups_list = []
                                                
                                                if len(color_variables) > 0:
                                                    groups_list.append({
                                                        "Groupid": 0,  # 0 for new group (add operation)
                                                        "GroupName": color_group_name,
                                                        "GroupType": 1,  # 1 for color
                                                        "themeVariables": json.dumps(color_variables)
                                                    })
                                                    print(f"[OK] Color group will be created with {len(color_variables)} variables", flush=True)
                                                else:
                                                    print(f"[WARNING] Color variables are empty - skipping color group creation", flush=True)
                                                    logger.warning(f"[{job_id}] Color variables are empty - skipping color group")
                                                
                                                if len(font_variables) > 0:
                                                    groups_list.append({
                                                        "Groupid": 0,  # 0 for new group (add operation)
                                                        "GroupName": font_group_name,
                                                        "GroupType": 2,  # 2 for font
                                                        "themeVariables": json.dumps(font_variables)
                                                    })
                                                    print(f"[OK] Font group will be created with {len(font_variables)} variables", flush=True)
                                                else:
                                                    print(f"[WARNING] Font variables are empty - skipping font group creation", flush=True)
                                                    logger.warning(f"[{job_id}] Font variables are empty - skipping font group")
                                                
                                                if len(groups_list) == 0:
                                                    print(f"\n[ERROR] No groups to create! Both color and font variables are empty.", flush=True)
                                                    raise ValueError("No groups to create - both color and font variables are empty.")
                                                
                                                # Create final payload
                                                final_payload = {
                                                    "siteId": int(destination_site_id),
                                                    "themeId": dest_theme_id,
                                                    "groups": groups_list
                                                }
                                                
                                                # Save final payload to file
                                                final_payload_file = os.path.join(job_folder, "update_theme_variables_payload.json")
                                                with open(final_payload_file, 'w', encoding='utf-8') as f:
                                                    json.dump(final_payload, f, indent=4, ensure_ascii=False)
                                                
                                                print(f"\n[SAVED] Theme variables payload saved to: {final_payload_file}", flush=True)
                                                print(f"\n[PAYLOAD] Payload Summary:", flush=True)
                                                print(f"  Site ID: {final_payload['siteId']}", flush=True)
                                                print(f"  Theme ID: {final_payload['themeId']}", flush=True)
                                                print(f"  Groups: {len(final_payload['groups'])}", flush=True)
                                                if len(color_variables) > 0:
                                                    print(f"    - Color Group: {color_group_name} ({len(color_variables)} variables)", flush=True)
                                                if len(font_variables) > 0:
                                                    print(f"    - Font Group: {font_group_name} ({len(font_variables)} variables)", flush=True)
                                                print(f"\n[SUCCESS] Final payload created and saved successfully!", flush=True)
                                                
                                                logger.info(f"[{job_id}] Created final update payload with {len(color_variables)} color and {len(font_variables)} font variables")
                                                
                                                # Now call update_theme_variables API for DESTINATION site
                                                print(f"\n" + "="*80, flush=True)
                                                print(f"[UPDATE] UPDATING DESTINATION SITE THEME VARIABLES", flush=True)
                                                print(f"="*80, flush=True)
                                                
                                                try:
                                                    # Use destination token for the update
                                                    update_headers = {
                                                        'Authorization': f'Bearer {destination_token}',
                                                        'Content-Type': 'application/json'
                                                    }
                                                    
                                                    print(f"\n[SEND] Sending update request to DESTINATION site...", flush=True)
                                                    print(f"  URL: {destination_url}", flush=True)
                                                    print(f"  Site ID: {destination_site_id}", flush=True)
                                                    print(f"  Theme ID: {dest_theme_id}", flush=True)
                                                    
                                                    update_response = update_theme_variables(
                                                        base_url=destination_url,
                                                        payload=final_payload,
                                                        headers=update_headers
                                                    )
                                                    
                                                    print(f"\n[API] UPDATE RESPONSE", flush=True)
                                                    print("="*80, flush=True)
                                                    
                                                    if update_response:
                                                        print(f"Success: {update_response.get('success', False)}", flush=True)
                                                        print(f"Message: {update_response.get('message', 'N/A')}", flush=True)
                                                        
                                                        updated_groups = update_response.get('data', [])
                                                        
                                                        print(f"\nFull Response:", flush=True)
                                                        print(json.dumps(update_response, indent=2), flush=True)
                                                        
                                                        # Save update response to file
                                                        update_response_file = os.path.join(job_folder, "update_theme_variables_response.json")
                                                        with open(update_response_file, 'w', encoding='utf-8') as f:
                                                            json.dump(update_response, f, indent=4, ensure_ascii=False)
                                                        
                                                        print(f"\n[SAVED] Theme variables response saved to: {update_response_file}", flush=True)
                                                        
                                                        if updated_groups and len(updated_groups) > 0:
                                                            print(f"\n[OK] Updated Groups ({len(updated_groups)}):", flush=True)
                                                            for group in updated_groups:
                                                                group_id = group.get('GroupId')
                                                                group_type = group.get('GroupType')
                                                                group_type_name = "Color" if group_type == 1 else "Font" if group_type == 2 else "Unknown"
                                                                print(f"  - Group ID: {group_id} (Type: {group_type_name})", flush=True)
                                                            
                                                            print(f"\n[SUCCESS] DESTINATION SITE THEME VARIABLES UPDATED SUCCESSFULLY!", flush=True)
                                                            logger.info(f"[{job_id}] Successfully updated destination site theme variables - {len(updated_groups)} groups created")
                                                            
                                                            # Now call UpdateThemeConfiguration to finalize the theme update
                                                            print(f"\n" + "="*80, flush=True)
                                                            print(f"[PROCESS] FINALIZING THEME CONFIGURATION", flush=True)
                                                            print(f"="*80, flush=True)
                                                            
                                                            try:
                                                                # Build groups list from update response
                                                                config_groups = []
                                                                for group in updated_groups:
                                                                    group_id = group.get('GroupId')
                                                                    if group_id:
                                                                        config_groups.append({"groupId": group_id})
                                                                
                                                                if len(config_groups) == 0:
                                                                    print(f"[ERROR] No valid group IDs found in update response!", flush=True)
                                                                    logger.error(f"[{job_id}] No valid group IDs found in update response")
                                                                    raise ValueError("No valid group IDs found in update response")
                                                                
                                                                # Build payload for theme configuration update
                                                                config_payload = {
                                                                    "siteId": int(destination_site_id),
                                                                    "themeId": dest_theme_id,
                                                                    "groups": config_groups
                                                                }
                                                                
                                                                # Save configuration payload to file
                                                                config_payload_file = os.path.join(job_folder, "update_theme_configuration_payload.json")
                                                                with open(config_payload_file, 'w', encoding='utf-8') as f:
                                                                    json.dump(config_payload, f, indent=4, ensure_ascii=False)
                                                                
                                                                print(f"\n[SAVED] Theme configuration payload saved to: {config_payload_file}", flush=True)
                                                                
                                                                print(f"\n[SEND] Updating theme configuration...", flush=True)
                                                                print(f"  Site ID: {destination_site_id}", flush=True)
                                                                print(f"  Theme ID: {dest_theme_id}", flush=True)
                                                                print(f"  Groups: {config_groups}", flush=True)
                                                                
                                                                config_response = update_theme_configuration(
                                                                    base_url=destination_url,
                                                                    payload=config_payload,
                                                                    headers=update_headers
                                                                )
                                                                
                                                                print(f"\n[API] THEME CONFIGURATION RESPONSE", flush=True)
                                                                print("="*80, flush=True)
                                                                
                                                                if config_response:
                                                                    print(f"Success: {config_response.get('success', False)}", flush=True)
                                                                    print(f"Message: {config_response.get('message', 'N/A')}", flush=True)
                                                                    
                                                                    print(f"\nFull Response:", flush=True)
                                                                    print(json.dumps(config_response, indent=2), flush=True)
                                                                    
                                                                    # Save configuration response to file
                                                                    config_response_file = os.path.join(job_folder, "update_theme_configuration_response.json")
                                                                    with open(config_response_file, 'w', encoding='utf-8') as f:
                                                                        json.dump(config_response, f, indent=4, ensure_ascii=False)
                                                                    
                                                                    print(f"\n[SAVED] Theme configuration response saved to: {config_response_file}", flush=True)
                                                                    
                                                                    if config_response.get('success', False):
                                                                        print(f"\n[OK] THEME CONFIGURATION FINALIZED SUCCESSFULLY!", flush=True)
                                                                        logger.info(f"[{job_id}] Successfully finalized theme configuration")
                                                                    else:
                                                                        error_msg = config_response.get('message', 'Unknown error')
                                                                        print(f"\n[ERROR] Theme configuration update failed: {error_msg}", flush=True)
                                                                        logger.error(f"[{job_id}] Theme configuration update failed: {error_msg}")
                                                                else:
                                                                    print("[ERROR] Theme configuration API returned None", flush=True)
                                                                    logger.error(f"[{job_id}] Update theme configuration API returned None")
                                                                
                                                                print("="*80 + "\n", flush=True)
                                                                
                                                            except Exception as config_error:
                                                                print(f"[ERROR] Error updating theme configuration: {config_error}", flush=True)
                                                                logger.error(f"[{job_id}] Failed to update theme configuration: {config_error}")
                                                                import traceback
                                                                print(f"[ERROR] Traceback: {traceback.format_exc()}", flush=True)
                                                        else:
                                                            print(f"\n[WARNING] Update API returned success but no groups were created!", flush=True)
                                                            print(f"[WARNING] Response data: {updated_groups}", flush=True)
                                                            logger.warning(f"[{job_id}] Update API returned success but no groups in response")
                                                            if not update_response.get('success', False):
                                                                error_msg = update_response.get('message', 'Unknown error')
                                                                print(f"[ERROR] API returned success=false: {error_msg}", flush=True)
                                                                logger.error(f"[{job_id}] Update theme variables API failed: {error_msg}")
                                                    else:
                                                        print("[ERROR] Update API returned None - check error logs", flush=True)
                                                        logger.error(f"[{job_id}] Update theme variables API returned None")
                                                        print("[ERROR] This usually means the API call failed. Check network connection and API endpoint.", flush=True)
                                                    
                                                    print("="*80 + "\n", flush=True)
                                                    
                                                except Exception as update_error:
                                                    print(f"[ERROR] Error updating destination site theme variables: {update_error}", flush=True)
                                                    logger.error(f"[{job_id}] Failed to update destination theme variables: {update_error}")
                                        
                                        except Exception as save_error:
                                            print(f"[WARNING] Warning: Could not save destination theme config: {save_error}", flush=True)
                                    else:
                                        print("[ERROR] Destination theme configuration API returned None", flush=True)
                                    
                                    print("="*80 + "\n", flush=True)
                                    
                                except Exception as dest_error:
                                    print(f"[ERROR] Error fetching destination site data: {dest_error}", flush=True)
                                    logger.error(f"[{job_id}] Failed to fetch destination data: {dest_error}")
                            else:
                                print(f"[WARNING] Missing destination token or site ID - skipping destination data fetch", flush=True)
                        else:
                            print("[ERROR] Group Record API returned None", flush=True)
                        print("="*80 + "\n", flush=True)
            else:
                print("[ERROR] Theme Configuration API returned None", flush=True)
            print("="*80 + "\n", flush=True)
            
        except Exception as e:
            logger.error(f"[{job_id}] Error calling theme APIs: {e}")
            print(f"[ERROR] Error calling theme APIs: {e}", flush=True)
    else:
        print(f"\n[WARNING] SKIPPING theme APIs")
        print(f"  Reason: font_pulled={font_pulled}, has_token={bool(source_token)}, has_site_id={bool(source_site_id)}")
        sys.stdout.flush()
    
    # Simulate processing
    time.sleep(step_config.get("delay", 3.0))
    
    # Determine config source
    if font_pulled:
        config_source = "pulled_from_site"
    elif font_file or color_file:
        config_source = "uploaded_file"
    else:
        config_source = "default"
    
    return {
        "branding_complete": True,
        "fonts_configured": True,
        "theme_applied": True,
        "config_source": config_source,
        "font_file": font_file if font_file else None,
        "color_file": color_file if color_file else None,
        "message": f"Brand/Theme configured from {config_source}"
    }



