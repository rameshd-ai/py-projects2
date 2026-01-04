"""
Flask app for Figma to CMS Component Generator
"""
from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
import os
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

@app.route('/api/generate', methods=['POST'])
def generate_component():
    """Generate CMS component from Figma URL"""
    try:
        data = request.get_json()
        figma_url = data.get('figma_url')
        
        if not figma_url:
            return jsonify({'error': 'Figma URL is required'}), 400
        
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
        
        # TODO: Phase 2 - Implement LangGraph workflow for full component generation
        # For now, return HTML and screenshot path
        return jsonify({
            'status': 'success',
            'message': 'HTML generated successfully (Phase 1 complete)',
            'figma_url': figma_url,
            'screenshot_path': screenshot_path,
            'html_preview': html_content[:500] + '...' if len(html_content) > 500 else html_content,
            'html_length': len(html_content),
            'note': 'Full component generation with LangGraph will be implemented in Phase 2'
        })
    
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/refresh-library', methods=['POST'])
def refresh_library():
    """Refresh component library from CMS"""
    try:
        data = request.get_json() or {}
        cms_client = get_cms_client(data.get('cms_base_url'), data.get('cms_api_key'))
        
        if not cms_client:
            return jsonify({'error': 'CMS API not configured. Please enter your CMS API credentials in Settings.'}), 500
        
        # Get all components from CMS
        components = cms_client.get_components()
        
        # TODO: Phase 3 - Store components in database with embeddings
        return jsonify({
            'status': 'success',
            'message': f'Found {len(components)} components in CMS',
            'components_count': len(components),
            'note': 'Component storage in database will be implemented in Phase 3'
        })
    
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

