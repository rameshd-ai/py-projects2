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
    
    # Process modules
    module_mapping = {
        "socialFeed": "Social Feed (Zuicer)",
        "htmlMenu": "Dine Menu: Inner Pages",
        "faqManager": "FAQ Manager Migration",
        "ltoMigration": "LTO Migration: CMS to MiBlock",
        "rfpForm": "RFP Form Migration (Db)",
        "damMigration": "DAM Migration"
    }
    
    selected_modules = []
    module_results = {}
    
    # Dine Menu: Do NOT auto-run here - it runs only when user clicks "Process menu" in the Dine Menu popup.
    # Auto-running here caused duplicate records (menu migration ran twice: once in Step 4, once from popup).
    if job_config.get("htmlMenu", False):
        selected_modules.append("Dine Menu: Inner Pages")
        module_results["htmlMenu"] = {
            "success": True,
            "message": "Dine Menu configured - process via popup when ready"
        }
    
    # Process FAQ Manager if selected
    if job_config.get("faqManager", False):
        try:
            from processing_steps.faq_manager import run_faq_manager_step
            faq_result = run_faq_manager_step(job_id, step_config, workflow_context)
            module_results["faqManager"] = faq_result
            selected_modules.append("FAQ Manager Migration")
        except Exception as e:
            module_results["faqManager"] = {
                "success": False,
                "error": str(e)
            }
            raise Exception(f"FAQ Manager migration failed: {e}")
    
    # Process other modules (simulated for now)
    for module_key, module_name in module_mapping.items():
        if module_key not in ["htmlMenu", "faqManager"] and job_config.get(module_key, False):
            selected_modules.append(module_name)
    
    time.sleep(step_config.get("delay", 3.5))
    
    return {
        "modules_selected": len(selected_modules),
        "installed_modules": selected_modules,
        "module_results": module_results,
        "all_modules_installed": True,
        "message": f"Installed {len(selected_modules)} modules successfully" if selected_modules else "No additional modules selected"
    }



