"""
Flask Application for CMS Workflow Manager
Main application with routes for wizard UI and SSE streaming
"""
import os
import uuid
import logging
from flask import Flask, render_template, request, jsonify, Response, send_from_directory
from werkzeug.utils import secure_filename
from config import (
    PROCESSING_STEPS, UPLOAD_FOLDER, OUTPUT_FOLDER, 
    MAX_CONTENT_LENGTH, ALLOWED_EXTENSIONS
)
from utils import (
    save_job_config, generate_workflow_stream, allowed_file
)

# Initialize Flask app
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@app.route('/')
def index():
    """Render the main wizard interface"""
    return render_template('index.html', steps=PROCESSING_STEPS)


@app.route('/api/steps', methods=['GET'])
def get_steps():
    """Get all processing steps configuration"""
    return jsonify({
        "success": True,
        "steps": PROCESSING_STEPS,
        "total_steps": len(PROCESSING_STEPS)
    })


@app.route('/api/save-config', methods=['POST'])
def save_config():
    """
    Save wizard configuration for a job
    Expects JSON data with job_id and configuration data
    """
    try:
        data = request.get_json()
        
        if not data or 'job_id' not in data:
            return jsonify({
                "success": False,
                "error": "job_id is required"
            }), 400
        
        job_id = data['job_id']
        
        # Save configuration
        success = save_job_config(job_id, data)
        
        if success:
            logger.info(f"Saved configuration for job: {job_id}")
            return jsonify({
                "success": True,
                "job_id": job_id,
                "message": "Configuration saved successfully"
            })
        else:
            return jsonify({
                "success": False,
                "error": "Failed to save configuration"
            }), 500
            
    except Exception as e:
        logger.error(f"Error saving config: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/upload', methods=['POST'])
def upload_file():
    """
    Handle file upload (CSV, JSON, Excel files)
    Returns a unique job_id for tracking
    """
    try:
        if 'file' not in request.files:
            return jsonify({
                "success": False,
                "error": "No file provided"
            }), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({
                "success": False,
                "error": "No file selected"
            }), 400
        
        if file and allowed_file(file.filename, ALLOWED_EXTENSIONS):
            # Generate unique job ID
            job_id = str(uuid.uuid4())
            
            # Secure filename with job_id prefix
            filename = secure_filename(file.filename)
            unique_filename = f"{job_id}_{filename}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            
            # Save file
            file.save(filepath)
            
            logger.info(f"File uploaded: {unique_filename} (job_id: {job_id})")
            
            return jsonify({
                "success": True,
                "job_id": job_id,
                "filename": filename,
                "message": "File uploaded successfully"
            })
        else:
            return jsonify({
                "success": False,
                "error": f"File type not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
            }), 400
            
    except Exception as e:
        logger.error(f"Upload error: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/start-workflow', methods=['POST'])
def start_workflow():
    """
    Start the workflow processing
    Returns the SSE stream URL
    """
    try:
        data = request.get_json()
        
        if not data or 'job_id' not in data:
            return jsonify({
                "success": False,
                "error": "job_id is required"
            }), 400
        
        job_id = data['job_id']
        
        # Save final configuration before starting workflow
        save_job_config(job_id, data)
        
        logger.info(f"Starting workflow for job: {job_id}")
        
        return jsonify({
            "success": True,
            "job_id": job_id,
            "stream_url": f"/api/stream/{job_id}",
            "message": "Workflow started"
        })
        
    except Exception as e:
        logger.error(f"Start workflow error: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/stream/<job_id>')
def stream_workflow(job_id):
    """
    SSE endpoint for real-time workflow progress
    Streams processing updates to the client
    """
    logger.info(f"SSE stream started for job: {job_id}")
    
    return Response(
        generate_workflow_stream(job_id),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'  # Disable buffering for Nginx
        }
    )


@app.route('/download/<filename>')
def download_file(filename):
    """
    Download generated reports or output files
    """
    try:
        return send_from_directory(
            app.config['OUTPUT_FOLDER'],
            filename,
            as_attachment=True
        )
    except FileNotFoundError:
        return jsonify({
            "success": False,
            "error": "File not found"
        }), 404


@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "CMS Workflow Manager",
        "steps_loaded": len(PROCESSING_STEPS)
    })


@app.errorhandler(413)
def file_too_large(e):
    """Handle file size limit exceeded"""
    return jsonify({
        "success": False,
        "error": "File too large. Maximum size is 16MB."
    }), 413


@app.errorhandler(404)
def not_found(e):
    """Handle 404 errors"""
    return jsonify({
        "success": False,
        "error": "Resource not found"
    }), 404


@app.errorhandler(500)
def internal_error(e):
    """Handle internal server errors"""
    logger.error(f"Internal error: {e}")
    return jsonify({
        "success": False,
        "error": "Internal server error"
    }), 500


if __name__ == '__main__':
    # Development server
    # For production, use gunicorn or uwsgi
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True,
        threaded=True
    )

