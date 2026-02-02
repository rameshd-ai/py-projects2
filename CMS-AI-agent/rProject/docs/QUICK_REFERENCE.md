# Quick Reference: Component Types

## Decision Flow (Corrected)

```
┌─────────────────────────────────────────────────────────────┐
│                    ANALYZE COMPONENT                         │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
            ┌────────────────────────┐
            │ Has Multiple Sections? │
            │ (2+ separate MiBlocks) │
            └────────┬───────────────┘
                     │
        ┌────────────┴────────────┐
        │                         │
       YES                       NO
        │                         │
        ▼                         ▼
  ┌──────────┐         ┌─────────────────┐
  │ COMPOUND │         │ Has Repeating   │
  └──────────┘         │ Sections?       │
        │              └────────┬────────┘
        │                       │
        │              ┌────────┴────────┐
        │              │                 │
        │             YES               NO
        │              │                 │
        │              ▼                 ▼
        │         ┌────────┐       ┌────────┐
        │         │ NESTED │       │ SIMPLE │
        │         └────────┘       └────────┘
        │
        │
        └──────────────────────────────────────────┐
                                                   │
    Each MiBlock in Compound                      │
    can be Simple OR Nested ────────────────────►─┘
```

---

## Component Types Summary

### 1. Simple Component
- **What**: Single MiBlock, no repeating content
- **Example**: Hero section, CTA banner
- **Pass**: 1 MiBlock ID
- **Structure**:
  ```
  MiBlock: hero_section
    - heading
    - subheading
    - ctaButton
    - image
  ```

### 2. Nested Component
- **What**: Repeating sections within 1 MiBlock
- **Example**: FAQ, accordion, tabs
- **Pass**: Parent MiBlock ID only
- **Structure**:
  ```
  MiBlock: faq_section (parent)
    Parent fields:
      - sectionTitle
    Child records:
      - question
      - answer
  ```
- **Linking**: Sub-records linked to parent record ID

### 3. Compound Component
- **What**: User combines 2+ separate MiBlocks
- **Example**: Features section with header + cards
- **Pass**: ALL MiBlock IDs
- **Structure**:
  ```
  MiBlock 1: features_header (Simple)
    - sectionTitle
    - sectionSubtitle
  
  MiBlock 2: feature_cards (Nested)
    Parent:
      - cardsTitle
    Children:
      - cardTitle
      - cardDescription
  ```
- **Key**: Each MiBlock can be Simple OR Nested

---

## Common Patterns

### Pattern 1: Hero (Simple)
```
Component Type: Simple
MiBlocks: 1
Implementation: Pass 1 ID
```

### Pattern 2: FAQ (Nested)
```
Component Type: Nested
MiBlocks: 1 parent with children
Implementation: Pass parent ID only
Linking: Children → parent record ID
```

### Pattern 3: Features Section (Compound)
```
Component Type: Compound
MiBlocks: 
  - Header (Simple)
  - Cards (Nested)
Implementation: Pass both MiBlock IDs
```

### Pattern 4: Product Grid (Compound)
```
Component Type: Compound
MiBlocks:
  - Grid Header (Simple)
  - Product Cards (Nested with variants)
  - CTA Footer (Simple)
Implementation: Pass all 3 MiBlock IDs
```

---

## Quick Decision Guide

### Ask These Questions:

1. **Will user combine multiple separate components?**
   - YES → **Compound**
   - NO → Continue to #2

2. **Does it have repeating sections within same component?**
   - YES → **Nested**
   - NO → **Simple**

### Examples:

| HTML Structure | Type | Why |
|----------------|------|-----|
| Hero section | Simple | No repeating, no multiple sections |
| FAQ with Q&A items | Nested | Repeating within same section |
| Header + Cards | Compound | Two separate components combined |
| Accordion | Nested | Repeating panels within accordion |
| Header + Cards (with nested items) | Compound | Header (Simple) + Cards (Nested) |
| Tabs | Nested | Repeating tab panels within tabs component |

---

## Implementation Checklist

### For Simple:
- [ ] Create 1 MiBlock
- [ ] Add all fields to definitions
- [ ] Pass 1 MiBlock ID when creating component

### For Nested:
- [ ] Create 1 parent MiBlock
- [ ] Define parent fields in `definitions`
- [ ] Define child fields in `child_definitions`
- [ ] Structure records with `childRecords` array
- [ ] Pass parent MiBlock ID only
- [ ] Ensure children link to parent record ID

### For Compound:
- [ ] Create 2+ separate MiBlocks
- [ ] Determine if each MiBlock is Simple or Nested
- [ ] If Nested, add `child_definitions` to that MiBlock
- [ ] Pass ALL MiBlock IDs when creating component
- [ ] No parent-child relationship between MiBlocks themselves

---

## Common Mistakes

### ❌ Mistake 1: Using Compound for Nested
```
WRONG: FAQ as Compound
  - FAQ Header (separate MiBlock)
  - FAQ Items (separate MiBlock)

RIGHT: FAQ as Nested
  - FAQ Section (parent with Q&A children)
```

### ❌ Mistake 2: Using Nested for Compound
```
WRONG: Header + Cards as Nested
  - Won't work - they are separate components

RIGHT: Header + Cards as Compound
  - Header (Simple MiBlock)
  - Cards (Nested MiBlock)
```

### ❌ Mistake 3: Wrong ID passing
```
WRONG: Nested → Pass all child record IDs
RIGHT: Nested → Pass parent MiBlock ID only

WRONG: Compound → Pass only first MiBlock ID
RIGHT: Compound → Pass ALL MiBlock IDs
```

---

**Version**: 1.2  
**Last Updated**: 2026-01-31  
**Purpose**: Quick reference for component type decisions
