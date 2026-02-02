# rProject - HTML to CMS Definition Generator

## Overview

This project contains the core logic and patterns for automatically generating CMS field definitions from HTML sections. It's a refactored and improved version of the AgenticComponentGenerator, focusing on clean architecture and reusability.

## Purpose

Extract field definitions from HTML components to create:
- **MiBlock Definitions**: Field structure for CMS data components
- **Handlebars Templates**: Dynamic templates with data bindings
- **Sample Records**: Realistic sample data for testing

## Project Structure

```
rProject/
├── README.md                          # This file
├── docs/
│   ├── 01_CORE_CONCEPTS.md           # Fundamental concepts
│   ├── 02_HTML_ANALYSIS_LOGIC.md     # HTML parsing and analysis
│   ├── 03_FIELD_DEFINITION_GUIDE.md  # Creating field definitions
│   ├── 04_HANDLEBARS_TEMPLATES.md    # Template generation
│   └── 05_BEST_PRACTICES.md          # Patterns and anti-patterns
├── examples/
│   ├── simple_component.html         # Simple component example
│   ├── nested_component.html         # Nested component example (FAQ)
│   ├── compound_component.html       # Compound component example
│   ├── simple_component.json         # Generated payload
│   ├── nested_component.json         # Generated payload
│   └── compound_component.json       # Generated payload
└── schemas/
    ├── field_definition.schema.json  # JSON schema for field defs
    ├── miblock.schema.json           # JSON schema for MiBlocks
    └── payload.schema.json           # JSON schema for payloads
```

## Key Features

1. **Automatic Content Detection**: Identifies editable vs static content
2. **Smart Field Typing**: Determines appropriate field types (Text, File, RichText)
3. **Three Component Types**: 
   - **Simple**: Single MiBlock for non-repeating content
   - **Nested**: Repeating sections within 1 MiBlock (parent-child relationship)
   - **Compound**: Multiple separate MiBlocks combined by user
4. **Template Generation**: Converts HTML to Handlebars with proper bindings
5. **Validation**: JSON schemas for all data structures
6. **Best Practices**: Battle-tested patterns from production use

## Quick Start

1. Read [Core Concepts](docs/01_CORE_CONCEPTS.md) to understand the fundamentals
2. Study [HTML Analysis Logic](docs/02_HTML_ANALYSIS_LOGIC.md) for parsing patterns
3. Review [Field Definition Guide](docs/03_FIELD_DEFINITION_GUIDE.md) for creating definitions
4. Check [Examples](examples/) for real-world use cases

## Use Cases

- **Automated CMS Migration**: Convert static HTML to dynamic CMS components
- **Component Library Generation**: Create reusable component definitions
- **Documentation**: Generate field documentation from HTML
- **Validation**: Ensure HTML structure matches CMS requirements

## Technologies

- **HTML Parsing**: BeautifulSoup4, lxml
- **Schema Validation**: JSON Schema
- **Template Engine**: Handlebars.js
- **CMS Platform**: Milestone CMS (adaptable to others)

## Contributing

This is a reference implementation. Use it as a foundation for your own version with:
- Improved error handling
- Better type detection algorithms
- Custom field type mappings
- Your preferred tech stack

## License

Internal use - based on AgenticComponentGenerator

## Related Projects

- **AgenticComponentGenerator**: Original implementation
- **Figma-to-CMS**: Upstream Figma integration

---

**Version**: 1.0  
**Created**: 2026-01-31  
**Purpose**: Core logic extraction for HTML-to-CMS definition generation
