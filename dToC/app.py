from flask import Flask, request, url_for, render_template, jsonify, Response, send_from_directory
from werkzeug.utils import secure_filename
import os
import json
import uuid
import sys

# Import config and utils files
# Note: You must ensure 'config.py' defines UPLOAD_FOLDER, MAX_CONTENT_LENGTH, and allowed_file
from config import UPLOAD_FOLDER, MAX_CONTENT_LENGTH, PROCESSING_STEPS, allowed_file
from utils import generate_progress_stream 

# Configure environment to ignore output folder before Flask app initialization
# This prevents Flask's auto-reloader from restarting when files are created in output folder
os.environ['WATCHDOG_IGNORE_PATTERNS'] = '*/output/*;*/output/**/*'

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH 

# Ensure the upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True) 

# --- Routes ---

@app.route('/', methods=['GET'])
def index():
    """Renders the main upload page, passing the processing steps for the progress list."""
    return render_template('index.html', steps=PROCESSING_STEPS) 

@app.route('/upload', methods=['POST'])
def upload_file():
    """
    Handles file upload via AJAX. Returns a JSON response with the stream URL and the unique file prefix.
    """
    if 'file' not in request.files:
        return jsonify({"success": False, "message": "No file part"}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"success": False, "message": "No selected file"}), 400
        
    if file and allowed_file(file.filename):
        # 1. Generate a unique prefix
        original_filename = secure_filename(file.filename)
        unique_prefix = str(uuid.uuid4())
        
        # 2. Construct the unique filename
        filename, extension = os.path.splitext(original_filename)
        unique_filename = f"{unique_prefix}_{filename}{extension}"
        
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(filepath)
        
        # Return JSON success message with the stream URL and the prefix
        return jsonify({
            "success": True, 
            "message": "File uploaded successfully. Awaiting configuration save...",
            "stream_url": url_for('stream', filename=unique_filename),
            "file_prefix": unique_prefix # CRITICAL: Return the prefix for config saving
        }), 200
    
    return jsonify({"success": False, "message": "File type not allowed"}), 400


@app.route('/save_config', methods=['POST'])
def save_config():
    """
    Receives configuration data and saves it to a unique config.json file.
    """
    try:
        data = request.get_json()
        file_prefix = data.get('filePrefix')
        
        if not file_prefix:
            return jsonify({"success": False, "message": "Missing file prefix for configuration."}), 400
        
        # Prepare the config file content (remove the prefix key used for naming)
        config_to_save = {
            "target_site_url": data.get('targetSiteUrl'),
            "site_id": data.get('siteId'),
            "profile_alias": data.get('profileAlias')
        }
        
        # Save the config file in the uploads directory, using the same unique prefix
        config_filename = f"{file_prefix}_config.json"
        config_filepath = os.path.join(app.config['UPLOAD_FOLDER'], config_filename)
        
        with open(config_filepath, 'w') as f:
            json.dump(config_to_save, f, indent=4)
            
        return jsonify({
            "success": True, 
            "message": f"Configuration saved to {config_filename}.",
            "config_filename": config_filename
        }), 200

    except Exception as e:
        return jsonify({"success": False, "message": f"Server error while saving config: {str(e)}"}), 500


@app.route('/stream/<filename>')
def stream(filename):
    """Streams the progress updates to the client via Server-Sent Events (SSE)."""
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    if not os.path.exists(filepath):
        error_message = {'status': 'error', 'step_id': 'initial', 'message': 'File not found to process. Please try uploading again.'}
        return Response(
            f"event: update\ndata: {json.dumps(error_message)}\n\n",
            mimetype='text/event-stream'
        )
    
    return Response(
        generate_progress_stream(filepath), 
        mimetype='text/event-stream'
    )


# --- NEW: Download Route ---
@app.route('/download_status/<filename>', methods=['GET'])
def download_status_report(filename):
    """
    Serves the status report file (e.g., CSV) from the UPLOAD_FOLDER using the 
    secure send_from_directory helper function.
    """
    try:
        return send_from_directory(
            app.config['UPLOAD_FOLDER'],
            filename,
            as_attachment=True # Forces the browser to download instead of displaying
        )
    except FileNotFoundError:
        app.logger.error(f"Download request failed: File not found in {app.config['UPLOAD_FOLDER']}: {filename}")
        # Return a 404 error with a custom message that matches the browser error
        return "File wasn't available on site", 404


# --- Run Application ---

if __name__ == '__main__':
    # Monkey patch werkzeug's reloader to ignore output folder
    # This prevents Flask from restarting when files are created in output folder during processing
    try:
        from werkzeug._reloader import WatchdogReloaderLoop
        original_trigger_reload = WatchdogReloaderLoop.trigger_reload
        output_dir_abs = os.path.abspath('output')
        
        def patched_trigger_reload(self, filename):
            """Skip reload if the file is in the output directory"""
            if filename and output_dir_abs in os.path.abspath(str(filename)):
                return
            return original_trigger_reload(self, filename)
        
        WatchdogReloaderLoop.trigger_reload = patched_trigger_reload
    except ImportError:
        # If watchdog is not available, it will fall back to stat reloader
        pass
    
    app.run(debug=True, host='0.0.0.0', port=5000)