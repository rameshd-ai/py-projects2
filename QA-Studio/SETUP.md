# QA Studio - Setup Guide

## Virtual Environment & Package Management

### What is a Virtual Environment?

A virtual environment (venv) is an isolated Python environment that keeps project dependencies separate from your system Python. This prevents conflicts between different projects.

**Common virtual environment folder names:**
- `venv/` (most common)
- `env/`
- `.venv/`
- `ENV/`

All of these are **excluded from git** (see `.gitignore`) because they contain installed packages and shouldn't be committed.

---

## Initial Setup

### Step 1: Create Virtual Environment

**Windows:**
```powershell
python -m venv venv
```

**Linux/Mac:**
```bash
python3 -m venv venv
```

This creates a `venv/` folder in your project directory.

### Step 2: Activate Virtual Environment

**Windows (PowerShell):**
```powershell
.\venv\Scripts\Activate.ps1
```

**Windows (Command Prompt):**
```cmd
venv\Scripts\activate.bat
```

**Linux/Mac:**
```bash
source venv/bin/activate
```

You'll see `(venv)` in your terminal prompt when activated.

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

This installs all packages listed in `requirements.txt` into your virtual environment.

### Step 4: Install Playwright Browsers

```bash
playwright install
```

This downloads Chromium, Firefox, and WebKit browsers needed for testing.

### Step 5: Verify Installation

```bash
python -c "import flask; import playwright; print('All packages installed!')"
```

---

## Package Management

### How Dependencies Are Managed

**`requirements.txt`** - This file lists all project dependencies with specific versions:

```
Flask==3.0.0
Flask-SocketIO==5.3.6
playwright==1.40.0
...
```

### Adding a New Package

1. Activate virtual environment
2. Install the package:
   ```bash
   pip install package-name
   ```
3. Update requirements.txt:
   ```bash
   pip freeze > requirements.txt
   ```
   Or manually add it to `requirements.txt` with version pinning.

### Updating Packages

```bash
# Update a specific package
pip install --upgrade package-name

# Update all packages (then update requirements.txt)
pip install --upgrade -r requirements.txt
pip freeze > requirements.txt
```

### Removing a Package

1. Remove from `requirements.txt`
2. Uninstall:
   ```bash
   pip uninstall package-name
   ```

### Checking Installed Packages

```bash
# List all installed packages
pip list

# Show package info
pip show package-name

# Check for outdated packages
pip list --outdated
```

---

## Project Structure

```
QA-Studio/
├── venv/              # Virtual environment (NOT in git)
│   ├── Scripts/       # Windows executables
│   ├── bin/           # Linux/Mac executables
│   └── lib/           # Installed packages
├── requirements.txt   # Dependency list (IN git)
├── app.py
├── utils/             # Project modules
└── tests/             # Test files
```

---

## Daily Workflow

### Starting Work

1. Activate virtual environment:
   ```powershell
   .\venv\Scripts\Activate.ps1
   ```

2. Start the server:
   ```bash
   python app.py
   ```

### Ending Work

1. Deactivate virtual environment (optional):
   ```bash
   deactivate
   ```

---

## Troubleshooting

### Virtual Environment Not Found

If `venv/` folder doesn't exist:
```bash
python -m venv venv
```

### Packages Not Found After Installation

- Make sure virtual environment is activated
- Reinstall: `pip install -r requirements.txt`

### Permission Errors (Windows)

If PowerShell blocks activation:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Clean Reinstall

If things get messy:
```bash
# Remove virtual environment
rm -rf venv/          # Linux/Mac
rmdir /s venv         # Windows

# Recreate
python -m venv venv
.\venv\Scripts\Activate.ps1  # Windows
source venv/bin/activate      # Linux/Mac

# Reinstall
pip install -r requirements.txt
playwright install
```

---

## Why Use Virtual Environments?

✅ **Isolation**: Each project has its own packages  
✅ **Version Control**: Different projects can use different package versions  
✅ **Clean System**: Keeps your system Python clean  
✅ **Reproducibility**: `requirements.txt` ensures everyone uses same versions  
✅ **Easy Cleanup**: Delete `venv/` folder to remove everything

---

## Alternative: Using Conda

If you prefer Conda:

```bash
# Create environment
conda create -n qa-studio python=3.10

# Activate
conda activate qa-studio

# Install packages
pip install -r requirements.txt
playwright install
```
