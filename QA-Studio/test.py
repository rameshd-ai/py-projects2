#!/usr/bin/env python
"""
Simple test runner - Quick way to run individual test files.
Usage: python test.py test_site_structure.py --base-url https://example.com
"""
import sys
import subprocess
from pathlib import Path

if __name__ == '__main__':
    # Get test file name from arguments
    if len(sys.argv) < 2:
        print("Usage: python test.py <test_file> [pytest_args...]")
        print("\nExamples:")
        print("  python test.py test_site_structure.py --base-url https://example.com")
        print("  python test.py test_ui_responsiveness.py --base-url https://example.com --browsers chromium firefox")
        print("  python test.py test_seo_metadata.py --base-url https://example.com --devices desktop mobile")
        sys.exit(1)
    
    test_file = sys.argv[1]
    
    # Check if test file exists
    test_path = Path('tests') / test_file
    if not test_path.exists():
        print(f"Error: Test file not found: {test_path}")
        print(f"Available test files:")
        for tf in Path('tests').glob('test_*.py'):
            print(f"  - {tf.name}")
        sys.exit(1)
    
    # Build pytest command
    pytest_cmd = ['pytest', str(test_path), '-v'] + sys.argv[2:]
    
    # Run pytest
    print(f"Running: {' '.join(pytest_cmd)}")
    print("=" * 80)
    sys.exit(subprocess.call(pytest_cmd))
