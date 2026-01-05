"""
Component matching utilities using vector similarity
Finds similar components in training library using pgvector
"""
from typing import List, Dict, Any, Optional, Tuple
import os


def find_similar_components(
    screenshot_path: str,
    similarity_threshold: float = 0.85,
    limit: int = 5
) -> List[Dict[str, Any]]:
    """
    Find similar components in training library using vector similarity
    
    Args:
        screenshot_path: Path to Figma screenshot
        similarity_threshold: Minimum similarity score (0.0-1.0)
        limit: Maximum number of results to return
        
    Returns:
        List of matched components with similarity scores
    """
    # TODO: Phase 3 - Implement vector similarity search
    # 1. Generate CLIP embedding for screenshot
    # 2. Query PostgreSQL with pgvector: ORDER BY embedding <=> %s LIMIT %s
    # 3. Filter by similarity_threshold
    # 4. Return matched components with scores
    
    # Placeholder implementation
    return []


def generate_embedding(image_path: str) -> Optional[List[float]]:
    """
    Generate vector embedding for an image using CLIP
    
    Args:
        image_path: Path to image file
        
    Returns:
        Embedding vector (512 dimensions) or None if error
    """
    # TODO: Phase 3 - Implement CLIP embedding generation
    # Use CLIP model to generate embedding
    # Return as list of floats
    
    return None


def compare_html_with_screenshot(
    html_content: str,
    screenshot_path: str,
    match_threshold: float = 0.95
) -> Tuple[float, bool]:
    """
    Compare generated HTML (rendered as image) with Figma screenshot
    Uses visual similarity to determine if HTML matches the design
    
    Args:
        html_content: Generated HTML content
        screenshot_path: Path to original Figma screenshot
        match_threshold: Minimum similarity score for 100% match (default 0.95 = 95%)
        
    Returns:
        Tuple of (similarity_score: float, is_match: bool)
        - similarity_score: 0.0 to 1.0 (0% to 100% similarity)
        - is_match: True if similarity >= match_threshold
    """
    try:
        from PIL import Image
        import imagehash
        import os
        import tempfile
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.chrome.service import Service
        
        # Method 1: Render HTML to image and compare visually
        # Step 1: Render HTML to image
        html_image_path = _render_html_to_image(html_content)
        
        if not html_image_path or not os.path.exists(html_image_path):
            return 0.0, False
        
        # Step 2: Compare images using multiple methods
        similarity_score = _compare_images_visual(
            image1_path=html_image_path,
            image2_path=screenshot_path
        )
        
        # Cleanup temporary HTML image
        try:
            if os.path.exists(html_image_path):
                os.remove(html_image_path)
        except:
            pass
        
        # Step 3: Determine if it's a match
        is_match = similarity_score >= match_threshold
        
        return similarity_score, is_match
        
    except Exception as e:
        # Fallback: Use simple hash comparison
        try:
            similarity_score = _compare_images_hash(
                image1_path=_render_html_to_image(html_content),
                image2_path=screenshot_path
            )
            is_match = similarity_score >= match_threshold
            return similarity_score, is_match
        except:
            return 0.0, False


def _render_html_to_image(html_content: str) -> Optional[str]:
    """
    Render HTML content to an image file
    
    Args:
        html_content: HTML string to render
        
    Returns:
        Path to rendered image file or None if error
    """
    try:
        import tempfile
        import os
        
        # Create temporary HTML file
        temp_html = tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False)
        temp_html.write(f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ margin: 0; padding: 0; }}
                img {{ max-width: 100%; height: auto; }}
            </style>
        </head>
        <body>
            {html_content}
        </body>
        </html>
        """)
        temp_html.close()
        
        # Render HTML to image using headless browser
        # TODO: Implement using Selenium or Playwright
        # For now, return None (will use hash comparison as fallback)
        
        # Cleanup
        try:
            os.remove(temp_html.name)
        except:
            pass
        
        return None
        
    except Exception as e:
        return None


def _compare_images_visual(image1_path: str, image2_path: str) -> float:
    """
    Compare two images using visual similarity methods
    Combines multiple comparison techniques for accuracy
    
    Args:
        image1_path: Path to first image (rendered HTML)
        image2_path: Path to second image (Figma screenshot)
        
    Returns:
        Similarity score between 0.0 and 1.0
    """
    try:
        from PIL import Image
        import imagehash
        import numpy as np
        from skimage.metrics import structural_similarity as ssim
        
        # Load images
        img1 = Image.open(image1_path)
        img2 = Image.open(image2_path)
        
        # Resize to same dimensions for comparison
        img1 = img1.resize((800, 600), Image.Resampling.LANCZOS)
        img2 = img2.resize((800, 600), Image.Resampling.LANCZOS)
        
        # Method 1: Perceptual Hash (fast, good for exact matches)
        hash1 = imagehash.phash(img1)
        hash2 = imagehash.phash(img2)
        hash_similarity = 1.0 - (hash1 - hash2) / len(hash1.hash) ** 2
        
        # Method 2: Structural Similarity Index (SSIM) - more accurate
        img1_array = np.array(img1.convert('L'))
        img2_array = np.array(img2.convert('L'))
        ssim_score = ssim(img1_array, img2_array, data_range=255)
        
        # Method 3: Average Hash (for quick comparison)
        avg_hash1 = imagehash.average_hash(img1)
        avg_hash2 = imagehash.average_hash(img2)
        avg_hash_similarity = 1.0 - (avg_hash1 - avg_hash2) / len(avg_hash1.hash) ** 2
        
        # Combine scores (weighted average)
        # SSIM is most accurate, so give it more weight
        combined_score = (
            ssim_score * 0.6 +           # 60% weight for SSIM
            hash_similarity * 0.25 +      # 25% weight for perceptual hash
            avg_hash_similarity * 0.15     # 15% weight for average hash
        )
        
        return max(0.0, min(1.0, combined_score))
        
    except Exception as e:
        # Fallback to hash comparison
        return _compare_images_hash(image1_path, image2_path)


def _compare_images_hash(image1_path: str, image2_path: str) -> float:
    """
    Compare two images using hash-based methods (faster but less accurate)
    
    Args:
        image1_path: Path to first image
        image2_path: Path to second image
        
    Returns:
        Similarity score between 0.0 and 1.0
    """
    try:
        from PIL import Image
        import imagehash
        
        img1 = Image.open(image1_path)
        img2 = Image.open(image2_path)
        
        # Resize to same dimensions
        img1 = img1.resize((800, 600), Image.Resampling.LANCZOS)
        img2 = img2.resize((800, 600), Image.Resampling.LANCZOS)
        
        # Calculate perceptual hash
        hash1 = imagehash.phash(img1)
        hash2 = imagehash.phash(img2)
        
        # Calculate similarity (0.0 to 1.0)
        hamming_distance = hash1 - hash2
        max_distance = len(hash1.hash) ** 2
        similarity = 1.0 - (hamming_distance / max_distance)
        
        return max(0.0, min(1.0, similarity))
        
    except Exception as e:
        return 0.0
