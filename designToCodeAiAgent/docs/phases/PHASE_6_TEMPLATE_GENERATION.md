# PHASE 6: Template Generation

**Duration**: Week 6  
**Steps**: 66-77  
**Status**: ⏳ PENDING  
**Checkpoint**: Handlebars templates valid

---

## 📋 Overview

Phase 6 implements the Template Generator Agent (Agent 5) and Output Formatter Agent (Agent 6):
- Convert static HTML to Handlebars templates
- Generate sample component records
- Format final MiBlock CMS output
- Create all three JSON files (Config, Format, Records)

---

## 🎯 Key Deliverables

### Template Generator Agent (Agent 5)

**Purpose**: Create Handlebars template (FormatContent)

**Input**: HTML + Definitions
**Output**: MiBlockComponentFormat.json

**Template Syntax**:
- `{{data.PropertyName}}` for Level0 properties
- `{{#each Child.ComponentName}}...{{/each}}` for repeating sections
- Keep all HTML structure intact

### Output Formatter Agent (Agent 6)

**Purpose**: Generate final MiBlock CMS output

**Output**: Three JSON files
1. **ComponentConfig.json** - Component hierarchy and definitions
2. **ComponentFormat.json** - Handlebars template
3. **ComponentRecords.json** - Sample data (1 active parent + children)

---

## 📦 Files to Create

- `src/agents/template_generator_agent.py` - Agent 5
- `src/agents/output_formatter_agent.py` - Agent 6
- `src/utils/handlebars_helpers.py` - Handlebars utilities
- `tests/test_template_generator.py`
- `tests/test_output_formatter.py`

---

**Status**: ⏳ PENDING  
**Next**: Phase 7 - Orchestration + Web UI


