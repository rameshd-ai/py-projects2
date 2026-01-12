# Removed Features Documentation

This file documents features that were removed from the codebase and provides instructions for restoring them if needed in the future.

---

## Sub-Record Migration for MiBlock Components

**Date Removed:** 2026-01-12  
**Reason:** CMS automatically generates sub-records (child components) when a parent component is added. Manual migration was creating duplicate sub-records.

### What Was Removed

The automatic migration of child/nested component records across multiple levels. Previously, the system would migrate:
- **Level 0 (Parent):** Main component records - `mainComp()` function ✅ **KEPT**
- **Level 1 (Children):** First-level child records - `migrate_next_level_components(level=1)` ❌ **REMOVED**
- **Level 2 (Nested Children):** Second-level nested records - `migrate_next_level_components(level=2)` ❌ **REMOVED**
- **Level 3 (Deep Nested):** Third-level nested records - `migrate_next_level_components(level=3)` ❌ **REMOVED**

### Files Modified

**File:** `processing_steps/process_assembly.py`

**Location:** Lines ~746-749 in `add_records_for_page()` function

### Original Code (Before Removal)

```python
createPayloadJson(site_id, miBlockId, page_name)
createRecordsPayload(site_id, miBlockId, page_name)
# This is to add records of all levels
mainComp(save_folder, component_id, pageSectionGuid, base_url, headers, component_alias, vComponentId)
migrate_next_level_components(save_folder, pageSectionGuid, base_url, headers, level=1)
migrate_next_level_components(save_folder, pageSectionGuid, base_url, headers, level=2)
migrate_next_level_components(save_folder, pageSectionGuid, base_url, headers, level=3)
```

### Current Code (After Removal)

```python
createPayloadJson(site_id, miBlockId, page_name)
createRecordsPayload(site_id, miBlockId, page_name)
# This is to add records of all levels (parent only - CMS auto-generates sub-records)
mainComp(save_folder, component_id, pageSectionGuid, base_url, headers, component_alias, vComponentId)
# NOTE: Sub-record migration removed - CMS handles this automatically
# See REMOVED_FEATURES.md for restoration instructions
```

### Function Details

The `migrate_next_level_components()` function is still present in the codebase (line ~1549) but is no longer called. It handles:

**Function Signature:**
```python
def migrate_next_level_components(save_folder, pageSectionGuid, base_url, headers, level):
```

**Purpose:**
- Migrates component records at a specific level (1, 2, or 3)
- Processes records that have a `parent_new_record_id` and are not marked as `isMigrated`
- Uses bulk API when available, falls back to individual API calls
- Updates asset fields for records with images
- Tags next-level children with the new parent ID

**Key Features:**
- Bulk processing (up to 50 records at a time)
- Individual fallback for failed bulk operations
- Asset update integration via `update_record_asset_if_needed()`
- Parent-child relationship tracking

### How to Restore

If the CMS behavior changes or manual sub-record migration becomes necessary:

1. **Locate the function calls** in `processing_steps/process_assembly.py` around line 746
2. **Uncomment the migration calls:**

```python
mainComp(save_folder, component_id, pageSectionGuid, base_url, headers, component_alias, vComponentId)

# Restore these lines:
migrate_next_level_components(save_folder, pageSectionGuid, base_url, headers, level=1)
migrate_next_level_components(save_folder, pageSectionGuid, base_url, headers, level=2)
migrate_next_level_components(save_folder, pageSectionGuid, base_url, headers, level=3)
```

3. **Test thoroughly** with a small dataset first to ensure:
   - Sub-records are not duplicated
   - Parent-child relationships are correct
   - Asset updates work properly

### Related Functions

The following functions are still active and work with the `migrate_next_level_components()` function:

- `mainComp()` - Migrates parent (Level 0) records ✅ **ACTIVE**
- `update_record_asset_if_needed()` - Updates images for records ✅ **ACTIVE**
- `createPayloadJson()` - Creates component hierarchy JSON ✅ **ACTIVE**
- `createRecordsPayload()` - Creates records tree structure ✅ **ACTIVE**
- `add_levels_to_records()` - Adds level fields to records ✅ **ACTIVE**
- `add_has_image_to_records()` - Detects images in records ✅ **ACTIVE**

### Testing Evidence

**Component Tested:** 560556 on "What we do" page

**Observation:** When only parent records were migrated, the CMS automatically generated the appropriate sub-records, confirming that manual migration is redundant.

### Additional Notes

- The `migrate_next_level_components()` function definition has been **kept** in the codebase for future use
- All supporting infrastructure (bulk API, asset updates, parent ID tracking) remains intact
- Only the function **calls** have been removed from the processing pipeline

---

## Questions?

If you need to restore this feature or have questions about why it was removed, refer to:
- Git commit history around 2026-01-12
- This documentation file
- The `migrate_next_level_components()` function definition in `process_assembly.py` (line ~1549)

