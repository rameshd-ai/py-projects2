# 🔄 CMS Workflow Manager - Complete Program Flow Explanation

## 📋 Table of Contents
1. [Application Startup](#1-application-startup)
2. [User Interaction Phase](#2-user-interaction-phase)
3. [Step-by-Step Processing](#3-step-by-step-processing)
4. [Configuration Management](#4-configuration-management)
5. [Status Tracking](#5-status-tracking)
6. [Completion & Reporting](#6-completion--reporting)

---

## 1. Application Startup

### 📍 **File: `app.py`**

When you run `python app.py`:

```
┌─────────────────────────────────────────┐
│  1. Flask App Initialization            │
│     • app = Flask(__name__)             │
│     • Configure upload/output folders    │
│     • Set max file size (16MB)          │
│     • Initialize logging                 │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│  2. Import Modules                      │
│     • config.py → Loads PROCESSING_STEPS│
│     • utils.py → Loads step modules     │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│  3. Dynamic Module Loading               │
│     (utils.py: load_step_modules)       │
│     • Loop through PROCESSING_STEPS      │
│     • Import each step module           │
│     • Store functions in STEP_MODULES  │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│  4. Server Starts                        │
│     • Port: 5000                        │
│     • Debug mode: ON                    │
│     • Ready to accept requests          │
└──────────────────────────────────────────┘
```

**Result:** All 5 processing steps are loaded and ready:
- ✅ `run_site_setup_step`
- ✅ `run_brand_theme_step`
- ✅ `run_content_plugin_step`
- ✅ `run_modules_features_step`
- ✅ `run_finalize_step`

---

## 2. User Interaction Phase

### 📍 **File: `templates/index.html` (JavaScript)**

### **Step 1: User Opens Browser**

```
User → http://127.0.0.1:5000
         │
         ▼
┌─────────────────────────────────────┐
│  Flask Route: GET /                 │
│  → render_template('index.html')    │
└──────────────┬──────────────────────┘
               │
         ┌─────▼─────┐
         │  Browser  │
         │  Renders  │
         │  Wizard   │
         └───────────┘
```

### **Step 2: JavaScript Initialization**

```javascript
let currentStep = 1;
const totalSteps = 5;
let jobId = generateJobId();  // "job_1701355200000_abc123"
let stepStatus = {};  // Track: 'success', 'failed', 'skipped'
```

---

## 3. Step-by-Step Processing

### 📍 **NEW FLOW: Each Step Processes Immediately**

### **When User Clicks "Process" Button:**

```
User clicks "Process" on Step 1
         │
         ▼
┌─────────────────────────────────────┐
│  JavaScript: saveAndProcessStep()     │
│  1. Show processing indicator (⟳)  │
│  2. Collect form data               │
│  3. POST to /api/save-config        │
│     with step_number: 1             │
└──────────────┬──────────────────────┘
               │
         ┌─────▼─────┐
         │  Flask    │
         │  Route    │
         └─────┬─────┘
               │
┌──────────────▼──────────────────────────┐
│  app.py: save_config()                   │
│  1. Save configuration                   │
│  2. Call execute_single_step(1)         │
└──────────────┬───────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│  utils.py: execute_single_step()        │
│  1. Load job config                     │
│  2. Load previous step results          │
│  3. Execute step function               │
│  4. Save results to uploads/{job_id}_results.json│
│  5. Return status: 'success' or 'skipped'│
└──────────────┬───────────────────────────┘
               │
         ┌─────▼─────┐
         │  Browser  │
         │  Updates │
         │  Icon     │
         └─────┬─────┘
               │
    ┌──────────┼──────────┐
    │          │          │
┌───▼───┐  ┌───▼───┐  ┌───▼───┐
│  ✓    │  │  ✗    │  │  ⊘    │
│ Green │  │ Red   │  │Orange │
│Success│  │Failed │  │Skipped│
└───────┘  └───────┘  └───────┘
```

### **Step Execution Flow:**

```javascript
// 1. User clicks "Process"
async function saveAndProcessStep() {
    // 2. Show spinner
    stepIcon.innerHTML = '⟳';
    stepIcon.style.background = '#2563eb';
    
    // 3. Send request
    const response = await fetch('/api/save-config', {
        method: 'POST',
        body: JSON.stringify({
            job_id: jobId,
            step_number: currentStep,
            // ... all form data
        })
    });
    
    // 4. Get result
    const result = await response.json();
    
    // 5. Update icon based on status
    if (result.step_result?.status === 'skipped') {
        stepStatus[currentStep] = 'skipped';
        stepIcon.innerHTML = '⊘';  // Orange
        stepIcon.style.background = '#f59e0b';
    } else if (result.success) {
        stepStatus[currentStep] = 'success';
        stepIcon.innerHTML = '✓';  // Green
        stepIcon.style.background = '#10b981';
    } else {
        stepStatus[currentStep] = 'failed';
        stepIcon.innerHTML = '✗';  // Red
        stepIcon.style.background = '#ef4444';
    }
}
```

---

## 4. Configuration Management

### 📍 **File: `app.py` (Route: `/api/save-config`)**

### **Flow Diagram:**

```
User clicks "Process"
         │
         ▼
┌─────────────────────────────────────┐
│  JavaScript: saveAndProcessStep()     │
│  • Collects all form data            │
│  • Adds step_number                  │
│  • POST to /api/save-config          │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│  app.py: save_config()                   │
│  1. Extract job_id and step_number       │
│  2. Save configuration to JSON           │
│  3. If step_number > 0:                  │
│     → Call execute_single_step()         │
└──────────────┬───────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│  utils.py: execute_single_step()        │
│  1. Load job_config from JSON           │
│  2. Load previous results from           │
│     uploads/{job_id}_results.json       │
│  3. Build workflow_context              │
│  4. Execute step function               │
│  5. Save results to results.json        │
│  6. Return status                       │
└───────────────────────────────────────────┘
```

**Files Created:**
- `uploads/{job_id}/config.json` - Configuration
- `uploads/{job_id}/results.json` - Step results
- `uploads/{job_id}/source_*.json` - Source site API responses
- `uploads/{job_id}/destination_*.json` - Destination site API responses
- `uploads/{job_id}/*_mapper.json` - Updated variable mappings
- `uploads/{job_id}/update_*.json` - API payloads and responses

---

## 5. Status Tracking

### 📍 **Visual Status Indicators**

### **Status Types:**

| Status | Icon | Color | CSS Class | When Shown |
|--------|------|-------|-----------|------------|
| **Success** | ✓ | Green (#10b981) | `.completed` | Step completed successfully |
| **Failed** | ✗ | Red (#ef4444) | `.failed` | Step processing failed |
| **Skipped** | ⊘ | Orange (#f59e0b) | `.skipped` | Step was skipped/not enabled |
| **Processing** | ⟳ | Blue (#2563eb) | `.active` | Step is currently executing |
| **Pending** | (empty) | Gray border | `.pending` | Step not started yet |

### **Status Detection Logic:**

```javascript
// In saveAndProcessStep()
const stepStatusFromBackend = result.step_result?.status || 'success';
const stepMessage = result.step_result?.result?.message || '';

// Check if skipped
const isSkipped = stepStatusFromBackend === 'skipped' || 
                 stepMessage.toLowerCase().includes('skipped') || 
                 stepMessage.toLowerCase().includes('not enabled');

// Update status
if (!result.success) {
    stepStatus[currentStep] = 'failed';  // Red ✗
} else if (isSkipped) {
    stepStatus[currentStep] = 'skipped';  // Orange ⊘
} else {
    stepStatus[currentStep] = 'success';  // Green ✓
}
```

### **Status Persistence:**

```javascript
// Status is stored in stepStatus object
let stepStatus = {
    1: 'success',   // Step 1 completed
    2: 'skipped',   // Step 2 skipped
    3: 'success',   // Step 3 completed
    4: 'failed',   // Step 4 failed
    5: 'pending'    // Step 5 not started
};

// Status persists when navigating between steps
// Only clears when starting new workflow
```

---

## 6. Completion & Reporting

### 📍 **File: `app.py` (Route: `/api/generate-report`)**

### **Final Step Flow:**

```
User on Step 5 → Clicks "Process"
         │
         ▼
┌─────────────────────────────────────┐
│  Step 5 executes (finalize)          │
│  → Generates deployment summary      │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│  JavaScript: showCompletion()            │
│  → POST /api/generate-report            │
└──────────────┬───────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│  app.py: generate_report()               │
│  1. Load all results from results.json  │
│  2. Load job configuration              │
│  3. Create comprehensive report         │
│  4. Save to output/{job_id}_report.json│
│  5. Return download URL                  │
└──────────────────────────────────────────┘
```

**Report Structure:**
```json
{
    "job_id": "job_123...",
    "status": "completed",
    "timestamp": "2025-11-30 19:30:00",
    "configuration": {...},
    "results": {
        "site_setup": {...},
        "brand_theme": {...},
        "content_plugin": {...},
        "modules_features": {...},
        "finalize": {...}
    },
    "completed_steps": ["site_setup", "brand_theme", ...]
}
```

---

## 🔄 Complete Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    APPLICATION STARTUP                       │
│  1. Flask app initializes                                    │
│  2. Load config.py → PROCESSING_STEPS                       │
│  3. utils.py loads all step modules dynamically             │
│  4. Server starts on port 5000                               │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    USER INTERACTION                          │
│  User opens http://127.0.0.1:5000                           │
│  → GET / → Renders index.html                               │
│  → JavaScript initializes (jobId generated)                  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    STEP-BY-STEP PROCESSING                  │
│                                                               │
│  Step 1: Fill form → Click "Process"                          │
│    → POST /api/save-config (step_number: 1)                 │
│    → execute_single_step(1)                                 │
│    → Step icon: ⟳ → ✓ (green) or ✗ (red) or ⊘ (orange)     │
│    → Moves to Step 2                                         │
│                                                               │
│  Step 2: Fill form → Click "Process"                         │
│    → POST /api/save-config (step_number: 2)                 │
│    → execute_single_step(2)                                 │
│    → Loads Step 1 results from results.json                  │
│    → Step icon: ⟳ → ✓/✗/⊘                                   │
│    → Moves to Step 3                                         │
│                                                               │
│  Step 3: Fill form → Click "Process"                         │
│    → POST /api/save-config (step_number: 3)                 │
│    → execute_single_step(3)                                 │
│    → Loads Steps 1 & 2 results                               │
│    → Step icon: ⟳ → ✓/✗/⊘                                   │
│    → Moves to Step 4                                         │
│                                                               │
│  Step 4: Fill form → Click "Process"                         │
│    → POST /api/save-config (step_number: 4)                 │
│    → execute_single_step(4)                                 │
│    → Loads Steps 1, 2, 3 results                            │
│    → Step icon: ⟳ → ✓/✗/⊘                                   │
│    → Moves to Step 5                                         │
│                                                               │
│  Step 5: Review → Click "Process"                            │
│    → POST /api/save-config (step_number: 5)                 │
│    → execute_single_step(5)                                 │
│    → Loads all previous results                             │
│    → Generates deployment summary                            │
│    → POST /api/generate-report                               │
│    → Final report generated                                  │
│    → Download link provided                                  │
└─────────────────────────────────────────────────────────────┘
```

---

## 📊 Data Flow Summary

### **Configuration Flow:**
```
Form Fields → JavaScript collectFormData()
           → POST /api/save-config
           → utils.py save_job_config()
           → uploads/{job_id}_config.json
```

### **Step Results Flow:**
```
Step Execution → execute_single_step()
              → Step function returns results
              → Save to uploads/{job_id}_results.json
              → Next step loads previous results
```

### **Status Tracking:**
```
Backend Response → JavaScript checks status
                → Updates stepStatus object
                → updateUI() shows correct icon
                → Status persists across navigation
```

---

## 🎯 Key Concepts

### **1. Immediate Step Processing**
- Each step executes **immediately** when "Process" is clicked
- No waiting until the end
- Results saved after each step

### **2. Sequential Dependency**
- Each step can access previous step results
- Steps validate dependencies
- Example: Step 2 checks if Step 1 completed

### **3. Status Tracking**
- Three states: success (✓), failed (✗), skipped (⊘)
- Status persists in `stepStatus` object
- Visual feedback in real-time

### **4. Results Persistence**
- Results saved to `uploads/{job_id}_results.json`
- Each step adds its results
- Next steps can read previous results

### **5. Error Handling**
- Failed steps show red cross (✗)
- Workflow can continue (user decides)
- Clear error messages displayed

---

## 🔍 Step Execution Details

### **Example: Step 1 Execution**

```python
# utils.py: execute_single_step(job_id, 1)
def execute_single_step(job_id: str, step_number: int):
    # 1. Load configuration
    job_config = load_job_config(job_id)
    
    # 2. Build workflow context
    workflow_context = {
        "job_id": job_id,
        "job_config": job_config
    }
    
    # 3. Load previous results (if any)
    results_file = f"uploads/{job_id}_results.json"
    if os.path.exists(results_file):
        previous_results = json.load(results_file)
        workflow_context.update(previous_results)
    
    # 4. Execute step
    step_function = STEP_MODULES["run_site_setup_step"]
    step_result = step_function(job_id, step_config, workflow_context)
    
    # 5. Save results
    all_results[step_id] = step_result
    save_to_file(all_results)
    
    # 6. Return status
    return {
        "success": True,
        "step_id": "site_setup",
        "result": step_result,
        "status": "success" or "skipped"
    }
```

---

## 📚 File Responsibilities

| File | Responsibility |
|------|---------------|
| `app.py` | HTTP routes, step processing trigger, job management |
| `config.py` | Pipeline definition, settings |
| `utils.py` | Single step execution, config management, job folders |
| `apis.py` | CMS API integrations (tokens, theme, updates) |
| `processing_steps/*.py` | Individual step logic, API orchestration |
| `resource/*.json` | Mapping templates (font, color) |
| `templates/index.html` | UI, status tracking, visual feedback |
| `templates/jobs_list.html` | Job management interface |

---

## 🎓 Summary

**The program flow follows this pattern:**

1. **Startup** → Load modules → Start server
2. **User Input** → Fill step form → Click "Process"
3. **Immediate Processing** → Execute step → Save results
4. **Status Update** → Show ✓/✗/⊘ → Move to next step
5. **Repeat** → Steps 2, 3, 4, 5
6. **Complete** → Generate report → Download

**Key Technologies:**
- ✅ Flask for web framework
- ✅ Step-by-step execution (not batch)
- ✅ JSON for configuration persistence
- ✅ Status tracking for visual feedback
- ✅ Dependency validation between steps

**This architecture provides:**
- ✨ Immediate feedback per step
- ✨ Clear success/failure/skip indicators
- ✨ Sequential dependency validation
- ✨ Results persistence
- ✨ Error handling at step level

---

**🎉 You now understand the complete step-by-step program flow!**
