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

                                mainComp(save_folder,component_id,pageSectionGuid,base_url,headers)

                                level1Comp(save_folder,component_id,pageSectionGuid,base_url,headers)
                               


                                

                                
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




def mainComp(save_folder,component_id,pageSectionGuid,base_url,headers):
    #call the ComponentRecordsTree.json here and get the records with "recordType": "MainComponent" only and print its id
    # --- NEW LOGIC START ---
    records_file_path = os.path.join(save_folder, "ComponentRecordsTree.json")
    print(f"  [INFO] Searching for MainComponent records in {records_file_path}...")
    try:
        with open(records_file_path, 'r', encoding='utf-8') as rf:
            records_data = json.load(rf)

        records = records_data
        found_main_components = False
        
        if isinstance(records, list):
            for record in records:
                if isinstance(record, dict) and record.get("recordType") == "MainComponent":
                    main_component_id = record.get("id")
                    print(f"  [FOUND] MainComponent ID: {main_component_id}")
                    found_main_components = True
                    #this is for main

                    migrated_record_data = record.get("RecordJsonString")
                    
                    # Convert the content dictionary to a JSON string, as required by the API
                    recordDataJson_str = json.dumps(migrated_record_data)


                    payload = {
                        "componentId": component_id,
                        "recordId": 0,  # Using the source ID for upsert/migration
                        "parentRecordId": 0,
                        "recordDataJson": recordDataJson_str,
                        "status": record.get("status", True),
                        "tags": record.get("tags", []),
                        "displayOrder": record.get("displayOrder", 0),
                        "updatedBy": 0,
                        "pageSectionGuid": pageSectionGuid 
                    }

                    resp_success, resp_data = addUpdateRecordsToCMS(base_url, headers, payload)
                    
                    # Update logic based on API response
                    # Assuming resp_data is {str(old_id): new_id}
                    if resp_success and isinstance(resp_data, dict) and str(main_component_id) in resp_data:
                        # Extract the new ID
                        new_record_id = resp_data[str(main_component_id)] 
                        print(f"  [SUCCESS] CMS Record Updated. Old ID: {main_component_id} -> New ID: {new_record_id}")
                        
                        # Update the record object in the list for persistence
                        record["new_record_id"] = new_record_id 
                        record["isMigrated"] = True
                        record["sectionGuid"] = pageSectionGuid
                        
                        # Since there should only be one MainComponent, we can break
                        break 
                    else:
                        print(f"  [WARNING] Failed to update CMS record for MainComponent ID {main_component_id}. Response: {resp_data}")
                        
                    
        if not found_main_components:
            print("  [INFO] No MainComponent records found in the component tree file.")

    except FileNotFoundError:
        print(f"  [WARNING] ComponentRecordsTree.json not found at {records_file_path}. Skipping main component record processing.")
    except json.JSONDecodeError:
        print(f"  [ERROR] Failed to decode JSON from {records_file_path}. Skipping main component record processing.")
    except Exception as e:
        print(f"  [FATAL ERROR] Unexpected error while reading component records: {e}")
    # --- NEW LOGIC END ---




def level1Comp(save_folder,component_id,pageSectionGuid,base_url,headers):
    #call the ComponentRecordsTree.json here and get the records with "recordType": "MainComponent" only and print its id
    # --- NEW LOGIC START ---
    records_file_path = os.path.join(save_folder, "ComponentRecordsTree.json")
    print(f"  [INFO] Searching for MainComponent records in {records_file_path}...")
    try:
        with open(records_file_path, 'r', encoding='utf-8') as rf:
            records_data = json.load(rf)

        records = records_data
        found_main_components = False
        
        if isinstance(records, list):
            for record in records:
                if isinstance(record, dict) and record.get("recordType") == "Level1Child":
                    main_component_id = record.get("id")
                    print(f"  [FOUND] MainComponent ID: {main_component_id}")
                    found_main_components = True
                    #this is for main

                    migrated_record_data = record.get("RecordJsonString")
                    
                    # Convert the content dictionary to a JSON string, as required by the API
                    recordDataJson_str = json.dumps(migrated_record_data)


                    payload = {
                        "componentId": component_id,
                        "recordId": 0,  # Using the source ID for upsert/migration
                        "parentRecordId": 0,
                        "recordDataJson": recordDataJson_str,
                        "status": record.get("status", True),
                        "tags": record.get("tags", []),
                        "displayOrder": record.get("displayOrder", 0),
                        "updatedBy": 0,
                        "pageSectionGuid": pageSectionGuid 
                    }

                    resp_success, resp_data = addUpdateRecordsToCMS(base_url, headers, payload)
                    
                    # Update logic based on API response
                    # Assuming resp_data is {str(old_id): new_id}
                    if resp_success and isinstance(resp_data, dict) and str(main_component_id) in resp_data:
                        # Extract the new ID
                        new_record_id = resp_data[str(main_component_id)] 
                        print(f"  [SUCCESS] CMS Record Updated. Old ID: {main_component_id} -> New ID: {new_record_id}")
                        
                        # Update the record object in the list for persistence
                        record["new_record_id"] = new_record_id 
                        record["isMigrated"] = True
                        record["sectionGuid"] = pageSectionGuid
                        
                        # Since there should only be one MainComponent, we can break
                        break 
                    else:
                        print(f"  [WARNING] Failed to update CMS record for MainComponent ID {main_component_id}. Response: {resp_data}")
                        
                    
        if not found_main_components:
            print("  [INFO] No MainComponent records found in the component tree file.")

    except FileNotFoundError:
        print(f"  [WARNING] ComponentRecordsTree.json not found at {records_file_path}. Skipping main component record processing.")
    except json.JSONDecodeError:
        print(f"  [ERROR] Failed to decode JSON from {records_file_path}. Skipping main component record processing.")
    except Exception as e:
        print(f"  [FATAL ERROR] Unexpected error while reading component records: {e}")
    # --- NEW LOGIC END ---

        

if __name__ == "__main__":
    process_sitemap(FILE_NAME)