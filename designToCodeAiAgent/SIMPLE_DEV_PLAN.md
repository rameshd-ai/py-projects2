# SIMPLE DEVELOPMENT PLAN
## Figma to CMS Component Generator

> **🎯 Goal**: Build a simple Flask app with LangGraph that converts Figma designs to CMS components  
> **📦 Tech Stack**: Flask + LangGraph + PostgreSQL + pgvector + Claude AI  
> **⏱️ Timeline**: 3-4 weeks (much simpler than original plan)

---

## 🎯 Core Workflow (Simplified)

```
1. User enters Figma URL in browser
2. System downloads screenshot from Figma API
3. LangGraph orchestrates agents:
   a. Check if similar component exists (simple matching)
   b. If match → return existing component
   c. If no match → generate new component
4. Return 3 JSON files (Config, Format, Records)
```

---

## 📁 Simple Project Structure

```
designToCodeAiAgent/
├── app.py                 # Flask app (single file to start)
├── agents/
│   ├── __init__.py
│   ├── graph.py          # LangGraph workflow
│   └── nodes.py           # Agent functions
├── api/
│   ├── __init__.py
│   ├── figma.py           # Figma API client
│   ├── cms.py             # CMS API client
│   └── claude.py          # Claude AI client
├── models/
│   ├── __init__.py
│   └── db.py              # PostgreSQL + pgvector models
├── utils/
│   ├── __init__.py
│   ├── matching.py        # Simple visual matching
│   └── generator.py       # JSON generation
├── templates/
│   └── index.html         # Single page UI
├── static/
│   └── style.css          # Basic styling
├── .env                   # Environment variables
├── requirements.txt       # Dependencies
└── README.md
```

---

## 🚀 Implementation Phases (4 Phases Only)

### **Phase 1: Basic Flask App + API Clients** (Week 1)
**Goal**: Get Flask running with API clients

**Steps:**
1. ✅ Create Flask app (`app.py`)
2. ✅ Create basic HTML page (`templates/index.html`)
3. ✅ Figma API client (`api/figma.py`) - get screenshot from URL
4. ✅ CMS API client (`api/cms.py`) - download components
5. ✅ Claude API client (`api/claude.py`) - generate HTML
6. ✅ Test all APIs work

**Files:**
- `app.py` - Flask routes
- `templates/index.html` - UI
- `api/figma.py` - Figma integration
- `api/cms.py` - CMS integration
- `api/claude.py` - Claude integration

---

### **Phase 2: LangGraph Workflow** (Week 2)
**Goal**: Build agent workflow with LangGraph

**Steps:**
1. ✅ Create LangGraph workflow (`agents/graph.py`)
2. ✅ Create agent nodes (`agents/nodes.py`):
   - `match_component` - Check if similar exists
   - `generate_html` - Use Claude to create HTML
   - `extract_structure` - Parse HTML to find elements
   - `create_definitions` - Convert to CMS format
   - `generate_json` - Create 3 JSON files
3. ✅ Connect nodes in graph
4. ✅ Test workflow end-to-end

**Files:**
- `agents/graph.py` - LangGraph StateGraph
- `agents/nodes.py` - All agent functions

**Simple Graph Flow:**
```
START
  ↓
Match Component? (vector search in PostgreSQL + pgvector)
  ↓
  ├─ Match Found → Return Existing
  └─ No Match → Generate HTML
                ↓
            Extract Structure
                ↓
            Create Definitions
                ↓
            Generate JSON Files
                ↓
            END
```

---

### **Phase 3: Component Matching** (Week 3)
**Goal**: Simple matching system

**Steps:**
1. ✅ Create database table for components
2. ✅ Store component screenshots + metadata
3. ✅ Simple matching function:
   - Compare screenshot hashes (perceptual hash)
   - Compare component names/descriptions
   - Return best match if similarity > 70%
4. ✅ Add "Refresh Library" button to UI
5. ✅ Download all components from CMS API
6. ✅ Store in database

**Files:**
- `models/db.py` - PostgreSQL + pgvector models
- `utils/matching.py` - Vector similarity matching with pgvector
- Update `app.py` - Add library refresh route

**Vector Matching:**
- Generate CLIP embedding for input screenshot
- Query PostgreSQL with pgvector for similar components (cosine similarity)
- Use pgvector's `<=>` operator for fast similarity search
- Return best match if similarity > 0.85
- Production-ready vector search!

---

### **Phase 4: JSON Generation & Polish** (Week 4)
**Goal**: Generate correct CMS JSON format

**Steps:**
1. ✅ Parse HTML structure (find headings, images, text)
2. ✅ Create ComponentConfig.json structure
3. ✅ Create ComponentFormat.json with Handlebars
4. ✅ Create ComponentRecords.json with definitions
5. ✅ Test with sample Figma URL
6. ✅ Add download buttons in UI
7. ✅ Add progress indicators
8. ✅ Final testing

**Files:**
- `utils/generator.py` - JSON generation
- Update `agents/nodes.py` - Use generator
- Update `templates/index.html` - Add download UI

---

## 📋 Detailed Steps (40 Steps Total)

### **Phase 1: Basic Flask App (Steps 1-10)**

**Step 1**: Create Flask app structure
- Create `app.py` with basic route
- Create `templates/` and `static/` folders

**Step 2**: Create HTML page
- Simple form with Figma URL input
- Submit button
- Results area

**Step 3**: Figma API client
- Parse Figma URL (extract file_id, node_id)
- Get screenshot from Figma API
- Save screenshot locally

**Step 4**: CMS API client
- Download component list
- Download component JSON files (Config, Format, Records)
- Download component screenshots

**Step 5**: Claude API client
- Send screenshot to Claude
- Get HTML response
- Handle errors

**Step 6**: Test Figma API
- Test with sample URL
- Verify screenshot downloads

**Step 7**: Test CMS API
- Test component download
- Verify JSON files received

**Step 8**: Test Claude API
- Test HTML generation
- Verify HTML output

**Step 9**: Connect Flask to APIs
- Create `/api/generate` route
- Call Figma → Claude → return HTML

**Step 10**: Test end-to-end
- Enter Figma URL in browser
- Verify HTML is generated

---

### **Phase 2: LangGraph Workflow (Steps 11-20)**

**Step 11**: Install LangGraph
- Add to requirements.txt
- Install package

**Step 12**: Define State
- Create State class with:
  - figma_url
  - screenshot_path
  - html_content
  - matched_component_id
  - component_config
  - component_format
  - component_records

**Step 13**: Create match_component node
- Check database for similar components
- Return match if found

**Step 14**: Create generate_html node
- Call Claude API
- Save HTML to state

**Step 15**: Create extract_structure node
- Parse HTML with BeautifulSoup
- Find headings, images, text blocks
- Store structure in state

**Step 16**: Create create_definitions node
- Convert HTML structure to CMS definitions
- Map elements to ControlId (1=Text, 7=Image, etc.)

**Step 17**: Create generate_json node
- Create ComponentConfig.json
- Create ComponentFormat.json
- Create ComponentRecords.json

**Step 18**: Build LangGraph
- Create StateGraph
- Add all nodes
- Define edges (conditional routing)

**Step 19**: Connect Flask to LangGraph
- Call graph from Flask route
- Return results

**Step 20**: Test workflow
- Test with Figma URL
- Verify all nodes execute

---

### **Phase 3: Component Matching (Steps 21-30)**

**Step 21**: Create database schema
- Use existing PostgreSQL database (from Phase 0)
- Create `components` table with `vector(512)` column for embeddings
- Store component metadata and JSON files
- pgvector extension already installed!

**Step 22**: Create database models
- Create SQLAlchemy models for components table
- Use pgvector for embedding column (`vector(512)`)
- Store: component_id, name, embedding, config_json, format_json, records_json

**Step 23**: Vector matching function
- Generate CLIP embedding for input screenshot
- Query PostgreSQL with pgvector for similar components (cosine similarity)
- Use SQL: `ORDER BY embedding <=> %s LIMIT 5`
- Return best match with similarity score

**Step 24**: Add matching to graph
- Update match_component node
- Use matching function

**Step 25**: Create library refresh route
- `/api/refresh-library` endpoint
- Download all components from CMS

**Step 26**: Download components
- Call CMS API
- Download Config, Format, Records
- Download screenshots

**Step 27**: Store in database
- Generate CLIP embedding for each component screenshot
- Store embedding in PostgreSQL (pgvector column)
- Store metadata and JSON files in database
- Save screenshots locally

**Step 28**: Add refresh button to UI
- Button in HTML
- Call refresh route
- Show progress

**Step 29**: Test matching
- Refresh library
- Test with similar design
- Verify match found

**Step 30**: Test no-match case
- Test with new design
- Verify generation path works

---

### **Phase 4: JSON Generation & Polish (Steps 31-40)**

**Step 31**: Parse HTML structure
- Use BeautifulSoup
- Find all headings (h1, h2, h3)
- Find all images
- Find all text blocks

**Step 32**: Create ComponentConfig structure
- Parent component
- Child components (if nested)
- Definitions array

**Step 33**: Map elements to ControlId
- Text → ControlId: 1
- Image → ControlId: 7
- Yes/No → ControlId: 8
- etc.

**Step 34**: Create ComponentFormat
- Generate Handlebars template
- Replace content with {{data.xxx}}
- Handle loops with {{#each}}

**Step 35**: Create ComponentRecords
- Parent record
- Child records (if nested)
- Only active records

**Step 36**: Test JSON generation
- Generate from sample HTML
- Verify format matches CMS standard

**Step 37**: Add download buttons
- Download Config button
- Download Format button
- Download Records button

**Step 38**: Add progress indicators
- Show "Processing..." message
- Show progress steps
- Use WebSockets or polling

**Step 39**: Final testing
- Test with real Figma URLs
- Test matching
- Test generation
- Verify JSON files

**Step 40**: Documentation
- Update README
- Add usage instructions
- Add API documentation

---

## 🛠️ Technology Choices (Simplified)

### **Web Framework**
- **Flask** (not FastAPI) - simpler, easier to understand
- Single `app.py` file to start
- Add routes as needed

### **Agent Orchestration**
- **LangGraph** - visual workflow, easy to debug
- Simple StateGraph with conditional edges
- Each agent = one function

### **Database**
- **PostgreSQL + pgvector** - Production-ready vector database
- Stores component embeddings in `vector(512)` columns
- Fast similarity search with cosine distance
- Perfect for visual component matching
- Already set up in Phase 0!

### **AI/ML**
- **Claude AI** - for HTML generation
- **Simple image hashing** - for matching (no CLIP for now)
- Can add CLIP later if needed

### **Frontend**
- **Plain HTML/CSS/JavaScript** (no React/Vue)
- Single page application
- Simple form + results display

---

## 📦 Dependencies (Simplified)

```txt
# Web Framework
flask==3.0.0
flask-cors==4.0.0

# Agent Orchestration
langgraph==0.0.20
langchain==0.1.0
langchain-anthropic==0.1.0

# Database
psycopg2-binary==2.9.9
pgvector==0.2.4
sqlalchemy==2.0.25

# AI
anthropic==0.18.0

# CLIP for embeddings (for vector search)
torch==2.2.2
torchvision==0.17.2
transformers==4.36.2
clip-by-openai==1.0

# Utilities
requests==2.31.0
beautifulsoup4==4.12.2
pillow==10.2.0
imagehash==4.3.1  # For simple image matching
python-dotenv==1.0.0
```

**Total: ~17 packages** (vs 60+ in original plan)

**Note**: PostgreSQL + pgvector is already set up from Phase 0! Includes CLIP for visual embeddings.

---

## 🎯 Key Simplifications

### **1. PostgreSQL + pgvector**
- Use PostgreSQL with pgvector extension for vector search
- Generate CLIP embeddings for visual matching
- Production-ready vector similarity search
- Already set up in Phase 0!

### **2. Single Flask File to Start**
- All routes in `app.py`
- Split later if needed
- Easier to understand

### **3. Vector Matching with pgvector**
- CLIP embeddings for visual similarity
- PostgreSQL + pgvector for fast similarity search
- Use `<=>` operator for cosine similarity
- 85% similarity threshold (adjustable)
- Production-ready and scalable

### **4. No Redis Cache**
- Use in-memory cache (Python dict)
- Simple TTL-based expiration
- Can add Redis later

### **5. Plain HTML Frontend**
- No React/Vue/Angular
- Simple JavaScript
- Easy to modify

### **6. Fewer Agents**
- 5 agents instead of 7
- Simpler workflow
- Easier to debug

### **7. PostgreSQL + pgvector**
- **Production-ready** - PostgreSQL is battle-tested
- **Fast vector search** - pgvector extension optimized for similarity
- **Already set up** - from Phase 0 prerequisites
- **Scalable** - handles millions of vectors
- **Perfect for component matching** - stores embeddings + metadata in one place

---

## 📊 Comparison: Original vs Simple

| Feature | Original Plan | Simple Plan |
|---------|--------------|-------------|
| **Phases** | 8 phases | 4 phases |
| **Steps** | 122 steps | 40 steps |
| **Dependencies** | 60+ packages | ~15 packages |
| **Agents** | 7 agents | 5 agents |
| **Database** | PostgreSQL + pgvector | PostgreSQL + pgvector |
| **Vector Search** | pgvector + CLIP | pgvector + CLIP |
| **Frontend** | React/Vue | Plain HTML |
| **Cache** | Redis | In-memory |
| **Timeline** | 8 weeks | 3-4 weeks |

---

## 🚀 Getting Started

### **Prerequisites (Already Done in Phase 0!)**
- ✅ PostgreSQL installed (from Phase 0)
- ✅ Database created (`miblock_components`)
- ✅ pgvector extension installed
- ✅ Virtual environment set up
- ✅ Install dependencies: `pip install -r requirements.txt`

### **Start Phase 1**
1. Create `app.py` with Flask
2. Create basic HTML page
3. Test Flask runs: `python app.py`
4. Start building API clients

---

## 📝 Notes

- **This is a simplified plan** - focus on core functionality first
- **Can add complexity later** - CLIP, Redis, React, etc.
- **Iterative approach** - build, test, improve
- **Each phase is independent** - can test as you go

---

## ✅ Success Criteria

**Phase 1 Complete When:**
- Flask app runs
- Can enter Figma URL
- APIs return data

**Phase 2 Complete When:**
- LangGraph workflow runs
- All nodes execute
- Returns HTML

**Phase 3 Complete When:**
- Can refresh library
- Matching works
- Finds similar components

**Phase 4 Complete When:**
- Generates correct JSON
- Can download files
- Works end-to-end

---

## 🎯 Next Steps

1. **Review this plan** - make sure it makes sense
2. **Start Phase 1** - create Flask app
3. **Build incrementally** - test each step
4. **Ask questions** - if anything unclear

**Ready to start?** Just say "start Phase 1" and we'll begin! 🚀

