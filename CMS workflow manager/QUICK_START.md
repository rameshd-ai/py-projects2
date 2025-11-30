# 🚀 Quick Start Guide - CMS Workflow Manager

## Get Started in 3 Steps!

### Step 1: Activate Virtual Environment

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

### Step 2: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 3: Run the Application

**Option A: Use the run script (Windows)**
```cmd
run.bat
```

**Option B: Use the run script (Linux/Mac)**
```bash
chmod +x run.sh
./run.sh
```

**Option C: Run directly**
```bash
python app.py
```

### Step 4: Open Your Browser

Navigate to: **http://localhost:5000**

---

## 🎯 What You'll See

1. **Beautiful Wizard Interface** with 5 steps
2. **Real-time Progress Tracking** when you start a workflow
3. **Downloadable Reports** after completion

---

## 📋 Quick Test Workflow

Fill in the form with sample data:

### Step 1 - Site Setup:
- **Source URL**: `https://source-site.com`
- **Source Site ID**: `12345`
- **Destination URL**: `https://destination-site.com`
- **Destination Site ID**: `67890`
- **Site Name**: `Test Migration Site`
- **Site URL**: `https://test-site.web5`

### Step 2 - Brand/Theme:
- Check "Pull from Current Site" or upload a sample CSV

### Step 3 - Content:
- Check "MiBlock Records Migration" (optional)

### Step 4 - Modules:
- Select any modules you want to test

### Step 5 - Review & Complete:
- Click "Start Workflow"
- Watch the real-time progress!

---

## 🎉 Success!

Your workflow will process in real-time and generate a completion report that you can download.

---

## 📝 Notes

- Configuration is saved automatically as you navigate between steps
- Each workflow gets a unique Job ID
- Reports are saved in the `output/` folder
- Logs are available in the console and `workflow.log`

---

## 🆘 Need Help?

Check the full [README.md](README.md) for detailed documentation.


