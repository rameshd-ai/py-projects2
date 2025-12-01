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
2. **Step-by-Step Processing** - Each step processes immediately when you click "Process"
3. **Visual Status Indicators** - Green ✓ (success), Red ✗ (failed), Orange ⊘ (skipped)
4. **Downloadable Reports** after all steps complete

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
- Review the summary
- Click **"Process"** to complete the final step
- Final report will be generated automatically

---

## 🎉 Success!

Each step processes immediately when you click "Process":
- **✓ Green Checkmark** = Step completed successfully
- **✗ Red Cross** = Step failed (check error message)
- **⊘ Orange Symbol** = Step skipped (not enabled/selected)

After all 5 steps, a completion report is generated automatically.

---

## 📝 Notes

- **Step-by-Step Processing**: Each step executes immediately when "Process" is clicked
- **Status Persistence**: Step status (✓/✗/⊘) persists when navigating between steps
- **Results Saved**: Each step's results are saved to `uploads/{job_id}_results.json`
- **Configuration Saved**: Form data saved to `uploads/{job_id}_config.json`
- **Final Report**: Generated in `output/` folder after Step 5 completes

---

## 🆘 Need Help?

Check the full [README.md](README.md) for detailed documentation.



