import time
import logging

# Configure logging for the processing step
# Set level to INFO to see all steps executed in the console
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Helper Functions for detailed assembly logic ---

def check_component_availability(component_name: str) -> bool:
    """Simulates checking if a component exists in the CMS library."""
    # Dummy logic: The component is available only if its name is "HeroBanner"
    is_available = component_name == "HeroBanner"
    logging.info(f"Checking component '{component_name}' availability: {'Available' if is_available else 'Not Available'}")
    return is_available

def add_records_for_page(page_name: str):
    """Adds necessary database records/metadata for the new page."""
    logging.info(f"    a) Adding records/metadata for page: {page_name}")
    time.sleep(0.1)

def add_component_to_page(page_name: str, component_name: str):
    """Inserts the component into the page structure (e.g., JSON or template)."""
    logging.info(f"    b) Adding component '{component_name}' to page: {page_name}")
    time.sleep(0.1)

def do_mapping(page_name: str, component_name: str):
    """Performs data mapping between the content record and component slots."""
    logging.info(f"    c) Performing data mapping for {component_name} on {page_name}")
    time.sleep(0.1)

def publish_page_immediately(page_name: str):
    """Marks the specific page for immediate publishing."""
    logging.info(f"    d) Marking page {page_name} for immediate publishing.")
    time.sleep(0.1)

# --- Core Assembly Logic Function ---

def assemble_page_templates(state: dict):
    """
    Handles the detailed process of checking component availability and assembling pages.
    
    Implements the conditional logic provided by the user.
    """
    logging.info("--- Starting component-based template assembly ---")
    
    # Define a page and a required component for this simulation
    page_to_process = "homepage"
    component_to_use = "HeroBanner" # Change this to "MissingComponent" to test the 'else' path
    
    if check_component_availability(component_to_use):
        logging.info(f"Component '{component_to_use}' is available. Starting assembly sequence for {page_to_process}.")
        
        # a) add records for that page
        add_records_for_page(page_to_process)
        
        # b) add component to page
        add_component_to_page(page_to_process, component_to_use)
        
        # c) do mapping
        do_mapping(page_to_process, component_to_use)
        
        # d) publish page
        publish_page_immediately(page_to_process)
        
        logging.info(f"Assembly sequence for {page_to_process} complete.")
    else:
        # else print("comp not available")
        logging.info("Component not available. Skipping assembly steps for this page.")


# --- Main Pipeline Entry Point (Fixed for External Arguments and State Type) ---

def run_assembly_processing_step(state: dict, *args, **kwargs) -> dict:
    """
    Handles the assembly step.

    *args and **kwargs are added to prevent the positional argument error.
    
    The state variable is checked to ensure it is a dictionary, resolving 
    the "'str' object does not support item assignment" error if the pipeline 
    passed an unexpected string value for the state.
    """
    logging.info("Starting Assembling CMS Pages and Publishing (Focused Logic)...")
    
    # CRITICAL FIX: Check if state is a dictionary before assignment
    if not isinstance(state, dict):
        logging.warning(f"Input 'state' was type {type(state)}. Initializing state as an empty dict to proceed safely.")
        # If state is not a dict (e.g., it's an error message string), re-initialize it.
        state = {} 

    try:
        # Execute the core component logic
        assemble_page_templates(state)
        
        # Update state with success indicator
        state['assembly_status'] = "SUCCESS: Component logic executed."
        
        logging.info("Focused Assembly Logic finished successfully.")

    except Exception as e:
        # Since we ensured 'state' is a dict, assignment here is safe.
        state['assembly_status'] = f"FAILURE: {str(e)}"
        logging.error(f"Error during assembly: {e}")
        # Re-raise the exception to signal a pipeline failure
        raise

    return state