import json
import os
import re
import sys
from typing import Dict, Any, Optional

# --- MOCK DEPENDENCIES ---
# Mock the CMS token generation API call
def generate_cms_token(url: str, alias: str) -> str:
    """Simulates CMS login token generation API call."""
    print(f"DEBUG: Calling generate_cms_token(url={url}, alias={alias})")
    # Creates a unique, deterministic token based on inputs
    return f"CMS_LOGIN_TOKEN_FOR_{alias.upper()}_{url.split('//')[-1].split('/')[0].replace('.', '_')}_{os.urandom(4).hex()}"

# Mock configuration settings (Fallback if config.py is not available)
try:
    from config import UPLOAD_FOLDER
except ImportError:
    class MockConfig:
        UPLOAD_FOLDER = os.path.join(os.getcwd(), "temp_uploads") 
    UPLOAD_FOLDER = MockConfig.UPLOAD_FOLDER


# --- FILE UTILITIES ---

def get_config_filepath(file_prefix: str) -> str:
    """
    Constructs the unique config.json filepath based on the prefix. 
    This ensures the config file name is strictly '<UUID>_config.json'.
    """
    config_filename = f"{file_prefix}_config.json"
    return os.path.join(UPLOAD_FOLDER, config_filename)

def load_settings(file_prefix: str) -> Dict[str, Any] | None:
    """Loads the settings/config file based on the unique prefix for persistence."""
    filepath = get_config_filepath(file_prefix)
    
    if not os.path.exists(filepath):
        return {} 
    try:
        with open(filepath, "r", encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Token Generator: Error loading persistence config file ({filepath}): {e}", file=sys.stderr)
        return None

def save_settings(file_prefix: str, settings: Dict[str, Any]) -> bool:
    """Saves the updated settings/config file."""
    filepath = get_config_filepath(file_prefix)
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True) 
        with open(filepath, "w", encoding='utf-8') as f:
            json.dump(settings, f, indent=4)
        return True
    except IOError as e:
        print(f"Token Generator: Error saving settings file ({filepath}): {e}", file=sys.stderr)
        return False

# --- LOGIC UTILITIES ---

def extract_automation_details(json_data: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """
    Searches the loaded JSON data for the 'Automation Guide' page and extracts 
    Site Link, SiteId, and Profile Alias from its description/content.
    """
    print("DEBUG: Starting Automation Guide detail extraction...")
    try:
        for page in json_data.get('pages', []):
            page_name = page.get('text', page.get('page_name', '')) 
            normalized_page_name = page_name.strip().lower()
            
            if "automation guide" in normalized_page_name:
                print("DEBUG: Found 'Automation Guide' page.")
                
                content_source = page.get('content_blocks', '') or page.get('description', '') 
                normalized_content = re.sub(r'\s+', ' ', content_source).strip()
                
                link_pattern = r'Site\s*Link:\s*([^\s]+)'
                site_id_pattern = r'SiteId:\s*(\d+)'
                alias_pattern = r'Profile\s*Alias:\s*([^\s]+)'

                link_match = re.search(link_pattern, normalized_content, re.IGNORECASE)
                site_id_match = re.search(site_id_pattern, normalized_content, re.IGNORECASE)
                alias_match = re.search(alias_pattern, normalized_content, re.IGNORECASE)

                site_link = link_match.group(1).strip() if link_match else None
                site_id = site_id_match.group(1).strip() if site_id_match else None
                profile_alias = alias_match.group(1).strip() if alias_match else None

                if all([site_link, site_id, profile_alias]):
                    return {
                        "target_site_url": site_link,
                        "site_id": site_id,
                        "profile_alias": profile_alias
                    }
                else:
                    print("DEBUG: Extraction FAILED (One or more required fields were missing or invalid).")
                    return None
            
        print("DEBUG: 'Automation Guide' page not found after checking all pages.")
        return None 
    except Exception as e:
        print(f"Error during JSON parsing and extraction: {e}", file=sys.stderr)
        return None

# --- MAIN STEP FUNCTION ---

def run_token_generation_step(
    input_filepath: str, 
    step_config: Dict[str, Any], 
    previous_step_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    The main execution function for the token generation step.
    Loads the converted JSON file, extracts config, generates a CMS login token, 
    and saves the token and config back to the persistent settings file.
    """
    
    target_suffix = "_util_pages.json" 
    
    # 1. Get file_prefix from previous step. We rely on the preceding step to provide this key.
    file_prefix = previous_step_data.get('file_prefix')
    
    if not file_prefix:
        raise ValueError(
            "Token Generation failed: The required unique file prefix was not provided in 'previous_step_data'. "
            "Please ensure the preceding step is reliably setting this value."
        )
    
    print(f"INFO: Using file_prefix from previous step: {file_prefix}")

    # 2. RESOLVE THE CORRECT PATH TO THE _util_pages.json file
    target_filename = f"{file_prefix}{target_suffix}"
    file_to_load = os.path.join(UPLOAD_FOLDER, target_filename)
    
    # 3. Load the uploaded JSON file
    try:
        with open(file_to_load, 'r', encoding='utf-8') as f:
            uploaded_json_data = json.load(f)
        print(f"DEBUG: Successfully loaded JSON data from: {file_to_load}")
        
    except FileNotFoundError:
        raise RuntimeError(
            f"Could not load the required utility page file at {file_to_load}. File not found."
        )
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Could not load the file at {file_to_load}. Found file, but it is not valid JSON. Original Error: {e}"
        )
    except Exception as e:
        raise RuntimeError(f"Could not load the file at {file_to_load}. Generic Error: {e}")

    # 4. Extract required configuration from the JSON data
    extracted_config = extract_automation_details(uploaded_json_data)
    
    if not extracted_config:
        raise ValueError(
            "Error: Could not find or extract Automation Guide details from the loaded JSON content. "
            "Please verify the required fields (Site Link, SiteId, Profile Alias)."
        )

    destination_url = extracted_config["target_site_url"]
    destination_profile_alias = extracted_config["profile_alias"]
    
    # 5. Generate the CMS LOGIN token
    cms_login_token_data = generate_cms_token(destination_url, destination_profile_alias)
    
    # 6. Load/Update persistence settings (using the single, correct config file)
    settings = load_settings(file_prefix)
    if settings is None:
        raise RuntimeError("Failed to initialize or load config storage.")

    # 7. Update settings with the new token AND the extracted config details
    settings["cms_login_token"] = cms_login_token_data # <--- Renamed key to 'cms_login_token'
    settings.update(extracted_config) 
    
    # 8. Save the updated settings
    if not save_settings(file_prefix, settings):
        raise IOError("Failed to save the generated token and config back to the configuration file.")
        
    print(f"INFO: Generated CMS Login Token and saved to config: {cms_login_token_data}")

    # 9. Return data for the next step
    return {
        "token_generated": True,
        "file_prefix": file_prefix # Continue propagating the prefix for subsequent steps
    }