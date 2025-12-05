# 🔌 CMS API Documentation

## Overview

The `apis.py` module provides integration with CMS Theme APIs for automated theme migration and management.

---

## 📋 API Functions

### 1. **generate_cms_token()**

Generate authentication token for CMS API access.

**Signature:**
```python
generate_cms_token(base_url: str, profile_alias: str) -> dict
```

**Parameters:**
- `base_url` (str): CMS base URL (e.g., "https://example.com")
- `profile_alias` (str): Profile alias ID for authentication

**Returns:**
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expiresIn": 86400
}
```

**Usage:**
```python
from apis import generate_cms_token

token_response = generate_cms_token(
    base_url="https://www.example.com",
    profile_alias="79455"
)
token = token_response.get('token')
```

---

### 2. **get_theme_configuration()**

Fetch theme configuration including theme ID and group mappings.

**Signature:**
```python
get_theme_configuration(base_url: str, site_id: int, headers: dict) -> dict
```

**Parameters:**
- `base_url` (str): CMS base URL
- `site_id` (int): Site ID
- `headers` (dict): HTTP headers with Authorization token

**Request:**
```json
{
  "SiteId": 14941
}
```

**Returns:**
```json
{
  "websiteThemeMappping": {
    "themeName": "OSB Style- 1",
    "themeId": 3,
    "groupMapping": [
      {
        "groupId": 1254,
        "groupName": "Penny Blue - Color",
        "groupType": 1
      },
      {
        "groupId": 1255,
        "groupName": "Penny Blue - Font",
        "groupType": 2
      }
    ]
  },
  "success": true,
  "errorMessage": null
}
```

**Usage:**
```python
from apis import get_theme_configuration

headers = {
    'Authorization': f'Bearer {token}',
    'Content-Type': 'application/json'
}

response = get_theme_configuration(
    base_url="https://www.example.com",
    site_id=14941,
    headers=headers
)

theme_id = response['websiteThemeMappping']['themeId']
```

---

### 3. **get_group_record()**

Fetch theme group records with all variables and their values.

**Signature:**
```python
get_group_record(base_url: str, payload: dict, headers: dict) -> dict
```

**Parameters:**
- `base_url` (str): CMS base URL
- `payload` (dict): Request payload with SiteId and groups
- `headers` (dict): HTTP headers with Authorization token

**Request Payload:**
```json
{
  "SiteId": 14941,
  "groups": [
    {"themeId": 3, "groupId": 1254},
    {"themeId": 3, "groupId": 1255}
  ]
}
```

**Returns:**
```json
{
  "groupsRecordDetails": [
    {
      "themeId": 3,
      "themeName": "OSB Style- 1",
      "groupId": 1254,
      "groupName": "Penny Blue - Color",
      "grouptype": 1,
      "groupVariables": [
        {
          "variableName": "Primary Color",
          "variableType": 1,
          "variableAlias": "primary-color",
          "variableValue": "#282864"
        },
        {
          "variableName": "Primary BG",
          "variableType": 1,
          "variableAlias": "primary-bg",
          "variableValue": "#FAF0de"
        }
      ]
    }
  ],
  "success": true,
  "errorMessage": null
}
```

**Usage:**
```python
from apis import get_group_record

payload = {
    "SiteId": 14941,
    "groups": [
        {"themeId": 3, "groupId": 1254},
        {"themeId": 3, "groupId": 1255}
    ]
}

response = get_group_record(
    base_url="https://www.example.com",
    payload=payload,
    headers=headers
)

variables = response['groupsRecordDetails'][0]['groupVariables']
```

---

### 4. **update_theme_variables()**

Add or update theme groups with variables on destination site.

**Signature:**
```python
update_theme_variables(base_url: str, payload: dict, headers: dict) -> dict
```

**Parameters:**
- `base_url` (str): CMS base URL
- `payload` (dict): Complete request payload
- `headers` (dict): HTTP headers with Authorization token

**Request Payload:**
```json
{
  "siteId": 16696,
  "themeId": 97,
  "groups": [
    {
      "Groupid": 0,
      "GroupName": "mysite_color",
      "GroupType": 1,
      "themeVariables": "{\"body-color\":\"#FAF0de\",\"body-font-color\":\"#282864\"}"
    },
    {
      "Groupid": 0,
      "GroupName": "mysite_font",
      "GroupType": 2,
      "themeVariables": "{\"h1-font-family\":\"Arial\",\"body-font-size\":\"15px\"}"
    }
  ]
}
```

**Returns:**
```json
{
  "success": true,
  "message": "Theme variables saved successfully.",
  "data": [
    {
      "GroupId": 3977,
      "GroupType": 1
    },
    {
      "GroupId": 3978,
      "GroupType": 2
    }
  ]
}
```

**Usage:**
```python
from apis import update_theme_variables

payload = {
    "siteId": 16696,
    "themeId": 97,
    "groups": [...]
}

response = update_theme_variables(
    base_url="https://destination.com",
    payload=payload,
    headers=headers
)

# Extract new group IDs
color_group_id = response['data'][0]['GroupId']
font_group_id = response['data'][1]['GroupId']
```

---

### 5. **update_theme_configuration()**

Finalize theme configuration by linking groups to theme.

**Signature:**
```python
update_theme_configuration(base_url: str, payload: dict, headers: dict) -> dict
```

**Parameters:**
- `base_url` (str): CMS base URL
- `payload` (dict): Complete request payload
- `headers` (dict): HTTP headers with Authorization token

**Request Payload:**
```json
{
  "siteId": 16696,
  "themeId": 97,
  "groups": [
    {"groupId": 3977},
    {"groupId": 3978}
  ]
}
```

**Returns:**
```json
{
  "success": true,
  "message": "Website theme configuration updated successfully."
}
```

**Usage:**
```python
from apis import update_theme_configuration

# Use group IDs from update_theme_variables response
payload = {
    "siteId": 16696,
    "themeId": 97,
    "groups": [
        {"groupId": 3977},
        {"groupId": 3978}
    ]
}

response = update_theme_configuration(
    base_url="https://destination.com",
    payload=payload,
    headers=headers
)

if response.get('success'):
    print("Theme configuration finalized!")
```

---

## 🔄 Complete API Call Sequence

### Step 1: Token Generation
```python
# Generate tokens for both sites
source_token = generate_cms_token(source_url, source_profile_alias)
destination_token = generate_cms_token(destination_url, destination_profile_alias)
```

### Step 2: Theme Migration
```python
# 1. Fetch source theme structure
source_theme = get_theme_configuration(source_url, source_site_id, source_headers)

# 2. Fetch source theme variables
source_groups = get_group_record(source_url, source_payload, source_headers)

# 3. Map variables (internal processing)
# ... mapping logic ...

# 4. Fetch destination theme info
dest_theme = get_theme_configuration(dest_url, dest_site_id, dest_headers)

# 5. Update destination theme variables
update_response = update_theme_variables(dest_url, variables_payload, dest_headers)

# 6. Extract group IDs and finalize
group_ids = [g['GroupId'] for g in update_response['data']]
config_response = update_theme_configuration(dest_url, config_payload, dest_headers)
```

---

## 🛡️ Error Handling

All API functions include comprehensive error handling:

```python
try:
    response = requests.post(api_endpoint, json=payload, headers=headers, timeout=30)
    response.raise_for_status()
    return response.json()
except requests.exceptions.HTTPError as http_err:
    logging.error(f"HTTP error: {http_err}")
    return None
except requests.exceptions.ConnectionError as conn_err:
    logging.error(f"Connection error: {conn_err}")
    return None
except requests.exceptions.Timeout as timeout_err:
    logging.error(f"Timeout error: {timeout_err}")
    return None
except Exception as e:
    logging.error(f"Unexpected error: {e}")
    return None
```

**All functions return `None` on error, allowing graceful degradation.**

---

## 📝 Best Practices

### 1. **Always Check Response**
```python
response = get_theme_configuration(...)
if response and response.get('success'):
    # Process response
else:
    # Handle error
```

### 2. **Use Payload Pattern**
```python
# Good: Flexible and clear
payload = {"siteId": 123, "groups": [...]}
response = get_group_record(base_url, payload, headers)

# Avoid: Too many parameters
response = get_group_record(base_url, site_id, groups, headers)
```

### 3. **Save All Payloads and Responses**
```python
# Save payload
with open('payload.json', 'w') as f:
    json.dump(payload, f, indent=4)

# Call API
response = api_function(...)

# Save response
with open('response.json', 'w') as f:
    json.dump(response, f, indent=4)
```

### 4. **Use Descriptive File Names**
```python
# Good: Clear what it contains
"update_theme_variables_payload.json"
"update_theme_variables_response.json"

# Avoid: Generic names
"payload.json"
"response.json"
```

---

## 🎯 Summary

The `apis.py` module provides:

✅ **5 CMS API integrations**  
✅ **Payload-based design** for flexibility  
✅ **Comprehensive error handling**  
✅ **Detailed logging** for debugging  
✅ **Type hints** for code clarity  
✅ **Timeout protection** (30 seconds)  
✅ **JSON response parsing**  

**Perfect for automated theme migration workflows!** 🚀

