# HTML Analysis Logic

## Overview

This document details the algorithmic approach to analyzing HTML components and extracting field definitions.

---

## 1. HTML Parsing Strategy

### Step 1: Load and Parse HTML
```python
from bs4 import BeautifulSoup

def parse_html_component(html_content):
    """Parse HTML and return BeautifulSoup object"""
    soup = BeautifulSoup(html_content, 'html.parser')
    return soup
```

### Step 2: Identify Root Element
```python
def identify_root_element(soup):
    """
    Find the main component wrapper
    Usually: <section>, <div[data-component]>, <article>
    """
    # Priority order:
    root = (
        soup.find(attrs={'data-component': True}) or
        soup.find('section') or
        soup.find('article') or
        soup.find('div', class_=lambda x: x and 'component' in x.lower())
    )
    return root
```

---

## 2. Content Detection Algorithm

### Algorithm: Identify Editable Content

```python
def identify_editable_elements(root_element):
    """
    Scan HTML and classify elements as editable or static
    
    Returns:
        editable_elements: List of (element, field_info) tuples
    """
    editable_elements = []
    
    # Text Content Elements
    text_tags = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'span', 'a', 'button', 'label']
    for tag in root_element.find_all(text_tags):
        if has_meaningful_text(tag):
            element_info = {
                'type': 'text',
                'tag': tag.name,
                'text': tag.get_text(strip=True),
                'suggested_field': suggest_field_name(tag)
            }
            editable_elements.append((tag, element_info))
    
    # Image Elements
    for img in root_element.find_all('img'):
        if not is_decorative_image(img):
            element_info = {
                'type': 'file',
                'resource_type': 'Image',
                'src': img.get('src'),
                'alt': img.get('alt'),
                'suggested_field': 'image'
            }
            editable_elements.append((img, element_info))
    
    # Link Elements (separate URL and text)
    for link in root_element.find_all('a'):
        if has_meaningful_text(link):
            element_info = {
                'type': 'link',
                'href': link.get('href'),
                'text': link.get_text(strip=True),
                'suggested_fields': ['linkText', 'linkUrl']
            }
            editable_elements.append((link, element_info))
    
    return editable_elements

def has_meaningful_text(element):
    """Check if element contains actual content (not just whitespace)"""
    text = element.get_text(strip=True)
    return len(text) > 0 and not text.isspace()

def is_decorative_image(img):
    """Check if image is decorative (alt="" or role="presentation")"""
    return (
        img.get('alt') == '' or
        img.get('role') == 'presentation' or
        img.get('aria-hidden') == 'true'
    )
```

---

## 3. Field Name Generation

### Algorithm: Suggest Field Names

```python
import re

def suggest_field_name(element):
    """
    Generate camelCase field name from element
    
    Priority:
    1. data-field attribute
    2. Element text content
    3. Class name
    4. Tag name
    """
    # Check for explicit data attribute
    if element.get('data-field'):
        return to_camel_case(element['data-field'])
    
    # Generate from text content
    text = element.get_text(strip=True)
    if text and len(text) < 50:
        return generate_field_name_from_text(text)
    
    # Generate from class name
    classes = element.get('class', [])
    for cls in classes:
        if not cls.startswith('uk-') and not cls.startswith('feature-'):
            # Skip framework classes
            return to_camel_case(cls)
    
    # Fallback to tag-based name
    tag_names = {
        'h1': 'mainHeading',
        'h2': 'heading',
        'h3': 'subheading',
        'p': 'description',
        'button': 'buttonText',
        'a': 'linkText'
    }
    return tag_names.get(element.name, 'content')

def generate_field_name_from_text(text):
    """Generate field name from text content"""
    # Remove special characters
    clean_text = re.sub(r'[^a-zA-Z0-9\s]', '', text)
    
    # Take first few words
    words = clean_text.split()[:3]
    
    # Convert to camelCase
    if not words:
        return 'content'
    
    field_name = words[0].lower()
    for word in words[1:]:
        field_name += word.capitalize()
    
    return field_name

def to_camel_case(text):
    """Convert text to camelCase"""
    # Split on spaces, dashes, underscores
    words = re.split(r'[\s\-_]+', text)
    if not words:
        return 'field'
    
    # First word lowercase, rest capitalized
    camel = words[0].lower()
    for word in words[1:]:
        camel += word.capitalize()
    
    return camel
```

---

## 4. Field Type Detection

### Algorithm: Determine Field Type

```python
def determine_field_type(element, element_info):
    """
    Determine appropriate CMS field type
    
    Returns:
        field_definition: Dict with ControlName and properties
    """
    element_type = element_info['type']
    
    if element_type == 'text':
        return determine_text_field_type(element, element_info)
    elif element_type == 'file':
        return {
            'ControlName': 'File',
            'ResourceTypeName': element_info['resource_type'],
            'PropertyMaxLength': 500
        }
    elif element_type == 'link':
        return {
            'ControlName': 'Text',
            'PropertyMaxLength': 500
        }
    
    return {'ControlName': 'Text', 'PropertyMaxLength': 500}

def determine_text_field_type(element, element_info):
    """Determine if Text or RichText field"""
    text = element_info['text']
    text_length = len(text)
    
    # Short text → Text field
    if text_length < 200:
        return {
            'ControlName': 'Text',
            'PropertyMaxLength': 200,
            'DataType': 'string'
        }
    
    # Medium text → Text field with larger max
    elif text_length < 500:
        return {
            'ControlName': 'Text',
            'PropertyMaxLength': 500,
            'DataType': 'string'
        }
    
    # Long text or formatted content → RichText
    else:
        return {
            'ControlName': 'RichText',
            'DataType': 'string'
        }
```

---

## 5. Repeating Elements Detection

### Algorithm: Identify Repeating Sections

```python
def detect_repeating_sections(root_element):
    """
    Identify repeating sections (cards, list items, etc.)
    
    Returns:
        repeating_groups: List of (container, items) tuples
    """
    repeating_groups = []
    
    # Common repeating patterns
    patterns = [
        ('div', 'uk-card'),           # UIkit cards
        ('li', None),                  # List items
        ('article', None),             # Articles
        ('div', 'card'),               # Generic cards
        ('div', 'item'),               # Generic items
        ('div', 'col')                 # Grid columns
    ]
    
    for tag, class_hint in patterns:
        if class_hint:
            items = root_element.find_all(tag, class_=lambda x: x and class_hint in str(x))
        else:
            items = root_element.find_all(tag)
        
        # Check if siblings have similar structure
        if len(items) >= 2:
            if have_similar_structure(items):
                container = items[0].parent
                repeating_groups.append((container, items))
    
    return repeating_groups

def have_similar_structure(elements):
    """Check if elements have similar HTML structure"""
    if len(elements) < 2:
        return False
    
    # Compare tag structure
    first_structure = get_tag_structure(elements[0])
    
    for element in elements[1:]:
        structure = get_tag_structure(element)
        if not structures_match(first_structure, structure):
            return False
    
    return True

def get_tag_structure(element):
    """Get simplified structure of element"""
    structure = {
        'tag': element.name,
        'children': []
    }
    
    for child in element.find_all(recursive=False):
        if child.name:
            structure['children'].append(child.name)
    
    return structure

def structures_match(struct1, struct2, threshold=0.8):
    """Check if two structures are similar enough"""
    if struct1['tag'] != struct2['tag']:
        return False
    
    # Compare children (allow some variation)
    children1 = set(struct1['children'])
    children2 = set(struct2['children'])
    
    if not children1 and not children2:
        return True
    
    common = children1.intersection(children2)
    similarity = len(common) / max(len(children1), len(children2))
    
    return similarity >= threshold
```

---

## 6. Component Type Classification

### Algorithm: Classify Component

```python
def classify_component(root_element, editable_elements):
    """
    Classify component as Simple, Compound, or Nested
    
    Returns:
        component_type: 'simple', 'compound', or 'nested'
        miblocks: List of MiBlock definitions
    """
    # Step 1: Check if multiple separate sections (Compound)
    separate_sections = detect_separate_sections(root_element)
    
    if separate_sections and len(separate_sections) > 1:
        # Compound component - user combines multiple MiBlocks
        return 'compound', classify_compound_component(root_element, separate_sections)
    
    # Step 2: Check for repeating sections within same MiBlock
    repeating_sections = detect_repeating_sections(root_element)
    
    if repeating_sections:
        # Nested component - repeating within 1 MiBlock
        return 'nested', [create_nested_miblock(root_element, repeating_sections)]
    
    # Simple component - no multiple sections, no repeating
    return 'simple', [create_simple_miblock(editable_elements)]

def detect_separate_sections(root_element):
    """
    Detect if component has multiple separate sections that should be
    different MiBlocks (Compound pattern)
    
    Indicators:
    - Multiple semantic sections (header + content area)
    - Clear separation in HTML structure
    - User intention to combine separate components
    """
    sections = []
    
    # Look for distinct semantic sections
    semantic_tags = ['header', 'section', 'article', 'aside']
    for tag in semantic_tags:
        found = root_element.find_all(tag, recursive=False)
        if found:
            sections.extend(found)
    
    # Look for clear structural divisions
    if not sections:
        # Check for divs with component-like classes
        divs = root_element.find_all('div', recursive=False)
        for div in divs:
            classes = ' '.join(div.get('class', [])).lower()
            if any(indicator in classes for indicator in 
                   ['header', 'content', 'section', 'component']):
                sections.append(div)
    
    return sections if len(sections) > 1 else []

def is_nested_component(repeating_sections):
    """
    Determine if repeating sections are nested within parent
    
    Nested characteristics:
    - Repeating items within single semantic unit
    - Parent-child relationship (FAQ, Accordion, Tabs)
    - All items share common parent content
    
    Compound characteristics:
    - Separate semantic units that can stand alone
    - User combines multiple components
    - No inherent parent-child relationship
    """
    # Check if repeating section has parent content
    container, items = repeating_sections[0]
    
    # Look for parent-level content outside repeating items
    parent_content = get_content_outside_repeating(container, items)
    
    # Nested if:
    # 1. Has parent-level content (section title, etc.)
    # 2. Repeating items are semantically children (Q&A, accordion items)
    # 3. Pattern indicates parent-child (FAQ, tabs, accordion)
    if parent_content and is_parent_child_pattern(container, items):
        return True
    
    return False

def is_parent_child_pattern(container, items):
    """Check if structure indicates parent-child relationship"""
    # Common nested patterns
    nested_indicators = [
        'faq', 'accordion', 'tabs', 'collapse',
        'questions', 'answers', 'steps', 'timeline'
    ]
    
    # Check classes and attributes
    container_classes = ' '.join(container.get('class', [])).lower()
    
    for indicator in nested_indicators:
        if indicator in container_classes:
            return True
    
    # Check if items have consistent parent reference
    # (e.g., all items are within same semantic section)
    return has_semantic_parent(container, items)

def create_nested_miblock(root_element, repeating_sections):
    """Create MiBlock for nested component with parent-child records"""
    container, items = repeating_sections[0]
    
    # Parent fields (outside repeating section)
    parent_elements = get_content_outside_repeating(container, items)
    parent_fields = extract_fields_from_elements(parent_elements)
    
    # Child fields (from repeating items)
    child_elements = analyze_repeating_item_structure(items[0])
    child_fields = extract_fields_from_elements(child_elements)
    
    return {
        'type': 'nested',
        'parent_fields': parent_fields,
        'child_fields': child_fields,
        'implementation': {
            'pass_id': 'parent_miblock_id_only',
            'child_linking': 'parent_record_id'
        }
    }

def classify_compound_component(root_element, separate_sections):
    """
    Create MiBlocks for compound component
    
    Each MiBlock can be Simple or Nested internally
    """
    miblocks = []
    
    for section in separate_sections:
        # Check if this section has repeating content (Nested)
        section_repeating = detect_repeating_sections(section)
        
        if section_repeating:
            # This MiBlock is Nested
            nested_block = create_nested_miblock(section, section_repeating)
            nested_block['is_part_of_compound'] = True
            miblocks.append(nested_block)
        else:
            # This MiBlock is Simple
            section_elements = identify_editable_elements(section)
            simple_block = {
                'type': 'simple',
                'elements': section_elements,
                'is_part_of_compound': True
            }
            miblocks.append(simple_block)
    
    return miblocks
```

---

## 7. Comprehensive Analysis Function

### Complete Analysis Pipeline

```python
def analyze_html_component(html_content):
    """
    Complete analysis of HTML component
    
    Returns:
        analysis_result: Dict containing all analysis data
    """
    # Step 1: Parse HTML
    soup = parse_html_component(html_content)
    root = identify_root_element(soup)
    
    # Step 2: Identify editable content
    editable_elements = identify_editable_elements(root)
    
    # Step 3: Detect repeating sections
    repeating_sections = detect_repeating_sections(root)
    
    # Step 4: Classify component (simple, compound, or nested)
    component_type, miblocks = classify_component(root, editable_elements)
    
    # Step 5: Generate field definitions
    field_definitions = []
    for element, info in editable_elements:
        field_type = determine_field_type(element, info)
        field_name = suggest_field_name(element)
        
        field_def = {
            'PropertyName': to_display_name(field_name),
            'PropertyAliasName': field_name,
            **field_type
        }
        field_definitions.append(field_def)
    
    # Step 6: Create analysis result
    result = {
        'component_type': component_type,
        'root_element': root.name,
        'editable_count': len(editable_elements),
        'repeating_sections': len(repeating_sections),
        'miblocks': miblocks,
        'field_definitions': field_definitions
    }
    
    # Step 7: Add implementation details
    if component_type == 'simple':
        result['implementation'] = {
            'pass_ids': '1 MiBlock ID',
            'relationship': 'none'
        }
    elif component_type == 'compound':
        result['implementation'] = {
            'pass_ids': 'ALL MiBlock IDs',
            'relationship': 'independent components'
        }
    elif component_type == 'nested':
        result['implementation'] = {
            'pass_ids': 'Parent MiBlock ID only',
            'relationship': 'parent-child linked',
            'child_linking': 'parent_record_id'
        }
    
    return result

def to_display_name(camel_case_name):
    """Convert camelCase to Display Name"""
    # Insert spaces before capitals
    spaced = re.sub(r'([A-Z])', r' \1', camel_case_name)
    # Capitalize first letter of each word
    return ' '.join(word.capitalize() for word in spaced.split())
```

---

## 8. Practical Examples

### Example 1: Simple Component

#### Input HTML:
```html
<section class="uk-section">
    <h2>Welcome to Our Platform</h2>
    <p>Discover amazing features</p>
    <button>Get Started</button>
    <img src="/hero.jpg" alt="Hero image">
</section>
```

#### Analysis Output:
```python
{
    'component_type': 'simple',
    'editable_count': 4,
    'implementation': {
        'pass_ids': '1 MiBlock ID',
        'relationship': 'none'
    },
    'field_definitions': [
        {
            'PropertyName': 'Welcome To Our Platform',
            'PropertyAliasName': 'welcomeToOurPlatform',
            'ControlName': 'Text',
            'IsIdentifier': True,
            'PropertyMaxLength': 200
        },
        # ... more fields
    ]
}
```

---

### Example 2: Compound Component

#### Input HTML:
```html
<section>
    <!-- Header component (separate) -->
    <h2>Our Features</h2>
    <p>What we offer</p>
    
    <!-- Feature cards (separate repeating component) -->
    <div class="uk-grid">
        <div class="uk-card">
            <h3>Fast</h3>
            <p>Lightning speed</p>
        </div>
        <div class="uk-card">
            <h3>Secure</h3>
            <p>Bank-level security</p>
        </div>
    </div>
</section>
```

#### Analysis Output:
```python
{
    'component_type': 'compound',
    'miblocks': [
        {
            'type': 'header',
            'is_separate_component': True
        },
        {
            'type': 'repeating',
            'is_separate_component': True
        }
    ],
    'implementation': {
        'pass_ids': 'ALL MiBlock IDs',
        'relationship': 'independent components'
    }
}
```

---

### Example 3: Nested Component

#### Input HTML:
```html
<section class="faq-section">
    <!-- Parent content -->
    <h2>Frequently Asked Questions</h2>
    <p>Find answers to common questions</p>
    
    <!-- Nested repeating items -->
    <div class="accordion">
        <div class="faq-item">
            <h3>What is your return policy?</h3>
            <p>We offer 30-day returns</p>
        </div>
        <div class="faq-item">
            <h3>How do I contact support?</h3>
            <p>Email us at support@example.com</p>
        </div>
        <div class="faq-item">
            <h3>Do you ship internationally?</h3>
            <p>Yes, we ship worldwide</p>
        </div>
    </div>
</section>
```

#### Analysis Output:
```python
{
    'component_type': 'nested',
    'miblocks': [
        {
            'type': 'nested',
            'parent_fields': [
                {
                    'PropertyName': 'Section Title',
                    'PropertyAliasName': 'sectionTitle',
                    'ControlName': 'Text',
                    'IsIdentifier': True
                },
                {
                    'PropertyName': 'Section Subtitle',
                    'PropertyAliasName': 'sectionSubtitle',
                    'ControlName': 'Text'
                }
            ],
            'child_fields': [
                {
                    'PropertyName': 'Question',
                    'PropertyAliasName': 'question',
                    'ControlName': 'Text',
                    'IsIdentifier': True
                },
                {
                    'PropertyName': 'Answer',
                    'PropertyAliasName': 'answer',
                    'ControlName': 'Text'
                }
            ],
            'implementation': {
                'pass_id': 'parent_miblock_id_only',
                'child_linking': 'parent_record_id'
            }
        }
    ],
    'implementation': {
        'pass_ids': 'Parent MiBlock ID only',
        'relationship': 'parent-child linked',
        'child_linking': 'parent_record_id'
    }
}
```

---

## Next Steps

- Read [Field Definition Guide](03_FIELD_DEFINITION_GUIDE.md)
- Study [Handlebars Templates](04_HANDLEBARS_TEMPLATES.md)
- Review [Best Practices](05_BEST_PRACTICES.md)

---

**Version**: 1.0  
**Last Updated**: 2026-01-31
