# Best Practices Guide

## Overview

Battle-tested patterns, anti-patterns, and lessons learned from production use.

---

## 1. Field Definition Best Practices

### ✅ DO: Use Descriptive Names

```json
✅ GOOD:
{
  "PropertyName": "Primary Call To Action Button Text",
  "PropertyAliasName": "primaryCtaButtonText"
}

❌ BAD:
{
  "PropertyName": "Button",
  "PropertyAliasName": "btn"
}
```

**Why**: Clear names prevent confusion and make the CMS editor-friendly

### ✅ DO: Set Appropriate Max Lengths

```json
✅ GOOD - Based on content type:
{
  "PropertyAliasName": "headline",
  "PropertyMaxLength": 200  // Headlines rarely exceed 200
}
{
  "PropertyAliasName": "shortDescription",
  "PropertyMaxLength": 500  // Descriptions can be longer
}
{
  "PropertyAliasName": "pageUrl",
  "PropertyMaxLength": 500  // URLs need more space
}

❌ BAD - Generic or arbitrary:
{
  "PropertyAliasName": "headline",
  "PropertyMaxLength": 5000  // Way too large
}
```

**Why**: Appropriate limits prevent data bloat and guide content creation

### ✅ DO: Pair Related Fields

```json
✅ GOOD - Image + Alt Text:
[
  {"PropertyAliasName": "heroImage", "ControlName": "File"},
  {"PropertyAliasName": "heroImageAlt", "ControlName": "Text"}
]

✅ GOOD - Link Text + URL:
[
  {"PropertyAliasName": "ctaText", "ControlName": "Text"},
  {"PropertyAliasName": "ctaLink", "ControlName": "Text"}
]

❌ BAD - Missing pairs:
[
  {"PropertyAliasName": "image", "ControlName": "File"}
  // Missing alt text field!
]
```

**Why**: Accessibility (alt text) and usability (link text/URL separation)

---

## 2. Component Structure Best Practices

### ✅ DO: Use Simple Components When Possible

```json
✅ GOOD - Simple component for non-repeating content:
{
  "component_type": "simple",
  "miblocks": [
    {
      "component_alias_name": "ag-hero-section",
      "definitions": [ /* all fields */ ]
    }
  ]
}
```

**When to use**: Hero sections, CTA banners, single content blocks
**Implementation**: Pass 1 MiBlock ID

### ✅ DO: Use Nested for Repeating Within One MiBlock

```json
✅ GOOD - Nested for parent-child relationship:
{
  "component_type": "nested",
  "miblocks": [
    {
      "component_alias_name": "ag-faq-section",
      "definitions": [ /* parent fields */ ],
      "child_definitions": [ /* child fields */ ],
      "records": [
        {
          "sectionTitle": "FAQ",
          "childRecords": [ /* repeating items */ ]
        }
      ]
    }
  ]
}
```

**When to use**: FAQ sections, accordions, tabs, timeline
**Implementation**: Pass parent MiBlock ID only, sub-records linked to parent record ID

### ✅ DO: Use Compound for Separate Components Combined

```json
✅ GOOD - Compound for separate components:
{
  "component_type": "compound",
  "miblocks": [
    {
      "component_alias_name": "ag-features-header",
      "type": "simple",  // Header is simple
      "definitions": [ /* header fields */ ]
    },
    {
      "component_alias_name": "ag-feature-cards",
      "type": "nested",  // Cards section with repeating items
      "definitions": [ /* parent fields */ ],
      "child_definitions": [ /* card fields */ ]
    }
  ]
}
```

**When to use**: User selects 2+ separate MiBlocks (header + items as independent components)
**Implementation**: Pass ALL MiBlock IDs, no parent-child relationship between MiBlocks
**Note**: Each MiBlock in compound can be Simple OR Nested internally

### ❌ DON'T: Confuse Nested with Compound

```json
❌ BAD - Using compound when nested is appropriate:
// FAQ where items should be children of parent section
{
  "component_type": "compound",  // WRONG - should be nested
  "miblocks": [
    {"component_alias_name": "ag-faq-header"},
    {"component_alias_name": "ag-faq-item"}  // These are children, not separate!
  ]
}

✅ BETTER - Use nested:
{
  "component_type": "nested",  // Correct - parent-child relationship
  "miblocks": [
    {
      "component_alias_name": "ag-faq-section",
      "definitions": [ /* parent: section title */ ],
      "child_definitions": [ /* children: Q&A items */ ]
    }
  ]
}
```

**Key difference**: 
- **Nested**: Repeating sections within 1 MiBlock (FAQ items under FAQ section)
- **Compound**: Multiple separate MiBlocks combined (Features header + Feature cards)

### ❌ DON'T: Create Compound When Simple Works

```json
❌ BAD - Unnecessary compound:
{
  "component_type": "compound",  // Overkill for simple content
  "miblocks": [
    {"component_alias_name": "ag-header"},
    {"component_alias_name": "ag-text"}  // Just one text block?
  ]
}

✅ BETTER - Use simple:
{
  "component_type": "simple",
  "miblocks": [
    {
      "component_alias_name": "ag-text-section",
      "definitions": [
        {"PropertyAliasName": "heading"},
        {"PropertyAliasName": "bodyText"}
      ]
    }
  ]
}
```

---

## 3. Template Best Practices

### ✅ DO: Preserve Framework Classes

```handlebars
✅ GOOD - All UIkit classes preserved:
<div class="uk-grid uk-grid-large uk-child-width-1-3@m" uk-grid>
  {{#each ComponentRecordJson.ag-cards}}
    <div>
      <div class="uk-card uk-card-default">
        <h3>{{data.title}}</h3>
      </div>
    </div>
  {{/each}}
</div>

❌ BAD - Classes removed:
<div>
  {{#each ComponentRecordJson.ag-cards}}
    <div>
      <h3>{{data.title}}</h3>
    </div>
  {{/each}}
</div>
```

**Why**: Framework classes provide layout, responsiveness, and styling

### ✅ DO: Use Semantic HTML

```handlebars
✅ GOOD - Semantic tags:
<section>
  <header>
    <h2>{{data.heading}}</h2>
  </header>
  <article>
    <p>{{data.content}}</p>
  </article>
</section>

❌ BAD - Generic divs:
<div>
  <div>
    <div>{{data.heading}}</div>
  </div>
  <div>
    <div>{{data.content}}</div>
  </div>
</div>
```

**Why**: SEO, accessibility, maintainability

### ✅ DO: Add Loading Attributes

```handlebars
✅ GOOD - Lazy loading images:
<img src="{{data.image}}" 
     alt="{{data.imageAlt}}" 
     loading="lazy"
     width="600"
     height="400">

❌ BAD - No performance optimization:
<img src="{{data.image}}" 
     alt="{{data.imageAlt}}">
```

**Why**: Performance optimization (lazy loading)

---

## 4. Naming Conventions

### ✅ DO: Follow Consistent Patterns

**Component Names**:
```
✅ GOOD:
- "AG Hero Section"
- "AG Feature Cards"
- "AG Contact Form"

❌ BAD:
- "hero_section"
- "Features"
- "form-contact"
```

**Component Aliases**:
```
✅ GOOD:
- "ag-hero-section"
- "ag-feature-cards"
- "ag-contact-form"

❌ BAD:
- "agHeroSection"
- "AG_feature_cards"
- "ag.contact.form"
```

**Field Aliases**:
```
✅ GOOD:
- "mainHeading"
- "primaryCtaText"
- "featureImage"

❌ BAD:
- "MainHeading"
- "primary_cta_text"
- "feature-image"
```

---

## 5. Category Selection

### ✅ DO: Test Category IDs First

```python
✅ GOOD - Verify category works:
{
  "categoryId": 21  # Tested and confirmed working
}

❌ BAD - Guessing category:
{
  "categoryId": 10  # May cause 500 errors
}
```

**Lesson Learned**: Category ID mismatch causes VComponent creation failures. Always use tested category IDs from successful runs.

### ✅ DO: Document Working Categories

```markdown
# Tested Category IDs

- **21**: Feature components (confirmed working)
- **15**: Form components (confirmed working)
- **10**: ⚠️ Causes 500 errors with feature components
```

---

## 6. Error Prevention

### ✅ DO: Validate Field Aliases Match Template

```python
# Field definition
{
  "PropertyAliasName": "primaryCtaText"
}

# Template MUST match exactly
{{data.primaryCtaText}}  # ✅ Correct
{{data.primaryCTAText}}  # ❌ Wrong - case mismatch
{{data.primary_cta_text}}  # ❌ Wrong - different format
```

### ✅ DO: Use Image Arrays in Sample Data

```json
✅ GOOD:
{
  "heroImage": ["https://example.com/image.jpg"]
}

❌ BAD:
{
  "heroImage": "https://example.com/image.jpg"
}
```

**Why**: CMS expects image URLs as arrays

### ✅ DO: Escape Quotes in JSON Strings

```json
✅ GOOD:
{
  "content": "She said, \"Hello!\""
}

❌ BAD:
{
  "content": "She said, "Hello!""
}
```

---

## 7. Common Mistakes to Avoid

### ❌ DON'T: Wrap Templates in `{{#with VCompJson}}`

```handlebars
❌ WRONG:
{{#with VCompJson}}
  {{#each ComponentRecordJson.ag-hero}}
    <!-- content -->
  {{/each}}
{{/with}}

✅ CORRECT:
{{#each ComponentRecordJson.ag-hero}}
  <!-- content -->
{{/each}}
```

**Why**: CMS auto-wraps templates, manual wrapping breaks rendering

### ❌ DON'T: Add Multiple Edit Markers in Same Loop

```handlebars
❌ WRONG:
{{#each ComponentRecordJson.ag-hero}}
  <h1 %%componentRecordEditable%%>{{data.heading}}</h1>
  <p %%componentRecordEditable%%>{{data.text}}</p>  <!-- ❌ Second marker -->
{{/each}}

✅ CORRECT:
{{#each ComponentRecordJson.ag-hero}}
  <h1 %%componentRecordEditable%%>{{data.heading}}</h1>
  <p>{{data.text}}</p>  <!-- ✅ Auto-enabled -->
{{/each}}
```

**Why**: CMS auto-enables all fields, multiple markers cause conflicts

### ❌ DON'T: Use `-mi-block` Suffix in Templates

```handlebars
❌ WRONG:
{{#each ComponentRecordJson.ag-hero-section-mi-block}}

✅ CORRECT:
{{#each ComponentRecordJson.ag-hero-section}}
```

**Why**: CMS adds suffix internally, template should use base alias

---

## 8. Performance Best Practices

### ✅ DO: Optimize Images

```handlebars
✅ GOOD:
<img src="{{data.image}}" 
     alt="{{data.imageAlt}}"
     loading="lazy"
     width="600"
     height="400"
     srcset="{{data.image}} 1x, {{data.image2x}} 2x">
```

### ✅ DO: Minimize Custom CSS

```css
✅ GOOD - Use framework classes:
<!-- UIkit handles styling -->
<div class="uk-card uk-card-default uk-card-hover">
  <h3 class="uk-card-title">{{data.title}}</h3>
</div>

❌ BAD - Custom CSS for everything:
<div class="my-custom-card">
  <h3 class="my-custom-title">{{data.title}}</h3>
</div>
/* Then 100+ lines of custom CSS */
```

**Why**: Framework CSS is optimized, cached, and maintained

---

## 9. Accessibility Best Practices

### ✅ DO: Include Alt Text for Images

```json
✅ GOOD:
[
  {"PropertyAliasName": "heroImage", "ControlName": "File"},
  {"PropertyAliasName": "heroImageAlt", "ControlName": "Text", "IsMandatory": true}
]
```

### ✅ DO: Use ARIA Attributes

```handlebars
✅ GOOD:
<button type="button" 
        aria-label="Close modal"
        aria-expanded="false">
  {{data.buttonText}}
</button>

<nav aria-label="Main navigation">
  <!-- navigation links -->
</nav>
```

### ✅ DO: Maintain Heading Hierarchy

```handlebars
✅ GOOD:
<h1>{{data.pageTitle}}</h1>
<section>
  <h2>{{data.sectionTitle}}</h2>
  <h3>{{data.subsectionTitle}}</h3>
</section>

❌ BAD:
<h1>{{data.pageTitle}}</h1>
<h3>{{data.sectionTitle}}</h3>  <!-- ❌ Skipped h2 -->
```

---

## 10. Testing Checklist

Before deploying component:

**Field Definitions**:
- [ ] First field has `IsIdentifier: true`
- [ ] Image fields have alt text pairs
- [ ] Link fields have text + URL pairs
- [ ] Field names follow conventions
- [ ] Max lengths are appropriate

**Templates**:
- [ ] Wrapped in `{{#each}}` loop
- [ ] Component alias matches (no `-mi-block`)
- [ ] Bindings use `{{data.fieldName}}`
- [ ] ONE edit marker per loop
- [ ] Framework classes preserved
- [ ] ARIA attributes included

**Payload**:
- [ ] Correct category ID (tested)
- [ ] Image URLs in array format
- [ ] Valid JSON (no syntax errors)
- [ ] Sample data is realistic

**CMS Testing**:
- [ ] Component appears in CMS
- [ ] Visual matches Figma design
- [ ] Edit icons appear
- [ ] Inline editing works
- [ ] Changes save correctly
- [ ] Responsive on all breakpoints

---

## 11. Lessons Learned

### From Production Issues:

1. **Category ID Matters**: Wrong category = 500 error
   - Solution: Always test category IDs first

2. **Name Conflicts**: Existing components cause failures
   - Solution: Use unique run tokens

3. **Template Syntax**: Small errors break rendering
   - Solution: Validate Handlebars syntax

4. **Image Arrays**: CMS expects arrays, not strings
   - Solution: Always use `["url"]` format

5. **Edit Markers**: Multiple markers cause conflicts
   - Solution: ONE marker per `{{#each}}` loop

---

## Next Steps

- Review complete [Examples](../examples/)
- Study [JSON Schemas](../schemas/)
- Build your own analyzer using these patterns

---

**Version**: 1.0  
**Last Updated**: 2026-01-31  
**Based on**: AgenticComponentGenerator production experience
