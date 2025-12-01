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
    return render_template('index.html', steps=PROCESSING_STEPS)


@app.route('/jobs')
def jobs_list():
    """Display list of all jobs"""
    return render_template('jobs_list.html')


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
                    
                    # Get job config
                    job_config = {}
                    if os.path.exists(config_path):
                        with open(config_path, 'r', encoding='utf-8') as f:
                            job_config = json.load(f)
                    
                    # Get results to check completion status
                    completed_steps = []
                    has_results = os.path.exists(results_path)
                    if has_results:
                        with open(results_path, 'r', encoding='utf-8') as f:
                            results = json.load(f)
                            completed_steps = results.get("completed_steps", [])
                    
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


@app.route('/download/<job_id>/<filename>')
def download_file(job_id, filename):
    """Download file from job-specific folder"""
    try:
        from utils import get_job_output_folder
        job_output_folder = get_job_output_folder(job_id)
        return send_from_directory(job_output_folder, filename, as_attachment=True)
    except FileNotFoundError:
        return jsonify({"success": False, "error": "File not found"}), 404


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

