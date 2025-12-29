# PHASE 1: Foundation & Setup

**Duration**: Week 1  
**Steps**: 1-15  
**Status**: ✅ COMPLETED (December 29, 2025)  
**Checkpoint**: APIs + Database ready

---

## 📋 Overview

Phase 1 establishes the complete foundation for the Figma to MiBlock Component Generator. This includes:
- Project structure and dependencies
- API clients (Figma, CMS, Claude)
- Database setup with pgvector
- FastAPI application framework
- Base agent infrastructure
- Logging and caching systems

---

## 🎯 Steps Completed

### Step 1-2: Project Structure & Environment
**What**: Create project folders and Python environment setup

**Files Created**:
```
designToCodeAiAgent/
├── src/
│   ├── api/
│   ├── agents/
│   ├── models/
│   ├── config/
│   └── utils/
├── frontend/
├── scripts/
├── tests/
├── storage/
│   ├── uploads/
│   ├── screenshots/
│   ├── results/
│   └── temp/
└── logs/
```

**Purpose**: Organize code into logical modules following Python best practices

---

### Step 3: Dependencies
**What**: Install all required Python packages

**File Created**: `requirements.txt`

**Key Dependencies**:
- **Web Framework**: FastAPI 0.109.0, uvicorn 0.27.0
- **Database**: psycopg2-binary 2.9.9, pgvector 0.2.4, sqlalchemy 2.0.25
- **Redis**: redis 5.0.1
- **AI/ML**: anthropic 0.18.0, torch 2.1.2, transformers 4.36.2, clip-by-openai
- **Image Processing**: opencv-python 4.9.0.80, scikit-image 0.22.0, imagehash 4.3.1
- **Agent Orchestration**: langgraph 0.0.26, langchain 0.1.4
- **Utilities**: python-dotenv 1.0.0, pydantic 2.5.3, structlog 24.1.0

**Purpose**: Ensure all dependencies are tracked and reproducible

**Installation**:
```bash
pip install -r requirements.txt
```

---

### Step 4: Configuration System
**What**: Environment configuration and settings management

**Files Created**:
1. `env.example` - Template with all environment variables
2. `src/config/settings.py` - Pydantic settings class
3. `src/config/__init__.py` - Module exports

**Environment Variables**:
```bash
# FastAPI Server
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=True

# Database
DATABASE_URL=postgresql://user:pass@localhost/miblock_components

# Redis Cache
REDIS_HOST=localhost
REDIS_PORT=6379

# Figma API
FIGMA_API_TOKEN=your_token_here
FIGMA_API_BASE_URL=https://api.figma.com/v1

# CMS API
CMS_API_BASE_URL=https://your-cms.com/api
CMS_API_KEY=your_key
CMS_API_SECRET=your_secret

# Anthropic Claude
ANTHROPIC_API_KEY=your_key
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022

# Thresholds
IMAGE_SIMILARITY_THRESHOLD=0.85
CLIP_SIMILARITY_THRESHOLD=0.90
```

**Purpose**: Centralized configuration with validation and type safety

**Usage**:
```python
from src.config import settings

# Access any setting
api_key = settings.figma_api_token
db_url = settings.database_url
```

---

### Step 5-8: Database Setup (PostgreSQL + pgvector)
**What**: Database schema with vector similarity search support

**Files Created**:
1. `scripts/setup_database.sql` - Complete database schema
2. `src/models/database.py` - SQLAlchemy ORM models
3. `src/models/__init__.py` - Module exports

**Database Tables**:

#### 1. `components` Table
Stores library components with CLIP embeddings for visual similarity search.

**Columns**:
- `component_id` (SERIAL PRIMARY KEY) - Unique component ID
- `component_name` (VARCHAR) - Component name
- `component_type` (VARCHAR) - Type/category
- `description` (TEXT) - Description
- `config_json` (JSONB) - MiBlockComponentConfig.json content
- `format_json` (JSONB) - MiBlockComponentFormat.json content
- `records_json` (JSONB) - MiBlockComponentRecords.json content
- `screenshot_url` (VARCHAR) - Screenshot URL from CMS
- `screenshot_path` (VARCHAR) - Local screenshot file path
- `screenshot_hash` (VARCHAR) - Hash for duplicate detection
- `embedding` (VECTOR(512)) - CLIP visual embedding
- `created_at`, `updated_at`, `last_used_at` (TIMESTAMP) - Tracking
- `usage_count` (INTEGER) - How many times component was matched
- `is_active`, `is_verified` (BOOLEAN) - Status flags
- `source_component_id` (INTEGER) - Original CMS component ID
- `source_cms_url` (VARCHAR) - Source URL

**Indexes**:
- Primary key on `component_id`
- Index on `component_name`
- Index on `component_type`
- Index on `is_active`
- Index on `screenshot_hash`
- **pgvector IVFFlat index** on `embedding` for fast similarity search

**Purpose**: Store and search components using visual similarity

#### 2. `generation_tasks` Table
Tracks component generation requests from Figma URLs.

**Columns**:
- `task_id` (UUID PRIMARY KEY) - Unique task identifier
- `figma_url` (TEXT) - Input Figma URL
- `figma_file_id`, `figma_node_id` (VARCHAR) - Parsed URL components
- `section_name` (VARCHAR) - Section being processed
- `status` (VARCHAR) - pending, processing, completed, failed
- `progress` (INTEGER) - 0-100 percentage
- `current_step` (VARCHAR) - Current agent/step
- `matched_component_id` (INTEGER) - FK to components if match found
- `match_score` (FLOAT) - Similarity score
- `is_library_match` (BOOLEAN) - True if existing component matched
- `generated_config`, `generated_format`, `generated_records` (JSONB) - Results
- `input_screenshot_path`, `generated_screenshot_path` (VARCHAR) - Paths
- `similarity_score` (FLOAT) - Visual similarity score
- `agents_executed` (JSONB) - Array of agents run with timing
- Timestamps: `created_at`, `started_at`, `completed_at`
- `duration_seconds` (INTEGER) - Total execution time
- `error_message`, `error_details` (TEXT/JSONB) - Error info

**Indexes**:
- Primary key on `task_id`
- Index on `status`
- Index on `created_at`
- Index on `figma_url`

**Purpose**: Track progress and results of component generation

#### 3. `library_refresh_tasks` Table
Tracks library download and training operations.

**Columns**:
- `task_id` (UUID PRIMARY KEY) - Unique task identifier
- `refresh_type` (VARCHAR) - "full" or "incremental"
- `status` (VARCHAR) - pending, downloading, embedding, storing, completed, failed
- `total_components` (INTEGER) - Total to process
- `downloaded_components`, `processed_embeddings`, `stored_components` (INTEGER) - Progress
- `new_components_count`, `updated_components_count`, `failed_components_count` (INTEGER) - Results
- `current_component_name` (VARCHAR) - Currently processing
- `current_phase` (VARCHAR) - downloading, embedding, storing
- Timestamps: `created_at`, `started_at`, `completed_at`
- `duration_seconds`, `estimated_time_remaining` (INTEGER) - Timing
- `error_message`, `failed_component_ids` (TEXT/JSONB) - Error info
- `triggered_by` (VARCHAR) - system, user, schedule

**Indexes**:
- Primary key on `task_id`
- Index on `status`
- Index on `created_at`

**Purpose**: Track library refresh progress for UI updates

**Helper Functions**:
1. `search_similar_components(query_embedding, threshold, limit)` - Find similar components using pgvector
2. `increment_component_usage(component_id)` - Increment usage counter

**Views**:
1. `component_stats` - Library statistics (total, active, with embeddings, etc.)
2. `recent_generations` - Last 100 generation tasks

**Installation**:
```bash
# Create database
psql -U postgres -c "CREATE DATABASE miblock_components;"

# Run schema
psql -U postgres -d miblock_components -f scripts/setup_database.sql
```

**Purpose**: Provide persistent storage with fast vector similarity search

---

### Step 11: Figma API Client
**What**: Complete integration with Figma API for design extraction

**File Created**: `src/api/figma_client.py`

**Class**: `FigmaClient`

**Key Methods**:
1. `parse_figma_url(url)` - Extract file_id and node_id from Figma URL
2. `get_file(file_id)` - Get complete file structure
3. `get_node(file_id, node_id)` - Get specific node data
4. `get_sections(file_id, node_id=None)` - Get all sections/frames
5. `get_screenshot(file_id, node_id, scale, format)` - Download screenshot via Figma API
6. `process_figma_url(url)` - Main method: parse URL, get sections, download screenshots
7. `get_file_metadata(file_id)` - Get file metadata

**Features**:
- ✅ Parses both page and node URLs
- ✅ Detects if URL is for entire page or single section
- ✅ Automatically extracts all sections from a page
- ✅ Downloads screenshots via Figma's image API
- ✅ Extracts metadata (name, dimensions, position, background)
- ✅ Rate limiting (60 requests/minute)
- ✅ Async/await support
- ✅ Comprehensive error handling

**Usage Example**:
```python
from src.api import FigmaClient

client = FigmaClient()

# Process Figma URL
sections, screenshots = await client.process_figma_url(
    "https://figma.com/file/ABC123/Design?node-id=1:2"
)

for section, screenshot in zip(sections, screenshots):
    print(f"Section: {section['name']}")
    print(f"Size: {section['width']}x{section['height']}")
    # Save screenshot...
```

**Purpose**: Automate Figma design extraction without manual screenshots

---

### Step 12: CMS API Client
**What**: Complete integration with MiBlock CMS API

**File Created**: `src/api/cms_client.py`

**Class**: `CMSClient`

**Key Methods**:
1. `get_components_list(limit, offset, active_only)` - Get all components from CMS
2. `get_component_config(component_id)` - Download ComponentConfig.json
3. `get_component_format(component_id)` - Download ComponentFormat.json
4. `get_component_records(component_id, active_only, limit_per_parent)` - Download ComponentRecords.json (filtered!)
5. `get_component_screenshot(component_id)` - Download component screenshot
6. `download_component(component_id, include_screenshot)` - Download all data for one component
7. `download_all_components(max_components, batch_size, progress_callback)` - Batch download with progress
8. `check_component_updated(component_id, last_check_timestamp)` - Check if component was updated

**Features**:
- ✅ Downloads Config, Format, Records JSON
- ✅ Downloads component screenshots
- ✅ Filters records to only active parent+children (not all 500+!)
- ✅ Batch downloading with configurable concurrency
- ✅ Progress callbacks for UI updates
- ✅ Incremental update support
- ✅ Rate limiting (100 requests/minute)
- ✅ Async/await support
- ✅ Error handling with retries

**Usage Example**:
```python
from src.api import CMSClient

client = CMSClient()

# Download all components
components = await client.download_all_components(
    max_components=150,
    batch_size=10,
    progress_callback=lambda curr, total, name: print(f"{curr}/{total}: {name}")
)

# Download single component
comp_data = await client.download_component(560183)
print(comp_data['config'])
print(comp_data['format']['FormatContent'])  # Handlebars template
```

**Purpose**: Automate library component download and training data collection

---

### Step 13: Claude API Client
**What**: Integration with Anthropic Claude for AI-powered HTML generation

**File Created**: `src/api/claude_client.py`

**Class**: `ClaudeClient`

**Key Methods**:
1. `generate_html_from_screenshot(screenshot, context)` - Generate HTML from image
2. `analyze_html_structure(html)` - Analyze HTML and identify component hierarchy
3. `extract_component_definitions(html, config_structure)` - Map HTML to CMS definitions
4. `create_handlebars_template(html, definitions)` - Convert HTML to Handlebars template
5. `validate_html_match(screenshot, html)` - Validate if HTML matches screenshot visually

**Features**:
- ✅ Multi-modal input (image + text)
- ✅ Base64 image encoding
- ✅ Structured output (JSON)
- ✅ Context-aware generation
- ✅ Markdown code block parsing
- ✅ Rate limiting (50 requests/minute)
- ✅ Async/await support
- ✅ Error handling

**Usage Example**:
```python
from src.api import ClaudeClient

client = ClaudeClient()

# Generate HTML from screenshot
html = await client.generate_html_from_screenshot(
    screenshot=screenshot_bytes,
    additional_context="E-commerce product card"
)

# Analyze structure
structure = await client.analyze_html_structure(html)

# Extract definitions
definitions = await client.extract_component_definitions(
    html=html,
    config_structure=example_config
)

# Create Handlebars template
template = await client.create_handlebars_template(html, definitions)
```

**Purpose**: AI-powered HTML generation and component definition extraction

---

### Step 14: FastAPI Application
**What**: Complete REST API server with WebSocket support

**File Created**: `src/main.py`

**Application**: `FastAPI` app instance

**Key Endpoints**:

#### Health & Status
- `GET /` - API info
- `GET /health` - Health check
- `GET /api/status` - Service status (DB, Redis, APIs)

#### Component Generation
- `POST /api/generate/from-url` - Generate component from Figma URL
  - **Input**: `figma_url`, `component_name` (optional)
  - **Output**: `task_id` for tracking
- `GET /api/generate/task/{task_id}` - Get generation task status
  - **Output**: Status, progress, results

#### Library Management
- `GET /api/library/status` - Get library statistics
  - **Output**: Total components, last refresh time, status
- `POST /api/library/refresh` - Trigger library refresh
  - **Input**: `refresh_type` ("full" or "incremental")
  - **Output**: `task_id` for tracking
- `GET /api/library/refresh/{task_id}` - Get refresh progress
  - **Output**: Progress per phase (download, embed, store)

#### WebSocket
- `WS /ws/task/{task_id}` - Real-time task updates
  - **Messages**: Progress updates, current step, completion

**Features**:
- ✅ CORS middleware configured
- ✅ Auto-generated API docs at `/docs`
- ✅ WebSocket connection manager
- ✅ Static file serving for frontend
- ✅ Lifespan events (startup/shutdown)
- ✅ Client initialization (Figma, CMS, Claude)
- ✅ Error handling

**Usage**:
```bash
# Run server
python src/main.py

# Or with uvicorn
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# Access API docs
open http://localhost:8000/docs
```

**Purpose**: Provide REST API for browser-based UI and external integrations

---

### Step 15: Base Agent Infrastructure
**What**: Foundation for all AI agents with orchestration

**File Created**: `src/agents/base_agent.py`

**Classes**:

#### 1. `BaseAgent` (Abstract)
Base class that all specialized agents inherit from.

**Abstract Methods**:
- `name` (property) - Agent name
- `description` (property) - Agent description
- `execute(input_data)` - Main execution logic

**Provided Methods**:
- `run(input_data, progress_callback)` - Execute with timeout, retry, tracking
- `get_stats()` - Get execution statistics
- `reset_stats()` - Reset statistics

**Features**:
- ✅ Timeout enforcement (configurable, default 300s)
- ✅ Retry logic with exponential backoff
- ✅ Execution tracking (success/failure counts, timing)
- ✅ Progress callbacks for UI updates
- ✅ Comprehensive error handling
- ✅ Structured logging integration
- ✅ Metadata in results

**Example Agent**:
```python
from src.agents import BaseAgent

class ExampleAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "ExampleAgent"
    
    @property
    def description(self) -> str:
        return "Does something useful"
    
    async def execute(self, input_data):
        # Your agent logic here
        result = do_work(input_data)
        return {"output": result}

# Usage
agent = ExampleAgent(timeout=120, retry_count=3)
result = await agent.run({"input": "data"})
stats = agent.get_stats()
```

#### 2. `AgentOrchestrator`
Manages multiple agents and execution workflows.

**Methods**:
- `register_agent(agent)` - Register an agent
- `run_sequence(agent_names, input_data)` - Run agents in sequence (output → input)
- `run_parallel(agent_names, input_data)` - Run agents in parallel (same input)
- `get_all_stats()` - Get stats for all agents

**Usage**:
```python
from src.agents import AgentOrchestrator

orchestrator = AgentOrchestrator()
orchestrator.register_agent(agent1)
orchestrator.register_agent(agent2)

# Run in sequence
result = await orchestrator.run_sequence(
    ["Agent1", "Agent2"],
    input_data={"screenshot": bytes_data}
)

# Run in parallel
results = await orchestrator.run_parallel(
    ["Agent1", "Agent2"],
    input_data={"html": html_code}
)
```

**Purpose**: Provide consistent agent behavior and workflow orchestration

---

### Step 10: Logging System
**What**: Structured logging with JSON output

**File Created**: `src/utils/logging_config.py`

**Features**:
- ✅ Structured logging with `structlog`
- ✅ JSON format for production
- ✅ Human-readable console format for development
- ✅ Configurable log levels
- ✅ File and stdout output
- ✅ Automatic timestamp, logger name, log level
- ✅ Exception stack traces
- ✅ Context preservation

**Configuration**:
```bash
# In .env
LOG_LEVEL=INFO
LOG_FORMAT=json  # or "text"
LOG_FILE=./logs/app.log
```

**Usage**:
```python
import structlog

logger = structlog.get_logger("MyModule")

logger.info("user_registered", user_id=123, email="user@example.com")
logger.error("api_error", endpoint="/api/test", status_code=500)
```

**Output** (JSON format):
```json
{
  "event": "user_registered",
  "user_id": 123,
  "email": "user@example.com",
  "timestamp": "2025-12-29T19:00:00.000Z",
  "logger": "MyModule",
  "level": "info"
}
```

**Purpose**: Comprehensive logging for debugging and monitoring

---

### Step 10: Caching System
**What**: Redis-based caching with decorators

**File Created**: `src/utils/cache.py`

**Class**: `RedisCache`

**Key Methods**:
- `get(key, deserialize)` - Get value from cache
- `set(key, value, ttl, serialize)` - Set value in cache
- `delete(key)` - Delete key
- `exists(key)` - Check if key exists
- `clear_pattern(pattern)` - Clear keys matching pattern (e.g., "figma:*")
- `get_stats()` - Get Redis statistics

**Features**:
- ✅ Async/await support
- ✅ JSON, pickle, bytes serialization
- ✅ TTL (Time To Live) support
- ✅ Pattern-based clearing
- ✅ Statistics (hits, misses, memory)
- ✅ Graceful degradation if Redis unavailable
- ✅ Decorator for function result caching

**Decorator Usage**:
```python
from src.utils import cached

@cached("figma_file", ttl=600)
async def get_figma_file(file_id: str):
    # Expensive operation
    return await figma_api.get_file(file_id)

# First call: executes function, caches result
result1 = await get_figma_file("ABC123")

# Second call within 10 minutes: returns cached result
result2 = await get_figma_file("ABC123")  # Fast!
```

**Direct Usage**:
```python
from src.utils import cache

# Set value
await cache.set("my_key", {"data": "value"}, ttl=3600)

# Get value
value = await cache.get("my_key")

# Clear all Figma cache
await cache.clear_pattern("figma:*")
```

**Purpose**: Improve performance by caching API responses and computed results

---

## 📦 All Files Created

### Configuration & Setup
- `requirements.txt` - Python dependencies
- `env.example` - Environment variables template
- `README.md` - Project documentation
- `scripts/setup.py` - Setup helper script
- `scripts/setup_database.sql` - PostgreSQL schema

### Source Code - Configuration
- `src/config/settings.py` - Pydantic settings
- `src/config/__init__.py`

### Source Code - API Clients
- `src/api/figma_client.py` - Figma API integration
- `src/api/cms_client.py` - CMS API integration
- `src/api/claude_client.py` - Claude AI integration
- `src/api/__init__.py`

### Source Code - Database
- `src/models/database.py` - SQLAlchemy ORM models
- `src/models/__init__.py`

### Source Code - Agents
- `src/agents/base_agent.py` - Base agent class + orchestrator
- `src/agents/__init__.py`

### Source Code - Utilities
- `src/utils/logging_config.py` - Structured logging
- `src/utils/cache.py` - Redis caching
- `src/utils/__init__.py`

### Source Code - Main Application
- `src/main.py` - FastAPI application
- `src/__init__.py`

### Documentation
- `docs/phases/PHASE_1_FOUNDATION.md` - This file!

---

## 🎯 What Can You Do Now?

With Phase 1 complete, you have:

1. ✅ **Working API Server** - Run `python src/main.py` and access API at `http://localhost:8000`
2. ✅ **API Documentation** - View auto-generated docs at `http://localhost:8000/docs`
3. ✅ **Figma Integration** - Parse URLs and download screenshots
4. ✅ **CMS Integration** - Download components and training data
5. ✅ **Claude Integration** - Generate HTML from screenshots
6. ✅ **Database Ready** - PostgreSQL with pgvector for similarity search
7. ✅ **Caching Ready** - Redis for performance optimization
8. ✅ **Agent Framework** - Build specialized agents easily
9. ✅ **Logging System** - Track everything that happens
10. ✅ **Foundation Complete** - Ready to build agents!

---

## 🚀 Next Phase

**Phase 2: Library Ingestion & Training** (Steps 16-30)

Will implement:
- Agent 0: Library Ingestion Agent
- Download all components from CMS
- Generate CLIP embeddings
- Store in PostgreSQL with pgvector
- Enable visual similarity search

---

## 📝 Notes

- All code follows async/await patterns for performance
- Error handling is comprehensive with custom exceptions
- Rate limiting prevents API abuse
- Configuration is centralized and validated
- Logging provides excellent debugging capabilities
- Database schema is optimized for vector similarity search
- Agent framework makes adding new agents easy

---

**Phase 1 Complete! ✅**  
**Ready for Phase 2!** 🚀


