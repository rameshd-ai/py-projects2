# PHASE 0: Prerequisites & Environment Setup

**Duration**: 30-60 minutes  
**Status**: ✅ COMPLETED (December 29, 2025)  
**Checkpoint**: Ready to start Phase 1

---

## 📋 Overview

Phase 0 covers all prerequisite setup before starting Phase 1 implementation. This includes:
- PostgreSQL database installation and setup
- Python virtual environment creation
- Dependency installation
- Environment configuration
- Verification that everything works

---

## ✅ Step 1: PostgreSQL Installation

### Windows Installation

1. **Download PostgreSQL**
   - Go to: https://www.postgresql.org/download/windows/
   - Download PostgreSQL 18 (or 15+)
   - Run the installer

2. **During Installation**
   - Set password for `postgres` user: `Google@1`
   - Default port: `5432` (keep it)
   - Remember the installation directory

3. **Verify Installation**
   ```powershell
   # Check if PostgreSQL is running
   sc query postgresql-x64-18
   ```

**Status**: ✅ PostgreSQL 18.1 installed

---

## ✅ Step 2: Create Database

### Option A: Using Python Script (Recommended)

```bash
# Navigate to project directory
cd D:\GItHIbProjects\py-projects2\designToCodeAiAgent

# Create database and tables
python scripts/create_database.py --force
```

**Output:**
```
============================================================
DATABASE SETUP
============================================================

Step 1: Connecting to PostgreSQL...
SUCCESS: Connected to PostgreSQL

Step 2: Checking if database exists...
Creating database 'miblock_components'...
SUCCESS: Database created

Step 3: Creating tables and schema...
SUCCESS: Schema created

Step 4: Verifying tables...
SUCCESS: 3 tables created:
  - components
  - generation_tasks
  - library_refresh_tasks

============================================================
DATABASE SETUP COMPLETE!
============================================================
```

### Option B: Manual Setup

```bash
# Connect to PostgreSQL
psql -U postgres

# Create database
CREATE DATABASE miblock_components;

# Exit
\q

# Run schema file
psql -U postgres -d miblock_components -f scripts/setup_database_simple.sql
```

**Status**: ✅ Database `miblock_components` created with 3 tables

---

## ✅ Step 3: Environment Configuration

### Create .env File

```bash
# Using Python script
python scripts/create_env.py
```

**Or manually:**

```bash
# Copy template
cp env.example .env
```

**Edit `.env` file:**

```bash
# Database (REQUIRED)
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=miblock_components
DATABASE_USER=postgres
DATABASE_PASSWORD=Google@1
DATABASE_URL=postgresql://postgres:Google@1@localhost:5432/miblock_components

# API Keys (Add these when you have them)
FIGMA_API_TOKEN=your_figma_token_here
ANTHROPIC_API_KEY=your_anthropic_key_here
CMS_API_KEY=your_cms_key_here
CMS_API_SECRET=your_cms_secret_here

# Flask Settings
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=True
```

**Status**: ✅ `.env` file created with database credentials

---

## ✅ Step 4: Python Virtual Environment

### Create Virtual Environment

```bash
# Navigate to project root
cd D:\GItHIbProjects\py-projects2\designToCodeAiAgent

# Create virtual environment
python -m venv venv
```

**This creates:**
```
venv/
├── Scripts/
│   ├── Activate.ps1      ← For PowerShell
│   ├── activate.bat      ← For CMD
│   └── python.exe        ← Isolated Python
├── Lib/
│   └── site-packages/    ← Dependencies install here
└── pyvenv.cfg
```

**Status**: ✅ Virtual environment created at `venv/`

---

## ✅ Step 5: Activate Virtual Environment

### For PowerShell (Recommended)

```powershell
# Activate
.\venv\Scripts\Activate.ps1

# You'll see (venv) prefix in your prompt:
(venv) PS D:\GItHIbProjects\py-projects2\designToCodeAiAgent>
```

### For Command Prompt

```cmd
# Activate
venv\Scripts\activate.bat

# You'll see:
(venv) D:\GItHIbProjects\py-projects2\designToCodeAiAgent>
```

### For Git Bash

```bash
# Activate
source venv/Scripts/activate
```

### Verify Activation

```bash
# Check Python location (should be in venv)
python --version
# Output: Python 3.13.1

# Check pip location
pip --version
# Output: pip 24.3.1 from D:\...\venv\Lib\site-packages\pip

# Check which Python
where python
# Output: D:\...\designToCodeAiAgent\venv\Scripts\python.exe
```

**Status**: ✅ Virtual environment activated

---

## ✅ Step 6: Install Dependencies

### Install All Packages

```bash
# Make sure venv is activated (you see (venv) in prompt)
pip install -r requirements.txt
```

**This installs:**
- ✅ **Flask** - Web framework
- ✅ **PostgreSQL drivers** - Database connection
- ✅ **Anthropic SDK** - Claude AI client
- ✅ **LangGraph** - Agent orchestration
- ✅ **Image processing** - OpenCV, scikit-image
- ✅ **And 40+ other packages**

**Installation takes:** ~5-10 minutes

### Verify Installation

```bash
# Check installed packages
pip list

# Check specific packages
pip show flask
pip show anthropic
pip show psycopg2-binary
```

**Status**: ✅ All dependencies installed

---

## ✅ Step 7: Verify Database Connection

### Run Database Check Script

```bash
# Make sure venv is activated
python scripts/check_database.py
```

**Expected Output:**

```
✅ Loading settings from .env file

============================================================
🗄️  DATABASE STATUS CHECK
============================================================

📡 Connecting to PostgreSQL...
   Host: localhost
   Port: 5432
   Database: miblock_components
   User: postgres

✅ Connected successfully!

📊 PostgreSQL Information:
   Version: PostgreSQL 18.1 on x86_64-windows
   Database Size: 8366 kB

🔌 Extensions:
   ❌ pgvector: NOT INSTALLED
   💡 Install with: CREATE EXTENSION vector;

📋 Tables:
   ✅ components: 0 rows
   ✅ generation_tasks: 0 rows
   ✅ library_refresh_tasks: 0 rows

🔍 Indexes:
   ✅ 7 found

👁️  Views:
   ✅ 2 found

⚙️  Functions:
   ✅ 3 found

============================================================
📊 SUMMARY
============================================================
+--------------------+-----------------+
| Check              | Status          |
+====================+=================+
| Connection         | ✅ Success       |
| Tables             | ✅ 3 found       |
| Indexes            | ✅ 7 found       |
| Views              | ✅ 2 found       |
| Functions          | ✅ 3 found       |
+--------------------+-----------------+

✅ Database is ready!
```

**Status**: ✅ Database connection verified

---

## ✅ Step 8: View Tables in pgAdmin

### Open pgAdmin

1. **Launch pgAdmin**
   - Windows Start Menu → "pgAdmin 4"
   - Or: `C:\Program Files\PostgreSQL\18\pgAdmin 4\bin\pgAdmin4.exe`

2. **First Time Setup**
   - Set master password (any password for pgAdmin)
   - Connect to server

3. **Navigate to Database**
   ```
   Servers
   └── PostgreSQL 18
       └── Databases
           └── miblock_components
               └── Schemas
                   └── public
                       └── Tables
                           ├── components
                           ├── generation_tasks
                           └── library_refresh_tasks
   ```

4. **View Table Data**
   - Right-click any table
   - Select "View/Edit Data" → "All Rows"
   - See data in spreadsheet view

**Status**: ✅ Can view tables in pgAdmin GUI

---

## ✅ Step 9: Project Structure Verification

### Verify All Files Exist

```bash
# List project structure
tree /F /A
```

**Expected Structure:**

```
designToCodeAiAgent/
├── .env                          ✅ Configuration file
├── requirements.txt              ✅ Dependencies
├── README.md                     ✅ Documentation
├── FINAL_DEVELOPMENT_PLAN.md     ✅ Master plan
│
├── venv/                         ✅ Virtual environment
│   ├── Scripts/
│   └── Lib/
│
├── src/                          ✅ Source code
│   ├── main.py                   ✅ Flask app
│   ├── config/
│   │   └── settings.py           ✅ Settings
│   ├── api/
│   │   ├── figma_client.py       ✅ Figma API
│   │   ├── claude_client.py      ✅ Claude API
│   │   └── cms_client.py         ✅ CMS API
│   ├── agents/
│   │   └── base_agent.py         ✅ Agent base
│   ├── models/
│   │   └── database.py           ✅ DB models
│   └── utils/
│       ├── logging_config.py     ✅ Logging
│       └── cache.py              ✅ Caching
│
├── scripts/                      ✅ Helper scripts
│   ├── create_database.py        ✅ DB setup
│   ├── check_database.py         ✅ DB verify
│   ├── create_env.py             ✅ Env setup
│   └── setup_database_simple.sql ✅ DB schema
│
├── docs/                         ✅ Documentation
│   ├── DATABASE_SETUP.md
│   ├── PHASE_0_PREREQUISITES.md  ✅ This file
│   └── phases/
│       ├── PHASE_1_FOUNDATION.md
│       └── ...
│
├── frontend/                     📁 Empty (Phase 1)
├── tests/                        📁 Empty (Phase 1)
└── storage/                      📁 Empty (Phase 1)
```

**Status**: ✅ All required files present

---

## ✅ Step 10: Test Import Paths

### Verify Python Can Import Modules

```bash
# Make sure venv is activated
python -c "from src.config import settings; print('✅ Settings imported')"
python -c "from src.models.database import Component; print('✅ Models imported')"
python -c "import flask; print('✅ Flask imported')"
python -c "import anthropic; print('✅ Anthropic imported')"
python -c "import psycopg2; print('✅ PostgreSQL driver imported')"
```

**All should print:** ✅ Success messages

**Status**: ✅ All imports working

---

## 📊 Phase 0 Completion Checklist

Use this checklist to verify everything is ready:

```
Environment Setup:
 ✅ PostgreSQL 18+ installed
 ✅ PostgreSQL service running
 ✅ Database 'miblock_components' created
 ✅ 3 tables created (components, generation_tasks, library_refresh_tasks)
 ✅ Can view tables in pgAdmin
 ✅ Database password set: Google@1

Python Environment:
 ✅ Python 3.13.1 installed
 ✅ Virtual environment created at venv/
 ✅ Virtual environment activated
 ✅ All dependencies installed (40+ packages)
 ✅ Can import src modules

Configuration:
 ✅ .env file created
 ✅ Database credentials configured
 ✅ Connection tested successfully

Project Files:
 ✅ src/ folder with all modules
 ✅ scripts/ folder with helper scripts
 ✅ docs/ folder with documentation
 ✅ requirements.txt with dependencies

Verification:
 ✅ python scripts/check_database.py passes
 ✅ Can import from src.config
 ✅ Can import from src.models
 ✅ Flask can be imported
 ✅ Anthropic can be imported
```

---

## 🚀 What's Next?

### You are now ready for Phase 1!

**Phase 1 will implement:**
1. Complete Flask application with routes
2. API clients (Figma, Claude, CMS)
3. Database models with SQLAlchemy
4. Agent architecture with LangGraph
5. WebSocket for real-time updates
6. Simple frontend UI

**Estimated time:** 1-2 hours

---

## 🆘 Troubleshooting

### Virtual Environment Issues

**Problem:** "venv not activating"
```bash
# Try this instead:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\venv\Scripts\Activate.ps1
```

**Problem:** "Cannot find python in venv"
```bash
# Recreate venv
rm -r venv
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### Dependency Installation Issues

**Problem:** "Package installation fails"
```bash
# Update pip first
python -m pip install --upgrade pip

# Try again
pip install -r requirements.txt
```

**Problem:** "Specific package fails"
```bash
# Install without that package
pip install -r requirements.txt --no-deps
pip install <failing_package> --no-binary :all:
```

### Database Connection Issues

**Problem:** "Connection refused"
```bash
# Check if PostgreSQL is running
sc query postgresql-x64-18

# Start if not running
sc start postgresql-x64-18
```

**Problem:** "Password authentication failed"
```bash
# Check password in .env
# Should be: DATABASE_PASSWORD=Google@1
```

---

## 📝 Quick Reference Commands

### Virtual Environment

```bash
# Activate (PowerShell)
.\venv\Scripts\Activate.ps1

# Deactivate
deactivate

# Check if active
echo $env:VIRTUAL_ENV  # PowerShell
echo %VIRTUAL_ENV%     # CMD
```

### Database

```bash
# Check connection
python scripts/check_database.py

# Recreate database
python scripts/create_database.py --force

# View in pgAdmin
# Start Menu → pgAdmin 4
```

### Python Packages

```bash
# List installed
pip list

# Check specific package
pip show flask

# Install new package
pip install package_name

# Update requirements.txt
pip freeze > requirements.txt
```

---

## ✅ Summary

**What You Have Now:**

| Component | Status | Details |
|-----------|--------|---------|
| PostgreSQL | ✅ Installed | Version 18.1 |
| Database | ✅ Created | miblock_components |
| Tables | ✅ Ready | 3 tables, 0 rows |
| Python | ✅ Installed | Version 3.13.1 |
| Virtual Env | ✅ Created | venv/ folder |
| Dependencies | ✅ Installed | 40+ packages |
| Configuration | ✅ Done | .env file |
| Connection | ✅ Verified | All working |

**Ready for:** ✅ Phase 1 Implementation

---

**Last Updated:** December 29, 2025  
**PostgreSQL Version:** 18.1  
**Python Version:** 3.13.1  
**Virtual Environment:** venv/  
**Dependencies:** 40+ packages installed

---

## 🎯 Next Step

Say: **"Start Phase 1"** to begin implementation! 🚀

