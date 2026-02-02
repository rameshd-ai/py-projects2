# Quick Start: 30-Minute Implementation

## Goal
Build a working MVP in 30 minutes using the documented logic.

---

## Setup (5 minutes)

```bash
# Create project
mkdir my-html-cms-generator
cd my-html-cms-generator

# Install dependencies
pip install beautifulsoup4 lxml

# Create files
touch analyzer.py
touch test_input.html
```

---

## Implementation (20 minutes)

### Step 1: Create `analyzer.py`

```python
from bs4 import BeautifulSoup
import json
import re

def analyze_html(html_content, component_name, category_id=21):
    """Simple HTML to CMS payload generator"""
    
    # Parse HTML
    soup = BeautifulSoup(html_content, 'html.parser')
    root = soup.find('section') or soup.find('div')
    
    # Find editable elements
    definitions = []
    sample_data = {}
    is_first = True
    
    # Headings
    for tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
        for element in root.find_all(tag):
            text = element.get_text(strip=True)
            if text:
                field_name = f"{tag}Text" if is_first else f"{tag}Text{len(definitions)}"
                definitions.append({
                    "PropertyName": text[:20] + "..." if len(text) > 20 else text,
                    "PropertyAliasName": to_camel_case(field_name),
                    "ControlName": "Text",
                    "IsIdentifier": is_first,
                    "IsMandatory": True,
                    "DataType": "string",
                    "PropertyMaxLength": 200
                })
                sample_data[to_camel_case(field_name)] = text
                is_first = False
    
    # Paragraphs
    for p in root.find_all('p'):
        text = p.get_text(strip=True)
        if text:
            field_name = f"description{len(definitions)}"
            definitions.append({
                "PropertyName": "Description",
                "PropertyAliasName": to_camel_case(field_name),
                "ControlName": "Text",
                "IsIdentifier": False,
                "IsMandatory": True,
                "DataType": "string",
                "PropertyMaxLength": 500
            })
            sample_data[to_camel_case(field_name)] = text
    
    # Images
    for img in root.find_all('img'):
        if img.get('alt') != '':
            field_name = f"image{len(definitions)}"
            definitions.append({
                "PropertyName": "Image",
                "PropertyAliasName": to_camel_case(field_name),
                "ControlName": "File",
                "IsIdentifier": False,
                "IsMandatory": True,
                "DataType": "string",
                "ResourceTypeName": "Image",
                "PropertyMaxLength": 500
            })
            sample_data[to_camel_case(field_name)] = [img.get('src', 'https://via.placeholder.com/600')]
            
            # Alt text
            definitions.append({
                "PropertyName": "Image Alt Text",
                "PropertyAliasName": to_camel_case(field_name + "Alt"),
                "ControlName": "Text",
                "IsIdentifier": False,
                "IsMandatory": True,
                "DataType": "string",
                "PropertyMaxLength": 200
            })
            sample_data[to_camel_case(field_name + "Alt")] = img.get('alt', 'Image description')
    
    # Buttons
    for btn in root.find_all(['button', 'a'], class_=lambda x: x and 'button' in str(x).lower()):
        text = btn.get_text(strip=True)
        if text:
            field_name = f"buttonText{len(definitions)}"
            definitions.append({
                "PropertyName": "Button Text",
                "PropertyAliasName": to_camel_case(field_name),
                "ControlName": "Text",
                "IsIdentifier": False,
                "IsMandatory": True,
                "DataType": "string",
                "PropertyMaxLength": 50
            })
            sample_data[to_camel_case(field_name)] = text
            
            # Button link
            if btn.name == 'a' and btn.get('href'):
                link_field = f"buttonLink{len(definitions)}"
                definitions.append({
                    "PropertyName": "Button Link",
                    "PropertyAliasName": to_camel_case(link_field),
                    "ControlName": "Text",
                    "IsIdentifier": False,
                    "IsMandatory": False,
                    "DataType": "string",
                    "PropertyMaxLength": 500
                })
                sample_data[to_camel_case(link_field)] = btn.get('href', '#')
    
    # Build payload
    component_alias = to_kebab_case(component_name)
    
    payload = {
        "component_name": f"ag_{component_alias}",
        "component_type": "simple",
        "category_id": category_id,
        "description": f"Auto-generated component: {component_name}",
        "miblocks": [{
            "component_name": f"AG {component_name}",
            "component_alias_name": f"ag-{component_alias}",
            "definitions": definitions,
            "records": [{
                "RecordJsonString": sample_data,
                "Status": True,
                "DisplayOrder": 1
            }]
        }],
        "css": {
            "fileName": f"ag-{component_alias}-styles",
            "content": "/* Component styles */"
        },
        "format": {
            "formatName": f"AG {component_name} Format",
            "formatKey": f"ag-{component_alias}-format",
            "formatContent": create_simple_template(str(root), definitions, f"ag-{component_alias}")
        },
        "vcomponent": {
            "name": f"AG {component_name} Component",
            "alias": f"ag-{component_alias}-component",
            "description": f"Auto-generated component: {component_name}",
            "categoryId": category_id,
            "isActive": True,
            "interactionType": "None"
        }
    }
    
    return payload

def to_camel_case(text):
    """Convert to camelCase"""
    words = re.split(r'[\s\-_]+', text.lower())
    return words[0] + ''.join(w.capitalize() for w in words[1:]) if words else 'field'

def to_kebab_case(text):
    """Convert to kebab-case"""
    text = re.sub(r'(?<!^)(?=[A-Z])', '-', text).lower()
    return re.sub(r'[\s_]+', '-', text)

def create_simple_template(html, definitions, alias):
    """Create basic Handlebars template"""
    # Simple replacement (you'd improve this)
    template = html
    
    # Add edit marker to first heading
    template = re.sub(
        r'(<h[1-6][^>]*>)',
        r'\1 %%componentRecordEditable%%',
        template,
        count=1
    )
    
    # Replace content with placeholders (simplified)
    # In production, you'd parse and replace more carefully
    
    return f"{{{{#each ComponentRecordJson.{alias}}}}}\n{template}\n{{{{/each}}}}"

# Usage
if __name__ == "__main__":
    # Read HTML
    with open('test_input.html', 'r') as f:
        html = f.read()
    
    # Generate payload
    payload = analyze_html(html, "Test Component", category_id=21)
    
    # Save
    with open('output.json', 'w') as f:
        json.dump(payload, f, indent=2)
    
    print(f"✅ Generated payload with {len(payload['miblocks'][0]['definitions'])} fields")
```

### Step 2: Create `test_input.html`

```html
<section class="uk-section">
  <div class="uk-container">
    <h2>Welcome to Our Service</h2>
    <p>This is a description of our amazing service.</p>
    <img src="image.jpg" alt="Service screenshot">
    <a href="/learn-more" class="uk-button">Learn More</a>
  </div>
</section>
```

---

## Test (5 minutes)

```bash
# Run the analyzer
python analyzer.py

# Check output
cat output.json

# Verify:
# ✅ Has definitions
# ✅ Has sample data
# ✅ Has template
# ✅ Category ID is 21
```

---

## What You Built

In 30 minutes, you created:
- ✅ HTML parser
- ✅ Field generator
- ✅ Payload assembler
- ✅ Working MVP

**Next**: Improve it using the full documentation in `rProject/docs/`

---

## Improvements to Add

### Week 1
- Better field name generation
- Smarter type detection
- Handle more HTML patterns

### Week 2
- Compound component detection
- Better template generation
- Add validation

### Week 3
- CLI interface
- Configuration system
- Unit tests

### Week 4
- Error handling
- Logging
- Documentation
- Production ready!

---

**Created**: 2026-01-31  
**Difficulty**: Beginner  
**Time**: 30 minutes  
**Result**: Working MVP
