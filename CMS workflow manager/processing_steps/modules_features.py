"""
Step 4: Modules/Features
Installs and configures selected modules and features
"""
import time
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


def run_modules_features_step(job_id: str, step_config: Dict, workflow_context: Dict) -> Dict[str, Any]:
    """
    Process modules and features installation
    
    Args:
        job_id: Unique job identifier
        step_config: Step configuration from config.py
        workflow_context: Shared context between steps
    
    Returns:
        dict: Step results
    """
    logger.info(f"[{job_id}] Starting modules/features setup step")
    
    # Get job configuration
    job_config = workflow_context.get("job_config", {})
    
    # Simulate processing delay
    time.sleep(step_config.get("delay", 3.5))
    
    # Extract module selections
    selected_modules = []
    module_mapping = {
        "socialFeed": "Social Feed (Zuicer)",
        "htmlMenu": "HTML Menu: Inner Pages",
        "faqManager": "FAQ Manager Migration",
        "ltoMigration": "LTO Migration: CMS to MiBlock",
        "rfpForm": "RFP Form Migration (Db)",
        "damMigration": "DAM Migration"
    }
    
    # Check which modules are enabled
    for module_key, module_name in module_mapping.items():
        if job_config.get(module_key, False):
            selected_modules.append(module_name)
            logger.info(f"[{job_id}] Installing module: {module_name}")
    
    # Process module installations
    results = {
        "modules_selected": len(selected_modules),
        "installed_modules": selected_modules,
        "all_modules_installed": True,
        "message": f"Installed {len(selected_modules)} modules successfully"
    }
    
    if len(selected_modules) == 0:
        results["message"] = "No additional modules selected"
        logger.info(f"[{job_id}] No modules were selected for installation")
    else:
        logger.info(f"[{job_id}] Installed {len(selected_modules)} modules")
    
    logger.info(f"[{job_id}] Modules/features step completed successfully")
    
    return results



