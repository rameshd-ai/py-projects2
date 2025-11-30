import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
OUTPUT_FOLDER = os.path.join(BASE_DIR, "output")
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

PROCESSING_STEPS = [
    {"id": "site_setup", "name": "Site Setup Readiness", "module": "run_site_setup_step", "delay": 2.0},
    {"id": "brand_theme", "name": "Brand/Theme Setup", "module": "run_brand_theme_step", "delay": 3.0},
    {"id": "content_plugin", "name": "Content Plug-in", "module": "run_content_plugin_step", "delay": 4.0},
    {"id": "modules_features", "name": "Modules/Features", "module": "run_modules_features_step", "delay": 3.5},
    {"id": "finalize", "name": "Finalize & Deploy", "module": "run_finalize_step", "delay": 2.5}
]

