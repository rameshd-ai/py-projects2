# PHASE 3: HTML Generation

**Duration**: Week 3  
**Steps**: 31-42  
**Status**: ⏳ PENDING  
**Checkpoint**: Claude AI generating valid HTML

---

## 📋 Overview

Phase 3 implements the HTML Generator Agent (Agent 1) and Visual Validator Agent (Agent 2):
- Generate HTML from Figma screenshots using Claude AI
- Validate HTML matches screenshot visually
- Retry generation if validation fails
- Store validated HTML for next steps

---

## 🎯 Steps to Complete

### Steps 31-35: HTML Generator Agent
- **31**: Create `HTMLGeneratorAgent` class
- **32**: Integrate with Claude API client
- **33**: Implement prompt engineering for HTML generation
- **34**: Handle Claude API responses and extract HTML
- **35**: Add retry logic for failed generations

### Steps 36-42: Visual Validator Agent
- **36**: Create `VisualValidatorAgent` class
- **37**: Implement screenshot comparison (SSIM, perceptual hash, CLIP)
- **38**: Set up Playwright for HTML rendering
- **39**: Implement screenshot capture from generated HTML
- **40**: Compare rendered HTML vs original Figma screenshot
- **41**: Calculate similarity scores and determine match
- **42**: Implement regeneration loop (max 3 retries)

---

## 📦 Files to Create

### Agent Implementations
- `src/agents/html_generator_agent.py` - Agent 1
- `src/agents/visual_validator_agent.py` - Agent 2
- `src/utils/image_comparison.py` - Image similarity utilities

### Tests
- `tests/test_html_generator.py`
- `tests/test_visual_validator.py`
- `tests/test_image_comparison.py`

---

## 🔧 Key Components

### HTMLGeneratorAgent (Agent 1)

**Purpose**: Generate semantic HTML from Figma screenshots

**Input**:
```python
{
    "screenshot": bytes,  # Figma screenshot
    "section_name": "Hero Section",
    "metadata": {
        "width": 1920,
        "height": 800
    }
}
```

**Output**:
```python
{
    "html": "<div class='hero'>...</div>",
    "generation_time": 5.2,
    "token_count": 1024
}
```

### VisualValidatorAgent (Agent 2)

**Purpose**: Validate generated HTML matches original screenshot

**Methods**:
- `render_html(html)` - Render HTML to screenshot using Playwright
- `compare_images(img1, img2)` - Calculate similarity
- `validate(original_screenshot, html)` - Main validation

**Comparison Metrics**:
1. **SSIM** (Structural Similarity Index) - 0-1 score
2. **Perceptual Hash** - Hamming distance
3. **CLIP Embeddings** - Cosine similarity

**Output**:
```python
{
    "is_valid": True,
    "similarity_scores": {
        "ssim": 0.92,
        "perceptual_hash": 3,
        "clip_similarity": 0.89
    },
    "overall_score": 0.91,
    "passes_threshold": True  # threshold: 0.85
}
```

---

## ✅ Completion Criteria

- [ ] HTMLGeneratorAgent implemented and tested
- [ ] Generates semantic, clean HTML from screenshots
- [ ] VisualValidatorAgent implemented and tested
- [ ] Playwright rendering works correctly
- [ ] Image comparison calculates accurate similarity scores
- [ ] Regeneration loop works (max 3 attempts)
- [ ] Performance acceptable (<10 seconds per generation)
- [ ] 80%+ validation success rate

---

**Status**: ⏳ PENDING  
**Next**: Phase 4 - Structure Analysis


