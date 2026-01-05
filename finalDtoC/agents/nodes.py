"""
Agent nodes for LangGraph workflow
Each node is a function that processes the state and returns updated state
"""
from typing import Dict, Any, List
from agents.graph import ComponentGenerationState
from api.figma import FigmaClient
from api.claude import ClaudeClient
from api.cms import CMSClient
from utils.matching import find_similar_components
from utils.generator import generate_component_json
import os


def detect_sections(state: ComponentGenerationState) -> ComponentGenerationState:
    """
    Detect if Figma design has multiple sections or single section
    Analyzes Figma file structure to identify sections
    """
    figma_url = state.get('figma_url', '')
    figma_client = FigmaClient()  # Initialize with token from state/session
    
    try:
        # Parse Figma URL
        file_id, node_id = figma_client.parse_figma_url(figma_url)
        
        # Get Figma file structure
        # TODO: Implement section detection logic
        # For now, assume single section (can be enhanced later)
        # In real implementation, would analyze Figma file structure
        
        # Placeholder: Check if node has children that could be sections
        has_multiple = False  # Default to single section
        sections = [{'id': node_id, 'name': 'Main Section'}]  # Default single section
        
        state['figma_file_id'] = file_id
        state['figma_node_id'] = node_id
        state['has_multiple_sections'] = has_multiple
        state['sections'] = sections
        state['current_section_index'] = 0
        state['current_step'] = 'sections_detected'
        
    except Exception as e:
        state['status'] = 'error'
        state['error'] = f"Error detecting sections: {str(e)}"
        state['current_step'] = 'error'
    
    return state


def check_library_match(state: ComponentGenerationState) -> ComponentGenerationState:
    """
    Check training library for similar components using vector similarity
    Generates embedding for current section screenshot and searches database
    """
    current_index = state.get('current_section_index', 0)
    screenshot_paths = state.get('screenshot_paths', [])
    
    if current_index >= len(screenshot_paths):
        # No screenshot yet, skip matching
        state['matched_components'] = state.get('matched_components', []) + [None]
        state['match_similarity_scores'] = state.get('match_similarity_scores', []) + [0.0]
        return state
    
    screenshot_path = screenshot_paths[current_index]
    
    try:
        # Find similar components in training library
        matches = find_similar_components(
            screenshot_path=screenshot_path,
            similarity_threshold=0.85,
            limit=5
        )
        
        if matches and len(matches) > 0:
            best_match = matches[0]
            similarity = best_match.get('similarity', 0.0)
            
            # Update matched components list
            matched = state.get('matched_components', [])
            if len(matched) <= current_index:
                matched.extend([None] * (current_index - len(matched) + 1))
            matched[current_index] = best_match
            
            # Update similarity scores
            scores = state.get('match_similarity_scores', [])
            if len(scores) <= current_index:
                scores.extend([0.0] * (current_index - len(scores) + 1))
            scores[current_index] = similarity
            
            state['matched_components'] = matched
            state['match_similarity_scores'] = scores
            state['current_step'] = f'match_checked_section_{current_index}'
        else:
            # No match found
            matched = state.get('matched_components', [])
            if len(matched) <= current_index:
                matched.extend([None] * (current_index - len(matched) + 1))
            matched[current_index] = None
            
            scores = state.get('match_similarity_scores', [])
            if len(scores) <= current_index:
                scores.extend([0.0] * (current_index - len(scores) + 1))
            scores[current_index] = 0.0
            
            state['matched_components'] = matched
            state['match_similarity_scores'] = scores
            state['current_step'] = f'no_match_section_{current_index}'
            
    except Exception as e:
        # On error, assume no match
        matched = state.get('matched_components', [])
        if len(matched) <= current_index:
            matched.extend([None] * (current_index - len(matched) + 1))
        matched[current_index] = None
        
        scores = state.get('match_similarity_scores', [])
        if len(scores) <= current_index:
            scores.extend([0.0] * (current_index - len(scores) + 1))
        scores[current_index] = 0.0
        
        state['matched_components'] = matched
        state['match_similarity_scores'] = scores
        state['current_step'] = f'match_error_section_{current_index}'
    
    return state


def generate_html(state: ComponentGenerationState) -> ComponentGenerationState:
    """
    Generate HTML from Figma screenshot using Claude AI
    Uses training data context if available
    Handles retries with improved prompts for better accuracy
    """
    current_index = state.get('current_section_index', 0)
    screenshot_paths = state.get('screenshot_paths', [])
    matched_components = state.get('matched_components', [])
    html_match_scores = state.get('html_match_scores', [])
    html_retry_count = state.get('html_retry_count', [])
    
    if current_index >= len(screenshot_paths):
        state['status'] = 'error'
        state['error'] = f"No screenshot for section {current_index}"
        return state
    
    screenshot_path = screenshot_paths[current_index]
    matched = matched_components[current_index] if current_index < len(matched_components) else None
    
    # Get retry count for this section
    current_retry = 0
    if len(html_retry_count) > current_index:
        current_retry = html_retry_count[current_index]
    
    # Get previous match score if this is a retry
    previous_score = None
    if len(html_match_scores) > current_index and current_retry > 0:
        previous_score = html_match_scores[current_index]
    
    try:
        claude_client = ClaudeClient()  # Initialize with token from state/session
        
        # Prepare prompt with training data context if match found
        prompt_context = ""
        if matched:
            # Use matched component structure as reference
            prompt_context = f"Use the structure from matched component: {matched.get('name', 'Unknown')}"
        
        # If this is a retry, improve the prompt
        if current_retry > 0:
            if previous_score is not None:
                prompt_context += f"\n\nPrevious attempt achieved {previous_score:.1%} similarity. Please pay closer attention to:"
                prompt_context += "\n- Exact layout and spacing"
                prompt_context += "\n- Font sizes and weights"
                prompt_context += "\n- Colors and styling details"
                prompt_context += "\n- Image positioning and sizing"
                prompt_context += "\n- Text alignment and formatting"
            else:
                prompt_context += "\n\nThis is a retry attempt. Please ensure the HTML closely matches the design with precise styling, layout, and visual elements."
        
        # Generate HTML
        html_content = claude_client.generate_html_from_image(
            image_path=screenshot_path,
            additional_context=prompt_context
        )
        
        # Update HTML contents list
        html_contents = state.get('html_contents', [])
        if len(html_contents) <= current_index:
            html_contents.extend([''] * (current_index - len(html_contents) + 1))
        html_contents[current_index] = html_content
        
        state['html_contents'] = html_contents
        
        if current_retry > 0:
            state['current_step'] = f'html_regenerated_section_{current_index}_retry_{current_retry}'
        else:
            state['current_step'] = f'html_generated_section_{current_index}'
        
    except Exception as e:
        state['status'] = 'error'
        state['error'] = f"Error generating HTML: {str(e)}"
        state['current_step'] = f'html_error_section_{current_index}'
    
    return state


def verify_html_match(state: ComponentGenerationState) -> ComponentGenerationState:
    """
    Verify if generated HTML matches the Figma screenshot
    Renders HTML to image and compares with original screenshot using visual similarity
    If match < 95%, triggers retry (up to 3 attempts)
    """
    current_index = state.get('current_section_index', 0)
    screenshot_paths = state.get('screenshot_paths', [])
    html_contents = state.get('html_contents', [])
    max_retries = 3  # Maximum number of retry attempts
    
    if current_index >= len(screenshot_paths) or current_index >= len(html_contents):
        # Skip verification if no screenshot or HTML
        state['html_match_scores'] = state.get('html_match_scores', []) + [0.0]
        state['html_verified'] = state.get('html_verified', []) + [False]
        state['html_retry_count'] = state.get('html_retry_count', []) + [0]
        return state
    
    screenshot_path = screenshot_paths[current_index]
    html_content = html_contents[current_index]
    
    # Get current retry count for this section
    retry_counts = state.get('html_retry_count', [])
    if len(retry_counts) <= current_index:
        retry_counts.extend([0] * (current_index - len(retry_counts) + 1))
    current_retry_count = retry_counts[current_index]
    
    try:
        from utils.matching import compare_html_with_screenshot
        
        # Compare generated HTML with Figma screenshot
        similarity_score, is_match = compare_html_with_screenshot(
            html_content=html_content,
            screenshot_path=screenshot_path,
            match_threshold=0.95  # 95% similarity for 100% match
        )
        
        # Update match scores and verification status
        scores = state.get('html_match_scores', [])
        if len(scores) <= current_index:
            scores.extend([0.0] * (current_index - len(scores) + 1))
        scores[current_index] = similarity_score
        
        verified = state.get('html_verified', [])
        if len(verified) <= current_index:
            verified.extend([False] * (current_index - len(verified) + 1))
        verified[current_index] = is_match
        
        state['html_match_scores'] = scores
        state['html_verified'] = verified
        state['html_retry_count'] = retry_counts
        
        if is_match:
            state['current_step'] = f'html_verified_match_section_{current_index}'
        else:
            # Check if we should retry
            if current_retry_count < max_retries:
                # Mark for retry - will trigger regeneration
                state['needs_retry'] = True
                state['retry_section_index'] = current_index
                state['current_step'] = f'html_retry_needed_section_{current_index}_attempt_{current_retry_count + 1}'
                state['warnings'] = state.get('warnings', []) + [
                    f"Section {current_index}: HTML similarity {similarity_score:.2%} is below 95% threshold. Retrying generation (attempt {current_retry_count + 1}/{max_retries})..."
                ]
            else:
                # Max retries reached, continue with warning
                state['needs_retry'] = False
                state['current_step'] = f'html_verified_low_match_section_{current_index}_max_retries'
                state['warnings'] = state.get('warnings', []) + [
                    f"Section {current_index}: HTML similarity {similarity_score:.2%} is below 95% threshold after {max_retries} retries. Continuing with generated HTML."
                ]
        
    except Exception as e:
        # On error, assume not verified but continue
        scores = state.get('html_match_scores', [])
        if len(scores) <= current_index:
            scores.extend([0.0] * (current_index - len(scores) + 1))
        scores[current_index] = 0.0
        
        verified = state.get('html_verified', [])
        if len(verified) <= current_index:
            verified.extend([False] * (current_index - len(verified) + 1))
        verified[current_index] = False
        
        state['html_match_scores'] = scores
        state['html_verified'] = verified
        state['html_retry_count'] = retry_counts
        state['current_step'] = f'html_verification_error_section_{current_index}'
    
    return state


def extract_structure(state: ComponentGenerationState) -> ComponentGenerationState:
    """
    Extract structure from HTML or use matched component structure
    Parses HTML to find elements (headings, images, text blocks)
    """
    current_index = state.get('current_section_index', 0)
    matched_components = state.get('matched_components', [])
    html_contents = state.get('html_contents', [])
    
    matched = matched_components[current_index] if current_index < len(matched_components) else None
    
    try:
        if matched and matched.get('config_json'):
            # Use matched component structure
            structure = {
                'source': 'matched',
                'component_id': matched.get('component_id'),
                'config_json': matched.get('config_json'),
                'format_json': matched.get('format_json'),
                'records_json': matched.get('records_json')
            }
        else:
            # Extract from HTML
            from bs4 import BeautifulSoup
            html_content = html_contents[current_index] if current_index < len(html_contents) else ''
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Extract structure
            headings = [h.get_text() for h in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])]
            images = [img.get('src', '') for img in soup.find_all('img')]
            text_blocks = [p.get_text() for p in soup.find_all('p')]
            
            structure = {
                'source': 'generated',
                'headings': headings,
                'images': images,
                'text_blocks': text_blocks,
                'html': html_content
            }
        
        # Store structure (will be used in create_definitions)
        if 'extracted_structures' not in state:
            state['extracted_structures'] = []
        structures = state['extracted_structures']
        if len(structures) <= current_index:
            structures.extend([{}] * (current_index - len(structures) + 1))
        structures[current_index] = structure
        
        state['extracted_structures'] = structures
        state['current_step'] = f'structure_extracted_section_{current_index}'
        
    except Exception as e:
        state['status'] = 'error'
        state['error'] = f"Error extracting structure: {str(e)}"
        state['current_step'] = f'structure_error_section_{current_index}'
    
    return state


def create_definitions(state: ComponentGenerationState) -> ComponentGenerationState:
    """
    Create CMS definitions from extracted structure
    Maps elements to ControlId (1=Text, 7=Image, etc.)
    """
    current_index = state.get('current_section_index', 0)
    extracted_structures = state.get('extracted_structures', [])
    
    if current_index >= len(extracted_structures):
        state['status'] = 'error'
        state['error'] = f"No structure for section {current_index}"
        return state
    
    structure = extracted_structures[current_index]
    
    try:
        if structure.get('source') == 'matched':
            # Use matched component definitions
            definitions = {
                'config_json': structure.get('config_json'),
                'format_json': structure.get('format_json'),
                'records_json': structure.get('records_json')
            }
        else:
            # Create definitions from extracted structure
            # TODO: Implement full definition creation logic
            # This is a placeholder - will be implemented in Phase 4
            definitions = {
                'config_json': {},  # Placeholder
                'format_json': {},  # Placeholder
                'records_json': {}  # Placeholder
            }
        
        # Store definitions (will be used in generate_json)
        if 'definitions' not in state:
            state['definitions'] = []
        defs_list = state['definitions']
        if len(defs_list) <= current_index:
            defs_list.extend([{}] * (current_index - len(defs_list) + 1))
        defs_list[current_index] = definitions
        
        state['definitions'] = defs_list
        state['current_step'] = f'definitions_created_section_{current_index}'
        
    except Exception as e:
        state['status'] = 'error'
        state['error'] = f"Error creating definitions: {str(e)}"
        state['current_step'] = f'definitions_error_section_{current_index}'
    
    return state


def generate_json(state: ComponentGenerationState) -> ComponentGenerationState:
    """
    Generate ComponentConfig.json, ComponentFormat.json, ComponentRecords.json
    Uses generator utility
    """
    current_index = state.get('current_section_index', 0)
    definitions = state.get('definitions', [])
    
    if current_index >= len(definitions):
        state['status'] = 'error'
        state['error'] = f"No definitions for section {current_index}"
        return state
    
    definition = definitions[current_index]
    
    try:
        # Generate JSON files using generator utility
        json_files = generate_component_json(definition)
        
        # Update JSON lists
        configs = state.get('component_configs', [])
        if len(configs) <= current_index:
            configs.extend([{}] * (current_index - len(configs) + 1))
        configs[current_index] = json_files.get('config', {})
        
        formats = state.get('component_formats', [])
        if len(formats) <= current_index:
            formats.extend([{}] * (current_index - len(formats) + 1))
        formats[current_index] = json_files.get('format', {})
        
        records = state.get('component_records', [])
        if len(records) <= current_index:
            records.extend([{}] * (current_index - len(records) + 1))
        records[current_index] = json_files.get('records', {})
        
        state['component_configs'] = configs
        state['component_formats'] = formats
        state['component_records'] = records
        state['current_step'] = f'json_generated_section_{current_index}'
        
    except Exception as e:
        state['status'] = 'error'
        state['error'] = f"Error generating JSON: {str(e)}"
        state['current_step'] = f'json_error_section_{current_index}'
    
    return state


def add_to_cms(state: ComponentGenerationState) -> ComponentGenerationState:
    """
    Add generated component to CMS using site details from project
    """
    current_index = state.get('current_section_index', 0)
    site_details = state.get('site_details', {})
    component_configs = state.get('component_configs', [])
    component_formats = state.get('component_formats', [])
    component_records = state.get('component_records', [])
    
    if current_index >= len(component_configs):
        state['status'] = 'error'
        state['error'] = f"No component config for section {current_index}"
        return state
    
    try:
        cms_client = CMSClient()  # Initialize with credentials from state/session
        
        # Add component to CMS
        cms_component_id = cms_client.add_component(
            config_json=component_configs[current_index],
            format_json=component_formats[current_index],
            records_json=component_records[current_index],
            site_url=site_details.get('target_site_url'),
            profile_alias=site_details.get('profile_alias'),
            site_id=site_details.get('site_id')
        )
        
        # Update CMS component IDs list
        cms_ids = state.get('cms_component_ids', [])
        if len(cms_ids) <= current_index:
            cms_ids.extend([''] * (current_index - len(cms_ids) + 1))
        cms_ids[current_index] = cms_component_id
        
        state['cms_component_ids'] = cms_ids
        state['current_step'] = f'added_to_cms_section_{current_index}'
        
    except Exception as e:
        state['status'] = 'error'
        state['error'] = f"Error adding to CMS: {str(e)}"
        state['current_step'] = f'cms_error_section_{current_index}'
    
    return state


def generate_final_report(state: ComponentGenerationState) -> Dict[str, Any]:
    """
    Generate final report with all verification and retry details
    """
    sections = state.get('sections', [])
    html_match_scores = state.get('html_match_scores', [])
    html_verified = state.get('html_verified', [])
    html_retry_count = state.get('html_retry_count', [])
    match_similarity_scores = state.get('match_similarity_scores', [])
    matched_components = state.get('matched_components', [])
    warnings = state.get('warnings', [])
    cms_component_ids = state.get('cms_component_ids', [])
    
    report = {
        'summary': {
            'total_sections': len(sections),
            'sections_processed': len([s for s in html_match_scores if s > 0]),
            'sections_verified': len([v for v in html_verified if v]),
            'total_retries': sum(html_retry_count) if html_retry_count else 0,
            'total_warnings': len(warnings),
            'components_added_to_cms': len([c for c in cms_component_ids if c])
        },
        'sections': []
    }
    
    # Generate detailed report for each section
    for i in range(len(sections)):
        section_report = {
            'section_index': i,
            'section_name': sections[i].get('name', f'Section {i + 1}') if i < len(sections) else f'Section {i + 1}',
            'library_matching': {
                'matched': matched_components[i] is not None if i < len(matched_components) else False,
                'similarity_score': match_similarity_scores[i] if i < len(match_similarity_scores) else 0.0,
                'matched_component_id': matched_components[i].get('component_id') if i < len(matched_components) and matched_components[i] else None,
                'matched_component_name': matched_components[i].get('name') if i < len(matched_components) and matched_components[i] else None
            },
            'html_generation': {
                'retry_count': html_retry_count[i] if i < len(html_retry_count) else 0,
                'final_similarity_score': html_match_scores[i] if i < len(html_match_scores) else 0.0,
                'verified': html_verified[i] if i < len(html_verified) else False,
                'verification_status': 'PASSED' if (i < len(html_verified) and html_verified[i]) else 'FAILED',
                'cms_component_id': cms_component_ids[i] if i < len(cms_component_ids) else None
            }
        }
        
        # Add retry history if retries occurred
        if section_report['html_generation']['retry_count'] > 0:
            section_report['html_generation']['retry_details'] = {
                'attempts': section_report['html_generation']['retry_count'] + 1,  # +1 for initial attempt
                'final_attempt_similarity': section_report['html_generation']['final_similarity_score'],
                'status': 'SUCCESS' if section_report['html_generation']['verified'] else 'MAX_RETRIES_REACHED'
            }
        
        report['sections'].append(section_report)
    
    # Add warnings if any
    if warnings:
        report['warnings'] = warnings
    
    return report


def update_project(state: ComponentGenerationState) -> ComponentGenerationState:
    """
    Update project with generated components
    Links components to training data if matched
    Generates final report with verification and retry details
    """
    project_id = state.get('project_id')
    
    # Generate final report
    final_report = generate_final_report(state)
    state['final_report'] = final_report
    
    # TODO: Implement project update logic
    # This will update the project JSON file with new components
    
    state['current_step'] = 'project_updated'
    
    # If multiple sections, increment index for next iteration
    if state.get('has_multiple_sections', False):
        current_index = state.get('current_section_index', 0)
        sections = state.get('sections', [])
        if current_index < len(sections) - 1:
            state['current_section_index'] = current_index + 1
        else:
            state['status'] = 'completed'
    else:
        state['status'] = 'completed'
    
    return state
