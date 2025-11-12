import requests
import json
import logging
import time
from datetime import datetime


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