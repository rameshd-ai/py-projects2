# Visual Workflow Diagrams

## Overview

Visual representations of the HTML-to-CMS definition generation process.

---

## 1. Complete Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│                        HTML COMPONENT                           │
│  <section>                                                      │
│    <h2>Heading</h2>                                            │
│    <p>Description</p>                                          │
│    <img src="..." alt="...">                                   │
│  </section>                                                     │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                    STEP 1: PARSE HTML                           │
│  • BeautifulSoup parsing                                       │
│  • Identify root element                                       │
│  • Build element tree                                          │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│              STEP 2: CLASSIFY CONTENT                           │
│                                                                 │
│  Dynamic (Editable):          Static (Template):               │
│  • <h2>Heading</h2>          • <section> tag                   │
│  • <p>Description</p>        • CSS classes                     │
│  • <img src>                 • Layout divs                     │
│  • <a href>                  • Data attributes                 │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│           STEP 3: DETECT COMPONENT TYPE                         │
│                                                                 │
│  Has Multiple Sections? (Separate MiBlocks)                   │
│           │                                                     │
│      ┌────┴────┐                                               │
│      │         │                                               │
│     YES       NO                                               │
│      │         │                                               │
│      ▼         ▼                                               │
│  COMPOUND   Has repeating sections?                           │
│  (2+ separate    │                                            │
│  MiBlocks)  ┌────┴────┐                                       │
│      │      │         │                                       │
│      │     YES       NO                                       │
│      │      │         │                                       │
│      │      ▼         ▼                                       │
│      │   NESTED    SIMPLE                                     │
│      │  (Within 1   (1 MiBlock,                               │
│      │   MiBlock)   no repeat)                                │
│      │      │         │                                       │
│      │      │         │                                       │
│  ⭐ Each MiBlock in compound can be Simple or Nested          │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│           STEP 4: DETERMINE FIELD TYPES                         │
│                                                                 │
│  For each editable element:                                    │
│                                                                 │
│  Text Content → Text or RichText                               │
│  Images → File (ResourceTypeName: Image) + Alt Text           │
│  Links → URL field + Text field                               │
│  Numbers → Number                                              │
│  Toggles → Boolean                                             │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│          STEP 5: GENERATE FIELD DEFINITIONS                     │
│                                                                 │
│  {                                                              │
│    "PropertyName": "Main Heading",                            │
│    "PropertyAliasName": "mainHeading",                        │
│    "ControlName": "Text",                                      │
│    "IsIdentifier": true,                                       │
│    "IsMandatory": true,                                        │
│    "DataType": "string",                                       │
│    "PropertyMaxLength": 200                                    │
│  }                                                              │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│         STEP 6: CREATE HANDLEBARS TEMPLATE                      │
│                                                                 │
│  {{#each ComponentRecordJson.ag-component}}                    │
│    <section>                                                    │
│      <h2 %%componentRecordEditable%%>                          │
│        {{data.mainHeading}}                                    │
│      </h2>                                                      │
│      <p>{{data.description}}</p>                               │
│      <img src="{{data.image}}" alt="{{data.imageAlt}}">       │
│    </section>                                                   │
│  {{/each}}                                                      │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│            STEP 7: ASSEMBLE PAYLOAD JSON                        │
│                                                                 │
│  {                                                              │
│    "component_name": "ag_component",                          │
│    "component_type": "simple|compound|nested",                │
│    "miblocks": [ /* definitions */ ],                         │
│    "css": { /* styles */ },                                   │
│    "format": { /* template */ },                              │
│    "vcomponent": { /* metadata */ }                           │
│  }                                                              │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                    CMS PAYLOAD JSON                             │
│                  (Ready for injection)                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Content Classification Decision Tree

```
                    HTML Element
                         │
                         ▼
                 Has meaningful content?
                         │
                  ┌──────┴──────┐
                 YES            NO
                  │              │
                  ▼              ▼
         ┌─────────────┐    [SKIP - Static]
         │ Content Type│
         └──────┬──────┘
                │
      ┌─────────┼─────────┬─────────┬─────────┐
      │         │         │         │         │
      ▼         ▼         ▼         ▼         ▼
   <h1-h6>   <p>      <img>      <a>    <button>
      │         │         │         │         │
      ▼         ▼         ▼         ▼         ▼
   Text      Text     File     Link      Text
   Field     Field    Field    Fields    Field
             (or               (URL +
           RichText)            Text)
```

---

## 3. Component Type Decision Flow

```
                  Analyze Component
                         │
                         ▼
            Has Multiple Sections?
         (User will combine 2+ MiBlocks?)
                         │
          ┌──────────────┼──────────────┐
          │                             │
         YES                           NO
          │                             │
          ▼                             ▼
      ┌──────────┐           Has repeating sections
      │COMPOUND  │           within same MiBlock?
      └──────────┘                     │
          │                    ┌───────┴────────┐
          │                   YES               NO
          │                    │                 │
          │                    ▼                 ▼
          │               ┌────────┐        ┌──────┐
          │               │NESTED  │        │SIMPLE│
          │               └────────┘        └──────┘
          │                    │                 │
          │                    │                 │
          └────────────────────┴─────────────────┘
                         │
                         ▼
                Create MiBlock(s)
                         │
          ┌──────────────┼──────────────┬────────────┐
          │              │              │            │
      Simple:        Compound:      Nested:     Implementation
      1 MiBlock      2+ MiBlocks    1 Parent    Details:
      All fields     Each can be    MiBlock     - Simple: Pass 1 ID
      together       Simple OR      + Child     - Compound: Pass ALL IDs
                     Nested         Records     - Nested: Pass parent ID
                                                  (children linked)

⭐ KEY INSIGHT: Compound components can contain Simple or Nested MiBlocks
   Example: Features Header (Simple) + Feature Cards (Nested with items)
```

---

## 4. Field Type Selection Flow

```
                  Editable Element
                         │
                         ▼
                  What type is it?
                         │
      ┌──────────────────┼──────────────────┬──────────┐
      │                  │                  │          │
      ▼                  ▼                  ▼          ▼
   <img>              <a>            Text content   Other
      │                  │                  │          │
      ▼                  ▼                  ▼          │
   FILE               LINK            Check length    │
      │                  │                  │          │
      │                  │        ┌─────────┼──────┐  │
      │                  │        │                 │  │
      │                  │        ▼                 ▼  │
      │                  │    < 500 chars      > 500   │
      │                  │        │                 │  │
      │                  │        ▼                 ▼  │
      │                  │     TEXT            RICHTEXT│
      │                  │                             │
      ▼                  ▼                             ▼
ResourceTypeName:   Split into:                    Default:
  - Image          • linkText (Text)                 TEXT
  - Document       • linkUrl (Text)
  - Video
      │
      ▼
  Add Alt Text
    (paired field)
```

---

## 5. Template Generation Flow

```
              Original HTML
                    │
                    ▼
         ┌──────────────────────┐
         │  Parse with           │
         │  BeautifulSoup        │
         └──────────┬────────────┘
                    │
                    ▼
         ┌──────────────────────┐
         │  Find editable        │
         │  elements             │
         └──────────┬────────────┘
                    │
                    ▼
         ┌──────────────────────┐
         │  Replace content      │
         │  with {{data.*}}      │
         └──────────┬────────────┘
                    │
                    ▼
         ┌──────────────────────┐
         │  Add edit marker      │
         │  (first text element) │
         └──────────┬────────────┘
                    │
                    ▼
         ┌──────────────────────┐
         │  Wrap in {{#each}}    │
         │  loop                 │
         └──────────┬────────────┘
                    │
                    ▼
           Handlebars Template
```

---

## 6. MiBlock Structure

```
┌────────────────────────────────────────────────┐
│              MIBLOCK COMPONENT                  │
├────────────────────────────────────────────────┤
│                                                 │
│  Component Name: "AG Hero Section"             │
│  Component Alias: "ag-hero-section"            │
│                                                 │
│  ┌──────────────────────────────────────────┐ │
│  │         FIELD DEFINITIONS                 │ │
│  ├──────────────────────────────────────────┤ │
│  │                                           │ │
│  │  1. mainHeading (Text) ⭐ Identifier     │ │
│  │  2. subheading (Text)                    │ │
│  │  3. ctaText (Text)                       │ │
│  │  4. ctaLink (Text)                       │ │
│  │  5. backgroundImage (File)               │ │
│  │                                           │ │
│  └──────────────────────────────────────────┘ │
│                                                 │
│  ┌──────────────────────────────────────────┐ │
│  │            SAMPLE RECORDS                 │ │
│  ├──────────────────────────────────────────┤ │
│  │                                           │ │
│  │  {                                        │ │
│  │    "mainHeading": "Welcome...",          │ │
│  │    "subheading": "Discover...",          │ │
│  │    "ctaText": "Get Started",             │ │
│  │    "ctaLink": "/start",                  │ │
│  │    "backgroundImage": ["url"]            │ │
│  │  }                                        │ │
│  │                                           │ │
│  └──────────────────────────────────────────┘ │
│                                                 │
└────────────────────────────────────────────────┘
```

---

## 7. Compound Component Structure

```
┌────────────────────────────────────────────────────────────┐
│                  COMPOUND COMPONENT                         │
│  (User selects and combines 2+ separate MiBlocks)          │
├────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────────────────────────────────────────┐ │
│  │         MIBLOCK 1: HEADER (Simple)                    │ │
│  ├──────────────────────────────────────────────────────┤ │
│  │  Name: "AG Features Header"                          │ │
│  │  Alias: "ag-features-header"                         │ │
│  │  Type: Simple (no repeating content)                 │ │
│  │                                                       │ │
│  │  Fields:                                             │ │
│  │  • sectionTitle (Text) ⭐                           │ │
│  │  • sectionSubtitle (Text)                           │ │
│  │                                                       │ │
│  │  Records: 1 (single header)                          │ │
│  │  Implementation: Separate component                  │ │
│  └──────────────────────────────────────────────────────┘ │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐ │
│  │      MIBLOCK 2: FEATURE ITEMS (Nested)                │ │
│  ├──────────────────────────────────────────────────────┤ │
│  │  Name: "AG Feature Cards Section"                    │ │
│  │  Alias: "ag-feature-cards"                           │ │
│  │  Type: Nested (has repeating child cards)            │ │
│  │                                                       │ │
│  │  Parent Fields:                                      │ │
│  │  • cardsTitle (Text) ⭐                             │ │
│  │                                                       │ │
│  │  Child Fields (repeating):                           │ │
│  │  • cardTitle (Text) ⭐                              │ │
│  │  • cardDescription (Text)                           │ │
│  │  • cardIcon (File)                                  │ │
│  │  • cardIconAlt (Text)                               │ │
│  │                                                       │ │
│  │  Records: 1 parent with multiple child cards         │ │
│  │  Implementation: Separate component (nested)         │ │
│  └──────────────────────────────────────────────────────┘ │
│                                                             │
│  ⭐ PASS ALL MIBLOCK IDs                                   │
│  ⭐ NO parent-child relationship between MiBlocks          │
│  ⭐ Each MiBlock can be Simple OR Nested internally        │
└────────────────────────────────────────────────────────────┘

TEMPLATE:
─────────
{{#each ComponentRecordJson.ag-features-header}}
  <h2 %%componentRecordEditable%%>{{data.sectionTitle}}</h2>
{{/each}}

{{#each ComponentRecordJson.ag-feature-cards}}
  <h3 %%componentRecordEditable%%>{{data.cardsTitle}}</h3>
  
  {{#each this.childRecords}}
    <div class="card">
      <h4 %%componentRecordEditable%%>{{data.cardTitle}}</h4>
      <p>{{data.cardDescription}}</p>
    </div>
  {{/each}}
{{/each}}
```

---

## 8. Nested Component Structure

```
┌────────────────────────────────────────────────────────────┐
│                    NESTED COMPONENT                         │
│  (Repeating sections within 1 MiBlock)                     │
├────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────────────────────────────────────────┐ │
│  │         PARENT MIBLOCK: FAQ SECTION                   │ │
│  ├──────────────────────────────────────────────────────┤ │
│  │  Name: "AG FAQ Section"                              │ │
│  │  Alias: "ag-faq-section"                             │ │
│  │                                                       │ │
│  │  Parent Fields:                                      │ │
│  │  • sectionTitle (Text) ⭐                           │ │
│  │  • sectionSubtitle (Text)                           │ │
│  │                                                       │ │
│  │  ┌────────────────────────────────────────────────┐ │ │
│  │  │      NESTED CHILD RECORDS                       │ │ │
│  │  ├────────────────────────────────────────────────┤ │ │
│  │  │  • question (Text) ⭐                          │ │ │
│  │  │  • answer (Text)                               │ │ │
│  │  │  • parentRecordId (Link to parent)             │ │ │
│  │  │                                                 │ │ │
│  │  │  Records: Multiple FAQs                        │ │ │
│  │  │  Each linked to parent record ID               │ │ │
│  │  └────────────────────────────────────────────────┘ │ │
│  │                                                       │ │
│  │  Implementation: Pass parent MiBlock ID only         │ │
│  └──────────────────────────────────────────────────────┘ │
│                                                             │
│  ⭐ PASS PARENT MIBLOCK ID ONLY                            │
│  ⭐ Sub-records linked to parent record ID                 │
└────────────────────────────────────────────────────────────┘

TEMPLATE:
─────────
{{#each ComponentRecordJson.ag-faq-section}}
  <section>
    <h2 %%componentRecordEditable%%>{{data.sectionTitle}}</h2>
    <p>{{data.sectionSubtitle}}</p>
    
    {{#each this.childRecords}}
      <div class="faq-item">
        <h3 %%componentRecordEditable%%>{{data.question}}</h3>
        <p>{{data.answer}}</p>
      </div>
    {{/each}}
  </section>
{{/each}}
```

---

## 9. Component Type Comparison

```
┌──────────────┬─────────────┬──────────────┬─────────────┐
│ Feature      │ Simple      │ Compound     │ Nested      │
├──────────────┼─────────────┼──────────────┼─────────────┤
│ MiBlocks     │ 1           │ 2+           │ 1 (parent)  │
│ Records      │ Single      │ Multiple     │ Parent +    │
│              │             │ separate     │ Children    │
│ Pass IDs     │ 1 MiBlock   │ ALL MiBlock  │ Parent      │
│              │ ID          │ IDs          │ MiBlock ID  │
│              │             │              │ only        │
│ Relationship │ None        │ Independent  │ Parent-     │
│              │             │ MiBlocks     │ Child       │
│              │             │              │ linked      │
│ Can Contain  │ N/A         │ Simple OR    │ N/A         │
│              │             │ Nested       │             │
│              │             │ MiBlocks     │             │
│ Use Case     │ Hero,       │ Features     │ FAQ,        │
│              │ Banner,     │ section with │ Accordion,  │
│              │ CTA         │ separate     │ Tabs        │
│              │             │ header +     │             │
│              │             │ cards        │             │
│ Example      │ Single hero │ Header       │ FAQ section │
│              │ section     │ (Simple) +   │ with Q&A    │
│              │             │ Cards        │ items       │
│              │             │ (Nested)     │             │
└──────────────┴─────────────┴──────────────┴─────────────┘

⭐ KEY: Compound is about COMBINING multiple MiBlocks
        Each MiBlock in compound can be Simple OR Nested
```

---

## 10. Field Definition Creation Process

```
              HTML Element: <h2>Welcome</h2>
                            │
                            ▼
              ┌─────────────────────────┐
              │  Extract Information     │
              │  • Tag: h2              │
              │  • Text: "Welcome"      │
              │  • Length: 7 chars      │
              └───────────┬─────────────┘
                          │
                          ▼
              ┌─────────────────────────┐
              │  Generate Field Name     │
              │  • From text: "welcome" │
              │  • CamelCase: "welcome" │
              │  • Display: "Welcome"   │
              └───────────┬─────────────┘
                          │
                          ▼
              ┌─────────────────────────┐
              │  Determine Field Type    │
              │  • Short text (< 200)   │
              │  • Type: Text           │
              │  • MaxLength: 200       │
              └───────────┬─────────────┘
                          │
                          ▼
              ┌─────────────────────────┐
              │  Set Properties          │
              │  • IsIdentifier: true   │
              │  • IsMandatory: true    │
              │  • DataType: "string"   │
              └───────────┬─────────────┘
                          │
                          ▼
              ┌─────────────────────────────────┐
              │  COMPLETE FIELD DEFINITION       │
              │  {                               │
              │    "PropertyName": "Welcome",   │
              │    "PropertyAliasName": "welcome"│
              │    "ControlName": "Text",       │
              │    "IsIdentifier": true,        │
              │    "IsMandatory": true,         │
              │    "DataType": "string",        │
              │    "PropertyMaxLength": 200     │
              │  }                               │
              └─────────────────────────────────┘
```

---

## 11. Image Field Pairing Pattern

```
         HTML: <img src="hero.jpg" alt="Hero image">
                          │
          ┌───────────────┴───────────────┐
          │                               │
          ▼                               ▼
   ┌──────────────┐              ┌──────────────┐
   │  IMAGE FIELD  │              │ ALT TEXT FIELD│
   ├──────────────┤              ├──────────────┤
   │ heroImage    │              │ heroImageAlt  │
   │ (File)       │              │ (Text)        │
   │ Required     │              │ Required      │
   └──────┬───────┘              └──────┬───────┘
          │                               │
          └───────────────┬───────────────┘
                          │
                          ▼
              Template: <img src="{{data.heroImage}}" 
                             alt="{{data.heroImageAlt}}">
```

---

## 12. Edit Marker Placement

### Simple Component
```
{{#each ComponentRecordJson.ag-hero}}
┌───────────────────────────────────┐
│  <section>                        │
│    <h1 %%componentRecordEditable%%>  ← ⭐ ONE marker
│      {{data.heading}}             │
│    </h1>                           │
│    <p>{{data.text}}</p>           │  ← ✅ Auto-enabled
│    <button>{{data.btnText}}</button> ← ✅ Auto-enabled
│  </section>                        │
└───────────────────────────────────┘
{{/each}}
```

### Compound Component
```
{{#each ComponentRecordJson.ag-header}}
┌───────────────────────────────────┐
│  <h2 %%componentRecordEditable%%>   ← ⭐ Marker #1
│    {{data.title}}                 │
│  </h2>                             │
└───────────────────────────────────┘
{{/each}}

{{#each ComponentRecordJson.ag-card}}
┌───────────────────────────────────┐
│  <div class="card">                │
│    <h3 %%componentRecordEditable%%> ← ⭐ Marker #2
│      {{data.cardTitle}}           │
│    </h3>                           │
│    <p>{{data.cardText}}</p>       │  ← ✅ Auto-enabled
│  </div>                            │
└───────────────────────────────────┘
{{/each}}
```

### Nested Component
```
{{#each ComponentRecordJson.ag-faq}}
┌───────────────────────────────────┐
│  <section>                        │
│    <h2 %%componentRecordEditable%%>  ← ⭐ Parent marker
│      {{data.sectionTitle}}        │
│    </h2>                           │
│                                    │
│    {{#each this.childRecords}}    │  ← ⭐ Nested loop
│    ┌─────────────────────────┐   │
│    │  <div class="faq">       │   │
│    │    <h3 %%componentRecordEditable%%> ← ⭐ Child marker
│    │      {{data.question}}   │   │
│    │    </h3>                 │   │
│    │    <p>{{data.answer}}</p>│   │  ← ✅ Auto-enabled
│    │  </div>                  │   │
│    └─────────────────────────┘   │
│    {{/each}}                      │
│  </section>                        │
└───────────────────────────────────┘
{{/each}}
```

---

## 13. Data Flow Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      INPUT LAYER                             │
│  • Figma Design URL                                         │
│  • HTML Files                                               │
│  • CSS Files                                                │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   ANALYSIS LAYER                             │
│  • HTML Parser (BeautifulSoup)                              │
│  • Content Classifier                                       │
│  • Field Type Detector                                      │
│  • Component Type Analyzer                                  │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                 GENERATION LAYER                             │
│  • Field Definition Generator                               │
│  • Template Transformer (HTML → Handlebars)                │
│  • Sample Data Generator                                    │
│  • CSS Extractor                                            │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                 ASSEMBLY LAYER                               │
│  • MiBlock Assembler                                        │
│  • Payload Builder                                          │
│  • JSON Validator                                           │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    OUTPUT LAYER                              │
│  • Payload JSON                                             │
│  • Ready for CMS Injection                                  │
└─────────────────────────────────────────────────────────────┘
```

---

## 14. Error Prevention Workflow

```
                    Create Field Definition
                              │
                              ▼
                   ┌──────────────────┐
                   │  Validation Gate  │
                   └────────┬──────────┘
                            │
          ┌─────────────────┼─────────────────┐
          │                 │                 │
          ▼                 ▼                 ▼
    Is first field?   File field?      Link field?
          │                 │                 │
          ▼                 ▼                 ▼
   Set IsIdentifier   Has ResourceType?   Has URL field?
      = true               │                 │
          │           ┌────┴────┐       ┌───┴────┐
          │          YES        NO      YES      NO
          │           │          │       │        │
          │           ▼          ▼       ▼        ▼
          │        ✅ Pass    ❌ ERROR ✅ Pass ❌ ERROR
          │
          └─────────────────┬─────────────────┘
                            │
                            ▼
                    All validations pass?
                            │
                       ┌────┴────┐
                      YES        NO
                       │          │
                       ▼          ▼
                   ✅ Save    ❌ Fix Issues
```

---

## 15. Complete Payload Structure

```
CMS Payload JSON
├── component_name (string)
├── component_type ("simple" | "compound" | "nested")
├── category_id (number) ⚠️ Critical!
├── description (string)
│
├── miblocks (array)
│   └── [0..n]
│       ├── component_name (string)
│       ├── component_alias_name (string)
│       ├── definitions (array)
│       │   └── [0..n] Field Definition
│       └── records (array)
│           └── [0..n] Sample Record
│               ├── data (object)
│               └── childRecords (array) ⭐ For nested only
│
├── css (object)
│   ├── fileName (string)
│   └── content (string)
│
├── format (object)
│   ├── formatName (string)
│   ├── formatKey (string)
│   └── formatContent (string - Handlebars)
│
└── vcomponent (object)
    ├── name (string)
    ├── alias (string)
    ├── description (string)
    ├── categoryId (number) ⚠️ Must match!
    ├── isActive (boolean)
    └── interactionType (string)
```

---

## 16. Field Type Matrix

```
┌────────────┬──────────┬────────────┬──────────────────────┐
│ HTML       │ Content  │ CMS Field  │ Additional Props     │
│ Element    │ Type     │ Type       │ Required             │
├────────────┼──────────┼────────────┼──────────────────────┤
│ <h1-h6>    │ Short    │ Text       │ PropertyMaxLength    │
│ <p>        │ Long     │ RichText   │ None                 │
│ <img>      │ Media    │ File       │ ResourceTypeName     │
│            │          │            │ + Alt Text pair      │
│ <a>        │ Link     │ Text (2x)  │ URL + Text fields    │
│ <button>   │ Action   │ Text       │ PropertyMaxLength    │
│ <input>    │ Data     │ Text       │ PropertyMaxLength    │
│ price      │ Number   │ Number     │ DataType: number     │
│ toggle     │ Boolean  │ Boolean    │ DataType: boolean    │
└────────────┴──────────┴────────────┴──────────────────────┘
```

---

**Created**: 2026-01-31  
**Purpose**: Visual reference for workflow understanding  
**Format**: ASCII diagrams for documentation
