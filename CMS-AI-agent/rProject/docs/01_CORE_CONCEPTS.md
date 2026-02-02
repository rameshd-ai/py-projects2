# Core Concepts: HTML to CMS Definition Generation

## Overview

This document explains the fundamental concepts behind converting HTML components into CMS field definitions.

---

## 1. The Transformation Pipeline

```
HTML Component
    ↓
Content Analysis
    ↓
Field Definition
    ↓
Template Generation
    ↓
CMS Payload
```

---

## 2. Content Classification

### Dynamic Content (Becomes Fields)
Content that editors need to modify:

```html
<!-- ✅ DYNAMIC - Becomes Field -->
<h2>Headline Text</h2>           → headline (Text field)
<p>Paragraph content</p>         → description (Text/RichText field)
<img src="image.jpg" alt="...">  → image (File field)
<a href="/link">Link</a>         → linkUrl + linkText (Text fields)
<button>Click Me</button>        → buttonText (Text field)
```

### Static Content (Stays in Template)
Structure and styling that shouldn't change:

```html
<!-- ❌ STATIC - Stays in Template -->
<div class="uk-container">       → Static container
<section class="uk-section">     → Static section wrapper
<span class="uk-icon">            → Static icon/decoration
<div class="uk-grid">             → Static grid layout
```

---

## 3. Component Types

### Simple Component
Single logical unit with one set of data:

**Example**: Hero section, CTA banner, contact form
```
MiBlock: hero_section
  - headline
  - subheading
  - buttonText
  - buttonLink
  - backgroundImage
```

**Characteristics**:
- Single MiBlock
- No repeating sections
- All content is static or single-instance

### Compound Component
Multiple MiBlocks that users select and combine together:

**Example**: Features grid with separate header and items as independent components
```
MiBlock 1: features_header (Simple - separate component)
  - sectionTitle
  - sectionSubtitle

MiBlock 2: feature_cards (Nested - separate component)
  Parent fields:
    - cardsTitle
  Child fields (repeating):
    - cardTitle
    - cardDescription
    - cardIcon
```

**Characteristics**:
- User selects 2+ MiBlocks together
- Each MiBlock is independent
- Each MiBlock can be **Simple** OR **Nested** internally
- When creating component, **pass ALL MiBlock IDs**
- No parent-child relationship between MiBlocks themselves
- But individual MiBlocks can have parent-child records if Nested

### Nested Component
Single MiBlock with repeating sections inside:

**Example**: Accordion, tabs, FAQ section
```
MiBlock: faq_section (parent)
  - sectionTitle
  - sectionSubtitle
  
  Nested Records (child):
    - question
    - answer
```

**Characteristics**:
- Single parent MiBlock
- Repeating sections within same MiBlock
- When creating component, **pass only parent MiBlock ID**
- Sub-records have **parent record ID linked**
- Parent-child relationship maintained in database

---

## 4. Field Types

### Text Field
Short, single-line text:
```json
{
  "PropertyName": "Heading",
  "PropertyAliasName": "heading",
  "ControlName": "Text",
  "DataType": "string",
  "PropertyMaxLength": 200
}
```

**Use for**: Headlines, labels, short descriptions, button text

### RichText Field
Long, formatted text with HTML:
```json
{
  "PropertyName": "Article Content",
  "PropertyAliasName": "articleContent",
  "ControlName": "RichText",
  "DataType": "string"
}
```

**Use for**: Blog posts, long descriptions, formatted content

### File Field
Images, documents, media:
```json
{
  "PropertyName": "Hero Image",
  "PropertyAliasName": "heroImage",
  "ControlName": "File",
  "ResourceTypeName": "Image",
  "DataType": "string",
  "PropertyMaxLength": 500
}
```

**Use for**: Images, PDFs, videos

### Number Field
Numeric values:
```json
{
  "PropertyName": "Price",
  "PropertyAliasName": "price",
  "ControlName": "Number",
  "DataType": "number"
}
```

**Use for**: Prices, quantities, ratings

### Boolean Field
True/false toggles:
```json
{
  "PropertyName": "Show Banner",
  "PropertyAliasName": "showBanner",
  "ControlName": "Boolean",
  "DataType": "boolean"
}
```

**Use for**: Feature flags, visibility toggles

---

## 5. Key Principles

### Principle 1: Identifier Field
Every MiBlock needs exactly ONE identifier field:
```json
{
  "PropertyName": "Title",
  "PropertyAliasName": "title",
  "IsIdentifier": true,  // ⭐ First field is identifier
  "IsMandatory": true
}
```

### Principle 2: Naming Conventions
- **PropertyName**: Human-readable, PascalCase with spaces
  - ✅ "Product Name", "Hero Image", "Primary CTA Text"
  - ❌ "productName", "hero_image", "primary-cta-text"

- **PropertyAliasName**: Code-friendly, camelCase
  - ✅ "productName", "heroImage", "primaryCtaText"
  - ❌ "ProductName", "hero_image", "primary-cta-text"

### Principle 3: Image URLs as Arrays
Images must be in array format:
```json
{
  "heroImage": ["https://example.com/image.jpg"]  // ✅ Array
}

// ❌ WRONG:
{
  "heroImage": "https://example.com/image.jpg"  // ❌ String
}
```

### Principle 4: Mandatory vs Optional
Make fields mandatory if content is critical:
```json
{
  "IsMandatory": true   // Required field (e.g., headline, image)
}
{
  "IsMandatory": false  // Optional field (e.g., link, subtitle)
}
```

---

## 6. Template Binding

### Data Access Pattern
In Handlebars templates, access fields via `data.fieldAlias`:

```handlebars
{{#each ComponentRecordJson.component-alias}}
  <h2>{{data.headline}}</h2>
  <p>{{data.description}}</p>
  <img src="{{data.image}}" alt="{{data.imageAlt}}">
  <a href="{{data.link}}">{{data.linkText}}</a>
{{/each}}
```

### Edit Marker
Add `%%componentRecordEditable%%` to the FIRST text element:
```handlebars
<h2 %%componentRecordEditable%%>{{data.headline}}</h2>
<!-- CMS auto-enables editing for ALL fields -->
```

---

## 7. Decision Tree: Component Type

```
Analyze Component Structure
    │
    ▼
Has Multiple Sections? (User combines 2+ MiBlocks?)
    │
    ├─ YES → Compound Component
    │         ├─ Create 2+ separate MiBlocks
    │         ├─ Pass ALL MiBlock IDs
    │         ├─ Each MiBlock can be Simple OR Nested
    │         └─ Example: Header (Simple) + Cards (Nested)
    │
    └─ NO → Has repeating sections within same MiBlock?
              │
              ├─ YES → Nested Component
              │         ├─ Create 1 parent MiBlock
              │         ├─ Repeating sections are child records
              │         ├─ Pass only parent MiBlock ID
              │         └─ Sub-records linked to parent record ID
              │
              └─ NO → Simple Component
                      └─ Create single MiBlock with all fields

⭐ KEY INSIGHT:
   - Compound = Combining multiple separate MiBlocks
   - Each MiBlock in compound can itself be Simple or Nested
   - Nested = Repeating content within ONE MiBlock
```

---

## 8. Decision Tree: Field Type

```
What type of content?
│
├─ Text Content
│   ├─ Short (< 200 chars)?
│   │   └─ Text Field (max 200-500)
│   └─ Long / Formatted?
│       └─ RichText Field
│
├─ Image / File
│   └─ File Field (with ResourceTypeName)
│
├─ Numeric Value
│   └─ Number Field
│
└─ Toggle / Flag
    └─ Boolean Field
```

---

## 9. Analysis Checklist

When analyzing HTML, ask:

1. **What content will editors change?**
   - Headlines, paragraphs, images, links → Fields

2. **What stays the same?**
   - Structure, classes, layout → Template

3. **Are there repeating elements?**
   - No → Simple component (one MiBlock)
   - Yes → Check if within 1 MiBlock or separate MiBlocks:
     - Within 1 MiBlock → Nested component (parent MiBlock ID only)
     - Separate MiBlocks → Compound component (all MiBlock IDs)

4. **What field types are needed?**
   - Short text → Text
   - Long text → RichText
   - Images → File
   - Numbers → Number
   - Toggles → Boolean

5. **Which field is the identifier?**
   - Usually the main headline or title
   - Must be unique and descriptive

6. **Component type implementation details:**
   - **Simple**: Pass 1 MiBlock ID
   - **Compound**: Pass ALL MiBlock IDs (no parent-child relationship)
   - **Nested**: Pass parent MiBlock ID only (sub-records linked to parent record ID)

---

## 10. Common Patterns

### Pattern 1: Hero Section (Simple)
```
Component Type: Simple
Fields:
- heading (Text, Identifier)
- subheading (Text)
- ctaText (Text)
- ctaLink (Text)
- backgroundImage (File)

Implementation:
- 1 MiBlock
- Pass single MiBlock ID
```

### Pattern 2: Feature Cards (Compound with Nested)
```
Component Type: Compound

Header MiBlock (Simple):
- sectionTitle (Text, Identifier)
- sectionSubtitle (Text)

Cards MiBlock (Nested):
Parent fields:
- cardsTitle (Text, Identifier)

Child fields (repeating):
- cardTitle (Text, Identifier)
- cardDescription (Text)
- cardIcon (File)

Implementation:
- 2 separate MiBlocks
- User selects both components
- Pass ALL MiBlock IDs
- Header is Simple, Cards is Nested
- No parent-child between header and cards
- But cards have parent-child within themselves
```

### Pattern 3: FAQ/Accordion (Nested)
```
Component Type: Nested

Parent MiBlock:
- sectionTitle (Text, Identifier)
- sectionSubtitle (Text)

Child Records (repeating):
- question (Text)
- answer (Text)

Implementation:
- 1 parent MiBlock with nested records
- Pass parent MiBlock ID only
- Sub-records linked to parent record ID
```

### Pattern 4: Image + Text (Simple)
```
Component Type: Simple
Fields:
- headline (Text, Identifier)
- bodyText (RichText)
- image (File)
- imageAlt (Text)

Implementation:
- 1 MiBlock
- Pass single MiBlock ID
```

---

## Next Steps

- Read [HTML Analysis Logic](02_HTML_ANALYSIS_LOGIC.md)
- Study [Field Definition Guide](03_FIELD_DEFINITION_GUIDE.md)
- Review [Handlebars Templates](04_HANDLEBARS_TEMPLATES.md)

---

**Version**: 1.0  
**Last Updated**: 2026-01-31
