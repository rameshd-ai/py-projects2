# PHASE 2: Library Ingestion & Training

**Duration**: Week 2  
**Steps**: 16-30  
**Status**: ⏳ PENDING  
**Checkpoint**: Components downloaded + Embeddings indexed

---

## 📋 Overview

Phase 2 implements the Library Ingestion & Training Agent (Agent 0), which:
- Downloads all existing components from CMS
- Generates visual embeddings using CLIP
- Stores components in PostgreSQL with pgvector
- Enables visual similarity search for component matching

This is the **prerequisite** for all component matching functionality.

---

## 🎯 Steps to Complete

### Steps 16-20: CLIP Integration
- **16**: Install and test CLIP model (OpenAI CLIP or Hugging Face)
- **17**: Create CLIP embedding generator utility
- **18**: Test embedding generation on sample images
- **19**: Verify embedding dimensionality (512-dim vectors)
- **20**: Create batch embedding generation for multiple images

### Steps 21-25: Library Ingestion Agent (Agent 0)
- **21**: Create `LibraryIngestionAgent` class inheriting from `BaseAgent`
- **22**: Implement CMS component list fetching
- **23**: Implement component download logic (Config, Format, Records, Screenshot)
- **24**: Implement embedding generation for downloaded screenshots
- **25**: Implement database storage with pgvector

### Steps 26-30: Testing & CLI Interface
- **26**: Create library refresh task tracking in database
- **27**: Add progress tracking and WebSocket updates
- **28**: Create CLI script for library ingestion (`scripts/ingest_library.py`)
- **29**: Test full refresh (download all components)
- **30**: Test incremental refresh (only new/updated)

---

## 📦 Files to Create

### Agent Implementation
- `src/agents/library_ingestion_agent.py` - Agent 0 implementation
- `src/utils/clip_embeddings.py` - CLIP embedding generator
- `scripts/ingest_library.py` - CLI script for manual library refresh

### Tests
- `tests/test_library_ingestion.py` - Unit tests for Agent 0
- `tests/test_clip_embeddings.py` - Embedding generation tests

---

## 🔧 Key Components

### LibraryIngestionAgent

**Purpose**: Download components from CMS and index them for similarity search

**Methods**:
- `execute(input_data)` - Main ingestion process
- `fetch_component_list()` - Get list from CMS
- `download_component_batch()` - Download components in batches
- `generate_embeddings_batch()` - Generate CLIP embeddings
- `store_components_batch()` - Store in PostgreSQL
- `update_progress()` - Update task progress in DB

**Input**:
```python
{
    "refresh_type": "full" | "incremental",
    "task_id": "uuid",
    "max_components": 1000
}
```

**Output**:
```python
{
    "total_components": 150,
    "new_components": 5,
    "updated_components": 12,
    "failed_components": 0,
    "duration_seconds": 720
}
```

### CLIP Embedding Generator

**Purpose**: Generate 512-dimensional visual embeddings from screenshots

**Methods**:
- `load_model()` - Load CLIP model
- `generate_embedding(image)` - Generate single embedding
- `generate_embeddings_batch(images)` - Batch generation
- `encode_image()` - Preprocess image for CLIP

**Usage**:
```python
from src.utils.clip_embeddings import generate_embedding

embedding = await generate_embedding(screenshot_bytes)
# Returns numpy array of shape (512,)
```

---

## 🧪 Testing Strategy

1. **Unit Tests**: Test individual methods (download, embed, store)
2. **Integration Tests**: Test full ingestion workflow
3. **Performance Tests**: Measure embedding generation speed
4. **Database Tests**: Verify pgvector index performance

---

## ✅ Completion Criteria

- [ ] CLIP model loaded and tested
- [ ] LibraryIngestionAgent implemented
- [ ] Downloads all components from CMS successfully
- [ ] Generates embeddings for all component screenshots
- [ ] Stores components in PostgreSQL with embeddings
- [ ] pgvector index created and searchable
- [ ] Progress tracking works (database + WebSocket)
- [ ] CLI script works for manual library refresh
- [ ] Full refresh tested (all components)
- [ ] Incremental refresh tested (new/updated only)
- [ ] Performance acceptable (<1 second per component)

---

## 📝 Implementation Notes

### CLIP Model Selection
- Use `openai/clip-vit-base-patch32` (faster)
- OR `openai/clip-vit-large-patch14` (more accurate)
- Embedding size: 512 dimensions
- Model loaded once at startup

### Batch Processing
- Process components in batches of 10
- Parallel download (respecting rate limits)
- Sequential embedding generation (GPU optimization)
- Batch database inserts

### Error Handling
- Continue on individual component failures
- Track failed component IDs
- Retry failed components at end
- Report failures in task results

### Progress Tracking
Three phases to track:
1. **Downloading**: Fetching from CMS API
2. **Embedding**: Generating CLIP vectors
3. **Storing**: Inserting into PostgreSQL

---

## 🚀 Next Phase

After Phase 2 completion, proceed to:

**Phase 3: HTML Generation** (Steps 31-42)
- Implement HTML Generator Agent (Agent 1)
- Generate HTML from Figma screenshots
- Validate HTML matches screenshot
- Store results

---

**Status**: ⏳ PENDING  
**Waiting for**: Phase 2 implementation start command


