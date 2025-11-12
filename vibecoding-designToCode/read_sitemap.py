import json
import os
import uuid
import base64
from apis2 import login_token_generator,CreatePage,generateComponentSectionPayloadForPage,createPayloadJson,createRecordsPayload
from apis import addUpdateRecordsToCMS,export_mi_block_component
import time
import logging
import zipfile
# Define the filename to read
FILE_NAME = 'sitemap_page_names_components_only.json'


SETTINGS_FILE = "settings.json"

def load_settings():
    """Loads settings from the settings.json file."""
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as f:
                return json.load(f)
        except (IOError, json.JSONDecodeError) as e:
            print(f"Error loading settings file: {e}")
            return {}
    return {}


def generatecontentHtml(dataScope, vcompAlias, pageSectionGuid,section_position=0):
    if dataScope == 1:
        # print("independent")
        htmlContent = f"""
        <div class="VComponent" data-created_by="page-studio"
            data-scope="{dataScope}" data-section_guid="{pageSectionGuid}"
            data-section_position="{section_position}"
            data-vcomponent_alias="{vcompAlias}"
            data-version="3.0" isdeleted="false">
                <div class="inlineme" contenteditable="false">
                    %%vcomponent-{vcompAlias}[sectionguid:{pageSectionGuid}]%%
                </div>
        </div>
        """
       
    elif dataScope == 3:
        # print("profile level")
        htmlContent = f"""
        <div class="VComponent" data-created_by="page-studio"
            data-scope="{dataScope}" data-section_guid="{pageSectionGuid}"
            data-section_position="{section_position}"
            data-vcomponent_alias="{vcompAlias}"
            data-version="3.0" isdeleted="false">
            <div class="profile-content" contenteditable="false">
                %%vcomponent-{vcompAlias}%%
            </div>
        </div>
        """
 
    elif dataScope == 13:
        # print("Forms")
        htmlContent = f"""
        <div class="VComponent" data-created_by="page-studio"
            data-scope="{dataScope}" data-section_guid="{pageSectionGuid}"
            data-section_position="{section_position}"
            data-vcomponent_alias="{vcompAlias}"
            data-version="3.0" isdeleted="false">
            <div class="profile-content" contenteditable="false">
                %%vcomponent-{vcompAlias}%%
            </div>
        </div>
        """
 
    else:
        # print("site level")
        htmlContent = f"""
        <div class="VComponent" data-created_by="page-studio"
            data-scope="{dataScope}" data-section_guid="{pageSectionGuid}"
            data-section_position="{section_position}"
            data-vcomponent_alias="{vcompAlias}"
            data-version="3.0" isdeleted="false">
            <div class="site-content" contenteditable="false">
                %%vcomponent-{vcompAlias}%%
            </div>
        </div>
        """
    # Convert HTML content to Base64
    # htmlContent = base64.b64encode(htmlContent.encode('utf-8')).decode('utf-8')
 
    return htmlContent



def process_sitemap(filename):
    """
    Reads the sitemap JSON file, extracts the site title, 
    and iterates through the 'pages' list to process components for the 
    "Guest Rooms" page. It retrieves both the V-Component's alias and ID, 
    concatenates the generated HTML into a single string, and attempts to 
    create a new page via the CreatePage API.
    """
    # Create a temporary input.json if it doesn't exist for the mock to work
    if filename == 'input.json' and not os.path.exists(filename):
         # Creating a mock input.json for demonstration
        with open('input.json', 'w', encoding='utf-8') as f:
            mock_data = {
                "title": "Mock Hotel Site",
                "pages": [
                    {"page_name": "Home"},
                    {"page_name": "Guest Rooms", "components": ["RoomHero", "RoomGallery", "RoomDetails"]}
                ]
            }
            json.dump(mock_data, f, indent=4)


    if not os.path.exists(filename):
        print(f"Error: The input file '{filename}' was not found.")
        print("Please ensure 'input.json' is in the same directory as this script.")
        return

    try:
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if not isinstance(data, dict):
            print("Error: JSON file structure is invalid (expected a root object).")
            return

        site_title = data.get("title", "UNTITLED SITE")
        pages_list = data.get("pages", [])

        print(f"--- Processing Sitemap Data for Site: {site_title} ---")
        
        if not pages_list:
            print("No pages found in the sitemap.")
            return
        
        token = login_token_generator() 

        settings = load_settings()
        
        # Robustness check
        if not isinstance(settings, dict):
            print(f"❌ FATAL Error: 'settings' is not a dictionary ({type(settings)}). Aborting.")
            return 

        base_url = settings.get("destination_site_url")
        destination_site_id = settings.get("destination_site_id")
        destination_token = settings.get("destination_token", {}).get("token")
        
        headers = {
            'Content-Type': 'application/json',
            'ms_cms_clientapp': 'ProgrammingApp',
            'Authorization': f'Bearer {destination_token}',
        }
        
        # Define HTML wrappers
        htmlPrefix = '<div class="box2" id="data_page_content"><div id="pagestudio">'
        htmlPostfix = "</div></div>"

        # Loop through each page in the 'pages' array
        for page_entry in pages_list:
            page_name = page_entry.get("page_name", "UNKNOWN PAGE NAME")
            components = page_entry.get("components", [])
            
            # --- Target Page Check ---
            if page_name == "Guest Rooms": 
                
                generated_section_payloads = "" 
                final_html = "" # Initialize final_html outside the component loop
                
                if components:
                    print(f"\nProcessing components for: {page_name}")
                    for component in components:
                        try:
                            # 1. Get the component alias and ID (returns tuple on success, dict on error)
                            alias_result = generateComponentSectionPayloadForPage(base_url, headers, component)
                            # print(alias_result)

                            if isinstance(alias_result, tuple):
                                # Success: Unpack the alias (index 0) and ID (index 1)
                                component_alias, component_id = alias_result
                                print(f"  [INFO] Component ID: {component_id}")
                                print(f"  [INFO] Component component_alias: {component_alias}")
                                pageSectionGuid = str(uuid.uuid4()) 

                                response_content, content_disposition = export_mi_block_component(base_url,component_id,destination_site_id, headers)
                                miBlockId = component_id
                                mi_block_folder = f"mi-block-ID-{miBlockId}"
                                output_dir = os.path.join("output", str(destination_site_id)) 
                                save_folder = os.path.join(output_dir, mi_block_folder)
                                payload_file_path = os.path.join(output_dir, "api_response_final.json") 
                                os.makedirs(save_folder, exist_ok=True)
                                
                                try:
                                    # 1. Save and Unzip the exported file
                                    if response_content:
                                        filename = (
                                            content_disposition.split('filename=')[1].strip('"')
                                            if content_disposition and 'filename=' in content_disposition
                                            else f"site_{destination_site_id}.zip"
                                        )
                                        file_path = os.path.join(save_folder, filename)

                                        with open(file_path, "wb") as file:
                                            file.write(response_content)

                                        if zipfile.is_zipfile(file_path):
                                            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                                                zip_ref.extractall(save_folder)
                                            os.remove(file_path)
                                        else:
                                            print(f"  [WARNING] Exported file {filename} is not a zip file.")
                                    else:
                                        logging.info("Skipping file save/unzip as export_mi_block_component returned no content.")
                                    
                                    # Give OS a moment to finish file operations after unzipping/deleting the zip.
                                    time.sleep(2) 

                                    # 2. Convert .txt files to .json (if they exist)
                                    for extracted_file in os.listdir(save_folder):
                                        extracted_file_path = os.path.join(save_folder, extracted_file)
                                        if extracted_file.endswith('.txt'):
                                            new_file_path = os.path.splitext(extracted_file_path)[0] + '.json'
                                            try:
                                                # Read and process content inside the 'with' block
                                                with open(extracted_file_path, 'r', encoding="utf-8") as txt_file:
                                                    content = txt_file.read()
                                                    json_content = json.loads(content)
                                                
                                                # Write to new file inside its own 'with' block
                                                with open(new_file_path, 'w', encoding="utf-8") as json_file:
                                                    json.dump(json_content, json_file, indent=4)
                                                
                                                # Add a micro-sleep to help OS release the file handle before deletion
                                                time.sleep(0.05) 
                                                
                                                os.remove(extracted_file_path)
                                            except (json.JSONDecodeError, OSError) as e:
                                                # Log the error but continue to the next file
                                                logging.error(f"⚠️ Error processing file {extracted_file_path}: {e}")

                                    # --- POLLING LOGIC to wait for MiBlockComponentConfig.json to be accessible ---
                                    config_file_name = "MiBlockComponentConfig.json"
                                    config_file_path = os.path.join(save_folder, config_file_name)
                                    
                                    MAX_WAIT_SECONDS = 120 # 2 minutes max wait
                                    POLL_INTERVAL = 5      # Check every 5 seconds
                                    start_time = time.time()
                                    file_ready = False

                                    print(f"Waiting up to {MAX_WAIT_SECONDS} seconds for {config_file_name} to be available...")

                                    while time.time() - start_time < MAX_WAIT_SECONDS:
                                        if os.path.exists(config_file_path):
                                            # Try to open the file to check if it's locked
                                            try:
                                                with open(config_file_path, 'r') as f:
                                                    f.read(1) # Read a byte to confirm accessibility
                                                file_ready = True
                                                break
                                            except IOError:
                                                print(f"File {config_file_name} exists but is locked. Retrying in {POLL_INTERVAL}s...")
                                        else:
                                            print(f"File {config_file_name} not found yet. Retrying in {POLL_INTERVAL}s...")
                                        
                                        time.sleep(POLL_INTERVAL)

                                    if not file_ready:
                                        raise FileNotFoundError(f"🚨 Timeout: Required configuration file {config_file_name} was not generated or released within {MAX_WAIT_SECONDS} seconds.")
                                    # --- END POLLING LOGIC ---
                                
                                except FileNotFoundError as e:
                                    logging.error(f"❌ File Polling Failed: {e}")
                                    return None
                                

                                createPayloadJson(destination_site_id,component_id)
                                createRecordsPayload(destination_site_id,component_id)
                                # print("go inside main records=====================")
                                mainComp(save_folder,component_id,pageSectionGuid,base_url,headers)

                                # level1Comp(save_folder,component_id,pageSectionGuid,base_url,headers)
                               


                                

                                
                                # 2. Use the component_alias (string) for HTML generation
                                section_payload = generatecontentHtml(1, component_alias, pageSectionGuid)
                                
                                # 3. Only proceed if we have a successful section payload (expected to be a string)
                                if isinstance(section_payload, str):
                                    generated_section_payloads += section_payload
                                    print(f"  [SUCCESS] Retrieved and concatenated content for: {component} (ID: {component_id})")
                                else:
                                    print(f"  [FAILURE] Component '{component}' Error: generatecontentHtml returned non-string.")
                            
                            else:
                                # Failure: alias_result is an error dictionary
                                print(f"  [FAILURE] Component '{component}' Error: {alias_result.get('details')}")

                        except Exception as e:
                            print(f"  [FATAL ERROR] An exception occurred while processing '{component}': {e}")
                            
                # --- Final Assembly Logic ---
                
                print("\n--- Final Generated Payloads (Accumulated) ---")
                
                if generated_section_payloads:
                    # Add the prefix and postfix wrappers to the concatenated string
                    final_html = htmlPrefix + generated_section_payloads + htmlPostfix
                    
                    # Print the final assembled HTML (commented out for brevity)
                    # print(final_html)
                else:
                    print("No raw HTML content was successfully retrieved to assemble the final page.")
                    # If there's no content, we skip the page creation API call
                    return 

                # Prepare payload for page creation
                page_content_bytes = final_html.encode("utf-8")
                base64_encoded_content = base64.b64encode(page_content_bytes).decode("utf-8")
                page_name = page_name + "-Demo"
                payload = {
                    "pageId": 0,
                    "pageName": page_name,
                    "pageAlias": page_name.lower().replace(' ', '-'),
                    "pageContent": base64_encoded_content,
                    "isPageStudioPage": True,
                    "pageUpdatedBy": 0,
                    "isUniqueMetaContent": True,
                    "pageMetaTitle": page_name,
                    "pageMetaDescription": page_name,
                    "pageStopSEO": 1,
                    "pageCategoryId": 0,
                    "pageProfileId": 0,
                    "tags": ""
                    }
                print(f"New page payload ready for '{page_name}'.")

    except json.JSONDecodeError:
        print(f"❌ CRITICAL ERROR: Could not decode JSON from '{filename}'. Please ensure the file is valid JSON.")
    except Exception as e:
        print(f"❌ CRITICAL ERROR: An unexpected error occurred during sitemap processing: {e}")







def mainComp(save_folder, component_id, pageSectionGuid, base_url, headers):
    """
    Finds and migrates the 'MainComponent' record, updates its child records 
    in memory, and persists all changes back to the JSON file.
    """
    records_file_path = os.path.join(save_folder, "ComponentRecordsTree.json")
    print(f"  [INFO] Searching for MainComponent records in {records_file_path}...")
    
    main_component_old_id = None
    main_component_new_id = None
    records = []
    
    try:
        # --- File Reading ---
        with open(records_file_path, 'r', encoding='utf-8') as rf:
            records_data = json.load(rf)
        
        # Determine if the root is a list or a dictionary wrapper
        original_wrapper_is_dict = False
        if isinstance(records_data, dict) and "componentRecordsTree" in records_data:
            records = records_data["componentRecordsTree"]
            original_wrapper_is_dict = True
        elif isinstance(records_data, list):
            records = records_data
        
        if not isinstance(records, list):
            print("  [ERROR] Extracted component records content is not a list. Skipping.")
            return

        # --- PHASE 1: FIND AND MIGRATE MAIN COMPONENT ---
        found_main_components = False
        
        for record in records:
            if isinstance(record, dict) and record.get("recordType") == "MainComponent":
                
                main_component_old_id = record.get("ComponentId") 
                print(f"  [FOUND] MainComponent ID: {main_component_old_id}")
                found_main_components = True
                
                # --- API Payload Construction ---
                migrated_record_data = record.get("RecordJsonString")
                try:
                    recordDataJson_str = migrated_record_data if isinstance(migrated_record_data, str) else json.dumps(migrated_record_data)
                except TypeError:
                    print(f"  [ERROR] RecordJsonString for ID {main_component_old_id} is invalid for JSON serialization.")
                    continue

                tags_value = record.get("tags", [])
                if not isinstance(tags_value, list): tags_value = []

                single_record = {
                    "componentId": component_id, "recordId": 0, "parentRecordId": 0, 
                    "recordDataJson": recordDataJson_str, 
                    "status": record.get("Status", True), "tags": tags_value,
                    "displayOrder": record.get("DisplayOrder", 0), 
                    "updatedBy": record.get("UpdatedBy", 0),
                    "pageSectionGuid": pageSectionGuid 
                }

                api_payload = {"main_record_set": [single_record]}

                # Call the API to create the record
                # NOTE: The implementation above will return True, {0: 2981622}
                resp_success, resp_data = addUpdateRecordsToCMS(base_url, headers, api_payload)
                
                # --- Extract New Record ID ---
                main_component_new_id = None
                if resp_success and isinstance(resp_data, dict):
                    if 0 in resp_data: main_component_new_id = resp_data[0] # Checks for integer key 0
                    elif "0" in resp_data: main_component_new_id = resp_data["0"] # Checks for string key "0"

                if main_component_new_id:
                    print(f"  [SUCCESS] CMS Record Created. Old ComponentId: {main_component_old_id} -> New RecordId: {main_component_new_id}")
                    
                    # *** CRITICAL FIX: Update properties in the in-memory record ***
                    record["isMigrated"] = True
                    record["sectionGuid"] = pageSectionGuid
                    
                    break 
                else:
                    print(f"  [WARNING] Failed to update CMS record for MainComponent ID {main_component_old_id}. Response: {resp_data}")
                    
        if not found_main_components:
            print("  [INFO] No MainComponent records found in the component tree file.")
            return

        # --- PHASE 2: UPDATE CHILD RECORDS WITH NEW PARENT ID (In Memory) ---
        if main_component_new_id:
            updated_children_count = 0
            
            for record in records:
                # Check if the record is a child of the migrated MainComponent
                if isinstance(record, dict) and record.get("ParentComponentId") == main_component_old_id:
                    # *** CRITICAL FIX: Link the child record to the new parent ID ***
                    record["parent_new_record_id"] = main_component_new_id
                    updated_children_count += 1

            if updated_children_count > 0:
                print(f"  [INFO] Successfully linked {updated_children_count} child records to new parent ID {main_component_new_id} in memory.")
            else:
                print("  [INFO] No child records found for the migrated MainComponent.")
        else:
            print("  [WARNING] MainComponent migration failed, skipping child record updates.")

        # --- PHASE 3: WRITE UPDATES BACK TO FILE (Persistence Fix) ---
        with open(records_file_path, 'w', encoding='utf-8') as wf:
            if original_wrapper_is_dict:
                 # Write back into the original dictionary structure
                 records_data["componentRecordsTree"] = records
                 json.dump(records_data, wf, indent=4)
            else:
                 # Write back as a list
                 json.dump(records, wf, indent=4)
        print(f"  [SUCCESS] All migration metadata and child links persisted to {records_file_path}.")

    except FileNotFoundError:
        print(f"  [WARNING] ComponentRecordsTree.json not found at {records_file_path}. Skipping processing.")
    except json.JSONDecodeError:
        print(f"  [ERROR] Failed to decode JSON from {records_file_path}. Skipping processing.")
    except Exception as e:
        print(f"  [FATAL ERROR] Unexpected error while processing component records: {e}")
        

        





def level1Comp(save_folder, pageSectionGuid, base_url, headers):
    """
    Finds and migrates Level 1 components that have a new parent ID set 
    (from the MainComponent migration step) but are not yet migrated themselves.
    It then tags their children (Level 2) with the new Level 1 ID.
    """
    records_file_path = os.path.join(save_folder, "ComponentRecordsTree.json")
    print(f"\n[INFO] Starting Level 1 Component migration process for {records_file_path}...")
    
    records = []
    migrated_count = 0
    
    try:
        # --- File Reading ---
        with open(records_file_path, 'r', encoding='utf-8') as rf:
            records_data = json.load(rf)
        
        # Determine if the root is a list or a dictionary wrapper
        original_wrapper_is_dict = False
        if isinstance(records_data, dict) and "componentRecordsTree" in records_data:
            records = records_data["componentRecordsTree"]
            original_wrapper_is_dict = True
        elif isinstance(records_data, list):
            records = records_data
        
        if not isinstance(records, list):
            print("  [ERROR] Extracted component records content is not a list. Skipping.")
            return

        # --- PHASE 1: IDENTIFY, MIGRATE, AND TAG GRANDCHILDREN ---
        
        # We use a temporary list to store records ready for migration 
        # to avoid modifying the list while iterating over it.
        records_to_migrate = [
            r for r in records 
            if isinstance(r, dict) and 
               r.get("parent_new_record_id") is not None and 
               not r.get("isMigrated")
        ]
        
        if not records_to_migrate:
            print("  [INFO] No Level 1 components found ready for migration (missing 'parent_new_record_id' or already 'isMigrated').")
            return

        print(f"  [INFO] Found {len(records_to_migrate)} Level 1 component(s) to migrate.")
        
        for record in records_to_migrate:
            
            old_id = record.get("ComponentId") 
            new_parent_id = record.get("parent_new_record_id") # This is the new ID of the MainComponent
            
            print(f"  [START] Migrating Level 1 Component ID: {old_id} (Parent New ID: {new_parent_id})")
            
            # --- API Payload Construction ---
            migrated_record_data = record.get("RecordJsonString")
            try:
                recordDataJson_str = migrated_record_data if isinstance(migrated_record_data, str) else json.dumps(migrated_record_data)
            except TypeError:
                print(f"  [ERROR] RecordJsonString for ID {old_id} is invalid for JSON serialization. Skipping.")
                continue

            tags_value = record.get("tags", [])
            if not isinstance(tags_value, list): tags_value = []

            single_record = {
                # CRITICAL: Use the component ID from the record itself
                "componentId": record.get("ComponentId"), 
                "recordId": 0, 
                # CRITICAL: Set the ParentRecordId to the new MainComponent ID
                "parentRecordId": new_parent_id, 
                "recordDataJson": recordDataJson_str, 
                "status": record.get("Status", True), 
                "tags": tags_value,
                "displayOrder": record.get("DisplayOrder", 0), 
                "updatedBy": record.get("UpdatedBy", 0),
                "pageSectionGuid": pageSectionGuid 
            }

            api_payload = {"main_record_set": [single_record]}

            # Call the API to create the record
            resp_success, resp_data = addUpdateRecordsToCMS(base_url, headers, api_payload)
            
            # --- Extract New Record ID ---
            new_record_id = None
            if resp_success and isinstance(resp_data, dict):
                # We expect the new ID under key 0 from the API response
                if 0 in resp_data: new_record_id = resp_data[0] 
                elif "0" in resp_data: new_record_id = resp_data["0"]
            
            if new_record_id:
                migrated_count += 1
                print(f"  [SUCCESS] CMS Record Created. Old ComponentId: {old_id} -> New RecordId: {new_record_id}")
                
                # 1. Update the Level 1 record with its own new ID and mark as migrated
                # Note: We are updating the record object which is a reference to the list item
                record["isMigrated"] = True
                record["new_record_id"] = new_record_id
                record["sectionGuid"] = pageSectionGuid
                
                # 2. Tag Grandchildren (Level 2 components)
                updated_grandchildren_count = 0
                for grandchild in records:
                    # Check if the grandchild's old parent ID matches the current Level 1 old ID
                    if isinstance(grandchild, dict) and grandchild.get("ParentComponentId") == old_id:
                        # Link the grandchild to the new Level 1 component's ID
                        grandchild["parent_new_record_id"] = new_record_id
                        updated_grandchildren_count += 1
                
                if updated_grandchildren_count > 0:
                    print(f"  [TAGGED] Linked {updated_grandchildren_count} Level 2 record(s) to new Level 1 ID {new_record_id}.")
                
            else:
                print(f"  [WARNING] Failed to update CMS record for Level 1 Component ID {old_id}. Response: {resp_data}")

        # --- PHASE 2: WRITE UPDATES BACK TO FILE (Persistence) ---
        if migrated_count > 0:
            with open(records_file_path, 'w', encoding='utf-8') as wf:
                if original_wrapper_is_dict:
                    records_data["componentRecordsTree"] = records
                    json.dump(records_data, wf, indent=4)
                else:
                    json.dump(records, wf, indent=4)
            print(f"  [SUCCESS] Total {migrated_count} Level 1 record(s) migrated and all metadata persisted to {records_file_path}.")
        else:
             print("  [INFO] No records were migrated in this run. File not updated.")


    except FileNotFoundError:
        print(f"  [WARNING] ComponentRecordsTree.json not found at {records_file_path}. Skipping processing.")
    except json.JSONDecodeError:
        print(f"  [ERROR] Failed to decode JSON from {records_file_path}. Skipping processing.")
    except Exception as e:
        print(f"  [FATAL ERROR] Unexpected error while processing Level 1 component records: {e}")

        
if __name__ == "__main__":
    process_sitemap(FILE_NAME)