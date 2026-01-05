"""
LangGraph workflow for component generation
Handles single and multiple section Figma designs
Checks library for matches before generating new components
"""
from typing import TypedDict, List, Optional, Dict, Any
from langgraph.graph import StateGraph, END
from agents.nodes import (
    detect_sections,
    check_library_match,
    generate_html,
    verify_html_match,
    extract_structure,
    create_definitions,
    generate_json,
    add_to_cms,
    update_project
)

# Define State structure
class ComponentGenerationState(TypedDict):
    """State for component generation workflow"""
    # Project information
    project_id: str
    project_name: str
    site_details: Dict[str, str]  # target_site_url, profile_alias, site_id
    
    # Figma information
    figma_url: str
    figma_file_id: Optional[str]
    figma_node_id: Optional[str]
    
    # Section information
    has_multiple_sections: bool
    sections: List[Dict[str, Any]]  # List of section data
    current_section_index: int
    
    # Screenshots
    screenshot_paths: List[str]  # One per section
    
    # Library matching
    matched_components: List[Dict[str, Any]]  # Matched components from library
    match_similarity_scores: List[float]  # Similarity scores for matches
    
    # Generated content
    html_contents: List[str]  # HTML for each section
    html_match_scores: List[float]  # Similarity scores for HTML vs screenshot
    html_verified: List[bool]  # Whether HTML matches screenshot (≥95%)
    html_retry_count: List[int]  # Number of retry attempts per section
    warnings: List[str]  # Warnings for low match scores
    component_configs: List[Dict[str, Any]]  # ComponentConfig.json for each
    component_formats: List[Dict[str, Any]]  # ComponentFormat.json for each
    component_records: List[Dict[str, Any]]  # ComponentRecords.json for each
    
    # CMS integration
    cms_component_ids: List[str]  # CMS IDs after adding to CMS
    
    # Status
    status: str  # 'processing', 'completed', 'error'
    error: Optional[str]
    current_step: str
    needs_retry: bool  # Whether HTML generation needs retry
    retry_section_index: Optional[int]  # Which section needs retry
    final_report: Optional[Dict[str, Any]]  # Final report with verification and retry details


def should_continue_sections(state: ComponentGenerationState) -> str:
    """Determine if we should process more sections or finish"""
    if not state.get('has_multiple_sections', False):
        return 'finish'
    
    current_index = state.get('current_section_index', 0)
    sections = state.get('sections', [])
    
    if current_index < len(sections) - 1:
        return 'next_section'
    return 'finish'


def should_use_match(state: ComponentGenerationState) -> str:
    """Determine if we should use matched component or generate new"""
    current_index = state.get('current_section_index', 0)
    matched_components = state.get('matched_components', [])
    match_similarity_scores = state.get('match_similarity_scores', [])
    
    if current_index < len(matched_components) and current_index < len(match_similarity_scores):
        similarity = match_similarity_scores[current_index]
        if similarity >= 0.85:  # 85% similarity threshold
            return 'use_match'
    
    return 'generate_new'


def should_retry_html(state: ComponentGenerationState) -> str:
    """Determine if we should retry HTML generation due to low match score"""
    if state.get('needs_retry', False):
        retry_section = state.get('retry_section_index', -1)
        current_index = state.get('current_section_index', 0)
        
        # Only retry if it's for the current section
        if retry_section == current_index:
            retry_counts = state.get('html_retry_count', [])
            if len(retry_counts) > current_index:
                current_retry = retry_counts[current_index]
                if current_retry < 3:  # Max 3 retries
                    # Increment retry count
                    retry_counts[current_index] = current_retry + 1
                    state['html_retry_count'] = retry_counts
                    return 'retry'
    
    # No retry needed, continue
    state['needs_retry'] = False
    return 'continue'


def build_component_generation_graph():
    """Build the LangGraph workflow for component generation"""
    
    # Create StateGraph
    workflow = StateGraph(ComponentGenerationState)
    
    # Add nodes
    workflow.add_node("detect_sections", detect_sections)
    workflow.add_node("check_library_match", check_library_match)
    workflow.add_node("generate_html", generate_html)
    workflow.add_node("verify_html_match", verify_html_match)
    workflow.add_node("extract_structure", extract_structure)
    workflow.add_node("create_definitions", create_definitions)
    workflow.add_node("generate_json", generate_json)
    workflow.add_node("add_to_cms", add_to_cms)
    workflow.add_node("update_project", update_project)
    
    # Define edges
    workflow.set_entry_point("detect_sections")
    
    # After detecting sections, check library for matches
    workflow.add_edge("detect_sections", "check_library_match")
    
    # After checking library, decide: use match or generate new
    workflow.add_conditional_edges(
        "check_library_match",
        should_use_match,
        {
            "use_match": "extract_structure",  # Skip HTML generation, use matched structure
            "generate_new": "generate_html"  # Generate new HTML
        }
    )
    
    # After generating HTML (if needed), verify it matches the screenshot
    workflow.add_edge("generate_html", "verify_html_match")
    
    # After verification, decide: retry or continue
    workflow.add_conditional_edges(
        "verify_html_match",
        should_retry_html,
        {
            "retry": "generate_html",  # Loop back to regenerate HTML
            "continue": "extract_structure"  # Continue with extraction
        }
    )
    
    # Continue with structure processing
    workflow.add_edge("extract_structure", "create_definitions")
    workflow.add_edge("create_definitions", "generate_json")
    workflow.add_edge("generate_json", "add_to_cms")
    workflow.add_edge("add_to_cms", "update_project")
    
    # After updating project, check if more sections to process
    workflow.add_conditional_edges(
        "update_project",
        should_continue_sections,
        {
            "next_section": "check_library_match",  # Loop back for next section
            "finish": END
        }
    )
    
    return workflow.compile()


# Create the compiled graph
component_generation_graph = build_component_generation_graph()
