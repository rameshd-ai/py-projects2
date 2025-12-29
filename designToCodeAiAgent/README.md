# Figma to MiBlock CMS Component Generator

AI-powered system that generates MiBlock CMS components from Figma designs.

## Overview

This application uses Claude AI and visual embeddings to:
1. Take Figma URL input (page or specific section)
2. Automatically fetch screenshots and metadata via Figma API
3. Search existing component library for matches (using CLIP embeddings + pgvector)
4. If no match: Generate HTML → Extract structure → Create CMS definitions
5. Output: MiBlock ComponentConfig.json, ComponentFormat.json, ComponentRecords.json

## Features

- 🌐 **Browser-Based UI** - No CLI usage for end users
- 🔗 **Figma URL Input** - Paste URL, system extracts sections automatically
- 🎯 **Multi-Section Processing** - Process entire pages or individual sections
- 🔄 **On-Demand Library Training** - Refresh button to retrain library anytime
- 📊 **Real-Time Progress** - WebSocket updates for live progress tracking
- 🧠 **Visual Similarity Matching** - CLIP embeddings with pgvector
- 🤖 **Multi-Agent Architecture** - 7 specialized AI agents
- ⚡ **Simple Flask Backend** - Easy to understand and maintain

## Quick Start

### Phase 0: Prerequisites (First Time Only)

Before starting, complete the environment setup. **See detailed guide:** [docs/phases/PHASE_0_PREREQUISITES.md](docs/phases/PHASE_0_PREREQUISITES.md)

**Quick Summary:**

1. **Install PostgreSQL 18+**
   - Download from https://www.postgresql.org/download/windows/
   - Set password: `Google@1`

2. **Create Database**
   ```bash
   python scripts/create_database.py --force
   ```

3. **Create .env File**
   ```bash
   python scripts/create_env.py
   ```

4. **Create Virtual Environment**
   ```bash
   python -m venv venv
   ```

5. **Activate Virtual Environment**
   ```bash
   # PowerShell
   .\venv\Scripts\Activate.ps1
   
   # Or CMD
   venv\Scripts\activate.bat
   ```

6. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

7. **Verify Setup**
   ```bash
   python scripts/check_database.py
   ```

✅ **Phase 0 complete!** You only need to do this once.

### Run the Application

After Phase 0 is complete, just:

```bash
# 1. Activate virtual environment (if not already active)
.\venv\Scripts\Activate.ps1

# 2. Run the server
python src/main.py
```

Server will start at `http://localhost:8000`  
**That's it! Much simpler than FastAPI!**

### First-Time Setup: Train Library

Before generating components, you need to download and train the component library:

**Option 1: Browser (Recommended)**
1. Open `http://localhost:8000/app`
2. Click "🔄 Refresh Library" button
3. Choose "Full Refresh"
4. Wait for completion (~10-15 minutes for 150 components)

**Option 2: CLI (For setup only)**
```bash
# Full refresh - download all components
python scripts/ingest_library.py --full

# Or incremental - only new/updated
python scripts/ingest_library.py --incremental
```

## Usage

### Generate Component from Figma

1. Open browser: `http://localhost:8000/app`
2. Paste Figma URL:
   - Page URL: `https://figma.com/file/ABC123/Design` (processes all sections)
   - Node URL: `https://figma.com/file/ABC123?node-id=123:456` (single section)
3. Click "Fetch from Figma"
4. Select sections to process
5. Click "Process Selected Sections"
6. Download results (Config, Format, Records JSON files)

### Refresh Library

When you have new CMS components:
1. Click "🔄 Refresh Library" button
2. Choose refresh type:
   - **Incremental**: Only new/updated components (faster)
   - **Full**: Re-download everything (slower, more thorough)
3. Watch real-time progress
4. Library is updated!

## Architecture

### Multi-Agent System

7 Specialized AI Agents:
1. **Library Ingestion Agent** - Downloads and indexes library components
2. **Library Matcher Agent** - Finds similar components using visual embeddings
3. **HTML Generator Agent** - Generates HTML from screenshots using Claude
4. **Visual Validator Agent** - Validates HTML matches screenshot
5. **Structure Analyzer Agent** - Analyzes HTML structure and hierarchy
6. **Definition Extractor Agent** - Maps HTML to CMS definitions
7. **Template Generator Agent** - Creates Handlebars templates

### Tech Stack

**Backend:**
- Flask - Simple web framework
- PostgreSQL + pgvector - Database with vector similarity search
- In-Memory Cache - Simple caching (no Redis needed)
- LangGraph - Agent orchestration
- Anthropic Claude 3.5 Sonnet - AI generation
- CLIP - Visual embeddings

**Frontend:**
- HTML/CSS/JavaScript (or React/Vue - TBD in Phase 9)

**APIs:**
- Figma API - Design extraction
- CMS API - Component library
- Anthropic API - AI generation

## Project Structure

```
designToCodeAiAgent/
├── src/
│   ├── api/              # API clients (Figma, CMS, Claude)
│   ├── agents/           # AI agents
│   ├── models/           # Database models
│   ├── config/           # Configuration
│   ├── utils/            # Utilities (cache, logging)
│   └── main.py           # FastAPI application
├── frontend/             # Web UI
├── scripts/              # Setup and utility scripts
├── tests/                # Unit tests
├── mi-block-ID-560183/   # Sample component data
├── requirements.txt      # Python dependencies
├── env.example           # Environment variables template
└── FINAL_DEVELOPMENT_PLAN.md  # Detailed development plan

```

## API Endpoints

### Component Generation
- `POST /api/generate/from-url` - Generate from Figma URL
- `GET /api/generate/task/{task_id}` - Get generation status

### Library Management
- `GET /api/library/status` - Get library statistics
- `POST /api/library/refresh` - Trigger library refresh
- `GET /api/library/refresh/{task_id}` - Get refresh progress

### WebSocket
- `WS /ws/task/{task_id}` - Real-time task updates

## Development

### Run in Development Mode
```bash
# Flask auto-reloads by default in debug mode
python src/main.py
```

### Run Tests
```bash
pytest tests/
```

### Code Quality
```bash
# Format code
black src/

# Lint
flake8 src/

# Type checking
mypy src/
```

## Configuration

Key environment variables in `.env`:

```bash
# Figma
FIGMA_API_TOKEN=your_token_here

# CMS
CMS_API_BASE_URL=https://your-cms.com/api
CMS_API_KEY=your_key
CMS_API_SECRET=your_secret

# Anthropic Claude
ANTHROPIC_API_KEY=your_api_key
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022

# Database
DATABASE_URL=postgresql://user:pass@localhost/miblock_components

# Thresholds
IMAGE_SIMILARITY_THRESHOLD=0.85
CLIP_SIMILARITY_THRESHOLD=0.90
```

## Troubleshooting

### Library refresh fails
- Check CMS API credentials in `.env`
- Verify CMS API is accessible
- Check logs: `tail -f logs/app.log`

### Figma API errors
- Verify Figma API token in `.env`
- Check rate limits (60 req/min)
- Ensure Figma file is accessible

### Database connection errors
- Verify PostgreSQL is running
- Check DATABASE_URL in `.env`
- Ensure pgvector extension is installed

## Documentation

### Main Documentation
- **README.md** (this file) - Quick start and overview
- **FINAL_DEVELOPMENT_PLAN.md** - Complete 122-step implementation plan
- **docs/PROJECT_STATUS.md** - Current progress and status
- **docs/WHY_FLASK.md** - Why we chose Flask over FastAPI (simplicity!)
- **docs/SIMPLIFIED_CHANGES.md** - Recent simplification changes
- **mi-block-ID-560183/** - Sample MiBlock component structure

### Phase-by-Phase Documentation
Detailed documentation for each implementation phase in `docs/phases/`:

- **[docs/phases/README.md](docs/phases/README.md)** - Phase documentation index
- **[Phase 0: Prerequisites](docs/phases/PHASE_0_PREREQUISITES.md)** - ✅ COMPLETED
  - PostgreSQL installation
  - Database setup
  - Virtual environment creation
  - Dependency installation
  - Environment configuration
- **[Phase 1: Foundation](docs/phases/PHASE_1_FOUNDATION.md)** - ⏳ IN PROGRESS
  - Flask application setup
  - API client implementation
  - Database models
  - Agent architecture
  - WebSocket integration
- **[Phase 2: Library Ingestion](docs/phases/PHASE_2_LIBRARY_INGESTION.md)** - ⏳ PENDING
- **[Phase 3: HTML Generation](docs/phases/PHASE_3_HTML_GENERATION.md)** - ⏳ PENDING
- **[Phase 4: Structure Analysis](docs/phases/PHASE_4_STRUCTURE_ANALYSIS.md)** - ⏳ PENDING
- **[Phase 5: Definition Extraction](docs/phases/PHASE_5_DEFINITION_EXTRACTION.md)** - ⏳ PENDING
- **[Phase 6: Template Generation](docs/phases/PHASE_6_TEMPLATE_GENERATION.md)** - ⏳ PENDING
- **[Phase 7: Orchestration + UI](docs/phases/PHASE_7_ORCHESTRATION_UI.md)** - ⏳ PENDING
- **[Phase 8: Testing & Deployment](docs/phases/PHASE_8_TESTING_DEPLOYMENT.md)** - ⏳ PENDING

Each phase document includes:
- Step-by-step breakdown
- Files to create with descriptions
- Code examples and usage
- Completion criteria

## License

[Your License]

## Support

[Your support contact information]

