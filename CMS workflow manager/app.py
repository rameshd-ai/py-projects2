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

