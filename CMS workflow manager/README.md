# CMS Workflow Manager

A sophisticated web application for managing CMS website creation workflows with real-time progress tracking. Built with Flask and Server-Sent Events (SSE) for seamless user experience.

## 🌟 Features

- **Multi-Step Wizard Interface**: Beautiful, modern UI with 5 comprehensive steps
- **Real-Time Progress Tracking**: Server-Sent Events (SSE) for live workflow updates
- **Modular Architecture**: Independent, reusable processing steps
- **Dynamic Configuration**: Flexible configuration management with JSON persistence
- **Responsive Design**: Modern, mobile-friendly UI built with custom CSS
- **Comprehensive Logging**: Detailed logging for debugging and monitoring
- **Report Generation**: Automatic completion reports in JSON format

## 📁 Project Structure

```
CMS workflow manager/
├── app.py                      # Main Flask application
├── config.py                   # Configuration and pipeline definition
├── utils.py                    # Utility functions and SSE orchestration
├── requirements.txt            # Python dependencies
├── README.md                   # This file
├── .gitignore                  # Git ignore patterns
│
├── processing_steps/           # Modular processing steps
│   ├── site_setup.py          # Step 1: Site Setup Readiness
│   ├── brand_theme.py         # Step 2: Brand/Theme Configuration
│   ├── content_plugin.py      # Step 3: Content Migration
│   ├── modules_features.py    # Step 4: Modules Installation
│   └── finalize.py            # Step 5: Finalization & Reports
│
├── templates/                  # HTML templates
│   └── index.html             # Main wizard interface
│
├── static/                     # Static files (CSS, JS, images)
├── uploads/                    # Uploaded files and job configs
└── output/                     # Generated reports and outputs
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

#### **Step 2: Brand/Theme Setup**
- Pull fonts from existing site, or
- Upload custom CSV/JSON configuration

#### **Step 3: Content Plug-in**
- Enable MiBlock migration (optional)
- Upload content mapping sheet
- Define migration approach

#### **Step 4: Modules/Features**
- Select required modules:
  - Social Feed (Zuicer)
  - HTML Menu
  - FAQ Manager
  - LTO Migration
  - RFP Form
  - DAM Migration

#### **Step 5: Review & Complete**
- Review configuration summary
- Start the workflow
- Monitor real-time progress
- Download completion report

### 3. Monitor Progress

The workflow processing will show:
- Real-time step execution
- Processing logs
- Step completion status
- Total duration
- Download link for final report

## 🔧 Configuration

### Application Settings (`config.py`)

```python
# File upload settings
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
ALLOWED_EXTENSIONS = {'csv', 'json', 'xlsx', 'xls'}

# Processing pipeline
PROCESSING_STEPS = [...]  # 5 steps defined
```

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

### Server-Sent Events (SSE)

The application uses SSE for real-time communication:
- **No polling required** - Server pushes updates to client
- **Event-driven** - Updates sent as they occur
- **Automatic reconnection** - Browser handles connection issues
- **Structured messages** - JSON-formatted event data

### Event Types

```javascript
{
  "status": "start" | "in_progress" | "done" | "complete" | "error" | "close",
  "step_id": "site_setup",
  "step_name": "Site Setup Readiness",
  "message": "Processing...",
  "duration": 2.5
}
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

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Main wizard interface |
| GET | `/api/steps` | Get all processing steps |
| POST | `/api/save-config` | Save wizard configuration |
| POST | `/api/upload` | Upload files |
| POST | `/api/start-workflow` | Start workflow processing |
| GET | `/api/stream/<job_id>` | SSE stream for progress |
| GET | `/download/<filename>` | Download reports |
| GET | `/health` | Health check |

## 🧪 Testing

### Manual Testing

1. Fill out the wizard with test data
2. Upload test files (CSV/JSON)
3. Start the workflow
4. Observe real-time progress
5. Download and verify the completion report

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

## 📊 Workflow Report Format

Generated reports include:

```json
{
  "job_id": "job_1234567890_abc123",
  "status": "completed",
  "total_duration_seconds": 15.7,
  "completed_steps": ["site_setup", "brand_theme", ...],
  "timestamp": "2025-11-30 17:30:00",
  "configuration": { ... },
  "results": {
    "site_setup": { ... },
    "brand_theme": { ... }
  }
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



