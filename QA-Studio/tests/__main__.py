"""
Allow running tests directory as a module: python -m tests
"""
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import and run the CLI runner
from run_tests import main

if __name__ == '__main__':
    # If no arguments provided, show help
    if len(sys.argv) == 1:
        sys.argv.extend(['--help'])
    
    main()
