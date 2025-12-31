import os
from typing import List, Dict, Any

# --- File System Configuration ---
# Get the absolute path of the directory containing this file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Define the folder where uploaded and processed files will be stored
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')

# --- Upload Limits ---
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 Megabytes

# --- File Validation ---
ALLOWED_EXTENSIONS = {'xml'}
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- Processing Pipeline Definition ---
# This list defines the order, module, and configuration for each step.
# The 'id' must match the filename (without .py) in the processing_steps directory.
PROCESSING_STEPS: List[Dict[str, Any]] = [
    {
        "id": "process_xml", 
        "name": "Processing XML and Generating JSON Structures", 
        "module": "run_xml_processing_step", 
        "delay": 2.5, 
        "error_chance": 0.00
    },
    {
        "id": "generate_token", 
        "name": "Generating Login Token", 
        "module": "run_token_generation_step", 
        "delay": 1.0, 
        "error_chance": 0.00
    },
    {
        "id": "process_modules", 
        "name": "Fetching and Processing Site Modules", 
        "module": "run_module_processing_step", 
        "delay": 1.5, 
        "error_chance": 0.00
    },
    {
        "id": "process_menu_navigation",
        "name": "Processing Menu Navigation and Records",
        "module": "run_menu_navigation_step",
        "delay": 2.0,
        "error_chance": 0.00
    },
    {
        "id": "process_home_page",
        "name": "Processing Home Page Templates",
        "module": "run_homepage_processing_step",
        "delay": 3.0,
        "error_chance": 0.00
    },
    {
        "id": "process_assembly",
        "name": "Assembling CMS Pages and Publishing",
        "module": "run_assembly_processing_step",
        "delay": 3.0,
        "error_chance": 0.00
    },
    {
        "id": "cleanup", 
        "name": "Final Cleanup and Resource Release", 
        "module": "run_cleanup_step", 
        "delay": 0.5, 
        "error_chance": 0.00
    }
]