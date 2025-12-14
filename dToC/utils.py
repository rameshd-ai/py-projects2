# utils.py

import time
import os
import json
import random
import importlib
from typing import Generator, Any, Dict

# Import config constants
from config import UPLOAD_FOLDER, PROCESSING_STEPS 

# --- Dynamic Step Module Loader ---
STEP_MODULES = {}
for step in PROCESSING_STEPS:
    step_id = step["id"]
    step_function_name = step["module"]
    try:
        # Dynamically import the module, e.g., 'processing_steps.process_xml'
        module = importlib.import_module(f"processing_steps.{step_id}")
        STEP_MODULES[step_function_name] = getattr(module, step_function_name)
    except Exception as e:
        print(f"ERROR: Could not load processing step '{step_id}' with function '{step_function_name}'. Error: {e}")
        
def format_sse(data: Dict[str, Any], event: str = 'update') -> str:
    """Formats a dictionary into a Server-Sent Event stream string."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"

def extract_file_prefix(filename: str) -> str:
    """Extracts the unique UUID prefix from the filename (e.g., 'UUID_original.xml')."""
    # Filenames are structured as: UUID_originalfilename.ext
    parts = filename.split('_', 1)
    return parts[0] if len(parts) > 1 else ''

def generate_progress_stream(filename: str) -> Generator[str, None, None]:
    
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    
    # --- CRITICAL ADDITION: Extract and store the file prefix ---
    file_prefix = extract_file_prefix(filename)
    if not file_prefix:
        yield format_sse({
            "status": "error",
            "message": "Processing failed: Could not determine unique file prefix from filename.",
            "step_id": "initial"
        }, event='update')
        # Cleanup is handled by the finally block below, but we must return here.
        return

    # Initialize previous_step_data and ensure the file_prefix is always available
    previous_step_data = {"file_prefix": file_prefix} 
    step_id = 'initial'
    last_ping_time = time.time()
    PING_INTERVAL = 30  # Send keep-alive ping every 30 seconds

    try:
        yield format_sse({"status": "start", "message": "Processing started..."}, event='update')

        for step_config in PROCESSING_STEPS:
            step_id = step_config["id"]
            step_function_name = step_config["module"]
            step_name = step_config["name"]
            error_chance = step_config["error_chance"]

            if step_function_name not in STEP_MODULES:
                 # Catch the error if the function failed to load at startup
                 raise NotImplementedError(f"Processing module for '{step_name}' not properly loaded.")

            step_function = STEP_MODULES[step_function_name]

            yield format_sse({
                "status": "in_progress",
                "step_id": step_id,
                "message": f"Step **'{step_name}'** is now in progress..."
            }, event='update')
            
            # Send keep-alive ping if needed
            current_time = time.time()
            if current_time - last_ping_time >= PING_INTERVAL:
                yield format_sse({"status": "ping", "message": "keep-alive"}, event='ping')
                last_ping_time = current_time

            # Simulate an occasional failure if error_chance > 0
            if random.random() < error_chance:
                raise Exception(f"Simulated failure during: {step_name}")

            # Execute the step function
            # Note: We pass the full filepath of the original XML file
            step_result = step_function(filepath, step_config, previous_step_data)
            
            # Update shared data with results from the current step
            previous_step_data.update(step_result)
            
            # Send keep-alive ping if needed
            current_time = time.time()
            if current_time - last_ping_time >= PING_INTERVAL:
                yield format_sse({"status": "ping", "message": "keep-alive"}, event='ping')
                last_ping_time = current_time

            yield format_sse({
                "status": "done",
                "step_id": step_id,
                "message": f"Step **'{step_name}'** successfully completed."
            }, event='update')

        # Final completion message (modified to exclude output_files)
        final_message = "Processing complete. All required operations finished successfully."
        
        yield format_sse({
            "status": "complete",
            "message": final_message,
            # 'output_files' list is intentionally removed from the payload
        }, event='update')

    except Exception as e:
        yield format_sse({
            "status": "error",
            "message": f"Processing failed at step '{step_id}': {str(e)}",
            "step_id": step_id
        }, event='update')

    finally:
        # Guarantee cleanup: delete the original uploaded file regardless of success/fail
        if os.path.exists(filepath):
            os.remove(filepath)
        yield format_sse({"status": "close"}, event='update')