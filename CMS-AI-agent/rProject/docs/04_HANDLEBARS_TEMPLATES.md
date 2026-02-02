# Handlebars Templates Guide

## Overview

This guide explains how to transform HTML into Handlebars templates with proper data bindings and edit markers.

---

## 1. Template Structure

### Basic Template Pattern

```handlebars
{{#each ComponentRecordJson.component-alias}}
  <!-- HTML structure with data bindings -->
  <element %%componentRecordEditable%%>{{data.fieldName}}</element>
{{/each}}
```

**Key elements**:
- `{{#each}}` loop wrapper
- `ComponentRecordJson.component-alias` path
- `{{data.fieldName}}` data bindings
- `%%componentRecordEditable%%` edit marker

---

## 2. Data Binding Rules

### Rule 1: Use `data.` Prefix

All field access uses `{{data.fieldName}}`:

```handlebars
✅ CORRECT:
{{data.headline}}
{{data.buttonText}}
{{data.image}}

❌ WRONG:
{{headline}}
{{VCompJson.headline}}
{{this.headline}}
```

### Rule 2: Match Field Aliases Exactly

PropertyAliasName from definitions must match template bindings (case-sensitive):

```json
// Field definition
{
  "PropertyAliasName": "primaryCtaText"
}
```

```handlebars
<!-- Template (MUST match) -->
{{data.primaryCtaText}}
```

### Rule 3: Image URLs

Images are stored as arrays but accessed as strings in templates:

```json
// Record data
{
  "heroImage": ["https://example.com/image.jpg"]
}
```

```handlebars
<!-- Template (CMS handles array→string) -->
<img src="{{data.heroImage}}" alt="{{data.heroImageAlt}}">
```

---

## 3. Component Alias Naming

### Alias WITHOUT "-mi-block" Suffix

```json
// MiBlock definition
{
  "component_alias_name": "ag-hero-section"  // ← Use this
}
```

```handlebars
<!-- Template uses alias WITHOUT suffix -->
{{#each ComponentRecordJson.ag-hero-section}}
  <!-- NOT: ag-hero-section-mi-block -->
{{/each}}
```

**⚠️ Common Mistake**: Adding `-mi-block` suffix in templates (CMS adds this internally)

---

## 4. Edit Marker Placement

### Simple Component: ONE Marker Total

Place `%%componentRecordEditable%%` on the FIRST text element only:

```handlebars
{{#each ComponentRecordJson.ag-hero-section}}
  <section class="uk-section">
    <!-- ⭐ Marker on FIRST text element -->
    <h1 class="uk-heading" %%componentRecordEditable%%>
      {{data.mainHeading}}
    </h1>
    
    <!-- ✅ No marker needed - CMS auto-enables ALL fields -->
    <p class="uk-text-lead">
      {{data.subheading}}
    </p>
    
    <!-- ✅ No marker needed -->
    <a href="{{data.ctaLink}}" class="uk-button">
      {{data.ctaText}}
    </a>
  </section>
{{/each}}
```

### Compound Component: ONE Marker Per MiBlock

Each `{{#each}}` loop gets ONE marker on its first text element:

```handlebars
<!-- Header MiBlock -->
{{#each ComponentRecordJson.ag-cards-header}}
  <div class="uk-section">
    <!-- ⭐ Marker #1: Header section -->
    <h2 class="uk-heading" %%componentRecordEditable%%>
      {{data.sectionTitle}}
    </h2>
    
    <!-- ✅ No marker - auto-enabled -->
    <p>{{data.sectionSubtitle}}</p>
  </div>
{{/each}}

<!-- Items MiBlock -->
<div class="uk-grid" uk-grid>
  {{#each ComponentRecordJson.ag-card-item}}
    <div class="uk-width-1-3@m">
      <div class="uk-card">
        <!-- ⭐ Marker #2: Card items -->
        <h3 class="uk-card-title" %%componentRecordEditable%%>
          {{data.cardTitle}}
        </h3>
        
        <!-- ✅ No marker - auto-enabled -->
        <p>{{data.cardDescription}}</p>
      </div>
    </div>
  {{/each}}
</div>
```

---

## 5. Preserving HTML Structure

### Keep All Static Content

**DO NOT remove or modify**:
- HTML tags (divs, sections, etc.)
- CSS classes (especially `uk-*` framework classes)
- Data attributes (`uk-grid`, `data-*`)
- ARIA attributes (`aria-label`, `role`)
- Structure elements (wrappers, containers)

```handlebars
✅ CORRECT - All classes preserved:
<section class="uk-section uk-section-large uk-light" data-component="hero">
  <div class="uk-container uk-position-relative">
    <div class="uk-grid uk-grid-large uk-flex-middle" uk-grid>
      <div class="uk-width-1-2@m">
        <h2 class="uk-heading-medium">{{data.headline}}</h2>
      </div>
    </div>
  </div>
</section>

❌ WRONG - Classes removed:
<section>
  <div>
    <h2>{{data.headline}}</h2>
  </div>
</section>
```

---

## 6. Conditional Content

### Using `{{#if}}` for Optional Fields

```handlebars
{{#each ComponentRecordJson.ag-component}}
  <section>
    <h2>{{data.heading}}</h2>
    
    <!-- Optional subtitle -->
    {{#if data.subtitle}}
      <p class="subtitle">{{data.subtitle}}</p>
    {{/if}}
    
    <!-- Optional CTA button -->
    {{#if data.ctaLink}}
      <a href="{{data.ctaLink}}" class="uk-button">
        {{data.ctaText}}
      </a>
    {{else}}
      <button class="uk-button" type="button">
        {{data.ctaText}}
      </button>
    {{/if}}
  </section>
{{/each}}
```

**Use `{{#if}}` when**:
- Field is not mandatory
- Content appears conditionally
- Switching between elements (button vs link)

---

## 7. Complete Examples

### Example 1: Simple Hero Section

```handlebars
{{#each ComponentRecordJson.ag-hero-section}}
<section class="uk-section uk-section-large uk-background-cover uk-light" 
         style="background-image: url('{{data.backgroundImage}}');">
  
  <div class="uk-container">
    <div class="uk-text-center">
      
      <!-- Edit marker on first text element -->
      <h1 class="uk-heading-xlarge uk-margin-remove-top" %%componentRecordEditable%%>
        {{data.mainHeading}}
      </h1>
      
      <!-- No marker needed - auto-enabled -->
      <p class="uk-text-lead uk-margin-medium-top">
        {{data.subheading}}
      </p>
      
      <!-- Button with conditional link -->
      {{#if data.ctaLink}}
        <a href="{{data.ctaLink}}" 
           class="uk-button uk-button-primary uk-button-large uk-margin-medium-top">
          {{data.ctaText}}
        </a>
      {{else}}
        <button class="uk-button uk-button-primary uk-button-large uk-margin-medium-top" 
                type="button">
          {{data.ctaText}}
        </button>
      {{/if}}
      
    </div>
  </div>
  
</section>
{{/each}}
```

### Example 2: Compound Feature Cards

```handlebars
<!-- Header Section -->
{{#each ComponentRecordJson.ag-features-header}}
<div class="uk-section">
  <div class="uk-container">
    <div class="uk-text-center">
      
      <!-- Marker for header section -->
      <h2 class="uk-heading-medium uk-margin-remove-top" %%componentRecordEditable%%>
        {{data.sectionTitle}}
      </h2>
      
      {{#if data.sectionSubtitle}}
        <p class="uk-text-lead uk-margin-medium-top">
          {{data.sectionSubtitle}}
        </p>
      {{/if}}
      
    </div>
  </div>
</div>
{{/each}}

<!-- Cards Grid -->
<div class="uk-section uk-section-muted">
  <div class="uk-container">
    <div class="uk-grid-match uk-child-width-1-3@m uk-child-width-1-2@s" uk-grid>
      
      {{#each ComponentRecordJson.ag-feature-card}}
      <div>
        <div class="uk-card uk-card-default uk-card-hover uk-card-body">
          
          <!-- Icon -->
          <div class="uk-margin-bottom">
            <img src="{{data.cardIcon}}" 
                 alt="{{data.cardIconAlt}}" 
                 class="uk-width-small">
          </div>
          
          <!-- Marker for each card -->
          <h3 class="uk-card-title" %%componentRecordEditable%%>
            {{data.cardTitle}}
          </h3>
          
          <p>{{data.cardDescription}}</p>
          
          {{#if data.cardLink}}
            <a href="{{data.cardLink}}" class="uk-button uk-button-text">
              {{data.cardLinkText}}
              <span uk-icon="arrow-right"></span>
            </a>
          {{/if}}
          
        </div>
      </div>
      {{/each}}
      
    </div>
  </div>
</div>
```

### Example 3: Image + Text Section

```handlebars
{{#each ComponentRecordJson.ag-image-text}}
<section class="uk-section">
  <div class="uk-container">
    <div class="uk-grid-large uk-flex-middle" uk-grid>
      
      <!-- Image Column -->
      <div class="uk-width-1-2@m">
        <div class="uk-panel">
          <img src="{{data.featureImage}}" 
               alt="{{data.featureImageAlt}}" 
               class="uk-width-1-1"
               loading="lazy">
        </div>
      </div>
      
      <!-- Text Column -->
      <div class="uk-width-1-2@m">
        <div class="uk-panel">
          
          <h2 class="uk-heading-medium" %%componentRecordEditable%%>
            {{data.heading}}
          </h2>
          
          <div class="uk-margin-medium-top">
            {{{data.bodyText}}}
          </div>
          
          {{#if data.ctaLink}}
            <div class="uk-margin-medium-top">
              <a href="{{data.ctaLink}}" class="uk-button uk-button-primary">
                {{data.ctaText}}
              </a>
            </div>
          {{/if}}
          
        </div>
      </div>
      
    </div>
  </div>
</section>
{{/each}}
```

---

## 8. Special Handlebars Syntax

### Triple Braces for HTML Content

Use `{{{` for RichText fields (renders HTML):

```handlebars
<!-- Double braces - escapes HTML -->
<div>{{data.content}}</div>
Output: &lt;p&gt;Bold text&lt;/p&gt;

<!-- Triple braces - renders HTML -->
<div>{{{data.content}}}</div>
Output: <p>Bold text</p>
```

### Loops with Index

```handlebars
{{#each ComponentRecordJson.ag-items}}
  <div data-index="{{@index}}">
    <h3>Item {{@index}}: {{data.title}}</h3>
  </div>
{{/each}}
```

### Else Blocks

```handlebars
{{#if data.items}}
  <ul>
    {{#each data.items}}
      <li>{{this}}</li>
    {{/each}}
  </ul>
{{else}}
  <p>No items available</p>
{{/if}}
```

---

## 9. Transformation Algorithm

### HTML to Handlebars Conversion

```python
def transform_html_to_handlebars(html, field_mappings, component_alias):
    """
    Transform HTML to Handlebars template
    
    Args:
        html: Original HTML string
        field_mappings: Dict of {element_id: field_alias}
        component_alias: MiBlock alias (without -mi-block)
    
    Returns:
        handlebars_template: String
    """
    soup = BeautifulSoup(html, 'html.parser')
    root = soup.find(True)  # Get root element
    
    # Track if edit marker has been added
    edit_marker_added = False
    
    # Process each element with field mapping
    for element_id, field_alias in field_mappings.items():
        element = root.find(id=element_id) or root.find(attrs={'data-field-id': element_id})
        
        if not element:
            continue
        
        # Replace text content with Handlebars
        if element.string:
            element.string.replace_with(f'{{{{data.{field_alias}}}}}')
        
        # Add edit marker to first text element
        if not edit_marker_added and element.name in ['h1', 'h2', 'h3', 'p']:
            element['%%componentRecordEditable%%'] = ''
            edit_marker_added = True
        
        # Replace image src
        if element.name == 'img':
            element['src'] = f'{{{{data.{field_alias}}}}}'
            # Replace alt
            alt_field = field_mappings.get(f'{element_id}_alt')
            if alt_field:
                element['alt'] = f'{{{{data.{alt_field}}}}}'
        
        # Replace link href
        if element.name == 'a':
            href_field = field_mappings.get(f'{element_id}_href')
            if href_field:
                element['href'] = f'{{{{data.{href_field}}}}}'
    
    # Wrap in {{#each}} loop
    template = f'''{{{{#each ComponentRecordJson.{component_alias}}}}}
{str(root)}
{{{{/each}}}}'''
    
    return template
```

---

## 10. Validation Checklist

Before finalizing template:

- [ ] Wrapped in `{{#each ComponentRecordJson.alias}}`
- [ ] Component alias matches MiBlock (no `-mi-block` suffix)
- [ ] All bindings use `{{data.fieldName}}`
- [ ] Field names match PropertyAliasName exactly
- [ ] Edit marker on first text element only
- [ ] All UIkit classes preserved
- [ ] Data attributes preserved (`uk-grid`, `data-*`)
- [ ] ARIA attributes preserved
- [ ] Conditional content uses `{{#if}}`
- [ ] Images have both src and alt bindings
- [ ] Links have both href and text bindings
- [ ] RichText uses triple braces `{{{}}}`

---

## Next Steps

- Read [Best Practices](05_BEST_PRACTICES.md)
- Review complete [Examples](../examples/)
- Study [JSON Schemas](../schemas/)

---

**Version**: 1.0  
**Last Updated**: 2026-01-31
