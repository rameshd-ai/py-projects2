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
        logging.error(f"[ERROR] API Request Failed: {e}")
        return None

def export_mi_block_component(base_url,componentId,siteId, headers):
    time.sleep(2)
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
        logging.error(f"[ERROR] API request failed: {e}")
    except Exception as e:
        logging.error(f"[ERROR] Unexpected error during API call: {e}")
    
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
        print(f"[SUCCESS] Fetched {len(valid_page_ids)} active PageIds.")
        return valid_page_ids
    except requests.RequestException as e:
        print(f"[ERROR] Failed to fetch active pages: {e}")
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
        print(f"[SUCCESS] Fetched {len(active_pages)} active Page records.")
        return active_pages
    except requests.RequestException as e:
        print(f"[ERROR] Failed to fetch active pages: {e}")
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
        logging.info("[SUCCESS] Successfully fetched VComponents data from API.")
        return data

    except requests.RequestException as e:
        logging.error(f"[ERROR] Failed to fetch VComponents: {e}")
        return None
    


def addUpdateRecordsToCMS(base_url, headers, payload):
    # Reduced sleep time since we're using bulk processing for most cases
    time.sleep(0.5)
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
    api_url = f"{base_url}/ccadmin/cms/api/PageApi/SaveMiblockRecord?isDraft=false"
    
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
        time.sleep(2)
        return True, responses

    except requests.RequestException as e:
        return False, f"Failed to update records via API: {e}"
    except Exception as e:
        return False, f"An unexpected error occurred in API call: {e}"


def addUpdateRecordsToCMS_bulk(base_url, headers, records_list):
    """
    Bulk version: Sends multiple records to the CMS API in parallel using threading.
    This significantly reduces API call time when processing many records.

    Args:
        base_url (str): The base URL for the API.
        headers (dict): The authorization headers for the API request.
        records_list (list): List of record dictionaries to be saved.

    Returns:
        tuple: (bool, dict or str): A boolean indicating success or failure,
               and a dictionary mapping record_id -> new_record_id, or an error message.
    """
    import concurrent.futures
    import threading
    
    api_url = f"{base_url}/ccadmin/cms/api/PageApi/SaveMiblockRecord?isDraft=false"
    responses = {}
    errors = []
    lock = threading.Lock()
    
    def process_record(record, index):
        """Process a single record and store the response."""
        try:
            original_record_id = record.get('recordId', 0)  # Original recordId from payload
            response = requests.post(api_url, headers=headers, json=record, timeout=30)
            response.raise_for_status()
            result = response.json()
            
            if result.get("result"):
                new_record_id = result.get('result')
                with lock:
                    # Map by original recordId (for compatibility) and by index (for bulk processing)
                    responses[original_record_id] = new_record_id
                    responses[index] = new_record_id  # Also map by index for easy lookup
                return True, original_record_id, new_record_id
            else:
                with lock:
                    errors.append(f"API response indicates failure for record {original_record_id}: {result}")
                return False, original_record_id, None
        except Exception as e:
            with lock:
                errors.append(f"Error processing record {record.get('recordId', index)}: {e}")
            return False, record.get('recordId', index), None
    
    try:
        # Use ThreadPoolExecutor to process records in parallel
        # Limit to 10 concurrent requests to avoid overwhelming the API
        max_workers = min(10, len(records_list))
        
        logging.info(f"[BULK API] Processing {len(records_list)} records with {max_workers} parallel workers...")
        start_time = time.time()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(process_record, record, idx) for idx, record in enumerate(records_list)]
            
            # Wait for all futures to complete
            for future in concurrent.futures.as_completed(futures):
                success, record_id, new_id = future.result()
                if not success:
                    logging.warning(f"[BULK API] Failed to process record {record_id}")
        
        elapsed_time = time.time() - start_time
        logging.info(f"[BULK API] Completed {len(records_list)} records in {elapsed_time:.2f} seconds (avg {elapsed_time/len(records_list):.2f}s per record)")
        
        if errors:
            logging.warning(f"[BULK API] {len(errors)} errors occurred during bulk processing")
            for error in errors[:5]:  # Log first 5 errors
                logging.warning(f"  - {error}")
        
        if len(responses) == len(records_list):
            time.sleep(1)  # Small delay after bulk operations
            return True, responses
        elif len(responses) > 0:
            logging.warning(f"[BULK API] Partial success: {len(responses)}/{len(records_list)} records processed")
            return True, responses  # Return partial success
        else:
            return False, f"All records failed. Errors: {errors[:3]}"
            
    except Exception as e:
        return False, f"An unexpected error occurred in bulk API call: {e}"
    



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
            message = f"[SUCCESS] Successfully published PageId {page_id}."
            logging.info(message)
            return True, message
        else:
            message = f"[ERROR] Failed to publish PageId {page_id}: {publish_resp.status_code} - {publish_resp.text}"
            logging.error(message)
            return False, message

    except requests.RequestException as e:
        message = f"[ERROR] Failed to publish PageId {page_id} due to API request error: {e}"
        logging.error(message)
        return False, message
    except Exception as e:
        message = f"[ERROR] An unexpected error occurred while trying to publish PageId {page_id}: {e}"
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
        logging.info(f"[SUCCESS] Successfully fetched page info for PageId: {page_id}")
        return page_info
    except requests.RequestException as e:
        logging.error(f"[ERROR] Failed to fetch page info for PageId {page_id}: {e}")
        return {}
    except Exception as e:
        logging.error(f"[ERROR] An unexpected error occurred while fetching page info for {page_id}: {e}")
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
        logging.error(f"[ERROR] Failed to fetch vcomponent details from API: {e}")
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
        logging.info(f"[SUCCESS] Mapping API call successful. Status: {response.status_code}")
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"[ERROR] Mapping API call failed: {e}")
        return {"status": "error", "message": str(e)}
        
def psPublishApi(base_url, headers, site_id, payload):
    """
    Calls the Publish API to publish pages and miBlocks.
    Includes delay to prevent API blocking/rate limiting.

    Args:
        base_url (str): The base URL for the API.
        headers (dict): The request headers.
        site_id (str): The ID of the site to publish.
        payload (list): The JSON payload containing publish data.
    """
    api_url = f"{base_url}/api/PublishApi/Publish_PSV2?siteId={site_id}&publishNotes=Published%2520from%2520Page%2520Studio"
    
    # Add delay before API call to prevent blocking/rate limiting
    # Publish API can get blocked if called too frequently
    logging.info("[TIMING] Waiting 2 seconds before Publish API call to avoid rate limiting...")
    time.sleep(2)
    
    try:
        logging.info("Calling Publish API...")
        api_start = time.time()
        response = requests.post(api_url, headers=headers, data=json.dumps(payload), timeout=60)
        api_duration = time.time() - api_start
        response.raise_for_status()
        logging.info(f"[SUCCESS] Publish API call successful. Status: {response.status_code}, Duration: {api_duration:.2f} seconds")
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        status_code = response.status_code if 'response' in locals() else 'N/A'
        response_text = response.text if 'response' in locals() else 'No response'
        
        # Special handling for 500 Internal Server Error with retry suggestion
        if status_code == 500:
            logging.error(f"[ERROR] 500 Internal Server Error in psPublishApi")
            logging.error(f"[ERROR] Response text: {response_text[:500]}")
            logging.warning(f"[WARNING] 500 error may be temporary. Consider retrying after a delay.")
            return {"status": "error", "message": "500 Internal Server Error", "status_code": 500, "retry_suggested": True}
        
        logging.error(f"[ERROR] HTTP error in psPublishApi: {http_err} (Status Code: {status_code})")
        if status_code >= 500:
            logging.error(f"[ERROR] Server error response: {response_text[:500]}")
        return {"status": "error", "message": str(http_err), "status_code": status_code}
    except requests.exceptions.Timeout as e:
        logging.error(f"[ERROR] Publish API call timed out after 60 seconds: {e}")
        return {"status": "error", "message": "Request timeout"}
    except requests.exceptions.RequestException as e:
        logging.error(f"[ERROR] Publish API call failed: {e}")
        logging.exception("Full traceback:")
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
        logging.info(f"[SUCCESS] Fetched page info for page ID: {page_id}")
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"[ERROR] Failed to fetch page info: {e}")
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
        logging.info(f"[SUCCESS] Updated Meta Info for page ID: {payload.get('pageId')}")
    except requests.exceptions.RequestException as e:
        logging.error(f"[ERROR] Failed to update Meta Info for page ID: {payload.get('pageId')}: {e}")
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

    print(f"[API] Attempting POST to: {api_url}")
    
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
        time.sleep(2)
        # 4. Return the successful JSON response content
        return response.json()

    except requests.exceptions.HTTPError as http_err:
        print(f"[ERROR] HTTP error occurred: {http_err} (Status Code: {response.status_code})")
        return {"error": "HTTP Error", "details": str(http_err), "status_code": response.status_code}
    except requests.exceptions.ConnectionError as conn_err:
        print(f"[ERROR] Connection error occurred: {conn_err}")
        return {"error": "Connection Error", "details": str(conn_err)}
    except requests.exceptions.Timeout as timeout_err:
        print(f"[ERROR] Timeout error occurred: {timeout_err}")
        return {"error": "Timeout Error", "details": str(timeout_err)}
    except requests.exceptions.RequestException as req_err:
        print(f"[ERROR] An unexpected error occurred: {req_err}")
        return {"error": "Request Error", "details": str(req_err)}
    except json.JSONDecodeError:
        print(f"[ERROR] Failed to decode JSON response. Response text: {response.text}")
        return {"error": "JSON Decode Error", "details": "Response was not valid JSON"}
    






def CreatePage(base_url, headers, payload,template_id):
    print("after")
    print(template_id)
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

    print(f"\n[API] Attempting CreatePage: {api_url} ============================================?>>>>>>>>>>>>>>>>>>>")
    print(payload)
    print(f"\n[API] Attempting ) ============================================?>>>>>>>>>>>>>>>>>>>")
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
        response_text = response.text if 'response' in locals() else 'No response'
        
        # Special handling for 500 Internal Server Error
        if status_code == 500:
            logging.error(f"[ERROR] 500 Internal Server Error in CreatePage: {http_err}")
            logging.error(f"[ERROR] Response text: {response_text[:500]}")  # Log first 500 chars
            return {"error": "500 Internal Server Error", "details": f"Server error: {str(http_err)}", "status_code": 500, "response_text": response_text[:200]}
        
        print(f"[ERROR] HTTP error occurred: {http_err} (Status Code: {status_code})")
        if status_code >= 500:
            logging.error(f"[ERROR] Server error ({status_code}): {response_text[:500]}")
        return {"error": "HTTP Error", "details": str(http_err), "status_code": status_code}
    except requests.exceptions.ConnectionError as conn_err:
        print(f"[ERROR] Connection error occurred: {conn_err}")
        return {"error": "Connection Error", "details": str(conn_err)}
    except requests.exceptions.Timeout as timeout_err:
        print(f"[ERROR] Timeout error occurred: {timeout_err}")
        return {"error": "Timeout Error", "details": str(timeout_err)}
    except requests.exceptions.RequestException as req_err:
        print(f"[ERROR] An unexpected request error occurred: {req_err}")
        return {"error": "Request Error", "details": str(req_err)}
    except json.JSONDecodeError:
        print(f"[ERROR] Failed to decode JSON response. Response text: {response.text if 'response' in locals() else 'No response object.'}")
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

    print(f"\n[API] Attempting GET to: {api_url}")

    try:
        # 2. Send GET request
        response = requests.get(
            api_url, 
            headers=headers,
            timeout=10
        )

        # 3. Trigger exception for HTTP error codes (4xx, 5xx)
        response.raise_for_status()
        time.sleep(2)
        # 4. Return JSON body (expected to be a list of categories)
        return response.json()

    except requests.exceptions.HTTPError as http_err:
        status_code = response.status_code if 'response' in locals() else 'N/A'
        print(f"[ERROR] HTTP error occurred: {http_err} (Status Code: {status_code})")
        return {"error": "HTTP Error", "details": str(http_err), "status_code": status_code}

    except requests.exceptions.ConnectionError as conn_err:
        print(f"[ERROR] Connection error occurred: {conn_err}")
        return {"error": "Connection Error", "details": str(conn_err)}

    except requests.exceptions.Timeout as timeout_err:
        print(f"[ERROR] Timeout error occurred: {timeout_err}")
        return {"error": "Timeout Error", "details": str(timeout_err)}

    except requests.exceptions.RequestException as req_err:
        print(f"[ERROR] Request exception occurred: {req_err}")
        return {"error": "Request Error", "details": str(req_err)}

    except json.JSONDecodeError:
        print(f"[ERROR] Failed to decode JSON. Response text: {response.text if 'response' in locals() else 'No response'}")
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
        "PageSize": 100, # Increased page size for a better chance of finding the item
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
            print(f"[WARNING] V-Component '{component_name}' not found. 'vComponents' array was empty or search failed.")
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
                
                # print(f"[SUCCESS] Found V-Component Alias and ID for '{component_name}': ({component_alias}, {component_id})")
                return (vComponentId,component_alias, component_id) # <-- Return both values as a tuple

        # 5. Fallback if search returned data, but no exact name match was found
        # print(f"[WARNING] Search returned data, but no exact match found for '{component_name}' in the 'vComponents' list.")
        return {"error": "Component Not Found", "details": f"No exact component name match for '{component_name}' in returned list."}

    except requests.exceptions.RequestException as err:
        status_code = response.status_code if response is not None else 'N/A'
        print(f"[ERROR] API Error in GetComponentAliasByName: {err} (Status Code: {status_code})")
        return {"error": "Request Error", "details": str(err), "status_code": status_code}
    except json.JSONDecodeError:
        response_text = response.text if response is not None else 'No response object.'
        print(f"[ERROR] JSON Decode Error. Response text: {response_text}")
        return {"error": "JSON Decode Error", "details": "Response was not valid JSON"}


def GetAllVComponents(base_url: str, headers: Dict[str, str], page_size: int = 1000) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
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
    time.sleep(2)
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
        response = None  # Initialize to avoid UnboundLocalError in exception handlers
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
            time.sleep(2)
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
            logger.error(f"[ERROR] API Request Error on Page {current_page}: {err} (Status Code: {status_code})")
            return {"error": "Request Error", "details": str(err), "status_code": status_code, "page": current_page}
            
        except json.JSONDecodeError:
            response_text = response.text if response is not None else 'No response object.'
            logger.error(f"[ERROR] JSON Decode Error on Page {current_page}. Response text: {response_text[:100]}...")
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

        # print(f"[SUCCESS] Found {len(matched_pages)} match(es) for '{template_page_name}'.")
        return matched_pages

    except requests.exceptions.RequestException as err:
        status_code = response.status_code if response is not None else "N/A"
        print(f"[ERROR] API Request Error in GetTemplatePageByName: {err} (Status Code: {status_code})")
        return {"error": "Request Error", "details": str(err), "status_code": status_code}

    except json.JSONDecodeError:
        response_text = response.text if response is not None else "No response object"
        print(f"[ERROR] JSON Decode Error in GetTemplatePageByName. Response body: {response_text}")
        return {"error": "JSON Decode Error", "details": "Invalid JSON response received from API"}



def get_theme_configuration(base_url: str, site_id: int, headers: Dict[str, str]) -> Union[Dict[str, Any], None]:
    """
    Fetches theme configuration from the CMS Theme API.
    
    Endpoint: /ccadmin/cms/api/ThemeApi/GetThemeConfiguration
    
    Args:
        base_url (str): The base URL of the CMS API (e.g., "https://cpdulles.cms.milestoneinternet.info").
        site_id (int): The Site ID to fetch theme configuration for.
        headers (dict): HTTP headers, typically including Authorization and Content-Type.
    
    Returns:
        dict: The JSON response containing theme configuration if successful, otherwise None.
        
    Example Response:
        {
            "websiteThemeMappping": {
                "themeName": "Default Branding",
                "themeId": 5202814,
                "groupMapping": [
                    {
                        "groupId": 46,
                        "groupName": " MarriottGlobal1 color group",
                        "groupType": 1
                    },
                    {
                        "groupId": 47,
                        "groupName": " MarriottGlobal1 font group ",
                        "groupType": 2
                    }
                ]
            },
            "success": true,
            "errorMessage": null
        }
    """
    api_url = f"{base_url}/ccadmin/cms/api/ThemeApi/GetThemeConfiguration"
    
    payload = {
        "SiteId": site_id
    }
    
    try:
        logging.info(f"Fetching theme configuration for SiteId: {site_id}")
        response = requests.post(api_url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        
        response_data = response.json()
        
        if response_data.get("success", False):
            logging.info(f"[SUCCESS] Successfully fetched theme configuration for SiteId: {site_id}")
            return response_data
        else:
            error_message = response_data.get("errorMessage", "Unknown error")
            logging.error(f"[ERROR] API returned success=false: {error_message}")
            return None
            
    except requests.exceptions.HTTPError as http_err:
        status_code = response.status_code if 'response' in locals() else 'N/A'
        logging.error(f"[ERROR] HTTP error occurred: {http_err} (Status Code: {status_code})")
        return None
    except requests.exceptions.ConnectionError as conn_err:
        logging.error(f"[ERROR] Connection error occurred: {conn_err}")
        return None
    except requests.exceptions.Timeout as timeout_err:
        logging.error(f"[ERROR] Timeout error occurred: {timeout_err}")
        return None
    except requests.exceptions.RequestException as req_err:
        logging.error(f"[ERROR] Request error occurred: {req_err}")
        return None
    except json.JSONDecodeError as json_err:
        response_text = response.text if 'response' in locals() else 'No response'
        logging.error(f"[ERROR] JSON decode error: {json_err}. Response: {response_text[:200]}")
        return None
    except Exception as e:
        logging.error(f"[ERROR] Unexpected error in get_theme_configuration: {e}")
        return None


def get_group_record(base_url: str, payload: dict, headers: Dict[str, str]) -> Union[Dict[str, Any], None]:
    """
    Fetches group records with theme variables from the CMS Theme API.
    
    Endpoint: /ccadmin/cms/api/ThemeApi/GetGroupRecord
    
    Args:
        base_url (str): The base URL of the CMS API.
        payload (dict): Complete request payload containing:
                       - SiteId: Site ID (int)
                       - groups: List of group objects with themeId and groupId
        headers (dict): HTTP headers, typically including Authorization and Content-Type.
    
    Returns:
        dict: The JSON response containing group records with variables if successful, otherwise None.
        
    Example:
        payload = {
            "SiteId": 8292,
            "groups": [
                {"themeId": 81, "groupId": 9533},
                {"themeId": 83, "groupId": 9542}
            ]
        }
        response = get_group_record(base_url, payload, headers)
        
    Example Response:
        {
            "groupsRecordDetails": [
                {
                    "themeId": 81,
                    "themeName": "milestoneGlobal",
                    "groupId": 9533,
                    "groupName": "Front 12",
                    "grouptype": 2,
                    "groupVariables": [
                        {
                            "variableName": "milestoneGlobal font variable",
                            "variableType": 2,
                            "variableAlias": null,
                            "variableValue": "test2121"
                        }
                    ]
                }
            ],
            "success": true,
            "errorMessage": null
        }
    """
    api_url = f"{base_url}/ccadmin/cms/api/ThemeApi/GetGroupRecord"
    
    try:
        site_id = payload.get('SiteId')
        groups = payload.get('groups', [])
        logging.info(f"Fetching group records for SiteId: {site_id} with {len(groups)} groups")
        response = requests.post(api_url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        
        response_data = response.json()
        
        if response_data.get("success", False):
            logging.info(f"[SUCCESS] Successfully fetched group records for SiteId: {site_id}")
            return response_data
        else:
            error_message = response_data.get("errorMessage", "Unknown error")
            logging.error(f"[ERROR] API returned success=false: {error_message}")
            return None
            
    except requests.exceptions.HTTPError as http_err:
        status_code = response.status_code if 'response' in locals() else 'N/A'
        logging.error(f"[ERROR] HTTP error occurred: {http_err} (Status Code: {status_code})")
        return None
    except requests.exceptions.ConnectionError as conn_err:
        logging.error(f"[ERROR] Connection error occurred: {conn_err}")
        return None
    except requests.exceptions.Timeout as timeout_err:
        logging.error(f"[ERROR] Timeout error occurred: {timeout_err}")
        return None
    except requests.exceptions.RequestException as req_err:
        logging.error(f"[ERROR] Request error occurred: {req_err}")
        return None
    except json.JSONDecodeError as json_err:
        response_text = response.text if 'response' in locals() else 'No response'
        logging.error(f"[ERROR] JSON decode error: {json_err}. Response: {response_text[:200]}")
        return None
    except Exception as e:
        logging.error(f"[ERROR] Unexpected error in get_group_record: {e}")
        return None


def update_theme_configuration(base_url: str, payload: dict, headers: dict = None) -> dict:
    """
    Update theme configuration for a site
    
    Args:
        base_url: Base URL of the CMS (e.g., "https://example.cms.milestoneinternet.info")
        payload: Complete request payload containing:
                 - siteId: Site ID (int)
                 - themeId: Theme ID (int)
                 - groups: List of group objects with groupId
        headers: Optional headers (should include Authorization token)
    
    Returns:
        dict: API response with success status
    
    Example:
        payload = {
            "siteId": 8292,
            "themeId": 75037833,
            "groups": [
                {"groupId": 8871},
                {"groupId": 8872}
            ]
        }
        response = update_theme_configuration(base_url, payload, headers)
    """
    try:
        # Build the API endpoint
        api_endpoint = f"{base_url.rstrip('/')}/ccadmin/cms/api/ThemeApi/UpdateThemeConfiguration"
        
        # Set default headers if not provided
        if headers is None:
            headers = {
                'Content-Type': 'application/json'
            }
        else:
            # Ensure Content-Type is set
            headers = headers.copy()
            headers['Content-Type'] = 'application/json'
        
        logging.info(f"Calling UpdateThemeConfiguration API: {api_endpoint}")
        logging.info(f"Payload: siteId={payload.get('siteId')}, themeId={payload.get('themeId')}, groups={len(payload.get('groups', []))}")
        
        # Make POST request
        response = requests.post(
            api_endpoint,
            json=payload,
            headers=headers,
            timeout=30
        )
        
        # Log response status
        logging.info(f"UpdateThemeConfiguration API response status: {response.status_code}")
        
        # Raise exception for bad status codes
        response.raise_for_status()
        
        # Parse and return JSON response
        response_data = response.json()
        logging.info(f"UpdateThemeConfiguration API response: {response_data.get('success', False)}")
        
        return response_data
        
    except requests.exceptions.HTTPError as http_err:
        status_code = response.status_code if 'response' in locals() else 'N/A'
        logging.error(f"[ERROR] HTTP error in update_theme_configuration: {http_err} (Status Code: {status_code})")
        return None
    except requests.exceptions.ConnectionError as conn_err:
        logging.error(f"[ERROR] Connection error in update_theme_configuration: {conn_err}")
        return None
    except requests.exceptions.Timeout as timeout_err:
        logging.error(f"[ERROR] Timeout error in update_theme_configuration: {timeout_err}")
        return None
    except requests.exceptions.RequestException as req_err:
        logging.error(f"[ERROR] Request error in update_theme_configuration: {req_err}")
        return None
    except json.JSONDecodeError as json_err:
        response_text = response.text if 'response' in locals() else 'No response'
        logging.error(f"[ERROR] JSON decode error in update_theme_configuration: {json_err}. Response: {response_text[:200]}")
        return None
    except Exception as e:
        logging.error(f"[ERROR] Unexpected error in update_theme_configuration: {e}")
        return None


def update_theme_variables(base_url: str, payload: dict, headers: dict = None) -> dict:
    """
    Update theme variables for a site
    
    Args:
        base_url: Base URL of the CMS (e.g., "https://example.cms.milestoneinternet.info")
        payload: Complete request payload containing:
                 - siteId: Site ID (int)
                 - themeId: Theme ID (int)
                 - groups: List of groups with variables
        headers: Optional headers (should include Authorization token)
    
    Returns:
        dict: API response with success status and updated group IDs
    
    Example:
        payload = {
            "siteId": 28,
            "themeId": 78,
            "groups": [
                {
                    "Groupid": 46,
                    "GroupName": "Color",
                    "GroupType": 1,
                    "themeVariables": "{\"color-variable\":\"#0d39b3\"}"
                }
            ]
        }
        response = update_theme_variables(base_url, payload, headers)
    """
    try:
        # Build the API endpoint
        api_endpoint = f"{base_url.rstrip('/')}/ccadmin/cms/api/ThemeApi/UpdateThemeVariables"
        
        # Set default headers if not provided
        if headers is None:
            headers = {
                'Content-Type': 'application/json'
            }
        else:
            # Ensure Content-Type is set
            headers = headers.copy()
            headers['Content-Type'] = 'application/json'
        
        logging.info(f"Calling UpdateThemeVariables API: {api_endpoint}")
        logging.info(f"Payload: siteId={payload.get('siteId')}, themeId={payload.get('themeId')}, groups={len(payload.get('groups', []))}")
        
        # Make POST request
        response = requests.post(
            api_endpoint,
            json=payload,
            headers=headers,
            timeout=30
        )
        
        # Log response status
        logging.info(f"UpdateThemeVariables API response status: {response.status_code}")
        
        # Raise exception for bad status codes
        response.raise_for_status()
        
        # Parse and return JSON response
        response_data = response.json()
        logging.info(f"UpdateThemeVariables API response: {response_data.get('success', False)}")
        
        return response_data
        
    except requests.exceptions.HTTPError as http_err:
        status_code = response.status_code if 'response' in locals() else 'N/A'
        logging.error(f"[ERROR] HTTP error in update_theme_variables: {http_err} (Status Code: {status_code})")
        return None
    except requests.exceptions.ConnectionError as conn_err:
        logging.error(f"[ERROR] Connection error in update_theme_variables: {conn_err}")
        return None
    except requests.exceptions.Timeout as timeout_err:
        logging.error(f"[ERROR] Timeout error in update_theme_variables: {timeout_err}")
        return None
    except requests.exceptions.RequestException as req_err:
        logging.error(f"[ERROR] Request error in update_theme_variables: {req_err}")
        return None
    except json.JSONDecodeError as json_err:
        response_text = response.text if 'response' in locals() else 'No response'
        logging.error(f"[ERROR] JSON decode error in update_theme_variables: {json_err}. Response: {response_text[:200]}")
        return None
    except Exception as e:
        logging.error(f"[ERROR] Unexpected error in update_theme_variables: {e}")
        return None


def save_module_category(base_url: str, headers: dict, payload: dict) -> Union[Dict[str, Any], None]:
    """
    Saves or updates a module category using the CMS Module API.
    
    Endpoint: /ccadmin/cms/api/ModuleApi/SaveCategory
    
    Args:
        base_url (str): The base URL of the CMS API (e.g., "https://example.cms.milestoneinternet.info").
        headers (dict): HTTP headers, typically including Authorization and Content-Type.
        payload (dict): Complete request payload containing:
                       - ModuleCategory: Dictionary with category details including:
                         - CategoryId: int (0 for new category, existing ID for update)
                         - ParentCategory: int (parent category ID, 0 for root)
                         - CategoryName: str (name of the category)
                         - CategoryAlias: str (alias/slug for the category)
                         - ResourceTypeID: int (resource type identifier)
                         - ResourceTypeIdForMultipleImages: int
                         - categorystatus: int (1 for active, 0 for inactive)
                         - MilestoneModuleCategoryID: int
                         - ModuleIdentifier: str (module identifier string)
                         - ShowSnippets: int
                         - TopNavigationFormatId: int
                         - ModuleOrder: int (display order)
                         - SchemaBusinessTypeDetailID: int
                         - IsEnableRedirection: bool
                         - RedirectionURL: str
                         - SiteId: int (site identifier)
    
    Returns:
        dict: The JSON response from the API if successful, otherwise None.
    
    Example:
        payload = {
            "ModuleCategory": {
                "CategoryId": 0,
                "ParentCategory": 0,
                "CategoryName": "Test Sample Category",
                "CategoryAlias": "Test 55",
                "ResourceTypeID": 1,
                "ResourceTypeIdForMultipleImages": 0,
                "categorystatus": 1,
                "MilestoneModuleCategoryID": 0,
                "ModuleIdentifier": "MODULE_ABC",
                "ShowSnippets": 0,
                "TopNavigationFormatId": 0,
                "ModuleOrder": 1,
                "SchemaBusinessTypeDetailID": 0,
                "IsEnableRedirection": False,
                "RedirectionURL": "",
                "SiteId": 28
            }
        }
        response = save_module_category(base_url, headers, payload)
    """
    api_url = f"{base_url}/ccadmin/cms/api/ModuleApi/SaveCategory"
    
    try:
        # Ensure Content-Type is set
        if headers is None:
            headers = {
                'Content-Type': 'application/json'
            }
        else:
            headers = headers.copy()
            headers['Content-Type'] = 'application/json'
        
        site_id = payload.get('ModuleCategory', {}).get('SiteId', 'N/A')
        category_name = payload.get('ModuleCategory', {}).get('CategoryName', 'N/A')
        logging.info(f"Calling SaveCategory API for SiteId: {site_id}, CategoryName: {category_name}")
        
        response = requests.post(
            api_url,
            headers=headers,
            json=payload,
            timeout=30
        )
        
        logging.info(f"SaveCategory API response status: {response.status_code}")
        
        # Raise exception for bad status codes
        response.raise_for_status()
        
        # Parse and return JSON response
        response_data = response.json()
        logging.info(f"[SUCCESS] Successfully saved module category: {category_name}")
        return response_data
        
    except requests.exceptions.HTTPError as http_err:
        status_code = response.status_code if 'response' in locals() else 'N/A'
        response_text = response.text if 'response' in locals() else 'No response'
        logging.error(f"[ERROR] HTTP error in save_module_category: {http_err} (Status Code: {status_code})")
        if status_code >= 500:
            logging.error(f"[ERROR] Server error response: {response_text[:500]}")
        return None
    except requests.exceptions.ConnectionError as conn_err:
        logging.error(f"[ERROR] Connection error in save_module_category: {conn_err}")
        return None
    except requests.exceptions.Timeout as timeout_err:
        logging.error(f"[ERROR] Timeout error in save_module_category: {timeout_err}")
        return None
    except requests.exceptions.RequestException as req_err:
        logging.error(f"[ERROR] Request error in save_module_category: {req_err}")
        return None
    except json.JSONDecodeError as json_err:
        response_text = response.text if 'response' in locals() else 'No response'
        logging.error(f"[ERROR] JSON decode error in save_module_category: {json_err}. Response: {response_text[:200]}")
        return None
    except Exception as e:
        logging.error(f"[ERROR] Unexpected error in save_module_category: {e}")
        return None


def update_miblock_record_asset(base_url: str, headers: dict, payload: dict) -> Union[Dict[str, Any], None]:
    """
    Updates asset fields (e.g., images) for a Miblock record using the CMS Miblock API.
    This function is typically called just after a record is created to update component images.
    
    Endpoint: /ccadmin/cms/api/MiblockApi/UpdateMiblockRecordAsset
    
    Args:
        base_url (str): The base URL of the CMS API (e.g., "https://example.cms.milestoneinternet.info").
        headers (dict): HTTP headers, typically including Authorization and Content-Type.
        payload (dict): Complete request payload containing:
                       - MiBlockId: int (the MiBlock component ID)
                       - RecordId: int (the record ID to update)
                       - AssetFields: list of dictionaries, each containing:
                         - FieldAlias: str (e.g., "image")
                         - AssetUrls: list of str (URLs of the assets to set)
    
    Returns:
        dict: The JSON response from the API if successful, otherwise None.
    
    Example:
        payload = {
            "MiBlockId": 56779,
            "RecordId": 375110,
            "AssetFields": [
                {
                    "FieldAlias": "image",
                    "AssetUrls": [
                        "https://assets.staging.milestoneinternet.com/cms-platform-for-marriott-replica/abecy-sports-social-module/1920-x-1080-hd-wallpapers-7.jpg"
                    ]
                }
            ]
        }
        response = update_miblock_record_asset(base_url, headers, payload)
    """
    api_url = f"{base_url}/ccadmin/cms/api/MiblockApi/UpdateMiblockRecordAsset"
    
    try:
        # Ensure Content-Type is set
        if headers is None:
            headers = {
                'Content-Type': 'application/json'
            }
        else:
            headers = headers.copy()
            headers['Content-Type'] = 'application/json'
        
        mi_block_id = payload.get('MiBlockId', 'N/A')
        record_id = payload.get('RecordId', 'N/A')
        asset_fields_count = len(payload.get('AssetFields', []))
        logging.info(f"Calling UpdateMiblockRecordAsset API for MiBlockId: {mi_block_id}, RecordId: {record_id}, AssetFields: {asset_fields_count}")
        
        response = requests.post(
            api_url,
            headers=headers,
            json=payload,
            timeout=30
        )
        
        logging.info(f"UpdateMiblockRecordAsset API response status: {response.status_code}")
        
        # Raise exception for bad status codes
        response.raise_for_status()
        
        # Parse and return JSON response
        response_data = response.json()
        logging.info(f"[SUCCESS] Successfully updated Miblock record asset for RecordId: {record_id}")
        return response_data
        
    except requests.exceptions.HTTPError as http_err:
        status_code = response.status_code if 'response' in locals() else 'N/A'
        response_text = response.text if 'response' in locals() else 'No response'
        logging.error(f"[ERROR] HTTP error in update_miblock_record_asset: {http_err} (Status Code: {status_code})")
        if status_code >= 500:
            logging.error(f"[ERROR] Server error response: {response_text[:500]}")
        return None
    except requests.exceptions.ConnectionError as conn_err:
        logging.error(f"[ERROR] Connection error in update_miblock_record_asset: {conn_err}")
        return None
    except requests.exceptions.Timeout as timeout_err:
        logging.error(f"[ERROR] Timeout error in update_miblock_record_asset: {timeout_err}")
        return None
    except requests.exceptions.RequestException as req_err:
        logging.error(f"[ERROR] Request error in update_miblock_record_asset: {req_err}")
        return None
    except json.JSONDecodeError as json_err:
        response_text = response.text if 'response' in locals() else 'No response'
        logging.error(f"[ERROR] JSON decode error in update_miblock_record_asset: {json_err}. Response: {response_text[:200]}")
        return None
    except Exception as e:
        logging.error(f"[ERROR] Unexpected error in update_miblock_record_asset: {e}")
        return None


def get_miblock_records(base_url: str, headers: dict, params: dict) -> Union[Dict[str, Any], List[Dict[str, Any]], None]:
    """
    Retrieves MiBlock records for a specific component and parent using the CMS PageApi.
    This API is used to get immediate parent's sub-record details.
    
    Endpoint: GET /api/PageApi/GetMiblockRecords
    
    Args:
        base_url (str): The base URL of the CMS API (e.g., "https://example.cms.milestoneinternet.info").
        headers (dict): HTTP headers, typically including Authorization.
        params (dict): Query parameters containing:
                      - miblockId: int (the MiBlock component ID)
                      - pageSectionGuid: str (the unique GUID for the page section)
                      - parentRecordId: int (the parent record ID to get sub-records for, 0 for root records)
                      - languageId: int (language ID, default is 0)
    
    Returns:
        dict/list: The JSON response from the API if successful, otherwise None.
                  Returns a list of record objects with complete record details including:
                  - RecordId, ParentRecordId, MiBlockId
                  - RecordJsonString (the actual record data as JSON string)
                  - SubComponentRecordCount (number of child records)
                  - Status, DisplayOrder, CreatedDate, UpdatedDate
    
    Example Request:
        params = {
            "miblockId": 560556,
            "pageSectionGuid": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "parentRecordId": 0,  # 0 for root records, or parent's RecordId for sub-records
            "languageId": 0
        }
        response = get_miblock_records(base_url, headers, params)
    
    Example Response:
        [
          {
            "RecordId": 3383620,
            "ParentRecordId": 3383619,
            "RecordJsonString": "{\\"Id\\": \\"3383620\\", \\"ParentId\\": \\"##ParentId##\\", \\"snippet-image\\": null, \\"snippet-image-alt-text\\": \\"Enter Snippet Image ALT Text\\", \\"snippet-tagline\\": \\"Enter Snippet Tagline\\", \\"snippet-description\\": \\"Enter Snippet Description\\", \\"snippet-description-more\\": \\"Enter Snippet Description More\\", \\"snippet-primary-button-text\\": \\"Enter Snippet Primary Button - Text\\", \\"snippet-primary-button-link\\": \\"Enter Snippet Primary Button - Link\\", \\"snippet-secondary-button-text\\": \\"Enter Snippet Secondary Button - Text\\", \\"snippet-secondary-button-link\\": \\"Enter Snippet Secondary Button - Link\\", \\"snippet-title\\": \\"Enter Snippet Title\\"}",
            "SiteId": 16776,
            "MiBlockId": 560557,
            "ParentMiBlockId": 560556,
            "MainParentMiBlockId": 560556,
            "MiBlockName": "Feature-right-Image-Items",
            "ResourceTypeID": 0,
            "Status": true,
            "DisplayOrder": 834,
            "CreatedDate": "2026-01-12T09:14:41.05",
            "CreatedBy": 26083,
            "UpdatedDate": "2026-01-12T09:14:41.05",
            "UpdatedBy": 26083,
            "Tags": null,
            "DraftExists": true,
            "SelectedProfiles": null,
            "ChildComponents": null,
            "MappedProfiles": null,
            "IsPersonalizationEnabled": false,
            "RefByContentLibrary": false,
            "LanguageId": 0,
            "PrimaryLanguageRecordId": 0,
            "RecordUrl": null,
            "StartDate": null,
            "EndDate": null,
            "Region": null,
            "OffsetZoneName": null,
            "Offset": null,
            "TemplateId": 0,
            "TabletTemplateId": 0,
            "MobileTemplateId": 0,
            "AmpTemplateId": 0,
            "SubComponentRecordCount": 0
          }
        ]
    
    Notes:
        - Use parentRecordId = 0 to get root/parent records
        - Use parentRecordId = {parent's RecordId} to get immediate child records
        - RecordJsonString contains the actual field data as a JSON string
        - SubComponentRecordCount indicates if the record has child records
    """
    api_url = f"{base_url}/api/PageApi/GetMiblockRecords"
    
    try:
        miblock_id = params.get('miblockId', 'N/A')
        parent_record_id = params.get('parentRecordId', 'N/A')
        logging.info(f"Calling GetMiblockRecords API for MiblockId: {miblock_id}, ParentRecordId: {parent_record_id}")
        
        response = requests.get(
            api_url,
            headers=headers,
            params=params,
            timeout=30
        )
        
        logging.info(f"GetMiblockRecords API response status: {response.status_code}")
        
        # Raise exception for bad status codes
        response.raise_for_status()
        
        # Parse and return JSON response
        response_data = response.json()
        record_count = len(response_data) if isinstance(response_data, list) else 1
        logging.info(f"[SUCCESS] Successfully retrieved {record_count} MiBlock record(s) for MiblockId: {miblock_id}")
        return response_data
        
    except requests.exceptions.HTTPError as http_err:
        status_code = response.status_code if 'response' in locals() else 'N/A'
        response_text = response.text if 'response' in locals() else 'No response'
        logging.error(f"[ERROR] HTTP error in get_miblock_records: {http_err} (Status Code: {status_code})")
        if status_code >= 500:
            logging.error(f"[ERROR] Server error response: {response_text[:500]}")
        return None
    except requests.exceptions.ConnectionError as conn_err:
        logging.error(f"[ERROR] Connection error in get_miblock_records: {conn_err}")
        return None
    except requests.exceptions.Timeout as timeout_err:
        logging.error(f"[ERROR] Timeout error in get_miblock_records: {timeout_err}")
        return None
    except requests.exceptions.RequestException as req_err:
        logging.error(f"[ERROR] Request error in get_miblock_records: {req_err}")
        return None
    except json.JSONDecodeError as json_err:
        response_text = response.text if 'response' in locals() else 'No response'
        logging.error(f"[ERROR] JSON decode error in get_miblock_records: {json_err}. Response: {response_text[:200]}")
        return None
    except Exception as e:
        logging.error(f"[ERROR] Unexpected error in get_miblock_records: {e}")
        return None
