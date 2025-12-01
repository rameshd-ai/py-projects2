import time
import logging
from typing import Dict, Any
from apis import generate_cms_token

logger = logging.getLogger(__name__)


def run_site_setup_step(job_id: str, step_config: Dict, workflow_context: Dict) -> Dict[str, Any]:
    """
    Step 1: Site Setup Readiness
    Validates and processes site configuration
    Generates CMS tokens for source and destination if all required fields are provided
    """
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



