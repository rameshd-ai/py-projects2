# FINAL DEVELOPMENT PLAN
## Figma to MiBlock CMS Component Generator

> **📌 Implementation Approach**: This plan contains **122 numbered steps** across 8 phases.  
> **🌐 Browser-Based Application**: Everything runs in the web browser - no CLI usage required!  
> **🔗 Figma URL Input**: Paste Figma URL, system automatically extracts sections and screenshots via Figma API  
> **🔄 On-Demand Training**: Refresh component library anytime with a browser button - no CLI!  
> You can guide implementation by saying "work on step X" or "start from step Y".  
> See [Master Workflow](#-master-workflow---numbered-implementation-steps) section for complete numbered list.

---

## 🎯 IMPLEMENTATION STATUS

**Last Updated**: December 29, 2025

> 📁 **Detailed Phase Documentation**: See `docs/phases/` folder for comprehensive documentation of each phase, including all steps, files created, and their purposes.

### ✅ Phase 1: Foundation & Setup (Steps 1-15) - COMPLETED

📖 **Full Documentation**: [docs/phases/PHASE_1_FOUNDATION.md](docs/phases/PHASE_1_FOUNDATION.md)

**What was implemented:**

1. ✅ **Project Structure** - Created complete directory structure:
   - `src/api/` - API clients
   - `src/agents/` - AI agents (base classes)
   - `src/models/` - Database models
   - `src/config/` - Configuration management
   - `src/utils/` - Utilities (logging, caching)
   - `frontend/` - Web UI (placeholder)
   - `scripts/` - Setup scripts
   - `tests/` - Unit tests (placeholder)

2. ✅ **Dependencies** - Created `requirements.txt` with all necessary packages:
   - FastAPI, uvicorn - Web framework
   - PostgreSQL, pgvector, SQLAlchemy - Database
   - Redis - Caching
   - Anthropic, Claude - AI generation
   - CLIP, torch, transformers - Visual embeddings
   - LangGraph, langchain - Agent orchestration
   - All supporting libraries

3. ✅ **Configuration** - Created comprehensive configuration system:
   - `env.example` - Template with all environment variables
   - `src/config/settings.py` - Pydantic settings with validation
   - Auto-directory creation for storage/logs
   - Support for all features (API keys, thresholds, etc.)

4. ✅ **Database Setup** - Created PostgreSQL schema with pgvector:
   - `scripts/setup_database.sql` - Complete schema
   - `components` table with vector(512) column for CLIP embeddings
   - `generation_tasks` table for tracking component generation
   - `library_refresh_tasks` table for tracking library training
   - pgvector indexes (IVFFlat) for fast similarity search
   - Helper functions for search and updates
   - Views for statistics

5. ✅ **Database Models** - Created SQLAlchemy ORM models:
   - `src/models/database.py` - Component, GenerationTask, LibraryRefreshTask
   - Full integration with pgvector extension
   - Proper relationships and indexes

6. ✅ **Figma API Client** - Full implementation:
   - `src/api/figma_client.py` - Complete Figma API integration
   - URL parsing (extract file_id, node_id)
   - Detect page vs node URLs
   - Get file structure and sections
   - Get screenshots via Figma API
   - Extract metadata
   - Rate limiting (60 req/min)
   - Comprehensive error handling

7. ✅ **CMS API Client** - Full implementation:
   - `src/api/cms_client.py` - Complete CMS API integration
   - Download component list
   - Download Config, Format, Records JSON
   - Download component screenshots
   - Batch downloading with progress tracking
   - Support for active-only records filtering
   - Rate limiting and error handling

8. ✅ **Claude API Client** - Full implementation:
   - `src/api/claude_client.py` - Anthropic Claude integration
   - Generate HTML from screenshots
   - Analyze HTML structure
   - Extract component definitions
   - Create Handlebars templates
   - Visual validation
   - Rate limiting and error handling

9. ✅ **FastAPI Application** - Base application structure:
   - `src/main.py` - Complete FastAPI application
   - CORS middleware configured
   - REST API endpoints (generation, library management)
   - WebSocket support for real-time updates
   - Connection manager for WebSockets
   - Health check endpoints
   - Static file serving for frontend
   - Lifespan management (startup/shutdown)

10. ✅ **Base Agent Class** - Agent infrastructure:
    - `src/agents/base_agent.py` - BaseAgent abstract class
    - Timeout and retry logic
    - Execution tracking and statistics
    - Progress callbacks
    - AgentOrchestrator for running agents in sequence/parallel
    - Error handling (AgentError, AgentTimeoutError)
    - Structured logging integration

11. ✅ **Logging System** - Structured logging:
    - `src/utils/logging_config.py` - structlog configuration
    - JSON and console output formats
    - Log levels configurable
    - Log file rotation ready
    - Integration with all modules

12. ✅ **Caching System** - Redis caching:
    - `src/utils/cache.py` - Full Redis cache implementation
    - Get/Set/Delete operations
    - Pattern-based clearing
    - TTL support
    - Decorator for function result caching
    - Statistics and monitoring
    - Graceful degradation if Redis unavailable

13. ✅ **Documentation**:
    - `README.md` - Comprehensive project documentation
    - Quick start guide
    - Architecture overview
    - API endpoints
    - Troubleshooting guide
    - Configuration reference

**Files Created**:
- `requirements.txt` - All dependencies
- `env.example` - Configuration template
- `README.md` - Project documentation
- `scripts/setup_database.sql` - Database schema
- `src/config/settings.py` - Settings management
- `src/models/database.py` - ORM models
- `src/api/figma_client.py` - Figma API
- `src/api/cms_client.py` - CMS API
- `src/api/claude_client.py` - Claude AI API
- `src/main.py` - FastAPI application
- `src/agents/base_agent.py` - Base agent class
- `src/utils/logging_config.py` - Logging
- `src/utils/cache.py` - Redis caching
- All `__init__.py` files for proper Python packaging

**Next Steps**: Phase 2 (Steps 16-30) - Library Ingestion & Training Agent

### 🔄 In Progress
- None currently

### ⏳ Pending
- [ ] Phase 2 (Steps 16-30): Library Ingestion
- [ ] Phase 3 (Steps 31-42): HTML Generation
- [ ] Phase 4 (Steps 43-52): Structure Analysis
- [ ] Phase 5 (Steps 53-65): Definition Extraction
- [ ] Phase 6 (Steps 66-77): Template Generation
- [ ] Phase 7 (Steps 78-105): Orchestration + Figma + Web UI
- [ ] Phase 8 (Steps 106-122): Testing & Deployment

---

## ⭐ ARCHITECTURE DECISION

**Since deployment platform is uncertain (Azure, AWS, or others):**

### ✅ We will use: **Option A - Platform-Agnostic Architecture**

```
┌─────────────────────────────────────┐
│   Browser (Web UI)                  │
│   - Enter Figma URL                 │
│   - Preview detected sections       │
│   - Select sections to process      │
│   - See real-time progress          │
│   - Download results                │
└──────────────┬──────────────────────┘
               │ HTTP/WebSocket
               ▼
┌─────────────────────────────────────┐
│   Flask Server (Python 3.11+)       │
│   - Simple REST API                 │
│   - Serves web UI                   │
│   - WebSocket for live updates      │
│   - Figma API integration           │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│   Figma API Client                  │
│   - Parse Figma URL                 │
│   - Detect: Page vs Node/Section    │
│   - Get sections/nodes list         │
│   - Get screenshots via API         │
│   - Extract metadata                │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│   LangGraph (Agent Orchestration)   │
│   - Process each section            │
│   - Route to appropriate agents     │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│   Anthropic Claude API (Direct)     │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│   PostgreSQL + pgvector             │
│   In-Memory Cache (No Redis)        │
│   Storage (Screenshots/Results)     │
└─────────────────────────────────────┘
```

**Why this choice:**
- ✅ Works on Azure, AWS, GCP, on-prem - **ANY PLATFORM**
- ✅ No vendor lock-in
- ✅ Same code deploys everywhere
- ✅ Lower cost (~$305-430/month)
- ✅ Easy to migrate between clouds
- ✅ Maximum flexibility

**User Experience:**
- 🌐 **Web-based interface** - Everything runs in the browser
- 🔗 **Figma URL input** - Just paste the link, no manual screenshots!
- 🎯 **Auto-detect sections** - Processes entire page or single section
- ⚡ **Real-time updates** - Watch progress live per section
- 📥 **One-click download** - Get generated JSON files per section
- ❌ **No CLI usage** - Users never touch the command line!
- 📸 **No manual screenshots** - Figma API handles everything!

**Alternative (AWS-only):** Option B using AWS Bedrock is documented but NOT recommended for your case.

---

### 👥 Two Types of Users

#### **🔧 Developer (You) - Setup Phase**
- Uses CLI for setup (Steps 1-15):
  - Install dependencies: `pip install -r requirements.txt`
  - Setup database: `psql` commands
  - Run server: `python -m uvicorn ...`
  - Get Figma API token
- One-time setup only

#### **👤 End User - Usage Phase**
- **NEVER uses CLI!** Everything in browser:
  
  **Component Generation:**
  1. Open `http://your-domain.com` in browser
  2. Paste Figma URL (page or specific section)
  3. System auto-fetches sections via Figma API
  4. Preview detected sections
  5. Select sections to process
  6. Click "Generate"
  7. Download results per section
  
  **Library Training/Refresh:**
  1. Click "🔄 Refresh Library" button in browser
  2. Choose: Full Refresh or Incremental Update
  3. Watch real-time progress:
     - Downloading components from CMS
     - Generating embeddings
     - Storing in database
  4. See completion summary
  5. Library is now updated!
  
- **Pure web interface** ✅
- **No manual screenshots needed** ✅
- **No CLI for training** ✅

**Bottom Line:** 
- **Setup requires CLI** (developer only, one time)
- **Everything else is 100% browser-based** (component generation + library training!) ✅

---

## 🔗 Figma API Integration Details

### How Figma URL Processing Works

**Step 1: URL Parsing**
```python
# User inputs Figma URL (two types):

# Type A: Specific Node/Section URL
# https://www.figma.com/file/ABC123/Design?node-id=123:456
# → Processes only that specific node

# Type B: Page/File URL  
# https://www.figma.com/file/ABC123/Design
# → Processes all sections/frames on the page
```

**Step 2: Figma API Calls**
```python
import requests

# Get file structure
response = requests.get(
    f"https://api.figma.com/v1/files/{file_id}",
    headers={"X-Figma-Token": FIGMA_API_TOKEN}
)

# Extract sections/frames
if node_id:
    # Single node specified
    sections = [get_node_by_id(node_id)]
else:
    # Get all top-level frames/sections on page
    sections = get_all_frames_on_page(page_id)
```

**Step 3: Get Screenshots via Figma API**
```python
# Figma provides screenshot endpoint
for section in sections:
    screenshot_url = requests.get(
        f"https://api.figma.com/v1/images/{file_id}",
        params={
            "ids": section['id'],
            "format": "png",
            "scale": 2
        },
        headers={"X-Figma-Token": FIGMA_API_TOKEN}
    )
    
    # Download screenshot
    screenshot_data = requests.get(screenshot_url['images'][section['id']])
    save_screenshot(screenshot_data, f"section_{section['id']}.png")
```

**Step 4: Extract Metadata**
```python
for section in sections:
    metadata = {
        "name": section['name'],  # e.g., "Hero Section"
        "type": section['type'],  # e.g., "FRAME"
        "width": section['absoluteBoundingBox']['width'],
        "height": section['absoluteBoundingBox']['height'],
        "x": section['absoluteBoundingBox']['x'],
        "y": section['absoluteBoundingBox']['y']
    }
```

**Step 5: Process Each Section**
```python
results = []
for section in sections:
    # Each section goes through full pipeline:
    result = orchestrator.process(
        screenshot=section['screenshot'],
        metadata=section['metadata']
    )
    results.append(result)

# Return all results
return {
    "sections_processed": len(sections),
    "results": results
}
```

### Figma API Requirements

**Authentication:**
- Personal Access Token required
- Get from: Figma Account Settings → Personal Access Tokens
- Set in `.env`: `FIGMA_API_TOKEN=your_token_here`

**API Endpoints Used:**
1. `GET /v1/files/:file_key` - Get file structure
2. `GET /v1/images/:file_key` - Get node screenshots
3. `GET /v1/files/:file_key/nodes` - Get specific nodes

**Rate Limits:**
- 60 requests per minute per token
- Need to implement rate limiting and retry logic

---

## 🔄 Library Refresh Feature (Browser-Based Training)

### Overview

Instead of using CLI commands to refresh the component library, users can click a button in the browser to trigger the training process.

### Backend API Endpoints

```python
# FastAPI endpoints for library refresh

@app.post("/api/library/refresh")
async def refresh_library(refresh_type: str = "incremental"):
    """
    Trigger library refresh
    - refresh_type: "full" or "incremental"
    """
    # Start background task
    task_id = start_library_refresh_task(refresh_type)
    return {"task_id": task_id, "status": "started"}

@app.get("/api/library/status")
async def get_library_status():
    """
    Get current library statistics
    """
    return {
        "total_components": 150,
        "last_refresh": "2025-12-29T10:30:00Z",
        "status": "ready"  # or "refreshing"
    }

@app.get("/api/library/refresh/progress/{task_id}")
async def get_refresh_progress(task_id: str):
    """
    Get real-time progress of library refresh
    """
    return {
        "task_id": task_id,
        "status": "in_progress",  # or "completed", "failed"
        "progress": {
            "download": {"current": 45, "total": 150},
            "embeddings": {"current": 30, "total": 45},
            "storage": {"current": 30, "total": 45}
        },
        "current_component": "Hero Section Variant 3",
        "estimated_time_remaining": 300  # seconds
    }
```

### WebSocket Updates

```python
# Real-time progress via WebSocket

@app.websocket("/ws/library/refresh/{task_id}")
async def library_refresh_websocket(websocket: WebSocket, task_id: str):
    await websocket.accept()
    
    # Send progress updates
    while task_running:
        progress = get_task_progress(task_id)
        await websocket.send_json({
            "type": "progress",
            "data": progress
        })
        await asyncio.sleep(1)
    
    # Send completion
    await websocket.send_json({
        "type": "complete",
        "data": {
            "total_components": 150,
            "new": 5,
            "updated": 12,
            "time_taken": 720  # seconds
        }
    })
```

### Frontend Implementation

```javascript
// Library Refresh Button Handler
document.getElementById('refreshLibraryBtn').addEventListener('click', async () => {
    // Show progress modal
    showRefreshModal();
    
    // Start refresh
    const response = await fetch('/api/library/refresh', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({refresh_type: 'incremental'})
    });
    
    const {task_id} = await response.json();
    
    // Connect WebSocket for live updates
    const ws = new WebSocket(`ws://localhost:8000/ws/library/refresh/${task_id}`);
    
    ws.onmessage = (event) => {
        const {type, data} = JSON.parse(event.data);
        
        if (type === 'progress') {
            // Update progress bars
            updateDownloadProgress(data.progress.download);
            updateEmbeddingProgress(data.progress.embeddings);
            updateStorageProgress(data.progress.storage);
            updateCurrentComponent(data.current_component);
        }
        
        if (type === 'complete') {
            // Show success message
            showCompletionSummary(data);
            ws.close();
        }
    };
});
```

### Refresh Options

**Full Refresh:**
- Re-downloads ALL components from CMS
- Regenerates ALL embeddings
- Rebuilds entire database
- Use when: Major changes to CMS, or first-time setup

**Incremental Refresh:**
- Only downloads new/updated components
- Only generates embeddings for new components
- Updates existing records
- Use when: Regular updates, adding new components

### Background Processing

```python
from celery import Celery  # or use FastAPI background tasks

@app.post("/api/library/refresh")
async def refresh_library(
    refresh_type: str = "incremental",
    background_tasks: BackgroundTasks
):
    task_id = str(uuid.uuid4())
    
    # Run in background so it doesn't block
    background_tasks.add_task(
        run_library_refresh,
        task_id=task_id,
        refresh_type=refresh_type
    )
    
    return {"task_id": task_id, "status": "started"}

async def run_library_refresh(task_id: str, refresh_type: str):
    """
    Runs the library ingestion agent (Agent 0)
    """
    agent = LibraryIngestionAgent()
    
    # Update progress as we go
    await agent.ingest(
        refresh_type=refresh_type,
        progress_callback=lambda p: update_task_progress(task_id, p)
    )
```

### Progress Tracking

Track these phases:
1. **Downloading** (0-60%):
   - Fetching component list from CMS
   - Downloading Config/Format/Records
   - Downloading screenshots
   
2. **Embedding Generation** (60-85%):
   - Loading CLIP model
   - Processing each screenshot
   - Generating 512-dim vectors
   
3. **Database Storage** (85-100%):
   - Inserting/updating records
   - Storing embeddings
   - Rebuilding pgvector index

### Error Handling

```python
try:
    await agent.ingest(...)
except CMSAPIError as e:
    # CMS API failed
    update_task_status(task_id, "failed", error="CMS API unavailable")
except EmbeddingError as e:
    # CLIP model failed
    update_task_status(task_id, "failed", error="Embedding generation failed")
except DatabaseError as e:
    # Database failed
    update_task_status(task_id, "failed", error="Database error")
```

**Show user-friendly errors in the UI:**
- "Failed to connect to CMS API - check your API key"
- "Embedding generation failed - CLIP model may need reinstalling"
- "Database error - check PostgreSQL connection"

---

## 📑 Table of Contents

1. [Understanding Your CMS Structure](#understanding-your-cms-structure)
2. [System Goal & Architecture](#system-goal)
3. [Why pgvector?](#why-pgvector)
4. [Quick Reference: Your Questions Answered](#-quick-reference-your-questions-answered)
5. [Visual System Flow](#visual-summary-complete-system-flow)
6. [**Master Workflow - 100 Numbered Steps** 🔢](#-master-workflow---numbered-implementation-steps) ⭐
7. [Detailed Agent Specifications](#detailed-agent-specifications)
8. [Implementation Phases (8 Weeks)](#implementation-phases-8-weeks)
9. [Data Flow Example](#data-flow-example---complete-walkthrough)
10. [Success Metrics](#success-metrics)
11. [Technology Stack](#technology-stack)
12. [Progress Tracking](#-progress-tracking)
13. [Next Steps](#next-steps-to-begin-implementation)
14. [Questions to Clarify](#questions-to-clarify-before-starting)

---

## Understanding Your CMS Structure

Based on the sample data in `mi-block-ID-560183/`, your CMS has three main parts:

**Note**: Each component in the library also has an associated **screenshot** of the design, which will be used for visual matching.

### 1. **MiBlockComponentConfig.json**
- **`component`**: Component hierarchy with ParentId relationships
  - Level 0: Main component (e.g., "Navbar-with-center-logo")
  - Level 1+: Child components with ParentId pointing to parent
- **`componentDefinition`**: Properties/fields for each component
  - PropertyName, PropertyAliasName (kebab-case)
  - ControlId: Field type (1=Text, 7=Image/Resource, 8=Yes/No, etc.)
  - IsMandatory, PropertyMaxLength, DisplayOrder
- **`componentSiteLevelSetting`**: Links component to FormatId

### 2. **MiBlockComponentFormat.json**
- **`FormatContent`**: Handlebars HTML template
  - Uses `{{data.property-alias-name}}` for simple fields
  - Uses `{{data.image-field.0.OriginalImagePath}}` for images
  - Uses `{{#each Child.child-component-alias}}` for nested components
  - Uses conditional helpers like `{{IfCond}}`, `{{IfCondObj}}`

### 3. **MiBlockComponentRecords.json**
- Actual record data with values
- RecordJsonString contains the property values in JSON format
- Shows parent-child relationships via ParentId and level
- **Note**: For output/training, include only **ONE ACTIVE SET** of records:
  - 1 parent record (level 0)
  - Its direct children (level 1+)
  - Do NOT include all 500+ historical/inactive records
  - Purpose: Demonstrate structure, not provide full dataset

### 4. **Component Screenshots**
- Each component has a screenshot showing the design
- Used for visual matching against Figma inputs
- Will be downloaded from CMS API during library ingestion
- Stored locally with paths in database
- Visual embeddings stored in PostgreSQL using pgvector extension

---

## Library Component Data Structure

For each component in the library, stored in **PostgreSQL with pgvector**:

```sql
-- Database Schema
CREATE TABLE components (
    component_id INTEGER PRIMARY KEY,
    component_name VARCHAR(255),
    component_alias VARCHAR(255),
    screenshot_url VARCHAR(500),
    screenshot_path VARCHAR(500),
    embedding vector(512),  -- pgvector: CLIP embedding (512 dimensions)
    config_json JSONB,      -- ComponentConfig data
    format_json JSONB,      -- ComponentFormat data
    records_json JSONB,     -- ComponentRecords data
    definitions JSONB,      -- componentDefinition array
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- Create index for fast similarity search
CREATE INDEX components_embedding_idx 
ON components 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
```

**Example Record:**
```json
{
  "component_id": 560183,
  "component_name": "Navbar-with-center-logo",
  "component_alias": "navbar-with-center-logo",
  "screenshot_url": "https://cms.api/screenshots/560183.png",
  "screenshot_path": "./data/screenshots/560183.png",
  "embedding": "[0.123, 0.456, ...]",  // 512-dimensional CLIP vector
  "config_json": { /* ComponentConfig data */ },
  "format_json": { /* ComponentFormat data */ },
  "records_json": [ /* ComponentRecords data */ ],
  "definitions": [ /* componentDefinition array */ ]
}
```

**Similarity Search Query:**
```sql
-- Find top 5 similar components to input embedding
SELECT 
    component_id,
    component_name,
    component_alias,
    screenshot_path,
    1 - (embedding <=> $1::vector) AS similarity_score
FROM components
ORDER BY embedding <=> $1::vector
LIMIT 5;
```

---

## Why pgvector?

**Benefits of using pgvector instead of separate vector databases:**

1. **Simplified Architecture**
   - Single database (PostgreSQL) for all data
   - No need to sync between relational DB and vector DB
   - Easier deployment and maintenance

2. **ACID Transactions**
   - Atomic updates: component data + embedding together
   - No consistency issues between metadata and vectors
   - Reliable rollback if ingestion fails

3. **Unified Queries**
   - Join vector search with metadata filters in single SQL query
   - Example: "Find similar navbars created in last 30 days"
   ```sql
   SELECT * FROM components 
   WHERE created_at > NOW() - INTERVAL '30 days'
   ORDER BY embedding <=> $1::vector 
   LIMIT 5;
   ```

4. **Built-in PostgreSQL Features**
   - Backup/restore (pg_dump includes vectors)
   - Replication and high availability
   - Connection pooling
   - Existing monitoring tools

5. **Performance**
   - IVFFlat index: Fast approximate nearest neighbor search
   - Competitive with dedicated vector DBs for datasets < 1M vectors
   - Our use case: ~150-500 components (perfect for pgvector)

6. **Cost-Effective**
   - No additional vector DB service costs
   - Use existing PostgreSQL infrastructure
   - No data transfer between services

**pgvector Index Configuration:**
- **IVFFlat**: Approximate nearest neighbor search
- **lists = 100**: Number of clusters (good for 150-10,000 vectors)
- **probes**: Query-time parameter (default: 1, increase for better accuracy)
- **Distance operator**: `<=>` (cosine distance)

---

## System Goal

### 📥 INPUT
```
1. Figma Screenshot
   - Image file (PNG/JPG)
   - Shows the design section to convert
   
2. Metadata
   - Section name (e.g., "Hero Section", "Navigation Bar")
   - Purpose/description
   - Page context (e.g., "Homepage", "About Page")
   - Design tokens (colors, fonts) - optional
```

### 📤 OUTPUT
```
Complete MiBlock component structure in 3 JSON files:

1. ComponentConfig.json
   ├─ component[] - Component hierarchy with ParentId relationships
   └─ componentDefinition[] - Properties with ControlIds, names, validation

2. ComponentFormat.json
   └─ FormatContent - Handlebars HTML template with {{data.xxx}} variables

3. ComponentRecords.json (Sample)
   └─ componentRecords[] - Sample data demonstrating the structure
```

### 🎯 Process Summary

**Two possible flows:**

**Flow A: Match Found (Fast - 3 seconds)**
```
Figma Screenshot → Library Matcher → MATCH FOUND (>85%) 
→ Load existing component data from database 
→ Return ComponentConfig + ComponentFormat + ComponentRecords 
→ DONE ✅ (No AI generation needed)
```

**Flow B: No Match Found (Full Generation - 35 seconds)**
```
Figma Screenshot → Library Matcher → NO MATCH (<85%) 
→ HTML Generation (Claude AI) → Visual Validation 
→ Structure Detection → Definition Extraction → Template Generation 
→ MiBlock JSON Output
```

---

## Revised AI Agent Architecture

### 🔧 PREREQUISITE: Library Ingestion & Training (One-time Setup)

```
┌────────────────────────────────────────────────────────────────┐
│           LIBRARY INGESTION & TRAINING AGENT                   │
│                  (Runs once or periodically)                   │
├────────────────────────────────────────────────────────────────┤
│ INPUT:                                                         │
│ • CMS API endpoint                                             │
│ • API credentials                                              │
│                                                                │
│ PROCESS:                                                       │
│ 1. Call CMS API to get all components list                    │
│ 2. For each component:                                         │
│    ├─ Download ComponentConfig.json                           │
│    ├─ Download ComponentFormat.json                           │
│    ├─ Download ComponentRecords.json                          │
│    └─ Download component screenshot (PNG/JPG)                 │
│ 3. Generate CLIP visual embeddings from screenshots           │
│ 4. Store all data in PostgreSQL database:                     │
│    ├─ Component metadata (regular tables)                     │
│    ├─ Visual embeddings (pgvector extension)                  │
│    └─ Screenshots (Local storage + paths in DB)               │
│ 5. Create pgvector index for fast similarity search           │
│                                                                │
│ OUTPUT:                                                        │
│ • Library database ready for matching                         │
│ • Total components: 150 (example)                             │
│ • Embeddings indexed: 150                                     │
│ • Ready for production use                                    │
└────────────────────────────────────────────────────────────────┘
                              │
                              │ Library ready ✓
                              ▼
```

---

### 🚀 MAIN WORKFLOW: Component Generation

```
┌────────────────────── INPUT ──────────────────────┐
│  • Figma Screenshot (PNG/JPG)                     │
│  • Metadata (section name, purpose, design info)  │
└────────────────────┬──────────────────────────────┘
                     │
     ┌───────────────▼────────────────────────────────────────────┐
     │              ORCHESTRATOR AGENT                            │
     │  Input: Figma screenshot + metadata                        │
     │  Decides: Match existing OR Create new component           │
     │  Note: Requires library to be ingested first               │
     └───────┬────────────────────────────────────┬───────────────┘
             │                                    │
             │ Decision: Try matching first       │ No match found
             │ (Search trained library)           │ OR confidence < 85%
   ┌─────────▼─────────┐               ┌─────────▼──────────────┐
   │ LIBRARY MATCHER   │               │ COMPONENT CREATOR      │
   │     AGENT         │               │    PIPELINE            │
   │                   │               │                        │
   │ Uses: Pre-trained │               │                        │
   │ library embeddings│               │                        │
   ├───────────────────┤               └────────────────────────┘
   │ INPUT:            │                          │
   │ • Figma screenshot│                          │
   │ • Metadata        │               ┌──────────▼─────────────┐
   │                   │               │ 1. HTML GENERATOR      │
   │ PROCESS:          │               │    AGENT (Claude AI)   │
   │ • Load library    │               ├────────────────────────┤
   │   component       │               │ INPUT:                 │
   │   screenshots     │               │ • Figma screenshot     │
   │ • Compare visually│               │ • Metadata             │
   │ • Calculate       │               │ • Library examples     │
   │   confidence      │               │                        │
   │                   │               │ OUTPUT:                │
   │ OUTPUT:           │               │ • Clean HTML           │
   │ • Match found?    │               │ • Element list         │
   │ • Confidence: 92% │               └──────────┬─────────────┘
   │ • Component data  │                          │
   └───────┬───────────┘                          │
           │                           ┌──────────▼─────────────┐
           │ Match found               │ 2. VISUAL VALIDATOR    │
           │ Confidence > 85%          │    AGENT               │
           │                           ├────────────────────────┤
           │                           │ INPUT:                 │
           │                           │ • Original Figma       │
           │                           │   screenshot           │
           │                           │ • Generated HTML       │
           │                           │                        │
           │                           │ PROCESS:               │
           │                           │ • Render HTML to image │
           │                           │ • Compare images       │
           │                           │ • Calculate similarity │
           │                           │                        │
           │                           │ OUTPUT:                │
           │                           │ • Valid? (Yes/No)      │
           │                           │ • Similarity: 93%      │
           │                           │ • Feedback (if needed) │
           │                           └──────────┬─────────────┘
           │                                      │
           │                                      │ Valid HTML
           │                                      │
           │                           ┌──────────▼─────────────┐
           │                           │ 3. COMPONENT           │
           │                           │    STRUCTURE AGENT     │
           │                           ├────────────────────────┤
           │                           │ INPUT:                 │
           │                           │ • Validated HTML       │
           │                           │ • Component name       │
           │                           │                        │
           │                           │ PROCESS:               │
           │                           │ • Parse HTML structure │
           │                           │ • Identify repeating   │
           │                           │   sections (children)  │
           │                           │ • Build hierarchy      │
           │                           │                        │
           │                           │ OUTPUT:                │
           │                           │ • Parent component     │
           │                           │ • Child components     │
           │                           │ • Level assignments    │
           │                           └──────────┬─────────────┘
           │                                      │
           │                           ┌──────────▼─────────────┐
           │                           │ 4. DEFINITION          │
           │                           │    GENERATOR AGENT     │
           │                           ├────────────────────────┤
           │                           │ INPUT:                 │
           │                           │ • Component structure  │
           │                           │ • HTML for each part   │
           │                           │ • Library patterns     │
           │                           │                        │
           │                           │ PROCESS:               │
           │                           │ • Identify content     │
           │                           │   areas                │
           │                           │ • Assign ControlIds    │
           │                           │ • Generate property    │
           │                           │   names                │
           │                           │                        │
           │                           │ OUTPUT:                │
           │                           │ • componentDefinition  │
           │                           │   array for each       │
           │                           │   component            │
           │                           └──────────┬─────────────┘
           │                                      │
           │                           ┌──────────▼─────────────┐
           │                           │ 5. FORMAT TEMPLATE     │
           │                           │    GENERATOR AGENT     │
           │                           ├────────────────────────┤
           │                           │ INPUT:                 │
           │                           │ • Original HTML        │
           │                           │ • Component structure  │
           │                           │ • Definitions          │
           │                           │                        │
           │                           │ PROCESS:               │
           │                           │ • Replace content with │
           │                           │   Handlebars variables │
           │                           │ • Add child component  │
           │                           │   loops                │
           │                           │ • Add CMS attributes   │
           │                           │                        │
           │                           │ OUTPUT:                │
           │                           │ • FormatContent        │
           │                           │   (Handlebars HTML)    │
           │                           └──────────┬─────────────┘
           │                                      │
           └──────────────────┬───────────────────┘
                              │
                  ┌───────────▼────────────────────┐
                  │   OUTPUT FORMATTER AGENT       │
                  ├────────────────────────────────┤
                  │ INPUT:                         │
                  │ • Component structure          │
                  │ • Definitions                  │
                  │ • FormatContent                │
                  │                                │
                  │ OUTPUT:                        │
                  │ • ComponentConfig.json         │
                  │ • ComponentFormat.json         │
                  │ • ComponentRecords.json        │
                  └────────────────────────────────┘
                              │
              ┌───────────────▼────────────────┐
              │         FINAL OUTPUT           │
              ├────────────────────────────────┤
              │ 1. ComponentConfig.json        │
              │    - component[]               │
              │    - componentDefinition[]     │
              │    - componentSiteLevelSetting │
              │                                │
              │ 2. ComponentFormat.json        │
              │    - FormatContent (Handlebars)│
              │                                │
              │ 3. ComponentRecords.json       │
              │    - Sample records with data  │
              └────────────────────────────────┘
```

---

## 📌 Quick Reference: Your Questions Answered

### Q1: "If match found, then use the matched data and pass that info"

**Answer**: ✅ YES! When Library Matcher Agent finds a match with >85% confidence:

1. **Load existing data from database** (PostgreSQL):
   - ComponentConfig.json (component structure + definitions)
   - ComponentFormat.json (Handlebars template)
   - ComponentRecords.json (sample records)

2. **Skip all generation agents** (no need to generate anything):
   - ❌ Skip HTML Generator Agent
   - ❌ Skip Visual Validator Agent
   - ❌ Skip Component Structure Agent
   - ❌ Skip Definition Generator Agent
   - ❌ Skip Format Template Generator Agent

3. **Return matched component data** as final output
   - Processing time: ~3 seconds (vs ~35 seconds)
   - Cost: $0 (vs $0.10-0.30 for Claude AI)
   - Quality: Already proven and tested ✅

### Q2: "Which block does the download and training?"

**Answer**: 🔧 **Agent 0 - Library Ingestion & Training Agent**

**Location in Plan**: Lines ~370-510 (Agent 0 specification)

**What it does**:
1. **Downloads** all components from CMS API:
   - ComponentConfig.json
   - ComponentFormat.json
   - ComponentRecords.json (1 active set per component)
   - Component screenshots

2. **Generates** CLIP embeddings (512-dimensional vectors) from screenshots

3. **Stores** everything in PostgreSQL with pgvector:
   - Component metadata in regular tables
   - Visual embeddings in vector(512) columns
   - Creates IVFFlat index for fast similarity search

4. **When it runs**:
   - **Once**: Initial setup (takes ~15 minutes for 150 components)
   - **Weekly/Monthly**: Periodic refresh to get new components
   - **On-demand**: When components added/updated in CMS

**This is a PREREQUISITE** - must complete before any matching/generation can happen!

### Visual Summary: Complete System Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    PREREQUISITE STEP                            │
│         Agent 0: Library Ingestion & Training                   │
│                                                                 │
│  1. Download all components from CMS API                        │
│  2. Generate CLIP embeddings from screenshots                   │
│  3. Store in PostgreSQL with pgvector                           │
│  4. Create IVFFlat index                                        │
│                                                                 │
│  Result: Library ready for matching (150 components indexed)    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ Library ready ✓
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    MAIN WORKFLOW START                          │
│                                                                 │
│  Input: Figma Screenshot + Metadata                             │
└──────────────────────┬──────────────────────────────────────────┘
                       │
        ┌──────────────▼──────────────┐
        │  Library Matcher Agent       │
        │  (Search pgvector database) │
        └──────────────┬──────────────┘
                       │
         ┌─────────────┴─────────────┐
         │                           │
    Match Found                  No Match
    (>85%)                       (<85%)
         │                           │
         │                           │
┌────────▼─────────┐     ┌───────────▼────────────┐
│ FLOW A: USE      │     │ FLOW B: CREATE NEW     │
│ EXISTING         │     │ COMPONENT              │
├──────────────────┤     ├────────────────────────┤
│                  │     │                        │
│ 1. Load from DB: │     │ 1. HTML Generator      │
│    • Config      │     │    (Claude AI)         │
│    • Format      │     │                        │
│    • Records     │     │ 2. Visual Validator    │
│                  │     │    (Render & Compare)  │
│ 2. Return data   │     │                        │
│                  │     │ 3. Structure Agent     │
│ Time: 3 sec      │     │    (Find hierarchy)    │
│ Cost: $0         │     │                        │
│ API calls: 0     │     │ 4. Definition Agent    │
│                  │     │    (Extract properties)│
│                  │     │                        │
│                  │     │ 5. Template Agent      │
│                  │     │    (Generate Handlebars│
│                  │     │                        │
│                  │     │ Time: 35 sec           │
│                  │     │ Cost: $0.10-0.30       │
│                  │     │ API calls: 3-5         │
└────────┬─────────┘     └───────────┬────────────┘
         │                           │
         └───────────┬───────────────┘
                     │
        ┌────────────▼──────────────┐
        │  Output Formatter Agent   │
        │  (Assemble final JSON)    │
        └────────────┬──────────────┘
                     │
┌────────────────────▼───────────────────────────┐
│              FINAL OUTPUT                      │
│                                                │
│  • ComponentConfig.json                        │
│  • ComponentFormat.json                        │
│  • ComponentRecords.json (1 parent + children) │
│                                                │
│  Ready for CMS import ✅                       │
└────────────────────────────────────────────────┘
```

---

## Detailed Agent Specifications

### Agent 0: **Library Ingestion & Training Agent** ⚙️ (PREREQUISITE - Runs First)

**Purpose**: Download all components from CMS API, generate embeddings, and build searchable library database

**⚠️ IMPORTANT**: This agent must run BEFORE any component generation can happen. It's a one-time setup (or periodic refresh) that creates the library database that the Library Matcher Agent searches.

**When it runs:**
- **Initial Setup**: Run once when deploying the system
- **Periodic Refresh**: Weekly/monthly to sync new components from CMS
- **On-Demand**: When new components are added to CMS

**This is the "Download and Training" block you asked about!**

**Input**:
```json
{
  "cms_api_config": {
    "base_url": "https://cms-api.example.com",
    "api_key": "xxxxx",
    "endpoints": {
      "list_components": "/api/components/list",
      "get_component": "/api/components/{id}",
      "get_screenshot": "/api/components/{id}/screenshot"
    }
  },
  "storage_config": {
    "database_url": "postgresql://...",
    "pgvector_enabled": true,
    "screenshots_path": "./data/screenshots"
  }
}
```

**Process**:

**Step 1: Fetch Component List**
```python
# Call CMS API
response = cms_api.get("/api/components/list")
component_ids = [comp['ComponentId'] for comp in response]
# Returns: [560183, 560184, 523456, 534789, ...]
```

**Step 2: Download Each Component Data**
```python
for component_id in component_ids:
    # Download JSON files
    config = cms_api.get(f"/api/components/{component_id}/config")
    format = cms_api.get(f"/api/components/{component_id}/format")
    
    # Download ONLY ONE ACTIVE SET of records (not all 500+)
    # Get 1 parent record + its children only
    records = cms_api.get(
        f"/api/components/{component_id}/records",
        params={"active_only": True, "limit_per_parent": 1}
    )
    
    # Download screenshot
    screenshot = cms_api.get(f"/api/components/{component_id}/screenshot")
    save_screenshot(screenshot, f"./data/screenshots/{component_id}.png")
```

**Important**: For ComponentRecords:
- Download **only 1 parent record** (level 0) per component
- Include **all child records** of that parent
- Exclude inactive/historical records
- This provides structure example without overwhelming data

**Step 3: Generate Visual Embeddings**
```python
import clip
model = clip.load("ViT-B/32")

for component_id, screenshot_path in screenshots:
    # Load image
    image = load_image(screenshot_path)
    
    # Generate CLIP embedding (512-dimensional vector)
    embedding = model.encode_image(image)
    
    # Store in vector database
    vector_db.add(
        id=component_id,
        embedding=embedding,
        metadata={
            "component_name": component_name,
            "component_alias": component_alias
        }
    )
```

**Step 4: Store in Database**
```python
# PostgreSQL with pgvector - Store everything in one database
db.execute("""
    INSERT INTO components (
        component_id,
        component_name,
        component_alias,
        screenshot_path,
        config_json,
        format_json,
        records_json,
        definitions,
        embedding,
        created_at
    ) VALUES (
        560183,
        'Navbar-with-center-logo',
        'navbar-with-center-logo',
        './data/screenshots/560183.png',
        %s::jsonb,
        %s::jsonb,
        %s::jsonb,
        %s::jsonb,
        %s::vector(512),  -- pgvector column for CLIP embedding
        NOW()
    )
""", (config_json, format_json, records_json, definitions, embedding_vector))

# Create pgvector index for fast similarity search
db.execute("""
    CREATE INDEX IF NOT EXISTS components_embedding_idx 
    ON components 
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
""")
```

**Output**:
```json
{
  "ingestion_complete": true,
  "stats": {
    "total_components": 150,
    "successful_downloads": 150,
    "failed_downloads": 0,
    "embeddings_generated": 150,
    "screenshots_saved": 150,
    "database_entries": 150,
    "pgvector_index_created": true,
    "database_size": "85MB"
  },
  "library_ready": true,
  "indexed_at": "2025-12-29T10:30:00Z",
  "sample_components": [
    {
      "id": 560183,
      "name": "Navbar-with-center-logo",
      "has_screenshot": true,
      "has_embedding": true,
      "definitions_count": 12
    }
  ]
}
```

**Execution Frequency**:
- **Initial Setup**: Run once when deploying system
- **Periodic Refresh**: Run weekly/monthly to sync new components
- **On-Demand**: Run when new components added to CMS
- **Incremental**: Only download new/updated components

**Performance**:
- Download rate: ~10 components/minute
- 150 components: ~15 minutes total
- Embedding generation: ~1 second per screenshot
- Database insertion: ~100ms per component

**Error Handling**:
```python
def ingest_component(component_id):
    try:
        # Download and process
        ...
    except APIError as e:
        log_error(f"Failed to download {component_id}: {e}")
        retry_queue.add(component_id)
    except EmbeddingError as e:
        log_error(f"Failed to generate embedding for {component_id}: {e}")
        # Use placeholder embedding or mark for manual review
```

**PostgreSQL + pgvector Setup**:
```sql
-- Install pgvector extension (run once)
CREATE EXTENSION IF NOT EXISTS vector;

-- Create components table with vector column
CREATE TABLE components (
    component_id INTEGER PRIMARY KEY,
    component_name VARCHAR(255) NOT NULL,
    component_alias VARCHAR(255) NOT NULL UNIQUE,
    screenshot_url VARCHAR(500),
    screenshot_path VARCHAR(500) NOT NULL,
    embedding vector(512),  -- CLIP embedding
    config_json JSONB NOT NULL,
    format_json JSONB NOT NULL,
    records_json JSONB,
    definitions JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create IVFFlat index for fast similarity search
-- Lists parameter: sqrt(rows), e.g., sqrt(150) ≈ 12, round up to 100 for growth
CREATE INDEX components_embedding_idx 
ON components 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Create indexes for metadata search
CREATE INDEX idx_component_alias ON components(component_alias);
CREATE INDEX idx_component_name ON components USING gin(to_tsvector('english', component_name));
```

**CLI Command**:
```bash
# Full ingestion
python scripts/ingest_library.py --full

# Incremental (only new components)
python scripts/ingest_library.py --incremental

# Specific components
python scripts/ingest_library.py --ids 560183,560184

# Verify library
python scripts/ingest_library.py --verify

# Rebuild pgvector index
python scripts/ingest_library.py --rebuild-index
```

---

### Agent 1: **Library Matcher Agent**

**Purpose**: Find matching component from existing MiBlock library

**Input**:
- Figma screenshot
- Metadata (section name, purpose)

**Process**:

**Step 1: Generate Embedding from Input**
```python
import clip
model = clip.load("ViT-B/32")

# Load Figma screenshot
figma_image = load_image("figma_screenshot.png")

# Generate 512-dimensional embedding
input_embedding = model.encode_image(figma_image)  # Returns np.array of shape (512,)
```

**Step 2: Search Using pgvector**
```python
# Query PostgreSQL with pgvector for top 5 similar components
query = """
    SELECT 
        component_id,
        component_name,
        component_alias,
        screenshot_path,
        config_json,
        format_json,
        1 - (embedding <=> %s::vector) AS similarity_score
    FROM components
    WHERE embedding IS NOT NULL
    ORDER BY embedding <=> %s::vector
    LIMIT 5;
"""

# Execute with input embedding
candidates = db.execute(query, (input_embedding.tolist(), input_embedding.tolist()))

# Returns top 5 candidates based on cosine similarity
# <=> operator in pgvector = cosine distance
# 1 - distance = similarity score (0-1)
```

**Step 3: Detailed Visual Comparison**
```python
for candidate in candidates:
    # Load library component screenshot
    library_screenshot = load_image(candidate['screenshot_path'])
    
    # Calculate multiple similarity metrics
    ssim_score = calculate_ssim(figma_image, library_screenshot)
    perceptual_hash_score = calculate_phash_similarity(figma_image, library_screenshot)
    
    # Semantic similarity (component name vs metadata)
    semantic_score = semantic_similarity(
        candidate['component_name'],
        figma_metadata['section_name']
    )
    
    # Combined confidence score
    confidence = (
        0.5 * candidate['similarity_score'] +  # CLIP from pgvector
        0.2 * ssim_score +
        0.2 * perceptual_hash_score +
        0.1 * semantic_score
    )
```

**Step 4: Return Best Matches**
- Sort by confidence score
- Return top matches with threshold check (85%)

**Output**:
```json
{
  "matches": [
    {
      "component_id": 560183,
      "component_name": "Navbar-with-center-logo",
      "confidence_score": 0.92,
      "visual_similarity": 0.89,
      "semantic_similarity": 0.95,
      "screenshot_url": "https://cms-api.com/screenshots/560183.png",
      "component_config": {...},
      "format_content": "..."
    }
  ],
  "best_match_found": true,
  "use_existing": true  // If confidence > 85%
}
```

**Decision**: 
- **If best match confidence > 85%** → Use existing component data directly
  - Use matched ComponentConfig.json (component hierarchy + definitions)
  - Use matched ComponentFormat.json (Handlebars template)
  - Use matched ComponentRecords.json (1 sample parent + children)
  - **Skip HTML generation, validation, and all other agents**
  - Return matched data as final output
  
- **If no good match (confidence < 85%)** → Go to Component Creator Pipeline
  - Generate new HTML
  - Create new component structure
  - Extract new definitions
  - Generate new Handlebars template

---

### Agent 2: **HTML Generator Agent** (Claude AI)

**Purpose**: Generate clean, semantic HTML from Figma screenshot

**Input**:
- Figma screenshot
- Metadata
- Context: Similar library component examples (for learning patterns)

**Process**:
1. Prepare Claude prompt with:
   - Screenshot
   - Instructions for semantic HTML
   - 2-3 similar component examples from library
   - Guidelines: accessibility, structure, no CSS
2. Call Claude API (vision-to-code)
3. Parse and clean generated HTML
4. Validate HTML structure

**Output**:
```json
{
  "html": "<header>...</header>",
  "identified_elements": {
    "images": ["logo", "icon"],
    "text_fields": ["title", "description"],
    "links": ["button-link", "nav-links"],
    "repeating_sections": ["navigation-items", "dropdown-items"]
  }
}
```

**Key Requirement**: HTML should be clean, without inline styles, and well-structured for easy parsing

---

### Agent 3: **Visual Validator Agent**

**Purpose**: Ensure generated HTML visually matches Figma screenshot

**Input**:
- Original Figma screenshot
- Generated HTML

**Process**:
1. Render HTML to screenshot using Playwright
2. Resize both images to same dimensions
3. Calculate similarity metrics:
   - SSIM (Structural Similarity)
   - MSE (Mean Squared Error)
   - CLIP-based perceptual similarity
4. Overall score = weighted combination
5. If score < 90% → Generate feedback

**Output**:
```json
{
  "is_valid": true,
  "similarity_score": 0.93,
  "metrics": {
    "ssim": 0.91,
    "perceptual": 0.95
  },
  "feedback": null,  // Only if needs refinement
  "iteration": 2,
  "should_refine": false
}
```

**Iterations**: Max 3 attempts, use feedback to improve HTML

---

### Agent 4: **Component Structure Agent**

**Purpose**: Analyze HTML and identify component hierarchy for MiBlock structure

**Input**:
- Validated HTML
- Component name

**Process**:
1. Parse HTML structure
2. Identify main component container
3. Detect repeating sections (child components):
   - Navigation lists
   - Dropdown menus
   - Card grids
   - Any repeated patterns
4. Determine parent-child relationships
5. Assign levels (0 = parent, 1+ = children)
6. Generate component names and aliases

**Output**:
```json
{
  "components": [
    {
      "component_name": "Hero Section",
      "component_alias": "hero-section",
      "parent_id": null,
      "level": 0,
      "html_section": "<section>...</section>"
    },
    {
      "component_name": "Hero Section CTA Button",
      "component_alias": "hero-section-cta-button",
      "parent_id": "hero-section",
      "level": 1,
      "html_section": "<button>...</button>",
      "max_records": 3,
      "min_records": 1
    }
  ],
  "hierarchy_map": {
    "hero-section": ["hero-section-cta-button", "hero-section-features"]
  }
}
```

**Learning**: Train on library patterns to understand how to split components appropriately

---

### Agent 5: **Definition Generator Agent**

**Purpose**: Extract component definitions (properties) from HTML elements

**Input**:
- Component structure
- HTML for each component
- Library examples (to learn naming conventions and ControlId patterns)

**Process**:
1. For each component, analyze HTML elements
2. Identify dynamic content areas:
   - Text content → ControlId 1 (Text)
   - Images/logos → ControlId 7 (Resource)
   - Yes/No options → ControlId 8 (Checkbox)
   - Links/URLs → ControlId 1 (Text)
   - Rich text → ControlId 2 (Rich Text Editor)
3. Generate PropertyName (human-readable)
4. Generate PropertyAliasName (kebab-case)
5. Determine IsMandatory based on semantic importance
6. Set PropertyMaxLength
7. Assign DisplayOrder
8. Use Claude AI to understand context and suggest appropriate names

**Output** (for each component):
```json
{
  "component_id": "hero-section",
  "definitions": [
    {
      "PropertyName": "Hero Title",
      "PropertyAliasName": "hero-title",
      "ControlId": 1,
      "IsMandatory": true,
      "PropertyMaxLength": 200,
      "DisplayOrder": 1,
      "Tooltip": "Main heading for hero section",
      "html_selector": "h1.hero-title",
      "current_value": "Welcome to Our Site"
    },
    {
      "PropertyName": "Background Image",
      "PropertyAliasName": "background-image",
      "ControlId": 7,
      "IsMandatory": true,
      "PropertyMaxLength": 1,
      "ResourceTypeId": 313562,
      "DisplayOrder": 2,
      "html_selector": "img.hero-bg",
      "current_value": "hero-bg.jpg"
    }
  ]
}
```

**Key Learning**: Study library components to understand:
- Naming conventions (e.g., "Main Logo" not "Logo1")
- When to use ControlId 7 vs 1 for images
- Common patterns (e.g., "Enable X" for toggles)

---

### Agent 6: **Format Template Generator Agent**

**Purpose**: Convert HTML to Handlebars FormatContent template

**Input**:
- Original HTML
- Component structure
- Component definitions

**Process**:
1. Start with original HTML
2. For each definition, replace content with Handlebars variable:
   - Text: `{{data.property-alias}}`
   - Image: `{{data.property-alias.0.OriginalImagePath}}`
   - Yes/No: `{{IfCond data.property-alias[].0 '=' 'Yes'}}...{{/IfCond}}`
3. For child components, wrap in loop:
   ```handlebars
   {{#each Child.child-component-alias}}
   {{IfCond this.ParentId '=' ../this.Id}}
     <!-- child component HTML with {{data.xxx}} variables -->
   {{/IfCond}}
   {{/each}}
   ```
4. Add CMS-specific attributes:
   - `%%componentRecordEditable%%`
   - `dynamiccomponenteditenable` class
5. Preserve conditional logic
6. Use Claude AI to ensure proper Handlebars syntax

**Output**:
```json
{
  "FormatContent": "{{#each ComponentRecordJson.hero-section}}\n<section class=\"hero dynamiccomponenteditenable\" %%componentRecordEditable%%>\n  <h1>{{data.hero-title}}</h1>\n  <img src=\"{{data.background-image.0.OriginalImagePath}}\" alt=\"{{data.image-alt-text}}\">\n  {{#each Child.hero-section-cta-button}}\n  {{IfCond this.ParentId '=' ../this.Id}}\n  <button class=\"dynamiccomponenteditenable\" %%componentRecordEditable%%>{{data.button-text}}</button>\n  {{/IfCond}}\n  {{/each}}\n</section>\n{{/each}}",
  "handlebars_variables_used": [
    "data.hero-title",
    "data.background-image.0.OriginalImagePath",
    "data.button-text"
  ]
}
```

**Critical**: Must follow exact Handlebars syntax patterns from library examples

---

### Agent 7: **Output Formatter Agent**

**Purpose**: Assemble all outputs into MiBlock JSON format

**Input**:
- Component structure
- Component definitions
- Format template

**Output**: Three JSON files matching your format:

**1. ComponentConfig.json**
```json
{
  "component": [
    {
      "ComponentId": 0,  // To be assigned
      "ComponentName": "Hero Section",
      "ComponentAliasName": "hero-section",
      "ParentId": null,
      "FormatId": 0,
      "MaxRecord": 5,
      "MinRecord": 1,
      "Status": true,
      // ... other fields with defaults
    }
  ],
  "componentDefinition": [
    {
      "DefinitionId": 0,
      "ComponentId": 0,
      "PropertyName": "Hero Title",
      "PropertyAliasName": "hero-title",
      "ControlId": 1,
      "IsMandatory": true,
      "PropertyMaxLength": 200,
      "DisplayOrder": 1,
      // ... other fields
    }
  ],
  "componentSiteLevelSetting": [...]
}
```

**2. ComponentFormat.json**
```json
{
  "ComponentFormat": [
    {
      "FormatId": 0,
      "FormatName": "Hero Section",
      "FormatKey": "hero-section",
      "FormatContent": "{{#each ComponentRecordJson.hero-section}}...",
      "Status": 1
    }
  ]
}
```

**3. ComponentRecords.json** (Sample - ONE ACTIVE SET)
```json
{
  "componentRecords": [
    {
      "Id": 1,
      "RecordJsonString": "{\"Id\":\"##Id##\",\"ParentId\":\"##ParentId##\",\"hero-title\":\"Welcome\",\"background-image\":[{...}]}",
      "ComponentId": 0,
      "ParentComponentId": null,
      "ParentId": 0,
      "MainParentComponentId": 0,
      "level": 0,
      "Status": true
    }
    // Include child records if component has children
  ]
}
```

**Important**: Generate ONLY 1 parent record + its children (not all 500+ records)

**Sample Record Generation Logic**:
```python
def generate_sample_records(component_structure, definitions):
    """
    Generate ONE set of sample records (parent + children)
    """
    records = []
    record_id = 1
    
    # 1. Generate parent record (level 0)
    parent_record = {
        "Id": record_id,
        "ComponentId": component_structure['parent']['id'],
        "ParentComponentId": None,
        "RecordJsonString": generate_json_string(
            definitions['parent'],
            include_sample_values=True
        ),
        "ParentId": 0,
        "MainParentComponentId": component_structure['parent']['id'],
        "level": 0,
        "Status": True
    }
    records.append(parent_record)
    record_id += 1
    
    # 2. Generate child records (if any)
    for child_component in component_structure.get('children', []):
        # Generate 2-3 sample child records per child component type
        for i in range(min(3, child_component.get('max_records', 3))):
            child_record = {
                "Id": record_id,
                "ComponentId": child_component['id'],
                "ParentComponentId": component_structure['parent']['id'],
                "RecordJsonString": generate_json_string(
                    definitions['children'][child_component['id']],
                    include_sample_values=True
                ),
                "ParentId": parent_record['Id'],
                "MainParentComponentId": component_structure['parent']['id'],
                "level": child_component['level'],
                "Status": True
            }
            records.append(child_record)
            record_id += 1
    
    return {"componentRecords": records}
```

---

## Key Technical Challenges & Solutions

### Challenge 1: Understanding ControlId Types
**Solution**: 
- Train on library examples
- Create mapping of HTML elements → ControlId:
  - `<img>` → ControlId 7 (Resource)
  - Text content → ControlId 1 (Text)
  - Checkboxes/toggles → ControlId 8 (Yes/No)
  - Rich text areas → ControlId 2
- Use Claude AI to suggest appropriate types

### Challenge 2: Generating Correct Handlebars Syntax
**Solution**:
- Provide 5-10 FormatContent examples to Claude as context
- Create template rules:
  - Always start with `{{#each ComponentRecordJson.component-alias}}`
  - Child components use `{{#each Child.child-alias}}`
  - Always include `{{IfCond this.ParentId '=' ../this.Id}}`
  - Images use `.0.OriginalImagePath` pattern
- Validate generated Handlebars syntax

### Challenge 3: Identifying Component Hierarchy
**Solution**:
- Use Claude AI to analyze HTML structure
- Look for repeated patterns (lists, cards, items)
- Max 3 levels deep (level 0, 1, 2) in most cases
- Each child component should have clear boundary
- Learn from library: navigation → navigation-item → dropdown-item

### Challenge 4: Matching Against Library
**Solution**:
- Visual similarity (CLIP embeddings + SSIM)
- Semantic similarity (component names, purpose)
- Structural similarity (compare HTML structure)
- Combined confidence score
- Threshold: 85% for using existing component

### Challenge 5: Property Naming Conventions
**Solution**:
- Learn from library examples:
  - "Main Logo" not "Logo"
  - "Button Text" and "Button Link" (separate)
  - "Enable X to do Y" for toggles
  - "X Alt Text" for image alt tags
- Use Claude AI with library context to suggest names
- Consistent kebab-case for aliases

---

## 🔢 MASTER WORKFLOW - Numbered Implementation Steps

### 🎯 How to Use This Workflow

This section contains **122 numbered implementation steps** divided into 8 phases. Use these numbers to guide the development process step-by-step.

**Example Commands:**
- "Work on step 5" - I'll implement step 5 (Install PostgreSQL)
- "Start from step 16" - I'll begin Phase 2 (Library Ingestion)
- "Do steps 100-105" - I'll create Library Refresh UI
- "Show me step 50" - I'll explain what step 50 involves
- "Skip to Phase 7" - I'll jump to steps 78-105 (Orchestration + Figma + UI + Training UI)

**What You Get:**
- 🌐 **Browser-based web interface** (no CLI for users!)
- 🔗 **Figma URL input** (paste link, system extracts sections automatically)
- 📸 **Auto-screenshot** via Figma API (no manual screenshots!)
- 🎯 **Multi-section processing** (entire page or single section)
- ⚡ Real-time progress tracking per section
- 🔄 **On-demand library refresh** (button to retrain anytime, no CLI!)
- 📊 **Live training progress** (see downloading, embedding generation, storage)
- 📥 One-click download of generated JSON files
- 📱 Clean, modern UI

**Benefits:**
- ✅ Clear progression tracking
- ✅ Easy to pause and resume
- ✅ Flexible implementation order
- ✅ Granular control over development
- ✅ Everything accessible via browser

---

### 📖 Quick Step Reference

| Phase | Steps | Focus | Checkpoint |
|-------|-------|-------|-----------|
| **Phase 1** | 1-15 | Foundation & Setup | APIs + Database ready |
| **Phase 2** | 16-30 | Library Ingestion | Components downloaded + Embeddings indexed |
| **Phase 3** | 31-42 | HTML Generation | Claude AI generating valid HTML |
| **Phase 4** | 43-52 | Structure Analysis | Parent-child hierarchy working |
| **Phase 5** | 53-65 | Definition Extraction | ControlIds and properties correct |
| **Phase 6** | 66-77 | Template Generation | Handlebars templates valid |
| **Phase 7** | 78-105 | Orchestration + Figma + Web UI + Library Refresh UI | Backend + Figma + Frontend + Training UI |
| **Phase 8** | 106-122 | UI Polish & Testing | Production-ready web app |

**Total: 122 numbered steps spanning 8 weeks**

---

### 📦 PHASE 1: Foundation (Week 1) - Steps 1-15

**🔧 Implementation Choice**: 

**RECOMMENDED: Option A - Anthropic Direct API + LangGraph** ⭐

This approach works on **any platform** (Azure, AWS, GCP, on-prem):
- ✅ Platform-agnostic (no vendor lock-in)
- ✅ Works identically on Azure, AWS, GCP
- ✅ Lower cost (~$330/month)
- ✅ Maximum flexibility
- ✅ Easy to migrate between platforms

**The numbered steps below implement Option A (platform-agnostic approach).**

*Note: If you're certain you'll ONLY use AWS, see [AWS Bedrock Implementation Guide](#-aws-bedrock-implementation-guide) for Option B.*

---

**1.** Create project folder structure
**2.** Set up Python 3.11+ virtual environment
**3.** Install core dependencies (anthropic, pillow, playwright, sqlalchemy, psycopg2-binary, pgvector, redis)
**4.** Create .env configuration file with API keys placeholders
**5.** Install PostgreSQL 15+ database
**6.** Install pgvector extension
**7.** Create database `figma_cms_generator` and enable vector extension
**8.** Create database schema (components table with vector column)
**9.** Set up SQLAlchemy models for components
**10.** Create migration system with Alembic
**11.** Create Figma API client with:
    - URL parsing (extract file ID, node ID)
    - Detect if URL is page or specific node
    - Get file/page structure (list all sections/nodes)
    - Get screenshot for each section via Figma API
    - Extract metadata (name, dimensions, properties)
**12.** Create API client for CMS (with auth and error handling)
**13.** Create API client for Claude AI/Anthropic
**14.** Create base agent class structure
**15.** Set up structured logging and Redis caching

**✅ Checkpoint 1**: Project skeleton ready, all APIs connected (including Figma API), database configured

---

### 🗄️ PHASE 2: Library Ingestion & Training (Week 2) - Steps 16-30

**16.** Implement CMS API authentication
**17.** Create function to list all components from CMS API
**18.** Create function to download ComponentConfig.json for each component
**19.** Create function to download ComponentFormat.json for each component  
**20.** Create function to download ComponentRecords.json (ONE ACTIVE SET only)
**21.** Create function to download component screenshot
**22.** Create library ingestion script (orchestrates 17-21)
**23.** Create database tables for storing component data
**24.** Implement data storage logic (save JSON + screenshot to DB)
**25.** Set up CLIP model (ViT-B/32) for embeddings
**26.** Create embedding generation function (screenshot → 512-dim vector)
**27.** Batch process all screenshots to generate embeddings
**28.** Store embeddings in PostgreSQL vector(512) column
**29.** Create IVFFlat index on embeddings column
**30.** Implement Library Matcher Agent with pgvector similarity search

**✅ Checkpoint 2**: Complete library downloaded, embeddings generated, search working

---

### 🎨 PHASE 3: HTML Generation & Validation (Week 3) - Steps 31-42

**31.** Design Claude AI prompt template for HTML generation
**32.** Add library component examples to prompt context
**33.** Implement HTML Generator Agent class
**34.** Create function to call Claude API with screenshot
**35.** Implement HTML response parsing and cleaning
**36.** Set up Playwright for HTML rendering
**37.** Create function to render HTML to screenshot
**38.** Implement Visual Validator Agent class
**39.** Create SSIM similarity calculation function
**40.** Create CLIP-based perceptual similarity function
**41.** Implement iterative refinement loop (max 3 attempts)
**42.** Create feedback generation for failed validations

**✅ Checkpoint 3**: HTML generation working with 90%+ visual similarity

---

### 🏗️ PHASE 4: Component Structure Analysis (Week 4) - Steps 43-52

**43.** Analyze library components to understand parent-child patterns
**44.** Create Component Structure Agent class
**45.** Implement HTML parsing with BeautifulSoup
**46.** Create function to detect repeating sections (child components)
**47.** Implement parent-child relationship identification
**48.** Create component naming function (with Claude AI)
**49.** Implement level assignment (0 = parent, 1+ = children)
**50.** Create function to determine MaxRecord/MinRecord values
**51.** Handle nested components (multi-level)
**52.** Test hierarchy detection with various component types

**✅ Checkpoint 4**: Component structure extraction with correct parent-child relationships

---

### 📝 PHASE 5: Definition Generation (Week 5) - Steps 53-65

**53.** Study library ControlId patterns (1=Text, 7=Image, 8=Yes/No, etc.)
**54.** Create ControlId mapping rules (HTML element → ControlId)
**55.** Implement Definition Generator Agent class
**56.** Create function to identify content areas in HTML
**57.** Implement property name generation (PropertyName + PropertyAliasName)
**58.** Create ControlId assignment logic based on HTML element type
**59.** Implement mandatory field detection
**60.** Create DisplayOrder assignment logic
**61.** Handle special cases (image resources, Yes/No toggles, URLs)
**62.** Generate alt text definitions for images
**63.** Create function to extract default values from HTML
**64.** Use Claude AI for semantic property name suggestions
**65.** Test definition generation against library standards

**✅ Checkpoint 5**: Definitions generated with correct ControlIds and naming

---

### 🔧 PHASE 6: Format Template Generation (Week 6) - Steps 66-77

**66.** Study Handlebars syntax in library ComponentFormat examples
**67.** Document all Handlebars patterns ({{data.xxx}}, {{#each}}, {{IfCond}})
**68.** Implement Format Template Generator Agent class
**69.** Create function to replace text content with {{data.property-alias}}
**70.** Create function to replace images with {{data.property.0.OriginalImagePath}}
**71.** Implement child component loop wrapping ({{#each Child.xxx}})
**72.** Add {{IfCond this.ParentId '=' ../this.Id}} conditionals
**73.** Add CMS-specific attributes (%%componentRecordEditable%%, dynamiccomponenteditenable)
**74.** Handle Yes/No fields with {{IfCond data.field[].0 '=' 'Yes'}}
**75.** Use Claude AI for complex Handlebars logic generation
**76.** Validate generated Handlebars syntax
**77.** Test template rendering with sample data

**✅ Checkpoint 6**: Valid Handlebars templates generated

---

### 🔄 PHASE 7: Integration & Orchestration (Week 7) - Steps 78-95

**Backend Integration:**
**78.** Design LangGraph workflow for agent orchestration
**79.** Implement Orchestrator Agent class
**80.** Create workflow: Input → Library Matcher → Decision
**81.** Implement "Match Found" flow (load from DB, return data)
**82.** Implement "No Match" flow (route through all agents)
**83.** Create state management for workflow
**84.** Implement error handling and retry logic
**85.** Create Output Formatter Agent class
**86.** Generate ComponentConfig.json output format
**87.** Generate ComponentFormat.json output format
**88.** Generate ComponentRecords.json output (ONE ACTIVE SET)
**89.** Implement sample record generation with proper parent-child structure
**90.** Test complete backend pipeline

**Figma Integration & Batch Processing:**
**91.** Create Figma URL processor:
    - Parse Figma URL (file ID + node ID extraction)
    - Call Figma API to get file structure
    - Detect if single node or entire page
    - Get list of all sections/frames if page URL
**92.** Implement section iterator:
    - Loop through each section
    - Get screenshot for each via Figma API
    - Extract metadata per section
    - Queue sections for processing
**93.** Add batch processing logic:
    - Process sections one by one
    - Track progress per section
    - Aggregate results

**Web UI Development:**
**94.** Create frontend folder structure (HTML/CSS/JS or React)
**95.** Design web interface layout:
    - Figma URL input field
    - Section detection and preview
    - Section selection checkboxes
    - Progress indicator per section
    - Results display area
    - **Library status display (count, last refresh time)**
    - **"Refresh Library" button**
**96.** Implement Figma URL submission to backend
**97.** Display detected sections with thumbnails
**98.** Create WebSocket connection for real-time progress updates per section
**99.** Implement progress tracking UI (show which section + agent is running)

**Library Refresh UI:**
**100.** Create "Refresh Library" button and modal
**101.** Implement library refresh trigger (calls backend API)
**102.** Show real-time progress for library refresh:
    - Downloading components progress bar
    - Generating embeddings progress bar
    - Storing in database progress bar
    - Current component being processed
**103.** Display refresh statistics and summary on completion
**104.** Add options for refresh type:
    - Full refresh (re-download all)
    - Incremental (only new/updated components)
**105.** Show library status on main page (component count, last refresh time)

**✅ Checkpoint 7**: Complete workflow + Figma integration + Web UI + Library Refresh working end-to-end

---

### ✅ PHASE 8: UI Finishing & Testing (Week 8) - Steps 106-120

**Component Generation UI Completion:**
**106.** Implement results display (show generated JSON with syntax highlighting)
**107.** Add download buttons per section (Config, Format, Records)
**108.** Add "Download All Sections" (ZIP file)
**109.** Create component preview visualization per section
**110.** Add error handling and user-friendly error messages
**111.** Implement loading states and animations
**112.** Add success/failure notifications per section
**113.** Create history/recent conversions view
**114.** Show statistics (X sections processed, Y matched, Z generated)

**Testing & Polish:**
**115.** Create test dataset (50+ Figma URLs with various section counts)
**116.** Test library refresh functionality (full + incremental)
**117.** Run end-to-end tests through web UI (single section + multi-section)
**118.** Measure success metrics (match accuracy, HTML similarity, etc.)
**119.** Fix identified UI/UX issues
**120.** Optimize frontend performance (lazy loading, caching)
**121.** Browser compatibility testing (Chrome, Firefox, Safari, Edge)
**122.** Final deployment and user guide

**✅ Final Checkpoint**: Production-ready web application with Figma URL integration and on-demand library refresh deployed

---

## Implementation Phases (8 Weeks)

### **Phase 1: Foundation (Week 1)**
**Goal**: Setup project and basic infrastructure

**Day 1: Environment Setup**
- [ ] Create project structure
- [ ] Set up Python environment (3.11+)
- [ ] Install core dependencies:
  ```bash
  pip install anthropic pillow playwright sqlalchemy psycopg2-binary pgvector redis
  ```
- [ ] Create configuration management (.env file)

**Day 2-3: Database Setup**
- [ ] Install PostgreSQL 15+ (if not already installed)
- [ ] Install pgvector extension:
  ```bash
  # On Ubuntu/Debian
  sudo apt install postgresql-15-pgvector
  
  # On macOS (Homebrew)
  brew install pgvector
  
  # Or compile from source
  git clone https://github.com/pgvector/pgvector.git
  cd pgvector
  make
  make install
  ```
- [ ] Create database:
  ```sql
  CREATE DATABASE figma_cms_generator;
  \c figma_cms_generator
  CREATE EXTENSION vector;
  ```
- [ ] Set up SQLAlchemy models
- [ ] Create migration system (Alembic)

**Day 4-5: API Clients**
- [ ] Create API client for Figma
- [ ] Create API client for your CMS
- [ ] Create API client for Claude AI (Anthropic)
- [ ] Add error handling and retries
- [ ] Test all API connections

**Day 6-7: Base Infrastructure**
- [ ] Create base agent classes
- [ ] Set up structured logging
- [ ] Create Redis caching layer
- [ ] Set up configuration management
- [ ] Create utility functions

**Deliverable**: 
- ✅ Working project skeleton
- ✅ PostgreSQL + pgvector configured
- ✅ All API integrations tested
- ✅ Base classes ready

---

### **Phase 2: Library Ingestion & Training (Week 2)**
**Goal**: Build complete component library database with visual embeddings (PREREQUISITE for all matching)

**Day 1-2: CMS API Integration**
- [ ] Implement CMS API client
  - Authentication
  - List all components endpoint
  - Get component data endpoints
  - Get screenshot endpoint
  - Error handling and retries
- [ ] Test API connectivity
- [ ] Document all available endpoints

**Day 3-4: Library Download & Storage**
- [ ] Create library ingestion script
- [ ] Download all components from CMS API:
  - ComponentConfig.json for each component
  - ComponentFormat.json for each component
  - **ComponentRecords.json (ONE ACTIVE SET per component)**
    - 1 parent record + its children only
    - NOT all 500+ historical/inactive records
    - Filter by Status: true (active)
  - Component screenshot (PNG/JPG)
- [ ] Set up PostgreSQL database with pgvector:
  - Install pgvector extension: `CREATE EXTENSION vector;`
  - Components table with `embedding vector(512)` column
  - Definitions table
  - Formats table
  - Metadata table
- [ ] Store all downloaded data
- [ ] Implement incremental update logic

**Day 5: Visual Embedding Generation**
- [ ] Set up CLIP model (ViT-B/32)
- [ ] Generate embeddings for all screenshots:
  - Load each screenshot
  - Generate 512-dimensional vector
  - Batch processing (32 images at a time)
- [ ] Quality check embeddings
- [ ] Store embeddings with component IDs

**Day 6: pgvector Index Setup**
- [ ] Create pgvector index on embeddings column
  - IVFFlat index for fast approximate search
  - Configure index parameters (lists, probes)
- [ ] Test similarity search queries:
  ```sql
  SELECT * FROM components 
  ORDER BY embedding <=> query_vector 
  LIMIT 5;
  ```
- [ ] Benchmark search performance
- [ ] Tune index parameters for optimal speed/accuracy

**Day 7: Library Matcher Agent**
- [ ] Implement Library Matcher Agent
  - Visual similarity search
  - Semantic text similarity
  - Combined ranking algorithm
  - Confidence scoring
- [ ] Test with sample Figma screenshots
- [ ] Tune confidence thresholds (target: 85%)
- [ ] Create verification report

**Deliverable**: 
- ✅ Complete library database (all components)
- ✅ All screenshots downloaded and stored
- ✅ Visual embeddings generated and indexed
- ✅ Library Matcher Agent working
- ✅ Match accuracy >80%
- ✅ Search latency <2 seconds

---

### **Phase 3: HTML Generation & Validation (Week 3)**
**Goal**: Generate and validate HTML from screenshots

**Tasks**:
- [ ] Design Claude AI prompts for HTML generation
  - Include library examples in context
  - Specify semantic HTML requirements
  - Add accessibility guidelines
- [ ] Implement HTML Generator Agent
  - Claude API integration
  - Response parsing
  - HTML cleaning and validation
- [ ] Implement Visual Validator Agent
  - Playwright screenshot rendering
  - SSIM calculation
  - Perceptual similarity (CLIP)
  - Feedback generation
- [ ] Create iterative refinement loop (max 3 iterations)
- [ ] Test with 20+ different Figma designs

**Deliverable**: HTML generation with 85%+ visual similarity

---

### **Phase 4: Component Structure Analysis (Week 4)**
**Goal**: Identify component hierarchy from HTML

**Tasks**:
- [ ] Study library component patterns
  - Analyze parent-child relationships
  - Understand component boundaries
  - Document common patterns
- [ ] Implement Component Structure Agent
  - HTML parsing and analysis
  - Repeated section detection
  - Parent-child relationship identification
  - Component naming (with Claude AI)
- [ ] Handle edge cases:
  - Deeply nested components
  - Optional child components
  - Multiple child types
- [ ] Test hierarchy detection accuracy

**Deliverable**: Component structure extraction with proper hierarchy

---

### **Phase 5: Definition Generation (Week 5)**
**Goal**: Generate component definitions

**Tasks**:
- [ ] Analyze library ControlId patterns
- [ ] Create ControlId mapping rules
- [ ] Implement Definition Generator Agent
  - Content area identification
  - Property name generation (human + alias)
  - ControlId assignment
  - Mandatory field detection
  - DisplayOrder assignment
- [ ] Use Claude AI for semantic understanding
- [ ] Handle special cases:
  - Image resources with ResourceTypeId
  - Yes/No toggles with default values
  - URL fields
  - Alt text fields
- [ ] Validate definitions against library patterns

**Deliverable**: Definition generation matching library standards

---

### **Phase 6: Format Template Generation (Week 6)**
**Goal**: Generate Handlebars FormatContent

**Tasks**:
- [ ] Study Handlebars syntax in library formats
- [ ] Document all patterns:
  - Main component loop structure
  - Child component loops
  - Conditional logic (IfCond, IfCondObj)
  - Image path syntax
  - CMS attributes
- [ ] Implement Format Template Generator Agent
  - Variable replacement logic
  - Child component wrapping
  - Conditional generation
  - Claude AI for complex logic
- [ ] Validate generated Handlebars syntax
- [ ] Test template rendering with sample data
- [ ] Compare with library examples

**Deliverable**: FormatContent generation with valid Handlebars

---

### **Phase 7: Integration & Output (Week 7)**
**Goal**: Complete end-to-end pipeline

**Tasks**:
- [ ] Implement Orchestrator Agent
  - LangGraph workflow
  - Decision logic (match vs create)
  - Agent coordination
  - Error handling
- [ ] Implement Output Formatter Agent
  - Generate ComponentConfig JSON
  - Generate ComponentFormat JSON
  - Generate sample ComponentRecords JSON
  - Validate JSON structure
- [ ] Create end-to-end workflow
- [ ] Add comprehensive error handling
- [ ] Implement retry logic
- [ ] Add logging and monitoring
- [ ] Test complete pipeline with real Figma designs

**Deliverable**: Working end-to-end system

---

### **Phase 8: Testing & Refinement (Week 8)**
**Goal**: Test, optimize, and document

**Tasks**:
- [ ] Create test dataset (50+ Figma designs)
- [ ] Run full pipeline tests
- [ ] Measure success metrics:
  - Match accuracy
  - HTML quality
  - Definition correctness
  - FormatContent validity
  - Processing time
- [ ] Fix issues and edge cases
- [ ] Optimize performance
- [ ] Add caching where beneficial
- [ ] Create comprehensive documentation:
  - Architecture overview
  - Agent specifications
  - API documentation
  - Deployment guide
- [ ] Create example use cases
- [ ] User acceptance testing

**Deliverable**: Production-ready system with documentation

---

## Data Flow Example - Complete Walkthrough

### ⚙️ PREREQUISITE: Library Ingestion (One-time Setup)

**Before any matching can happen, we must ingest the library:**

```
┌─────────────────────────────────────────────────┐
│ STEP 0: LIBRARY INGESTION & TRAINING           │
├─────────────────────────────────────────────────┤
│ INPUT:                                          │
│ • CMS API endpoint                              │
│ • API credentials                               │
└──────────────────┬──────────────────────────────┘
                   │
      ┌────────────▼────────────┐
      │ 1. Call CMS API         │
      │    GET /api/components  │
      │    Returns: 150 IDs     │
      └────────────┬────────────┘
                   │
      ┌────────────▼─────────────────────┐
      │ 2. Download each component:      │
      │    For ID 560183:                │
      │    ├─ Config.json                │
      │    ├─ Format.json                │
      │    ├─ Records.json               │
      │    └─ Screenshot.png             │
      │    (Repeat for all 150)          │
      └────────────┬─────────────────────┘
                   │
      ┌────────────▼─────────────────────┐
      │ 3. Generate embeddings:          │
      │    Load CLIP model               │
      │    For each screenshot:          │
      │    └─ Generate 512-dim vector    │
      │    Time: ~2 minutes for 150      │
      └────────────┬─────────────────────┘
                   │
      ┌────────────▼─────────────────────┐
      │ 4. Store in database:            │
      │    PostgreSQL (with pgvector):   │
      │    ├─ 150 component records      │
      │    ├─ 1,800 definitions          │
      │    ├─ 150 embedding vectors      │
      │    │   (vector(512) column)      │
      │    └─ IVFFlat index created      │
      │    Local Storage:                │
      │    └─ 150 screenshots            │
      └────────────┬─────────────────────┘
                   │
      ┌────────────▼─────────────────────┐
      │ OUTPUT:                          │
      │ ✅ Library Ready for Matching    │
      │ ✅ 150 components indexed        │
      │ ✅ Vector search enabled         │
      │ ✅ Total time: ~15 minutes       │
      └──────────────────────────────────┘
```

**This step runs:**
- **Once** during initial setup
- **Weekly/Monthly** to sync new components
- **On-demand** when components are added/updated

**After library is ready, the main workflow can begin:**

---

### 🎯 MAIN WORKFLOW - COMPONENT GENERATION

### INITIAL INPUT:
```json
{
  "figma_screenshot": "navbar_design.png",
  "figma_screenshot_data": "[Base64 image data]",
  "metadata": {
    "section_name": "Header Navigation",
    "purpose": "Main site navigation with logo and menu",
    "page": "Homepage"
  }
}
```

---

### 📍 STEP 1: ORCHESTRATOR AGENT
**Input Received:**
- Figma screenshot: navbar_design.png
- Metadata: Header Navigation

**Decision:** Route to Library Matcher first

---

### 📍 STEP 2: LIBRARY MATCHER AGENT

**INPUT:**
```
• Figma screenshot: navbar_design.png
• Metadata: "Header Navigation"
```

**PROCESS:**
```
1. Generate CLIP embedding from Figma screenshot
2. Search vector database → Get top 5 candidates
3. Load library component screenshots:
   - Component ID 560183: "Navbar-with-center-logo"
   - Component ID 523456: "Simple Header"
   - Component ID 534789: "Mega Menu Header"
   
4. Compare visually:
   ID 560183:
   ├─ SSIM: 0.58
   ├─ CLIP similarity: 0.62
   ├─ Perceptual hash: 0.55
   └─ Semantic match: 0.62
   Overall confidence: 60%
   
5. Best match: 60% (below 85% threshold)
```

**OUTPUT:**
```json
{
  "best_match_found": false,
  "confidence": 0.60,
  "decision": "CREATE_NEW_COMPONENT",
  "reason": "No library match above 85% threshold"
}
```

**ORCHESTRATOR DECISION:** Route to Component Creator Pipeline

---

### 🔀 ALTERNATIVE FLOW: If Match Found (Confidence > 85%)

```
┌─────────────────────────────────────────────────┐
│ STEP 2B: LIBRARY MATCHER - MATCH FOUND         │
├─────────────────────────────────────────────────┤
│ Best Match: Component ID 560183                 │
│ "Navbar-with-center-logo"                       │
│ Confidence: 89%                                 │
└──────────────────┬──────────────────────────────┘
                   │
      ┌────────────▼─────────────────────┐
      │ LOAD MATCHED COMPONENT DATA      │
      │ FROM DATABASE:                   │
      │                                  │
      │ • ComponentConfig.json           │
      │   - component[] (parent+children)│
      │   - componentDefinition[]        │
      │                                  │
      │ • ComponentFormat.json           │
      │   - FormatContent (Handlebars)   │
      │                                  │
      │ • ComponentRecords.json          │
      │   - 1 parent + children sample   │
      └────────────┬─────────────────────┘
                   │
      ┌────────────▼─────────────────────┐
      │ SKIP ALL OTHER AGENTS:           │
      │ ❌ HTML Generator (not needed)   │
      │ ❌ Visual Validator (not needed) │
      │ ❌ Structure Agent (not needed)  │
      │ ❌ Definition Agent (not needed) │
      │ ❌ Template Agent (not needed)   │
      │                                  │
      │ ✅ Use existing data as-is       │
      └────────────┬─────────────────────┘
                   │
      ┌────────────▼─────────────────────┐
      │ RETURN MATCHED COMPONENT         │
      │                                  │
      │ OUTPUT:                          │
      │ • ComponentConfig.json           │
      │ • ComponentFormat.json           │
      │ • ComponentRecords.json          │
      │                                  │
      │ Source: "MATCHED_FROM_LIBRARY"   │
      │ Component ID: 560183             │
      │ Processing time: ~3 seconds      │
      └──────────────────────────────────┘
```

**Benefits of Using Matched Component:**
- ⚡ **Fast**: ~3 seconds (vs ~35 seconds for new generation)
- 💰 **No API costs**: No Claude AI calls needed
- ✅ **Proven**: Component already exists and works
- 📐 **Consistent**: Maintains design system standards

---

### 📍 STEP 3: HTML GENERATOR AGENT (Claude AI)

**(Only runs if NO match found)**

**INPUT:**
```
• Figma screenshot: navbar_design.png
• Metadata: Header Navigation
• Context: 3 similar navbar examples from library for learning
```

**PROMPT TO CLAUDE:**
```
"Analyze this navigation bar screenshot and generate semantic HTML.
Include: logo, navigation menu, CTA button.
Examples from library: [navbar examples...]"
```

**OUTPUT:**
```json
{
  "html": "<header class=\"header\">\n  <div class=\"header-container\">\n    <a href=\"/\" class=\"logo\">\n      <img src=\"logo.png\" alt=\"Company Logo\">\n    </a>\n    <nav class=\"nav-menu\">\n      <ul class=\"nav-list\">\n        <li class=\"nav-item\"><a href=\"/home\">Home</a></li>\n        <li class=\"nav-item\"><a href=\"/about\">About</a></li>\n        <li class=\"nav-item\"><a href=\"/services\">Services</a></li>\n      </ul>\n    </nav>\n    <a href=\"/contact\" class=\"cta-button\">Contact Us</a>\n  </div>\n</header>",
  "identified_elements": {
    "images": ["logo"],
    "text_fields": ["nav-item text", "button text"],
    "links": ["nav links", "button link"],
    "repeating_sections": ["nav-list items"]
  }
}
```

---

### 📍 STEP 4: VISUAL VALIDATOR AGENT

**INPUT:**
```
• Original Figma screenshot: navbar_design.png
• Generated HTML: <header>...</header>
```

**PROCESS:**
```
1. Render HTML using Playwright → rendered_output.png
2. Resize both images to same dimensions
3. Calculate metrics:
   ├─ SSIM: 0.91
   ├─ MSE: 245.3
   ├─ CLIP perceptual: 0.95
   └─ Pixel accuracy: 0.92
4. Combined similarity score: 0.93 (above 0.90 threshold)
```

**OUTPUT:**
```json
{
  "is_valid": true,
  "similarity_score": 0.93,
  "metrics": {
    "ssim": 0.91,
    "perceptual": 0.95,
    "pixel_accuracy": 0.92
  },
  "decision": "PROCEED",
  "iterations": 1
}
```

---

### 📍 STEP 5: COMPONENT STRUCTURE AGENT

**INPUT:**
```
• Validated HTML: <header>...</header>
• Component name: "Header Navigation"
```

**PROCESS:**
```
1. Parse HTML structure
2. Identify main container: <header>
3. Detect repeating sections: <li class="nav-item"> (repeats 3 times)
4. Determine hierarchy:
   - Parent: Header Navigation (contains logo, button)
   - Child: Navigation Menu Items (repeating list items)
```

**OUTPUT:**
```json
{
  "components": [
    {
      "component_name": "Header Navigation",
      "component_alias": "header-navigation",
      "parent_id": null,
      "level": 0,
      "html_section": "<header>...</header>",
      "contains_children": true
    },
    {
      "component_name": "Header Navigation Menu Item",
      "component_alias": "header-navigation-menu-item",
      "parent_id": "header-navigation",
      "level": 1,
      "html_section": "<li><a>...</a></li>",
      "max_records": 50,
      "min_records": 1
    }
  ]
}
```

---

### 📍 STEP 6: DEFINITION GENERATOR AGENT

**INPUT:**
```
• Component structure (2 components)
• HTML for each component
• Library patterns for learning
```

**PROCESS:**
```
For "Header Navigation" (Parent):
1. Analyze <img> tag → Image resource → ControlId 7
2. Analyze button text → Text field → ControlId 1
3. Analyze button href → URL field → ControlId 1
4. Learn naming from library examples

For "Header Navigation Menu Item" (Child):
1. Analyze <a> text → Text field → ControlId 1
2. Analyze <a> href → URL field → ControlId 1
```

**OUTPUT:**
```json
{
  "component_id": "header-navigation",
  "definitions": [
    {
      "PropertyName": "Logo Image",
      "PropertyAliasName": "logo-image",
      "ControlId": 7,
      "IsMandatory": true,
      "PropertyMaxLength": 1,
      "ResourceTypeId": 313562,
      "DisplayOrder": 1,
      "html_selector": "img.logo"
    },
    {
      "PropertyName": "Logo Alt Text",
      "PropertyAliasName": "logo-alt-text",
      "ControlId": 1,
      "IsMandatory": true,
      "PropertyMaxLength": 200,
      "DisplayOrder": 2,
      "html_selector": "img.logo@alt"
    },
    {
      "PropertyName": "CTA Button Text",
      "PropertyAliasName": "cta-button-text",
      "ControlId": 1,
      "IsMandatory": true,
      "PropertyMaxLength": 50,
      "DisplayOrder": 3,
      "html_selector": "a.cta-button"
    },
    {
      "PropertyName": "CTA Button Link",
      "PropertyAliasName": "cta-button-link",
      "ControlId": 1,
      "IsMandatory": true,
      "PropertyMaxLength": 500,
      "DisplayOrder": 4,
      "html_selector": "a.cta-button@href"
    }
  ]
},
{
  "component_id": "header-navigation-menu-item",
  "definitions": [
    {
      "PropertyName": "Menu Item Name",
      "PropertyAliasName": "menu-item-name",
      "ControlId": 1,
      "IsMandatory": true,
      "PropertyMaxLength": 100,
      "DisplayOrder": 1,
      "html_selector": "a"
    },
    {
      "PropertyName": "Menu Item Link",
      "PropertyAliasName": "menu-item-link",
      "ControlId": 1,
      "IsMandatory": true,
      "PropertyMaxLength": 500,
      "DisplayOrder": 2,
      "html_selector": "a@href"
    }
  ]
}
```

---

### 📍 STEP 7: FORMAT TEMPLATE GENERATOR AGENT

**INPUT:**
```
• Original HTML
• Component structure
• Component definitions
```

**PROCESS:**
```
1. Start with original HTML
2. Replace "logo.png" → {{data.logo-image.0.OriginalImagePath}}
3. Replace "Company Logo" → {{data.logo-alt-text}}
4. Replace "Contact Us" → {{data.cta-button-text}}
5. Replace "/contact" → {{data.cta-button-link}}
6. Wrap nav items in child component loop
7. Add CMS attributes (dynamiccomponenteditenable, %%componentRecordEditable%%)
```

**OUTPUT:**
```json
{
  "FormatContent": "{{#each ComponentRecordJson.header-navigation}}\n<header class=\"header dynamiccomponenteditenable\" %%componentRecordEditable%%>\n  <div class=\"header-container\">\n    <a href=\"%%strpath%%\" class=\"logo\">\n      <img src=\"{{data.logo-image.0.OriginalImagePath}}\" alt=\"{{data.logo-alt-text}}\">\n    </a>\n    <nav class=\"nav-menu\">\n      <ul class=\"nav-list\">\n        {{#each Child.header-navigation-menu-item}}\n        {{IfCond this.ParentId '=' ../this.Id}}\n        <li class=\"nav-item dynamiccomponenteditenable\" %%componentRecordEditable%%>\n          <a href=\"{{data.menu-item-link}}\">{{data.menu-item-name}}</a>\n        </li>\n        {{/IfCond}}\n        {{/each}}\n      </ul>\n    </nav>\n    <a href=\"{{data.cta-button-link}}\" class=\"cta-button\">{{data.cta-button-text}}</a>\n  </div>\n</header>\n{{/each}}"
}
```

---

### 📍 STEP 8: OUTPUT FORMATTER AGENT

**INPUT:**
```
• Component structure (2 components)
• All definitions
• FormatContent template
```

**OUTPUT 1 - ComponentConfig.json:**
```json
{
  "component": [
    {
      "ComponentId": 0,
      "ComponentName": "Header Navigation",
      "ComponentAliasName": "header-navigation",
      "ParentId": null,
      "FormatId": 0,
      "MaxRecord": 5,
      "MinRecord": 1,
      "Status": true
    },
    {
      "ComponentId": 0,
      "ComponentName": "Header Navigation Menu Item",
      "ComponentAliasName": "header-navigation-menu-item",
      "ParentId": 0,
      "FormatId": 0,
      "MaxRecord": 50,
      "MinRecord": 1,
      "Status": true
    }
  ],
  "componentDefinition": [
    {
      "DefinitionId": 0,
      "ComponentId": 0,
      "PropertyName": "Logo Image",
      "PropertyAliasName": "logo-image",
      "ControlId": 7,
      "IsMandatory": true,
      "PropertyMaxLength": 1,
      "DisplayOrder": 1
    },
    // ... all other definitions
  ]
}
```

**OUTPUT 2 - ComponentFormat.json:**
```json
{
  "ComponentFormat": [
    {
      "FormatId": 0,
      "FormatName": "Header Navigation",
      "FormatKey": "header-navigation",
      "FormatContent": "{{#each ComponentRecordJson.header-navigation}}...",
      "Status": 1
    }
  ]
}
```

**OUTPUT 3 - ComponentRecords.json (Sample - ONE ACTIVE SET ONLY):**
```json
{
  "componentRecords": [
    {
      "Id": 1,
      "ComponentId": 0,
      "ParentComponentId": null,
      "RecordJsonString": "{\"Id\":\"##Id##\",\"ParentId\":\"##ParentId##\",\"logo-image\":[{...}],\"logo-alt-text\":\"Company Logo\",\"cta-button-text\":\"Contact Us\",\"cta-button-link\":\"/contact\"}",
      "ParentId": 0,
      "MainParentComponentId": 0,
      "level": 0,
      "Status": true
    },
    {
      "Id": 2,
      "ComponentId": 1,
      "ParentComponentId": 0,
      "RecordJsonString": "{\"Id\":\"##Id##\",\"ParentId\":\"##ParentId##\",\"menu-item-name\":\"Home\",\"menu-item-link\":\"/home\"}",
      "ParentId": 1,
      "MainParentComponentId": 0,
      "level": 1,
      "Status": true
    },
    {
      "Id": 3,
      "ComponentId": 1,
      "ParentComponentId": 0,
      "RecordJsonString": "{\"Id\":\"##Id##\",\"ParentId\":\"##ParentId##\",\"menu-item-name\":\"About\",\"menu-item-link\":\"/about\"}",
      "ParentId": 1,
      "MainParentComponentId": 0,
      "level": 1,
      "Status": true
    }
  ]
}
```

**Note**: 
- ✅ Includes 1 parent record (level 0)
- ✅ Includes its child records (level 1+)
- ✅ All records are active (Status: true)
- ❌ Does NOT include all 500+ historical records
- Purpose: Demonstrate structure for CMS import

---

### ✅ FINAL OUTPUT DELIVERED:
```
✓ ComponentConfig.json     (Ready for CMS import)
  - 2 components (parent + child)
  - 4 definitions total
  
✓ ComponentFormat.json     (Ready for CMS import)
  - Handlebars template with variables
  
✓ ComponentRecords.json    (Sample - ONE ACTIVE SET)
  - 1 parent record (level 0)
  - 2-3 child records (level 1)
  - All Status: true (active)
  - NOT all 500+ historical records

Total Processing Time: ~35 seconds
Success Rate: 100%
Visual Similarity: 93%
Component Structure: Validated ✓
```

---

## Success Metrics

### Quality Metrics
| Metric | Target | Measurement |
|--------|--------|-------------|
| Library Match Accuracy | >85% | % correct matches when similar component exists |
| HTML Visual Similarity | >90% | SSIM + perceptual score after generation |
| Component Structure Accuracy | >90% | % correct parent-child relationships |
| Definition Correctness | >85% | % definitions with correct ControlId and naming |
| FormatContent Validity | >95% | % templates that render correctly with sample data |
| Overall Success Rate | >80% | % Figma designs fully converted without errors |

### Performance Metrics
| Metric | Target |
|--------|--------|
| Library Search | <2 seconds |
| HTML Generation | <15 seconds |
| Visual Validation | <5 seconds |
| Definition Generation | <5 seconds |
| Template Generation | <3 seconds |
| **Total End-to-End** | **<45 seconds** |

### Cost Metrics
| Item | Estimated Cost |
|------|---------------|
| Claude API (per component) | $0.10 - 0.30 |
| Storage (embeddings + DB) | $50/month |
| Compute (rendering, etc.) | $100/month |

---

## Technology Stack & Architecture Options

### 🎯 RECOMMENDATION FOR YOUR SITUATION

**Since deployment platform is uncertain (might be Azure, AWS, or others):**

> **Use Option A: Anthropic Direct API + LangGraph + FastAPI** ⭐

**This gives you:**
- ✅ Deploy anywhere (Azure, AWS, GCP, on-prem)
- ✅ No vendor lock-in
- ✅ Lower cost ($305-430/month vs $440-540)
- ✅ Maximum flexibility
- ✅ Easy migration between platforms
- ✅ Same code everywhere

---

### Application Type

**Full-Stack Web Application** (Browser-Based UI + API Backend)

#### **Frontend: Web-Based User Interface**
- **React.js** or **HTML + JavaScript** - Browser-based UI
- Upload Figma screenshots via drag-and-drop
- Visual progress tracking and results display
- Real-time updates using WebSockets
- Download generated JSON files
- **No CLI needed for usage** - everything in the browser! ✅

#### **Backend: FastAPI REST API Server**
- Asynchronous Python web framework
- Handles file uploads, processing, and results
- WebSocket for real-time progress updates
- Serves the frontend interface
- Auto-generated API documentation (OpenAPI/Swagger)

**Why FastAPI over Flask?**
- ✅ Async/await support (critical for AI API calls)
- ✅ Built-in WebSocket support (for real-time updates)
- ✅ Automatic Pydantic validation
- ✅ Can serve frontend files
- ✅ Better performance (similar to Node.js/Go)
- ✅ Type hints and IDE support

**User Experience: Browser-Based Interface**

1. Open browser → Go to `http://localhost:8000` (or your domain)
2. See clean web interface
3. **Paste Figma URL** (two options):
   - **Option A**: Specific section/node URL → Processes that section only
   - **Option B**: Entire page URL → Automatically detects and processes all sections
4. Click "Fetch from Figma" button
5. System uses Figma API to:
   - Get screenshot for each section
   - Extract metadata (name, dimensions, properties)
   - Identify all child sections (if page URL)
6. Preview detected sections (if page URL, shows list)
7. Select which sections to process (or "Process All")
8. Watch real-time progress for each section:
   - "Section 1: Searching library..." ⏳
   - "Section 1: Generating HTML..." ⏳
   - "Section 2: Searching library..." ⏳
9. See results for each processed section:
   - Preview of generated component
   - Download buttons for JSON files
   - Match information (if found in library)
10. **No command line needed!** ✅
11. **No manual screenshots needed!** ✅

### Web UI Mockup

```
┌─────────────────────────────────────────────────────────────────┐
│  🎨 Figma to MiBlock Component Generator                        │
│                                                                  │
│  Library Status: ✅ 150 components | Last updated: 2 hours ago  │
│  [ 🔄 Refresh Library ] [ ⚙️ Settings ]                         │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  🔗 Enter Figma URL                                             │
│  ┌────────────────────────────────────────────────────────┐     │
│  │ https://www.figma.com/file/abc123/Design?node-id=... │ 🔍 │
│  └────────────────────────────────────────────────────────┘     │
│                                                                  │
│  💡 Tips:                                                        │
│  • Paste a specific section/node URL to process one section     │
│  • Paste a page URL to process all sections on that page        │
│                                                                  │
│  [ Fetch from Figma ] button                                    │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  📋 Detected Sections (3 found)                                 │
│  ┌────────────────────────────────────────────────────────┐     │
│  │ ☑️ Section 1: "Hero Section" (1920x800px)             │     │
│  │    Preview: [thumbnail image]                          │     │
│  │                                                         │     │
│  │ ☑️ Section 2: "Navigation Bar" (1920x80px)            │     │
│  │    Preview: [thumbnail image]                          │     │
│  │                                                         │     │
│  │ ☑️ Section 3: "Footer" (1920x400px)                   │     │
│  │    Preview: [thumbnail image]                          │     │
│  └────────────────────────────────────────────────────────┘     │
│                                                                  │
│  [ Select All ] [ Deselect All ]                                │
│  [ Process Selected Sections ] button                           │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  ⚙️ Processing Status                                           │
│  ┌────────────────────────────────────────────────────────┐     │
│  │ ✅ Searching library...         [====    ] 60%        │     │
│  │ ⏳ Generating HTML...            [        ]  0%        │     │
│  │ ⏸️  Visual validation...         [        ]  0%        │     │
│  │ ⏸️  Extracting definitions...    [        ]  0%        │     │
│  └────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  ✅ Results                                                      │
│  ┌────────────────────────────────────────────────────────┐     │
│  │ Status: ✅ Component Generated Successfully            │     │
│  │ Source: 📚 Matched from library (89% confidence)       │     │
│  │ Component: "Navbar-with-center-logo"                   │     │
│  │                                                         │     │
│  │ [ Download ComponentConfig.json   ]                    │     │
│  │ [ Download ComponentFormat.json   ]                    │     │
│  │ [ Download ComponentRecords.json  ]                    │     │
│  │ [ Download All (ZIP)              ]                    │     │
│  │                                                         │     │
│  │ 📊 Preview:                                            │     │
│  │ {                                                       │     │
│  │   "component_name": "Hero Section",                    │     │
│  │   "definitions": [...],                                │     │
│  │   ...                                                   │     │
│  │ }                                                       │     │
│  └────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  📜 Recent Conversions                                          │
│  • Navbar Component (2 minutes ago) - Matched                   │
│  • Hero Section (5 minutes ago) - Generated                    │
│  • Footer Component (10 minutes ago) - Matched                  │
└─────────────────────────────────────────────────────────────────┘

─────────────────────────────────────────────────────────────────

When "🔄 Refresh Library" button is clicked:

┌─────────────────────────────────────────────────────────────────┐
│  🔄 Refreshing Component Library                                │
│                                                                  │
│  📥 Downloading components from CMS...                          │
│  ┌────────────────────────────────────────────────────────┐     │
│  │ Progress: [=========>           ] 45/150 components    │     │
│  └────────────────────────────────────────────────────────┘     │
│                                                                  │
│  Current: Downloading "Hero Section Variant 3"                  │
│                                                                  │
│  📊 Downloaded:                                                 │
│  ├─ ComponentConfig: ✅ 45 files                                │
│  ├─ ComponentFormat: ✅ 45 files                                │
│  ├─ ComponentRecords: ✅ 45 files                               │
│  └─ Screenshots: ✅ 45 images                                   │
│                                                                  │
│  🧠 Generating embeddings...                                    │
│  ┌────────────────────────────────────────────────────────┐     │
│  │ Progress: [=======             ] 30/45 processed       │     │
│  └────────────────────────────────────────────────────────┘     │
│                                                                  │
│  💾 Storing in database...                                      │
│  ┌────────────────────────────────────────────────────────┐     │
│  │ Progress: [==========          ] 30/45 stored          │     │
│  └────────────────────────────────────────────────────────┘     │
│                                                                  │
│  ⏱️ Estimated time remaining: 5 minutes                         │
│                                                                  │
│  [ ⏸️ Pause ] [ ❌ Cancel ]                                      │
└─────────────────────────────────────────────────────────────────┘

After completion:

┌─────────────────────────────────────────────────────────────────┐
│  ✅ Library Refresh Complete!                                   │
│                                                                  │
│  📊 Summary:                                                    │
│  ├─ Total components: 150                                       │
│  ├─ New components: 5                                           │
│  ├─ Updated components: 12                                      │
│  ├─ Embeddings generated: 17                                    │
│  ├─ Database updated: ✅                                        │
│  ├─ Vector index rebuilt: ✅                                    │
│  └─ Time taken: 12 minutes                                      │
│                                                                  │
│  Last refresh: Just now                                         │
│                                                                  │
│  [ Close ] [ View Component List ]                              │
└─────────────────────────────────────────────────────────────────┘
```

### 🔧 Architecture Options

#### **Option A: Anthropic Claude API (Direct) - Current Plan**

**Core:**
- **Python 3.11+**
- **FastAPI** - REST API server
- **LangGraph** - Agent orchestration framework
- **Anthropic Claude 3.5 Sonnet API** - Direct API calls for vision-to-code

**Pros:**
- ✅ Simple, direct API integration
- ✅ Full control over prompts and responses
- ✅ Works anywhere (local, any cloud)
- ✅ Flexible pricing (pay per token)

**Cons:**
- ❌ Need to manage API keys manually
- ❌ No built-in agent framework features
- ❌ Rate limiting management needed

---

#### **Option B: AWS Bedrock + Agents (Recommended for AWS)**

**Core:**
- **Python 3.11+**
- **FastAPI** - REST API server
- **AWS Bedrock** - Managed AI service
- **Bedrock Agents** - Built-in agent orchestration
- **Claude 3.5 Sonnet via Bedrock** - Same model, AWS-managed

**Pros:**
- ✅ AWS-native integration
- ✅ Built-in agent framework (Bedrock Agents)
- ✅ IAM-based security
- ✅ Built-in guardrails and safety features
- ✅ Better for production AWS deployments
- ✅ Automatic scaling and management
- ✅ Can use multiple models (Claude, Llama, etc.)
- ✅ Integration with AWS services (S3, Lambda, etc.)

**Cons:**
- ❌ AWS-specific (vendor lock-in)
- ❌ Slightly higher costs than direct API
- ❌ Less flexible than custom LangGraph

**Bedrock Agent Architecture:**
```
FastAPI Server
    ↓
AWS Bedrock Agent (replaces LangGraph)
    ├─ Action Groups (Agent actions)
    │  ├─ Library Search Action
    │  ├─ HTML Generation Action
    │  ├─ Visual Validation Action
    │  └─ Component Assembly Action
    ↓
Claude 3.5 via Bedrock
PostgreSQL + pgvector
```

---

### ⭐ Recommended: **Option A (Anthropic Direct)** for Platform Flexibility

**If deployment platform is uncertain (AWS, Azure, GCP, on-prem) → Use Option A**

**Why Anthropic Direct is better for flexibility:**
1. ✅ **Works Everywhere**: Azure, AWS, GCP, on-premises, any cloud
2. ✅ **No Vendor Lock-in**: Not tied to any cloud provider
3. ✅ **Simpler Migration**: Easy to move between platforms
4. ✅ **Lower Cost**: ~$330/month vs $440+ for managed services
5. ✅ **Full Control**: Complete control over prompts and logic
6. ✅ **Standard Technologies**: FastAPI + LangGraph work anywhere

**Use Option B (AWS Bedrock) ONLY if:**
- ❌ Already committed to AWS
- ❌ Need AWS-specific integrations
- ❌ Want fully managed AI services

---

### 🌐 Platform-Agnostic Deployment (Option A)

**Option A works on ANY platform:**

#### **On Azure:**
```
Azure App Service / Container Instances
    ↓
FastAPI Application
    ↓
LangGraph (Agent Orchestration)
    ↓
Anthropic Claude API
    ↓
Azure Database for PostgreSQL (with pgvector)
Azure Cache for Redis
Azure Blob Storage (screenshots)
```

#### **On AWS:**
```
ECS/Fargate / EC2
    ↓
FastAPI Application
    ↓
LangGraph
    ↓
Anthropic Claude API
    ↓
RDS PostgreSQL + pgvector
ElastiCache Redis
S3
```

#### **On Google Cloud:**
```
Cloud Run / GKE
    ↓
FastAPI Application
    ↓
LangGraph
    ↓
Anthropic Claude API
    ↓
Cloud SQL PostgreSQL + pgvector
Memorystore Redis
Cloud Storage
```

#### **On-Premises:**
```
Docker / Kubernetes
    ↓
FastAPI Application
    ↓
LangGraph
    ↓
Anthropic Claude API
    ↓
Self-hosted PostgreSQL + pgvector
Self-hosted Redis
Local Storage
```

**Key Point**: The application code is IDENTICAL across all platforms. Only infrastructure changes.

---

### 📘 Quick Azure Deployment Guide (Option A)

Since you mentioned Azure as a possibility, here's how Option A deploys there:

#### **Azure Services:**

```
┌─────────────────────────────────────────┐
│ Azure App Service / Container Instances │
│ (FastAPI Application)                   │
└──────────────┬──────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────┐
│ Azure Database for PostgreSQL           │
│ (Flexible Server with pgvector)         │
│ - Component library                      │
│ - Embeddings in vector columns           │
└──────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────┐
│ Azure Cache for Redis                    │
│ (Caching layer)                          │
└──────────────────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────┐
│ Azure Blob Storage                       │
│ (Screenshot storage)                     │
└──────────────────────────────────────────┘
```

#### **Azure-Specific Configuration:**

```python
# .env for Azure
DATABASE_URL=postgresql://admin@myserver.postgres.database.azure.com:5432/figma_cms
CACHE_TTL=3600  # In-memory cache (no Redis)
STORAGE_ACCOUNT=mystorageaccount.blob.core.windows.net
ANTHROPIC_API_KEY=your_api_key  # Same everywhere!
```

#### **pgvector on Azure PostgreSQL:**

```bash
# Enable pgvector on Azure Database for PostgreSQL
az postgres flexible-server parameter set \
  --resource-group myResourceGroup \
  --server-name myserver \
  --name azure.extensions \
  --value VECTOR

# Then in database:
CREATE EXTENSION vector;
```

#### **Deployment:**

```bash
# Deploy to Azure App Service
az webapp up \
  --name figma-cms-generator \
  --runtime "PYTHON:3.11" \
  --sku B1

# Or use Docker
az acr build --registry myregistry --image figma-cms-generator:latest .
az webapp create --resource-group myRG \
  --plan myPlan \
  --name figma-cms-generator \
  --deployment-container-image-name myregistry.azurecr.io/figma-cms-generator:latest
```

#### **Cost on Azure (Monthly):**

| Service | Cost |
|---------|------|
| App Service (B1) | ~$55 |
| PostgreSQL Flexible Server (B1ms) | ~$30 |
| ~~Redis Cache (Basic)~~ | ~~$15~~ (removed) |
| Blob Storage | ~$5 |
| Anthropic Claude API | $200-300 |
| **Total** | **~$290-390/month** |

**Same application, works identically on Azure, AWS, or GCP!** 🎯  
**(Now even cheaper - no Redis needed!)** ✨

---

## 🚀 AWS Bedrock Implementation Guide (Option B - AWS Only)

### Bedrock Agent Architecture

Instead of LangGraph, use **AWS Bedrock Agents** for orchestration:

```python
# Bedrock Agent Configuration
bedrock_agent = {
    "agentName": "FigmaToMiBlockAgent",
    "foundationModel": "anthropic.claude-3-5-sonnet-20241022-v2:0",
    "instruction": """You convert Figma designs to MiBlock CMS components.
    Use action groups to:
    1. Search component library for matches
    2. Generate HTML from screenshots if no match
    3. Validate visual similarity
    4. Extract component structure and definitions
    5. Generate MiBlock JSON output""",
    
    "actionGroups": [
        {
            "actionGroupName": "LibrarySearch",
            "description": "Search component library using pgvector",
            "actionGroupExecutor": {
                "lambda": "arn:aws:lambda:us-east-1:xxx:function:library-search"
            }
        },
        {
            "actionGroupName": "HTMLGeneration",
            "description": "Generate HTML from Figma screenshots",
            "actionGroupExecutor": {
                "lambda": "arn:aws:lambda:us-east-1:xxx:function:html-generator"
            }
        },
        {
            "actionGroupName": "VisualValidation",
            "description": "Validate HTML against screenshot",
            "actionGroupExecutor": {
                "lambda": "arn:aws:lambda:us-east-1:xxx:function:visual-validator"
            }
        },
        {
            "actionGroupName": "ComponentExtraction",
            "description": "Extract structure, definitions, and generate MiBlock JSON",
            "actionGroupExecutor": {
                "lambda": "arn:aws:lambda:us-east-1:xxx:function:component-extractor"
            }
        }
    ]
}
```

### AWS Services Architecture

```
┌─────────────────────────────────────────────┐
│  User/Client                                │
└────────────┬────────────────────────────────┘
             │
             ▼
┌────────────────────────────────────────────┐
│  Amazon API Gateway                        │
│  (REST API endpoint)                       │
└────────────┬───────────────────────────────┘
             │
             ▼
┌────────────────────────────────────────────┐
│  AWS Lambda / ECS Fargate                  │
│  (FastAPI Application)                     │
└────────────┬───────────────────────────────┘
             │
             ▼
┌────────────────────────────────────────────┐
│  Amazon Bedrock Agent                      │
│  (Orchestrates all actions)                │
└────────────┬───────────────────────────────┘
             │
        ┌────┴────┐
        ▼         ▼
┌─────────────┐  ┌───────────────────┐
│ AWS Lambda  │  │ Claude 3.5 Sonnet │
│ Functions   │  │ via Bedrock       │
│ (Actions)   │  └───────────────────┘
└──────┬──────┘
       │
       ▼
┌────────────────────────────────────────────┐
│  Amazon RDS PostgreSQL + pgvector          │
│  (Component library + embeddings)          │
└────────────────────────────────────────────┘
       │
       ▼
┌────────────────────────────────────────────┐
│  Amazon S3                                 │
│  (Screenshot storage)                      │
└────────────────────────────────────────────┘
```

### Cost Comparison (Monthly, ~1000 components)

| Item | Anthropic Direct | AWS Bedrock |
|------|------------------|-------------|
| Claude API | $200-300 | $250-350 |
| Database (RDS) | $50 | $50 |
| Compute | $50 (self-hosted) | $100 (Lambda/ECS) |
| Storage (S3) | - | $10 |
| ~~Cache (ElastiCache)~~ | ~~$30~~ (removed) | ~~$30~~ (removed) |
| Management | Manual | Auto-managed |
| **Total** | **$300-400** | **$410-510** |

**Bedrock Premium**: ~27% more expensive but fully managed with auto-scaling.  
**Note**: Now even cheaper with in-memory cache (no ElastiCache needed)!

### 🎯 Which Architecture Should You Choose?

| Your Situation | Recommendation | Why |
|---------------|----------------|-----|
| **Deployment platform uncertain** | ✅ **Option A (Anthropic Direct)** | Works anywhere, no lock-in |
| **Might use Azure** | ✅ **Option A (Anthropic Direct)** | Azure has no equivalent to Bedrock Agents |
| **Might use multiple clouds** | ✅ **Option A (Anthropic Direct)** | One codebase, deploy anywhere |
| **Cost-conscious** | ✅ **Option A (Anthropic Direct)** | ~$110/month cheaper |
| **Need flexibility** | ✅ **Option A (Anthropic Direct)** | Full control, no vendor APIs |
| **Committed to AWS only** | Option B (AWS Bedrock) | Simplest for AWS-only |
| **Want fully managed** | Option B (AWS Bedrock) | AWS handles scaling/security |

**For your case (deployment uncertain, maybe Azure): Choose Option A** ⭐

---

### Why Option A is Perfect When Platform is Uncertain

**1. Platform Independence**
```python
# Same code works on Azure, AWS, GCP, on-prem
from anthropic import Anthropic
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
```

**2. Easy Migration**
- Move from Azure to AWS? Just change infrastructure, code stays same
- Start on-prem, move to cloud later? No problem
- Multi-cloud? Deploy to both simultaneously

**3. Standard Technologies**
- **FastAPI**: Runs on any Python host
- **PostgreSQL**: Available everywhere (Azure, AWS, GCP)
- **LangGraph**: Platform-agnostic Python library
- **Anthropic API**: Internet-accessible from anywhere

**4. Docker-Based Deployment**
```dockerfile
# Single Docker image works everywhere
FROM python:3.11
COPY . /app
RUN pip install -r requirements.txt
CMD ["uvicorn", "src.api.app:app", "--host", "0.0.0.0"]
```

**5. Cost Transparency**
- Anthropic: $200-300/month (same everywhere)
- Infrastructure: Varies by provider, but YOU control it
- No hidden managed service fees

---

### ⚠️ Don't Choose AWS Bedrock If:

- ❌ Deployment platform is uncertain
- ❌ Might use Azure or GCP
- ❌ Need to avoid vendor lock-in
- ❌ Want to keep infrastructure options open
- ❌ May need multi-cloud deployment

---

### AI/ML

**Option A: Direct Anthropic API**
- **anthropic** - Anthropic Claude API client
- **CLIP** (OpenAI) - Visual embeddings (512-dimensional vectors)
- **LangGraph** - Agent orchestration

**Option B: AWS Bedrock (Recommended for AWS)**
- **boto3** - AWS SDK for Python
- **bedrock-agent-runtime** - Bedrock Agents SDK
- **CLIP** (OpenAI) - Visual embeddings (512-dimensional vectors)
- No LangGraph needed (use Bedrock Agents instead)

### Data & Storage
- **PostgreSQL 15+** - Main database
  - Can use AWS RDS PostgreSQL with pgvector
- **pgvector 0.5+** - Vector similarity search extension (IVFFlat index)
- **psycopg2-binary** - PostgreSQL adapter
- **SQLAlchemy 2.0+** - ORM
- **pgvector-python** - Python client for pgvector
- **In-Memory Cache** - Simple Python dict cache (no Redis needed)

### Image Processing
- **Pillow (PIL)** - Image manipulation
- **scikit-image** - SSIM calculation
- **Playwright** - HTML rendering

### Web & API (Backend)
- **FastAPI** - REST API server
- **httpx** - Async HTTP client
- **Pydantic** - Data validation
- **python-multipart** - File upload handling
- **websockets** - Real-time updates

### Web UI (Frontend)
**Option 1: Simple HTML/JS (Recommended for MVP)**
- **HTML5** - Structure
- **CSS3** / **Tailwind CSS** - Styling
- **Vanilla JavaScript** - Interactivity
- **Fetch API** - HTTP requests
- **WebSocket API** - Real-time updates

**Option 2: React (For advanced UI)**
- **React.js** - Component-based UI
- **Axios** - HTTP client
- **React Dropzone** - File upload
- **Socket.io-client** - WebSocket connection
- **Tailwind CSS** - Styling

### Development
- **pytest** - Testing
- **black** - Code formatting
- **mypy** - Type checking

---

## File Structure

```
designToCodeAiAgent/
├── src/
│   ├── agents/
│   │   ├── orchestrator_agent.py
│   │   ├── library_matcher_agent.py
│   │   ├── html_generator_agent.py
│   │   ├── visual_validator_agent.py
│   │   ├── component_structure_agent.py
│   │   ├── definition_generator_agent.py
│   │   ├── format_template_generator_agent.py
│   │   └── output_formatter_agent.py
│   ├── api/
│   │   ├── figma_client.py
│   │   ├── claude_client.py
│   │   ├── cms_client.py
│   │   └── app.py
│   ├── models/
│   │   ├── miblock_component.py
│   │   ├── component_definition.py
│   │   ├── format_template.py
│   │   └── agent_state.py
│   ├── database/
│   │   ├── models.py
│   │   └── repository.py
│   ├── embeddings/
│   │   ├── visual_embeddings.py
│   │   └── vector_store.py
│   ├── validation/
│   │   ├── visual_similarity.py
│   │   └── html_validator.py
│   ├── prompts/
│   │   ├── html_generation_prompts.py
│   │   ├── definition_extraction_prompts.py
│   │   └── template_generation_prompts.py
│   ├── workflows/
│   │   └── langgraph_workflow.py
│   └── utils/
│       ├── config.py
│       ├── logging.py
│       └── handlebars_utils.py
├── tests/
├── data/
│   ├── component_library/
│   └── mi-block-ID-560183/  # Sample data
├── scripts/
│   ├── ingest_library.py
│   └── generate_embeddings.py
├── requirements.txt
├── .env.example
├── README.md
└── FINAL_DEVELOPMENT_PLAN.md
```

---

## 📊 Progress Tracking

**Use this checklist to track implementation progress:**

### Phase Completion
- [ ] **Phase 1 (Steps 1-15)**: Foundation & Setup
- [ ] **Phase 2 (Steps 16-30)**: Library Ingestion & Training
- [ ] **Phase 3 (Steps 31-42)**: HTML Generation & Validation
- [ ] **Phase 4 (Steps 43-52)**: Component Structure Analysis
- [ ] **Phase 5 (Steps 53-65)**: Definition Generation
- [ ] **Phase 6 (Steps 66-77)**: Format Template Generation
- [ ] **Phase 7 (Steps 78-105)**: Integration, Orchestration, Figma API, Web UI & Library Refresh UI
- [ ] **Phase 8 (Steps 106-122)**: UI Polish, Testing & Deployment

### Current Status
```
Phase: _____
Current Step: _____
Last Completed: _____
Next Step: _____
```

---

## Next Steps to Begin Implementation

### 1. Review & Approve
- [ ] Review this complete development plan
- [ ] Confirm the agent workflow makes sense
- [ ] Check the 100 numbered steps

### 2. Clarify Requirements (see Questions section below)
- [ ] CMS API endpoints and authentication
- [ ] ControlId types and meanings
- [ ] Handlebars helpers needed
- [ ] Screenshot formats

### 3. Start Implementation
**When ready, simply tell me which step to work on:**

**Examples:**
- "Start with step 1" → I'll create project structure
- "Let's do Phase 1" → I'll work through steps 1-15
- "Work on step 16" → I'll start library ingestion
- "Skip to step 31" → I'll start HTML generation
- "Do steps 5-7" → I'll set up database

**I'll wait for your instruction on which step to begin! 🚀**

---

## Questions to Clarify Before Starting

1. **CMS API for Library Ingestion** (Critical for Phase 2):
   - **List all components endpoint**: `GET /api/components/list` ?
   - **Get component config**: `GET /api/components/{id}/config` ?
   - **Get component format**: `GET /api/components/{id}/format` ?
   - **Get component records**: `GET /api/components/{id}/records` ?
     - **Important**: Can we filter to get only ONE ACTIVE parent record + its children?
     - Parameters: `?active_only=true&limit_per_parent=1`
     - Or should we filter on our side after download?
   - **Get component screenshot**: `GET /api/components/{id}/screenshot` ?
   - Authentication method? (API Key, OAuth, JWT?)
   - Rate limits? (requests per minute)
   - Screenshot format? (PNG, JPG, dimensions, file size?)
   - Total number of components in library? (approximate)
   - Are components grouped by categories/tags?

2. **ControlId Types**:
   - Complete list of ControlId values and their meanings?
   - Any special handling for specific types?

3. **Figma API**:
   - How do you currently get Figma screenshots?
   - Any specific metadata available from Figma?

4. **Component Hierarchy**:
   - Maximum nesting depth you need?
   - Any rules for when to create child vs keep in parent?

5. **Handlebars Helpers**:
   - Full list of custom helpers (IfCond, IfCondObj, etc.)?
   - Any other templating syntax to support?

6. **Output Format**:
   - Do we need to support all device types (Desktop, Tablet, Mobile, AMP)?
   - Or start with Desktop only?

7. **Validation**:
   - Who will review generated components before adding to library?
   - Manual review step needed?

---

## Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Claude API accuracy varies | High | Iterative refinement, learn from library patterns |
| Handlebars syntax complex | High | Extensive examples in prompts, validation step |
| Component hierarchy ambiguous | Medium | Conservative approach, learn from library |
| Visual validation false positives | Medium | Multiple metrics, manual review option |
| ControlId assignment incorrect | Medium | Learn from library, Claude AI context |
| Library matching too strict/loose | Medium | Tunable thresholds, A/B testing |

---

**This plan is designed to create a production-ready system in 8 weeks that generates valid MiBlock CMS components from Figma designs, either by matching existing library components or creating new ones with proper structure, definitions, and Handlebars templates.**

