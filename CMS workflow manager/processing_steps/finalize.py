import time
import json
import os
from typing import Dict, Any
from config import OUTPUT_FOLDER


def run_finalize_step(job_id: str, step_config: Dict, workflow_context: Dict) -> Dict[str, Any]:
    """
    Step 5: Finalize & Deploy
    Final processing, validation, and report generation
    """
    job_config = workflow_context.get("job_config", {})
    
    # Verify all previous steps completed
    site_setup = workflow_context.get("site_setup", {})
    brand_theme = workflow_context.get("brand_theme", {})
    content_plugin = workflow_context.get("content_plugin", {})
    modules_features = workflow_context.get("modules_features", {})
    
    if not site_setup.get("site_created"):
        raise ValueError("Site setup must be completed first")
    if not brand_theme.get("branding_complete"):
        raise ValueError("Brand/Theme setup must be completed first")
    
    # Simulate processing
    time.sleep(step_config.get("delay", 2.5))
    
    # Generate deployment checklist
    deployment_checklist = {
        "site_created": site_setup.get("site_created", False),
        "branding_applied": brand_theme.get("branding_complete", False),
        "content_migrated": content_plugin.get("miblock_migration_enabled", False),
        "modules_installed": modules_features.get("all_modules_installed", False),
        "ready_for_deployment": True
    }
    
    # Generate summary report
    from utils import get_job_output_folder, ensure_job_folders
    
    ensure_job_folders(job_id)
    site_name = site_setup.get("site_name", "Unknown")
    report_filename = "deployment_summary.json"
    report_path = os.path.join(get_job_output_folder(job_id), report_filename)
    
    report = {
        "job_id": job_id,
        "site_name": site_name,
        "site_url": site_setup.get("site_url", ""),
        "status": "completed",
        "deployment_checklist": deployment_checklist,
        "statistics": {
            "pages_migrated": content_plugin.get("pages_migrated", 0),
            "content_blocks": content_plugin.get("content_blocks_created", 0),
            "modules_installed": modules_features.get("modules_selected", 0)
        },
        "configuration": {
            "source_url": job_config.get("sourceUrl", ""),
            "destination_url": job_config.get("destinationUrl", ""),
            "site_language": job_config.get("siteLanguage", "en"),
            "site_country": job_config.get("siteCountry", "us")
        }
    }
    
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=4, ensure_ascii=False)
    
    return {
        "deployment_ready": True,
        "report_generated": report_filename,
        "all_steps_completed": True,
        "deployment_checklist": deployment_checklist,
        "message": f"Workflow finalized and ready for deployment: {site_name}"
    }



