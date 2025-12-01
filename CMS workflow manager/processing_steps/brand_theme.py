import time
from typing import Dict, Any


def run_brand_theme_step(job_id: str, step_config: Dict, workflow_context: Dict) -> Dict[str, Any]:
    """
    Step 2: Brand/Theme Setup
    Processes brand and theme configuration
    """
    job_config = workflow_context.get("job_config", {})
    
    # Check if site setup was completed (from previous step)
    site_setup = workflow_context.get("site_setup", {})
    if not site_setup.get("site_created"):
        raise ValueError("Site setup must be completed before brand/theme configuration")
    
    # Simulate processing
    time.sleep(step_config.get("delay", 3.0))
    
    # Process brand/theme
    font_pulled = job_config.get("fontPulled", False)
    csv_json_file = job_config.get("csvJsonFile", "")
    
    config_source = "pulled_from_site" if font_pulled else ("uploaded_file" if csv_json_file else "default")
    
    return {
        "branding_complete": True,
        "fonts_configured": True,
        "theme_applied": True,
        "config_source": config_source,
        "custom_file": csv_json_file if csv_json_file else None,
        "message": f"Brand/Theme configured from {config_source}"
    }



