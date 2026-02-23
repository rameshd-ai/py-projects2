# CMS Workflow Manager - Setup Guide

## For Developers: Getting Started

This project uses **Poetry** for dependency management. Similar to how you don't share `venv/` folders, we don't share Poetry's virtual environment.

---

## What Files Are Shared

### ✅ **DO SHARE** (Already configured in `.gitignore`)
- `pyproject.toml` - Defines all dependencies and project metadata
- `poetry.lock` - Locks exact versions for reproducible installs
- All Python source code (`.py` files)
- Templates, resources, configs
- `README.md`, `SETUP_GUIDE.md` (this file)
- `.gitignore`

### ❌ **DO NOT SHARE** (Excluded by `.gitignore`)
- `__pycache__/` - Python bytecode cache
- `.venv/` or any virtual environment folders
- `uploads/` - Job-specific data
- `output/` - Generated output files
- `*.log` - Log files
- `.env` - Environment variables (secrets)
- IDE-specific folders (`.vscode/`, `.idea/`)

---

## Installation Instructions for New Developers

### Prerequisites
1. **Python 3.10 or higher**
   ```bash
   python --version
   ```

2. **Poetry** (Python dependency manager)
   - **Install Poetry:** https://python-poetry.org/docs/#installation
   - Quick install (recommended):
     ```bash
     # Windows (PowerShell)
     (Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | py -
     
     # Linux/macOS
     curl -sSL https://install.python-poetry.org | python3 -
     ```
   - Verify installation:
     ```bash
     poetry --version
     ```

---

## Setup Steps

### 1. Clone the Repository
```bash
git clone <repository-url>
cd "CMS workflow manager"
```

### 2. Install Dependencies
Poetry will automatically create a virtual environment and install all dependencies:

```bash
poetry install
```

This command:
- Creates a virtual environment (usually in `C:\Users\<user>\AppData\Local\pypoetry\Cache\virtualenvs\` on Windows)
- Installs all packages from `poetry.lock` (exact versions)
- Sets up the project

### 3. Verify Installation
```bash
poetry show
```
This lists all installed packages.

---

## Running the Application

### Option 1: Using Poetry (Recommended)
```bash
poetry run python app.py
```

### Option 2: Activate Virtual Environment First
```bash
# Windows PowerShell
poetry shell

# Then run the app
python app.py
```

The app will start on: **http://127.0.0.1:5000**

---

## Common Poetry Commands

### Install Dependencies
```bash
poetry install          # Install all dependencies from poetry.lock
```

### Add a New Package
```bash
poetry add <package-name>              # Add to main dependencies
poetry add --group dev <package-name>  # Add to dev dependencies only
```

### Update Dependencies
```bash
poetry update           # Update all packages (within version constraints)
poetry update <package> # Update specific package
```

### Check Virtual Environment Location
```bash
poetry env info
```

### Remove Virtual Environment (if needed)
```bash
poetry env remove python
poetry install  # Recreate it
```

---

## Project Structure

```
CMS workflow manager/
├── pyproject.toml          # Poetry config & dependencies
├── poetry.lock             # Locked dependency versions
├── app.py                  # Main Flask application
├── apis.py                 # API interaction logic
├── utils.py                # Utility functions
├── config.py               # Configuration settings
├── processing_steps/       # Workflow step modules
│   ├── site_setup.py
│   ├── html_menu.py
│   ├── modules_features.py
│   └── ...
├── templates/              # HTML templates
│   └── index.html
├── resource/               # Config files (mappers, templates)
│   ├── menu_field_mapper.json
│   ├── menu_payload_template.json
│   └── ...
├── uploads/                # Job data (gitignored)
├── output/                 # Generated files (gitignored)
└── __pycache__/            # Python cache (gitignored)
```

---

## Troubleshooting

### Issue: "Poetry not found"
**Solution:** Add Poetry to your PATH or use full path
```bash
# Windows
%APPDATA%\Python\Scripts\poetry

# Linux/macOS
~/.local/bin/poetry
```

### Issue: "Python version mismatch"
**Solution:** Specify Python version
```bash
poetry env use python3.10
poetry install
```

### Issue: "Module not found" errors
**Solution:** Reinstall dependencies
```bash
poetry install --no-cache
```

### Issue: Port 5000 already in use
**Solution:** Kill the process or use a different port
```bash
# Windows
Get-Process python* | Stop-Process -Force

# Linux/macOS
lsof -ti:5000 | xargs kill -9
```

---

## Development Workflow

### Adding New Features
1. Create a new branch
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Make changes to code

3. If you add new dependencies:
   ```bash
   poetry add <new-package>
   ```

4. Test your changes
   ```bash
   poetry run python app.py
   ```

5. Commit changes (including `pyproject.toml` and `poetry.lock` if dependencies changed)
   ```bash
   git add .
   git commit -m "Your commit message"
   git push origin feature/your-feature-name
   ```

### Before Pushing
- ✅ Make sure `pyproject.toml` and `poetry.lock` are committed
- ✅ Don't commit `uploads/`, `output/`, `.venv/`, `__pycache__/`
- ✅ Test that the app runs with `poetry install && poetry run python app.py`

---

## Key Features

### Menu Migration
- Supports hierarchical menu structures (Level 0: Menu, Level 1: Section, Level 2: Item)
- Handles multiple languages (respects source URL language path)
- Cascading status logic (inactive parents → inactive children)
- Preserves special characters (e.g., pipe `|` separators)

### Workflow Steps
1. Site Setup
2. Brand & Theme
3. Content Plugin
4. Modules & Features (includes Dine Menu migration via popup)
5. Finalize

### APIs Used
See `MENU_MIGRATION_API_FLOW.md` for detailed API documentation.

---

## Support

For issues or questions:
1. Check this guide first
2. Review `README.md` (if available)
3. Check `.gitignore` to ensure you're not missing excluded files
4. Contact the project maintainer

---

## Notes for Repository Maintainers

When sharing this project:
- ✅ Always commit `pyproject.toml` and `poetry.lock` together
- ✅ Document any environment variables needed (in `.env.example`)
- ✅ Keep `.gitignore` updated
- ❌ Never commit secrets, tokens, or API keys
- ❌ Never commit job-specific data (`uploads/`, `output/`)
