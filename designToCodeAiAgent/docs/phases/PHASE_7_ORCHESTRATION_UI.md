# PHASE 7: Orchestration + Figma Integration + Web UI

**Duration**: Week 7  
**Steps**: 78-105  
**Status**: ⏳ PENDING  
**Checkpoint**: Backend + Figma + Frontend + Training UI working

---

## 📋 Overview

Phase 7 brings everything together:
- Implement Library Matcher Agent (Agent 1.5)
- Orchestrate all agents in complete workflow
- Integrate Figma URL processing
- Build web-based user interface
- Implement library refresh UI
- Enable WebSocket real-time updates

---

## 🎯 Key Deliverables

### Library Matcher Agent (Agent 1.5)

**Purpose**: Search existing components using visual similarity

**Process**:
1. Generate CLIP embedding for input screenshot
2. Query pgvector for similar components
3. Return top matches with similarity scores
4. If match found (score > 0.85), skip generation

### Complete Workflow Orchestration

**Two Paths**:

**Path A: Match Found**
1. Figma URL → Extract sections
2. Library Matcher → Find similar component
3. Return existing component (Config, Format, Records)

**Path B: No Match (Generate New)**
1. Figma URL → Extract sections
2. HTML Generator → Generate HTML
3. Visual Validator → Validate HTML
4. Structure Analyzer → Analyze hierarchy
5. Definition Extractor → Create definitions
6. Template Generator → Create Handlebars
7. Output Formatter → Generate 3 JSON files

### Figma Integration
- URL parsing and validation
- Section detection (page vs node)
- Batch processing for multiple sections
- Progress tracking per section

### Web UI (Browser-Based)

**Features**:
- Figma URL input field
- Section detection and preview
- Section selection (checkboxes)
- Real-time progress tracking
- Results display with download buttons
- Library status display
- **Library Refresh Button** with progress modal

**Pages**:
1. **Main Page** - Component generation
2. **Library Status** - Show stats
3. **History** - Recent conversions

---

## 📦 Files to Create

### Agents
- `src/agents/library_matcher_agent.py` - Agent 1.5
- `src/agents/workflow_orchestrator.py` - Main orchestrator

### Backend Updates
- `src/api/routes/generation.py` - Generation endpoints (refactored)
- `src/api/routes/library.py` - Library endpoints (refactored)
- `src/api/websocket/task_updates.py` - WebSocket handlers

### Frontend
- `frontend/index.html` - Main page
- `frontend/css/styles.css` - Styles
- `frontend/js/app.js` - Main application logic
- `frontend/js/figma.js` - Figma URL processing
- `frontend/js/library.js` - Library refresh UI
- `frontend/js/websocket.js` - WebSocket client

### Tests
- `tests/test_library_matcher.py`
- `tests/test_workflow_orchestrator.py`
- `tests/integration/test_complete_workflow.py`

---

**Status**: ⏳ PENDING  
**Next**: Phase 8 - Testing & Deployment


