import time
import json
import os
from typing import Dict, Any
from config import OUTPUT_FOLDER


def run_finalize_step(job_id: str, step_config: Dict, workflow_context: Dict) -> Dict[str, Any]:
    """Finalize workflow and generate reports"""
    job_config = workflow_context.get("job_config", {})
    time.sleep(step_config.get("delay", 2.5))
    
    site_setup = workflow_context.get("site_setup", {})
    report_filename = f"{job_id}_deployment_summary.json"
    report_path = os.path.join(OUTPUT_FOLDER, report_filename)
    
    report = {
        "job_id": job_id,
        "site_name": site_setup.get("site_name", "Unknown"),
        "status": "completed"
    }
    
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=4)
    
    return {
        "deployment_ready": True,
        "report_generated": report_filename,
        "message": "Workflow finalized"
    }



