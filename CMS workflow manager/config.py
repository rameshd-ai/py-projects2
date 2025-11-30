import os

# --- Configuration for the Pipeline ---

# Directory where uploaded and intermediate files will be stored.
# This folder must be created in the root directory.
UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')

# List of all steps in the processing pipeline.
# Each step must define 'id' (for UI matching), 'name' (human-readable), and 'module' (the function to execute).
PROCESSING_STEPS = [
    {
        "id": "upload_file",
        "name": "1. File Upload Acknowledged",
        # This step is simulated client-side, but kept here for UI consistency.
    },
    {
        "id": "site_setup",
        "name": "2. Site Setup Readiness (Initial configuration)",
        "module": "run_site_setup",
        "config": {"config_profile": "OSB/Template", "delay_s": 2}, 
    },
    {
        "id": "brand_theme",
        "name": "3. Brand/Theme Setup (Design configuration)",
        "module": "run_brand_theme_setup",
        "config": {"theme_id": "TPL-402", "delay_s": 3},
    },
    {
        "id": "content_plugin",
        "name": "4. Content Plug-in (Content migration)",
        "module": "run_content_plugin",
        "config": {"migration_mode": "full", "delay_s": 4},
    },
    {
        "id": "modules_features",
        "name": "5. Modules/Features (Select features)",
        "module": "run_modules_features",
        "config": {"feature_list": ["SEO", "Analytics"], "delay_s": 5},
    },
    {
        "id": "review_complete",
        "name": "6. Review & Complete (Final review and cleanup)",
        "module": "run_review_complete_step",
        "config": {"delay_s": 1},
    }
]

# The final report filename
FINAL_REPORT_FILENAME = "website_creation_report.csv"