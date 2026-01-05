# DEVELOPMENT PLAN
## Figma to CMS Component Generator

> **🎯 Goal**: Build a Flask app with LangGraph that converts Figma designs to CMS components using pre-trained component library  
> **📦 Tech Stack**: Flask + LangGraph + PostgreSQL + pgvector + Claude AI  
> **⏱️ Timeline**: 4-5 weeks

---

## 🎯 Core Workflow (Updated)

```
PHASE 1: Training Data Preparation (Separate Heavy Module)
1. User clicks "Train Components" button
2. User enters site details (Target Site URL, Profile Alias, Site ID)
3. System exports ALL data for that site from CMS API
4. System prepares training dataset (huge data, time-consuming)
5. System generates vector embeddings for all components
6. System stores training data + embeddings in PostgreSQL + pgvector

PHASE 2: Component Generation
1. User creates project OR adds component to existing project
2. User enters Figma URL
3. System checks if Figma design has multiple sections or single section
4. If multiple sections: Loop through each section one by one
5. If single section: Proceed to next step
6. For each section:
   a. Check training library for good matches (vector similarity)
   b. If good match found → Use same structure from library
   c. If no match → Generate new HTML/JSON based on training data + prompts
7. Generate ComponentConfig.json, ComponentFormat.json, ComponentRecords.json
8. Add components to CMS using site details from project
9. Update project with new components
```

---

## 🔄 Agentic Flow Diagram (LangGraph Workflow)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         COMPONENT GENERATION WORKFLOW                     │
│                           (LangGraph StateGraph)                         │
└─────────────────────────────────────────────────────────────────────────┘

START
  │
  ▼
┌─────────────────────────────────┐
│  1. DETECT SECTIONS             │
│  ─────────────────────────────  │
│  • Parse Figma URL              │
│  • Analyze file structure        │
│  • Detect single/multiple       │
│    sections                      │
│  • Store sections in state      │
└─────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────┐
│  2. CHECK LIBRARY MATCH         │
│  ─────────────────────────────  │
│  • Generate CLIP embedding      │
│    for screenshot               │
│  • Vector search in PostgreSQL  │
│    (pgvector similarity)       │
│  • Find best matches            │
│  • Calculate similarity scores   │
└─────────────────────────────────┘
  │
  ▼
  ┌───────────────────────────────┐
  │   DECISION: Match Found?       │
  │   (Similarity ≥ 85%)          │
  └───────────────────────────────┘
  │                    │
  │ YES                │ NO
  │                    │
  ▼                    ▼
┌─────────────┐    ┌─────────────────────────────────┐
│ USE MATCH   │    │  3. GENERATE HTML               │
│ (Skip HTML) │    │  ─────────────────────────────  │
│             │    │  • Use Claude AI                 │
│             │    │  • Generate HTML from screenshot │
│             │    │  • Use training data context     │
│             │    │  • Store HTML in state           │
└─────────────┘    └─────────────────────────────────┘
  │                    │
  └────────┬───────────┘
           │
           ▼
┌─────────────────────────────────┐
│  4. EXTRACT STRUCTURE           │
│  ─────────────────────────────  │
│  IF MATCHED:                     │
│    • Use matched component      │
│      structure (Config/Format/  │
│      Records JSON)               │
│  IF GENERATED:                   │
│    • Parse HTML with BeautifulSoup│
│    • Extract headings, images,   │
│      text blocks                 │
│    • Store structure in state   │
└─────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────┐
│  5. CREATE DEFINITIONS          │
│  ─────────────────────────────  │
│  IF MATCHED:                     │
│    • Use existing definitions   │
│  IF GENERATED:                   │
│    • Map elements to ControlId   │
│      (1=Text, 7=Image, etc.)    │
│    • Create CMS definitions     │
│    • Store in state             │
└─────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────┐
│  6. GENERATE JSON               │
│  ─────────────────────────────  │
│  • ComponentConfig.json          │
│  • ComponentFormat.json          │
│    (Handlebars template)        │
│  • ComponentRecords.json         │
│  • Store all JSON in state       │
└─────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────┐
│  7. ADD TO CMS                  │
│  ─────────────────────────────  │
│  • Use CMS API client           │
│  • Add component using site      │
│    details from project         │
│  • Store CMS component ID       │
└─────────────────────────────────┘
  │
  ▼
┌─────────────────────────────────┐
│  8. UPDATE PROJECT              │
│  ─────────────────────────────  │
│  • Update project JSON file      │
│  • Link components to training   │
│    data if matched              │
│  • Store component metadata      │
└─────────────────────────────────┘
  │
  ▼
  ┌───────────────────────────────┐
  │   MORE SECTIONS?              │
  │   (has_multiple_sections)     │
  └───────────────────────────────┘
  │                    │
  │ YES                │ NO
  │                    │
  │                    ▼
  │              ┌──────────┐
  │              │   END    │
  │              └──────────┘
  │
  ▼
  (Loop back to step 2)
  • Increment current_section_index
  • Process next section
  • Repeat workflow for each section


┌─────────────────────────────────────────────────────────────────────────┐
│                         STATE STRUCTURE                                  │
└─────────────────────────────────────────────────────────────────────────┘

ComponentGenerationState {
  // Project Info
  project_id: str
  project_name: str
  site_details: {
    target_site_url: str
    profile_alias: str
    site_id: str
  }
  
  // Figma Info
  figma_url: str
  figma_file_id: str
  figma_node_id: str
  
  // Section Info
  has_multiple_sections: bool
  sections: [{
    id: str
    name: str
    ...
  }]
  current_section_index: int
  
  // Screenshots (one per section)
  screenshot_paths: [str]
  
  // Library Matching
  matched_components: [{
    component_id: str
    name: str
    similarity: float
    config_json: {...}
    format_json: {...}
    records_json: {...}
  }]
  match_similarity_scores: [float]
  
  // Generated Content (one per section)
  html_contents: [str]
  component_configs: [{...}]
  component_formats: [{...}]
  component_records: [{...}]
  
  // CMS Integration
  cms_component_ids: [str]
  
  // Status
  status: 'processing' | 'completed' | 'error'
  error: str | null
  current_step: str
}


┌─────────────────────────────────────────────────────────────────────────┐
│                    CONDITIONAL ROUTING LOGIC                              │
└─────────────────────────────────────────────────────────────────────────┘

1. should_use_match(state):
   • Check similarity score for current section
   • IF similarity ≥ 0.85 (85%):
     → Route to "use_match" (skip HTML generation)
   • ELSE:
     → Route to "generate_new" (generate HTML)

2. should_continue_sections(state):
   • Check if has_multiple_sections
   • Check current_section_index vs total sections
   • IF more sections remain:
     → Route to "next_section" (loop back)
   • ELSE:
     → Route to "finish" (END)


┌─────────────────────────────────────────────────────────────────────────┐
│                    KEY DECISION POINTS                                   │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ Decision Point 1: Match Found?                                          │
│ ────────────────────────────────────────────────────────────────────────│
│ Location: After check_library_match                                      │
│ Condition: match_similarity_scores[current_index] ≥ 0.85                │
│                                                                          │
│ TRUE  → Use matched component structure                                 │
│         • Skip HTML generation                                          │
│         • Use existing Config/Format/Records JSON                      │
│         • Faster processing                                              │
│                                                                          │
│ FALSE → Generate new component                                          │
│         • Generate HTML with Claude AI                                  │
│         • Extract structure from HTML                                   │
│         • Create new definitions                                        │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│ Decision Point 2: Multiple Sections?                                    │
│ ────────────────────────────────────────────────────────────────────────│
│ Location: After update_project                                           │
│ Condition: has_multiple_sections AND current_index < sections.length-1  │
│                                                                          │
│ TRUE  → Process next section                                            │
│         • Increment current_section_index                                │
│         • Loop back to check_library_match                              │
│         • Process each section independently                            │
│                                                                          │
│ FALSE → Finish workflow                                                  │
│         • All sections processed                                         │
│         • Return final state                                            │
│         • END                                                            │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 📁 Project Structure

```
finalDtoC/
├── app.py                 # Flask app with routes
├── agents/
│   ├── __init__.py
│   ├── graph.py          # LangGraph workflow for component generation
│   └── nodes.py           # Agent functions (section detection, matching, generation)
├── api/
│   ├── __init__.py
│   ├── figma.py           # Figma API client
│   ├── cms.py             # CMS API client
│   └── claude.py          # Claude AI client
├── models/
│   ├── __init__.py
│   └── db.py              # PostgreSQL + pgvector models
├── training/
│   ├── __init__.py
│   ├── data_preparation.py # Export and prepare training data
│   ├── embeddings.py      # Generate vector embeddings
│   └── storage.py         # Store training data in database
├── utils/
│   ├── __init__.py
│   ├── matching.py        # Vector similarity matching
│   └── generator.py       # JSON generation
├── templates/
│   └── index.html         # UI
├── static/
│   └── style.css          # Styling
├── .env                   # Environment variables
├── requirements.txt       # Dependencies
└── README.md
```

---

## 🚀 Implementation Phases (4 Phases)

### **Phase 1: Training Data Preparation Module** (Week 1-2)
**Goal**: Export all site data, prepare training dataset, generate vector embeddings

**Steps:**
1. ✅ Create Flask app (`app.py`)
2. ✅ Create basic HTML page (`templates/index.html`)
3. ✅ Figma API client (`api/figma.py`)
4. ✅ CMS API client (`api/cms.py`)
5. ✅ Claude API client (`api/claude.py`)
6. ✅ Training module structure (`training/` folder)
7. **Create training data preparation endpoint** (`/api/train-library`)
   - Accept site details (Target Site URL, Profile Alias, Site ID)
   - Export ALL components from CMS for that site
   - Process and structure training data
   - Generate vector embeddings for each component
   - Store in PostgreSQL + pgvector database
8. **Create database schema**
   - `trained_components` table with `vector(512)` column
   - Store: component_id, name, site_info, embedding, config_json, format_json, records_json, screenshot_path
9. **Implement vector embedding generation**
   - Use CLIP or similar model to generate embeddings from screenshots
   - Store embeddings in pgvector column
10. **Add progress tracking**
    - Show progress for large data exports
    - Background job processing
    - Status updates

**Files:**
- `app.py` - Flask routes (training endpoint)
- `training/data_preparation.py` - Export and structure training data
- `training/embeddings.py` - Generate vector embeddings
- `training/storage.py` - Store in database
- `models/db.py` - Database models

**Key Features:**
- Heavy, time-consuming process (can take hours for large sites)
- Background processing with status updates
- Stores complete component data + embeddings
- Site-specific training data

---

### **Phase 2: LangGraph Workflow for Component Generation** (Week 2-3)
**Goal**: Build agent workflow that checks library, generates components, adds to CMS

**Steps:**
1. **Install LangGraph**
   - Add to requirements.txt
   - Install package

2. **Define State**
   - Create State class with:
     - project_id
     - figma_url
     - site_details (target_site_url, profile_alias, site_id)
     - sections (array of sections if multiple)
     - current_section_index
     - screenshot_paths (array)
     - matched_components (array)
     - generated_components (array)
     - html_contents (array)
     - component_configs (array)
     - component_formats (array)
     - component_records (array)

3. **Create agent nodes** (`agents/nodes.py`):
   - `detect_sections` - Check if Figma design has multiple sections
   - `check_library_match` - Vector search in training library for good matches
   - `generate_html` - Use Claude to create HTML (if no match or for new structure)
   - `extract_structure` - Parse HTML to find elements
   - `create_definitions` - Convert to CMS format
   - `generate_json` - Create 3 JSON files (Config, Format, Records)
   - `add_to_cms` - Add component to CMS using site details
   - `update_project` - Update project with new components

4. **Build LangGraph** (`agents/graph.py`):
   - Create StateGraph
   - Add all nodes
   - Define conditional edges
   - Handle loop for multiple sections

5. **Connect Flask to LangGraph**
   - Call graph from `/api/generate` route
   - Pass project details and Figma URL
   - Return results

6. **Test workflow end-to-end**

**Files:**
- `agents/graph.py` - LangGraph StateGraph
- `agents/nodes.py` - All agent functions
- `utils/matching.py` - Vector similarity search
- `utils/generator.py` - JSON generation

**LangGraph Flow:**
```
START
  ↓
Detect Sections (single or multiple?)
  ↓
  ├─ Single Section → Check Library Match
  └─ Multiple Sections → Loop:
                          ↓
                    Check Library Match (for each section)
                          ↓
                    Generate HTML (if no match) OR Use Matched Structure
                          ↓
                    Extract Structure
                          ↓
                    Create Definitions
                          ↓
                    Generate JSON Files
                          ↓
                    Add to CMS
                          ↓
                    Update Project
                          ↓
                    Next Section (if more)
                          ↓
                    END
```

**Library Matching Logic:**
- Generate CLIP embedding for Figma screenshot
- Query PostgreSQL with pgvector: `ORDER BY embedding <=> %s LIMIT 5`
- If similarity > 0.85 (85%): Use matched component structure
- If similarity < 0.85: Generate new component based on training data + prompts

---

### **Phase 3: Vector Embeddings & Matching** (Week 3)
**Goal**: Optimize vector matching and improve accuracy

**Steps:**
1. **Optimize embedding generation**
   - Use CLIP model for visual embeddings
   - Cache embeddings for faster matching
   - Batch processing for multiple components

2. **Improve matching algorithm**
   - Fine-tune similarity threshold (85% default)
   - Add metadata matching (component type, structure)
   - Combine visual + structural similarity

3. **Add matching preview**
   - Show matched components in UI
   - Display similarity scores
   - Allow user to choose match or generate new

4. **Performance optimization**
   - Index embeddings in PostgreSQL
   - Optimize vector queries
   - Add caching layer

**Files:**
- `utils/matching.py` - Enhanced matching logic
- `training/embeddings.py` - Optimized embedding generation

---

### **Phase 4: CMS Integration & Polish** (Week 4-5)
**Goal**: Complete CMS integration, UI polish, testing

**Steps:**
1. **Complete CMS integration**
   - Add components to CMS using site details
   - Handle CMS API responses
   - Error handling and retries

2. **Update project management**
   - Store generated components in projects
   - Link components to training data
   - Track component status

3. **UI enhancements**
   - Show progress for training data preparation
   - Display matched components
   - Show generation progress
   - Download JSON files

4. **Error handling**
   - Handle CMS API errors
   - Handle Figma API errors
   - Handle matching failures
   - Graceful degradation

5. **Testing**
   - Test with real Figma URLs
   - Test with multiple sections
   - Test matching accuracy
   - Test CMS integration
   - Test end-to-end workflow

6. **Documentation**
   - Update README
   - Add usage instructions
   - Document API endpoints

**Files:**
- `api/cms.py` - Enhanced CMS integration
- `templates/index.html` - UI updates
- `app.py` - Error handling

---

## 📋 Detailed Implementation Steps

### **Phase 1: Training Data Preparation (Steps 1-15)**

**Step 1-6**: ✅ Already completed (Flask app, API clients, UI)

**Step 7**: Create training data preparation module
- Create `training/` folder
- `training/data_preparation.py` - Export all components from CMS
- `training/embeddings.py` - Generate vector embeddings
- `training/storage.py` - Store in database

**Step 8**: Create database schema
- Create `trained_components` table
- Add `vector(512)` column for embeddings (pgvector)
- Store: component_id, name, site_info (JSON), embedding, config_json, format_json, records_json, screenshot_path, created_at

**Step 9**: Implement CMS data export
- Call CMS API with site details
- Export ALL components for that site
- Download Config, Format, Records JSON files
- Download screenshots

**Step 10**: Structure training data
- Organize components by type
- Extract metadata
- Prepare for embedding generation

**Step 11**: Generate vector embeddings
- Use CLIP model to generate embeddings from screenshots
- Store embeddings in pgvector format
- Batch process for efficiency

**Step 12**: Store in database
- Insert components with embeddings
- Store JSON files and metadata
- Link to site information

**Step 13**: Add progress tracking
- Background job processing
- Status updates via WebSocket or polling
- Show progress percentage

**Step 14**: Add training endpoint
- `/api/train-library` route (already exists, enhance it)
- Accept site details
- Start background job
- Return job ID for status tracking

**Step 15**: Test training data preparation
- Test with sample site
- Verify data export
- Verify embeddings generation
- Verify database storage

---

### **Phase 2: LangGraph Workflow (Steps 16-30)**

**Step 16**: Install LangGraph
- Add to requirements.txt
- Install package

**Step 17**: Define State
- Create State class with all required fields
- Support for multiple sections
- Support for matched vs generated components

**Step 18**: Create `detect_sections` node
- Analyze Figma design structure
- Detect if single or multiple sections
- Extract section boundaries
- Store sections in state

**Step 19**: Create `check_library_match` node
- Generate embedding for Figma screenshot
- Query database with pgvector
- Find best matches (similarity > 85%)
- Store matches in state

**Step 20**: Create `generate_html` node
- Use Claude API with training data context
- Generate HTML based on Figma screenshot
- Use matched component structure if available
- Store HTML in state

**Step 21**: Create `extract_structure` node
- Parse HTML with BeautifulSoup
- Find headings, images, text blocks
- Extract component structure
- Store structure in state

**Step 22**: Create `create_definitions` node
- Convert HTML structure to CMS definitions
- Map elements to ControlId (1=Text, 7=Image, etc.)
- Create definitions array
- Store in state

**Step 23**: Create `generate_json` node
- Create ComponentConfig.json
- Create ComponentFormat.json (Handlebars template)
- Create ComponentRecords.json
- Store in state

**Step 24**: Create `add_to_cms` node
- Use CMS API client
- Add component using site details from project
- Handle API responses
- Store CMS component ID

**Step 25**: Create `update_project` node
- Update project with generated components
- Link to training data if matched
- Store component metadata

**Step 26**: Build LangGraph
- Create StateGraph
- Add all nodes
- Define edges with conditional routing
- Handle loop for multiple sections

**Step 27**: Connect Flask to LangGraph
- Update `/api/generate` route
- Call graph with project details
- Pass site details and Figma URL
- Return results

**Step 28**: Handle multiple sections
- Loop through sections
- Process each section independently
- Combine results at end

**Step 29**: Test single section workflow
- Test with single section Figma design
- Verify matching works
- Verify generation works
- Verify CMS integration

**Step 30**: Test multiple sections workflow
- Test with multiple sections Figma design
- Verify loop works
- Verify all sections processed
- Verify CMS integration for all

---

### **Phase 3: Vector Embeddings & Matching (Steps 31-35)**

**Step 31**: Optimize embedding generation
- Batch processing
- Caching
- Performance improvements

**Step 32**: Fine-tune matching algorithm
- Adjust similarity threshold
- Add metadata matching
- Combine visual + structural similarity

**Step 33**: Add matching preview UI
- Show matched components
- Display similarity scores
- Allow user selection

**Step 34**: Performance optimization
- Index embeddings
- Optimize queries
- Add caching

**Step 35**: Test matching accuracy
- Test with various designs
- Verify match quality
- Adjust thresholds

---

### **Phase 4: CMS Integration & Polish (Steps 36-40)**

**Step 36**: Complete CMS integration
- Handle all CMS API endpoints
- Error handling
- Retry logic

**Step 37**: Update project management
- Store components in projects
- Link to training data
- Track status

**Step 38**: UI enhancements
- Progress indicators
- Matching preview
- Download buttons
- Error messages

**Step 39**: Testing
- End-to-end testing
- Error scenarios
- Performance testing

**Step 40**: Documentation
- README updates
- API documentation
- Usage guide

---

## 🛠️ Technology Choices

### **Web Framework**
- **Flask** - Simple, flexible web framework

### **Agent Orchestration**
- **LangGraph** - Visual workflow, easy to debug
- StateGraph with conditional edges
- Loop support for multiple sections

### **Database**
- **PostgreSQL + pgvector** - Production-ready vector database
- Stores component embeddings in `vector(512)` columns
- Fast similarity search with cosine distance
- Perfect for visual component matching

### **AI/ML**
- **Claude AI** - For HTML generation
- **CLIP** - For visual embeddings (vector search)

### **Frontend**
- **Plain HTML/CSS/JavaScript** - Simple, no framework needed

---

## 📦 Dependencies

```txt
# Web Framework
flask>=3.0.0
flask-cors>=4.0.0

# Agent Orchestration
langgraph>=1.0.0
langchain>=1.0.0
langchain-anthropic>=1.0.0

# Database
psycopg2-binary>=2.9.9
pgvector>=0.4.0
sqlalchemy>=2.0.0

# AI
anthropic>=0.75.0

# CLIP for embeddings (for vector search) - Optional for Phase 3
# torch>=2.6.0
# torchvision>=0.21.0
# transformers>=4.57.3
# clip-by-openai>=1.0.1

# Utilities
requests>=2.31.0
beautifulsoup4>=4.12.2
pillow>=10.4.0
imagehash>=4.3.0  # For simple image matching
python-dotenv>=1.0.0
```

---

## 🎯 Key Features

### **1. Training Data Preparation (Separate Heavy Module)**
- Exports ALL components from CMS for a site
- Generates vector embeddings for all components
- Stores complete training dataset in database
- Time-consuming process (can take hours)
- Background processing with progress tracking

### **2. Multi-Section Support**
- Detects if Figma design has multiple sections
- Loops through each section independently
- Processes all sections in sequence
- Combines results at end

### **3. Library Matching Before Generation**
- Checks training library for good matches (vector similarity)
- If match found (similarity > 85%): Uses same structure
- If no match: Generates new component based on training data
- Reduces redundant generation

### **4. CMS Integration**
- Adds generated components to CMS
- Uses site details from project
- Handles API responses and errors
- Updates project with new components

---

## ✅ Success Criteria

**Phase 1 Complete When:**
- Training data preparation works
- Can export all components from CMS
- Vector embeddings generated and stored
- Database populated with training data

**Phase 2 Complete When:**
- LangGraph workflow runs
- Section detection works
- Library matching works
- Component generation works
- Multiple sections handled
- CMS integration works

**Phase 3 Complete When:**
- Matching accuracy > 85%
- Performance optimized
- Matching preview works

**Phase 4 Complete When:**
- End-to-end workflow works
- UI polished
- Error handling complete
- Documentation updated

---

## 🚀 Next Steps

1. **Enhance training module** - Complete Phase 1 training data preparation
2. **Build LangGraph workflow** - Implement Phase 2 agent nodes
3. **Test and iterate** - Test with real data, improve accuracy

**Ready to continue?** Let's start enhancing the training module! 🚀
