# Changelog

## Version 1.2 - 2026-01-31

### Critical Correction: Decision Flow Logic

Fixed the component type decision flow to correctly reflect the relationship between component types.

#### Corrected Flow:

**Step 1: Check for Multiple Sections (Compound)**
```
Has Multiple Sections? (User combines 2+ MiBlocks?)
  ├─ YES → Compound Component
  │        └─ Each MiBlock can be Simple OR Nested
  │
  └─ NO → Check for repeating sections
           ├─ YES → Nested Component (within 1 MiBlock)
           └─ NO → Simple Component
```

#### Key Insights:

1. **Compound is about COMBINING multiple MiBlocks**
   - Each MiBlock in a compound can be **Simple** OR **Nested** internally
   - Example: Features Header (Simple) + Feature Cards (Nested with repeating items)

2. **Correct Decision Order:**
   - First: Check if multiple separate sections → Compound
   - Then: Check if repeating within one MiBlock → Nested vs Simple

3. **Compound Can Contain:**
   - Simple MiBlocks (header with no repeating content)
   - Nested MiBlocks (cards section with repeating child items)
   - Combination of both

#### Example: Compound with Simple + Nested

```
Compound Component:
├─ MiBlock 1: Features Header (Simple)
│   └─ sectionTitle, sectionSubtitle
│
└─ MiBlock 2: Feature Cards (Nested)
    ├─ Parent: cardsTitle
    └─ Children: cardTitle, cardDescription, cardIcon
```

### Files Updated in v1.2:

- **06_VISUAL_WORKFLOWS.md**: Fixed decision flow diagrams
- **01_CORE_CONCEPTS.md**: Updated decision tree and compound description
- **02_HTML_ANALYSIS_LOGIC.md**: Added detect_separate_sections() logic
- **05_BEST_PRACTICES.md**: Clarified compound can contain simple or nested
- **CHANGELOG.md**: Added this correction

---

## Version 1.1 - 2026-01-31

### Major Update: Three Component Types

Updated documentation to clarify that there are **three types of components**, not just two:

#### 1. Simple Component
- **Description**: Single MiBlock with all fields
- **Use Case**: Hero sections, CTA banners, contact forms
- **Implementation**: Pass 1 MiBlock ID
- **No changes from previous version**

#### 2. Compound Component ⚠️ Clarified
- **Description**: Multiple **separate** MiBlocks that users combine together
- **Use Case**: Features grid with separate header and items as independent components
- **Implementation**: 
  - Pass **ALL MiBlock IDs**
  - No parent-child relationship between records
  - Each MiBlock is a separate component
- **Key Difference**: User selects 2+ MiBlocks together (like selecting header component + card component)

#### 3. Nested Component ✨ NEW
- **Description**: Repeating sections **within 1 MiBlock** 
- **Use Case**: FAQ sections, accordions, tabs, timeline
- **Implementation**:
  - Pass **parent MiBlock ID only**
  - Sub-records are linked to parent record ID
  - Parent-child relationship maintained in database
- **Key Difference**: Repeating items are children of parent (like FAQ items under FAQ section)

---

### Key Distinctions

| Feature | Simple | Compound | Nested |
|---------|--------|----------|--------|
| **MiBlocks** | 1 | 2+ | 1 (parent) |
| **Records** | Single | Multiple separate | Parent + Children |
| **Pass IDs** | 1 MiBlock ID | ALL MiBlock IDs | Parent MiBlock ID only |
| **Relationship** | None | Independent | Parent-Child linked |
| **Example** | Hero section | Header + Feature cards (separate) | FAQ section with Q&A items |

---

### What Was Wrong Before?

Previously, the documentation only mentioned **Simple** and **Compound** components, which created confusion:

- ❌ **Problem**: Nested components (like FAQs) were incorrectly categorized as "compound"
- ❌ **Problem**: Unclear when to pass all MiBlock IDs vs parent ID only
- ❌ **Problem**: Parent-child relationship not documented

### What's Fixed Now?

- ✅ Three distinct component types clearly defined
- ✅ Implementation details for each type documented
- ✅ Parent-child linking for nested components explained
- ✅ MiBlock ID passing logic clarified
- ✅ Examples added for each component type

---

### Files Updated

#### Documentation Files

1. **01_CORE_CONCEPTS.md**
   - Section 3: Added Nested Component type
   - Section 7: Updated decision tree with nested component logic
   - Section 9: Updated analysis checklist
   - Section 10: Added nested component pattern examples

2. **02_HTML_ANALYSIS_LOGIC.md**
   - Section 6: Added nested component detection algorithm
   - Section 7: Updated comprehensive analysis function
   - Section 8: Added practical examples for all three types

3. **03_FIELD_DEFINITION_GUIDE.md**
   - Section 4: Added Example 3 for nested component (FAQ)

4. **05_BEST_PRACTICES.md**
   - Section 2: Added nested component best practices
   - Added comparison between nested vs compound
   - Added examples showing when to use each type

5. **06_VISUAL_WORKFLOWS.md**
   - Section 3: Updated decision tree diagram
   - Section 7-8: Added nested component structure diagram
   - Section 9: Added component type comparison table
   - Section 12: Added nested component edit marker example
   - Section 15: Updated payload structure with childRecords

6. **07_IMPLEMENTATION_GUIDE.md**
   - Updated component_classifier.py reference

7. **README.md**
   - Updated key features to mention three component types
   - Updated examples structure to include nested component

---

### Migration Guide

If you're using the old documentation:

**Before (2 types):**
```
Has repeating sections?
  YES → Compound (2+ MiBlocks)
  NO → Simple (1 MiBlock)
```

**Now (3 types):**
```
Has repeating sections?
  NO → Simple (1 MiBlock)
  YES → Check if within 1 MiBlock or separate:
    Within 1 MiBlock → Nested (parent-child)
    Separate MiBlocks → Compound (independent)
```

**Action Items:**
1. Review your existing components
2. Identify which ones should be "nested" instead of "compound"
3. Update implementation to:
   - Pass parent MiBlock ID only for nested
   - Link sub-records to parent record ID
   - Use childRecords structure in payload

---

### Examples Added

#### Nested Component Example (FAQ Section)

**HTML Structure:**
```html
<section class="faq-section">
  <!-- Parent content -->
  <h2>Frequently Asked Questions</h2>
  
  <!-- Nested repeating items -->
  <div class="faq-item">
    <h3>Question 1?</h3>
    <p>Answer 1</p>
  </div>
  <div class="faq-item">
    <h3>Question 2?</h3>
    <p>Answer 2</p>
  </div>
</section>
```

**Component Type:** Nested
- Parent fields: sectionTitle
- Child fields: question, answer
- Pass: Parent MiBlock ID only
- Linking: Sub-records linked to parent record ID

---

**Version**: 1.1  
**Date**: 2026-01-31  
**Author**: Documentation Update  
**Purpose**: Clarify component types and implementation details
