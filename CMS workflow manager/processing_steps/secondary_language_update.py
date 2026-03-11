"""
Update secondary language menu data into existing CMS records.

Revised flow:
- Use site_languages (from GetSiteLanguages) to get primary and secondary language IDs.
- Process one secondary language at a time. For each:
  - Get its destinationLanguageId from site_languages.
  - Get ALL records for that language only (LanguageId == that id), ordered: main menus (L0) first, then their sections (L1), then their items (L2).
  - Load that language's menu JSON, normalize order to 1,2,3,4, build data sequence.
  - Update each record in order via SaveMiblockRecord, passing recordId. Missing data is sent as blank so primary dummy values are replaced.
- Then do the same for the next secondary language if any.
"""
import os
import re
import json
import time
import logging
from typing import Dict, Any, List, Tuple, Optional

from apis import addUpdateRecordsToCMS
from utils import get_job_folder, load_job_config, make_destination_token_refresh_callback
from config import BASE_DIR

logger = logging.getLogger(__name__)

# #region agent log
_DEBUG_LOG = os.path.join(BASE_DIR, ".cursor", "debug.log")
def _agent_log(msg: str, data: Dict, hypothesis_id: str = None):
    try:
        payload = {"timestamp": int(time.time() * 1000), "location": "secondary_language_update.py", "message": msg, "data": data}
        if hypothesis_id:
            payload["hypothesisId"] = hypothesis_id
        with open(_DEBUG_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        pass
# #endregion

RESOURCE_DIR = os.path.join(BASE_DIR, "resource")
MENU_FIELD_MAPPER_PATH = os.path.join(RESOURCE_DIR, "menu_field_mapper.json")
MENU_PAYLOAD_TEMPLATE_PATH = os.path.join(RESOURCE_DIR, "menu_payload_template.json")


def _load_json(path: str) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("Load %s: %s", path, e)
        return None


def _get_primary_language_id(site_languages: List[Dict]) -> Optional[int]:
    for lang in site_languages or []:
        if lang.get("isPrimary"):
            return lang.get("destinationLanguageId")
    return None


def _get_level2_api_value(api_data: Dict, cms_key: str, api_key: str) -> Any:
    """
    Get value for level_2 (item) from API item. API has ItemPrices[] and ItemAddons[]
    instead of flat Price/item-price-option-N, so we resolve those here (same as html_menu).
    """
    if not isinstance(api_data, dict):
        return None
    # item-price-option-N or item-price-option-N-description: from ItemPrices[N-1]
    m = re.match(r"item-price-option-(\d+)(-description)?$", cms_key)
    if m:
        idx = int(m.group(1))
        prices = api_data.get("ItemPrices") or []
        if idx <= len(prices):
            p = prices[idx - 1]
            if m.group(2):
                return p.get("PriceDescription") or p.get(api_key)
            return p.get("Price") or p.get(api_key)
        return ""
    # item-add-on-N-name, item-add-on-N-price, item-add-on-N-price-notes: from ItemAddons[N-1]
    m = re.match(r"item-add-on-(\d+)-(name|price|price-notes)$", cms_key)
    if m:
        idx = int(m.group(1))
        sub = m.group(2)
        addons = api_data.get("ItemAddons") or []
        if idx <= len(addons):
            a = addons[idx - 1]
            if sub == "name":
                return a.get("Name") or a.get(api_key)
            if sub == "price":
                return a.get("Price") or a.get(api_key)
            return a.get("PriceNotes", "") or ""
        return ""
    # item-price / item-price-description: from ItemPrices[0] if present
    if cms_key == "item-price":
        prices = api_data.get("ItemPrices") or []
        if prices:
            return prices[0].get("Price") or api_data.get(api_key)
    if cms_key == "item-price-description":
        prices = api_data.get("ItemPrices") or []
        if prices:
            return prices[0].get("PriceDescription") or api_data.get(api_key)
    # Direct field
    return api_data.get(api_key)


def _api_data_to_record_json_string(level: str, api_data: Dict, field_mapper: Dict, template_record: Dict) -> str:
    """Map API menu/section/item object to CMS recordJsonString using menu_field_mapper."""
    if isinstance(level, int):
        level_key = f"level_{level}"
    else:
        level_key = level if level in ("level_0", "level_1", "level_2") else f"level_{level}"
    mapper = (field_mapper or {}).get(level_key, {})
    template = (template_record or {}).get("recordJsonString", {})
    out = {}
    for cms_key in template:
        api_key = mapper.get(cms_key, cms_key)
        if level_key == "level_2" and isinstance(api_data, dict):
            value = _get_level2_api_value(api_data, cms_key, api_key)
        elif level_key == "level_0" and isinstance(api_data, dict) and cms_key in ("menu-title", "menu-type"):
            value = api_data.get("Name") or api_data.get("name") or api_data.get(api_key)
        else:
            value = api_data.get(api_key) if isinstance(api_data, dict) else None
        if value is None:
            value = template.get(cms_key, "")
        if value is None and isinstance(template.get(cms_key), list):
            value = []
        out[cms_key] = value
    return json.dumps(out)


def _build_primary_ordered_sequence(records: List[Dict], component_ids: Dict[str, int]) -> List[Tuple[int, Dict]]:
    """
    Build ordered list (level, record) for primary records only.
    level 0 = L0, 1 = L1, 2 = L2. Order: L0 by DisplayOrder, then L1 children by DisplayOrder, then L2.
    """
    l0_cid = component_ids.get("L0")
    l1_cid = component_ids.get("L1")
    l2_cid = component_ids.get("L2")
    primary_l0 = [r for r in records if r.get("ComponentId") == l0_cid and (r.get("LanguageId") == 0 or r.get("PrimaryLanguageRecordId") is None)]
    primary_l0.sort(key=lambda r: (r.get("DisplayOrder") or 0, r["Id"]))
    result = []
    for r0 in primary_l0:
        result.append((0, r0))
        children_l1 = [r for r in records if r.get("ParentId") == r0["Id"] and r.get("ComponentId") == l1_cid and (r.get("LanguageId") == 0 or r.get("PrimaryLanguageRecordId") is None)]
        children_l1.sort(key=lambda r: (r.get("DisplayOrder") or 0, r["Id"]))
        for r1 in children_l1:
            result.append((1, r1))
            children_l2 = [r for r in records if r.get("ParentId") == r1["Id"] and r.get("ComponentId") == l2_cid and (r.get("LanguageId") == 0 or r.get("PrimaryLanguageRecordId") is None)]
            children_l2.sort(key=lambda r: (r.get("DisplayOrder") or 0, r["Id"]))
            for r2 in children_l2:
                result.append((2, r2))
    return result


def _build_primary_sequence_from_summary(job_folder: str) -> Optional[List[Tuple[int, int]]]:
    """
    Build primary sequence (level, primary_record_id) from record_ids_summary.json if it exists.
    Order: menu1 L0, its sections L1, its items L2, menu2 L0, ... so 1st slot = 1st primary menu's secondary gets 1st secondary data.
    Returns list of (level, primary_record_id) or None if file missing/empty.
    """
    path = os.path.join(job_folder, "record_ids_summary.json")
    data = _load_json(path)
    if not data or not isinstance(data.get("menus"), list):
        return None
    result = []
    for menu in data["menus"]:
        l0_id = menu.get("L0_record_id")
        if l0_id is not None:
            result.append((0, int(l0_id)))
        for sec in menu.get("sections") or []:
            l1_id = sec.get("L1_record_id")
            if l1_id is not None:
                result.append((1, int(l1_id)))
            for l2_id in sec.get("L2_record_ids") or []:
                if l2_id is not None:
                    result.append((2, int(l2_id)))
    return result if result else None


def _build_secondary_records_sequence_for_language(
    records: List[Dict], component_ids: Dict[str, int], lang_id: int
) -> List[Tuple[int, Dict]]:
    """
    Get ALL records for one secondary language (LanguageId == lang_id) in tree order:
    first all main menus (L0), then their sections (L1), then their items (L2).
    Same order as _build_secondary_data_sequence so we can zip 1:1 with menu data.
    """
    l0_cid = component_ids.get("L0")
    l1_cid = component_ids.get("L1")
    l2_cid = component_ids.get("L2")
    l0_recs = [r for r in records if r.get("ComponentId") == l0_cid and r.get("LanguageId") == lang_id and (r.get("ParentId") == 0 or r.get("ParentId") is None)]
    l0_recs.sort(key=lambda r: (r.get("DisplayOrder") or 0, r["Id"]))
    result = []
    for r0 in l0_recs:
        result.append((0, r0))
        l1_recs = [r for r in records if r.get("ParentId") == r0["Id"] and r.get("ComponentId") == l1_cid and r.get("LanguageId") == lang_id]
        l1_recs.sort(key=lambda r: (r.get("DisplayOrder") or 0, r["Id"]))
        for r1 in l1_recs:
            result.append((1, r1))
            l2_recs = [r for r in records if r.get("ParentId") == r1["Id"] and r.get("ComponentId") == l2_cid and r.get("LanguageId") == lang_id]
            l2_recs.sort(key=lambda r: (r.get("DisplayOrder") or 0, r["Id"]))
            for r2 in l2_recs:
                result.append((2, r2))
    return result


def _build_secondary_data_sequence(menu_api_list: List[Dict], field_mapper: Dict, template: Dict) -> List[Tuple[int, str]]:
    """
    Flatten menu API response to (level, recordDataJson) in same order as primary tree.
    level 0 = menu, 1 = section, 2 = item. Uses MenuOrder, SectionOrder, ItemOrder.
    """
    if not menu_api_list:
        return []
    # Sort menus by MenuOrder
    menus = sorted(menu_api_list, key=lambda m: (safe_int(m.get("MenuOrder")), m.get("Name", "")))
    result = []
    for menu in menus:
        record_json = _api_data_to_record_json_string("level_0", menu, field_mapper, template.get("level 0", {}).get("recordList", [{}])[0])
        result.append((0, record_json))
        sections = menu.get("Sections") or []
        sections = sorted(sections, key=lambda s: (safe_int(s.get("SectionOrder")), s.get("SectionName", "")))
        for sec in sections:
            sec_template = template.get("level 1", {}).get("recordList", [{}])[0]
            record_json = _api_data_to_record_json_string("level_1", sec, field_mapper, sec_template)
            result.append((1, record_json))
            items = sec.get("Items") or []
            items = sorted(items, key=lambda i: (safe_int(i.get("ItemOrder")), i.get("SectionItemName", "")))
            for item in items:
                item_template = template.get("level 2", {}).get("recordList", [{}])[0]
                record_json = _api_data_to_record_json_string("level_2", item, field_mapper, item_template)
                result.append((2, record_json))
    return result


def safe_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    if isinstance(value, str):
        value = value.strip()
        if value == "":
            return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def _normalize_display_order_secondary_api(menu_list: List[Dict]) -> List[Dict]:
    """
    Normalize order at all levels to 1, 2, 3, 4 (like primary).
    Sorts menus by MenuOrder then sets MenuOrder = 1,2,3,...;
    for each menu sorts Sections by SectionOrder and sets SectionOrder = 1,2,3,...;
    for each section sorts Items by ItemOrder and sets ItemOrder = 1,2,3,...
    Reorders the list in place so saved file has first menu = 1, second = 2, etc.
    """
    if not menu_list:
        return menu_list
    # Sort menus by MenuOrder and assign 1,2,3,...
    menus = sorted(menu_list, key=lambda m: (safe_int(m.get("MenuOrder")), m.get("Name", "")))
    for idx, menu in enumerate(menus, 1):
        menu["MenuOrder"] = idx
        sections = menu.get("Sections") or []
        sections = sorted(sections, key=lambda s: (safe_int(s.get("SectionOrder")), s.get("SectionName", "")))
        for sidx, sec in enumerate(sections, 1):
            sec["SectionOrder"] = sidx
            items = sec.get("Items") or []
            items = sorted(items, key=lambda i: (safe_int(i.get("ItemOrder")), i.get("SectionItemName", "")))
            for iidx, item in enumerate(items, 1):
                item["ItemOrder"] = iidx
            sec["Items"] = items
        menu["Sections"] = sections
    # Replace list contents so saved order matches 1,2,3,4
    menu_list.clear()
    menu_list.extend(menus)
    return menu_list


def _ensure_orphan_primaries_and_reexport(
    job_id: str,
    job_folder: str,
    job_config: Dict,
    records: List[Dict],
    component_ids: Dict[str, int],
    log: List[Dict],
    dry_run: bool = False,
) -> List[Dict]:
    """
    Find secondary records with no primary (PrimaryLanguageRecordId 0 or null).
    For each, create an inactive primary record using the secondary's data, then re-export and return new records list.
    When dry_run is True, skip all API calls and re-export; return records as-is.
    """
    if dry_run:
        return records
    from apis import getComponentInfo, export_mi_block_component
    from .html_menu import get_menu_component_names

    destination_url = (job_config.get("destinationUrl") or "").strip()
    destination_token = job_config.get("destination_cms_token")
    if not destination_url or not destination_token:
        return records
    l0_cid = component_ids.get("L0")
    orphans = [r for r in records if r.get("LanguageId") not in (0, None) and r.get("PrimaryLanguageRecordId") in (0, None) and r.get("ComponentId") == l0_cid]
    if not orphans:
        return records
    log.append({"step": 3, "message": f"Found {len(orphans)} orphan secondary record(s); creating inactive primary record(s)..."})
    logger.info("[Step 3] Found %s orphan secondary record(s); creating inactive primary record(s)...", len(orphans))
    headers = {
        "Content-Type": "application/json",
        "ms_cms_clientapp": "ProgrammingApp",
        "Authorization": f"Bearer {destination_token}",
    }
    destination_site_id = (job_config.get("destinationSiteId") or job_config.get("destination_site_id") or "").strip()
    created = 0
    for rec in orphans:
        record_data_json = rec.get("RecordJsonString") or "{}"
        try:
            data_dict = json.loads(record_data_json)
            data_dict.pop("Id", None)
            data_dict.pop("ParentId", None)
            data_dict.pop("LanguageCode", None)
            data_dict.pop("PrimaryLanguageRecordId", None)
            data_dict.pop("LanguageId", None)
            data_dict.pop("UrlLanguageCode", None)
            record_data_json = json.dumps(data_dict)
        except Exception:
            pass
        payload = {
            "componentId": int(rec["ComponentId"]),
            "recordId": 0,
            "parentRecordId": 0,
            "recordDataJson": record_data_json,
            "status": False,
            "tags": [],
            "displayOrder": int(rec.get("DisplayOrder") or 0),
            "updatedBy": 0,
        }
        api_payload = {f"orphan_primary_{rec['Id']}": [payload]}
        refresh_cb = make_destination_token_refresh_callback(job_id)
        success, _ = addUpdateRecordsToCMS(destination_url, headers, api_payload, batch_size=1, refresh_token_callback=refresh_cb)
        if success:
            created += 1
        time.sleep(1)
    if created == 0:
        return records
    log.append({"step": 3, "message": f"Created {created} inactive primary record(s); re-exporting to get latest..."})
    logger.info("[Step 3] Created %s inactive primary record(s); re-exporting to get latest...", created)
    try:
        names = get_menu_component_names()
        root_name = names.get("level_0", "Menu-new")
        response_data = getComponentInfo(root_name, destination_url, headers)
        if not response_data or not isinstance(response_data, list) or len(response_data) == 0:
            return records
        component_id = response_data[0].get("Id")
        if not component_id:
            return records
        time.sleep(1)
        response_content, content_disposition = export_mi_block_component(destination_url, component_id, destination_site_id, headers)
        if not response_content:
            return records
        import zipfile
        output_dir = job_folder
        mi_block_folder = f"mi-block-ID-{component_id}"
        save_folder = os.path.join(output_dir, mi_block_folder)
        os.makedirs(save_folder, exist_ok=True)
        filename = content_disposition.split("filename=")[1].strip('"') if content_disposition and "filename=" in (content_disposition or "") else f"menu_export_{job_id}.zip"
        zip_path = os.path.join(save_folder, filename)
        with open(zip_path, "wb") as f:
            f.write(response_content)
        if zipfile.is_zipfile(zip_path):
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(save_folder)
            os.remove(zip_path)
        rec_path = os.path.join(save_folder, "MiBlockComponentRecords.json")
        if os.path.isfile(rec_path):
            new_data = _load_json(rec_path)
            if new_data and "componentRecords" in new_data:
                return new_data["componentRecords"]
    except Exception as e:
        logger.warning("Re-export after orphan create failed: %s", e)
        log.append({"step": 3, "message": f"Re-export failed: {str(e)}; continuing with current records."})
        logger.warning("[Step 3] Re-export failed: %s; continuing with current records.", e)
    return records


def run_secondary_language_update_step(
    job_id: str,
    steps_log: Optional[List[Dict]] = None,
    lang_key: Optional[str] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Updates existing secondary language records with menu data from each secondary site.
    - lang_key: if set ('lang1', 'lang2', 'lang3'), only update that language; otherwise all configured.
    - dry_run: if True, build payloads and write secondary_update_paper_check.json only; no API calls, no DB writes.
    - Optionally creates inactive primary records for orphan secondaries, then re-exports (skipped when dry_run).
    - Loads export records, site_languages, component map, and secondary menu JSON per lang.
    - Aligns secondary menu data to primary sequence by position.
    - Calls SaveMiblockRecord for each secondary record with updated recordDataJson (unless dry_run).
    """
    log = steps_log if steps_log is not None else []

    def _step(msg: str) -> None:
        log.append({"step": 3, "message": msg})
        logger.info("[Step 3] %s", msg)

    job_folder = get_job_folder(job_id)
    job_config = load_job_config(job_id)
    destination_url = (job_config.get("destinationUrl") or "").strip()
    destination_token = job_config.get("destination_cms_token")
    if not destination_url or not destination_token:
        _step("Update skipped: destination URL or token missing.")
        return {"success": False, "error": "Destination URL or token missing", "steps": log}

    # Resolve mi-block folder (same component ID as in map)
    component_map_path = os.path.join(job_folder, "menu_component_name_id_map.json")
    component_map = _load_json(component_map_path)
    if not component_map:
        _step("Update skipped: component map not found.")
        return {"success": False, "error": "Component map not found", "steps": log}

    from .html_menu import get_menu_component_names
    names = get_menu_component_names()
    l0_name = names.get("level_0", "Menu-new")
    l1_name = names.get("level_1", "Menu-new Section")
    l2_name = names.get("level_2", "Menu-new Section Item")
    l0_cid = (component_map.get(l0_name) or {}).get("ComponentId")
    l1_cid = (component_map.get(l1_name) or {}).get("ComponentId")
    l2_cid = (component_map.get(l2_name) or {}).get("ComponentId")
    if not all([l0_cid, l1_cid, l2_cid]):
        _step("Update skipped: missing L0/L1/L2 component IDs in map.")
        return {"success": False, "error": "Missing component IDs", "steps": log}
    component_ids = {"L0": l0_cid, "L1": l1_cid, "L2": l2_cid}

    # Find MiBlockComponentRecords.json (in mi-block-ID-* folder)
    mi_block_folder = None
    for name in os.listdir(job_folder):
        path = os.path.join(job_folder, name)
        if os.path.isdir(path) and name.startswith("mi-block-ID-"):
            rec_path = os.path.join(path, "MiBlockComponentRecords.json")
            if os.path.isfile(rec_path):
                mi_block_folder = path
                break
    if not mi_block_folder:
        _step("Update skipped: MiBlockComponentRecords.json not found in job folder.")
        return {"success": False, "error": "MiBlockComponentRecords not found", "steps": log}

    records_data = _load_json(os.path.join(mi_block_folder, "MiBlockComponentRecords.json"))
    if not records_data or "componentRecords" not in records_data:
        _step("Update skipped: no componentRecords in export.")
        return {"success": False, "error": "No componentRecords", "steps": log}
    records = records_data["componentRecords"]

    # Orphan handling: create inactive primary for secondary-only records, then re-export (skipped when dry_run)
    records = _ensure_orphan_primaries_and_reexport(job_id, job_folder, job_config, records, component_ids, log, dry_run=dry_run)

    # Primary sequence: order of records in destination (menu1, then its sections, then its items, then menu2, ...)
    # Use record_ids_summary.json if present (same sequence as when primary records were created), else from export
    primary_sequence = _build_primary_sequence_from_summary(job_folder)
    if primary_sequence:
        _step(f"Using primary sequence from record_ids_summary.json: {len(primary_sequence)} slots.")
    else:
        primary_seq_recs = _build_primary_ordered_sequence(records, component_ids)
        primary_sequence = [(lev, rec["Id"]) for lev, rec in primary_seq_recs] if primary_seq_recs else []
        _step(f"Using primary sequence from export: {len(primary_sequence)} slots.")
    if not primary_sequence:
        _step("Update skipped: no primary sequence.")
        return {"success": False, "error": "No primary sequence", "steps": log}

    # Visibility: how much primary we have (so user sees "primary and secondary" picture)
    primary_l0 = sum(1 for lev, _ in primary_sequence if lev == 0)
    primary_l1 = sum(1 for lev, _ in primary_sequence if lev == 1)
    primary_l2 = sum(1 for lev, _ in primary_sequence if lev == 2)
    _step(f"Primary (anchor): {primary_l0} menus (L0), {primary_l1} sections (L1), {primary_l2} items (L2) = {len(primary_sequence)} slots. Updating existing secondary records only (1st↔1st, 2nd↔2nd, …). No new records created.")

    # #region agent log
    _agent_log("Step 3 update starting", {"job_id": job_id, "records_count": len(records), "primary_sequence_len": len(primary_sequence)}, "H5")
    # #endregion

    # Map (primary_record_id, lang_id) -> secondary record (so 1st primary's secondary gets 1st secondary data)
    secondary_by_primary_lang: Dict[Tuple[int, int], Dict] = {}
    for r in records:
        pr = r.get("PrimaryLanguageRecordId")
        if pr is None or pr == 0:
            continue
        lid = r.get("LanguageId")
        if lid is None:
            continue
        secondary_by_primary_lang[(int(pr), int(lid))] = r

    site_languages = _load_json(os.path.join(job_folder, "site_languages.json"))
    if not isinstance(site_languages, list):
        site_languages = []
    secondary_lang_entries = [sl for sl in site_languages if not sl.get("isPrimary")]
    if not secondary_lang_entries:
        _step("Update skipped: no secondary languages in site_languages.")
        return {"success": False, "error": "No secondary languages", "steps": log}

    field_mapper = _load_json(MENU_FIELD_MAPPER_PATH) or {}
    template = _load_json(MENU_PAYLOAD_TEMPLATE_PATH) or {}
    secondary_config = job_config.get("secondaryLanguage") or {}
    configured_langs = [
        (lk, secondary_config.get(lk) or {})
        for lk in ["lang1", "lang2", "lang3"]
        if (secondary_config.get(lk) or {}).get("sourceUrl")
    ]
    if lang_key and not any(lk == lang_key for lk, _ in configured_langs):
        _step(f"Update skipped: {lang_key} not configured (sourceUrl).")
        return {"success": False, "error": f"{lang_key} not configured", "steps": log}
    if not configured_langs:
        _step("Update skipped: no secondary language configured (sourceUrl).")
        return {"success": False, "error": "No secondary language configured", "steps": log}

    headers = {
        "Content-Type": "application/json",
        "ms_cms_clientapp": "ProgrammingApp",
        "Authorization": f"Bearer {destination_token}",
    }
    refresh_token_cb = make_destination_token_refresh_callback(job_id)
    updated_count = 0
    paper_check_payloads: List[Dict] = []
    _step(f"Destination (all updates go here): {destination_url}")
    if dry_run:
        _step("Paper check mode: no data will be written to the database.")

    # Process one secondary language at a time; updates follow primary sequence (1st primary's secondary = 1st secondary data)
    for idx, (lang_key_iter, lang_cfg) in enumerate(configured_langs):
        if lang_key is not None and lang_key_iter != lang_key:
            continue
        sl_entry = secondary_lang_entries[idx] if idx < len(secondary_lang_entries) else secondary_lang_entries[0]
        lang_id = sl_entry.get("destinationLanguageId")
        lang_name = sl_entry.get("languageName") or sl_entry.get("languageCode") or str(lang_id)
        source_url = (lang_cfg.get("sourceUrl") or "").strip()
        _step(f"Processing secondary language: {lang_name} (id {lang_id}) from {lang_key_iter} | source: {source_url or '(none)'}")

        menu_path = os.path.join(job_folder, f"menu_api_response_input_secondary_{lang_key_iter}.json")
        menu_list = _load_json(menu_path)
        if not isinstance(menu_list, list) or not menu_list:
            _step(f"No menu data for {lang_key_iter}: {menu_path}, skipping.")
            continue
        _normalize_display_order_secondary_api(menu_list)
        try:
            with open(menu_path, "w", encoding="utf-8") as f:
                json.dump(menu_list, f, indent=4)
            _step(f"{lang_key_iter}: normalized order to 1,2,3,4 and saved to {os.path.basename(menu_path)}.")
        except Exception as e:
            logger.warning("Could not save normalized secondary JSON %s: %s", menu_path, e)

        data_sequence = _build_secondary_data_sequence(menu_list, field_mapper, template)
        if len(data_sequence) != len(primary_sequence):
            _step(f"Data length {len(data_sequence)} vs primary sequence {len(primary_sequence)}; aligning by min.")

        # Build secondary records in same tree order (L0, L1, L2...) for this language.
        # Used as fallback when PrimaryLanguageRecordId is 0/null so main parent (L0) records still get updated.
        secondary_sequence_for_lang = _build_secondary_records_sequence_for_language(records, component_ids, lang_id)

        # L0-by-ordinal fallback: when index-based match fails (e.g. different tree sizes), match 1st primary menu -> 1st secondary L0, 2nd -> 2nd, etc.
        primary_l0_ids_ordered = [pid for lev, pid in primary_sequence if lev == 0]
        secondary_l0_recs_ordered = [rec for lev, rec in secondary_sequence_for_lang if lev == 0]
        # L0 menu data by ordinal: so we can update each secondary L0 with the correct menu title (e.g. 2nd menu "Grand Sunday Brunch" -> "週日早午餐") even when flat sequence lengths differ
        level_0_template = (template.get("level 0") or {}).get("recordList") or [{}]
        level_0_template = level_0_template[0] if level_0_template else {}

        # #region agent log
        _agent_log("secondary_lang sequence lengths", {"primary_sequence_len": len(primary_sequence), "data_sequence_len": len(data_sequence), "secondary_seq_len": len(secondary_sequence_for_lang), "lang_id": lang_id}, "H5")
        # #endregion

        per_lang_count = 0
        api_failures = 0
        skipped_level_mismatch = 0
        skipped_no_secondary_rec = 0
        slots_over_data_length = max(0, len(primary_sequence) - len(data_sequence))
        for i, (level, primary_id) in enumerate(primary_sequence):
            # For L0 (menus), use menu data by ordinal so 2nd/3rd menus get correct secondary title even when primary vs secondary slot counts differ
            if level == 0:
                try:
                    l0_ordinal = primary_l0_ids_ordered.index(primary_id)
                except ValueError:
                    l0_ordinal = -1
                if 0 <= l0_ordinal < len(menu_list):
                    record_data_json = _api_data_to_record_json_string("level_0", menu_list[l0_ordinal], field_mapper, level_0_template)
                    data_level = 0
                else:
                    if i >= len(data_sequence):
                        break
                    data_level, record_data_json = data_sequence[i]
            else:
                if i >= len(data_sequence):
                    break
                data_level, record_data_json = data_sequence[i]
            if data_level != level:
                skipped_level_mismatch += 1
                if skipped_level_mismatch == 1:
                    _step(f"Level mismatch at index {i}: primary level={level} vs data level={data_level} (alignment may be wrong).")
                continue
            secondary_rec = secondary_by_primary_lang.get((primary_id, lang_id))
            used_position_fallback = False
            if not secondary_rec and i < len(secondary_sequence_for_lang) and secondary_sequence_for_lang[i][0] == level:
                secondary_rec = secondary_sequence_for_lang[i][1]
                used_position_fallback = True
                if level == 0:
                    logger.info("[Step 3] L0 (main parent) updated by position (PrimaryLanguageRecordId missing or 0)")
            # L0 ordinal fallback: if still no match (e.g. tree sizes differ), match 1st primary menu -> 1st secondary L0, 2nd -> 2nd, so 1072855 -> 1072856 gets Chinese
            if not secondary_rec and level == 0:
                try:
                    l0_ordinal = primary_l0_ids_ordered.index(primary_id)
                except ValueError:
                    l0_ordinal = -1
                if 0 <= l0_ordinal < len(secondary_l0_recs_ordered):
                    secondary_rec = secondary_l0_recs_ordered[l0_ordinal]
                    used_position_fallback = True
                    logger.info("[Step 3] L0 matched by ordinal: primary_id=%s -> secondary_id=%s (ordinal %s)", primary_id, secondary_rec.get("Id"), l0_ordinal)
            if not secondary_rec:
                skipped_no_secondary_rec += 1
                # #region agent log
                if level == 0:
                    _agent_log("L0 skipped no secondary rec", {"primary_id": primary_id, "lang_id": lang_id, "index_i": i}, "H1")
                # #endregion
                continue
            try:
                existing_dict = json.loads(secondary_rec.get("RecordJsonString") or "{}")
                updated_dict = json.loads(record_data_json)
                for k, v in existing_dict.items():
                    if k in ("Id", "ParentId", "LanguageCode", "PrimaryLanguageRecordId", "LanguageId", "UrlLanguageCode") and k not in updated_dict:
                        updated_dict[k] = v
                for k in list(updated_dict.keys()):
                    if updated_dict[k] is None:
                        updated_dict[k] = [] if k and "image" in k.lower() and "alt" not in k.lower() else ""
                record_data_json = json.dumps(updated_dict)
                display_order = safe_int(updated_dict.get("displayorder"), 0) or int(secondary_rec.get("DisplayOrder") or 0)
            except Exception:
                display_order = int(secondary_rec.get("DisplayOrder") or 0)
            if level == 0:
                try:
                    menu_title_sent = json.loads(record_data_json).get("menu-title") if record_data_json else None
                except Exception:
                    menu_title_sent = None
                # #region agent log
                _agent_log("L0 payload before API", {"primary_id": primary_id, "secondary_id": secondary_rec["Id"], "menu_title_sent": menu_title_sent, "used_position_fallback": used_position_fallback, "record_data_json_len": len(record_data_json)}, "H1")
                _agent_log("L0 data_sequence slot", {"index_i": i, "menu_title_in_payload": menu_title_sent}, "H2")
                # #endregion
                logger.info(
                    "[Step 3] L0 update: primary_id=%s secondary_id=%s menu-title=%s",
                    primary_id, secondary_rec["Id"], menu_title_sent
                )
                _step(f"L0 primary {primary_id} -> secondary {secondary_rec['Id']}: menu-title={menu_title_sent!r}")
            payload = {
                "componentId": int(secondary_rec["ComponentId"]),
                "recordId": int(secondary_rec["Id"]),
                "parentRecordId": int(secondary_rec.get("ParentId") or 0),
                "recordDataJson": record_data_json,
                "status": bool(secondary_rec.get("Status", True)),
                "tags": [],
                "displayOrder": display_order,
                "updatedBy": 0,
            }
            api_payload = {f"update_{secondary_rec['Id']}": [payload]}
            if dry_run:
                paper_check_payloads.append({
                    "recordId": secondary_rec["Id"],
                    "level": level,
                    "lang_key": lang_key_iter,
                    "payload_key": f"update_{secondary_rec['Id']}",
                    "payload": api_payload,
                })
                per_lang_count += 1
                updated_count += 1
            else:
                success, api_response = addUpdateRecordsToCMS(destination_url, headers, api_payload, batch_size=1, refresh_token_callback=refresh_token_cb)
                # #region agent log
                if level == 0:
                    _agent_log("L0 API result", {"secondary_id": secondary_rec["Id"], "success": success, "api_response_preview": str(api_response)[:200] if api_response is not None else None}, "H3")
                # #endregion
                if success:
                    per_lang_count += 1
                    updated_count += 1
                else:
                    api_failures += 1
                    logger.warning("[Step 3] API update failed for record id %s: %s", secondary_rec["Id"], api_response)
                    if level == 0:
                        _step(f"L0 update FAILED for secondary_id={secondary_rec['Id']}: {api_response}")
        if api_failures:
            logger.info("[Step 3] %s: api_failures=%s", lang_key_iter, api_failures)
        _step(f"Destination {destination_url} <- {lang_key_iter} ({lang_name}, source {source_url}): updated {per_lang_count} records.")
        if skipped_level_mismatch or skipped_no_secondary_rec or slots_over_data_length:
            _step(f"[{lang_key_iter}] Skipped: {skipped_level_mismatch} level-mismatch, {skipped_no_secondary_rec} no secondary record; {slots_over_data_length} primary slots had no data (primary {len(primary_sequence)} vs data {len(data_sequence)}).")

    if dry_run and paper_check_payloads:
        paper_check_path = os.path.join(job_folder, "secondary_update_paper_check.json")
        try:
            with open(paper_check_path, "w", encoding="utf-8") as f:
                json.dump({
                    "dry_run": True,
                    "total_would_update": len(paper_check_payloads),
                    "payloads_preview": [
                        {"recordId": p["recordId"], "level": p["level"], "lang_key": p["lang_key"], "payload_key": p["payload_key"]}
                        for p in paper_check_payloads
                    ],
                    "payloads": paper_check_payloads,
                }, f, indent=2, ensure_ascii=False)
            _step(f"Paper check complete: {len(paper_check_payloads)} records would be updated. No data written to DB. See {os.path.basename(paper_check_path)}. Run again without paper check to apply.")
        except Exception as e:
            _step(f"Paper check: could not write preview file: {e}")
        updated_count = 0
    elif dry_run:
        _step("Paper check complete: no secondary records would be updated (none matched).")

    _step(f"Step 3 done. Total secondary records updated: {updated_count}.")
    # Persist step log to job folder so user can inspect after DB run
    try:
        steps_log_path = os.path.join(job_folder, "secondary_update_steps_log.json")
        with open(steps_log_path, "w", encoding="utf-8") as f:
            json.dump({
                "job_id": job_id,
                "dry_run": dry_run,
                "updated_count": updated_count,
                "steps": log,
                "written_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            }, f, indent=2, ensure_ascii=False)
        if not dry_run:
            _step(f"Step log saved to {os.path.basename(steps_log_path)}.")
    except Exception as e:
        logger.warning("Could not write secondary_update_steps_log.json: %s", e)
    return {"success": True, "steps": log, "updated_count": updated_count, "dry_run": dry_run}
