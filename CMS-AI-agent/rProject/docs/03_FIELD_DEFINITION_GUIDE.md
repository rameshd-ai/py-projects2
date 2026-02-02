# Field Definition Guide

## Overview

This guide provides detailed instructions for creating CMS field definitions from analyzed HTML components.

---

## 1. Field Definition Structure

### Complete Field Definition Template

```json
{
  "PropertyName": "Display Name",
  "PropertyAliasName": "camelCaseName",
  "ControlName": "Text|File|RichText|Number|Date|Boolean",
  "IsIdentifier": true|false,
  "IsMandatory": true|false,
  "DataType": "string|number|boolean",
  "ResourceTypeName": "Image|Document|Video",  // Only for File type
  "PropertyMaxLength": 500
}
```

---

## 2. Field Types Reference

### 2.1 Text Field

**When to use**: Short, single-line text (< 500 characters)

```json
{
  "PropertyName": "Product Name",
  "PropertyAliasName": "productName",
  "ControlName": "Text",
  "IsIdentifier": true,
  "IsMandatory": true,
  "DataType": "string",
  "PropertyMaxLength": 200
}
```

**Use cases**:
- Headlines (h1, h2, h3)
- Button text
- Labels
- Short descriptions
- Link text
- Alt text

**Max length guidelines**:
- Headlines: 200
- Descriptions: 500
- URLs: 500
- Alt text: 200

### 2.2 RichText Field

**When to use**: Long, formatted text with HTML

```json
{
  "PropertyName": "Article Content",
  "PropertyAliasName": "articleContent",
  "ControlName": "RichText",
  "IsIdentifier": false,
  "IsMandatory": true,
  "DataType": "string"
}
```

**Use cases**:
- Blog posts
- Long descriptions
- Formatted content
- HTML content blocks

**Note**: No PropertyMaxLength for RichText

### 2.3 File Field

**When to use**: Images, documents, media files

```json
{
  "PropertyName": "Hero Image",
  "PropertyAliasName": "heroImage",
  "ControlName": "File",
  "IsIdentifier": false,
  "IsMandatory": true,
  "DataType": "string",
  "ResourceTypeName": "Image",
  "PropertyMaxLength": 500
}
```

**ResourceTypeName values**:
- `"Image"`: For images (jpg, png, gif, svg)
- `"Document"`: For PDFs, docs
- `"Video"`: For video files

**Always include**:
- Image + Alt Text pair
- `PropertyMaxLength: 500` for URL storage

### 2.4 Number Field

**When to use**: Numeric values

```json
{
  "PropertyName": "Product Price",
  "PropertyAliasName": "productPrice",
  "ControlName": "Number",
  "IsIdentifier": false,
  "IsMandatory": true,
  "DataType": "number"
}
```

**Use cases**:
- Prices
- Quantities
- Ratings
- Counts

### 2.5 Boolean Field

**When to use**: True/false toggles

```json
{
  "PropertyName": "Show Banner",
  "PropertyAliasName": "showBanner",
  "ControlName": "Boolean",
  "IsIdentifier": false,
  "IsMandatory": false,
  "DataType": "boolean"
}
```

**Use cases**:
- Feature flags
- Visibility toggles
- Enable/disable options

### 2.6 Date Field

**When to use**: Date/time values

```json
{
  "PropertyName": "Event Date",
  "PropertyAliasName": "eventDate",
  "ControlName": "Date",
  "IsIdentifier": false,
  "IsMandatory": true,
  "DataType": "string"
}
```

**Use cases**:
- Event dates
- Publication dates
- Deadlines

---

## 3. Field Creation Rules

### Rule 1: Identifier Field

**Every MiBlock must have exactly ONE identifier field**

```json
{
  "PropertyName": "Headline",
  "PropertyAliasName": "headline",
  "ControlName": "Text",
  "IsIdentifier": true,  // ⭐ REQUIRED
  "IsMandatory": true,
  "DataType": "string",
  "PropertyMaxLength": 200
}
```

**Identifier should be**:
- First field in definitions array
- Unique and descriptive
- Usually the main headline or title
- Always mandatory

### Rule 2: Naming Conventions

#### PropertyName (Display Name)
```
✅ CORRECT:
- "Product Name"
- "Hero Image"
- "Primary CTA Text"
- "Section Heading"

❌ INCORRECT:
- "productName"
- "hero_image"
- "primary-cta-text"
- "SectionHeading"
```

**Pattern**: PascalCase with spaces, human-readable

#### PropertyAliasName (Code Name)
```
✅ CORRECT:
- "productName"
- "heroImage"
- "primaryCtaText"
- "sectionHeading"

❌ INCORRECT:
- "ProductName"
- "hero_image"
- "primary-cta-text"
- "Section Heading"
```

**Pattern**: camelCase, code-friendly, no spaces

### Rule 3: Image Field Pairing

**Always create image + alt text pairs**:

```json
[
  {
    "PropertyName": "Hero Image",
    "PropertyAliasName": "heroImage",
    "ControlName": "File",
    "ResourceTypeName": "Image",
    "IsMandatory": true
  },
  {
    "PropertyName": "Hero Image Alt Text",
    "PropertyAliasName": "heroImageAlt",
    "ControlName": "Text",
    "IsMandatory": true,
    "PropertyMaxLength": 200
  }
]
```

### Rule 4: Link Field Pairing

**Links need text + URL fields**:

```json
[
  {
    "PropertyName": "Call To Action Text",
    "PropertyAliasName": "ctaText",
    "ControlName": "Text",
    "IsMandatory": true,
    "PropertyMaxLength": 100
  },
  {
    "PropertyName": "Call To Action Link",
    "PropertyAliasName": "ctaLink",
    "ControlName": "Text",
    "IsMandatory": false,  // Optional if button has no link
    "PropertyMaxLength": 500
  }
]
```

---

## 4. Complete Examples

### Example 1: Hero Section (Simple Component)

```json
{
  "component_name": "ag_hero_section",
  "component_type": "simple",
  "miblocks": [
    {
      "component_name": "AG Hero Section",
      "component_alias_name": "ag-hero-section",
      "definitions": [
        {
          "PropertyName": "Main Heading",
          "PropertyAliasName": "mainHeading",
          "ControlName": "Text",
          "IsIdentifier": true,
          "IsMandatory": true,
          "DataType": "string",
          "PropertyMaxLength": 200
        },
        {
          "PropertyName": "Subheading",
          "PropertyAliasName": "subheading",
          "ControlName": "Text",
          "IsIdentifier": false,
          "IsMandatory": true,
          "DataType": "string",
          "PropertyMaxLength": 500
        },
        {
          "PropertyName": "CTA Button Text",
          "PropertyAliasName": "ctaButtonText",
          "ControlName": "Text",
          "IsIdentifier": false,
          "IsMandatory": true,
          "DataType": "string",
          "PropertyMaxLength": 50
        },
        {
          "PropertyName": "CTA Button Link",
          "PropertyAliasName": "ctaButtonLink",
          "ControlName": "Text",
          "IsIdentifier": false,
          "IsMandatory": false,
          "DataType": "string",
          "PropertyMaxLength": 500
        },
        {
          "PropertyName": "Background Image",
          "PropertyAliasName": "backgroundImage",
          "ControlName": "File",
          "IsIdentifier": false,
          "IsMandatory": true,
          "DataType": "string",
          "ResourceTypeName": "Image",
          "PropertyMaxLength": 500
        },
        {
          "PropertyName": "Background Image Alt",
          "PropertyAliasName": "backgroundImageAlt",
          "ControlName": "Text",
          "IsIdentifier": false,
          "IsMandatory": true,
          "DataType": "string",
          "PropertyMaxLength": 200
        }
      ]
    }
  ]
}
```

### Example 2: Feature Cards (Compound Component)

```json
{
  "component_name": "ag_feature_cards",
  "component_type": "compound",
  "miblocks": [
    {
      "component_name": "AG Feature Cards Header",
      "component_alias_name": "ag-feature-cards-header",
      "definitions": [
        {
          "PropertyName": "Section Title",
          "PropertyAliasName": "sectionTitle",
          "ControlName": "Text",
          "IsIdentifier": true,
          "IsMandatory": true,
          "DataType": "string",
          "PropertyMaxLength": 200
        },
        {
          "PropertyName": "Section Subtitle",
          "PropertyAliasName": "sectionSubtitle",
          "ControlName": "Text",
          "IsIdentifier": false,
          "IsMandatory": false,
          "DataType": "string",
          "PropertyMaxLength": 500
        }
      ]
    },
    {
      "component_name": "AG Feature Card Item",
      "component_alias_name": "ag-feature-card-item",
      "definitions": [
        {
          "PropertyName": "Card Title",
          "PropertyAliasName": "cardTitle",
          "ControlName": "Text",
          "IsIdentifier": true,
          "IsMandatory": true,
          "DataType": "string",
          "PropertyMaxLength": 200
        },
        {
          "PropertyName": "Card Description",
          "PropertyAliasName": "cardDescription",
          "ControlName": "Text",
          "IsIdentifier": false,
          "IsMandatory": true,
          "DataType": "string",
          "PropertyMaxLength": 500
        },
        {
          "PropertyName": "Card Icon",
          "PropertyAliasName": "cardIcon",
          "ControlName": "File",
          "IsIdentifier": false,
          "IsMandatory": true,
          "DataType": "string",
          "ResourceTypeName": "Image",
          "PropertyMaxLength": 500
        },
        {
          "PropertyName": "Card Icon Alt",
          "PropertyAliasName": "cardIconAlt",
          "ControlName": "Text",
          "IsIdentifier": false,
          "IsMandatory": true,
          "DataType": "string",
          "PropertyMaxLength": 200
        }
      ]
    }
  ]
}
```

### Example 3: FAQ Section (Nested Component)

```json
{
  "component_name": "ag_faq_section",
  "component_type": "nested",
  "miblocks": [
    {
      "component_name": "AG FAQ Section",
      "component_alias_name": "ag-faq-section",
      "definitions": [
        {
          "PropertyName": "Section Title",
          "PropertyAliasName": "sectionTitle",
          "ControlName": "Text",
          "IsIdentifier": true,
          "IsMandatory": true,
          "DataType": "string",
          "PropertyMaxLength": 200
        },
        {
          "PropertyName": "Section Subtitle",
          "PropertyAliasName": "sectionSubtitle",
          "ControlName": "Text",
          "IsIdentifier": false,
          "IsMandatory": false,
          "DataType": "string",
          "PropertyMaxLength": 500
        }
      ],
      "child_definitions": [
        {
          "PropertyName": "Question",
          "PropertyAliasName": "question",
          "ControlName": "Text",
          "IsIdentifier": true,
          "IsMandatory": true,
          "DataType": "string",
          "PropertyMaxLength": 200
        },
        {
          "PropertyName": "Answer",
          "PropertyAliasName": "answer",
          "ControlName": "RichText",
          "IsIdentifier": false,
          "IsMandatory": true,
          "DataType": "string"
        }
      ],
      "records": [
        {
          "sectionTitle": "Frequently Asked Questions",
          "sectionSubtitle": "Find answers to common questions",
          "childRecords": [
            {
              "question": "What is your return policy?",
              "answer": "<p>We offer 30-day returns on all products</p>"
            },
            {
              "question": "How do I contact support?",
              "answer": "<p>Email us at support@example.com</p>"
            }
          ]
        }
      ]
    }
  ],
  "implementation": {
    "pass_ids": "Parent MiBlock ID only",
    "child_linking": "Sub-records linked to parent record ID"
  }
}
```

---

## 5. Field Generation Algorithm

### Step-by-Step Process

```python
def generate_field_definitions(analyzed_elements):
    """Generate field definitions from analyzed HTML elements"""
    definitions = []
    is_first_field = True
    
    for element, info in analyzed_elements:
        # Determine field type
        field_type = determine_field_type(element, info)
        
        # Generate field name
        alias_name = suggest_field_name(element)
        display_name = to_display_name(alias_name)
        
        # Create base definition
        field_def = {
            "PropertyName": display_name,
            "PropertyAliasName": alias_name,
            "ControlName": field_type['ControlName'],
            "IsIdentifier": is_first_field,
            "IsMandatory": determine_if_mandatory(element, info),
            "DataType": field_type.get('DataType', 'string')
        }
        
        # Add type-specific properties
        if field_type['ControlName'] == 'File':
            field_def['ResourceTypeName'] = field_type['ResourceTypeName']
            field_def['PropertyMaxLength'] = 500
            
            # Add alt text field for images
            if field_type['ResourceTypeName'] == 'Image':
                definitions.append(field_def)
                
                # Create alt text field
                alt_field = {
                    "PropertyName": f"{display_name} Alt Text",
                    "PropertyAliasName": f"{alias_name}Alt",
                    "ControlName": "Text",
                    "IsIdentifier": False,
                    "IsMandatory": True,
                    "DataType": "string",
                    "PropertyMaxLength": 200
                }
                definitions.append(alt_field)
                is_first_field = False
                continue
        
        elif field_type['ControlName'] in ['Text', 'Number']:
            field_def['PropertyMaxLength'] = field_type.get('PropertyMaxLength', 500)
        
        definitions.append(field_def)
        is_first_field = False
    
    return definitions

def determine_if_mandatory(element, info):
    """Determine if field should be mandatory"""
    # Headlines are always mandatory
    if element.name in ['h1', 'h2', 'h3']:
        return True
    
    # Images are usually mandatory
    if info['type'] == 'file':
        return True
    
    # Links can be optional
    if info['type'] == 'link' and 'Url' in info.get('suggested_fields', [''])[0]:
        return False
    
    # Default: mandatory
    return True
```

---

## 6. Validation Checklist

Before finalizing field definitions:

- [ ] First field has `IsIdentifier: true`
- [ ] All other fields have `IsIdentifier: false`
- [ ] Image fields have matching alt text fields
- [ ] Link fields have both text and URL fields
- [ ] PropertyName is human-readable (spaces, PascalCase)
- [ ] PropertyAliasName is camelCase (no spaces)
- [ ] File fields have `ResourceTypeName`
- [ ] Text fields have `PropertyMaxLength`
- [ ] Mandatory fields marked appropriately
- [ ] No duplicate PropertyAliasName values

---

## Next Steps

- Read [Handlebars Templates](04_HANDLEBARS_TEMPLATES.md)
- Study [Best Practices](05_BEST_PRACTICES.md)
- Review complete [Examples](../examples/)

---

**Version**: 1.0  
**Last Updated**: 2026-01-31
