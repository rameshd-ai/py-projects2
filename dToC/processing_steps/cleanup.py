# processing_steps/cleanup.py

import time
from typing import Dict, Any

# --- Main Step Function (Name MUST match the 'module' key in config.py) ---
def run_cleanup_step(filepath: str, step_config: dict, previous_step_data: dict = None) -> dict:
    """
    Executes the cleanup/archiving step.
    """
    time.sleep(step_config["delay"]) 

    # We return the file list passed from the previous step (process_xml) 
    # to be used in the final SSE message.
    return {
        "output_files": previous_step_data.get("output_files", []),
        "message": "Cleanup and archiving completed successfully."
    }