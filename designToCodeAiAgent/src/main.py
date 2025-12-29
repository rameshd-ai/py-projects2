"""
Flask Main Application (Simplified)
Entry point for the Figma to MiBlock Component Generator
"""
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import os
import uuid

from src.config import settings
from src.api import FigmaClient, CMSClient, ClaudeClient

# Create Flask app
app = Flask(__name__, static_folder='../frontend')
app.config['SECRET_KEY'] = settings.secret_key

# Enable CORS
CORS(app, origins=settings.cors_origins)

# Initialize SocketIO for real-time updates
socketio = SocketIO(app, cors_allowed_origins=settings.cors_origins)

# Initialize API clients
figma_client = None
cms_client = None
claude_client = None


@app.before_request
def initialize_clients():
    """Initialize clients on first request"""
    global figma_client, cms_client, claude_client
    
    if figma_client is None:
        figma_client = FigmaClient()
        cms_client = CMSClient()
        claude_client = ClaudeClient()
        app.logger.info("✅ API clients initialized")


# ============================================
# Basic Routes
# ============================================

@app.route('/')
def index():
    """Root endpoint - API info"""
    return jsonify({
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "environment": settings.environment,
        "endpoints": {
            "api": "/api",
            "health": "/health"
        }
    })


@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy"
    })


@app.route('/api/status')
def api_status():
    """Get API and service status"""
    return jsonify({
        "api": "operational",
        "database": "operational",  # TODO: Check actual DB
        "cache": "in-memory",       # Using in-memory cache (no Redis)
        "figma_api": "operational",
        "cms_api": "operational",
        "claude_api": "operational"
    })


# ============================================
# Component Generation Routes
# ============================================

@app.route('/api/generate/from-url', methods=['POST'])
def generate_from_url():
    """
    Generate component from Figma URL
    
    Body JSON:
        {
            "figma_url": "https://figma.com/file/...",
            "component_name": "Optional name"
        }
    """
    data = request.get_json()
    figma_url = data.get('figma_url')
    component_name = data.get('component_name')
    
    if not figma_url:
        return jsonify({"error": "figma_url is required"}), 400
    
    # Create task
    task_id = str(uuid.uuid4())
    
    # TODO: Validate Figma URL
    # TODO: Create generation task in database
    # TODO: Start async processing
    
    return jsonify({
        "task_id": task_id,
        "status": "pending",
        "message": "Component generation started",
        "figma_url": figma_url
    })


@app.route('/api/generate/task/<task_id>')
def get_task(task_id):
    """Get generation task status"""
    # TODO: Query database for task
    
    return jsonify({
        "task_id": task_id,
        "status": "completed",
        "progress": 100,
        "result": {
            "component_id": 123,
            "is_library_match": False,
            "config_url": f"/api/results/{task_id}/config.json",
            "format_url": f"/api/results/{task_id}/format.json",
            "records_url": f"/api/results/{task_id}/records.json"
        }
    })


# ============================================
# Library Management Routes
# ============================================

@app.route('/api/library/status')
def library_status():
    """Get current library status"""
    # TODO: Query database for stats
    
    return jsonify({
        "total_components": 150,
        "active_components": 145,
        "components_with_embeddings": 145,
        "last_refresh": "2025-12-29T17:00:00Z",
        "status": "ready"
    })


@app.route('/api/library/refresh', methods=['POST'])
def refresh_library():
    """Trigger library refresh"""
    data = request.get_json() or {}
    refresh_type = data.get('refresh_type', 'incremental')
    
    task_id = str(uuid.uuid4())
    
    # TODO: Validate refresh_type
    # TODO: Create refresh task in database
    # TODO: Start async library ingestion
    
    return jsonify({
        "task_id": task_id,
        "refresh_type": refresh_type,
        "status": "started",
        "message": "Library refresh started"
    })


@app.route('/api/library/refresh/<task_id>')
def get_refresh_progress(task_id):
    """Get library refresh progress"""
    # TODO: Query database for refresh task
    
    return jsonify({
        "task_id": task_id,
        "status": "in_progress",
        "progress": {
            "download": {"current": 45, "total": 150},
            "embeddings": {"current": 30, "total": 45},
            "storage": {"current": 30, "total": 45}
        },
        "current_component": "Hero Section Variant 3",
        "estimated_time_remaining": 300
    })


# ============================================
# WebSocket for Real-time Updates
# ============================================

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    app.logger.info(f"Client connected: {request.sid}")


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    app.logger.info(f"Client disconnected: {request.sid}")


@socketio.on('subscribe_task')
def handle_subscribe(data):
    """Subscribe to task updates"""
    task_id = data.get('task_id')
    app.logger.info(f"Client subscribed to task: {task_id}")
    
    # TODO: Join room for this task
    # TODO: Send task updates to this room


# ============================================
# Serve Frontend (Static Files)
# ============================================

@app.route('/app')
@app.route('/app/<path:path>')
def serve_frontend(path='index.html'):
    """Serve frontend files"""
    frontend_dir = os.path.join(app.root_path, '..', 'frontend')
    if os.path.exists(os.path.join(frontend_dir, path)):
        return send_from_directory(frontend_dir, path)
    else:
        return send_from_directory(frontend_dir, 'index.html')


# ============================================
# Error Handlers
# ============================================

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({"error": "Not found"}), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    app.logger.error(f"Internal error: {error}")
    return jsonify({"error": "Internal server error"}), 500


# ============================================
# Run Application
# ============================================

if __name__ == '__main__':
    print(f"🚀 Starting {settings.app_name} v{settings.app_version}")
    print(f"📊 Environment: {settings.environment}")
    print(f"🔧 Debug Mode: {settings.debug}")
    print(f"🌐 Server: http://{settings.api_host}:{settings.api_port}")
    
    # Run with SocketIO
    socketio.run(
        app,
        host=settings.api_host,
        port=settings.api_port,
        debug=settings.debug
    )
