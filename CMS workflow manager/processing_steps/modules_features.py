import time
from typing import Dict, Any


def run_modules_features_step(job_id: str, step_config: Dict, workflow_context: Dict) -> Dict[str, Any]:
    """
    Step 4: Modules/Features
    Installs and configures selected modules and features
    """
    job_config = workflow_context.get("job_config", {})
    
    # Check if previous steps completed
    site_setup = workflow_context.get("site_setup", {})
    content_plugin = workflow_context.get("content_plugin", {})
    
    if not site_setup.get("site_created"):
        raise ValueError("Site setup must be completed first")
    
    # Simulate processing
    time.sleep(step_config.get("delay", 3.5))
    
    # Process modules
    module_mapping = {
        "socialFeed": "Social Feed (Zuicer)",
        "htmlMenu": "HTML Menu: Inner Pages",
        "faqManager": "FAQ Manager Migration",
        "ltoMigration": "LTO Migration: CMS to MiBlock",
        "rfpForm": "RFP Form Migration (Db)",
        "damMigration": "DAM Migration"
    }
    
    selected_modules = []
    for module_key, module_name in module_mapping.items():
        if job_config.get(module_key, False):
            selected_modules.append(module_name)
    
    return {
        "modules_selected": len(selected_modules),
        "installed_modules": selected_modules,
        "all_modules_installed": True,
        "message": f"Installed {len(selected_modules)} modules successfully" if selected_modules else "No additional modules selected"
    }



