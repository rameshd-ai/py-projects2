import os
import json
import time
import logging
from flask import Flask, render_template, request, jsonify, Response, send_from_directory
from config import PROCESSING_STEPS, UPLOAD_FOLDER, OUTPUT_FOLDER, MAX_CONTENT_LENGTH
from utils import save_job_config, generate_workflow_stream, execute_single_step

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key')

logging.basicConfig(level=logging.INFO)


@app.route('/')
def index():
    """Main wizard page - can accept job_id query parameter to resume a job"""
    job_id = request.args.get('job_id')
    return render_template('index.html', steps=PROCESSING_STEPS, job_id=job_id)


@app.route('/jobs')
def jobs_list():
    """Display list of all jobs"""
    return render_template('jobs_list.html')


@app.route('/api/job-config/<job_id>', methods=['GET'])
def get_job_config(job_id):
    """Get job configuration for resuming"""
    try:
        from utils import load_job_config
        
        job_config = load_job_config(job_id)
        if not job_config:
            return jsonify({"success": False, "error": "Job configuration not found"}), 404
        
        return jsonify({
            "success": True,
            "config": job_config
        })
    except Exception as e:
        logging.error(f"Error loading job config: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/job-results/<job_id>', methods=['GET'])
def get_job_results(job_id):
    """Get full job results including step results"""
    try:
        from utils import get_job_folder, ensure_job_folders
        
        ensure_job_folders(job_id)
        results_file = os.path.join(get_job_folder(job_id), "results.json")
        
        if os.path.exists(results_file):
            with open(results_file, 'r', encoding='utf-8') as f:
                results = json.load(f)
                return jsonify({
                    "success": True,
                    "results": results
                })
        else:
            return jsonify({
                "success": True,
                "results": {}
            })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/job-status/<job_id>', methods=['GET'])
def get_job_status(job_id):
    """Get current status of a job including completed steps"""
    try:
        from utils import get_job_folder, ensure_job_folders
        
        ensure_job_folders(job_id)
        results_file = os.path.join(get_job_folder(job_id), "results.json")
        
        if os.path.exists(results_file):
            with open(results_file, 'r', encoding='utf-8') as f:
                results = json.load(f)
                completed_steps = results.get("completed_steps", [])
                step_completion_times = results.get("step_completion_times", {})
                
                return jsonify({
                    "success": True,
                    "completed_steps": completed_steps,
                    "step_completion_times": step_completion_times
                })
        else:
            return jsonify({
                "success": True,
                "completed_steps": [],
                "step_completion_times": {}
            })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/save-config', methods=['POST'])
def save_config():
    try:
        data = request.get_json()
        if not data or 'job_id' not in data:
            return jsonify({"success": False, "error": "job_id is required"}), 400
        
        job_id = data['job_id']
        step_number = data.get('step_number', 0)
        
        # Save configuration
        success = save_job_config(job_id, data)
        if not success:
            return jsonify({"success": False, "error": "Failed to save"}), 500
        
        # Process the current step if step_number is provided
        if step_number > 0:
            try:
                step_result = execute_single_step(job_id, step_number)
                return jsonify({
                    "success": True,
                    "job_id": job_id,
                    "step_processed": True,
                    "step_result": step_result
                })
            except Exception as e:
                return jsonify({
                    "success": False,
                    "error": f"Step processing failed: {str(e)}"
                }), 500
        
        return jsonify({"success": True, "job_id": job_id})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/start-workflow', methods=['POST'])
def start_workflow():
    try:
        data = request.get_json()
        if not data or 'job_id' not in data:
            return jsonify({"success": False, "error": "job_id is required"}), 400
        
        job_id = data['job_id']
        save_job_config(job_id, data)
        
        return jsonify({
            "success": True,
            "job_id": job_id,
            "stream_url": f"/api/stream/{job_id}"
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/stream/<job_id>')
def stream_workflow(job_id):
    return Response(
        generate_workflow_stream(job_id),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache'}
    )


@app.route('/api/generate-report', methods=['POST'])
def generate_report():
    """Generate final completion report"""
    try:
        data = request.get_json()
        if not data or 'job_id' not in data:
            return jsonify({"success": False, "error": "job_id is required"}), 400
        
        job_id = data['job_id']
        from utils import load_job_config
        import json as json_lib
        import time
        
        from utils import get_job_folder, get_job_output_folder, ensure_job_folders
        
        # Ensure job folders exist
        ensure_job_folders(job_id)
        
        # Load all results
        results_file = os.path.join(get_job_folder(job_id), "results.json")
        if not os.path.exists(results_file):
            return jsonify({"success": False, "error": "No results found"}), 404
        
        with open(results_file, 'r', encoding='utf-8') as f:
            all_results = json.load(f)
        
        job_config = load_job_config(job_id)
        
        # Generate report
        report = {
            "job_id": job_id,
            "status": "completed",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "configuration": job_config,
            "results": {k: v for k, v in all_results.items() if k != "completed_steps"},
            "completed_steps": all_results.get("completed_steps", [])
        }
        
        report_path = os.path.join(get_job_output_folder(job_id), "report.json")
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=4, ensure_ascii=False)
        
        # Return download URL with job_id in path
        return jsonify({
            "success": True,
            "report_url": f"/download/{job_id}/report.json"
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/jobs', methods=['GET'])
def get_jobs_list():
    """Get list of all jobs with their details"""
    try:
        from utils import get_job_folder, get_job_output_folder, load_job_config
        import glob
        
        jobs = []
        
        # Get all job folders from uploads directory
        if os.path.exists(UPLOAD_FOLDER):
            job_folders = [d for d in os.listdir(UPLOAD_FOLDER) 
                          if os.path.isdir(os.path.join(UPLOAD_FOLDER, d)) and d.startswith('job_')]
            
            for job_id in job_folders:
                try:
                    config_path = os.path.join(get_job_folder(job_id), "config.json")
                    results_path = os.path.join(get_job_folder(job_id), "results.json")
                    report_path = os.path.join(get_job_output_folder(job_id), "report.json")
                    
                    # Validate job folder structure - skip if config.json doesn't exist
                    if not os.path.exists(config_path):
                        logging.warning(f"Skipping job {job_id}: config.json not found (incomplete/junk record)")
                        continue
                    
                    # Get job config
                    job_config = {}
                    try:
                        with open(config_path, 'r', encoding='utf-8') as f:
                            job_config = json.load(f)
                    except (json.JSONDecodeError, IOError) as e:
                        logging.warning(f"Skipping job {job_id}: Invalid or corrupted config.json - {e}")
                        continue
                    
                    # Validate job_id format - should match pattern job_timestamp_randomstring
                    if not job_id or len(job_id) < 20 or not job_id.startswith('job_'):
                        logging.warning(f"Skipping job {job_id}: Invalid job_id format")
                        continue
                    
                    # Validate that config has at least job_id field (basic validation)
                    if not isinstance(job_config, dict):
                        logging.warning(f"Skipping job {job_id}: config.json is not a valid dictionary")
                        continue
                    
                    # Get results to check completion status
                    completed_steps = []
                    has_results = os.path.exists(results_path)
                    if has_results:
                        try:
                            with open(results_path, 'r', encoding='utf-8') as f:
                                results = json.load(f)
                                completed_steps = results.get("completed_steps", [])
                        except (json.JSONDecodeError, IOError):
                            # If results.json is corrupted, just use empty list
                            completed_steps = []
                    
                    # Get file modification time
                    folder_path = get_job_folder(job_id)
                    if os.path.exists(folder_path):
                        mod_time = os.path.getmtime(folder_path)
                        created_date = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(mod_time))
                    else:
                        created_date = "Unknown"
                    
                    # Determine status
                    status = "in_progress"
                    if len(completed_steps) == len(PROCESSING_STEPS):
                        status = "completed"
                    elif len(completed_steps) > 0:
                        status = "in_progress"
                    else:
                        status = "pending"
                    
                    jobs.append({
                        "job_id": job_id,
                        "status": status,
                        "created_date": created_date,
                        "completed_steps": len(completed_steps),
                        "total_steps": len(PROCESSING_STEPS),
                        "has_report": os.path.exists(report_path),
                        "site_name": job_config.get("siteName", "N/A"),
                        "source_url": job_config.get("sourceUrl", "N/A")
                    })
                except Exception as e:
                    logging.error(f"Error processing job {job_id}: {e}")
                    continue
        
        # Sort by creation date (newest first)
        jobs.sort(key=lambda x: x.get("created_date", ""), reverse=True)
        
        return jsonify({"success": True, "jobs": jobs})
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/jobs/cleanup', methods=['POST'])
def cleanup_junk_jobs():
    """Remove invalid/junk job folders that don't have proper config.json"""
    try:
        from utils import get_job_folder
        import shutil
        
        if not os.path.exists(UPLOAD_FOLDER):
            return jsonify({"success": True, "cleaned": 0, "message": "No uploads folder found"})
        
        job_folders = [d for d in os.listdir(UPLOAD_FOLDER) 
                      if os.path.isdir(os.path.join(UPLOAD_FOLDER, d)) and d.startswith('job_')]
        
        cleaned_count = 0
        cleaned_jobs = []
        
        for job_id in job_folders:
            try:
                config_path = os.path.join(get_job_folder(job_id), "config.json")
                folder_path = get_job_folder(job_id)
                
                # Check if config.json exists and is valid
                is_junk = False
                if not os.path.exists(config_path):
                    is_junk = True
                else:
                    try:
                        with open(config_path, 'r', encoding='utf-8') as f:
                            job_config = json.load(f)
                        # Check if config is empty or invalid
                        if not isinstance(job_config, dict) or len(job_config) == 0:
                            is_junk = True
                        # Check job_id format
                        if not job_id or len(job_id) < 20 or not job_id.startswith('job_'):
                            is_junk = True
                    except (json.JSONDecodeError, IOError):
                        is_junk = True
                
                if is_junk:
                    try:
                        shutil.rmtree(folder_path)
                        cleaned_count += 1
                        cleaned_jobs.append(job_id)
                        logging.info(f"Cleaned up junk job folder: {job_id}")
                    except Exception as e:
                        logging.error(f"Failed to delete junk job folder {job_id}: {e}")
            except Exception as e:
                logging.error(f"Error checking job {job_id} for cleanup: {e}")
                continue
        
        return jsonify({
            "success": True,
            "cleaned": cleaned_count,
            "cleaned_jobs": cleaned_jobs,
            "message": f"Cleaned up {cleaned_count} junk job(s)"
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/mark-step-complete', methods=['POST'])
def mark_step_complete():
    """Explicitly mark a step as completed and update JSON"""
    try:
        data = request.get_json()
        if not data or 'job_id' not in data or 'step_number' not in data:
            return jsonify({"success": False, "error": "job_id and step_number are required"}), 400
        
        job_id = data['job_id']
        step_number = data['step_number']
        
        from utils import get_job_folder, ensure_job_folders
        
        ensure_job_folders(job_id)
        results_file = os.path.join(get_job_folder(job_id), "results.json")
        
        # Load existing results
        if os.path.exists(results_file):
            with open(results_file, 'r', encoding='utf-8') as f:
                all_results = json.load(f)
        else:
            all_results = {}
        
        # Mark step as completed
        step_id = PROCESSING_STEPS[step_number - 1]["id"]
        all_results["completed_steps"] = all_results.get("completed_steps", [])
        if step_id not in all_results["completed_steps"]:
            all_results["completed_steps"].append(step_id)
        
        # Add completion timestamp
        if "step_completion_times" not in all_results:
            all_results["step_completion_times"] = {}
        all_results["step_completion_times"][step_id] = time.strftime("%Y-%m-%d %H:%M:%S")
        
        # Save updated results
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(all_results, f, indent=4, ensure_ascii=False)
        
        return jsonify({
            "success": True,
            "message": f"Step {step_number} marked as completed",
            "step_id": step_id
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/skip-step', methods=['POST'])
def skip_step():
    """Mark a step as skipped (without executing it) and persist status."""
    try:
        data = request.get_json()
        if not data or 'job_id' not in data or 'step_number' not in data:
            return jsonify({"success": False, "error": "job_id and step_number are required"}), 400

        job_id = data['job_id']
        step_number = data['step_number']

        from utils import get_job_folder, ensure_job_folders

        ensure_job_folders(job_id)
        results_file = os.path.join(get_job_folder(job_id), "results.json")

        # Load existing results
        if os.path.exists(results_file):
            with open(results_file, 'r', encoding='utf-8') as f:
                all_results = json.load(f)
        else:
            all_results = {}

        # Resolve step id from config
        step_id = PROCESSING_STEPS[step_number - 1]["id"]

        # Add or update step result as skipped
        all_results[step_id] = {
            "status": "skipped",
            "message": "Step skipped by user from UI"
        }

        # Ensure completed_steps includes this step
        all_results["completed_steps"] = all_results.get("completed_steps", [])
        if step_id not in all_results["completed_steps"]:
            all_results["completed_steps"].append(step_id)

        # Track skip timestamp
        if "step_completion_times" not in all_results:
            all_results["step_completion_times"] = {}
        all_results["step_completion_times"][step_id] = time.strftime("%Y-%m-%d %H:%M:%S")

        # Save updated results
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(all_results, f, indent=4, ensure_ascii=False)

        return jsonify({
            "success": True,
            "message": f"Step {step_number} ({step_id}) marked as skipped",
            "step_id": step_id
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/jobs/<job_id>', methods=['DELETE'])
def delete_job(job_id):
    """Delete a job and all its associated files"""
    try:
        from utils import get_job_folder, get_job_output_folder
        import shutil
        
        job_upload_folder = get_job_folder(job_id)
        job_output_folder = get_job_output_folder(job_id)
        
        deleted_items = []
        
        # Delete upload folder
        if os.path.exists(job_upload_folder):
            shutil.rmtree(job_upload_folder)
            deleted_items.append("upload folder")
        
        # Delete output folder
        if os.path.exists(job_output_folder):
            shutil.rmtree(job_output_folder)
            deleted_items.append("output folder")
        
        if deleted_items:
            return jsonify({
                "success": True,
                "message": f"Job {job_id} deleted successfully",
                "deleted": deleted_items
            })
        else:
            return jsonify({
                "success": False,
                "error": "Job not found"
            }), 404
            
    except Exception as e:
        logging.error(f"Error deleting job {job_id}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/jobs/bulk-delete', methods=['POST'])
def bulk_delete_jobs():
    """Delete multiple jobs and all their associated files"""
    try:
        data = request.get_json()
        if not data or 'job_ids' not in data:
            return jsonify({"success": False, "error": "job_ids array is required"}), 400
        
        job_ids = data.get('job_ids', [])
        if not isinstance(job_ids, list) or len(job_ids) == 0:
            return jsonify({"success": False, "error": "job_ids must be a non-empty array"}), 400
        
        from utils import get_job_folder, get_job_output_folder
        import shutil
        
        deleted_count = 0
        failed_jobs = []
        
        for job_id in job_ids:
            try:
                job_upload_folder = get_job_folder(job_id)
                job_output_folder = get_job_output_folder(job_id)
                
                # Delete upload folder
                if os.path.exists(job_upload_folder):
                    shutil.rmtree(job_upload_folder)
                
                # Delete output folder
                if os.path.exists(job_output_folder):
                    shutil.rmtree(job_output_folder)
                
                deleted_count += 1
            except Exception as e:
                logging.error(f"Error deleting job {job_id}: {e}")
                failed_jobs.append({"job_id": job_id, "error": str(e)})
        
        if deleted_count > 0:
            response = {
                "success": True,
                "deleted_count": deleted_count,
                "message": f"Successfully deleted {deleted_count} job(s)"
            }
            if failed_jobs:
                response["failed_jobs"] = failed_jobs
                response["message"] += f", {len(failed_jobs)} failed"
            return jsonify(response)
        else:
            return jsonify({
                "success": False,
                "error": "No jobs were deleted",
                "failed_jobs": failed_jobs
            }), 500
            
    except Exception as e:
        logging.error(f"Error in bulk delete: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/download/<job_id>/<filename>')
def download_file(job_id, filename):
    """Download file from job-specific folder"""
    try:
        from utils import get_job_output_folder
        job_output_folder = get_job_output_folder(job_id)
        return send_from_directory(job_output_folder, filename, as_attachment=True)
    except FileNotFoundError:
        return jsonify({"success": False, "error": "File not found"}), 404


@app.route('/api/menu-config/<config_type>', methods=['GET'])
def get_menu_config(config_type):
    """Get menu configuration file (template or mapper)"""
    try:
        from config import BASE_DIR
        resource_dir = os.path.join(BASE_DIR, "resource")
        
        if config_type == 'template':
            file_path = os.path.join(resource_dir, "menu_payload_template.json")
        elif config_type == 'mapper':
            file_path = os.path.join(resource_dir, "menu_field_mapper.json")
        else:
            return jsonify({"success": False, "error": "Invalid config type"}), 400
        
        if not os.path.exists(file_path):
            return jsonify({"success": False, "error": "Configuration file not found"}), 404
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return jsonify({
            "success": True,
            "data": data
        })
    except Exception as e:
        logging.error(f"Error loading menu config: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/menu-config/<config_type>', methods=['POST'])
def save_menu_config(config_type):
    """Save menu configuration file (template or mapper)"""
    try:
        from config import BASE_DIR
        resource_dir = os.path.join(BASE_DIR, "resource")
        
        if config_type == 'template':
            file_path = os.path.join(resource_dir, "menu_payload_template.json")
        elif config_type == 'mapper':
            file_path = os.path.join(resource_dir, "menu_field_mapper.json")
        else:
            return jsonify({"success": False, "error": "Invalid config type"}), 400
        
        data = request.get_json()
        if not data or 'data' not in data:
            return jsonify({"success": False, "error": "Missing data in request"}), 400
        
        # Ensure resource directory exists
        os.makedirs(resource_dir, exist_ok=True)
        
        # Save the configuration
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data['data'], f, indent=2, ensure_ascii=False)
        
        logging.info(f"Menu {config_type} configuration saved successfully")
        return jsonify({
            "success": True,
            "message": f"{config_type} configuration saved successfully"
        })
    except json.JSONDecodeError as e:
        return jsonify({"success": False, "error": f"Invalid JSON: {str(e)}"}), 400
    except Exception as e:
        logging.error(f"Error saving menu config: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/process-sub-process', methods=['POST'])
def process_sub_process():
    """
    Process a specific sub-process module (e.g., FAQ Manager, Dine Menu)
    """
    try:
        from utils import load_job_config
        
        data = request.get_json()
        if not data or 'job_id' not in data or 'module_id' not in data:
            return jsonify({"success": False, "error": "job_id and module_id are required"}), 400
        
        job_id = data['job_id']
        module_id = data['module_id']
        form_data = data.get('form_data', {})
        
        # Load job configuration (or use form_data as fallback)
        job_config = load_job_config(job_id)
        
        # If job config doesn't exist or is empty, use form_data
        if not job_config:
            job_config = form_data.copy() if form_data else {}
        
        # Merge form_data into job_config to ensure latest values
        if form_data:
            job_config.update(form_data)
        
        # Ensure job_id is set
        job_config['job_id'] = job_id
        
        # Save the configuration if it was updated
        if form_data:
            from utils import save_job_config
            save_job_config(job_id, job_config)
        
        # Create workflow context
        workflow_context = {
            "job_config": job_config,
            "job_id": job_id
        }
        
        # Load previous step results (including site_setup, brand_theme, etc.)
        # This is needed for menu processing which requires site_setup data
        from utils import get_job_folder
        import os
        results_file = os.path.join(get_job_folder(job_id), "results.json")
        if os.path.exists(results_file):
            try:
                with open(results_file, 'r', encoding='utf-8') as f:
                    previous_results = json.load(f)
                    workflow_context.update(previous_results)
                logging.info(f"Loaded previous step results for job {job_id}")
            except Exception as e:
                logging.warning(f"Could not load previous results for job {job_id}: {e}")
        
        # Process based on module_id
        result = None
        if module_id == 'htmlMenu':
            from processing_steps.html_menu import run_html_menu_step
            step_config = {"delay": 1}
            result = run_html_menu_step(job_id, step_config, workflow_context)
        elif module_id == 'faqManager':
            # Get source link from request
            source_link = data.get('source_link')
            if not source_link:
                return jsonify({"success": False, "error": "source_link is required for FAQ processing"}), 400
            
            from processing_steps.faq_manager import process_faq_from_source_link
            # Add source_link to workflow context
            workflow_context["source_link"] = source_link
            result = process_faq_from_source_link(job_id, source_link)
        else:
            return jsonify({"success": False, "error": f"Unknown module_id: {module_id}"}), 400
        
        if result and result.get("success", True):
            # Mark module as processed in job config
            from utils import save_job_config
            if 'processed_modules' not in job_config:
                job_config['processed_modules'] = {}
            job_config['processed_modules'][module_id] = True
            job_config['processed_modules'][f"{module_id}_timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")
            save_job_config(job_id, job_config)
            logging.info(f"Marked {module_id} as processed for job {job_id}")
            
            return jsonify({
                "success": True,
                "module_id": module_id,
                "result": result
            })
        else:
            return jsonify({
                "success": False,
                "error": result.get("error", "Processing failed") if result else "Processing failed"
            }), 500
            
    except Exception as e:
        logging.error(f"Error processing sub-process: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/download-faq-file', methods=['GET'])
def download_faq_file():
    """
    Download FAQ output file
    """
    try:
        from utils import get_job_output_folder
        from flask import send_file
        
        job_id = request.args.get('job_id')
        file_name = request.args.get('file_name')  # Just the filename
        
        if not job_id or not file_name:
            return jsonify({"success": False, "error": "job_id and file_name are required"}), 400
        
        # Get the file path from job output folder
        output_dir = get_job_output_folder(job_id)
        file_path = os.path.join(output_dir, file_name)
        
        if not os.path.exists(file_path):
            return jsonify({"success": False, "error": "File not found"}), 404
        
        return send_file(file_path, as_attachment=True, download_name=file_name)
        
    except Exception as e:
        logging.error(f"Error downloading FAQ file: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

