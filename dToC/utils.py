import os
import json
import time
import importlib
import traceback
from typing import Dict, Any, Generator, Optional

from config import PROCESSING_STEPS


def _build_sse_event(payload: Dict[str, Any]) -> str:
    """
    Helper to format a dict as a Server-Sent Event (SSE) 'update' event.
    """
    return f"event: update\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def generate_progress_stream(filepath: str) -> Generator[str, None, None]:
    """
    Main generator used by the /stream route to run all processing steps
    and stream progress updates to the browser via SSE.

    Args:
        filepath: Full path to the uploaded XML file.
    Yields:
        SSE-formatted strings with JSON payloads describing progress.
    """
    # Derive the unique file prefix from the uploaded filename
    basename = os.path.basename(filepath)  # "<uuid>_OriginalName.xml"
    name_without_ext = basename.rsplit(".", 1)[0]
    file_prefix = name_without_ext.split("_", 1)[0] or name_without_ext

    total_steps = len(PROCESSING_STEPS)
    step_data: Dict[str, Any] = {"file_prefix": file_prefix}

    # Initial event
    yield _build_sse_event(
        {
            "status": "start",
            "step_id": "initial",
            "message": "Processing pipeline started.",
            "file_prefix": file_prefix,
        }
    )

    for index, step in enumerate(PROCESSING_STEPS, start=1):
        step_id = step.get("id")
        step_name = step.get("name", step_id)
        module_func_name = step.get("module")

        # Notify client that this step is starting
        # Include site_id if already available in step_data (set by generate_token step)
        _site_id_for_event = step_data.get("site_id") if isinstance(step_data, dict) else None
        yield _build_sse_event(
            {
                "status": "in_progress",
                "step_id": step_id,
                "step_index": index,
                "total_steps": total_steps,
                "message": f"Starting step {index}/{total_steps}: {step_name}",
                "site_id": _site_id_for_event,
            }
        )

        try:
            import time as time_module
            step_start_time = time_module.time()
            
            # Dynamically import the processing module based on the step id
            # e.g. id="process_xml"  ->  processing_steps.process_xml
            module = importlib.import_module(f"processing_steps.{step_id}")
            step_func = getattr(module, module_func_name)

            # Call signatures vary slightly between steps, so handle the known cases:
            if step_id == "process_xml":
                # First step works directly from the uploaded file path
                step_data = step_func(filepath, step)
            elif step_id in ("process_home_page", "process_assembly"):
                # These steps accept a dict and optionally file_prefix via kwargs
                step_data = step_func(step_data, step, {"file_prefix": file_prefix}, file_name=file_prefix)
            else:
                # Default pattern: (input_filepath, step_config, previous_step_data)
                step_data = step_func(filepath, step, step_data)

            # Calculate duration
            step_duration = round(time_module.time() - step_start_time, 2)

            # Small delay to keep UI in sync with configured delays (non-blocking for correctness)
            delay = step.get("delay", 0)
            if isinstance(delay, (int, float)) and delay > 0:
                time.sleep(min(delay, 3.0))

            # Emit success for this step (frontend expects "done" status with duration)
            yield _build_sse_event(
                {
                    "status": "done",
                    "step_id": step_id,
                    "step_index": index,
                    "total_steps": total_steps,
                    "message": f"Completed: {step_name}",
                    "duration": step_duration,
                }
            )

        except Exception as exc:
            error_message = f"Processing failed at step '{step_name}': {exc}"
            tb_str = traceback.format_exc()
            
            # Calculate duration if step_start_time was set
            try:
                step_duration = round(time.time() - step_start_time, 2)
            except:
                step_duration = 0

            # Emit error event
            yield _build_sse_event(
                {
                    "status": "error",
                    "step_id": step_id,
                    "step_index": index,
                    "total_steps": total_steps,
                    "message": error_message,
                    "traceback": tb_str,
                    "duration": step_duration,
                }
            )
            # Stop further processing on first hard failure
            return

    # All steps completed successfully
    output_files = None
    if isinstance(step_data, dict):
        output_files = step_data.get("output_files")

    yield _build_sse_event(
        {
            "status": "complete",
            "step_id": "final",
            "message": "All processing steps completed successfully.",
            "file_prefix": file_prefix,
            "output_files": output_files,
        }
    )


def generate_rerun_stream(file_prefix: str) -> Generator[str, None, None]:
    """
    Runs only the 'process_assembly' step for an already-processed file_prefix.
    Used by the Page Status modal re-run feature to replay selected pages.
    """
    # Find the assembly step config from PROCESSING_STEPS
    assembly_step = next((s for s in PROCESSING_STEPS if s.get("id") == "process_assembly"), None)
    if not assembly_step:
        yield _build_sse_event({"status": "error", "step_id": "process_assembly",
                                "message": "process_assembly step not found in config."})
        return

    yield _build_sse_event({
        "status": "start",
        "step_id": "initial",
        "message": f"Re-run assembly started for prefix: {file_prefix}",
        "file_prefix": file_prefix,
    })

    yield _build_sse_event({
        "status": "in_progress",
        "step_id": "process_assembly",
        "step_index": 1,
        "total_steps": 1,
        "message": "Assembling CMS Pages (re-run)...",
    })

    step_start_time = time.time()
    try:
        module = importlib.import_module("processing_steps.process_assembly")
        step_func = getattr(module, assembly_step["module"])
        step_data = {"file_prefix": file_prefix}
        step_data = step_func(step_data, assembly_step, {"file_prefix": file_prefix}, file_name=file_prefix, is_rerun=True)

        step_duration = round(time.time() - step_start_time, 2)

        output_files = step_data.get("output_files") if isinstance(step_data, dict) else None

        yield _build_sse_event({
            "status": "done",
            "step_id": "process_assembly",
            "step_index": 1,
            "total_steps": 1,
            "message": "Re-run assembly completed.",
            "duration": step_duration,
        })

        yield _build_sse_event({
            "status": "complete",
            "step_id": "final",
            "message": "Re-run completed successfully.",
            "file_prefix": file_prefix,
            "output_files": output_files,
        })

    except Exception as exc:
        step_duration = round(time.time() - step_start_time, 2)
        tb_str = traceback.format_exc()
        yield _build_sse_event({
            "status": "error",
            "step_id": "process_assembly",
            "step_index": 1,
            "total_steps": 1,
            "message": f"Re-run failed: {exc}",
            "traceback": tb_str,
            "duration": step_duration,
        })
