# SectionGuid Fix Documentation
## Fix for Duplicate SectionGuid Issue When Same Component Used on Multiple Pages

### Problem Description

When the same component (mi-block) is used on multiple pages, the `sectionGuid` was being stored in `ComponentRecordsTree.json` (which is shared per component, not per page). This caused the `sectionGuid` to be overwritten by the last page processed, leading to incorrect mappings and publishing failures.

**Example Issue:**
- Component 560556 used on Page A → sectionGuid: `guid-1`
- Component 560556 used on Page B → sectionGuid: `guid-2` (overwrites `guid-1` in ComponentRecordsTree.json)
- When mapping Page A, it reads `guid-2` instead of `guid-1` → **WRONG MAPPING**

### Solution Overview

Instead of storing `sectionGuid` in the shared `ComponentRecordsTree.json` file, we now:
1. Store `sectionGuid` in a page-specific mapping: `PAGE_COMPONENT_SECTIONGUID_MAP`
2. Use this mapping when creating page mappings
3. Remove the storage of `sectionGuid` in `ComponentRecordsTree.json`

---

## Code Changes Required

### 1. Add Global Tracking Variable

**File:** `processing_steps/process_assembly.py`

**Location:** After line ~91 (after `PAGE_COMPONENT_SECTIONGUID_MAP` definition)

**Add:**
```python
# --- 3.5. GLOBAL PAGE-COMPONENT SECTIONGUID MAPPING (FIX FOR DUPLICATE SECTIONGUID ISSUE) ---
# Maps (page_name, component_id) -> sectionGuid to prevent sectionGuid from being overwritten
# when the same component is used on multiple pages
PAGE_COMPONENT_SECTIONGUID_MAP: Dict[Tuple[str, int], str] = {}  # (page_name, component_id) -> sectionGuid
```

---

### 2. Store SectionGuid in Mapping When Processing

**File:** `processing_steps/process_assembly.py`

**Location:** In `add_records_for_page()` function, around line ~340-346

**Find:**
```python
else:
    COMPONENT_GUID_TRACKER[component_key] = pageSectionGuid
    logging.info(f"[GUID] Generated unique pageSectionGuid for component '{component_alias_unpacked}' (ID: {component_id_unpacked}) on page '{page_name}': {pageSectionGuid}")
```

**Replace with:**
```python
else:
    COMPONENT_GUID_TRACKER[component_key] = pageSectionGuid
    # Store sectionGuid mapping per page+component to prevent overwriting when same component used on multiple pages
    PAGE_COMPONENT_SECTIONGUID_MAP[(page_name, component_id_unpacked)] = pageSectionGuid
    logging.info(f"[GUID] Generated unique pageSectionGuid for component '{component_alias_unpacked}' (ID: {component_id_unpacked}) on page '{page_name}': {pageSectionGuid}")
```

---

### 3. Remove SectionGuid Storage from ComponentRecordsTree.json

**File:** `processing_steps/process_assembly.py`

**Location:** In `mainComp()` function, around line ~1500-1502

**Find:**
```python
# *** CRITICAL FIX: Update properties in the in-memory record ***
record["isMigrated"] = True
record["sectionGuid"] = pageSectionGuid
record["component_alias"] = component_alias
record["vComponentId"] = vComponentId
```

**Replace with:**
```python
# *** CRITICAL FIX: Update properties in the in-memory record ***
record["isMigrated"] = True
# NOTE: Do NOT store sectionGuid in ComponentRecordsTree.json as it's page-specific
# and gets overwritten when the same component is used on multiple pages.
# sectionGuid is now tracked in PAGE_COMPONENT_SECTIONGUID_MAP instead.
# record["sectionGuid"] = pageSectionGuid  # REMOVED to fix duplicate sectionGuid issue
record["component_alias"] = component_alias
record["vComponentId"] = vComponentId
```

---

### 4. Update updatePageMapping() to Use Mapping Instead of File

**File:** `processing_steps/process_assembly.py`

**Location:** In `updatePageMapping()` function, around line ~680-690

**Find:**
```python
# Extract the required fields from the main component record
mapping_data = {
    "pageId": page_id,
    "vComponentAlias": main_component_record.get("component_alias"),
    "vComponentId": main_component_record.get("vComponentId", ""), 
    "contentEntityType": 2, # Fixed value (for body components)
    "pageSectionGuid": main_component_record.get("sectionGuid")
}
```

**Replace with:**
```python
# Extract the required fields from the main component record
# FIX: Get sectionGuid from PAGE_COMPONENT_SECTIONGUID_MAP instead of ComponentRecordsTree.json
# to prevent duplicate sectionGuid issue when same component is used on multiple pages
component_id_from_file_int = int(component_id_from_file) if component_id_from_file.isdigit() else None
section_guid = None
if page_name and component_id_from_file_int:
    section_guid = PAGE_COMPONENT_SECTIONGUID_MAP.get((page_name, component_id_from_file_int))

# Fallback to reading from ComponentRecordsTree.json if not found in mapping (for backward compatibility)
if not section_guid:
    section_guid = main_component_record.get("sectionGuid")
    if section_guid:
        logging.warning(f"[MAPPING] sectionGuid not found in PAGE_COMPONENT_SECTIONGUID_MAP for page '{page_name}', component {component_id_from_file}. Using value from ComponentRecordsTree.json (may be incorrect if component used on multiple pages).")

mapping_data = {
    "pageId": page_id,
    "vComponentAlias": main_component_record.get("component_alias"),
    "vComponentId": main_component_record.get("vComponentId", ""), 
    "contentEntityType": 2, # Fixed value (for body components)
    "pageSectionGuid": section_guid
}
```

---

### 5. Update Function Signature to Accept page_name

**File:** `processing_steps/process_assembly.py`

**Location:** Function definition for `updatePageMapping()`, around line ~653

**Find:**
```python
def updatePageMapping(base_url: str, headers: Dict[str, str], page_id: int, site_id: int, header_footer_details: Dict[str, Any], home_debug_log_callback=None, page_component_ids: Optional[set] = None, page_component_names: Optional[List[str]] = None, component_cache: Optional[List[Dict[str, Any]]] = None):
```

**Replace with:**
```python
def updatePageMapping(base_url: str, headers: Dict[str, str], page_id: int, site_id: int, header_footer_details: Dict[str, Any], home_debug_log_callback=None, page_name: Optional[str] = None, page_component_ids: Optional[set] = None, page_component_names: Optional[List[str]] = None, component_cache: Optional[List[Dict[str, Any]]] = None):
```

---

### 6. Update Call to updatePageMapping() to Pass page_name

**File:** `processing_steps/process_assembly.py`

**Location:** In `pageAction()` function, around line ~622

**Find:**
```python
_, mapping_payload = updatePageMapping(base_url, headers,page_id,site_id,header_footer_details, page_component_ids=page_component_ids, page_component_names=page_component_names, component_cache=component_cache)
```

**Replace with:**
```python
_, mapping_payload = updatePageMapping(base_url, headers,page_id,site_id,header_footer_details, page_name=page_name, page_component_ids=page_component_ids, page_component_names=page_component_names, component_cache=component_cache)
```

---

### 7. Update Call in process_home_page.py

**File:** `processing_steps/process_home_page.py`

**Location:** Around line ~485

**Find:**
```python
_, mapping_payload = updatePageMapping(base_url, headers, page_id, site_id, header_footer_details, home_debug_log_callback=append_home_debug_log, page_component_ids=page_component_ids, page_component_names=page_component_names, component_cache=component_cache)
```

**Replace with:**
```python
_, mapping_payload = updatePageMapping(base_url, headers, page_id, site_id, header_footer_details, home_debug_log_callback=append_home_debug_log, page_name=page_name, page_component_ids=page_component_ids, page_component_names=page_component_names, component_cache=component_cache)
```

---

### 8. Update publishPage() to Use mapping_payload for SectionGuid

**File:** `processing_steps/process_assembly.py`

**Location:** In `publishPage()` function, around line ~880-893

**Find:**
```python
if main_component_record:
    # Extract the required fields (ComponentId and sectionGuid)
    component_id = str(main_component_record.get("ComponentId"))
    section_guid = main_component_record.get("sectionGuid")
    
    # CRITICAL: Only add components that are mapped to THIS page
    # Check if this sectionGuid is in the mapping payload for this page
    if component_id and section_guid:
```

**Replace with:**
```python
if main_component_record:
    # Extract the required fields (ComponentId and sectionGuid)
    component_id = str(main_component_record.get("ComponentId"))
    # FIX: Get sectionGuid from mapping_payload instead of ComponentRecordsTree.json
    # to prevent duplicate sectionGuid issue when same component is used on multiple pages
    section_guid = None
    if mapping_payload:
        # Find sectionGuid for this component from mapping_payload
        for mapping_entry in mapping_payload:
            if str(mapping_entry.get("vComponentId", "")) == str(main_component_record.get("vComponentId", "")):
                section_guid = mapping_entry.get("pageSectionGuid")
                break
    
    # Fallback to reading from ComponentRecordsTree.json if not found in mapping_payload (for backward compatibility)
    if not section_guid:
        section_guid = main_component_record.get("sectionGuid")
        if section_guid:
            logging.warning(f"[PUBLISH] sectionGuid not found in mapping_payload for component {component_id}. Using value from ComponentRecordsTree.json (may be incorrect if component used on multiple pages).")
    
    # CRITICAL: Only add components that are mapped to THIS page
    # Check if this sectionGuid is in the mapping payload for this page
    if component_id and section_guid:
```

---

## Testing Checklist

After implementing the fix, verify:

1. ✅ Same component used on multiple pages gets different `sectionGuid` for each page
2. ✅ Page mappings are created correctly with the right `sectionGuid` per page
3. ✅ Publishing works correctly for pages using the same component
4. ✅ No errors in logs about missing `sectionGuid`
5. ✅ Check `PAGE_COMPONENT_SECTIONGUID_MAP` contains entries for all page+component combinations

---

## Important Notes

- **Backward Compatibility**: The code includes fallback logic to read from `ComponentRecordsTree.json` if the mapping is not found, but this should not happen in normal operation
- **No Breaking Changes**: This fix only affects how `sectionGuid` is stored and retrieved; it doesn't change any API calls or data structures
- **Performance**: The mapping lookup is O(1) dictionary access, so there's no performance impact

---

## Summary

The fix ensures that each page gets its own unique `sectionGuid` for components, even when the same component is used on multiple pages. This prevents mapping and publishing errors that occurred when `sectionGuid` values were overwritten in the shared `ComponentRecordsTree.json` file.

