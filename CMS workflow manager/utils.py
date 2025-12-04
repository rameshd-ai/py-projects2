"""
Utility functions for workflow orchestration and SSE streaming
"""
import os
import json
import time
import importlib
import logging
from typing import Dict, Any, Generator
from config import PROCESSING_STEPS, UPLOAD_FOLDER, OUTPUT_FOLDER

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Dynamically load all processing step modules
STEP_MODULES = {}

def load_step_modules():
    """Load all processing step modules dynamically"""
    global STEP_MODULES
    for step in PROCESSING_STEPS:
        try:
            module = importlib.import_module(f"processing_steps.{step['id']}")
            STEP_MODULES[step["module"]] = getattr(module, step["module"])
            logger.info(f"Loaded module: {step['module']}")
        except Exception as e:
            logger.error(f"Failed to load module {step['id']}: {e}")

# Load modules on import
load_step_modules()


def get_job_folder(job_id: str) -> str:
    """Get the job-specific folder path"""
    return os.path.join(UPLOAD_FOLDER, job_id)


def get_job_output_folder(job_id: str) -> str:
    """Get the job-specific output folder path"""
    return os.path.join(OUTPUT_FOLDER, job_id)


def ensure_job_folders(job_id: str):
    """Create job-specific folders if they don't exist"""
    job_folder = get_job_folder(job_id)
    output_folder = get_job_output_folder(job_id)
    os.makedirs(job_folder, exist_ok=True)
    os.makedirs(output_folder, exist_ok=True)


def get_config_filepath(job_id: str) -> str:
    """Get the path to the job configuration file"""
    ensure_job_folders(job_id)
    return os.path.join(get_job_folder(job_id), "config.json")


def load_job_config(job_id: str) -> Dict[str, Any]:
    """Load job configuration from JSON file"""
    config_path = get_config_filepath(job_id)
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_job_config(job_id: str, config: Dict[str, Any]) -> bool:
    """Save job configuration to JSON file"""
    try:
        config_path = get_config_filepath(job_id)
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"Failed to save config for {job_id}: {e}")
        return False


def execute_single_step(job_id: str, step_number: int) -> Dict[str, Any]:
    """Execute a single processing step"""
    if step_number < 1 or step_number > len(PROCESSING_STEPS):
        raise ValueError(f"Invalid step number: {step_number}")
    
    step_config = PROCESSING_STEPS[step_number - 1]
    step_id = step_config["id"]
    step_function_name = step_config["module"]
    
    # Load job configuration and previous results
    job_config = load_job_config(job_id)
    workflow_context = {
        "job_id": job_id,
        "job_config": job_config
    }
    
    # Ensure job folders exist
    ensure_job_folders(job_id)
    
    # Load previous step results
    results_file = os.path.join(get_job_folder(job_id), "results.json")
    if os.path.exists(results_file):
        with open(results_file, 'r', encoding='utf-8') as f:
            previous_results = json.load(f)
            workflow_context.update(previous_results)
    
    # Get step function
    step_function = STEP_MODULES.get(step_function_name)
    if not step_function:
        raise Exception(f"Step function {step_function_name} not found")
    
    print(f"\n⚙️ Executing step function: {step_function_name}", flush=True)
    print(f"⚙️ Job ID: {job_id}", flush=True)
    print(f"⚙️ Step ID: {step_id}\n", flush=True)
    
    # Execute step
    step_result = step_function(
        job_id=job_id,
        step_config=step_config,
        workflow_context=workflow_context
    )
    
    print(f"\n✅ Step function completed: {step_function_name}\n", flush=True)
    
    # Save updated job_config if it was modified by the step (e.g., tokens added)
    # Since job_config is a mutable dict, modifications in the step function update workflow_context
    updated_job_config = workflow_context.get("job_config", {})
    
    # Check if tokens were added (indicating config was modified)
    has_tokens = "source_cms_token" in updated_job_config or "destination_cms_token" in updated_job_config
    if has_tokens:
        save_job_config(job_id, updated_job_config)
        logger.info(f"Updated job config saved for {job_id} (CMS tokens added)")
    
    # Save results
    if not os.path.exists(results_file):
        all_results = {}
    else:
        with open(results_file, 'r', encoding='utf-8') as f:
            all_results = json.load(f)
    
    all_results[step_id] = step_result
    all_results["completed_steps"] = all_results.get("completed_steps", [])
    if step_id not in all_results["completed_steps"]:
        all_results["completed_steps"].append(step_id)
    
    with open(results_file, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=4, ensure_ascii=False)
    
    # Check if step was skipped based on result message
    step_message = step_result.get("message", "").lower()
    is_skipped = any(keyword in step_message for keyword in ["skipped", "not enabled", "not selected", "no modules"])
    
    return {
        "success": True,
        "step_id": step_id,
        "step_name": step_config["name"],
        "result": step_result,
        "status": "skipped" if is_skipped else "success"
    }


def format_sse(data: Dict[str, Any]) -> str:
    """Format data as Server-Sent Event"""
    return f"data: {json.dumps(data)}\n\n"


def generate_workflow_stream(job_id: str) -> Generator[str, None, None]:
    """
    Main workflow orchestrator - executes all processing steps
    and streams progress via SSE
    """
    logger.info(f"Starting workflow for job: {job_id}")
    
    # Load job configuration
    job_config = load_job_config(job_id)
    
    # Shared context between steps
    workflow_context = {
        "job_id": job_id,
        "start_time": time.time(),
        "completed_steps": [],
        "job_config": job_config
    }
    
    try:
        yield format_sse({"status": "start", "message": "Workflow started"})
        
        # Execute each processing step
        for idx, step_config in enumerate(PROCESSING_STEPS, 1):
            step_id = step_config["id"]
            step_name = step_config["name"]
            step_function_name = step_config["module"]
            
            yield format_sse({
                "status": "in_progress",
                "step_id": step_id,
                "step_name": step_name,
                "message": f"Processing: {step_name}"
            })
            
            # Get the step function
            step_function = STEP_MODULES.get(step_function_name)
            
            if not step_function:
                raise Exception(f"Step function {step_function_name} not found")
            
            # Execute the step
            step_start_time = time.time()
            try:
                step_result = step_function(
                    job_id=job_id,
                    step_config=step_config,
                    workflow_context=workflow_context
                )
                
                # Update workflow context with step results
                workflow_context[step_id] = step_result
                workflow_context["completed_steps"].append(step_id)
                
                step_duration = time.time() - step_start_time
                
                # Notify: Step completed
                yield format_sse({
                    "status": "done",
                    "step_id": step_id,
                    "step_name": step_name,
                    "message": f"✓ Completed: {step_name}"
                })
                
                logger.info(f"Step {step_name} completed in {step_duration:.2f}s")
                
            except Exception as step_error:
                # Step-level error handling
                logger.error(f"Step {step_name} failed: {step_error}")
                raise Exception(f"Step '{step_name}' failed: {str(step_error)}")
        
        # Calculate total workflow time
        total_duration = time.time() - workflow_context["start_time"]
        
        # Generate final report
        report_path = generate_completion_report(job_id, workflow_context, total_duration)
        
        yield format_sse({
            "status": "complete",
            "message": "Workflow completed!",
            "report_url": f"/download/{job_id}/report.json"
        })
        
        logger.info(f"Workflow {job_id} completed in {total_duration:.2f}s")
        
    except Exception as e:
        # Workflow-level error handling
        logger.error(f"Workflow {job_id} failed: {e}")
        yield format_sse({"status": "error", "message": f"Workflow failed: {str(e)}"})
    
    finally:
        # Cleanup: Send close event
        yield format_sse({"status": "close"})


def generate_completion_report(job_id: str, workflow_context: Dict, total_duration: float) -> str:
    """Generate a completion report for the workflow"""
    ensure_job_folders(job_id)
    report_path = os.path.join(get_job_output_folder(job_id), "report.json")
    
    report = {
        "job_id": job_id,
        "status": "completed",
        "total_duration_seconds": round(total_duration, 2),
        "completed_steps": workflow_context["completed_steps"],
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "configuration": workflow_context.get("job_config", {}),
        "results": {}
    }
    
    # Add results from each step
    for step in PROCESSING_STEPS:
        step_id = step["id"]
        if step_id in workflow_context:
            report["results"][step_id] = workflow_context[step_id]
    
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=4, ensure_ascii=False)
    
    logger.info(f"Generated report: {report_path}")
    return report_path


def allowed_file(filename: str, allowed_extensions: set) -> bool:
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions



