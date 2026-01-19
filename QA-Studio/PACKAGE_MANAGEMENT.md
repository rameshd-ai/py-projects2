# QA Studio - Package Management Guide

## Overview

This project uses **Python's standard package management** with `pip` and `requirements.txt`.

---

## 📦 Package Management Structure

```
QA-Studio/
│
├── requirements.txt          ← Dependency list (IN git)
│   └── Lists all packages with versions
│
├── venv/                     ← Virtual environment (NOT in git)
│   ├── Scripts/              ← Windows executables
│   │   ├── python.exe
│   │   ├── pip.exe
│   │   └── activate.bat
│   │
│   ├── bin/                  ← Linux/Mac executables
│   │   ├── python
│   │   ├── pip
│   │   └── activate
│   │
│   └── lib/                  ← Installed packages
│       └── python3.x/
│           └── site-packages/
│               ├── flask/
│               ├── playwright/
│               ├── pytest/
│               └── ... (all installed packages)
│
└── .gitignore                ← Excludes venv/ from git
```

---

## 🔄 How It Works

### 1. **Virtual Environment (`venv/`)**
- **Purpose**: Isolated Python environment for this project
- **Location**: Project root directory
- **Status**: NOT committed to git (excluded in `.gitignore`)
- **Contains**: All installed packages and Python interpreter

### 2. **Requirements File (`requirements.txt`)**
- **Purpose**: Lists all project dependencies
- **Location**: Project root
- **Status**: Committed to git (shared with team)
- **Format**: One package per line with version

### 3. **Package Installation Flow**

```
Developer A                    Developer B
     │                              │
     ├─ Clone repo                  ├─ Clone repo
     │                              │
     ├─ Create venv                 ├─ Create venv
     │  python -m venv venv         │  python -m venv venv
     │                              │
     ├─ Activate venv               ├─ Activate venv
     │  .\venv\Scripts\activate     │  source venv/bin/activate
     │                              │
     └─ Install packages            └─ Install packages
        pip install -r requirements.txt  pip install -r requirements.txt
```

Both developers get the **same packages** because they use the same `requirements.txt`.

---

## 📋 Current Dependencies

See `requirements.txt` for the complete list. Main categories:

| Category | Packages | Purpose |
|----------|----------|---------|
| **Web Framework** | Flask, Flask-SocketIO | Web dashboard |
| **Testing** | pytest, pytest-playwright | Test execution |
| **Automation** | playwright | Browser automation |
| **Data Processing** | pydantic, beautifulsoup4 | Validation & parsing |
| **Utilities** | advertools, Pillow, PyYAML | Sitemap, images, config |

---

## 🛠️ Common Operations

### View Installed Packages
```bash
pip list
```

### Check Package Versions
```bash
pip show flask
pip show playwright
```

### Update a Package
```bash
# Update specific package
pip install --upgrade flask

# Update requirements.txt
pip freeze > requirements.txt
```

### Add a New Package
```bash
# 1. Install it
pip install new-package

# 2. Add to requirements.txt
pip freeze > requirements.txt
# Or manually add: new-package==1.2.3
```

### Remove a Package
```bash
# 1. Remove from requirements.txt (manually edit)
# 2. Uninstall
pip uninstall package-name
```

### Check for Outdated Packages
```bash
pip list --outdated
```

---

## 🔍 Why Virtual Environments?

### Without Virtual Environment (❌ Bad)
```
System Python
├── Project A uses Flask 2.0
├── Project B uses Flask 3.0  ← CONFLICT!
└── System packages get mixed
```

### With Virtual Environment (✅ Good)
```
Project A (venv/)
└── Flask 2.0

Project B (venv/)
└── Flask 3.0

System Python
└── Clean, untouched
```

**Benefits:**
- ✅ Isolation between projects
- ✅ No version conflicts
- ✅ Easy cleanup (delete `venv/` folder)
- ✅ Reproducible environments

---

## 📝 Maintaining requirements.txt

### Best Practices

1. **Pin Versions**: Always specify exact versions
   ```
   Flask==3.0.0          ✅ Good
   Flask>=3.0.0         ⚠️  Less precise
   Flask                 ❌ Bad (unpredictable)
   ```

2. **Update Regularly**: Keep packages up to date
   ```bash
   pip list --outdated
   pip install --upgrade package-name
   pip freeze > requirements.txt
   ```

3. **Test After Updates**: Always test after updating packages
   ```bash
   python app.py  # Test server starts
   pytest tests/  # Run tests
   ```

4. **Document Changes**: When updating, note why in commit message
   ```
   Update Flask to 3.0.0 for security fixes
   ```

---

## 🚨 Troubleshooting

### "Module not found" Error

**Problem**: Package not installed

**Solution**:
```bash
# Activate venv first!
.\venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# Install missing package
pip install package-name

# Or reinstall all
pip install -r requirements.txt
```

### "Wrong version" Error

**Problem**: Package version mismatch

**Solution**:
```bash
# Check installed version
pip show package-name

# Install correct version from requirements.txt
pip install -r requirements.txt
```

### Virtual Environment Not Activating

**Windows PowerShell**:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\venv\Scripts\Activate.ps1
```

**Windows CMD**:
```cmd
venv\Scripts\activate.bat
```

**Linux/Mac**:
```bash
source venv/bin/activate
```

### Clean Reinstall

If everything is broken:
```bash
# 1. Delete venv
rm -rf venv/          # Linux/Mac
rmdir /s venv         # Windows

# 2. Recreate
python -m venv venv
.\venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# 3. Reinstall
pip install -r requirements.txt
playwright install
```

---

## 📊 Package Size

Virtual environments can be large (200-500 MB) because they include:
- Python interpreter
- All installed packages
- Package dependencies
- Compiled binaries

This is why `venv/` is excluded from git - it's too large and can be regenerated.

---

## 🔗 Related Files

- `requirements.txt` - Package list
- `setup.py` - Automated setup script
- `SETUP.md` - Detailed setup instructions
- `.gitignore` - Excludes `venv/` from git

---

## 💡 Quick Reference

```bash
# Create venv
python -m venv venv

# Activate (Windows)
.\venv\Scripts\Activate.ps1

# Activate (Linux/Mac)
source venv/bin/activate

# Install packages
pip install -r requirements.txt

# Check packages
pip list

# Update requirements.txt
pip freeze > requirements.txt

# Deactivate
deactivate
```
