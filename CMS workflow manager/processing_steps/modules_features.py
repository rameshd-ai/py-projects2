import time
from typing import Dict, Any


def run_modules_features_step(job_id: str, step_config: Dict, workflow_context: Dict) -> Dict[str, Any]:
    """Process modules and features installation"""
    job_config = workflow_context.get("job_config", {})
    time.sleep(step_config.get("delay", 3.5))
    
    modules = ["socialFeed", "htmlMenu", "faqManager", "ltoMigration", "rfpForm", "damMigration"]
    selected = [m for m in modules if job_config.get(m, False)]
    
    return {
        "modules_selected": len(selected),
        "all_modules_installed": True,
        "message": f"Installed {len(selected)} modules" if selected else "No modules selected"
    }



