from flask import Flask, request, url_for, render_template, jsonify, Response, send_from_directory
from werkzeug.utils import secure_filename
import os
import json
import uuid
import sys
import shutil
import logging

# Force stdout/stderr to UTF-8 so unicode characters (arrows, emojis, etc.)
# don't crash the Windows cp1252 console handler
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Ensure console logging - add StreamHandler so logs appear in terminal
def _setup_console_logging():
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    # Add our handler if none exists, or if no handler writes to stdout
    has_stdout = any(getattr(h, 'stream', None) is sys.stdout for h in root.handlers)
    if not has_stdout:
        h = logging.StreamHandler(sys.stdout)
        h.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s'))
        root.addHandler(h)
_setup_console_logging()

# Import config and utils files
# Note: You must ensure 'config.py' defines UPLOAD_FOLDER, MAX_CONTENT_LENGTH, and allowed_file
from config import UPLOAD_FOLDER, MAX_CONTENT_LENGTH, PROCESSING_STEPS, allowed_file
from utils import generate_progress_stream, generate_rerun_stream
from processing_steps.process_assembly import load_settings, publish_created_pages_from_pending_file, load_pending_pages_to_publish

# Configure environment to ignore output and uploads folders before Flask app initialization
# This prevents Flask's auto-reloader from restarting when files are created during processing
os.environ['WATCHDOG_IGNORE_PATTERNS'] = '*/output/*;*/output/**/*;*/uploads/*;*/uploads/**/*'

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
        
        # Save the config file in site-specific folder if site_id is provided
        site_id = data.get('siteId')
        if site_id:
            site_folder = os.path.join(app.config['UPLOAD_FOLDER'], str(site_id))
            os.makedirs(site_folder, exist_ok=True)
        else:
            site_folder = app.config['UPLOAD_FOLDER']
        
        # Save the config file in the uploads directory, using the same unique prefix
        config_filename = f"{file_prefix}_config.json"
        config_filepath = os.path.join(site_folder, config_filename)
        
        with open(config_filepath, 'w', encoding='utf-8') as f:
            json.dump(config_to_save, f, indent=4)
        
        # Also save a copy to uploads root so process_menu_navigation and other steps find it
        root_config_path = os.path.join(app.config['UPLOAD_FOLDER'], config_filename)
        if root_config_path != config_filepath:
            with open(root_config_path, 'w', encoding='utf-8') as f:
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


# --- NEW: List Processed Projects ---
@app.route('/api/projects', methods=['GET'])
def list_projects():
    """
    Lists all processed projects by scanning site_id folders in uploads/ and output/.
    Returns a list of projects with their site_id and folder information.
    """
    try:
        uploads_folder = app.config['UPLOAD_FOLDER']
        output_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')
        
        projects = []
        site_ids = set()
        
        # Scan uploads folder for site_id directories
        if os.path.exists(uploads_folder):
            for item in os.listdir(uploads_folder):
                item_path = os.path.join(uploads_folder, item)
                if os.path.isdir(item_path) and item.isdigit():
                    site_ids.add(item)
        
        # Scan output folder for site_id directories
        if os.path.exists(output_folder):
            for item in os.listdir(output_folder):
                item_path = os.path.join(output_folder, item)
                if os.path.isdir(item_path) and item.isdigit():
                    site_ids.add(item)
        
        # Build project list with details
        for site_id in sorted(site_ids, key=lambda x: int(x) if x.isdigit() else 0, reverse=True):
            uploads_path = os.path.join(uploads_folder, site_id)
            output_path = os.path.join(output_folder, site_id)
            
            has_uploads = os.path.exists(uploads_path) and os.path.isdir(uploads_path)
            has_output = os.path.exists(output_path) and os.path.isdir(output_path)
            
            # Count files in uploads folder
            file_count = 0
            if has_uploads:
                try:
                    file_count = len([f for f in os.listdir(uploads_path) if os.path.isfile(os.path.join(uploads_path, f))])
                except:
                    pass
            
            # Try to get site URL from config file
            site_url = None
            if has_uploads:
                try:
                    # Look for config files in the uploads folder
                    for filename in os.listdir(uploads_path):
                        if filename.endswith('_config.json'):
                            config_path = os.path.join(uploads_path, filename)
                            try:
                                with open(config_path, 'r', encoding='utf-8') as f:
                                    config_data = json.load(f)
                                    # Try both 'target_site_url' and 'site_url' keys
                                    site_url = config_data.get('target_site_url') or config_data.get('site_url')
                                    app.logger.info(f"Found config file {filename} for site_id {site_id}, target_site_url: {config_data.get('target_site_url')}, site_url: {site_url}")
                                    if site_url and isinstance(site_url, str) and site_url.strip():
                                        break
                            except Exception as e:
                                app.logger.error(f"Error reading config file {filename}: {e}")
                                pass
                except Exception as e:
                    app.logger.debug(f"Error scanning uploads folder for site_id {site_id}: {e}")
                    pass
            
            # Fallback: if no URL found, use site_id
            if not site_url or (isinstance(site_url, str) and site_url.strip() == ''):
                site_url = f"Site ID: {site_id}"
            
            # Ensure site_url is always a string
            if not site_url:
                site_url = f"Site ID: {site_id}"
            
            projects.append({
                "site_id": str(site_id),
                "site_url": str(site_url),
                "has_uploads": has_uploads,
                "has_output": has_output,
                "file_count": file_count
            })
        
        return jsonify({
            "success": True,
            "projects": projects
        }), 200
        
    except Exception as e:
        app.logger.error(f"Error listing projects: {str(e)}")
        return jsonify({
            "success": False,
            "message": f"Error listing projects: {str(e)}"
        }), 500


# --- NEW: Delete Project ---
@app.route('/api/projects/<site_id>', methods=['DELETE'])
def delete_project(site_id):
    """
    Deletes a project by removing the site_id folder from both uploads/ and output/.
    """
    try:
        # Validate site_id (should be numeric)
        if not site_id.isdigit():
            return jsonify({
                "success": False,
                "message": "Invalid site_id. Must be numeric."
            }), 400
        
        uploads_folder = app.config['UPLOAD_FOLDER']
        output_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')
        
        uploads_path = os.path.join(uploads_folder, site_id)
        output_path = os.path.join(output_folder, site_id)
        
        deleted_folders = []
        errors = []
        
        # Delete uploads folder
        if os.path.exists(uploads_path) and os.path.isdir(uploads_path):
            try:
                shutil.rmtree(uploads_path)
                deleted_folders.append(f"uploads/{site_id}")
            except Exception as e:
                errors.append(f"Failed to delete uploads/{site_id}: {str(e)}")
        
        # Delete output folder
        if os.path.exists(output_path) and os.path.isdir(output_path):
            try:
                shutil.rmtree(output_path)
                deleted_folders.append(f"output/{site_id}")
            except Exception as e:
                errors.append(f"Failed to delete output/{site_id}: {str(e)}")
        
        if deleted_folders:
            message = f"Successfully deleted: {', '.join(deleted_folders)}"
            if errors:
                message += f". Errors: {', '.join(errors)}"
            return jsonify({
                "success": True,
                "message": message,
                "deleted_folders": deleted_folders
            }), 200
        else:
            return jsonify({
                "success": False,
                "message": f"No folders found for site_id {site_id}",
                "errors": errors
            }), 404
            
    except Exception as e:
        app.logger.error(f"Error deleting project {site_id}: {str(e)}")
        return jsonify({
            "success": False,
            "message": f"Error deleting project: {str(e)}"
        }), 500


# --- NEW: Get Global Config ---
@app.route('/api/global_config', methods=['GET'])
def get_global_config():
    """
    Returns the current global_config.json content.
    """
    try:
        global_config_path = os.path.join(app.config['UPLOAD_FOLDER'], 'global_config.json')
        
        if not os.path.exists(global_config_path):
            config_data = {"debug_page_filter": ""}
            return jsonify({"success": True, "config": config_data}), 200

        with open(global_config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)

        return jsonify({
            "success": True,
            "config": config_data
        }), 200
        
    except Exception as e:
        app.logger.error(f"Error reading global config: {str(e)}")
        return jsonify({
            "success": False,
            "message": f"Error reading global config: {str(e)}"
        }), 500


# --- Page Status: parse assembly_debug.log for a site ---
@app.route('/api/projects/<site_id>/page_status', methods=['GET'])
def get_page_status(site_id):
    log_file = os.path.join(app.config['UPLOAD_FOLDER'], site_id, 'assembly_debug.log')
    if not os.path.exists(log_file):
        return jsonify({"success": False, "message": "No assembly log found for this project"}), 404

    pages = {}          # key: hierarchy string -> page info dict
    last_content_key = None   # hierarchy key of last page that had content (for mapping_payload correlation)

    try:
        # Read all lines, then find the LAST assembly_run_start marker so we
        # only show data from the most recent run (log is append-only across runs).
        with open(log_file, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()

        last_run_start_idx = 0
        for i, line in enumerate(all_lines):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                if entry.get('section') == 'assembly_run_start':
                    last_run_start_idx = i
            except json.JSONDecodeError:
                continue

        # Only parse lines from the latest run onwards
        lines_to_parse = all_lines[last_run_start_idx:]

        for line in lines_to_parse:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            section   = entry.get('section', '')
            data      = entry.get('data', {})
            timestamp = entry.get('timestamp', '')

            if section == 'level1_page_start':
                page_name = data.get('page_name', 'UNKNOWN')
                key = page_name
                if key not in pages:
                    pages[key] = {
                        'page_name': page_name,
                        'hierarchy': page_name,
                        'level': 1,
                        'status': 'in_progress',
                        'page_id': None,
                        'timestamp': timestamp,
                    }

            elif section == 'level2_page_start':
                page_name = data.get('page_name', 'UNKNOWN')
                key = data.get('hierarchy', page_name)
                if key not in pages:
                    pages[key] = {
                        'page_name': page_name,
                        'hierarchy': key,
                        'level': 2,
                        'status': 'in_progress',
                        'page_id': None,
                        'timestamp': timestamp,
                    }

            elif section == 'page_content_check':
                page_name   = data.get('page_name', 'UNKNOWN')
                key         = data.get('hierarchy', page_name)
                has_content = data.get('has_content', False)
                if has_content:
                    last_content_key = key
                else:
                    if key in pages:
                        pages[key]['status'] = 'no_content'
                    last_content_key = None

            elif section == 'mapping_payload':
                page_id = data.get('page_id')
                if last_content_key and last_content_key in pages:
                    pages[last_content_key]['status'] = 'success'
                    pages[last_content_key]['page_id'] = page_id
                    last_content_key = None

            elif section == 'page_no_content':
                page_name = data.get('page_name', 'UNKNOWN')
                key = data.get('hierarchy', page_name)
                if key not in pages:
                    pages[key] = {
                        'page_name': page_name,
                        'hierarchy': key,
                        'level': data.get('page_level', 1),
                        'status': 'no_content',
                        'page_id': None,
                        'timestamp': timestamp,
                    }
                else:
                    pages[key]['status'] = 'no_content'

            elif section == 'level2_page_skipped':
                page_name = data.get('page_name', 'UNKNOWN')
                key = data.get('hierarchy', page_name)  # use hierarchy if available
                if key not in pages:
                    pages[key] = {
                        'page_name': page_name,
                        'hierarchy': key,
                        'level': 2,
                        'status': 'skipped',
                        'page_id': None,
                        'timestamp': timestamp,
                    }
                else:
                    pages[key]['status'] = 'skipped'

            elif section == 'page_error':
                page_name = data.get('page_name', 'UNKNOWN')
                key = data.get('hierarchy', page_name)
                if key not in pages:
                    pages[key] = {
                        'page_name': page_name,
                        'hierarchy': key,
                        'level': data.get('page_level', 1),
                        'status': 'error',
                        'page_id': None,
                        'timestamp': timestamp,
                    }
                else:
                    pages[key]['status'] = 'error'

            elif section == 'assembly_stopped':
                # Mark any still-in_progress pages as stopped
                for p in pages.values():
                    if p['status'] == 'in_progress':
                        p['status'] = 'stopped'

        pages_list = sorted(pages.values(), key=lambda x: x.get('timestamp', ''))

        # Mark pages that are created but not yet published as 'publish_pending' (not 'success')
        pending_entries = load_pending_pages_to_publish(int(site_id))
        pending_page_ids = {int(e.get('page_id')) for e in pending_entries if e.get('page_id') is not None}
        for p in pages_list:
            if p.get('status') == 'success' and p.get('page_id') is not None:
                if int(p['page_id']) in pending_page_ids:
                    p['status'] = 'publish_pending'

        # Detect assembly state
        is_stopped = any(p['status'] == 'stopped' for p in pages_list)
        stuck_in_progress = any(p['status'] == 'in_progress' for p in pages_list)

        stop_flag_file = os.path.join(app.config['UPLOAD_FOLDER'], site_id, 'STOP_REQUESTED')
        stop_requested = os.path.exists(stop_flag_file)

        # ASSEMBLY_RUNNING is created when assembly starts and deleted when it ends.
        # If it's absent but pages are still in_progress, the server was killed — mark them stopped.
        running_flag_file = os.path.join(app.config['UPLOAD_FOLDER'], site_id, 'ASSEMBLY_RUNNING')
        assembly_running = os.path.exists(running_flag_file)

        if stuck_in_progress and not assembly_running:
            for p in pages_list:
                if p['status'] == 'in_progress':
                    p['status'] = 'stopped'
            stuck_in_progress = False
            is_stopped = True

        is_running = assembly_running and stuck_in_progress and not stop_requested

        # Check if completed_pages.json exists (indicates at least one page was done before stop/kill)
        completed_pages_file = os.path.join(app.config['UPLOAD_FOLDER'], site_id, 'completed_pages.json')
        has_completed_pages = os.path.exists(completed_pages_file)
        can_resume = has_completed_pages and (is_stopped or stuck_in_progress)

        summary = {
            'total':           len(pages_list),
            'success':         sum(1 for p in pages_list if p['status'] == 'success'),
            'publish_pending': sum(1 for p in pages_list if p['status'] == 'publish_pending'),
            'no_content':      sum(1 for p in pages_list if p['status'] == 'no_content'),
            'skipped':         sum(1 for p in pages_list if p['status'] == 'skipped'),
            'in_progress':     sum(1 for p in pages_list if p['status'] == 'in_progress'),
            'stopped':         sum(1 for p in pages_list if p['status'] == 'stopped'),
            'error':           sum(1 for p in pages_list if p['status'] == 'error'),
        }
        pending_count = len(pending_entries)
        return jsonify({
            "success": True,
            "site_id": site_id,
            "pages": pages_list,
            "summary": summary,
            "pending_count": pending_count,
            "can_resume": can_resume,
            "is_stopped": is_stopped or stuck_in_progress,
            "is_running": is_running,
        }), 200

    except Exception as e:
        app.logger.error(f"Error reading page status for site {site_id}: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


# --- Re-run selected pages for a site ---
@app.route('/api/projects/<site_id>/rerun_pages', methods=['POST'])
def rerun_pages(site_id):
    """
    Accepts a list of page names, sets debug_page_filter in the site global_config,
    and returns a stream URL for the re-run.
    """
    try:
        data = request.get_json() or {}
        pages = data.get('pages', [])
        if not pages:
            return jsonify({"success": False, "message": "No pages provided."}), 400

        site_folder = os.path.join(app.config['UPLOAD_FOLDER'], site_id)
        os.makedirs(site_folder, exist_ok=True)

        # Find file_prefix from root uploads (config files live there, not in site subfolder)
        upload_root = app.config['UPLOAD_FOLDER']
        file_prefix = None
        best_mtime = 0
        for fname in os.listdir(upload_root):
            if fname.endswith('_config.json') and not fname.startswith('global'):
                fpath = os.path.join(upload_root, fname)
                if not os.path.isfile(fpath):
                    continue
                try:
                    with open(fpath, 'r', encoding='utf-8') as f:
                        cfg_data = json.load(f)
                    if str(cfg_data.get('site_id', '')) == str(site_id):
                        mtime = os.path.getmtime(fpath)
                        if mtime > best_mtime:
                            best_mtime = mtime
                            file_prefix = cfg_data.get('file_prefix') or fname.replace('_config.json', '')
                except Exception:
                    continue
        if not file_prefix:
            return jsonify({"success": False, "message": "No config file found for this site. Cannot determine file prefix."}), 404

        # Update debug_page_filter in site global_config
        global_config_path = os.path.join(site_folder, 'global_config.json')
        global_cfg = {}
        if os.path.exists(global_config_path):
            try:
                with open(global_config_path, 'r', encoding='utf-8') as f:
                    global_cfg = json.load(f)
            except Exception:
                pass
        global_cfg['debug_page_filter'] = ', '.join(pages)
        with open(global_config_path, 'w', encoding='utf-8') as f:
            json.dump(global_cfg, f, indent=2)

        # Also update root global_config so the assembly step finds it
        root_global_config = os.path.join(app.config['UPLOAD_FOLDER'], 'global_config.json')
        root_cfg = {}
        if os.path.exists(root_global_config):
            try:
                with open(root_global_config, 'r', encoding='utf-8') as f:
                    root_cfg = json.load(f)
            except Exception:
                pass
        root_cfg['debug_page_filter'] = ', '.join(pages)
        with open(root_global_config, 'w', encoding='utf-8') as f:
            json.dump(root_cfg, f, indent=2)

        return jsonify({
            "success": True,
            "file_prefix": file_prefix,
            "pages": pages,
            "stream_url": f"/stream_rerun/{file_prefix}"
        }), 200

    except Exception as e:
        app.logger.error(f"Error setting up rerun for site {site_id}: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/projects/<site_id>/stop', methods=['POST'])
def stop_assembly(site_id):
    """Creates a STOP_REQUESTED sentinel file so the running assembly halts at the next page boundary."""
    try:
        site_folder = os.path.join(app.config['UPLOAD_FOLDER'], site_id)
        os.makedirs(site_folder, exist_ok=True)
        stop_file = os.path.join(site_folder, 'STOP_REQUESTED')
        with open(stop_file, 'w', encoding='utf-8') as f:
            f.write('stop')
        app.logger.info(f"[STOP] Stop requested for site {site_id}")
        return jsonify({"success": True, "message": "Stop requested. Assembly will halt at the next page boundary."}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/projects/<site_id>/resume', methods=['POST'])
def resume_assembly(site_id):
    """Sets is_resume=true in global_config and returns an SSE stream URL to continue from where assembly stopped."""
    try:
        site_folder = os.path.join(app.config['UPLOAD_FOLDER'], site_id)
        if not os.path.exists(site_folder):
            return jsonify({"success": False, "message": f"Site folder not found for site_id {site_id}"}), 404

        # Find the most recent file_prefix whose config matches this site_id.
        # Config files live at the ROOT uploads/ folder (not inside the site subfolder).
        upload_root = app.config['UPLOAD_FOLDER']
        file_prefix = None
        best_mtime = 0
        for fname in os.listdir(upload_root):
            if fname.endswith('_config.json') and not fname.startswith('global'):
                fpath = os.path.join(upload_root, fname)
                if not os.path.isfile(fpath):
                    continue
                try:
                    with open(fpath, 'r', encoding='utf-8') as f:
                        cfg_data = json.load(f)
                    if str(cfg_data.get('site_id', '')) == str(site_id):
                        mtime = os.path.getmtime(fpath)
                        if mtime > best_mtime:
                            best_mtime = mtime
                            file_prefix = cfg_data.get('file_prefix') or fname.replace('_config.json', '')
                except Exception:
                    continue
        if not file_prefix:
            return jsonify({"success": False, "message": "No config file found for this site."}), 404

        # Set is_resume=True and clear the page filter so ALL remaining pages are processed
        for cfg_path in [
            os.path.join(site_folder, 'global_config.json'),
            os.path.join(app.config['UPLOAD_FOLDER'], 'global_config.json'),
        ]:
            cfg = {}
            if os.path.exists(cfg_path):
                try:
                    with open(cfg_path, 'r', encoding='utf-8') as f:
                        cfg = json.load(f)
                except Exception:
                    pass
            cfg['is_resume'] = True
            cfg['debug_page_filter'] = ''
            with open(cfg_path, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, indent=2)

        # Remove any leftover stop flag
        stop_file = os.path.join(site_folder, 'STOP_REQUESTED')
        if os.path.exists(stop_file):
            os.remove(stop_file)

        return jsonify({
            "success": True,
            "file_prefix": file_prefix,
            "stream_url": f"/stream_rerun/{file_prefix}"
        }), 200

    except Exception as e:
        app.logger.error(f"Error setting up resume for site {site_id}: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


def _get_file_prefix_and_settings_for_site(site_id):
    """Find file_prefix for this site_id and load settings (target_site_url, cms_login_token). Returns (file_prefix, settings) or (None, None)."""
    upload_root = app.config['UPLOAD_FOLDER']
    site_folder = os.path.join(upload_root, str(site_id))
    for folder in (site_folder, upload_root):
        if not os.path.isdir(folder):
            continue
        for fname in os.listdir(folder):
            if fname.endswith('_config.json') and not fname.startswith('global'):
                fpath = os.path.join(folder, fname)
                if not os.path.isfile(fpath):
                    continue
                try:
                    with open(fpath, 'r', encoding='utf-8') as f:
                        cfg_data = json.load(f)
                    if str(cfg_data.get('site_id', '')) != str(site_id):
                        continue
                    file_prefix = cfg_data.get('file_prefix') or fname.replace('_config.json', '')
                    settings = load_settings(file_prefix, int(site_id))
                    if settings:
                        return file_prefix, settings
                except Exception:
                    continue
    return None, None


@app.route('/api/projects/<site_id>/publish_created_pages', methods=['GET', 'POST'])
def publish_created_pages(site_id):
    """GET: return pending count for UI. POST: publish only created-but-unpublished pages (one-click after stop)."""
    try:
        if request.method == 'GET':
            pending = load_pending_pages_to_publish(int(site_id))
            return jsonify({"success": True, "pending_count": len(pending)}), 200

        site_folder = os.path.join(app.config['UPLOAD_FOLDER'], str(site_id))
        if not os.path.exists(site_folder):
            return jsonify({"success": False, "message": f"Site folder not found for site_id {site_id}"}), 404

        pending = load_pending_pages_to_publish(int(site_id))
        if not pending:
            return jsonify({
                "success": True,
                "published": 0,
                "total": 0,
                "message": "No created-but-unpublished pages found. Run assembly and create at least one page, or pages may already be published."
            }), 200

        _fp, settings = _get_file_prefix_and_settings_for_site(site_id)
        if not settings:
            return jsonify({"success": False, "message": "Could not load API config for this site. Save config with token first."}), 404

        api_base_url = settings.get("target_site_url")
        raw_token = settings.get("cms_login_token")
        if not api_base_url or not raw_token or not str(raw_token).strip():
            return jsonify({"success": False, "message": "API URL or CMS token missing in config."}), 400

        api_headers = {
            'Content-Type': 'application/json',
            'ms_cms_clientapp': 'ProgrammingApp',
            'Authorization': f'Bearer {raw_token}',
        }

        success_count, total_count, err = publish_created_pages_from_pending_file(api_base_url, api_headers, int(site_id))
        return jsonify({
            "success": True,
            "published": success_count,
            "total": total_count,
            "message": f"Published {success_count} of {total_count} created page(s)." if total_count else "No pages to publish."
        }), 200
    except Exception as e:
        app.logger.exception("publish_created_pages failed")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/stream_rerun/<file_prefix>')
def stream_rerun(file_prefix):
    """SSE endpoint that re-runs only the assembly step for an existing file_prefix."""
    return Response(
        generate_rerun_stream(file_prefix),
        mimetype='text/event-stream'
    )


# --- NEW: Update Global Config ---
@app.route('/api/global_config', methods=['POST'])
def update_global_config():
    """
    Updates the global_config.json file with new values.
    """
    try:
        data = request.get_json()
        debug_page_filter = (data.get('debug_page_filter') or '').strip()

        global_config_path = os.path.join(app.config['UPLOAD_FOLDER'], 'global_config.json')
        os.makedirs(os.path.dirname(global_config_path), exist_ok=True)

        config_data = {}
        if os.path.exists(global_config_path):
            try:
                with open(global_config_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
            except Exception:
                pass

        config_data["debug_page_filter"] = debug_page_filter

        with open(global_config_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=2)
        
        return jsonify({
            "success": True,
            "message": "Global config updated successfully",
            "config": config_data
        }), 200
        
    except Exception as e:
        app.logger.error(f"Error updating global config: {str(e)}")
        return jsonify({
            "success": False,
            "message": f"Error updating global config: {str(e)}"
        }), 500


# --- Run Application ---

if __name__ == '__main__':
    # Disable reloader to prevent connection breaks during processing
    # The reloader watches all Python files and can trigger restarts during long operations
    # For development, manually restart the server when code changes are needed
    # For production, reloader should always be disabled
    
    # Alternative: More aggressive monkey patch if you want to keep reloader but ignore data folders
    try:
        from werkzeug._reloader import WatchdogReloaderLoop
        original_trigger_reload = WatchdogReloaderLoop.trigger_reload
        output_dir_abs = os.path.abspath('output')
        uploads_dir_abs = os.path.abspath(UPLOAD_FOLDER)
        processing_steps_abs = os.path.abspath('processing_steps')
        
        def patched_trigger_reload(self, filename):
            """Skip reload for data files and processing step modules during runtime"""
            if filename:
                file_abs = os.path.abspath(str(filename))
                file_lower = file_abs.lower()
                
                # Ignore output and uploads folders
                if output_dir_abs in file_abs or uploads_dir_abs in file_abs:
                    return
                
                # Ignore JSON, CSV, TXT files in any location
                if file_lower.endswith(('.json', '.csv', '.txt', '.xml', '.zip')):
                    return
                
                # Only reload on actual Python code changes in main app files
                # Ignore changes in processing_steps during active processing
                if processing_steps_abs in file_abs:
                    # Allow reload only if it's a critical file change
                    # For now, ignore all processing_steps changes during runtime
                    return
            
            return original_trigger_reload(self, filename)
        
        WatchdogReloaderLoop.trigger_reload = patched_trigger_reload
    except (ImportError, AttributeError):
        # If watchdog is not available or structure changed, fall back to stat reloader
        pass
    
    # DISABLE RELOADER to prevent connection breaks
    # Set use_reloader=False to completely disable auto-reload
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False, use_debugger=True)