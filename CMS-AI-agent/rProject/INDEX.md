# rProject - Quick Reference Index

## 📖 Documentation Guide

### Start Here
1. [README.md](README.md) - Project overview
2. [GETTING_STARTED.md](GETTING_STARTED.md) - Quick start guide

### Core Documentation (Read in Order)

| # | Document | Focus | Read Time |
|---|----------|-------|-----------|
| 1 | [Core Concepts](docs/01_CORE_CONCEPTS.md) | Fundamental principles | 15 min |
| 2 | [HTML Analysis Logic](docs/02_HTML_ANALYSIS_LOGIC.md) | Parsing algorithms | 20 min |
| 3 | [Field Definition Guide](docs/03_FIELD_DEFINITION_GUIDE.md) | Creating fields | 15 min |
| 4 | [Handlebars Templates](docs/04_HANDLEBARS_TEMPLATES.md) | Template creation | 15 min |
| 5 | [Best Practices](docs/05_BEST_PRACTICES.md) | Lessons learned | 15 min |

**Total reading time**: ~80 minutes

---

## 🎯 Quick Lookup

### By Task

| What You Want To Do | Where To Look |
|---------------------|---------------|
| Understand the basics | [01_CORE_CONCEPTS.md](docs/01_CORE_CONCEPTS.md) |
| Write HTML parser | [02_HTML_ANALYSIS_LOGIC.md](docs/02_HTML_ANALYSIS_LOGIC.md) |
| Create field definitions | [03_FIELD_DEFINITION_GUIDE.md](docs/03_FIELD_DEFINITION_GUIDE.md) |
| Generate templates | [04_HANDLEBARS_TEMPLATES.md](docs/04_HANDLEBARS_TEMPLATES.md) |
| Avoid common mistakes | [05_BEST_PRACTICES.md](docs/05_BEST_PRACTICES.md) |
| See working examples | [examples/](examples/) |
| Validate JSON | [schemas/](schemas/) |

### By Concept

| Concept | Primary Doc | Section |
|---------|-------------|---------|
| Simple vs Compound | Core Concepts | Section 3 |
| Field Types | Field Definition Guide | Section 2 |
| Content Classification | HTML Analysis Logic | Section 2 |
| Identifier Field | Core Concepts | Section 5 |
| Edit Markers | Handlebars Templates | Section 4 |
| Image/Alt Pairing | Best Practices | Section 1 |
| Category IDs | Best Practices | Section 5 |
| Naming Conventions | Best Practices | Section 4 |

---

## 📚 Document Details

### 01_CORE_CONCEPTS.md
**Size**: 7 KB | **Sections**: 10

**Key Topics**:
- Transformation pipeline
- Content classification (dynamic vs static)
- Component types (simple vs compound)
- Field types overview
- Key principles
- Template binding basics
- Decision trees
- Common patterns

**Best For**: Understanding fundamentals

---

### 02_HTML_ANALYSIS_LOGIC.md
**Size**: 13 KB | **Sections**: 8

**Key Topics**:
- HTML parsing strategy
- Content detection algorithms (Python code)
- Field name generation
- Field type detection
- Repeating elements detection
- Component classification
- Complete analysis pipeline
- Practical examples

**Best For**: Implementing parsers

---

### 03_FIELD_DEFINITION_GUIDE.md
**Size**: 13 KB | **Sections**: 6

**Key Topics**:
- Field definition structure
- All field types (Text, RichText, File, Number, Boolean, Date)
- Field creation rules
- Identifier fields
- Naming conventions
- Image/Link pairing
- Complete examples
- Validation checklist

**Best For**: Creating field definitions

---

### 04_HANDLEBARS_TEMPLATES.md
**Size**: 13 KB | **Sections**: 10

**Key Topics**:
- Template structure
- Data binding rules
- Component alias naming
- Edit marker placement
- Preserving HTML structure
- Conditional content
- Complete examples (simple & compound)
- Special Handlebars syntax
- Transformation algorithms
- Validation checklist

**Best For**: Generating templates

---

### 05_BEST_PRACTICES.md
**Size**: 11 KB | **Sections**: 11

**Key Topics**:
- Field definition best practices
- Component structure patterns
- Template best practices
- Naming conventions
- Category selection
- Error prevention
- Common mistakes to avoid
- Performance optimization
- Accessibility guidelines
- Testing checklist
- Production lessons learned

**Best For**: Avoiding pitfalls

---

## 📁 Examples

### simple_component.html (1.1 KB)
Hero section with:
- Main heading
- Subheading
- Two CTA buttons
- Background image

### simple_component.json (5.3 KB)
Complete payload showing:
- 7 field definitions
- 1 sample record
- Handlebars template
- CSS content
- VComponent metadata

### compound_component.html (3.7 KB)
Feature cards with:
- Header section (title + subtitle)
- 3 repeating cards (icon, title, description, link)

---

## 🔧 Schemas

### field_definition.schema.json (2.1 KB)
JSON Schema for validating field definitions with:
- Required properties
- Type validation
- Pattern matching (naming conventions)
- Conditional requirements

---

## 📊 Statistics

### Total Files: 11

**Documentation**: 7 files (~63 KB)
**Examples**: 3 files (~10 KB)
**Schemas**: 1 file (~2 KB)

**Total Content**: ~75 KB of reference material

---

## 🔍 Search Index

### Algorithms
- HTML Parsing: `02_HTML_ANALYSIS_LOGIC.md` → Section 1
- Content Detection: `02_HTML_ANALYSIS_LOGIC.md` → Section 2
- Field Name Generation: `02_HTML_ANALYSIS_LOGIC.md` → Section 3
- Field Type Detection: `02_HTML_ANALYSIS_LOGIC.md` → Section 4
- Repeating Sections: `02_HTML_ANALYSIS_LOGIC.md` → Section 5

### Patterns
- Simple Component: `01_CORE_CONCEPTS.md` → Section 10
- Compound Component: `01_CORE_CONCEPTS.md` → Section 10
- Hero Section: `examples/simple_component.*`
- Feature Cards: `examples/compound_component.html`

### Rules
- Identifier Field: `03_FIELD_DEFINITION_GUIDE.md` → Section 3, Rule 1
- Naming Conventions: `03_FIELD_DEFINITION_GUIDE.md` → Section 3, Rule 2
- Image Pairing: `03_FIELD_DEFINITION_GUIDE.md` → Section 3, Rule 3
- Edit Markers: `04_HANDLEBARS_TEMPLATES.md` → Section 4

### Common Issues
- Category ID Problems: `05_BEST_PRACTICES.md` → Section 11
- Template Wrapping: `05_BEST_PRACTICES.md` → Section 7
- Multiple Edit Markers: `05_BEST_PRACTICES.md` → Section 7
- Image Arrays: `05_BEST_PRACTICES.md` → Section 6

---

## 🎓 Learning Paths

### Beginner Path
1. README.md
2. 01_CORE_CONCEPTS.md
3. examples/simple_component.*
4. 03_FIELD_DEFINITION_GUIDE.md (Sections 1-2)

### Intermediate Path
1. 02_HTML_ANALYSIS_LOGIC.md
2. 03_FIELD_DEFINITION_GUIDE.md (Complete)
3. 04_HANDLEBARS_TEMPLATES.md (Sections 1-6)
4. examples/compound_component.html

### Advanced Path
1. 02_HTML_ANALYSIS_LOGIC.md (Complete)
2. 04_HANDLEBARS_TEMPLATES.md (Complete)
3. 05_BEST_PRACTICES.md (Complete)
4. All examples + Build your own

---

## 💻 Code Examples

### Python
- `02_HTML_ANALYSIS_LOGIC.md`: 8 complete functions
- Topics: Parsing, detection, classification, naming

### Handlebars
- `04_HANDLEBARS_TEMPLATES.md`: 3 complete templates
- Topics: Simple, compound, conditional content

### JSON
- `examples/`: 1 complete payload
- `schemas/`: 1 validation schema

---

## 🔗 Cross-References

### Most Referenced Topics

1. **Identifier Field**: Referenced in 4 documents
2. **Edit Markers**: Referenced in 3 documents
3. **Image Pairing**: Referenced in 3 documents
4. **Component Types**: Referenced in 5 documents
5. **Field Types**: Referenced in 4 documents

---

## 📝 Checklists

Available checklists:
- Analysis Checklist: `01_CORE_CONCEPTS.md` → Section 9
- Field Validation: `03_FIELD_DEFINITION_GUIDE.md` → Section 6
- Template Validation: `04_HANDLEBARS_TEMPLATES.md` → Section 10
- Testing Checklist: `05_BEST_PRACTICES.md` → Section 10

---

## 🚀 Next Steps

After reading this documentation:

1. **Understand**: Read docs 01-05
2. **Analyze**: Study the examples
3. **Practice**: Analyze your own HTML
4. **Build**: Implement your version
5. **Improve**: Add your enhancements

---

**Last Updated**: 2026-01-31  
**Total Documentation**: 11 files, ~75 KB  
**Status**: ✅ Complete & Ready
