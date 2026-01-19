# QA Studio

A Python-only web dashboard for automated quality assurance testing of web properties. QA Studio provides real-time test execution, comprehensive reporting, and validation across 6 core testing pillars.

## Features

- **Real-time Test Execution**: Monitor test progress via WebSockets
- **6 Testing Pillars**:
  1. Rendering & Responsiveness
  2. Site Architecture & Navigation
  3. Functional & Business Logic
  4. Console & Technical Checks
  5. Cross-Browser & Device Testing
  6. Content, SEO & Schema Validation
- **Multi-Browser Support**: Test with Chromium, Firefox, and WebKit
- **Device Emulation**: Desktop, Tablet, and Mobile viewports
- **Visual Regression**: Automated screenshot comparison
- **Comprehensive Reporting**: Detailed results with screenshots and logs

## Tech Stack

- **Flask**: Web framework
- **Flask-SocketIO**: Real-time communication
- **Playwright**: Browser automation
- **Pytest**: Test framework
- **Pydantic**: Configuration validation
- **BeautifulSoup4**: HTML parsing
- **Advertools**: Sitemap parsing

## Installation

### Quick Setup (Recommended)

**Windows:**
```bash
setup.bat
```

**Linux/Mac:**
```bash
chmod +x setup.sh
./setup.sh
```

**Or use Python setup script:**
```bash
python setup.py
```

### Manual Setup

1. Clone the repository:
```bash
git clone <repository-url>
cd QA-Studio
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Install Playwright browsers:
```bash
playwright install
```

> **Note:** The virtual environment folder (`venv/`) is excluded from git. Each developer needs to create their own. See `SETUP.md` for detailed instructions.

## Usage

### Method 1: Web Dashboard (Recommended for Full Test Runs)

1. Start the Flask server:
```bash
python app.py
```

2. Open your browser and navigate to:
```
http://localhost:5000
```

3. Configure your test run:
   - Enter the base URL to test
   - Select browsers (Chromium, Firefox, WebKit)
   - Select devices (Desktop, Tablet, Mobile)
   - Choose which test pillars to execute
   - Click "Run Tests"

4. Monitor the test execution in real-time:
   - Watch progress bars for each pillar
   - View live log output
   - See status updates as tests complete

5. Review results:
   - Check pillar-by-pillar breakdown
   - View screenshots and error logs
   - Download detailed reports

### Method 2: Command Line (For Individual Test Files)

#### Quick Test Runner
Run a specific test file directly:
```bash
# Run site structure tests
python test.py test_site_structure.py --base-url https://example.com

# Run with specific browsers
python test.py test_ui_responsiveness.py --base-url https://example.com --browsers chromium firefox

# Run with specific devices
python test.py test_seo_metadata.py --base-url https://example.com --devices desktop mobile
```

#### Full CLI Runner
Use the comprehensive CLI runner for more control:
```bash
# Run all tests
python run_tests.py --base-url https://example.com

# Run specific test file
python run_tests.py tests/test_site_structure.py --base-url https://example.com

# Run specific pillar (1-6)
python run_tests.py --pillar 2 --base-url https://example.com

# Run with multiple browsers and devices
python run_tests.py --base-url https://example.com --browsers chromium firefox --devices desktop tablet mobile

# Generate HTML report
python run_tests.py --base-url https://example.com --html-report report.html
```

#### Direct Pytest (Advanced)
You can also run pytest directly:
```bash
# Run specific test file
pytest tests/test_site_structure.py --base-url https://example.com -v

# Run all tests
pytest tests/ --base-url https://example.com -v

# Run with specific options
pytest tests/test_ui_responsiveness.py --base-url https://example.com --browsers chromium,firefox --devices desktop,mobile
```

## Project Structure

```
QA-STUDIO/
├── app.py                      # Flask server & SocketIO manager
├── requirements.txt            # Dependencies
├── templates/
│   └── index.html              # Dashboard UI
├── static/
│   ├── css/                    # Styles
│   ├── js/                     # Client-side logic
│   └── reports/                # Test results
├── utils/                      # Utility modules
│   ├── config_models.py        # Configuration models
│   ├── report_models.py        # Report models
│   ├── error_models.py         # Error models
│   └── background_runner.py    # Test execution
└── tests/                      # Test suite
    ├── conftest.py             # Pytest configuration
    ├── test_ui_responsiveness.py
    ├── test_site_structure.py
    ├── test_user_flows.py
    ├── test_browser_health.py
    ├── test_compatibility.py
    └── test_seo_metadata.py
```

## Test Files Reference

| Test File | Pillar | Description |
|-----------|--------|-------------|
| `tests/test_ui_responsiveness.py` | 1 | Rendering & Responsiveness |
| `tests/test_site_structure.py` | 2 | Site Architecture & Navigation |
| `tests/test_user_flows.py` | 3 | Functional & Business Logic |
| `tests/test_browser_health.py` | 4 | Console & Technical Checks |
| `tests/test_compatibility.py` | 5 | Cross-Browser & Device Testing |
| `tests/test_seo_metadata.py` | 6 | Content, SEO & Schema Validation |

## Development Status

**Phase 0: Core Engine** ✅ Complete
- Flask server with SocketIO
- Background test execution
- Real-time log streaming
- Dashboard UI
- Command-line test runner

**Phase 1-6: Test Pillars** 🚧 In Progress
- Basic test implementations created
- Full feature implementation pending

## License

MIT
