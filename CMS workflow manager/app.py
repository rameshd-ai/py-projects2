# app.py
from flask import Flask, render_template, request, jsonify, Response
import uuid
import time
import json
from config import PIPELINE_STEPS

# Initialize the Flask app
app = Flask(__name__)

# In-memory storage for configurations and status (replace with database in production)
# Structure: {uuid: {config: {...}, status: {...}}}
JOB_DATA = {} 

## 🏠 Main Route
@app.route('/')
def index():
    """Serves the main wizard page."""
    # Renders the home.html which extends base.html
    return render_template('home.html')

# --- API Endpoints ---

## 💾 Save Configuration
@app.route('/save_config', methods=['POST'])
def save_config():
    """
    Receives and validates the final configuration from the wizard,
    initializes the job status, and returns a unique file_prefix (Job ID).
    """
    try:
        data = request.get_json()
    except Exception:
        return jsonify({"error": "Invalid JSON payload"}), 400

    if not data:
        return jsonify({"error": "No configuration data received"}), 400

    # 1. Generate a unique job ID
    job_id = str(uuid.uuid4())
    
    # 2. Initialize job status based on PIPELINE_STEPS from config.py
    initial_status = {
        "status": "pending",
        "message": "Job initialized, waiting to start."
    }
    
    # Initialize detailed step status
    step_status = {}
    for step_id, details in PIPELINE_STEPS.items():
        step_status[step_id] = {
            "step_num": details["step_num"],
            "status": "pending",
            "message": details["initial_message"]
        }

    # 3. Store the configuration and status
    JOB_DATA[job_id] = {
        "config": data,
        "status": initial_status,
        "steps": step_status
    }

    print(f"Job Initialized: {job_id}")
    return jsonify({"success": True, "file_prefix": job_id})

## 📊 SSE Stream Endpoint
@app.route('/stream/<job_id>')
def stream(job_id):
    """
    Generates a Server-Sent Event stream to send real-time status updates 
    for the pipeline job associated with the given job_id.
    """
    if job_id not in JOB_DATA:
        return jsonify({"error": "Job ID not found"}), 404

    def event_stream():
        # This generator function runs the mock pipeline logic
        job = JOB_DATA[job_id]
        
        # Mark overall job as running
        job["status"]["status"] = "running"
        yield f'data: {json.dumps({"status": "running", "message": "Pipeline started."})}\n\n'

        # Simulate execution of each defined step
        for step_id, step_details in PIPELINE_STEPS.items():
            
            # --- Start Step ---
            job["steps"][step_id]["status"] = "in_progress"
            job["status"]["message"] = f"Running Step {step_details['step_num']}: {step_details['name']}"
            
            # Send initial "in_progress" status
            step_update = {
                "step_id": step_id,
                "step_num": step_details["step_num"],
                "status": "in_progress",
                "message": step_details["running_message"]
            }
            yield f'data: {json.dumps(step_update)}\n\n'
            
            # Simulate work (adjust sleep time for realism)
            time.sleep(1.5) 
            
            # --- Complete Step (Success) ---
            job["steps"][step_id]["status"] = "done"
            job["status"]["message"] = f"Step {step_details['step_num']} complete."
            
            # Send "done" status
            step_update = {
                "step_id": step_id,
                "step_num": step_details["step_num"],
                "status": "done",
                "message": step_details["success_message"]
            }
            yield f'data: {json.dumps(step_update)}\n\n'
            
            # Pause between steps
            time.sleep(0.5)

        # --- Final Completion Event ---
        job["status"]["status"] = "complete"
        final_message = "All pipeline steps completed successfully."
        
        final_update = {
            "step_id": "pipeline_monitor",
            "status": "complete",
            "message": final_message
        }
        yield f'data: {json.dumps(final_update)}\n\n'

    # Set up the HTTP response for SSE
    return Response(event_stream(), mimetype="text/event-stream")

if __name__ == '__main__':
    # Use threaded=True for development environment to support concurrent requests/streams
    app.run(debug=True, threaded=True)