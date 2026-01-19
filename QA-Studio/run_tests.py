"""
QA Studio - Command Line Test Runner
Allows running tests directly from command line without the dashboard.
"""
import argparse
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='QA Studio - Run tests from command line',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all tests
  python run_tests.py --base-url https://example.com

  # Run specific test file
  python run_tests.py tests/test_site_structure.py --base-url https://example.com

  # Run specific pillar
  python run_tests.py --pillar 1 --base-url https://example.com

  # Run with specific browsers
  python run_tests.py --browsers chromium firefox --base-url https://example.com

  # Run with specific devices
  python run_tests.py --devices desktop mobile --base-url https://example.com
        """
    )
    
    # Required arguments
    parser.add_argument(
        '--base-url',
        required=True,
        help='Base URL to test (required)'
    )
    
    # Test selection
    parser.add_argument(
        'test_files',
        nargs='*',
        help='Specific test files to run (e.g., tests/test_site_structure.py)'
    )
    
    parser.add_argument(
        '--pillar',
        type=int,
        choices=[1, 2, 3, 4, 5, 6],
        help='Run tests for a specific pillar (1-6)'
    )
    
    # Configuration options
    parser.add_argument(
        '--sitemap-url',
        help='Sitemap URL (defaults to {base_url}/sitemap.xml)'
    )
    
    parser.add_argument(
        '--browsers',
        nargs='+',
        choices=['chromium', 'firefox', 'webkit'],
        default=['chromium'],
        help='Browsers to test (default: chromium)'
    )
    
    parser.add_argument(
        '--devices',
        nargs='+',
        choices=['desktop', 'tablet', 'mobile'],
        default=['desktop'],
        help='Devices to test (default: desktop)'
    )
    
    # Pytest options
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )
    
    parser.add_argument(
        '-s', '--no-capture',
        action='store_true',
        help='Don\'t capture output (show print statements)'
    )
    
    parser.add_argument(
        '--html-report',
        help='Generate HTML report (requires pytest-html)'
    )
    
    parser.add_argument(
        '--junit-xml',
        help='Generate JUnit XML report'
    )
    
    args = parser.parse_args()
    
    # Build pytest command
    pytest_args = ['pytest']
    
    # Add verbosity
    if args.verbose:
        pytest_args.append('-v')
    else:
        pytest_args.append('-q')
    
    # Add output capture
    if args.no_capture:
        pytest_args.append('-s')
    
    # Add custom options
    pytest_args.extend([
        f'--base-url={args.base_url}',
        f'--browsers={",".join(args.browsers)}',
        f'--devices={",".join(args.devices)}'
    ])
    
    if args.sitemap_url:
        pytest_args.append(f'--sitemap-url={args.sitemap_url}')
    
    # Determine which tests to run
    if args.pillar:
        # Run specific pillar
        pillar_map = {
            1: 'tests/test_ui_responsiveness.py',
            2: 'tests/test_site_structure.py',
            3: 'tests/test_user_flows.py',
            4: 'tests/test_browser_health.py',
            5: 'tests/test_compatibility.py',
            6: 'tests/test_seo_metadata.py'
        }
        test_file = pillar_map.get(args.pillar)
        if test_file and os.path.exists(test_file):
            pytest_args.append(test_file)
        else:
            print(f"Error: Test file for pillar {args.pillar} not found: {test_file}")
            sys.exit(1)
    elif args.test_files:
        # Run specific test files
        for test_file in args.test_files:
            if not os.path.exists(test_file):
                print(f"Error: Test file not found: {test_file}")
                sys.exit(1)
            pytest_args.append(test_file)
    else:
        # Run all tests
        pytest_args.append('tests/')
    
    # Add reports
    if args.html_report:
        pytest_args.extend(['--html', args.html_report, '--self-contained-html'])
    
    if args.junit_xml:
        pytest_args.extend(['--junit-xml', args.junit_xml])
    
    # Generate run ID
    from datetime import datetime
    run_id = datetime.now().strftime('%Y%m%d_%H%M%S')
    pytest_args.append(f'--run-id={run_id}')
    
    # Add pillar selection (for filtering within test files)
    # Only add if we're running all tests or multiple test files
    if not args.pillar and not args.test_files:
        pytest_args.append('--pillars=1,2,3,4,5,6')
    elif args.pillar:
        pytest_args.append(f'--pillars={args.pillar}')
    
    # Print command
    print("=" * 80)
    print("QA Studio - Command Line Test Runner")
    print("=" * 80)
    print(f"Base URL: {args.base_url}")
    print(f"Browsers: {', '.join(args.browsers)}")
    print(f"Devices: {', '.join(args.devices)}")
    if args.pillar:
        print(f"Pillar: {args.pillar}")
    print(f"Run ID: {run_id}")
    print("=" * 80)
    print(f"Running: {' '.join(pytest_args)}")
    print("=" * 80)
    print()
    
    # Run pytest
    import pytest
    exit_code = pytest.main(pytest_args)
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
