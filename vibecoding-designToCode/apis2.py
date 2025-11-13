
import os
import json
from apis import generate_cms_token 
import requests
from typing import List, Dict, Any, Optional

def _read_json_file(file_path: str) -> Optional[Dict[str, Any]]:
    """Helper function to safely read and parse a JSON file."""
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: Required file not found at {file_path}.")
        return None
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {file_path}. Check the file format.")
        return None
    except Exception as e:
        print(f"An unexpected error occurred while reading {file_path}: {e}")
        return None


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



def login_token_generator():
    """
    Loads site details from settings.json, generates CMS tokens,
    and saves the tokens back to the settings.json file.
    """
    print("Generating login token...")
    settings = load_settings()
    if not settings:
        print("Could not load settings. Aborting token generation.")
        return False

    destination_url = settings.get("destination_site_url")
    destination_profile_alias = settings.get("destination_profile_alias")
    if not all([destination_url, destination_profile_alias]):
        print("Error: Incomplete site configuration in settings.json.")
        return False
    token_data_destination = generate_cms_token(destination_url, destination_profile_alias)
    settings["destination_token"] = token_data_destination
    try:
        with open(SETTINGS_FILE, "w") as f:
            json.dump(settings, f, indent=4)
        print("Tokens successfully saved to settings.json.")
        return True
    except IOError as e:
        print(f"Error saving settings file: {e}")
        return False
    


def CreatePage(base_url, headers, payload,template_id):
    """
    Sends a POST request to create (save) a page using the MiBlock API.
    Endpoint: /api/PageApi/SavePage?templateId={id}&directPublish={bool}

    Args:
        base_url (str): The root URL for the API (e.g., "https://example.com").
        headers (dict): HTTP headers, typically including Authorization and Content-Type.
        payload (dict): The data payload for the page record to be created/saved.
        template_id (int): The ID of the template to use for the new page.
        direct_publish (bool): Whether to publish the page immediately after saving.

    Returns:
        dict: The JSON response body from the API call, or an error dictionary.
    """
    # Convert bool to lowercase string for URL parameter, as is common in Web APIs
    direct_publish = True
    direct_publish_str = str(direct_publish).lower()
    
    # 1. Construct the final API endpoint URL with query parameters
    api_url = f"{base_url}/api/PageApi/SavePage?templateId={template_id}&directPublish={direct_publish_str}"

    print(f"\n📡 Attempting POST to: {api_url}")
    
    try:
        # 2. Send the POST request with the JSON payload
        response = requests.post(
            api_url,
            headers=headers,
            json=payload,  # 'json=payload' automatically sets Content-Type to application/json
            timeout=10     # Set a timeout for the request
        )
        
        # 3. Raise an exception for bad status codes (4xx or 5xx)
        response.raise_for_status()

        # 4. Return the successful JSON response content
        return response.json()

    except requests.exceptions.HTTPError as http_err:
        # Check if response object exists and has status code
        status_code = response.status_code if 'response' in locals() else 'N/A'
        print(f"❌ HTTP error occurred: {http_err} (Status Code: {status_code})")
        return {"error": "HTTP Error", "details": str(http_err), "status_code": status_code}
    except requests.exceptions.ConnectionError as conn_err:
        print(f"❌ Connection error occurred: {conn_err}")
        return {"error": "Connection Error", "details": str(conn_err)}
    except requests.exceptions.Timeout as timeout_err:
        print(f"❌ Timeout error occurred: {timeout_err}")
        return {"error": "Timeout Error", "details": str(timeout_err)}
    except requests.exceptions.RequestException as req_err:
        print(f"❌ An unexpected request error occurred: {req_err}")
        return {"error": "Request Error", "details": str(req_err)}
    except json.JSONDecodeError:
        print(f"❌ Failed to decode JSON response. Response text: {response.text if 'response' in locals() else 'No response object.'}")
        return {"error": "JSON Decode Error", "details": "Response was not valid JSON"}



# Default payload structure for the GetSiteVComponents API
DEFAULT_VCOMPONENT_LIST_PAYLOAD = {
    "PageNumber": 1,
    "PageSize": 50, # Increased page size for a better chance of finding the item
    "ShowInActiveRecords": True,
    "HidePageStudioDerivedMiBlocks": True,
    "ShowOnlyLibraryFormVComponents": True,
    "searchBy": "name",
    "searchByValue": "",  # Placeholder for the component name
    "showOnlyContentLibraryVComponents": False,
    "categoryIds": [],
    "createdByIds": [],
    "vComponentIds": [],
    "contentScope": [1, 3, 5],
    "sortKey": "tv.createddate",
    "sortOrder": "desc"
}






def GetComponentAliasByName(base_url, headers, component_name):
    """
    Calls the GetSiteVComponents API, searches the 'vComponents' array in the response, 
    and returns the 'alias' and 'componentId' for a specific V-Component name.

    Endpoint: /api/VisualComponentsApi/GetSiteVComponents

    Args:
        base_url (str): The root URL for the API.
        headers (dict): HTTP headers, typically including Authorization and Content-Type.
        component_name (str): The exact 'name' of the V-Component to search for (e.g., "Stridecare-VCOMP").

    Returns:
        tuple: A tuple (alias: str, componentId: int) if an exact name match is found.
        dict: An error dictionary if the API call fails or the component is not found.
    """
    # Create a mutable copy of the default payload and set the search value
    payload = DEFAULT_VCOMPONENT_LIST_PAYLOAD.copy() 
    payload["searchByValue"] = component_name
    
    # Explicitly serialize the Python dictionary into a JSON string
    json_payload_string = json.dumps(payload)
    
    api_url = f"{base_url}/api/VisualComponentsApi/GetSiteVComponents"

    # print(f"\n📡 Attempting POST to: {api_url} to find V-Component '{component_name}'")
    
    response = None 
    
    try:
        # 1. Send the POST request
        response = requests.post(
            api_url, 
            headers=headers, 
            data=json_payload_string, 
            timeout=10
        )
        response.raise_for_status()
        
        # 2. Get the response data
        response_data = response.json()
        
        # 3. Check the 'vComponents' array in the response
        v_components = response_data.get("vComponents", [])

        if not v_components:
            print(f"⚠️ V-Component '{component_name}' not found. 'vComponents' array was empty or search failed.")
            return {"error": "Component Not Found", "details": f"No component matching '{component_name}' was returned by the API."}
        
        # 4. Iterate through the results to find an exact name match and extract the alias and ID
        for component in v_components:
            if component.get("name") == component_name:
                component_alias = component.get("alias")
                vComponentId = component.get("vComponentId")
                
                # --- START OF CORRECTION ---
                # The componentId is nested inside the 'component' key.
                nested_component_details = component.get("component", {}) 
                component_id = nested_component_details.get("componentId")
                # --- END OF CORRECTION ---
                
                # print(f"✅ Found V-Component Alias and ID for '{component_name}': ({component_alias}, {component_id})")
                return (vComponentId,component_alias, component_id) # <-- Return both values as a tuple

        # 5. Fallback if search returned data, but no exact name match was found
        # print(f"⚠️ Search returned data, but no exact match found for '{component_name}' in the 'vComponents' list.")
        return {"error": "Component Not Found", "details": f"No exact component name match for '{component_name}' in returned list."}

    except requests.exceptions.RequestException as err:
        status_code = response.status_code if response is not None else 'N/A'
        print(f"❌ API Error in GetComponentAliasByName: {err} (Status Code: {status_code})")
        return {"error": "Request Error", "details": str(err), "status_code": status_code}
    except json.JSONDecodeError:
        response_text = response.text if response is not None else 'No response object.'
        print(f"❌ JSON Decode Error. Response text: {response_text}")
        return {"error": "JSON Decode Error", "details": "Response was not valid JSON"}
    

    


def generateComponentSectionPayloadForPage(base_url, headers, component):
    """
    Wrapper for GetComponentIdByName, finding the componentId based on its name.
    """
    return GetComponentAliasByName(base_url, headers, component)





def createPayloadJson(destination_site_id, component_id):
    """
    Reads the MiBlockComponentConfig.json for a given component_id,
    determines the component hierarchy based on ParentId, and creates 
    a new JSON file with component ID, type (level), and name in the
    'output/{destination_site_id}/mi-block-ID-{component_id}' folder.

    Args:
        destination_site_id (int/str): The ID of the site, used as part of the folder path.
        component_id (int/str): The ID of the component (used to construct the folder path).
        
    Returns:
        bool: True if the operation was successful, False otherwise.
    """
    component_id_str = str(component_id)
    site_id_str = str(destination_site_id)
    
    # Construct the folder path: output/site_id/mi-block-ID-component_id
    folder_path = os.path.join("output", site_id_str, f"mi-block-ID-{component_id_str}")
    
    input_file_path = os.path.join(folder_path, "MiBlockComponentConfig.json")
    output_file_name = "ComponentHierarchy.json"
    output_file_path = os.path.join(folder_path, output_file_name)

    try:
        # 1. Read and parse MiBlockComponentConfig.json
        print(f"Reading configuration from: {input_file_path}")
        with open(input_file_path, 'r') as f:
            config_data = json.load(f)

        components = config_data.get("component", [])
        
        if not components:
            print("Warning: 'component' list is empty in the config file. Writing empty hierarchy file.")
            
            # Ensure the output directory exists even if we write an empty list
            os.makedirs(folder_path, exist_ok=True)
            with open(output_file_path, 'w') as f:
                json.dump([], f, indent=4)
            return True

        # 2. Map Component IDs to their properties and initialize levels
        component_map = {}
        for comp in components:
            comp_id = comp.get("ComponentId")
            parent_id = comp.get("ParentId")
            
            if comp_id is not None:
                component_map[comp_id] = {
                    "ComponentName": comp.get("ComponentName"),
                    "ParentId": parent_id,
                    "Level": -1 # Unknown initially
                }

        # 3. Determine the hierarchy (level)
        
        # First pass: Set Level 0 (Root) components (ParentId is None/null)
        for details in component_map.values():
            if details["ParentId"] is None:
                details["Level"] = 0
        
        # Iterative pass: Resolve child levels (Level 1, 2, ...)
        max_depth = len(components)
        level = 0
        
        while level < max_depth:
            changes_made = False
            next_level = level + 1
            
            for details in component_map.values():
                if details["Level"] == -1: # Only look at unclassified components
                    parent_id = details["ParentId"]
                    
                    # Check if the parent exists AND has the current level
                    if parent_id in component_map and component_map[parent_id]["Level"] == level:
                        details["Level"] = next_level
                        changes_made = True
            
            if not changes_made:
                break # Hierarchy is fully resolved
            
            level += 1
            
        # 4. Construct the final output payload
        output_payload = []
        for comp_id, details in component_map.items():
            comp_level = details["Level"]
            
            # Define the component type based on its calculated level
            if comp_level == 0:
                component_type = "MainComponent"
            elif comp_level > 0:
                component_type = f"Level{comp_level}Child"
            else:
                component_type = "Unlinked/Error"

            output_payload.append({
                "componentId": comp_id,
                "type": component_type,
                "componentName": details["ComponentName"]
            })

        # 5. Write the output payload to a new JSON file
        print(f"Writing component hierarchy to: {output_file_path}")
        
        # Ensure the output directory exists
        os.makedirs(folder_path, exist_ok=True)
        
        with open(output_file_path, 'w') as f:
            json.dump(output_payload, f, indent=4)
        
        print("Successfully determined component hierarchy and saved.")
        return True

    except FileNotFoundError:
        print(f"Error: Input file not found at {input_file_path}. Ensure the site and component IDs are correct.")
        return False
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {input_file_path}. Check the file format.")
        return False
    except Exception as e:
        print(f"An unexpected error occurred during processing: {e}")
        return False
    


def createRecordsPayload(destination_site_id, component_id):
    """
    Finds the root record for the given component_id, recursively collects
    all descendant records, and adds the 'recordType' based on ComponentHierarchy.json.
    """
    component_id_int = int(component_id)
    site_id_str = str(destination_site_id)
    
    # 1. Define Paths
    folder_path = os.path.join("output", site_id_str, f"mi-block-ID-{str(component_id)}")
    
    # Input files
    records_input_path = os.path.join(folder_path, "MiBlockComponentRecords.json")
    hierarchy_input_path = os.path.join(folder_path, "ComponentHierarchy.json") # New path
    
    # Output file
    output_file_name = "ComponentRecordsTree.json"
    output_file_path = os.path.join(folder_path, output_file_name)

    # 2. Load Data and Create Type Map
    records_data = _read_json_file(records_input_path)
    hierarchy_data = _read_json_file(hierarchy_input_path)

    if records_data is None or hierarchy_data is None:
        return False
        
    if not isinstance(hierarchy_data, list):
        print("Error: ComponentHierarchy.json is required and must contain a list of components.")
        return False

    # Create map: { componentId (int): type (str) }
    type_map = {int(item["componentId"]): item["type"] for item in hierarchy_data}

    all_records: List[Dict[str, Any]] = records_data.get("componentRecords", [])
    
    if not all_records:
        print("Warning: 'componentRecords' list is empty. Writing empty records tree file.")
        os.makedirs(folder_path, exist_ok=True)
        with open(output_file_path, 'w') as f:
            json.dump({"componentRecordsTree": []}, f, indent=4)
        return True

    # Helper to add recordType
    def enrich_record(record: Dict[str, Any], type_map: Dict[int, str]) -> Dict[str, Any]:
        comp_id = record.get("ComponentId")
        # Get type from map, default to "UnknownType" if not found
        record_type = type_map.get(comp_id, "UnknownType") 
        
        # Create a copy and add the new key
        enriched_record = record.copy() 
        enriched_record["recordType"] = record_type
        return enriched_record
    
    # 3. Find the single Root Record
    root_record = next(
        (
            record for record in all_records
            if record.get("ComponentId") == component_id_int and record.get("ParentId") == 0
        ),
        None
    )

    if root_record is None:
        print(f"Error: Could not find a root record (ComponentId={component_id_int}, ParentId=0).")
        return False

    # 4. Prepare data structure for quick lookup (Record ID -> List of Children)
    children_map: Dict[int, List[Dict[str, Any]]] = {}
    for record in all_records:
        parent_id = record.get("ParentId")
        if parent_id is not None and parent_id != 0:
            if parent_id not in children_map:
                children_map[parent_id] = []
            children_map[parent_id].append(record)

    # 5. Recursive function to collect the entire tree in sequence (Depth-First Search)
    # Start with the enriched root record
    records_tree: List[Dict[str, Any]] = [enrich_record(root_record, type_map)]
    
    def collect_descendants(parent_id: int):
        """Recursively finds and appends children in a depth-first manner."""
        children = children_map.get(parent_id, [])
        
        # Sort children by DisplayOrder or Id to maintain sequence
        children.sort(key=lambda x: x.get("DisplayOrder", x.get("Id")))
        
        for child in children:
            # Enrich the child record before adding it to the final tree
            records_tree.append(enrich_record(child, type_map)) 
            # Recurse for deeper levels
            collect_descendants(child["Id"])

    # Start the collection from the root record's Id
    collect_descendants(root_record["Id"])

    # 6. Write the output payload
    print(f"Found {len(records_tree)} records in the hierarchy. Writing to: {output_file_path}")
    
    os.makedirs(folder_path, exist_ok=True)
    with open(output_file_path, 'w') as f:
        # Save the list of records in sequence under the key 'componentRecordsTree'
        json.dump({"componentRecordsTree": records_tree}, f, indent=4)
    
    print("Successfully collected and saved component records tree with recordType.")
    return True