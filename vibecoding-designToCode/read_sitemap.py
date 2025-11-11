import json
import os
import uuid
import base64
from apis2 import login_token_generator,CreatePage,generateComponentSectionPayloadForPage
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
    "Guest Rooms" page, concatenating them into a single HTML string.
    """
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
        
        token = login_token_generator() # unused in this function but kept for context

        settings = load_settings()
        
        # Robustness check
        if not isinstance(settings, dict):
             print(f"❌ FATAL Error: 'settings' is not a dictionary ({type(settings)}). Aborting.")
             return 

        base_url = settings.get("destination_site_url")
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
            
            if page_name == "Guest Rooms": 
                
                # FIX: Initialize as an EMPTY STRING for concatenation
                generated_section_payloads = "" 
                
                if components:
                    print(f"\nProcessing components for: {page_name}")
                    for component in components:
                        try:
                            # 1. Get the raw HTML/Alias string for the component
                            alias_result = generateComponentSectionPayloadForPage(base_url, headers, component)
                            pageSectionGuid = str(uuid.uuid4()) 
                            section_payload = generatecontentHtml(1, alias_result, pageSectionGuid)
                            
                            # Only proceed if we have a successful result (a string containing HTML)
                            if isinstance(section_payload, str):
                                
                                # FIX: Concatenate the HTML string directly (alias_result IS the section_payload)
                                generated_section_payloads += section_payload
                                print(f"  [SUCCESS] Retrieved and concatenated content for: {component}")
                            else:
                                print(f"  [FAILURE] Component '{component}' Error: {alias_result.get('details')}")

                        except Exception as e:
                            print(f"  [FATAL ERROR] An exception occurred while processing '{component}': {e}")
                            
                # --- Final Assembly Logic ---
                
                print("\n--- Final Generated Payloads (Accumulated) ---")
                
                if generated_section_payloads:
                    # Add the prefix and postfix wrappers to the concatenated string
                    final_html = htmlPrefix + generated_section_payloads + htmlPostfix
                    
                    # Print the final assembled HTML
                    print(final_html)
                else:
                    print("No raw HTML content was successfully retrieved to assemble the final page.")

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
                # print("\n--- API Call Simulation ---")
                page_creation_result = CreatePage(base_url, headers, payload,418618)
                if page_creation_result and page_creation_result.get("success"):
                    print(f"Deployment successful! New page URL: {page_creation_result.get('page_url')}")
                else:
                    print("Deployment failed. Check API logs above.")


    except json.JSONDecodeError:
        print(f"❌ CRITICAL ERROR: Could not decode JSON from '{filename}'. Please ensure the file is valid JSON.")
    except Exception as e:
        print(f"❌ CRITICAL ERROR: An unexpected error occurred during sitemap processing: {e}")






        

if __name__ == "__main__":
    process_sitemap(FILE_NAME)