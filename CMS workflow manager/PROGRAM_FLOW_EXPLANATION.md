# 🔄 CMS Workflow Manager - Complete Program Flow Explanation

## 📋 Table of Contents
1. [Application Startup](#1-application-startup)
2. [User Interaction Phase](#2-user-interaction-phase)
3. [Configuration Management](#3-configuration-management)
4. [Workflow Execution](#4-workflow-execution)
5. [Real-Time Progress (SSE)](#5-real-time-progress-sse)
6. [Processing Pipeline](#6-processing-pipeline)
7. [Completion & Reporting](#7-completion--reporting)

---

## 1. Application Startup

### 📍 **File: `app.py` (Lines 19-30)**

When you run `python app.py`, here's what happens:

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
│     • Log: "Loaded module: ..."         │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│  4. Server Starts                        │
│     • Port: 5000                        │
│     • Debug mode: ON                    │
│     • Ready to accept requests          │
└──────────────────────────────────────────┘
```

**Key Code:**
```python
# utils.py (Lines 22-34)
def load_step_modules():
    for step in PROCESSING_STEPS:
        module = importlib.import_module(f"processing_steps.{step['id']}")
        STEP_MODULES[step["module"]] = getattr(module, step["module"])
```

**Result:** All 5 processing steps are loaded and ready:
- ✅ `run_site_setup_step`
- ✅ `run_brand_theme_step`
- ✅ `run_content_plugin_step`
- ✅ `run_modules_features_step`
- ✅ `run_finalize_step`

---

## 2. User Interaction Phase

### 📍 **File: `templates/index.html` (JavaScript: Lines 959-1361)**

### **Step 1: User Opens Browser**

```
User → http://127.0.0.1:5000
         │
         ▼
┌─────────────────────────────────────┐
│  Flask Route: GET /                 │
│  (app.py: Line 33)                  │
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
// Line 960-964
let currentStep = 1;
const totalSteps = 5;
let jobId = generateJobId();  // Creates unique ID: "job_1234567890_abc123"
let workflowInProgress = false;
let eventSource = null;
```

**Job ID Generation:**
```javascript
function generateJobId() {
    return 'job_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
}
// Example: "job_1701355200000_k3j9x2m"
```

### **Step 3: User Fills Form & Navigates**

```
User clicks "Save & Next"
         │
         ▼
┌─────────────────────────────────────┐
│  nextStep() function               │
│  (Line 1097)                       │
│  1. collectFormData()              │
│  2. saveConfiguration()            │
│  3. currentStep++                  │
│  4. updateUI()                      │
└─────────────────────────────────────┘
```

**Form Data Collection (Lines 1023-1068):**
```javascript
async function collectFormData() {
    const formData = {
        job_id: jobId,
        sourceUrl: document.getElementById('sourceUrl')?.value || '',
        sourceSiteId: document.getElementById('sourceSiteId')?.value || '',
        // ... collects ALL form fields from all 5 steps
    };
    return formData;
}
```

---

## 3. Configuration Management

### 📍 **File: `app.py` (Route: `/api/save-config`)**

### **Flow Diagram:**

```
User clicks "Save & Next"
         │
         ▼
┌─────────────────────────────────────┐
│  JavaScript: saveConfiguration()   │
│  (Line 1070)                        │
│  • Collects all form data          │
│  • POST to /api/save-config        │
└──────────────┬──────────────────────┘
               │
         ┌─────▼─────┐
         │  Flask    │
         │  Route    │
         │  Handler  │
         └─────┬─────┘
               │
┌──────────────▼──────────────────────────┐
│  app.py: save_config()                   │
│  (Line 49-87)                             │
│  1. Extract job_id from request          │
│  2. Call save_job_config()                │
└──────────────┬───────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│  utils.py: save_job_config()             │
│  (Line 51-60)                             │
│  • Create file: uploads/{job_id}_config.json│
│  • Write JSON data                        │
│  • Return success/failure                  │
└───────────────────────────────────────────┘
```

**Configuration File Structure:**
```json
{
    "job_id": "job_1701355200000_k3j9x2m",
    "sourceUrl": "https://source-cms.com",
    "sourceSiteId": "12345",
    "destinationUrl": "https://dest-cms.com",
    "siteName": "My Migration Site",
    // ... all form fields
}
```

**File Location:** `uploads/job_1701355200000_k3j9x2m_config.json`

---

## 4. Workflow Execution

### 📍 **File: `app.py` (Route: `/api/start-workflow`)**

### **When User Clicks "Start Workflow" (Step 5):**

```
User clicks "Start Workflow"
         │
         ▼
┌─────────────────────────────────────┐
│  JavaScript: startWorkflow()         │
│  (Line 1097)                          │
│  1. Save final configuration          │
│  2. Set workflowInProgress = true    │
│  3. Show processing modal            │
│  4. POST to /api/start-workflow      │
└──────────────┬───────────────────────┘
               │
         ┌─────▼─────┐
         │  Flask    │
         │  Returns  │
         │  stream_url│
         └─────┬─────┘
               │
┌──────────────▼──────────────────────────┐
│  JavaScript: connectToWorkflowStream()    │
│  (Line 1134)                              │
│  • Create EventSource                    │
│  • Connect to /api/stream/{job_id}      │
└───────────────────────────────────────────┘
```

**Code Flow:**
```javascript
// 1. Save config
await saveConfiguration();

// 2. Show modal
showProcessingModal();

// 3. Start workflow
const response = await fetch('/api/start-workflow', {
    method: 'POST',
    body: JSON.stringify({ job_id: jobId })
});

// 4. Get stream URL
const streamUrl = result.stream_url;  // "/api/stream/job_123..."

// 5. Connect to SSE
eventSource = new EventSource(streamUrl);
```

---

## 5. Real-Time Progress (SSE)

### 📍 **File: `app.py` (Route: `/api/stream/<job_id>`)**

### **Server-Sent Events (SSE) Connection:**

```
Browser creates EventSource
         │
         ▼
┌─────────────────────────────────────┐
│  GET /api/stream/{job_id}            │
│  (app.py: Line 182)                  │
│  → Response with mimetype:           │
│    'text/event-stream'               │
└──────────────┬───────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│  utils.py: generate_workflow_stream()     │
│  (Line 68)                                 │
│  • Generator function                     │
│  • Yields SSE events                     │
│  • Executes processing pipeline           │
└───────────────────────────────────────────┘
```

### **SSE Event Format:**

```python
# utils.py: format_sse() (Line 63-65)
def format_sse(data: Dict[str, Any]) -> str:
    return f"data: {json.dumps(data)}\n\n"
```

**Example SSE Event:**
```
data: {"status":"in_progress","step_id":"site_setup","message":"Processing..."}

```

### **Event Types:**

| Status | When Sent | Purpose |
|--------|-----------|---------|
| `start` | Workflow begins | Initial message |
| `in_progress` | Step starts | Show step is running |
| `done` | Step completes | Mark step as done |
| `complete` | All steps done | Show completion |
| `error` | Error occurs | Show error message |
| `close` | Stream ends | Close connection |

---

## 6. Processing Pipeline

### 📍 **File: `utils.py` (Function: `generate_workflow_stream`)**

### **Pipeline Execution Flow:**

```
┌─────────────────────────────────────────┐
│  generate_workflow_stream(job_id)       │
│  (Line 68-183)                          │
└──────────────┬──────────────────────────┘
               │
         ┌─────▼─────┐
         │  Load     │
         │  Config   │
         └─────┬─────┘
               │
┌──────────────▼──────────────────────────┐
│  1. Initialize workflow_context          │
│     {                                    │
│       "job_id": "...",                  │
│       "start_time": 1701355200.0,       │
│       "job_config": {...},              │
│       "completed_steps": []             │
│     }                                    │
└──────────────┬───────────────────────────┘
               │
         ┌─────▼─────┐
         │  Yield    │
         │  "start"  │
         └─────┬─────┘
               │
┌──────────────▼──────────────────────────┐
│  2. Loop through PROCESSING_STEPS        │
│     (config.py: Lines 20-61)             │
│     • site_setup                         │
│     • brand_theme                        │
│     • content_plugin                     │
│     • modules_features                   │
│     • finalize                           │
└──────────────┬───────────────────────────┘
               │
    ┌──────────┼──────────┐
    │          │          │
┌───▼───┐  ┌───▼───┐  ┌───▼───┐
│ Step  │  │ Step  │  │ Step  │
│ Loop  │  │ Loop  │  │ Loop  │
└───┬───┘  └───┬───┘  └───┬───┘
    │          │          │
    └──────────┼──────────┘
               │
    ┌──────────▼──────────┐
    │  For Each Step:      │
    │  1. Yield "in_progress"│
    │  2. Execute step      │
    │  3. Yield "done"      │
    └───────────────────────┘
```

### **Step Execution Detail:**

```python
# utils.py (Lines 94-151)
for idx, step_config in enumerate(PROCESSING_STEPS, 1):
    # 1. Notify: Step starting
    yield format_sse({
        "status": "in_progress",
        "step_id": step_config["id"],
        "message": f"Processing: {step_config['description']}"
    })
    
    # 2. Get step function
    step_function = STEP_MODULES[step_config["module"]]
    
    # 3. Execute step
    step_result = step_function(
        job_id=job_id,
        step_config=step_config,
        workflow_context=workflow_context
    )
    
    # 4. Store results
    workflow_context[step_config["id"]] = step_result
    
    # 5. Notify: Step completed
    yield format_sse({
        "status": "done",
        "step_id": step_config["id"],
        "message": f"✓ Completed: {step_config['name']}"
    })
```

### **Example: Step 1 Execution**

```
┌─────────────────────────────────────────┐
│  Step 1: Site Setup                     │
│  File: processing_steps/site_setup.py   │
└──────────────┬──────────────────────────┘
               │
         ┌─────▼─────┐
         │  Function:│
         │  run_site_│
         │  setup_   │
         │  step()   │
         └─────┬─────┘
               │
┌──────────────▼──────────────────────────┐
│  1. Get job_config from context         │
│  2. Extract form data                   │
│     • sourceUrl, sourceSiteId          │
│     • destinationUrl, etc.              │
│  3. Validate required fields            │
│  4. Simulate processing (time.sleep)     │
│  5. Return results dict                 │
└──────────────┬───────────────────────────┘
               │
         ┌─────▼─────┐
         │  Results: │
         │  {        │
         │    "site_ │
         │    created":│
         │    true,   │
         │    "site_ │
         │    name": │
         │    "...", │
         │    "message":│
         │    "..."  │
         │  }        │
         └───────────┘
```

**Step Function Signature:**
```python
def run_site_setup_step(
    job_id: str,              # Unique job identifier
    step_config: Dict,        # Step config from config.py
    workflow_context: Dict    # Shared context (includes job_config)
) -> Dict[str, Any]:          # Returns results
```

---

## 7. Completion & Reporting

### 📍 **File: `utils.py` (Function: `generate_completion_report`)**

### **Completion Flow:**

```
All 5 steps complete
         │
         ▼
┌─────────────────────────────────────┐
│  Calculate total duration            │
│  total_duration = time.time() -      │
│                   start_time         │
└──────────────┬───────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│  generate_completion_report()            │
│  (Line 186-210)                           │
│  1. Create report structure              │
│  2. Add all step results                 │
│  3. Save to output/{job_id}_report.json │
└──────────────┬───────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│  Yield "complete" event                 │
│  {                                      │
│    "status": "complete",                │
│    "message": "🎉 Workflow completed!", │
│    "total_duration": 15.7,              │
│    "report_url": "/download/..."       │
│  }                                      │
└──────────────┬───────────────────────────┘
               │
         ┌─────▼─────┐
         │  Browser  │
         │  Receives │
         │  Event    │
         └─────┬─────┘
               │
┌──────────────▼──────────────────────────┐
│  JavaScript: handleWorkflowUpdate()      │
│  (Line 1156)                              │
│  • Show completion message               │
│  • Display download button               │
│  • Close SSE connection                  │
└───────────────────────────────────────────┘
```

### **Report Structure:**

```json
{
    "job_id": "job_1701355200000_k3j9x2m",
    "status": "completed",
    "total_duration_seconds": 15.7,
    "completed_steps": [
        "site_setup",
        "brand_theme",
        "content_plugin",
        "modules_features",
        "finalize"
    ],
    "timestamp": "2025-11-30 19:30:00",
    "configuration": {
        "sourceUrl": "...",
        "siteName": "..."
    },
    "results": {
        "site_setup": {
            "site_created": true,
            "site_name": "..."
        },
        "brand_theme": {...},
        "content_plugin": {...},
        "modules_features": {...},
        "finalize": {...}
    }
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
│  4. Server starts on port 5000                              │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    USER INTERACTION                          │
│  User opens http://127.0.0.1:5000                           │
│  → GET / → Renders index.html                               │
│  → JavaScript initializes (jobId generated)                │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    WIZARD NAVIGATION                         │
│  User fills Step 1 → Clicks "Save & Next"                   │
│  → collectFormData() → All form fields collected            │
│  → POST /api/save-config → Saves to uploads/{job_id}_config.json│
│  → currentStep++ → updateUI() → Shows Step 2                │
│  (Repeats for Steps 2, 3, 4)                                 │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    WORKFLOW INITIATION                      │
│  User on Step 5 → Clicks "Start Workflow"                   │
│  → startWorkflow() → Final config save                       │
│  → POST /api/start-workflow → Returns stream_url            │
│  → showProcessingModal() → Modal appears                     │
│  → connectToWorkflowStream() → EventSource created          │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    SSE CONNECTION                           │
│  GET /api/stream/{job_id}                                    │
│  → Response with mimetype: 'text/event-stream'               │
│  → generate_workflow_stream() starts                        │
│  → Browser receives events in real-time                     │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    PROCESSING PIPELINE                      │
│  Loop through PROCESSING_STEPS:                              │
│                                                               │
│  Step 1: site_setup                                          │
│    → Yield "in_progress" → Browser shows "Processing..."     │
│    → Execute run_site_setup_step()                          │
│    → Yield "done" → Browser shows "✓ Completed"             │
│                                                               │
│  Step 2: brand_theme                                         │
│    → Yield "in_progress" → Browser updates                   │
│    → Execute run_brand_theme_step()                          │
│    → Yield "done" → Browser updates                          │
│                                                               │
│  Step 3: content_plugin                                      │
│    → Same pattern...                                         │
│                                                               │
│  Step 4: modules_features                                    │
│    → Same pattern...                                         │
│                                                               │
│  Step 5: finalize                                            │
│    → Same pattern...                                         │
│    → Generate completion report                              │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    COMPLETION                               │
│  Yield "complete" event                                     │
│  → Browser receives completion message                      │
│  → Shows download button                                     │
│  → User can download report from /download/{filename}       │
│  → Yield "close" → SSE connection closes                     │
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

### **Workflow Context Flow:**
```
workflow_context = {
    "job_id": "...",
    "start_time": 1701355200.0,
    "job_config": {...},           # Loaded from JSON file
    "site_setup": {...},           # Results from Step 1
    "brand_theme": {...},          # Results from Step 2
    "content_plugin": {...},       # Results from Step 3
    "modules_features": {...},     # Results from Step 4
    "finalize": {...}              # Results from Step 5
}
```

### **SSE Event Flow:**
```
Server (utils.py) → format_sse() → "data: {...}\n\n"
                 → HTTP Response (text/event-stream)
                 → Browser EventSource
                 → event.onmessage
                 → handleWorkflowUpdate()
                 → UI Updates
```

---

## 🎯 Key Concepts

### **1. Dynamic Module Loading**
- Steps are loaded at startup using `importlib`
- No hardcoding - add new steps by updating `config.py`
- Functions stored in `STEP_MODULES` dictionary

### **2. Generator Pattern (SSE)**
- `generate_workflow_stream()` is a Python generator
- Uses `yield` to send events incrementally
- Allows real-time streaming without blocking

### **3. Shared Context**
- `workflow_context` passed to each step
- Contains job config and previous step results
- Steps can access data from earlier steps

### **4. Event-Driven UI**
- Browser uses EventSource API (native JavaScript)
- No polling - server pushes updates
- Automatic reconnection on network issues

### **5. Persistent Configuration**
- All form data saved to JSON file
- Survives page refresh
- Can resume workflow if needed

---

## 🔍 Debugging Tips

### **Check Configuration:**
```bash
# View saved config
cat uploads/job_*_config.json
```

### **Check Reports:**
```bash
# View completion report
cat output/job_*_report.json
```

### **Monitor Logs:**
- Console output shows all step executions
- Logs include timing and error messages
- Check for "Loaded module" messages at startup

### **Test SSE Connection:**
```javascript
// In browser console
const es = new EventSource('/api/stream/job_123');
es.onmessage = (e) => console.log(JSON.parse(e.data));
```

---

## 📚 File Responsibilities

| File | Responsibility |
|------|---------------|
| `app.py` | HTTP routes, request handling, file uploads |
| `config.py` | Pipeline definition, settings, constants |
| `utils.py` | Orchestration, SSE streaming, config management |
| `processing_steps/*.py` | Individual step logic |
| `templates/index.html` | UI, JavaScript, form handling |

---

## 🎓 Summary

**The program flow follows this pattern:**

1. **Startup** → Load modules → Start server
2. **User Input** → Fill wizard → Save config
3. **Initiate** → Start workflow → Connect SSE
4. **Process** → Execute steps → Stream updates
5. **Complete** → Generate report → Download

**Key Technologies:**
- ✅ Flask for web framework
- ✅ Server-Sent Events for real-time updates
- ✅ Dynamic module loading for extensibility
- ✅ JSON for configuration persistence
- ✅ Generator pattern for streaming

**This architecture provides:**
- ✨ Real-time user feedback
- ✨ Modular, extensible design
- ✨ Persistent configuration
- ✨ Error handling at multiple levels
- ✨ Production-ready structure

---

**🎉 You now understand the complete program flow!**

