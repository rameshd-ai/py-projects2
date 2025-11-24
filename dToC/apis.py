import requests
import json
import time
from datetime import datetime
import logging
from typing import Dict, Any, List, Union
logger = logging.getLogger(__name__)
#API list:
#generate_cms_token(url, profile_alias)
#export_mi_block_component(base_url,componentId,siteId, headers)
#get_active_pages_from_api(base_url, site_id, headers)
"""
Example response from API:

[
    {
        "PageId": 323573,
        "PageName": "_PageStudioV2Page",
        "PageLocation": "-pagestudiov2page",
        "CategoryPath": "",
        "PageStatus": 1,
        "FullPath": "https://test-luxury-dining-template-2025.web5cms.milestoneinternet.info/-pagestudiov2page",
        "IsDraft": false,
        "UrlRedirectId": 0,
        "SiteId": 16277
    }
]
"""

#getComponentDetailsUsingVcompAlias(vcompalias, base_url, headers)


# Configure logging for this module
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def generate_cms_token(url, profile_alias):
    """
    Makes an API call to generate a CMS token using a static bearer token.
    
    Args:
        url (str): The base URL of the destination site.
        profile_alias (str): The profile alias required for token generation.
        
    Returns:
        dict: The JSON response data from the API, or None if the request fails.
    """
    token_url = f"{url}/api/authapi/GenerateCMSToken?profileAlias={profile_alias}"
    
    # This static bearer token is used to authenticate the token generation request
    static_bearer = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhdWQiOiJtaWxlc3RvbmUuY21zIiwiaXNzIjoibWlkZ2FyZCIsImV4cCI6MjE0NzQ4Mjc5OSwic3ViIjoiMjIyODIiLCJqdGkiOiJjYjA5M2U2Ni05NDAwLTQ1MzgtOWRhYy0wOGE3ODlhMTU1OGIiLCJrZXkiOiJ0cnVlIiwiYWdlbmN5SWQiOiIxIiwiYnVzaW5lc3NJZCI6IiIsInVzZXJUaGluZ0lkIjoiOTQ0OWE0ZjctMjQyZi1mMDExLThiM2QtMDAwZDNhM2Y4YWQ0IiwidXNlck5hbWUiOiJmcmV5amEuY21zZHh0ZWFtQG1pbGVzdG9uZWludGVybmV0LmNvbSIsImlhdCI6MTc0NzA1MjQyOCwibmJmIjoxNzQ3MDUyNDI4fQ.sqwq4WJ_aFGMgYsyro2lWXqy6z4kouelKKi5TwtxtEM"
    
    headers = {
        'Authorization': f'Bearer {static_bearer}',
        'Content-Type': 'application/json',
    }
    
    try:
        response = requests.post(token_url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"❌ API Request Failed: {e}")
        return None

def export_mi_block_component(base_url,componentId,siteId, headers):
    """
    Makes an API call to export a Mi-block component.

    Args:
        api_url (str): The full URL of the export API endpoint.
        payload (dict): The JSON payload for the API request.
        headers (dict): The headers for the API request.

    Returns:
        tuple: A tuple containing the response content (bytes),
               the Content-Disposition header, or (None, None) if the
               request fails.
    """
    try:
        api_url = f"{base_url}/ccadmin/cms/api/ComponentApi/ExportMiBlockComponent"
        payload = {
        "ComponentId": componentId,
        "SiteId": siteId,
        "IsExportComponentConfiguration": True,
        "IsExportComponentRecords": True,
        "IsExportComponentResources": True,
        "IsExportMiBlockFormat": True
    }
        
        response = requests.post(api_url, json=payload, headers=headers)
        response.raise_for_status()
        
        content_disposition = response.headers.get('Content-Disposition')
        return response.content, content_disposition

    except requests.exceptions.RequestException as e:
        logging.error(f"❌ API request failed: {e}")
    except Exception as e:
        logging.error(f"❌ Unexpected error during API call: {e}")
    
    time.sleep(1)
    return None, None

def get_active_pages_from_api(base_url, site_id, headers):
    """
    Fetches a set of active PageIds from the CMS API.

    Args:
        base_url (str): The base URL for the API.
        site_id (str): The ID of the target site.
        headers (dict): The authorization headers for the API request.

    Returns:
        set: A set of valid page IDs if successful, otherwise an empty set.
    """
    api_url = f"{base_url}/ccadmin/cms/api/PageApi/GetActivePages?siteId={site_id}"
    try:
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()
        active_pages = response.json()
        valid_page_ids = {str(page["PageId"]).strip() for page in active_pages}
        print(f"✅ Fetched {len(valid_page_ids)} active PageIds.")
        return valid_page_ids
    except requests.RequestException as e:
        print(f"❌ Failed to fetch active pages: {e}")
        return set()

def get_active_pages_from_api_all(base_url, site_id, headers):
    """
    Fetches a list of active Page records from the CMS API.

    Args:
        base_url (str): The base URL for the API.
        site_id (str): The ID of the target site.
        headers (dict): The authorization headers for the API request.

    Returns:
        list: A list of dictionaries (page records) if successful, otherwise an empty list.
    """
    api_url = f"{base_url}/ccadmin/cms/api/PageApi/GetActivePages?siteId={site_id}"
    try:
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()
        active_pages = response.json()
        print(f"✅ Fetched {len(active_pages)} active Page records.")
        return active_pages
    except requests.RequestException as e:
        print(f"❌ Failed to fetch active pages: {e}")
        return []

def getComponentDetailsUsingVcompAlias(vcompalias, base_url, headers):
    """
    Fetches VComponents from CMS API and returns the raw JSON response.

    Args:
        vcompalias (str): The alias of the VComponent (used for context, but not for filtering in this version).
        base_url (str): The base URL for the API.
        headers (dict): The authorization headers for the API request.

    Returns:
        dict or None: The JSON data from the API response if successful, else None.
    """
    api_url = f"{base_url}/ccadmin/cms/api/VisualComponentsApi/GetSiteVComponents"

    payload = {
        "PageNumber": 1,
        "PageSize": 100,  # set bigger page size so we fetch more at once
        "ShowInActiveRecords": True,
        "HidePageStudioDerivedMiBlocks": True,
        "ShowOnlyLibraryFormVComponents": True,
        "searchBy": "name",
        "searchByValue": "",
        "showOnlyContentLibraryVComponents": False,
        "categoryIds": [],
        "createdByIds": [],
        "vComponentIds": [],
        "contentScope": [1, 3, 5],
        "sortKey": "tv.createddate",
        "sortOrder": "desc"
    }

    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        logging.info("✅ Successfully fetched VComponents data from API.")
        return data

    except requests.RequestException as e:
        logging.error(f"❌ Failed to fetch VComponents: {e}")
        return None
    


def addUpdateRecordsToCMS(base_url, headers, payload):

    # print("Updated")
    # return True
    """
    Calls the CMS API to save/update miBlock records using the provided payload.

    Args:
        base_url (str): The base URL for the API.
        headers (dict): The authorization headers for the API request.
        payload (dict): The entire cleaned payload dictionary containing records to be saved.

    Returns:
        tuple: (bool, dict or str): A boolean indicating success or failure,
               and the JSON response data or an error message.
    """
    api_url = f"{base_url}/ccadmin/cms/api/PageApi/SaveMiblockRecord?isDraft=true"
    
    responses = {}
    try:
        for record_set_id, records in payload.items():
            for record in records:
                # print(api_url)
                # print(record)
                
                response = requests.post(api_url, headers=headers, json=record, timeout=30)
                response.raise_for_status()
                # print(response)
                # print("============================================================")
                result = response.json()
                record_id = record.get('recordId')
                if result.get("result"):
                    responses[record_id] = result.get('result')
                else:
                    return False, f"API response indicates failure for record: {record}"
        
        return True, responses

    except requests.RequestException as e:
        return False, f"Failed to update records via API: {e}"
    except Exception as e:
        return False, f"An unexpected error occurred in API call: {e}"
    



def publishPage(base_url, headers, site_id, page_id):
    """
    Publishes a specific page using the CMS Publish API.

    Args:
        base_url (str): The base URL of the CMS API.
        headers (dict): The authorization headers for the API request.
        site_id (str): The ID of the site where the page is located.
        page_id (str): The ID of the page to be published.

    Returns:
        tuple: (bool, str): A boolean indicating success or failure,
               and a message with the outcome of the API call.
    """
    try:
        publish_payload = [{"Id": str(page_id), "Type": "1"}]  # Type 1 = Page
        publish_url = f"{base_url}/api/PublishApi/Publish?siteId={site_id}&publishNotes=Published%20from%20Page%20Studio"
        
        logging.info(f"Attempting to publish PageId {page_id}...")
        
        publish_resp = requests.post(publish_url, json=publish_payload, headers=headers, timeout=30)
        publish_resp.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)

        if publish_resp.status_code // 100 == 2:
            message = f"✅ Successfully published PageId {page_id}."
            logging.info(message)
            return True, message
        else:
            message = f"❌ Failed to publish PageId {page_id}: {publish_resp.status_code} - {publish_resp.text}"
            logging.error(message)
            return False, message

    except requests.RequestException as e:
        message = f"❌ Failed to publish PageId {page_id} due to API request error: {e}"
        logging.error(message)
        return False, message
    except Exception as e:
        message = f"❌ An unexpected error occurred while trying to publish PageId {page_id}: {e}"
        logging.error(message)
        return False, message


def get_page_info_by_id(base_url, page_id, headers):
    """
    Fetches detailed page information from the CMS API for a given PageId.

    Args:
        base_url (str): The base URL for the API.
        page_id (str): The ID of the page to fetch.
        headers (dict): The authorization headers for the API request.

    Returns:
        dict: A dictionary containing the page's information if successful,
              otherwise an empty dictionary.
    """
    api_url = f"{base_url}/ccadmin/cms/api/PageApi/GetPageInfo?pageId={page_id}&isDraft=true"
    try:
        logging.info(f"Attempting to get page info for PageId: {page_id}")
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()
        page_info = response.json()
        logging.info(f"✅ Successfully fetched page info for PageId: {page_id}")
        return page_info
    except requests.RequestException as e:
        logging.error(f"❌ Failed to fetch page info for PageId {page_id}: {e}")
        return {}
    except Exception as e:
        logging.error(f"❌ An unexpected error occurred while fetching page info for {page_id}: {e}")
        return {}



def get_vcomponent_detail_by_aliases_api(base_url, aliases, headers):
    """
    Calls the GetVComponentDetailById API to fetch vComponent details
    by a list of aliases.

    Args:
        base_url (str): The base URL for the API.
        aliases (list): A list of vcomponent aliases to query.
        headers (dict): The request headers.

    Returns:
        dict: The full dictionary response from the API.
              Returns an empty dictionary in case of an error.
    """
    api_url = f"{base_url}/api/VisualComponentsApi/GetVComponentDetailById"
    payload = {"vComponentAliases": aliases}

    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()  # Raise an exception for bad status codes
        
        response_data = response.json()
        
        return response_data
    except requests.exceptions.RequestException as e:
        logging.error(f"❌ Failed to fetch vcomponent details from API: {e}")
        return {}
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        return {}
    


def psMappingApi(base_url, headers, payload):
    """
    Calls the PageContentEntityMappings API to update page miBlock mappings.

    Args:
        base_url (str): The base URL for the API.
        headers (dict): The request headers.
        payload (list): The JSON payload containing mapping data.
    """
    api_url = f"{base_url}/api/PageApi/UpdatePageMiBlockMappingsDraftV2"
    try:
        logging.info("Calling Mapping API...")
        response = requests.post(api_url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        logging.info(f"✅ Mapping API call successful. Status: {response.status_code}")
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"❌ Mapping API call failed: {e}")
        return {"status": "error", "message": str(e)}
        
def psPublishApi(base_url, headers, site_id, payload):
    """
    Calls the Publish API to publish pages and miBlocks.

    Args:
        base_url (str): The base URL for the API.
        headers (dict): The request headers.
        site_id (str): The ID of the site to publish.
        payload (list): The JSON payload containing publish data.
    """
    api_url = f"{base_url}/api/PublishApi/Publish_PSV2?siteId={site_id}&publishNotes=Published%2520from%2520Page%2520Studio"
    
    try:
        logging.info("Calling Publish API...")
        response = requests.post(api_url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        logging.info(f"✅ Publish API call successful. Status: {response.status_code}")
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"❌ Publish API call failed: {e}")
        return {"status": "error", "message": str(e)}
    


def get_page_info(base_url, page_id, headers):
    """
    Fetches page information from the CMS API for a given page ID.

    Args:
        base_url (str): The base URL for the API.
        page_id (str): The ID of the page to fetch.
        headers (dict): The authorization headers for the API request.

    Returns:
        dict: The JSON response containing page information if successful,
              otherwise an empty dictionary.
    """
    api_url = f"{base_url}/ccadmin/cms/api/PageApi/GetPageInfo?pageId={page_id}&isDraft=true"
    try:
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()
        logging.info(f"✅ Fetched page info for page ID: {page_id}")
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"❌ Failed to fetch page info: {e}")
        return {}
    




def save_page_metadata_api(base_url, headers, template_id, payload):
    """
    Saves the updated page metadata to the destination API.
    
    Args:
        base_url (str): The base URL of the destination API.
        headers (dict): The authorization headers.
        template_id (str): The template ID of the page.
        payload (dict): The JSON payload containing the updated metadata.
    """
    update_url = f"{base_url}/api/PageApi/SavePage?templateId={template_id}&directPublish=false"
    print(payload)

    try:
        resp = requests.post(update_url, headers=headers, json=payload)
        print(resp)
    
        resp.raise_for_status()
        logging.info(f"✅ Updated Meta Info for page ID: {payload.get('pageId')}")
    except requests.exceptions.RequestException as e:
        logging.error(f"❌ Failed to update Meta Info for page ID: {payload.get('pageId')}: {e}")
        logging.error(f"Response text: {resp.text if 'resp' in locals() else 'No response'}")



def menu_download_api(base_url):
    """
    Makes a GET request to the menu data API and returns the JSON response.

    Args:
        base_url (str): The base URL of the source CMS.

    Returns:
        dict or None: The parsed JSON data from the API response if successful,
                      otherwise None.
    """
    api_endpoint = "/api/MenuDataAPI/GetMenuData"
    full_url = f"{base_url.rstrip('/')}{api_endpoint}"

    print(f"Attempting to download menu data from: {full_url}")

    try:
        # Send a GET request to the full URL
        response = requests.post(full_url, timeout=10)
        
        # Raise an HTTPError for bad responses (4xx or 5xx)
        response.raise_for_status()
        
        # Parse the JSON data from the response body
        return response.json()

    except requests.exceptions.HTTPError as err_http:
        print(f"HTTP Error: {err_http}")
    except requests.exceptions.ConnectionError as err_conn:
        print(f"Connection Error: {err_conn}")
    except requests.exceptions.Timeout as err_timeout:
        print(f"Timeout Error: {err_timeout}")
    except requests.exceptions.RequestException as err:
        print(f"An unexpected error occurred: {err}")
    except json.JSONDecodeError as err_json:
        print(f"JSON Decode Error: Could not parse response as JSON. {err_json}")
    
    return None




      
def getComponentInfo(componentName, base_url,headers):
    """
    Fetches component information from the API.

    Args:
        componentName (str): The name of the component to get information for.
        base_url (str): The base URL of the API.

    Returns:
        dict: The JSON response from the API, or None if an error occurs.
    """
    print(f"Fetching component info for '{componentName}' from API...")
    api_url = f"{base_url}/ccadmin/cms/api/PageApi/GetMiBlocksInfo"

    payload = json.dumps([componentName])

    try:
        response = requests.post(api_url, headers=headers, data=payload)
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
        print("API call successful.")
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error during API call: {e}")
        return None
    


def CreateComponentRecord(base_url, headers, payload):
    """
    Sends a POST request to create a component record using the MiBlock API.

    Args:
        base_url (str): The root URL for the API (e.g., "https://example.com").
        headers (dict): HTTP headers, typically including Authorization and Content-Type.
        payload (dict): The data payload for the component record to be created.

    Returns:
        dict: The JSON response body from the API call, or an error dictionary.
    """
    # 1. Construct the final API endpoint URL
    api_url = f"{base_url}/api/MiblockApi/CreateComponentRecord"

    print(f"📡 Attempting POST to: {api_url}")
    
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
        print(f"❌ HTTP error occurred: {http_err} (Status Code: {response.status_code})")
        return {"error": "HTTP Error", "details": str(http_err), "status_code": response.status_code}
    except requests.exceptions.ConnectionError as conn_err:
        print(f"❌ Connection error occurred: {conn_err}")
        return {"error": "Connection Error", "details": str(conn_err)}
    except requests.exceptions.Timeout as timeout_err:
        print(f"❌ Timeout error occurred: {timeout_err}")
        return {"error": "Timeout Error", "details": str(timeout_err)}
    except requests.exceptions.RequestException as req_err:
        print(f"❌ An unexpected error occurred: {req_err}")
        return {"error": "Request Error", "details": str(req_err)}
    except json.JSONDecodeError:
        print(f"❌ Failed to decode JSON response. Response text: {response.text}")
        return {"error": "JSON Decode Error", "details": "Response was not valid JSON"}
    






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




def GetPageCategoryList(base_url, headers):
    """
    Sends a GET request to retrieve the list of page categories from the MiBlock API.
    Endpoint: /api/PageApi/GetPageCategoryList

    Args:
        base_url (str): The root URL for the API (e.g., "https://example.com").
        headers (dict): HTTP headers including Authorization token.

    Returns:
        dict or list: The JSON response from the API (expected to be a list of categories),
                      or an error dictionary.
    """

    # 1. Build the full API URL
    api_url = f"{base_url}/api/PageApi/GetPageCategoryList"

    print(f"\n📡 Attempting GET to: {api_url}")

    try:
        # 2. Send GET request
        response = requests.get(
            api_url, 
            headers=headers,
            timeout=10
        )

        # 3. Trigger exception for HTTP error codes (4xx, 5xx)
        response.raise_for_status()

        # 4. Return JSON body (expected to be a list of categories)
        return response.json()

    except requests.exceptions.HTTPError as http_err:
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
        print(f"❌ Request exception occurred: {req_err}")
        return {"error": "Request Error", "details": str(req_err)}

    except json.JSONDecodeError:
        print(f"❌ Failed to decode JSON. Response text: {response.text if 'response' in locals() else 'No response'}")
        return {"error": "JSON Decode Error", "details": "Invalid JSON response"}





def CustomGetComponentAliasByName(base_url, headers, component_name):
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


def GetAllVComponents(base_url: str, headers: Dict[str, str], page_size: int = 100) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Retrieves ALL V-Components from the CMS by iterating through paginated API results.

    Endpoint: /api/VisualComponentsApi/GetSiteVComponents

    Args:
        base_url (str): The root URL for the API.
        headers (dict): HTTP headers, typically including Authorization and Content-Type.
        page_size (int): The number of records to request per page (default is 50).

    Returns:
        list: A list of all V-Component dictionaries if successful.
        dict: An error dictionary if the API call fails at any point.
    """
    
    # --- 1. Base Payload Definition ---
    BASE_PAYLOAD = {
        "PageNumber": 1,
        "PageSize": page_size,
        "ShowInActiveRecords": True,
        "HidePageStudioDerivedMiBlocks": True,
        "ShowOnlyLibraryFormVComponents": True,
        "searchBy": "name",
        "searchByValue": "",
        "showOnlyContentLibraryVComponents": False,
        "categoryIds": [],
        "createdByIds": [],
        "vComponentIds": [],
        "contentScope": [1, 3, 5],
        "sortKey": "tv.createddate",
        "sortOrder": "desc"
    }
    
    api_url = f"{base_url}/api/VisualComponentsApi/GetSiteVComponents"
    all_components: List[Dict[str, Any]] = []
    current_page = 1
    total_records = float('inf')  # Start high to ensure the loop runs
    records_fetched = 0
    
    logger.info(f"Starting V-Component fetch with page size: {page_size}")

    while records_fetched < total_records:
        try:
            # --- 2. Update Payload for Current Page ---
            payload = BASE_PAYLOAD.copy()
            payload["PageNumber"] = current_page
            
            json_payload_string = json.dumps(payload)
            
            # --- 3. Send API Request ---
            response = requests.post(
                api_url, 
                headers=headers, 
                data=json_payload_string, 
                timeout=30 # Increased timeout for potentially long requests
            )
            response.raise_for_status() # Raises HTTPError for bad responses (4xx or 5xx)
            
            response_data = response.json()
            
            # --- 4. Process Response Data ---
            v_components = response_data.get("vComponents", [])
            total_records = response_data.get("TotalRecords", 0)
            
            if not v_components:
                logger.info(f"Page {current_page} returned no components. Fetch complete.")
                break # Exit loop if no components are returned

            # Add components from this page to the main list
            all_components.extend(v_components)
            records_fetched += len(v_components)
            
            logger.info(f"Fetched Page {current_page}. Records this page: {len(v_components)}. Total fetched: {records_fetched} / {total_records}.")
            
            # --- 5. Prepare for Next Iteration ---
            current_page += 1

            if records_fetched >= total_records:
                 logger.info("Total records retrieved. Fetch complete.")
                 break

        except requests.exceptions.RequestException as err:
            status_code = response.status_code if response is not None else 'N/A'
            logger.error(f"❌ API Request Error on Page {current_page}: {err} (Status Code: {status_code})")
            return {"error": "Request Error", "details": str(err), "status_code": status_code, "page": current_page}
            
        except json.JSONDecodeError:
            response_text = response.text if response is not None else 'No response object.'
            logger.error(f"❌ JSON Decode Error on Page {current_page}. Response text: {response_text[:100]}...")
            return {"error": "JSON Decode Error", "details": "Response was not valid JSON", "page": current_page}
        
    return all_components




    
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






def GetTemplatePageByName(base_url, headers, template_page_name):
    """
    Calls the GetTemplatePageList API, searches the 'TemplatePages' array in the response,
    and returns matching template page details based on the template page name.

    Endpoint:
        /api/PageApi/GetTemplatePageList?ms_cms_clientapp=ProgrammingApp

    Args:
        base_url (str): The base Site URL (e.g., https://example.com).
        headers (dict): HTTP headers, typically including Authorization and Content-Type.
        template_page_name (str): The 'PageName' or partial match of it (e.g. "Base Layout Page").

    Returns:
        list: A list of matching template page dictionaries.
        dict: Error dictionary if request fails or no matching pages found.
    """

    api_url = f"{base_url}/api/PageApi/GetTemplatePageList?ms_cms_clientapp=ProgrammingApp"
    response = None

    try:
        # print(f"\n📡 Attempting GET request to retrieve template pages from: {api_url}")

        # 1. Send GET request
        response = requests.get(api_url, headers=headers, timeout=10)
        response.raise_for_status()

        # 2. Parse response JSON
        response_data = response.json()

        # 3. Extract TemplatePages array
        template_pages = response_data.get("TemplatePages", [])

        if not template_pages:
            return {
                "error": "No Templates Returned",
                "details": "TemplatePages array was empty or missing in API response."
            }

        # 4. Perform case-insensitive partial match filter
        matched_pages = [
            page for page in template_pages
            if template_page_name.lower() in page.get("PageName", "").lower()
        ]

        if not matched_pages:
            return {
                "error": "Template Not Found",
                "details": f"No page name contains '{template_page_name}'."
            }

        # print(f"✅ Found {len(matched_pages)} match(es) for '{template_page_name}'.")
        return matched_pages

    except requests.exceptions.RequestException as err:
        status_code = response.status_code if response is not None else "N/A"
        print(f"❌ API Request Error in GetTemplatePageByName: {err} (Status Code: {status_code})")
        return {"error": "Request Error", "details": str(err), "status_code": status_code}

    except json.JSONDecodeError:
        response_text = response.text if response is not None else "No response object"
        print(f"❌ JSON Decode Error in GetTemplatePageByName. Response body: {response_text}")
        return {"error": "JSON Decode Error", "details": "Invalid JSON response received from API"}
