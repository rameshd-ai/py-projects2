# PHASE 5: Definition Extraction

**Duration**: Week 5  
**Steps**: 53-65  
**Status**: ⏳ PENDING  
**Checkpoint**: ControlIds and properties correct

---

## 📋 Overview

Phase 5 implements the Definition Extractor Agent (Agent 4):
- Map HTML elements to CMS component definitions
- Extract PropertyName and PropertyAliasName
- Assign ControlId (1=Text, 7=Image, 8=Boolean, etc.)
- Generate MiBlockComponentConfig.json structure

---

## 🎯 Key Deliverables

### Definition Extractor Agent (Agent 4)

**Purpose**: Create CMS component definitions from HTML structure

**Input**: HTML + Structure hierarchy
**Output**: ComponentConfig.json

**Mapping Rules**:
- Text content → ControlId: 1
- Images → ControlId: 7
- Booleans → ControlId: 8
- Links → ControlId: 1 (with URL)
- Repeating sections → Level1+ components

---

## 📦 Files to Create

- `src/agents/definition_extractor_agent.py` - Agent 4
- `src/utils/control_id_mapper.py` - ControlId mapping logic
- `tests/test_definition_extractor.py`

---

**Status**: ⏳ PENDING  
**Next**: Phase 6 - Template Generation



