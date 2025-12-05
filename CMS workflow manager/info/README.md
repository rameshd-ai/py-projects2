# CMS Workflow Manager

A sophisticated web application for managing CMS website creation workflows with real-time progress tracking. Built with Flask and Server-Sent Events (SSE) for seamless user experience.

## 🌟 Features

- **Multi-Step Wizard Interface**: Beautiful, modern UI with 5 comprehensive steps
- **Step-by-Step Processing**: Each step processes immediately when "Process" is clicked
- **Visual Status Indicators**: Green ✓ (success), Red ✗ (failed), Orange ⊘ (skipped)
- **CMS API Integration**: Token generation, theme configuration, group records, theme updates
- **Theme Migration**: Automated theme and branding transfer from source to destination site
- **Variable Mapping**: Font and color variable mapping with customizable templates
- **Modular Architecture**: Independent, reusable processing steps
- **Job-Based Organization**: All files organized by job ID in dedicated folders
- **Dynamic Configuration**: Flexible configuration management with JSON persistence
- **Responsive Design**: Modern, mobile-friendly UI built with custom CSS
- **Comprehensive Logging**: Detailed logging for debugging and monitoring
- **Report Generation**: Automatic completion reports in JSON format

## 📁 Project Structure

```
CMS workflow manager/
├── app.py                      # Main Flask application
├── config.py                   # Configuration and pipeline definition
├── utils.py                    # Utility functions and orchestration
├── apis.py                     # CMS API integrations (NEW)
├── requirements.txt            # Python dependencies
├── README.md                   # This file
├── .gitignore                  # Git ignore patterns
│
├── processing_steps/           # Modular processing steps
│   ├── site_setup.py          # Step 1: Site Setup & Token Generation
│   ├── brand_theme.py         # Step 2: Theme Migration & Updates
│   ├── content_plugin.py      # Step 3: Content Migration
│   ├── modules_features.py    # Step 4: Modules Installation
│   └── finalize.py            # Step 5: Finalization & Reports
│
├── resource/                   # Mapping templates (NEW)
│   ├── font_mapper.json       # Font variable mappings
│   └── color_mapper.json      # Color variable mappings
│
├── templates/                  # HTML templates
│   ├── index.html             # Main wizard interface
│   └── jobs_list.html         # Job management interface
│
├── static/                     # Static files (CSS, JS, images)
│
├── uploads/                    # Job-specific folders
│   └── {job_id}/              # Each job has its own folder
│       ├── config.json
│       ├── results.json
│       ├── source_get_theme_configuration.json
│       ├── source_get_group_record.json
│       ├── destination_get_theme_configuration.json
│       ├── font_mapper.json
│       ├── color_mapper.json
│       ├── update_theme_variables_payload.json
│       ├── update_theme_variables_response.json
│       ├── update_theme_configuration_payload.json
│       └── update_theme_configuration_response.json
│
└── output/                     # Generated reports
    └── {job_id}/              # Job-specific output
        └── report.json
```

## 🚀 Quick Start

### Prerequisites

- Python 3.8 or higher
- pip (Python package installer)
- Virtual environment (recommended)

### Installation

1. **Clone or navigate to the project directory**:
   ```bash
   cd "D:\py-projects2\CMS workflow manager"
   ```

2. **Activate the virtual environment**:
   ```bash
   # Windows
   venv\Scripts\activate
   
   # Linux/Mac
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Create necessary directories**:
   ```bash
   # On Windows (PowerShell)
   New-Item -ItemType Directory -Path uploads, output -Force
   
   # On Linux/Mac
   mkdir -p uploads output
   ```

### Running the Application

#### Development Mode

```bash
python app.py
```

The application will start on `http://localhost:5000`

#### Production Mode (with Gunicorn)

```bash
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

## 📖 Usage

### 1. Access the Web Interface

Open your browser and navigate to:
```
http://localhost:5000
```

### 2. Complete the Workflow Steps

#### **Step 1: Site Setup Readiness**
- Configure source and destination URLs
- Set site IDs and profile aliases
- Define site creation parameters
- Configure site language and country
- **Automatic CMS Token Generation** for both source and destination
- Click **"Process"** → Step executes immediately → ✓ Green checkmark appears

#### **Step 2: Brand/Theme Setup & Migration**
- Check "Pull from Current Site" to enable theme migration
- **Automated Theme Migration Process**:
  - Fetches source site theme configuration and group records
  - Extracts font and color variables with values
  - Maps variables using customizable templates
  - Fetches destination site theme information
  - Creates update payloads for destination site
  - Updates destination site with mapped theme variables
  - Finalizes theme configuration
- All API requests/responses saved to job folder
- Click **"Process"** → Complete migration executes → ✓ Green checkmark

#### **Step 3: Content Plug-in**
- Enable MiBlock migration (optional)
- Upload content mapping sheet
- Define migration approach
- Click **"Process"** → Step executes → ✓ Green or ⊘ Orange (if skipped)

#### **Step 4: Modules/Features**
- Select required modules:
  - Social Feed (Zuicer)
  - HTML Menu
  - FAQ Manager
  - LTO Migration
  - RFP Form
  - DAM Migration
- Click **"Process"** → Step executes → ✓ Green or ⊘ Orange (if none selected)

#### **Step 5: Review & Complete**
- Review configuration summary
- Click **"Process"** → Final step executes → Report generated
- Download completion report

### 3. Step Status Indicators

Each step shows visual feedback:
- **✓ Green Checkmark**: Step completed successfully
- **✗ Red Cross**: Step failed (error occurred)
- **⊘ Orange Symbol**: Step skipped (not enabled/selected)
- **⟳ Blue Spinner**: Step is currently processing
- **Empty Circle**: Step not started yet

## 🎨 Theme Migration Workflow (Step 2)

When "Pull from Current Site" is checked, Step 2 performs automated theme migration:

### **1. Fetch Source Site Data**
- Calls `get_theme_configuration()` to get theme structure
- Calls `get_group_record()` to get all font and color variables with values
- Saves responses: `source_get_theme_configuration.json`, `source_get_group_record.json`

### **2. Map Variables**
- Copies `font_mapper.json` and `color_mapper.json` from resource folder
- Updates font mappings: Matches `old_key` → `variableAlias` → Gets `variableValue`
- Updates color mappings: Matches `old_key` → `variableAlias` → Gets `variableValue`
- All mapped values saved in job folder

### **3. Fetch Destination Site Data**
- Calls `get_theme_configuration()` for destination to get theme ID
- Saves response: `destination_get_theme_configuration.json`

### **4. Create Update Payloads**
- Extracts destination theme ID and site ID
- Builds group names from destination URL (e.g., `sitename_font`, `sitename_color`)
- Creates payload with all mapped variables
- Saves: `update_theme_variables_payload.json`

### **5. Update Destination Site**
- Calls `update_theme_variables()` API with payload
- Receives new group IDs from response
- Saves: `update_theme_variables_response.json`

### **6. Finalize Theme Configuration**
- Extracts group IDs from previous response
- Calls `update_theme_configuration()` with group IDs
- Links new groups to destination theme
- Saves: `update_theme_configuration_payload.json`, `update_theme_configuration_response.json`

**Result:** Destination site now has all fonts and colors from source site! 🎉

---

## 🔧 Configuration

### Application Settings (`config.py`)

```python
# File upload settings
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB

# Processing pipeline - 5 steps
PROCESSING_STEPS = [
    {"id": "site_setup", "name": "Site Setup Readiness", ...},
    {"id": "brand_theme", "name": "Brand/Theme Setup", ...},
    {"id": "content_plugin", "name": "Content Plug-in", ...},
    {"id": "modules_features", "name": "Modules/Features", ...},
    {"id": "finalize", "name": "Finalize & Deploy", ...}
]
```

### CMS API Integration (`apis.py`)

The application integrates with CMS Theme APIs:

- **`generate_cms_token()`** - Generate authentication tokens
- **`get_theme_configuration()`** - Fetch theme configuration
- **`get_group_record()`** - Fetch theme group variables
- **`update_theme_variables()`** - Update theme variables (add groups)
- **`update_theme_configuration()`** - Finalize theme configuration

### Resource Mappers (`resource/`)

- **`font_mapper.json`** - 129 font variable mappings
- **`color_mapper.json`** - 46 color variable mappings

### Environment Variables

Create a `.env` file (optional):

```env
FLASK_SECRET_KEY=your-secret-key-here
CMS_API_TOKEN=your-cms-api-token
CMS_API_BASE_URL=https://api.cms-system.com
LOG_LEVEL=INFO
```

## 🏗️ Architecture

### Modular Pipeline Design

Each processing step:
- Is a separate Python file
- Implements a standardized function signature
- Receives job configuration and workflow context
- Returns results for the next step
- Can access shared configuration via JSON files

### Step-by-Step Processing Flow

**New Processing Model:**
- Each step processes **immediately** when "Process" button is clicked
- Steps execute **sequentially** as you navigate through the wizard
- Results are **saved** after each step completes
- Previous step results are **available** to subsequent steps

**Processing Flow:**
```
Step 1 → Click "Process" → Executes → ✓/✗/⊘ → Moves to Step 2
Step 2 → Click "Process" → Executes → ✓/✗/⊘ → Moves to Step 3
Step 3 → Click "Process" → Executes → ✓/✗/⊘ → Moves to Step 4
Step 4 → Click "Process" → Executes → ✓/✗/⊘ → Moves to Step 5
Step 5 → Click "Process" → Executes → ✓ → Generates Report
```

## 📝 Adding New Processing Steps

1. **Create a new Python file** in `processing_steps/`:

```python
# processing_steps/my_new_step.py
import time
import logging

logger = logging.getLogger(__name__)

def run_my_new_step(job_id: str, step_config: dict, workflow_context: dict) -> dict:
    logger.info(f"[{job_id}] Starting my new step")
    
    # Your processing logic here
    time.sleep(step_config.get("delay", 2.0))
    
    return {
        "status": "completed",
        "message": "Step completed successfully",
        "data": {}
    }
```

2. **Add to configuration** in `config.py`:

```python
PROCESSING_STEPS.append({
    "id": "my_new_step",
    "name": "My New Step",
    "module": "run_my_new_step",
    "description": "Description of what this step does",
    "delay": 2.0
})
```

3. **Restart the application** - The step will be automatically loaded!

## 🔍 API Endpoints

### **Application Endpoints**

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Main wizard interface |
| GET | `/jobs` | Job management interface |
| GET | `/api/jobs` | List all jobs with status |
| DELETE | `/api/jobs/<job_id>` | Delete a job and its files |
| POST | `/api/save-config` | Save config & process current step |
| GET | `/api/job-status/<job_id>` | Get job completion status |
| POST | `/api/mark-step-complete` | Mark a step as complete |
| POST | `/api/generate-report` | Generate final completion report |
| GET | `/download/<job_id>/<filename>` | Download reports |

### **CMS API Integrations (`apis.py`)**

| Function | API Endpoint | Purpose |
|----------|--------------|---------|
| `generate_cms_token()` | `/TokenGenerationApi/GenerateToken` | Generate authentication tokens |
| `get_theme_configuration()` | `/ThemeApi/GetThemeConfiguration` | Fetch theme structure and groups |
| `get_group_record()` | `/ThemeApi/GetGroupRecord` | Fetch theme variables with values |
| `update_theme_variables()` | `/ThemeApi/UpdateThemeVariables` | Add/update theme groups and variables |
| `update_theme_configuration()` | `/ThemeApi/UpdateThemeConfiguration` | Finalize theme with new groups |

## 🧪 Testing

### Manual Testing

1. Fill out Step 1 form
2. Click **"Process"** → Watch step icon change to ✓
3. Fill out Step 2 form
4. Click **"Process"** → Watch step icon change to ✓
5. Repeat for Steps 3, 4, 5
6. On Step 5, click **"Process"** → Final report generated
7. Download and verify the completion report

### Unit Testing (optional)

```bash
pytest tests/
```

## 🐛 Debugging

### Enable Debug Logging

In `config.py`:
```python
LOG_LEVEL = "DEBUG"
```

### View Logs

Check the console output or `workflow.log` file for detailed logs.

### Common Issues

1. **SSE Connection Fails**
   - Check browser console for errors
   - Ensure no proxy/firewall blocking SSE
   - Verify job_id is valid

2. **File Upload Fails**
   - Check file size < 16MB
   - Verify file extension is allowed
   - Ensure uploads/ folder exists and is writable

3. **Processing Step Errors**
   - Check `workflow.log` for stack traces
   - Verify all required fields are filled
   - Ensure configuration files are valid JSON

## 🔒 Security Notes

- **Never commit** sensitive data to version control
- **Use environment variables** for API tokens and secrets
- **Validate all user inputs** before processing
- **Sanitize filenames** using `secure_filename()`
- **Set strong SECRET_KEY** in production

## 📊 Job Folder Structure

Each job creates its own folder with all related files:

```
uploads/{job_id}/
  ├── config.json                                    # Job configuration
  ├── results.json                                   # Step results
  ├── source_get_theme_configuration.json            # Source theme config
  ├── source_get_group_record.json                   # Source theme variables
  ├── destination_get_theme_configuration.json       # Destination theme config
  ├── font_mapper.json                               # Font mappings (updated)
  ├── color_mapper.json                              # Color mappings (updated)
  ├── update_theme_variables_payload.json            # API payload for variables
  ├── update_theme_variables_response.json           # API response with group IDs
  ├── update_theme_configuration_payload.json        # API payload for config
  └── update_theme_configuration_response.json       # Final API response

output/{job_id}/
  └── report.json                                    # Final completion report
```

## 📊 Workflow Report Format

Generated reports include:

```json
{
  "job_id": "job_1234567890_abc123",
  "status": "completed",
  "timestamp": "2025-12-05 12:00:00",
  "configuration": { ... },
  "results": {
    "site_setup": {
      "source_cms_token": "...",
      "destination_cms_token": "...",
      "source_token_generated": true,
      "destination_token_generated": true
    },
    "brand_theme": {
      "branding_complete": true,
      "fonts_configured": true,
      "theme_applied": true,
      "config_source": "pulled_from_site"
    }
  },
  "completed_steps": ["site_setup", "brand_theme", ...]
}
```

## 🤝 Contributing

1. Create a new branch for your feature
2. Follow the existing code style
3. Add tests for new functionality
4. Update documentation as needed
5. Submit a pull request

## 📄 License

This project is proprietary. All rights reserved.

## 🆘 Support

For issues, questions, or feature requests, please contact the development team.

---

**Built with ❤️ using Flask and modern web technologies**



