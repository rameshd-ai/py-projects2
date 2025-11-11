
import os
import json
from apis import generate_cms_token 
import requests



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
    and returns the 'alias' for a specific V-Component name.

    Endpoint: /api/VisualComponentsApi/GetSiteVComponents

    Args:
        base_url (str): The root URL for the API.
        headers (dict): HTTP headers, typically including Authorization and Content-Type.
        component_name (str): The exact 'name' of the V-Component to search for (e.g., "Stridecare-VCOMP").

    Returns:
        str: The V-Component alias (GUID/string) if an exact name match is found.
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
        # 1. Send the POST request using the 'data' parameter for the JSON string
        # Content-Type header must be set to "application/json" for this to work correctly
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
        
        # 4. Iterate through the results to find an exact name match and extract the alias
        for component in v_components:
            if component.get("name") == component_name:
                component_alias = component.get("alias")
                # print(f"✅ Found V-Component Alias for '{component_name}': {component_alias}")
                return component_alias

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


