import os
import logging
from flask import Flask, render_template, request, jsonify, Response, send_from_directory
from config import PROCESSING_STEPS, UPLOAD_FOLDER, OUTPUT_FOLDER, MAX_CONTENT_LENGTH
from utils import save_job_config, generate_workflow_stream

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
        success = save_job_config(job_id, data)
        
        if success:
            return jsonify({"success": True, "job_id": job_id})
        return jsonify({"success": False, "error": "Failed to save"}), 500
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


@app.route('/download/<filename>')
def download_file(filename):
    try:
        return send_from_directory(app.config['OUTPUT_FOLDER'], filename, as_attachment=True)
    except FileNotFoundError:
        return jsonify({"success": False, "error": "File not found"}), 404


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

