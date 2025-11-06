import re
import json
import requests

# Base URL for the Figma API
FIGMA_API_BASE = "https://api.figma.com/v1"

def parse_figma_url(url):
    """Parses a Figma URL to extract the file key and an optional node ID."""
    file_key = None
    node_id = None

    # UPDATED Regex: Handle both '/file/' (legacy) and '/design/' (new) in the URL structure.
    # The file key is captured in group 2 after '/file/' or '/design/'.
    file_key_match = re.search(r'/(file|design)/([^/]+)/', url)
    if file_key_match:
        file_key = file_key_match.group(2)

    # Regex for node ID: ?node-id=ID
    node_id_match = re.search(r'node-id=([^&]+)', url)
    if node_id_match:
        # Replaces common URL escapes for ':'
        node_id_raw = node_id_match.group(1)
        # Note: '2-824' becomes '2:824', which is the format Figma API expects.
        node_id = node_id_raw.replace('%3A', ':').replace('-', ':')

    return file_key, node_id

def fetch_figma_data(token, file_key, node_id):
    """
    Fetches node details, image URL, and local variables from the Figma API.
    Handles multiple requests and error reporting.
    """
    
    # Standard headers including the Personal Access Token
    headers = {
        "X-Figma-Token": token
    }
    
    results = {
        'image_url': None,
        'node_details': 'No Node ID provided or failed to fetch.',
        'variables_json': 'Failed to fetch or no local variables found.',
        'error': None
    }

    # Helper for API calls to reduce redundancy and handle exceptions
    def api_call(url, error_context):
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            return response.json(), None
        except requests.exceptions.HTTPError as e:
            # Check for 403 Forbidden specifically on the variables endpoint
            if response.status_code == 403 and 'variables/local' in url:
                error_message = (
                    "Error fetching local variables: Forbidden (403). "
                    "This endpoint requires the 'file_variables:read' scope. "
                    "Please update your Personal Access Token permissions."
                )
            else:
                error_message = f"Error {error_context}: {e}"
                # If a non-403 error, still include the response text for debugging
                if response.text and response.status_code != 403: 
                    error_message += f"\nFull Response: {response.text}"
            return None, error_message
        except requests.exceptions.RequestException as e:
            error_message = f"Network or generic Error {error_context}: {e}"
            return None, error_message

    # 1. FETCH NODE DETAILS (Requires Node ID)
    if node_id:
        node_url = f"{FIGMA_API_BASE}/files/{file_key}/nodes?ids={node_id}"
        node_data, error = api_call(node_url, "fetching node details")
        
        if error:
            results['error'] = error
            results['node_details'] = 'Failed to fetch node details.'
        elif node_data:
            results['node_details'] = json.dumps(node_data, indent=2)

        # 2. FETCH IMAGE URL (Requires Node ID)
        image_url = f"{FIGMA_API_BASE}/images/{file_key}?ids={node_id}&format=png&scale=1"
        image_data, error = api_call(image_url, "fetching image URL")

        if error and not results['error']:
            results['error'] = error # Prioritize node error if already set
        
        if image_data and 'images' in image_data and node_id in image_data['images']:
            results['image_url'] = image_data['images'][node_id]
        elif node_id and not results['error']: # Only set this if fetching the image didn't cause a fatal error
             results['image_url'] = "Image URL not returned (node may be unrenderable or invisible)."


    # 3. FETCH LOCAL VARIABLES (Only requires File Key)
    variables_url = f"{FIGMA_API_BASE}/files/{file_key}/variables/local"
    variables_data, error = api_call(variables_url, "fetching local variables")
    
    # We always set the error here, but the custom message above will keep it clean
    if error and not results['error']:
        results['error'] = error
        results['variables_json'] = 'Failed to fetch local variables.'
    elif variables_data:
        if 'variables' in variables_data or 'variableCollections' in variables_data:
            results['variables_json'] = json.dumps(variables_data, indent=2)
        else:
            results['variables_json'] = 'No local variables found in this file.'

    return results