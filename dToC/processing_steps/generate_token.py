import json
import os
from typing import Dict, Any

# Import the API function and UPLOAD_FOLDER path
from apis import generate_cms_token
from config import UPLOAD_FOLDER

def get_config_filepath(file_prefix: str) -> str:
    """Constructs the unique config.json filepath based on the prefix."""
    config_filename = f"{file_prefix}_config.json"
    return os.path.join(UPLOAD_FOLDER, config_filename)

def load_settings(file_prefix: str) -> Dict[str, Any] | None:
    """Loads the settings/config file based on the unique prefix."""
    filepath = get_config_filepath(file_prefix)
    if not os.path.exists(filepath):
        print(f"Token Generator: Config file not found at {filepath}")
        return None
    try:
        with open(filepath, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Token Generator: Error loading config file: {e}")
        return None

def save_settings(file_prefix: str, settings: Dict[str, Any]) -> bool:
    """Saves the updated settings/config file."""
    filepath = get_config_filepath(file_prefix)
    try:
        with open(filepath, "w") as f:
            json.dump(settings, f, indent=4)
        return True
    except IOError as e:
        print(f"Token Generator: Error saving settings file: {e}")
        return False

def run_token_generation_step(
    input_filepath: str, 
    step_config: Dict[str, Any], 
    previous_step_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    The main execution function for the token generation step.
    Loads user config, generates a token, and saves it back to the config file.
    """
    # 1. Get the unique file prefix from the previous step's data
    file_prefix = previous_step_data.get('file_prefix')
    if not file_prefix:
        raise ValueError("Token Generation failed: Missing unique file prefix.")

    # 2. Load settings from the uniquely named config file
    settings = load_settings(file_prefix)
    if not settings:
        raise RuntimeError("Could not load user configuration. Aborting token generation.")

    # 3. Extract required fields (keys are snake_case from app.py)
    destination_url = settings.get("target_site_url")
    destination_profile_alias = settings.get("profile_alias")
    
    if not all([destination_url, destination_profile_alias]):
        raise ValueError("Error: Incomplete site configuration (URL or Alias missing) in config file.")
    
    print(f"Generating token for URL: {destination_url} and profile: {destination_profile_alias}")
    
    # 4. Generate the token
    token_data_destination = generate_cms_token(destination_url, destination_profile_alias)
    
    # 5. Update settings with the new token
    settings["destination_token"] = token_data_destination
    
    # 6. Save the updated settings
    if not save_settings(file_prefix, settings):
        raise IOError("Failed to save the generated token back to the configuration file.")

    # 7. Return data for the next step
    return {
        "token_generated": True,
        "file_prefix": file_prefix # Continue propagating the prefix
    }