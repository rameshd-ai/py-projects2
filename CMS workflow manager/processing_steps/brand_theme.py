import time
import logging
import json
import sys
from typing import Dict, Any
from apis import get_theme_configuration, get_group_record

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
    print("🎨 STEP 2: BRAND/THEME SETUP - STARTING")
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
    
    print(f"\n📊 STEP 2 INFO:")
    print(f"  Source URL: {source_url}")
    print(f"  Source Site ID: {source_site_id}")
    print(f"  Font Pulled Checkbox: {font_pulled}")
    print(f"  Source Token exists: {bool(source_token)}")
    print(f"  Font File: {font_file or 'None'}")
    print(f"  Color File: {color_file or 'None'}")
    sys.stdout.flush()
    
    # If "Pull from Current Site" is checked, call theme APIs
    print(f"\n🔍 Checking if should call theme APIs...")
    print(f"  font_pulled: {font_pulled}")
    print(f"  source_token: {'Yes' if source_token else 'No'}")
    print(f"  source_site_id: {source_site_id if source_site_id else 'No'}")
    sys.stdout.flush()
    
    if font_pulled and source_token and source_site_id:
        print("\n✅ All conditions met - calling theme APIs now...")
        sys.stdout.flush()
        try:
            print("\n" + "="*80, flush=True)
            print(f"🎨 CALLING GET_THEME_CONFIGURATION API", flush=True)
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
            print(f"📋 GET_THEME_CONFIGURATION API RESPONSE", flush=True)
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
                import json
                print(json.dumps(theme_config_response, indent=2), flush=True)
                
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
                        print(f"🔧 CALLING GET_GROUP_RECORD API", flush=True)
                        print("="*80, flush=True)
                        print(f"Theme ID: {theme_id}", flush=True)
                        print(f"Groups: {groups}", flush=True)
                        print("="*80, flush=True)
                        
                        group_record_response = get_group_record(source_url, int(source_site_id), groups, headers)
                        
                        print("\n" + "="*80, flush=True)
                        print(f"📋 GET_GROUP_RECORD API RESPONSE", flush=True)
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
                        else:
                            print("❌ Group Record API returned None", flush=True)
                        print("="*80 + "\n", flush=True)
            else:
                print("❌ Theme Configuration API returned None", flush=True)
            print("="*80 + "\n", flush=True)
            
        except Exception as e:
            logger.error(f"[{job_id}] Error calling theme APIs: {e}")
            print(f"❌ Error calling theme APIs: {e}", flush=True)
    else:
        print(f"\n⚠️ SKIPPING theme APIs")
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



