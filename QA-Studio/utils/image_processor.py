"""
Image processing utilities for visual regression testing.
Handles screenshot comparison, diff generation, and baseline management.
"""
import os
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
from PIL import Image, ImageChops, ImageStat
import json


class ImageProcessor:
    """Handles image comparison and diff generation for visual regression."""
    
    def __init__(self, reports_dir: str):
        """
        Initialize image processor.
        
        Args:
            reports_dir: Directory where reports and screenshots are stored
        """
        self.reports_dir = Path(reports_dir)
        self.screenshots_dir = self.reports_dir / 'screenshots'
        self.baselines_dir = self.reports_dir.parent / 'baselines'
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        self.baselines_dir.mkdir(parents=True, exist_ok=True)
    
    def compare_images(
        self,
        actual_path: str,
        baseline_path: Optional[str] = None,
        threshold: float = 0.01
    ) -> Dict[str, Any]:
        """
        Compare two images and generate diff if different.
        
        Args:
            actual_path: Path to the actual screenshot
            baseline_path: Path to baseline screenshot (optional)
            threshold: Difference threshold (0.0 to 1.0)
        
        Returns:
            Dictionary with comparison results
        """
        actual_img = Image.open(actual_path)
        actual_path_obj = Path(actual_path)
        
        # If no baseline provided, try to find it
        if baseline_path is None:
            baseline_path = self._get_baseline_path(actual_path_obj)
        
        # If baseline doesn't exist, check if we should auto-create it
        if not os.path.exists(baseline_path):
            # Check if there are any manually uploaded baselines (Figma images)
            # If baselines directory has files, don't auto-create (user wants manual control)
            # If baselines directory is empty, auto-create from first run
            has_uploaded_baselines = any(self.baselines_dir.glob('*.png'))
            
            if has_uploaded_baselines:
                # User has uploaded Figma images, but this specific baseline doesn't exist
                # Don't auto-create, return None
                return {
                    'match': None,
                    'is_baseline': False,
                    'difference': None,
                    'baseline_path': None,
                    'actual_path': actual_path,
                    'diff_path': None,
                    'message': 'No baseline image found for this device/URL - skipping visual regression comparison'
                }
            else:
                # No uploaded baselines exist - auto-create from first run
                self._save_baseline(actual_path, baseline_path)
                return {
                    'match': True,
                    'is_baseline': True,  # Mark as baseline creation
                    'difference': 0.0,
                    'baseline_path': str(baseline_path),
                    'actual_path': actual_path,
                    'diff_path': None,
                    'message': 'Baseline auto-created from first run (no Figma images uploaded)'
                }
        
        baseline_img = Image.open(baseline_path)
        
        # Resize if dimensions don't match
        if actual_img.size != baseline_img.size:
            baseline_img = baseline_img.resize(actual_img.size, Image.Resampling.LANCZOS)
        
        # Convert to RGB if needed
        if actual_img.mode != baseline_img.mode:
            if actual_img.mode == 'RGBA' and baseline_img.mode == 'RGB':
                actual_img = actual_img.convert('RGB')
            elif baseline_img.mode == 'RGBA' and actual_img.mode == 'RGB':
                baseline_img = baseline_img.convert('RGB')
            else:
                actual_img = actual_img.convert('RGB')
                baseline_img = baseline_img.convert('RGB')
        
        # Calculate difference
        diff = ImageChops.difference(actual_img, baseline_img)
        stat = ImageStat.Stat(diff)
        
        # Calculate difference percentage
        # Sum of all pixel differences / (width * height * max_pixel_value * channels)
        total_diff = sum(stat.sum)
        max_possible = actual_img.size[0] * actual_img.size[1] * 255 * len(stat.mean)
        difference_ratio = total_diff / max_possible if max_possible > 0 else 0.0
        
        match = difference_ratio <= threshold
        
        result = {
            'match': match,
            'is_baseline': False,
            'difference': round(difference_ratio * 100, 2),  # Percentage
            'baseline_path': str(baseline_path),
            'actual_path': actual_path,
            'diff_path': None,
            'threshold': threshold * 100,
            'dimensions': actual_img.size
        }
        
        # Generate diff image if not matching
        if not match:
            diff_path = self._generate_diff_image(
                actual_img, baseline_img, diff, actual_path_obj
            )
            result['diff_path'] = str(diff_path)
        
        return result
    
    def _get_baseline_path(self, actual_path: Path) -> Path:
        """Get the baseline path for a given screenshot."""
        # Extract device/viewport from filename
        # e.g., desktop_viewport.png -> baselines/desktop_viewport.png
        filename = actual_path.name
        return self.baselines_dir / filename
    
    def _save_baseline(self, source_path: str, baseline_path: Path):
        """Save a screenshot as baseline."""
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        source_img = Image.open(source_path)
        source_img.save(baseline_path)
    
    def _generate_diff_image(
        self,
        actual: Image.Image,
        baseline: Image.Image,
        diff: Image.Image,
        actual_path: Path
    ) -> Path:
        """Generate a visual diff image highlighting differences."""
        # Create a side-by-side comparison with diff
        width, height = actual.size
        
        # Create diff image (highlight differences in red)
        diff_highlight = diff.convert('RGB')
        diff_pixels = diff_highlight.load()
        for y in range(height):
            for x in range(width):
                r, g, b = diff_pixels[x, y]
                if r > 0 or g > 0 or b > 0:
                    # Highlight differences in red
                    diff_pixels[x, y] = (255, 0, 0)
        
        # Create composite image: baseline | actual | diff
        composite_width = width * 3
        composite = Image.new('RGB', (composite_width, height), (255, 255, 255))
        
        composite.paste(baseline, (0, 0))
        composite.paste(actual, (width, 0))
        composite.paste(diff_highlight, (width * 2, 0))
        
        # Save diff image
        diff_filename = actual_path.stem + '_diff.png'
        diff_path = self.screenshots_dir / diff_filename
        composite.save(diff_path)
        
        return diff_path
    
    def save_comparison_result(
        self,
        comparison_result: Dict[str, Any],
        device: str,
        url: str
    ):
        """Save comparison result to JSON file."""
        results_file = self.reports_dir / 'visual_regression_results.json'
        
        # Load existing results
        if results_file.exists():
            with open(results_file, 'r') as f:
                results = json.load(f)
        else:
            results = {'comparisons': []}
        
        # Add new result
        result_entry = {
            'device': device,
            'url': url,
            **comparison_result,
            'timestamp': str(Path(comparison_result['actual_path']).stat().st_mtime)
        }
        results['comparisons'].append(result_entry)
        
        # Save updated results
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)
    
    def get_comparison_summary(self) -> Dict[str, Any]:
        """Get summary of all visual regression comparisons."""
        results_file = self.reports_dir / 'visual_regression_results.json'
        
        if not results_file.exists():
            return {
                'total': 0,
                'matches': 0,
                'differences': 0,
                'baselines_created': 0
            }
        
        with open(results_file, 'r') as f:
            results = json.load(f)
        
        comparisons = results.get('comparisons', [])
        matches = sum(1 for c in comparisons if c.get('match', False))
        differences = sum(1 for c in comparisons if not c.get('match', False) and not c.get('is_baseline', False))
        baselines = sum(1 for c in comparisons if c.get('is_baseline', False))
        
        return {
            'total': len(comparisons),
            'matches': matches,
            'differences': differences,
            'baselines_created': baselines,
            'comparisons': comparisons
        }
