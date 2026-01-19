"""
QA Studio - Flask server with SocketIO for real-time test execution.
"""
import sys
sys.stdout.flush()  # Force unbuffered output
import os
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
# import eventlet  # Not needed with threading mode

from utils.config_models import TestRunConfig, SEOConfig
from utils.background_runner import BackgroundRunner

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Initialize SocketIO with async_mode
# Using 'threading' instead of 'eventlet' to avoid deprecation warnings
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Initialize background runner
runner = BackgroundRunner(socketio)
print(f"[STARTUP] BackgroundRunner initialized: {runner}", flush=True)
print(f"[STARTUP] Flask app: {app}", flush=True)
print(f"[STARTUP] SocketIO: {socketio}", flush=True)


@app.route('/')
def index():
    """Main dashboard page."""
    print("[DEBUG] Index page accessed", flush=True)
    return render_template('index.html')


@app.route('/api/baselines/upload', methods=['POST'])
def upload_baselines():
    """Upload baseline images from Figma."""
    if 'files' not in request.files:
        return jsonify({'success': False, 'error': 'No files provided'}), 400
    
    files = request.files.getlist('files')
    if not files:
        return jsonify({'success': False, 'error': 'No files provided'}), 400
    
    baselines_dir = os.path.join('static', 'reports', 'baselines')
    os.makedirs(baselines_dir, exist_ok=True)
    
    uploaded_count = 0
    errors = []
    
    for file in files:
        if file.filename == '':
            continue
            
        # Check if it's an image
        if not file.filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            errors.append(f'{file.filename}: Not a valid image file')
            continue
        
        try:
            # Save the file
            filepath = os.path.join(baselines_dir, file.filename)
            file.save(filepath)
            uploaded_count += 1
        except Exception as e:
            errors.append(f'{file.filename}: {str(e)}')
    
    response = {
        'success': uploaded_count > 0,
        'uploaded': uploaded_count,
        'message': f'Uploaded {uploaded_count} baseline image(s)'
    }
    
    if errors:
        response['errors'] = errors
    
    return jsonify(response)


@app.route('/api/baselines/list', methods=['GET'])
def list_baselines():
    """List all baseline images."""
    baselines_dir = os.path.join('static', 'reports', 'baselines')
    
    if not os.path.exists(baselines_dir):
        return jsonify({'success': True, 'baselines': [], 'count': 0})
    
    try:
        baselines = [
            {
                'filename': f,
                'url': f'/static/reports/baselines/{f}',
                'size': os.path.getsize(os.path.join(baselines_dir, f)),
                'created': os.path.getmtime(os.path.join(baselines_dir, f))
            }
            for f in os.listdir(baselines_dir)
            if f.lower().endswith(('.png', '.jpg', '.jpeg'))
        ]
        
        return jsonify({
            'success': True,
            'baselines': baselines,
            'count': len(baselines)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/baselines/delete', methods=['DELETE'])
def delete_baselines():
    """Delete all baseline images."""
    baselines_dir = os.path.join('static', 'reports', 'baselines')
    
    if not os.path.exists(baselines_dir):
        return jsonify({'success': True, 'message': 'No baselines to delete', 'deleted': 0})
    
    try:
        deleted_count = 0
        for filename in os.listdir(baselines_dir):
            if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                filepath = os.path.join(baselines_dir, filename)
                os.remove(filepath)
                deleted_count += 1
        
        return jsonify({
            'success': True,
            'message': f'Deleted {deleted_count} baseline image(s)',
            'deleted': deleted_count
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/run', methods=['POST'])
def start_run():
    """Start a new test run."""
    print("=" * 80, flush=True)
    print("[DEBUG] /api/run endpoint called", flush=True)
    print("=" * 80, flush=True)
    try:
        # Check if a run is already in progress
        if runner.is_running():
            print("[DEBUG] Run already in progress")
            return jsonify({
                'success': False,
                'error': 'A test run is already in progress'
            }), 400
        
        # Parse request data
        data = request.json
        print(f"[DEBUG] Request data: {data}")
        
        # Build SEO config if provided
        seo_config = None
        if 'seo_config' in data:
            seo_config = SEOConfig(**data['seo_config'])
        
        # Create test config
        config = TestRunConfig(
            base_url=data['base_url'],
            sitemap_url=data.get('sitemap_url'),
            browsers=data.get('browsers', ['chromium']),
            devices=data.get('devices', ['desktop']),
            pillars=data.get('pillars', [1, 2, 3, 4, 5, 6]),
            seo_config=seo_config
        )
        print(f"[DEBUG] Config created: {config.base_url}, pillars: {config.pillars}")
        
        # Generate run ID
        run_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        print(f"[DEBUG] Generated run_id: {run_id}")
        
        # Create reports directory
        reports_dir = os.path.join('static', 'reports', run_id)
        os.makedirs(reports_dir, exist_ok=True)
        os.makedirs(os.path.join(reports_dir, 'screenshots'), exist_ok=True)
        os.makedirs(os.path.join(reports_dir, 'logs'), exist_ok=True)
        print(f"[DEBUG] Created reports directory: {reports_dir}")
        
        # Start background run
        print(f"[DEBUG] About to call runner.start_run")
        thread = runner.start_run(run_id, config)
        print(f"[DEBUG] runner.start_run returned, thread: {thread}")
        
        return jsonify({
            'success': True,
            'run_id': run_id,
            'config': config.model_dump(mode='json')  # Use 'json' mode to serialize HttpUrl properly
        })
    
    except Exception as e:
        print(f"[ERROR] Exception in start_run: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400


@app.route('/api/run/<run_id>/cancel', methods=['POST'])
def cancel_run(run_id):
    """Cancel a running test."""
    if runner.cancel_run():
        return jsonify({'success': True, 'message': 'Run cancelled'})
    else:
        return jsonify({
            'success': False,
            'error': 'No active run to cancel'
        }), 400


@app.route('/api/run/<run_id>/status', methods=['GET'])
def get_run_status(run_id):
    """Get status of a test run."""
    current_run = runner.get_current_run()
    if current_run and current_run['run_id'] == run_id:
        return jsonify({
            'success': True,
            'status': current_run['status'],
            'duration': current_run.get('duration')
        })
    else:
        return jsonify({
            'success': False,
            'error': 'Run not found'
        }), 404


@app.route('/api/runs', methods=['GET'])
def list_runs():
    """List recent test runs."""
    reports_dir = os.path.join('static', 'reports')
    if not os.path.exists(reports_dir):
        return jsonify({'success': True, 'runs': []})
    
    runs = []
    for run_id in sorted(os.listdir(reports_dir), reverse=True)[:20]:
        # Skip the baselines folder - it's not a test run
        if run_id == 'baselines':
            continue
            
        run_dir = os.path.join(reports_dir, run_id)
        if os.path.isdir(run_dir):
            summary_path = os.path.join(run_dir, 'summary.json')
            # Get directory size and file count
            try:
                total_size = sum(
                    os.path.getsize(os.path.join(dirpath, filename))
                    for dirpath, dirnames, filenames in os.walk(run_dir)
                    for filename in filenames
                )
                file_count = sum(
                    len(files) for _, _, files in os.walk(run_dir)
                )
            except:
                total_size = 0
                file_count = 0
            
            runs.append({
                'run_id': run_id,
                'timestamp': run_id.replace('_', ' '),
                'has_summary': os.path.exists(summary_path),
                'size': total_size,
                'file_count': file_count
            })
    
    return jsonify({'success': True, 'runs': runs})


@app.route('/api/run/<run_id>/screenshots', methods=['GET'])
def get_screenshots(run_id):
    """Get list of screenshots for a run."""
    screenshots_dir = os.path.join('static', 'reports', run_id, 'screenshots')
    
    if not os.path.exists(screenshots_dir):
        return jsonify({'success': False, 'error': 'Screenshots not found'}), 404
    
    try:
        screenshots = [
            f for f in os.listdir(screenshots_dir)
            if f.lower().endswith(('.png', '.jpg', '.jpeg'))
        ]
        screenshots.sort()
        
        return jsonify({
            'success': True,
            'screenshots': screenshots,
            'count': len(screenshots)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/run/<run_id>/bug-report', methods=['GET'])
def get_bug_report(run_id):
    """Get detailed bug report for a run."""
    errors_path = os.path.join('static', 'reports', run_id, 'detailed_errors.json')
    
    if not os.path.exists(errors_path):
        return jsonify({'success': False, 'error': 'Bug report not found'}), 404
    
    try:
        with open(errors_path, 'r') as f:
            bug_report = json.load(f)
        
        return jsonify({
            'success': True,
            **bug_report
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/reports/<run_id>')
def view_report(run_id):
    """View a test run report with all files."""
    run_dir = os.path.join('static', 'reports', run_id)
    
    if not os.path.exists(run_dir):
        return f"<h1>Report Not Found</h1><p>Run {run_id} does not exist.</p>", 404
    
    # Load visual regression results if available
    visual_results = None
    visual_results_path = os.path.join(run_dir, 'visual_regression_results.json')
    if os.path.exists(visual_results_path):
        try:
            with open(visual_results_path, 'r') as f:
                visual_results = json.load(f)
        except:
            visual_results = None
    
    # Load detailed errors for bug report
    detailed_errors = None
    errors_path = os.path.join(run_dir, 'detailed_errors.json')
    if os.path.exists(errors_path):
        try:
            with open(errors_path, 'r') as f:
                detailed_errors = json.load(f)
        except:
            detailed_errors = None
    
    # Get all files in the report directory
    files = []
    for root, dirs, filenames in os.walk(run_dir):
        for filename in filenames:
            file_path = os.path.join(root, filename)
            rel_path = os.path.relpath(file_path, run_dir)
            file_size = os.path.getsize(file_path)
            file_url = f"/static/reports/{run_id}/{rel_path.replace(os.sep, '/')}"
            
            files.append({
                'name': filename,
                'path': rel_path.replace(os.sep, '/'),
                'url': file_url,
                'size': file_size,
                'is_image': filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp'))
            })
    
    # Sort files: images first, then by name
    files.sort(key=lambda x: (not x['is_image'], x['name']))
    
    # Generate HTML
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Test Report: {run_id}</title>
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                margin: 0;
                padding: 20px;
            }}
            .container {{
                max-width: 1200px;
                margin: 0 auto;
                background: white;
                border-radius: 12px;
                padding: 30px;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            }}
            h1 {{
                color: #667eea;
                margin-bottom: 10px;
            }}
            .back-link {{
                display: inline-block;
                margin-bottom: 20px;
                color: #667eea;
                text-decoration: none;
                font-weight: 500;
            }}
            .back-link:hover {{
                text-decoration: underline;
            }}
            .info {{
                background: #f0f7ff;
                padding: 15px;
                border-radius: 8px;
                margin-bottom: 20px;
                border-left: 4px solid #667eea;
            }}
            .screenshots {{
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
                gap: 20px;
                margin-bottom: 30px;
            }}
            .screenshot-card {{
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 15px;
                background: #f9f9f9;
            }}
            .screenshot-card img {{
                width: 100%;
                height: auto;
                border-radius: 5px;
                cursor: pointer;
                border: 1px solid #ccc;
            }}
            .screenshot-card img:hover {{
                opacity: 0.8;
            }}
            .screenshot-card h3 {{
                margin: 10px 0 5px;
                font-size: 0.9em;
                color: #667eea;
            }}
            .screenshot-card p {{
                margin: 0;
                font-size: 0.8em;
                color: #666;
                word-break: break-all;
            }}
            .files-section {{
                margin-top: 30px;
            }}
            .file-list {{
                list-style: none;
                padding: 0;
            }}
            .file-item {{
                padding: 10px;
                border-bottom: 1px solid #eee;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }}
            .file-item:hover {{
                background: #f9f9f9;
            }}
            .file-item a {{
                color: #667eea;
                text-decoration: none;
                flex: 1;
            }}
            .file-item a:hover {{
                text-decoration: underline;
            }}
            .file-size {{
                color: #999;
                font-size: 0.9em;
                margin-left: 10px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <a href="/" class="back-link">← Back to Dashboard</a>
            <h1>Test Report: {run_id}</h1>
            
            <div class="info">
                <strong>Run ID:</strong> {run_id}<br>
                <strong>Total Files:</strong> {len(files)}<br>
                <strong>Location:</strong> static/reports/{run_id}/
            </div>
    """
    
    # Add visual regression results OR UI health check results section
    if visual_results and 'comparisons' in visual_results and run_id != 'baselines':
        html += """
            <h2>🔍 Test Results</h2>
            <div style="background: #f0f7ff; padding: 20px; border-radius: 8px; margin-bottom: 30px; border-left: 4px solid #667eea;">
        """
        
        total_comparisons = len(visual_results['comparisons'])
        # Check if any comparisons have None match (no baseline)
        has_no_baselines = any(c.get('match') is None for c in visual_results['comparisons'])
        matches = sum(1 for c in visual_results['comparisons'] if c.get('match') is True)
        differences = sum(1 for c in visual_results['comparisons'] if c.get('match') is False)
        no_baseline_count = sum(1 for c in visual_results['comparisons'] if c.get('match') is None)
        
        if has_no_baselines:
            # UI Health Check Mode (no baselines)
            html += f"""
                <p style="font-size: 1.1em; margin-bottom: 10px;">
                    <strong>🔍 UI Health Check Mode</strong>
                </p>
                <p style="color: #666; margin-bottom: 15px;">
                    No baseline images were provided. Tests performed UI health checks instead of visual regression comparison.
                </p>
                <p style="font-size: 1.1em; margin-bottom: 10px;">
                    <strong>Checks Performed:</strong>
                </p>
                <ul style="color: #666; margin-left: 20px; margin-bottom: 15px;">
                    <li>Viewport meta tag validation</li>
                    <li>Responsive layout (horizontal overflow detection)</li>
                    <li>Critical elements visibility (header, main, nav, footer)</li>
                    <li>Broken image detection</li>
                    <li>Text readability (very small text detection)</li>
                </ul>
            """
            
            if differences > 0:
                html += f"""
                    <p style="color: #d9534f; font-weight: bold; font-size: 1.1em;">
                        ⚠️ {differences} UI issue(s) detected!
                    </p>
                """
            else:
                html += """
                    <p style="color: #5cb85c; font-weight: bold; font-size: 1.1em;">
                        ✅ All UI health checks passed!
                    </p>
                """
        else:
            # Visual Regression Mode (baselines exist)
            html += f"""
                <p style="font-size: 1.1em; margin-bottom: 10px;">
                    <strong>📊 Visual Regression Comparison</strong>
                </p>
                <p style="color: #666; margin-bottom: 15px;">
                    Comparing screenshots with uploaded Figma baseline images.
                </p>
                <p style="font-size: 1.1em; margin-bottom: 10px;">
                    <strong>Comparison Results:</strong> {matches}/{total_comparisons} matches
                </p>
            """
            if differences > 0:
                html += f"""
                    <p style="color: #d9534f; font-weight: bold;">
                        ⚠️ {differences} visual difference(s) detected!
                    </p>
                """
            else:
                html += """
                    <p style="color: #5cb85c; font-weight: bold;">
                        ✅ All screenshots match baselines perfectly!
                    </p>
                """
        
        # Show individual comparison results
        html += """
            <div style="margin-top: 15px;">
                <details style="cursor: pointer;">
                    <summary style="font-weight: bold; padding: 10px; background: white; border-radius: 5px;">
                        View Detailed Results
                    </summary>
                    <div style="margin-top: 10px; background: white; padding: 15px; border-radius: 5px;">
        """
        
        for comp in visual_results['comparisons']:
            device = comp.get('device', 'unknown')
            url = comp.get('url', 'N/A')
            match = comp.get('match')
            diff_percent = comp.get('difference')
            
            if match is None:
                # No baseline - UI health check
                status_icon = '🔍'
                status_color = '#667eea'
                status_text = 'UI Health Check'
                details = 'No baseline - UI checks performed'
            elif match:
                # Visual regression passed
                status_icon = '✅'
                status_color = '#5cb85c'
                status_text = 'Visual Match'
                details = f'Difference: {diff_percent:.2f}%' if diff_percent is not None else 'Match'
            else:
                # Visual regression failed
                status_icon = '⚠️'
                status_color = '#d9534f'
                status_text = 'Visual Difference'
                details = f'Difference: {diff_percent:.2f}%' if diff_percent is not None else 'Mismatch'
            
            html += f"""
                <div style="padding: 10px; margin-bottom: 10px; background: #f9f9f9; border-radius: 5px; border-left: 3px solid {status_color};">
                    <strong>{status_icon} {device.title()}</strong> - {url}<br>
                    <span style="color: #666; font-size: 0.9em;">
                        {status_text} - {details}
                    </span>
                </div>
            """
        
        html += """
                    </div>
                </details>
            </div>
        """
        
        # Add "Update Baselines" button if visual regression mode (baselines exist)
        if not has_no_baselines and run_id != 'baselines':
            html += f"""
                <div style="margin-top: 20px; padding: 15px; background: #fff3cd; border-radius: 5px; border: 1px solid #ffc107;">
                    <p style="margin-bottom: 10px;"><strong>⚙️ Baseline Management</strong></p>
                    <p style="font-size: 0.9em; color: #856404; margin-bottom: 10px;">
                        If the visual changes are intentional, you can update the baselines to use these screenshots as the new reference.
                    </p>
                    <button onclick="updateBaselines('{run_id}')" 
                            style="padding: 10px 20px; background: #667eea; color: white; border: none; border-radius: 5px; cursor: pointer; font-weight: bold;">
                        🔄 Update Baselines with These Screenshots
                    </button>
                    <p style="font-size: 0.8em; color: #856404; margin-top: 10px;">
                        ⚠️ This will replace the current baseline screenshots. Use with caution!
                    </p>
                </div>
            """
        
        html += """
            </div>
        """
    
    # Add detailed bug report section if errors exist
    if detailed_errors and detailed_errors.get('errors'):
        category_names = {
            'viewport_meta': 'Viewport Meta Tag Issues',
            'responsive_layout': 'Responsive Layout Issues',
            'missing_elements': 'Missing Elements',
            'broken_images': 'Broken Images',
            'text_readability': 'Text Readability Issues',
            'visual_diff': 'Visual Regression',
            'test_error': 'Test Errors',
            'other': 'Other Issues'
        }
        
        html += f"""
            <h2>🐛 Detailed Bug Report</h2>
            <div style="background: #fff5f5; padding: 20px; border-radius: 8px; margin-bottom: 30px; border-left: 4px solid #d9534f;">
                <p style="font-size: 1.2em; margin-bottom: 15px; color: #d9534f; font-weight: bold;">
                    ⚠️ {detailed_errors.get('total_errors', 0)} Issue(s) Found
                </p>
                <p style="color: #666; margin-bottom: 20px;">
                    Issues organized by category for easy debugging and fixing.
                </p>
        """
        
        errors_by_category = detailed_errors.get('errors_by_category', {})
        
        for category, category_errors in errors_by_category.items():
            category_display = category_names.get(category, category.replace('_', ' ').title())
            html += f"""
                <div style="margin-bottom: 25px; background: white; padding: 15px; border-radius: 5px; border: 1px solid #ddd;">
                    <h3 style="color: #d9534f; margin-bottom: 10px; font-size: 1.1em;">
                        📋 {category_display} ({len(category_errors)} issue(s))
                    </h3>
                    <div style="margin-left: 10px;">
            """
            
            for error in category_errors:
                device = error.get('device', 'unknown')
                url = error.get('url', 'N/A')
                message = error.get('message', 'No message')
                severity = error.get('severity', 'error')
                
                # Add extra details for visual regression
                if error.get('type') == 'visual_regression':
                    diff_pct = error.get('difference_percentage', 0)
                    diff_img = error.get('diff_image_path')
                    html += f"""
                        <div style="padding: 10px; margin-bottom: 10px; background: #f9f9f9; border-left: 3px solid #d9534f; border-radius: 3px;">
                            <div style="font-weight: bold; margin-bottom: 5px;">
                                🔴 {device.title()} - {url}
                            </div>
                            <div style="color: #666; font-size: 0.9em; margin-bottom: 5px;">
                                {message}
                            </div>
                            <div style="color: #999; font-size: 0.85em;">
                                Difference: {diff_pct}% | Severity: {severity}
                            </div>
                    """
                    if diff_img and os.path.exists(diff_img.replace('/static/', 'static/')):
                        diff_url = diff_img.replace('static/', '/static/')
                        html += f"""
                            <div style="margin-top: 5px;">
                                <a href="{diff_url}" target="_blank" style="color: #667eea; text-decoration: none;">
                                    📊 View Diff Image →
                                </a>
                            </div>
                        """
                    html += "</div>"
                else:
                    html += f"""
                        <div style="padding: 10px; margin-bottom: 10px; background: #f9f9f9; border-left: 3px solid #d9534f; border-radius: 3px;">
                            <div style="font-weight: bold; margin-bottom: 5px;">
                                🔴 {device.title()} - {url}
                            </div>
                            <div style="color: #666; font-size: 0.9em;">
                                {message}
                            </div>
                            <div style="color: #999; font-size: 0.85em; margin-top: 3px;">
                                Severity: {severity}
                            </div>
                        </div>
                    """
            
            html += """
                    </div>
                </div>
            """
        
        html += """
            </div>
        """
    
    # Add screenshots section
    screenshots = [f for f in files if f['is_image']]
    if screenshots:
        html += """
            <h2>📸 Screenshots</h2>
            <div class="screenshots">
        """
        for img in screenshots:
            device_type = '📱 Mobile' if 'mobile' in img['name'] else \
                         '📟 Tablet' if 'tablet' in img['name'] else \
                         '🖥️ Desktop' if 'desktop' in img['name'] else '📸'
            html += f"""
                <div class="screenshot-card">
                    <h3>{device_type}</h3>
                    <a href="{img['url']}" target="_blank">
                        <img src="{img['url']}" alt="{img['name']}">
                    </a>
                    <p>{img['name']}</p>
                </div>
            """
        html += """
            </div>
        """
    
    # Add all files section
    html += """
            <div class="files-section">
                <h2>📁 All Files</h2>
                <ul class="file-list">
    """
    for file in files:
        size_kb = file['size'] / 1024
        size_str = f"{size_kb:.1f} KB" if size_kb < 1024 else f"{size_kb/1024:.1f} MB"
        icon = '🖼️' if file['is_image'] else '📄'
        html += f"""
                    <li class="file-item">
                        <a href="{file['url']}" target="_blank">{icon} {file['path']}</a>
                        <span class="file-size">{size_str}</span>
                    </li>
        """
    html += """
                </ul>
            </div>
        </div>
        
        <script>
            async function updateBaselines(runId) {
                if (!confirm('Are you sure you want to update the baselines with screenshots from this run? This will replace the current baseline images.')) {
                    return;
                }
                
                try {
                    const response = await fetch(`/api/baselines/update/${runId}`, {
                        method: 'POST'
                    });
                    
                    const result = await response.json();
                    
                    if (result.success) {
                        alert(`✅ Success! Updated ${result.updated} baseline screenshot(s).`);
                        location.reload();
                    } else {
                        alert(`❌ Error: ${result.error}`);
                    }
                } catch (error) {
                    alert(`❌ Error updating baselines: ${error.message}`);
                }
            }
        </script>
    </body>
    </html>
    """
    
    return html


@app.route('/api/runs/<run_id>', methods=['DELETE'])
def delete_run(run_id):
    """Delete a test run and its reports."""
    import shutil
    
    reports_dir = os.path.join('static', 'reports', run_id)
    
    if not os.path.exists(reports_dir):
        return jsonify({
            'success': False,
            'error': 'Run not found'
        }), 404
    
    try:
        shutil.rmtree(reports_dir)
        return jsonify({
            'success': True,
            'message': f'Run {run_id} deleted successfully'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Failed to delete run: {str(e)}'
        }), 500


@app.route('/api/baselines/update/<run_id>', methods=['POST'])
def update_baselines(run_id):
    """Update baselines with screenshots from a specific run."""
    import shutil
    
    run_screenshots_dir = os.path.join('static', 'reports', run_id, 'screenshots')
    baselines_dir = os.path.join('static', 'reports', 'baselines')
    
    if not os.path.exists(run_screenshots_dir):
        return jsonify({'success': False, 'error': 'Run screenshots not found'}), 404
    
    try:
        # Create baselines directory if it doesn't exist
        os.makedirs(baselines_dir, exist_ok=True)
        
        # Copy all screenshots from the run to baselines
        updated_count = 0
        for filename in os.listdir(run_screenshots_dir):
            if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                src = os.path.join(run_screenshots_dir, filename)
                dst = os.path.join(baselines_dir, filename)
                shutil.copy2(src, dst)
                updated_count += 1
        
        return jsonify({
            'success': True,
            'message': f'Updated {updated_count} baseline screenshots',
            'updated': updated_count
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# SocketIO event handlers
@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    emit('connected', {'message': 'Connected to QA Studio'})
    print(f"Client connected: {request.sid}")


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection."""
    print(f"Client disconnected: {request.sid}")


@socketio.on('join_run')
def handle_join_run(data):
    """Join a run room for log streaming."""
    run_id = data.get('run_id')
    if run_id:
        room = f"run_{run_id}"
        join_room(room)
        emit('joined', {'run_id': run_id, 'room': room})
        print(f"Client {request.sid} joined room {room}")


@socketio.on('leave_run')
def handle_leave_run(data):
    """Leave a run room."""
    run_id = data.get('run_id')
    if run_id:
        room = f"run_{run_id}"
        leave_room(room)
        emit('left', {'run_id': run_id})
        print(f"Client {request.sid} left room {room}")


if __name__ == '__main__':
    # Ensure reports directory exists
    os.makedirs(os.path.join('static', 'reports'), exist_ok=True)
    
    # Run with threading mode (no eventlet needed)
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)
