import time
import logging
from typing import Dict, Any
from apis import generate_cms_token, get_theme_configuration, get_group_record

logger = logging.getLogger(__name__)


def run_site_setup_step(job_id: str, step_config: Dict, workflow_context: Dict) -> Dict[str, Any]:
    """
    Step 1: Site Setup Readiness
    Validates and processes site configuration
    Generates CMS tokens for source and destination if all required fields are provided
    """
    print("\n" + "🚀"*40, flush=True)
    print("STEP 1 FUNCTION CALLED - run_site_setup_step", flush=True)
    print("🚀"*40 + "\n", flush=True)
    
    job_config = workflow_context.get("job_config", {})
    
    # Validate required fields
    required_fields = {
        "sourceUrl": "Source URL",
        "sourceSiteId": "Source Site ID",
        "destinationUrl": "Destination URL",
        "destinationSiteId": "Destination Site ID"
    }
    
    missing = [name for field, name in required_fields.items() if not job_config.get(field)]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")
    
    # Extract values
    source_url = job_config.get("sourceUrl", "").strip()
    source_site_id = job_config.get("sourceSiteId", "").strip()
    source_profile_alias = job_config.get("sourceProfileAliasId", "").strip()
    
    destination_url = job_config.get("destinationUrl", "").strip()
    destination_site_id = job_config.get("destinationSiteId", "").strip()
    destination_profile_alias = job_config.get("destinationProfileAliasId", "").strip()
    
    # Initialize token variables
    source_token = None
    destination_token = None
    token_generation_errors = []
    
    # Generate source CMS token if all required fields are present
    if source_url and source_profile_alias:
        try:
            logger.info(f"[{job_id}] Generating source CMS token for URL: {source_url}")
            cms_response_data = generate_cms_token(source_url, source_profile_alias)
            
            if not cms_response_data:
                error_msg = "Source token generation failed: API call returned None. Check API logs for connectivity issues or errors."
                logger.error(f"[{job_id}] {error_msg}")
                token_generation_errors.append(f"Source: {error_msg}")
            else:
                source_token = cms_response_data.get('token')
                if source_token:
                    print(f"✅ Source token generated successfully!", flush=True)
                    logger.info(f"[{job_id}] ✓ Source CMS token generated successfully")
                else:
                    error_msg = f"Source token not found in API response. Response keys: {list(cms_response_data.keys())}"
                    logger.warning(f"[{job_id}] {error_msg}")
                    token_generation_errors.append(f"Source: {error_msg}")
        except Exception as e:
            error_msg = f"Source token generation exception: {str(e)}"
            logger.error(f"[{job_id}] {error_msg}")
            token_generation_errors.append(f"Source: {error_msg}")
    else:
        logger.info(f"[{job_id}] Skipping source token generation - missing URL or Profile Alias")
    
    # Generate destination CMS token if all required fields are present
    if destination_url and destination_profile_alias:
        try:
            logger.info(f"[{job_id}] Generating destination CMS token for URL: {destination_url}")
            cms_response_data = generate_cms_token(destination_url, destination_profile_alias)
            
            if not cms_response_data:
                error_msg = "Destination token generation failed: API call returned None. Check API logs for connectivity issues or errors."
                logger.error(f"[{job_id}] {error_msg}")
                token_generation_errors.append(f"Destination: {error_msg}")
            else:
                destination_token = cms_response_data.get('token')
                if destination_token:
                    print(f"✅ Destination token generated successfully!", flush=True)
                    logger.info(f"[{job_id}] ✓ Destination CMS token generated successfully")
                else:
                    error_msg = f"Destination token not found in API response. Response keys: {list(cms_response_data.keys())}"
                    logger.warning(f"[{job_id}] {error_msg}")
                    token_generation_errors.append(f"Destination: {error_msg}")
        except Exception as e:
            error_msg = f"Destination token generation exception: {str(e)}"
            logger.error(f"[{job_id}] {error_msg}")
            token_generation_errors.append(f"Destination: {error_msg}")
    else:
        logger.info(f"[{job_id}] Skipping destination token generation - missing URL or Profile Alias")
    
    # Call get_theme_configuration for source site if we have the token
    theme_config_response = None
    print(f"\n🔍 DEBUG: source_token exists: {bool(source_token)}", flush=True)
    print(f"🔍 DEBUG: source_site_id: {source_site_id}", flush=True)
    print(f"🔍 DEBUG: Will call theme API: {bool(source_token and source_site_id)}\n", flush=True)
    
    if source_token and source_site_id:
        try:
            logger.info(f"[{job_id}] Calling get_theme_configuration for source site...")
            print("\n" + "="*80, flush=True)
            print(f"🎨 CALLING GET_THEME_CONFIGURATION API", flush=True)
            print("="*80, flush=True)
            print(f"Base URL: {source_url}", flush=True)
            print(f"Site ID: {source_site_id}", flush=True)
            print("="*80, flush=True)
            
            # Build headers with the generated token
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
                    print(f"\nTheme Name: {theme_mapping.get('themeName', 'N/A')}")
                    print(f"Theme ID: {theme_mapping.get('themeId', 'N/A')}")
                    
                    group_mapping = theme_mapping.get('groupMapping', [])
                    print(f"\nGroup Mappings ({len(group_mapping)} groups):")
                    for group in group_mapping:
                        print(f"  - Group ID: {group.get('groupId')}")
                        print(f"    Name: {group.get('groupName')}")
                        print(f"    Type: {group.get('groupType')}")
                        print()
                
                print("\nFull Response:")
                import json
                print(json.dumps(theme_config_response, indent=2))
            else:
                print("❌ API returned None (check error logs above)")
            print("="*80 + "\n")
            
            logger.info(f"[{job_id}] Theme configuration API call completed")
            
            # Call get_group_record if theme configuration was successful
            if theme_config_response and theme_config_response.get('success'):
                try:
                    theme_mapping = theme_config_response.get('websiteThemeMappping', {})
                    theme_id = theme_mapping.get('themeId')
                    group_mapping = theme_mapping.get('groupMapping', [])
                    
                    if theme_id and group_mapping:
                        # Build groups list for API call
                        groups = []
                        for group in group_mapping:
                            groups.append({
                                "themeId": theme_id,
                                "groupId": group.get('groupId')
                            })
                        
                        logger.info(f"[{job_id}] Calling get_group_record with {len(groups)} groups...")
                        print("\n" + "="*80, flush=True)
                        print(f"🔧 CALLING GET_GROUP_RECORD API", flush=True)
                        print("="*80, flush=True)
                        print(f"Base URL: {source_url}", flush=True)
                        print(f"Site ID: {source_site_id}", flush=True)
                        print(f"Theme ID: {theme_id}", flush=True)
                        print(f"Groups: {groups}", flush=True)
                        print("="*80, flush=True)
                        
                        # Build headers with the source token
                        headers = {
                            'Authorization': f'Bearer {source_token}',
                            'Content-Type': 'application/json'
                        }
                        
                        group_record_response = get_group_record(source_url, int(source_site_id), groups, headers)
                        
                        print("\n" + "="*80, flush=True)
                        print(f"📋 GET_GROUP_RECORD API RESPONSE", flush=True)
                        print("="*80, flush=True)
                        if group_record_response:
                            print(f"Success: {group_record_response.get('success', False)}", flush=True)
                            print(f"Error Message: {group_record_response.get('errorMessage', 'None')}", flush=True)
                            
                            group_details = group_record_response.get('groupsRecordDetails', [])
                            print(f"\nGroup Records ({len(group_details)} groups):")
                            
                            for group_detail in group_details:
                                print(f"\n  Theme ID: {group_detail.get('themeId')}")
                                print(f"  Theme Name: {group_detail.get('themeName')}")
                                print(f"  Group ID: {group_detail.get('groupId')}")
                                print(f"  Group Name: {group_detail.get('groupName')}")
                                print(f"  Group Type: {group_detail.get('grouptype')}")
                                
                                variables = group_detail.get('groupVariables', [])
                                print(f"  Variables ({len(variables)}):")
                                for var in variables:
                                    print(f"    - Name: {var.get('variableName')}")
                                    print(f"      Type: {var.get('variableType')}")
                                    print(f"      Value: {var.get('variableValue')}")
                                    print(f"      Alias: {var.get('variableAlias')}")
                            
                            print("\nFull Response:")
                            import json
                            print(json.dumps(group_record_response, indent=2))
                        else:
                            print("❌ API returned None (check error logs above)")
                        print("="*80 + "\n")
                        
                        logger.info(f"[{job_id}] Group record API call completed")
                    else:
                        logger.warning(f"[{job_id}] Missing theme ID or group mappings, skipping get_group_record")
                except Exception as e:
                    logger.error(f"[{job_id}] Error calling get_group_record: {e}")
                    print(f"❌ Error calling group record API: {e}")
        except Exception as e:
            logger.error(f"[{job_id}] Error calling get_theme_configuration: {e}")
            print(f"❌ Error calling theme configuration API: {e}")
    else:
        logger.info(f"[{job_id}] Skipping theme configuration API - missing token or site ID")
    
    # Simulate processing
    time.sleep(step_config.get("delay", 2.0))
    
    # Process site setup
    site_name = job_config.get("siteName", "Unnamed Site")
    site_url = job_config.get("siteUrl", "")
    
    # Build result dictionary
    result = {
        "site_created": True,
        "site_name": site_name,
        "site_url": site_url,
        "source_validated": True,
        "destination_validated": True,
        "create_type": job_config.get("createSiteType", "existing"),
        "application_pool": job_config.get("applicationPool", ""),
        "message": f"Site setup completed for: {site_name}"
    }
    
    # Add tokens if generated successfully
    if source_token:
        result["source_cms_token"] = source_token
        result["source_token_generated"] = True
    else:
        result["source_token_generated"] = False
    
    if destination_token:
        result["destination_cms_token"] = destination_token
        result["destination_token_generated"] = True
    else:
        result["destination_token_generated"] = False
    
    # Add token generation errors if any
    if token_generation_errors:
        result["token_generation_errors"] = token_generation_errors
        result["token_generation_warnings"] = True
    else:
        result["token_generation_warnings"] = False
    
    # Update message based on token generation status
    if source_token and destination_token:
        result["message"] = f"Site setup completed for: {site_name}. Both CMS tokens generated successfully."
    elif source_token or destination_token:
        result["message"] = f"Site setup completed for: {site_name}. Partial token generation (check warnings)."
    else:
        result["message"] = f"Site setup completed for: {site_name}. Token generation skipped or failed."
    
    # Also save tokens in job_config for easy access in future steps
    # This will be persisted when the config is saved
    if source_token:
        job_config["source_cms_token"] = source_token
    if destination_token:
        job_config["destination_cms_token"] = destination_token
    
    return result



