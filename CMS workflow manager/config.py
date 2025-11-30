"""
Configuration file for CMS Workflow Manager
Defines the processing pipeline and application settings
"""
import os

# Application Settings
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
OUTPUT_FOLDER = os.path.join(BASE_DIR, "output")
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
ALLOWED_EXTENSIONS = {'csv', 'json', 'xlsx', 'xls'}

# Ensure directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Processing Pipeline Definition
# Each step corresponds to a wizard step in the UI
PROCESSING_STEPS = [
    {
        "id": "site_setup",
        "name": "Site Setup Readiness",
        "module": "run_site_setup_step",
        "description": "Processing site configuration and validation",
        "delay": 2.0,  # Simulated processing time
        "error_chance": 0.0  # For testing: 0.0 = no errors, 1.0 = always fails
    },
    {
        "id": "brand_theme",
        "name": "Brand/Theme Setup",
        "module": "run_brand_theme_step",
        "description": "Configuring brand and theme settings",
        "delay": 3.0,
        "error_chance": 0.0
    },
    {
        "id": "content_plugin",
        "name": "Content Plug-in",
        "module": "run_content_plugin_step",
        "description": "Migrating content and inner pages",
        "delay": 4.0,
        "error_chance": 0.0
    },
    {
        "id": "modules_features",
        "name": "Modules/Features",
        "module": "run_modules_features_step",
        "description": "Installing selected modules and features",
        "delay": 3.5,
        "error_chance": 0.0
    },
    {
        "id": "finalize",
        "name": "Finalize & Deploy",
        "module": "run_finalize_step",
        "description": "Finalizing setup and generating reports",
        "delay": 2.5,
        "error_chance": 0.0
    }
]

# API Configuration (placeholder for external CMS APIs)
CMS_API_BASE_URL = "https://api.cms-system.com"  # Replace with actual CMS API
CMS_API_TOKEN = os.getenv("CMS_API_TOKEN", "")  # Store in environment variables

# Logging Configuration
LOG_LEVEL = "INFO"
LOG_FILE = os.path.join(BASE_DIR, "workflow.log")

