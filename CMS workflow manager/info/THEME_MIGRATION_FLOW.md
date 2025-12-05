# 🎨 Theme Migration Flow - Step 2 Detailed Documentation

## Overview

Step 2 (Brand/Theme Setup) performs complete automated theme migration from source site to destination site, including fonts, colors, and all theme variables.

---

## 🔄 Complete Migration Flow

```
┌─────────────────────────────────────────────────────────────┐
│  Step 1 Complete: CMS Tokens Generated                      │
│  ✓ Source Token       ✓ Destination Token                   │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  STEP 2: User checks "Pull from Current Site" checkbox      │
│  Clicks "Process" button                                     │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  PHASE 1: FETCH SOURCE SITE DATA                            │
│  ────────────────────────────────                            │
│  1. Call get_theme_configuration(source_url, source_site_id)│
│     → Get theme structure, theme ID, group mappings          │
│     → Save: source_get_theme_configuration.json              │
│                                                               │
│  2. Call get_group_record(source_url, payload)               │
│     → Get all font and color variables with actual values    │
│     → Save: source_get_group_record.json                     │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  PHASE 2: MAP VARIABLES                                      │
│  ───────────────────                                         │
│  1. Copy font_mapper.json from resource/ to job folder       │
│                                                               │
│  2. Update font_mapper.json:                                 │
│     For each entry where value is blank:                     │
│       - Get old_key (e.g., "primary-font-file")              │
│       - Find in source group records by variableAlias        │
│       - Extract variableValue (e.g., "Arial-Regular")        │
│       - Update entry value                                   │
│                                                               │
│  3. Copy color_mapper.json from resource/ to job folder      │
│                                                               │
│  4. Update color_mapper.json:                                │
│     For each entry:                                          │
│       - Get old_key (e.g., "primary-bg")                     │
│       - Find in source group records by variableAlias        │
│       - Extract variableValue (e.g., "#FAF0de")              │
│       - Update entry value                                   │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  PHASE 3: FETCH DESTINATION SITE DATA                       │
│  ──────────────────────────────────                          │
│  1. Call get_theme_configuration(destination_url, dest_id)   │
│     → Get destination theme ID                               │
│     → Save: destination_get_theme_configuration.json         │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  PHASE 4: CREATE UPDATE PAYLOADS                            │
│  ────────────────────────────                                │
│  1. Extract destination theme ID                             │
│                                                               │
│  2. Create group names from destination URL:                 │
│     - URL: "https://mysite.web5cms.milestoneinternet.info"  │
│     - Color group: "mysite_color"                            │
│     - Font group: "mysite_font"                              │
│                                                               │
│  3. Load updated mapper files and extract variables:         │
│     - font_variables = {new_key: value} from font_mapper     │
│     - color_variables = {new_key: value} from color_mapper   │
│                                                               │
│  4. Build final payload:                                     │
│     {                                                         │
│       "siteId": destination_site_id,                          │
│       "themeId": destination_theme_id,                        │
│       "groups": [                                             │
│         {                                                     │
│           "Groupid": 0,  // 0 = new group (add)              │
│           "GroupName": "mysite_color",                        │
│           "GroupType": 1,  // 1 = color                      │
│           "themeVariables": "{...color_variables...}"         │
│         },                                                    │
│         {                                                     │
│           "Groupid": 0,                                       │
│           "GroupName": "mysite_font",                         │
│           "GroupType": 2,  // 2 = font                       │
│           "themeVariables": "{...font_variables...}"          │
│         }                                                     │
│       ]                                                       │
│     }                                                         │
│                                                               │
│  5. Save: update_theme_variables_payload.json                │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  PHASE 5: UPDATE DESTINATION THEME VARIABLES                │
│  ────────────────────────────────────────                    │
│  1. Call update_theme_variables(destination_url, payload)    │
│     → Creates new color and font groups                      │
│     → Adds all variables to groups                           │
│     → Returns new group IDs                                  │
│                                                               │
│  2. Response example:                                        │
│     {                                                         │
│       "success": true,                                        │
│       "message": "Theme variables saved successfully.",       │
│       "data": [                                              │
│         {"GroupId": 3975, "GroupType": 1},  // Color group   │
│         {"GroupId": 3976, "GroupType": 2}   // Font group    │
│       ]                                                       │
│     }                                                         │
│                                                               │
│  3. Save: update_theme_variables_response.json               │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  PHASE 6: FINALIZE THEME CONFIGURATION                      │
│  ──────────────────────────────────                          │
│  1. Extract group IDs from update response                   │
│     - Color group ID: 3975                                   │
│     - Font group ID: 3976                                    │
│                                                               │
│  2. Build configuration payload:                             │
│     {                                                         │
│       "siteId": destination_site_id,                          │
│       "themeId": destination_theme_id,                        │
│       "groups": [                                             │
│         {"groupId": 3975},  // Link color group               │
│         {"groupId": 3976}   // Link font group                │
│       ]                                                       │
│     }                                                         │
│                                                               │
│  3. Save: update_theme_configuration_payload.json            │
│                                                               │
│  4. Call update_theme_configuration(destination_url, payload)│
│     → Links groups to theme                                  │
│     → Finalizes theme configuration                          │
│                                                               │
│  5. Response:                                                │
│     {                                                         │
│       "success": true,                                        │
│       "message": "Website theme configuration updated..."     │
│     }                                                         │
│                                                               │
│  6. Save: update_theme_configuration_response.json           │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  COMPLETE! ✅                                                │
│  Destination site now has:                                   │
│  ✓ All font variables from source site                      │
│  ✓ All color variables from source site                     │
│  ✓ Theme configuration properly linked                       │
│  ✓ All payloads and responses saved for audit trail         │
└─────────────────────────────────────────────────────────────┘
```

---

## 📁 Files Generated by Step 2

When "Pull from Current Site" is checked, Step 2 creates 10 files:

### **Source Site Data (Read-only)**
1. `source_get_theme_configuration.json` - Theme structure from source
2. `source_get_group_record.json` - All variables with values from source

### **Mapping Files (Updated with source values)**
3. `font_mapper.json` - Font variable mappings with actual values
4. `color_mapper.json` - Color variable mappings with actual values

### **Destination Site Data**
5. `destination_get_theme_configuration.json` - Theme info from destination

### **Update Payloads & Responses**
6. `update_theme_variables_payload.json` - Payload to add groups
7. `update_theme_variables_response.json` - Response with new group IDs
8. `update_theme_configuration_payload.json` - Payload to finalize theme
9. `update_theme_configuration_response.json` - Final confirmation

---

## 🗺️ Variable Mapping Examples

### Font Mapping Process:

**Resource Template (`resource/font_mapper.json`):**
```json
{ "old_key": "primary-font-file", "new_key": "h1-font-family", "value": "" }
```

**Source Site Variable:**
```json
{
  "variableName": "Primary Font File",
  "variableAlias": "primary-font-file",
  "variableValue": "AyerWeb-Regular"
}
```

**Updated Job Mapper (`uploads/{job_id}/font_mapper.json`):**
```json
{ "old_key": "primary-font-file", "new_key": "h1-font-family", "value": "AyerWeb-Regular" }
```

**Final Payload Variable:**
```json
{
  "themeVariables": "{\"h1-font-family\":\"AyerWeb-Regular\"}"
}
```

### Color Mapping Process:

**Resource Template (`resource/color_mapper.json`):**
```json
{ "old_key": "primary-bg", "new_key": "body-color", "value": "" }
```

**Source Site Variable:**
```json
{
  "variableName": "Primary BG",
  "variableAlias": "primary-bg",
  "variableValue": "#FAF0de"
}
```

**Updated Job Mapper (`uploads/{job_id}/color_mapper.json`):**
```json
{ "old_key": "primary-bg", "new_key": "body-color", "value": "#FAF0de" }
```

**Final Payload Variable:**
```json
{
  "themeVariables": "{\"body-color\":\"#FAF0de\"}"
}
```

---

## 🔑 Key Design Decisions

### 1. **Payload-Based APIs**
All API functions accept complete payloads for flexibility:
```python
get_group_record(base_url, payload, headers)
update_theme_variables(base_url, payload, headers)
update_theme_configuration(base_url, payload, headers)
```

### 2. **File Naming Convention**
Files named after API functions for clarity:
- `update_theme_variables_payload.json`
- `update_theme_variables_response.json`
- `update_theme_configuration_payload.json`
- `update_theme_configuration_response.json`

### 3. **Source Prefix for Source Data**
Source site data files prefixed with `source_`:
- `source_get_theme_configuration.json`
- `source_get_group_record.json`

### 4. **Destination Prefix for Destination Data**
Destination site data files prefixed with `destination_`:
- `destination_get_theme_configuration.json`
- `destination_update_response.json`

### 5. **Resource vs Job Mappers**
- `resource/` contains **templates** (never modified)
- `uploads/{job_id}/` contains **job-specific copies** (updated with values)

---

## 🎯 Error Handling

The migration handles errors gracefully:

- **Missing tokens**: Skips API calls, shows warning
- **API failures**: Logs error, saves what was successful
- **Missing variables**: Only updates variables that exist in source
- **Network issues**: Comprehensive error logging with retry information

---

## 📊 Console Output Example

```
================================================================================
🎨 STEP 2: BRAND/THEME SETUP - STARTING
================================================================================

📊 STEP 2 INFO:
  Source URL: https://www.pennybluerestaurant.com
  Source Site ID: 14941
  Font Pulled Checkbox: True
  Source Token exists: True

🔍 Checking if should call theme APIs...
✅ All conditions met - calling theme APIs now...

================================================================================
🎨 CALLING GET_THEME_CONFIGURATION API (SOURCE)
================================================================================
Theme Name: OSB Style- 1
Theme ID: 3
Group Mappings: 2 groups

💾 Saved response to: source_get_theme_configuration.json

================================================================================
🔧 CALLING GET_GROUP_RECORD API (SOURCE)
================================================================================
Group Records: 2 groups, 28 variables

💾 Saved response to: source_get_group_record.json

📋 Copying mapper files to job folder...
✅ Copied: font_mapper.json
✅ Copied: color_mapper.json

🔄 Updating mapper files with API data...
📊 Built lookup with 28 variables

📝 Updating font_mapper.json...
  ✓ Updated 'h1-font-family' (from 'primary-font-file') = 'AyerWeb-Regular'
  ✓ Updated 'body-font-family' (from 'secondary-font-file') = 'Roboto-Regular'
  ...
✅ Updated 14 entries in font_mapper.json

🎨 Updating color_mapper.json...
  ✓ Updated 'body-color' (from 'primary-bg') = '#FAF0de'
  ✓ Updated 'body-font-color' (from 'primary-color') = '#282864'
  ...
✅ Updated 44 entries in color_mapper.json

🎉 All mapper files updated successfully!

================================================================================
🎯 FETCHING DESTINATION SITE THEME DATA
================================================================================
Theme Name: Default Branding
Theme ID: 97

💾 Saved destination theme config

================================================================================
📦 CREATING FINAL PAYLOAD FOR THEME UPDATE
================================================================================
  Destination Site ID: 16696
  Destination Theme ID: 97
  Font Group Name: themetesting-internal-luxuryseparated_font
  Color Group Name: themetesting-internal-luxuryseparated_color

✅ Loaded 125 font variables
✅ Loaded 46 color variables

💾 Theme variables payload saved to: update_theme_variables_payload.json

📦 Payload Summary:
  Site ID: 16696
  Theme ID: 97
  Groups: 2
    - Color Group: themetesting-internal-luxuryseparated_color (46 variables)
    - Font Group: themetesting-internal-luxuryseparated_font (125 variables)

🎉 Final payload created and saved successfully!

================================================================================
🚀 UPDATING DESTINATION SITE THEME VARIABLES
================================================================================

📤 Sending update request to DESTINATION site...

📋 UPDATE RESPONSE
Success: True
Message: Theme variables saved successfully.

✅ Updated Groups:
  - Group ID: 3977 (Type: Color)
  - Group ID: 3978 (Type: Font)

💾 Theme variables response saved to: update_theme_variables_response.json

🎉 DESTINATION SITE THEME VARIABLES UPDATED SUCCESSFULLY!

================================================================================
🔧 FINALIZING THEME CONFIGURATION
================================================================================

📤 Updating theme configuration...
  Groups: [{"groupId": 3977}, {"groupId": 3978}]

📋 THEME CONFIGURATION RESPONSE
Success: True
Message: Website theme configuration updated successfully.

💾 Configuration response saved to: update_theme_configuration_response.json

✅ THEME CONFIGURATION FINALIZED SUCCESSFULLY!
```

---

## 🧩 API Integration Details

### 1. **generate_cms_token()**
- **Called in**: Step 1 (site_setup.py)
- **Purpose**: Generate authentication tokens for API calls
- **Token Storage**: Saved to `job_config` and persisted

### 2. **get_theme_configuration()**
- **Called in**: Step 2 (brand_theme.py)
- **Purpose**: Fetch theme structure, theme ID, group mappings
- **Used for**: Both source and destination sites

### 3. **get_group_record()**
- **Called in**: Step 2 (brand_theme.py)
- **Purpose**: Fetch all theme variables with their current values
- **Used for**: Source site only (provides data for mapping)

### 4. **update_theme_variables()**
- **Called in**: Step 2 (brand_theme.py)
- **Purpose**: Add new groups with variables to destination site
- **Returns**: New group IDs (used in next API call)

### 5. **update_theme_configuration()**
- **Called in**: Step 2 (brand_theme.py)
- **Purpose**: Link new groups to theme (finalize theme setup)
- **Uses**: Group IDs from previous API response

---

## 📈 Success Criteria

Step 2 is successful when:

✅ Source theme data fetched and saved  
✅ Font mapper updated with actual font values  
✅ Color mapper updated with actual color values  
✅ Destination theme ID retrieved  
✅ Update payloads created successfully  
✅ Theme variables updated on destination (groups created)  
✅ Theme configuration finalized (groups linked to theme)  
✅ All 10 files saved in job folder  

---

## 🎓 Summary

**Input**: Source and destination site credentials  
**Process**: 6-phase automated theme migration  
**Output**: Destination site with complete theme from source site  
**Files Generated**: 10 JSON files documenting entire migration  

**Result**: Complete theme migration with full audit trail! 🎨✨

