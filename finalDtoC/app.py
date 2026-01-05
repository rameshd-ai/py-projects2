"""
Flask app for Figma to CMS Component Generator
"""
from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
import os
import json
import requests
from datetime import datetime
from uuid import uuid4
from dotenv import load_dotenv

# Import API clients
from api.figma import FigmaClient
from api.claude import ClaudeClient
from api.cms import CMSClient

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# Configuration
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Projects storage file
PROJECTS_FILE = 'projects.json'

def load_projects():
    """Load projects from JSON file"""
    if os.path.exists(PROJECTS_FILE):
        try:
            with open(PROJECTS_FILE, 'r') as f:
                return json.load(f)
        except:
            return []
    return []

def save_projects(projects):
    """Save projects to JSON file"""
    with open(PROJECTS_FILE, 'w') as f:
        json.dump(projects, f, indent=2)

def deduplicate_projects(projects):
    """Merge duplicate projects based on site URL, profile alias, and site ID (project-wise/site-wise)"""
    seen = {}
    merged = []
    
    for project in projects:
        # Create a unique key based on site details (project-wise/site-wise)
        # This ensures one project per unique site configuration
        key = (
            project.get('target_site_url', '').strip(),
            project.get('profile_alias', '').strip(),
            project.get('site_id', '').strip()
        )
        
        if key in seen:
            # Merge components from duplicate into existing project
            existing = seen[key]
            existing_components = existing.get('components', [])
            new_components = project.get('components', [])
            
            # If project has old format (figma_url at root), convert it
            if project.get('figma_url') and not new_components:
                new_components = [{
                    'id': str(uuid4()),
                    'figma_url': project.get('figma_url'),
                    'status': project.get('status', 'pending'),
                    'created_at': project.get('created_at', datetime.now().isoformat())
                }]
            
            # Merge components (avoid duplicates based on figma_url)
            for comp in new_components:
                # Check if component with same figma_url already exists
                if not any(c.get('figma_url') == comp.get('figma_url') for c in existing_components):
                    existing_components.append(comp)
            
            existing['components'] = existing_components
            # Keep the earliest created_at date
            if project.get('created_at') < existing.get('created_at', '9999-12-31'):
                existing['created_at'] = project.get('created_at')
            # Update to latest updated_at
            if project.get('updated_at', '') > existing.get('updated_at', ''):
                existing['updated_at'] = project.get('updated_at')
            # Use the most recent project name if different
            if project.get('project_name') and project.get('project_name') != existing.get('project_name'):
                existing['project_name'] = project.get('project_name')
        else:
            # First time seeing this project/site combination
            # Convert old format to new format if needed
            if project.get('figma_url') and 'components' not in project:
                project['components'] = [{
                    'id': str(uuid4()),
                    'figma_url': project.get('figma_url'),
                    'status': project.get('status', 'pending'),
                    'created_at': project.get('created_at', datetime.now().isoformat())
                }]
                # Remove old figma_url from root if it exists
                if 'figma_url' in project:
                    del project['figma_url']
            
            seen[key] = project
            merged.append(project)
    
    return merged

# Helper function to get API clients with tokens from session or env
def get_figma_client(token=None):
    """Get Figma client with token from session, parameter, or env"""
    api_token = token or session.get('figma_token') or os.getenv('FIGMA_ACCESS_TOKEN')
    if not api_token:
        return None
    try:
        return FigmaClient(access_token=api_token)
    except Exception:
        return None

def get_claude_client(token=None):
    """Get Claude client with token from session, parameter, or env"""
    api_token = token or session.get('claude_token') or os.getenv('ANTHROPIC_API_KEY')
    if not api_token:
        return None
    try:
        return ClaudeClient(api_key=api_token)
    except Exception:
        return None

def get_cms_client(base_url=None, api_key=None):
    """Get CMS client with credentials from session, parameters, or env"""
    cms_url = base_url or session.get('cms_base_url') or os.getenv('CMS_BASE_URL')
    cms_key = api_key or session.get('cms_api_key') or os.getenv('CMS_API_KEY')
    if not cms_key:
        return None
    try:
        return CMSClient(base_url=cms_url, api_key=cms_key)
    except Exception:
        return None

@app.route('/')
def index():
    """Main page with Figma URL input form"""
    # Load current tokens from session to pre-fill form
    return render_template('index.html', 
                          figma_token=session.get('figma_token', ''),
                          claude_token=session.get('claude_token', ''),
                          cms_base_url=session.get('cms_base_url', ''),
                          cms_api_key=session.get('cms_api_key', ''))

@app.route('/api/settings', methods=['GET', 'POST'])
def settings():
    """Get or save API tokens"""
    if request.method == 'GET':
        return jsonify({
            'figma_token': session.get('figma_token', '') or os.getenv('FIGMA_ACCESS_TOKEN', ''),
            'claude_token': session.get('claude_token', '') or os.getenv('ANTHROPIC_API_KEY', ''),
            'cms_base_url': session.get('cms_base_url', '') or os.getenv('CMS_BASE_URL', ''),
            'cms_api_key': session.get('cms_api_key', '') or os.getenv('CMS_API_KEY', '')
        })
    
    # POST - Save tokens
    try:
        data = request.get_json()
        
        # Save to session (treat empty strings as None)
        if 'figma_token' in data:
            session['figma_token'] = data['figma_token'] if data['figma_token'] else None
        if 'claude_token' in data:
            session['claude_token'] = data['claude_token'] if data['claude_token'] else None
        if 'cms_base_url' in data:
            session['cms_base_url'] = data['cms_base_url'] if data['cms_base_url'] else None
        if 'cms_api_key' in data:
            session['cms_api_key'] = data['cms_api_key'] if data['cms_api_key'] else None
        
        # Test connections
        test_results = {}
        
        figma_token = data.get('figma_token', '').strip()
        if figma_token:
            figma = get_figma_client(figma_token)
            test_results['figma'] = 'connected' if figma else 'failed'
        
        claude_token = data.get('claude_token', '').strip()
        if claude_token:
            claude = get_claude_client(claude_token)
            test_results['claude'] = 'connected' if claude else 'failed'
        
        cms_key = data.get('cms_api_key', '').strip()
        if cms_key:
            cms = get_cms_client(data.get('cms_base_url', '').strip() or None, cms_key)
            test_results['cms'] = 'connected' if cms else 'failed'
        
        return jsonify({
            'status': 'success',
            'message': 'Settings saved successfully',
            'test_results': test_results
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/projects', methods=['GET', 'POST'])
def projects():
    """Get all projects or create a new project"""
    if request.method == 'GET':
        try:
            projects_list = load_projects()
            # Deduplicate projects before returning
            projects_list = deduplicate_projects(projects_list)
            save_projects(projects_list)  # Save deduplicated version
            return jsonify({'projects': projects_list})
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    # POST - Create new project
    try:
        data = request.get_json()
        
        # Create project
        project = {
            'id': str(uuid4()),
            'project_name': data.get('project_name', 'Unnamed Project'),
            'target_site_url': data.get('target_site_url', ''),
            'profile_alias': data.get('profile_alias', ''),
            'site_id': data.get('site_id', ''),
            'figma_url': data.get('figma_url', ''),
            'status': 'pending',
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        
        projects_list = load_projects()
        projects_list.append(project)
        save_projects(projects_list)
        
        return jsonify({
            'status': 'success',
            'message': 'Project created successfully',
            'project': project
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/projects/<project_id>', methods=['GET', 'DELETE'])
def project_detail(project_id):
    """Get or delete a specific project"""
    try:
        projects_list = load_projects()
        # Deduplicate first
        projects_list = deduplicate_projects(projects_list)
        project = next((p for p in projects_list if p['id'] == project_id), None)
        
        if not project:
            return jsonify({'error': 'Project not found'}), 404
        
        if request.method == 'GET':
            return jsonify({'project': project})
        
        # DELETE
        projects_list = [p for p in projects_list if p['id'] != project_id]
        save_projects(projects_list)
        
        return jsonify({
            'status': 'success',
            'message': 'Project deleted successfully'
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/generate', methods=['POST'])
def generate_component():
    """Generate CMS component from Figma URL"""
    try:
        data = request.get_json()
        figma_url = data.get('figma_url')
        project_name = data.get('project_name')
        target_site_url = data.get('target_site_url')
        profile_alias = data.get('profile_alias')
        site_id = data.get('site_id')
        project_id = data.get('project_id')  # If adding component to existing project
        
        if not figma_url:
            return jsonify({'error': 'Figma URL is required'}), 400
        
        projects_list = load_projects()
        component_id = None
        
        # If adding to existing project, update that project with new component
        if project_id:
            existing_project = next((p for p in projects_list if p['id'] == project_id), None)
            if existing_project:
                # Initialize components array if it doesn't exist
                if 'components' not in existing_project:
                    existing_project['components'] = []
                
                # Create new component entry
                component = {
                    'id': str(uuid4()),
                    'figma_url': figma_url,
                    'status': 'processing',
                    'created_at': datetime.now().isoformat()
                }
                
                existing_project['components'].append(component)
                existing_project['updated_at'] = datetime.now().isoformat()
                existing_project['status'] = 'processing'  # Update project status
                
                # Update project in list
                for i, p in enumerate(projects_list):
                    if p['id'] == project_id:
                        projects_list[i] = existing_project
                        break
                
                save_projects(projects_list)
                project = existing_project
                component_id = component['id']
            else:
                # Project not found, create new one
                project = {
                    'id': str(uuid4()),
                    'project_name': project_name or 'Unnamed Project',
                    'target_site_url': target_site_url or '',
                    'profile_alias': profile_alias or '',
                    'site_id': site_id or '',
                    'components': [{
                        'id': str(uuid4()),
                        'figma_url': figma_url,
                        'status': 'processing',
                        'created_at': datetime.now().isoformat()
                    }],
                    'status': 'processing',
                    'created_at': datetime.now().isoformat(),
                    'updated_at': datetime.now().isoformat()
                }
                projects_list.append(project)
                save_projects(projects_list)
                component_id = project['components'][0]['id']
        else:
            # Check if project with same name and details already exists
            existing_project = next((
                p for p in projects_list 
                if p.get('project_name') == project_name 
                and p.get('target_site_url') == target_site_url
                and p.get('profile_alias') == profile_alias
                and p.get('site_id') == site_id
            ), None)
            
            if existing_project:
                # Add component to existing project
                if 'components' not in existing_project:
                    existing_project['components'] = []
                
                component = {
                    'id': str(uuid4()),
                    'figma_url': figma_url,
                    'status': 'processing',
                    'created_at': datetime.now().isoformat()
                }
                
                existing_project['components'].append(component)
                existing_project['updated_at'] = datetime.now().isoformat()
                existing_project['status'] = 'processing'
                
                # Update project in list
                for i, p in enumerate(projects_list):
                    if p['id'] == existing_project['id']:
                        projects_list[i] = existing_project
                        break
                
                save_projects(projects_list)
                project = existing_project
                component_id = component['id']
            else:
                # Create new project with first component
                project = {
                    'id': str(uuid4()),
                    'project_name': project_name or 'Unnamed Project',
                    'target_site_url': target_site_url or '',
                    'profile_alias': profile_alias or '',
                    'site_id': site_id or '',
                    'components': [{
                        'id': str(uuid4()),
                        'figma_url': figma_url,
                        'status': 'processing',
                        'created_at': datetime.now().isoformat()
                    }],
                    'status': 'processing',
                    'created_at': datetime.now().isoformat(),
                    'updated_at': datetime.now().isoformat()
                }
                projects_list.append(project)
                save_projects(projects_list)
                component_id = project['components'][0]['id']
        
        # Get clients with tokens from request or session
        figma_client = get_figma_client(data.get('figma_token'))
        if not figma_client:
            return jsonify({'error': 'Figma API not configured. Please enter your Figma access token in Settings.'}), 500
        
        claude_client = get_claude_client(data.get('claude_token'))
        if not claude_client:
            return jsonify({'error': 'Claude API not configured. Please enter your Anthropic API key in Settings.'}), 500
        
        # Step 1: Download screenshot from Figma
        screenshot_path = figma_client.get_screenshot(figma_url)
        
        # Step 2: Generate HTML using Claude
        html_content = claude_client.generate_html(screenshot_path)
        
        # Update project and component status
        projects_list = load_projects()
        for i, p in enumerate(projects_list):
            if p['id'] == project['id']:
                p['status'] = 'completed'
                p['updated_at'] = datetime.now().isoformat()
                
                # Update the specific component if we have component_id
                if component_id and 'components' in p:
                    for j, comp in enumerate(p['components']):
                        if comp['id'] == component_id:
                            p['components'][j]['status'] = 'completed'
                            p['components'][j]['screenshot_path'] = screenshot_path
                            p['components'][j]['html_length'] = len(html_content)
                            p['components'][j]['updated_at'] = datetime.now().isoformat()
                            break
                elif 'components' in p and len(p['components']) > 0:
                    # Update the last component if no component_id specified
                    p['components'][-1]['status'] = 'completed'
                    p['components'][-1]['screenshot_path'] = screenshot_path
                    p['components'][-1]['html_length'] = len(html_content)
                    p['components'][-1]['updated_at'] = datetime.now().isoformat()
                else:
                    # For backward compatibility, update main project fields
                    p['screenshot_path'] = screenshot_path
                    p['html_length'] = len(html_content)
                
                projects_list[i] = p
                break
        save_projects(projects_list)
        
        # TODO: Phase 2 - Implement LangGraph workflow for full component generation
        # For now, return HTML and screenshot path
        # When LangGraph is implemented, include final_report in response
        
        response_data = {
            'status': 'success',
            'message': 'HTML generated successfully (Phase 1 complete)',
            'project_id': project['id'],
            'figma_url': figma_url,
            'screenshot_path': screenshot_path,
            'html_preview': html_content[:500] + '...' if len(html_content) > 500 else html_content,
            'html_length': len(html_content),
            'note': 'Full component generation with LangGraph will be implemented in Phase 2'
        }
        
        # If LangGraph workflow was used, include final report
        # This will be populated when Phase 2 is complete
        # final_report = state.get('final_report')
        # if final_report:
        #     response_data['verification_report'] = final_report
        
        return jsonify(response_data)
    
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        # Update project status to error
        try:
            projects_list = load_projects()
            for p in projects_list:
                if p['id'] == project.get('id'):
                    p['status'] = 'error'
                    p['error'] = str(e)
                    p['updated_at'] = datetime.now().isoformat()
                    
                    # Update component status if exists
                    if 'components' in p and component_id:
                        for comp in p['components']:
                            if comp['id'] == component_id:
                                comp['status'] = 'error'
                                comp['error'] = str(e)
                                break
                    break
            save_projects(projects_list)
        except:
            pass
        return jsonify({'error': str(e)}), 500

@app.route('/api/refresh-library', methods=['POST'])
def refresh_library():
    """Refresh component library - shows trained components from projects"""
    try:
        # Refresh library shows trained components from projects
        # CMS settings in Settings tab are for a different purpose (not used here)
        # Training uses site details from popup form instead
        projects_list = load_projects()
        
        # Count trained components across all projects
        total_trained = 0
        for project in projects_list:
            components = project.get('components', [])
            trained = [c for c in components if c.get('status') == 'completed']
            total_trained += len(trained)
        
        return jsonify({
            'status': 'success',
            'message': f'Library refreshed. Found {total_trained} trained components across {len(projects_list)} projects.',
            'trained_components_count': total_trained,
            'projects_count': len(projects_list),
            'note': 'Library shows components trained from your projects. Use "Train All" to train new components with site details.'
        })
    
    except Exception as e:
        return jsonify({
            'error': f'Unexpected error: {str(e)}',
            'hint': 'Please try again'
        }), 500

@app.route('/api/train-library', methods=['POST'])
def train_library():
    """Train all new components from the library"""
    try:
        data = request.get_json() or {}
        
        # Get target site information from form (same as Step 2)
        target_site_url = data.get('target_site_url', '')
        profile_alias = data.get('profile_alias', '')
        site_id = data.get('site_id', '')
        
        if not target_site_url or not profile_alias or not site_id:
            return jsonify({
                'error': 'Target Site URL, Profile Alias, and Site ID are required',
                'hint': 'Please fill in all fields in the training form'
            }), 400
        
        cms_base_url = data.get('cms_base_url') or session.get('cms_base_url') or os.getenv('CMS_BASE_URL', '')
        cms_api_key = data.get('cms_api_key') or session.get('cms_api_key') or os.getenv('CMS_API_KEY', '')
        
        # Check if CMS credentials are configured
        if not cms_base_url or not cms_api_key:
            return jsonify({
                'error': 'CMS API not configured. Please enter your CMS API credentials in Settings → CMS Settings tab.',
                'hint': 'You need to provide both CMS Base URL and CMS API Key'
            }), 400
        
        # Check if URL is still the placeholder
        if 'example.com' in cms_base_url or cms_base_url == 'https://api.cms.example.com':
            return jsonify({
                'error': 'CMS Base URL is not configured. Please update it in Settings → CMS Settings tab.',
                'hint': 'The current URL appears to be a placeholder. Please enter your actual CMS API URL.'
            }), 400
        
        cms_client = get_cms_client(cms_base_url, cms_api_key)
        
        if not cms_client:
            return jsonify({
                'error': 'Failed to initialize CMS client. Please check your CMS API credentials in Settings.',
                'hint': 'Verify that your CMS Base URL and API Key are correct'
            }), 500
        
        # Get all components from CMS using site details to download fresh data
        try:
            components = cms_client.get_components(
                site_url=target_site_url,
                profile_alias=profile_alias,
                site_id=site_id
            )
        except requests.exceptions.ConnectionError as e:
            return jsonify({
                'error': f'Cannot connect to CMS API at {cms_base_url}',
                'hint': 'Please check: 1) The CMS Base URL is correct, 2) Your internet connection, 3) The CMS server is accessible'
            }), 500
        except requests.exceptions.HTTPError as e:
            return jsonify({
                'error': f'CMS API returned an error: {str(e)}',
                'hint': 'Please check your CMS API Key and ensure you have proper permissions'
            }), 500
        except Exception as e:
            return jsonify({
                'error': f'Error connecting to CMS: {str(e)}',
                'hint': 'Please verify your CMS API credentials in Settings → CMS Settings'
            }), 500
        
        # TODO: Phase 3 - Check which components are already trained in database
        # For now, we'll assume all components need training
        # In Phase 3, we'll check the database for trained components
        
        trained_components = []
        failed_components = []
        already_trained = 0
        
        # Process only new components (not already trained)
        for component in components:
            component_id = component.get('id') or component.get('component_id')
            
            # TODO: Phase 3 - Check if component is already trained in database
            # For now, we'll process all components
            # is_trained = check_if_trained(component_id)  # Phase 3
            
            try:
                # Download fresh component data using site details
                # TODO: Phase 3 - Generate embeddings and store in database
                # For now, download component files and mark as processed
                try:
                    component_files = cms_client.download_component_files(
                        component_id,
                        output_dir=f'components/{site_id}_{profile_alias}'
                    )
                except Exception as download_error:
                    # If download fails, continue without files
                    component_files = {}
                    print(f"Warning: Could not download files for component {component_id}: {download_error}")
                
                # Store target site information with component for future reference
                trained_components.append({
                    'id': component_id,
                    'name': component.get('name', 'Unnamed'),
                    'status': 'trained',
                    'trained_at': datetime.now().isoformat(),
                    'target_site_url': target_site_url,
                    'profile_alias': profile_alias,
                    'site_id': site_id,
                    'files': component_files,  # Store downloaded file paths
                    'component_data': component  # Store full component data
                })
            except Exception as e:
                failed_components.append({
                    'id': component_id,
                    'name': component.get('name', 'Unnamed'),
                    'error': str(e)
                })
        
        return jsonify({
            'status': 'success',
            'message': f'Training completed: {len(trained_components)} new components trained',
            'total_components': len(components),
            'trained_count': len(trained_components),
            'already_trained': already_trained,
            'failed_count': len(failed_components),
            'trained_components': trained_components,
            'failed_components': failed_components,
            'note': 'Full training with embeddings will be implemented in Phase 3'
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/trained-components', methods=['GET'])
def get_trained_components():
    """Get all trained components"""
    try:
        # TODO: Phase 3 - Fetch from database
        # For now, get from projects (components that are completed)
        projects_list = load_projects()
        trained_components = []
        
        for project in projects_list:
            components = project.get('components', [])
            for comp in components:
                if comp.get('status') == 'completed':
                    trained_components.append({
                        'id': comp.get('id', 'unknown'),
                        'name': project.get('project_name', 'Unnamed Project'),
                        'figma_url': comp.get('figma_url', ''),
                        'screenshot_path': comp.get('screenshot_path', ''),
                        'status': 'trained',
                        'trained_at': comp.get('updated_at', comp.get('created_at', datetime.now().isoformat())),
                        'created_at': comp.get('created_at', datetime.now().isoformat())
                    })
        
        return jsonify({
            'status': 'success',
            'components': trained_components,
            'count': len(trained_components),
            'note': 'Full database integration will be implemented in Phase 3'
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/prepare-training-data', methods=['POST'])
def prepare_training_data():
    """Prepare training dataset from component library"""
    try:
        data = request.get_json() or {}
        
        # Get target site information (optional - can prepare data for specific site or all)
        target_site_url = data.get('target_site_url', '')
        profile_alias = data.get('profile_alias', '')
        site_id = data.get('site_id', '')
        
        # Get all trained components from projects
        projects_list = load_projects()
        all_components = []
        
        # Collect all trained components
        for project in projects_list:
            components = project.get('components', [])
            for comp in components:
                if comp.get('status') == 'completed':
                    # Add project context to component
                    component_data = {
                        'id': comp.get('id', 'unknown'),
                        'name': comp.get('name', 'Unnamed'),
                        'project_name': project.get('project_name', 'Unnamed Project'),
                        'target_site_url': project.get('target_site_url', ''),
                        'profile_alias': project.get('profile_alias', ''),
                        'site_id': project.get('site_id', ''),
                        'figma_url': comp.get('figma_url', ''),
                        'screenshot_path': comp.get('screenshot_path', ''),
                        'html_content': comp.get('html_content', ''),
                        'created_at': comp.get('created_at', datetime.now().isoformat()),
                        'updated_at': comp.get('updated_at', datetime.now().isoformat())
                    }
                    
                    # Filter by site details if provided
                    if target_site_url and component_data['target_site_url'] != target_site_url:
                        continue
                    if profile_alias and component_data['profile_alias'] != profile_alias:
                        continue
                    if site_id and component_data['site_id'] != site_id:
                        continue
                    
                    all_components.append(component_data)
        
        # Prepare training data structure
        training_data = {
            'prepared_at': datetime.now().isoformat(),
            'total_components': len(all_components),
            'components': []
        }
        
        # Process each component to prepare training data
        processed_count = 0
        failed_count = 0
        
        for comp in all_components:
            try:
                # Prepare component training data
                training_item = {
                    'component_id': comp['id'],
                    'component_name': comp['name'],
                    'project_name': comp['project_name'],
                    'site_info': {
                        'target_site_url': comp['target_site_url'],
                        'profile_alias': comp['profile_alias'],
                        'site_id': comp['site_id']
                    },
                    'source': {
                        'figma_url': comp['figma_url'],
                        'screenshot_path': comp['screenshot_path']
                    },
                    'content': {
                        'html': comp.get('html_content', ''),
                        'has_html': bool(comp.get('html_content'))
                    },
                    'metadata': {
                        'created_at': comp['created_at'],
                        'updated_at': comp['updated_at']
                    },
                    'ready_for_training': True
                }
                
                # TODO: Phase 3 - Add image processing, feature extraction, embeddings preparation
                # For now, mark as ready
                training_data['components'].append(training_item)
                processed_count += 1
                
            except Exception as e:
                failed_count += 1
                print(f"Error preparing training data for component {comp.get('id')}: {str(e)}")
        
        # Save training data to file (for Phase 3 processing)
        training_data_file = 'training_data.json'
        with open(training_data_file, 'w') as f:
            json.dump(training_data, f, indent=2)
        
        return jsonify({
            'status': 'success',
            'message': f'Training data prepared: {processed_count} components ready',
            'total_components': len(all_components),
            'processed_count': processed_count,
            'failed_count': failed_count,
            'training_data_file': training_data_file,
            'note': 'Training data saved. Ready for Phase 3 embedding generation and matching.'
        })
    
    except Exception as e:
        return jsonify({
            'error': f'Error preparing training data: {str(e)}',
            'hint': 'Please check that you have trained components in your projects'
        }), 500

@app.route('/api/component-image/<component_id>', methods=['GET'])
def get_component_image(component_id):
    """Get component screenshot image"""
    try:
        from flask import send_file
        import os
        
        # TODO: Phase 3 - Get from database
        # For now, search in projects
        projects_list = load_projects()
        
        for project in projects_list:
            components = project.get('components', [])
            for comp in components:
                if comp.get('id') == component_id and comp.get('screenshot_path'):
                    screenshot_path = comp.get('screenshot_path')
                    if os.path.exists(screenshot_path):
                        return send_file(screenshot_path, mimetype='image/png')
        
        # Return placeholder if not found
        return jsonify({'error': 'Image not found'}), 404
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/test-figma', methods=['POST'])
def test_figma():
    """Test Figma API connection"""
    try:
        data = request.get_json() or {}
        figma_client = get_figma_client(data.get('figma_token'))
        
        if not figma_client:
            return jsonify({'error': 'Figma API not configured'}), 500
        
        figma_url = data.get('figma_url')
        
        if not figma_url:
            return jsonify({'error': 'Figma URL is required'}), 400
        
        file_id, node_id = figma_client.parse_figma_url(figma_url)
        
        return jsonify({
            'status': 'success',
            'file_id': file_id,
            'node_id': node_id,
            'message': 'Figma URL parsed successfully'
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

