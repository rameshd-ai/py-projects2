# QA Studio - Quick Start Guide

## Two Ways to Run Tests

### 🖥️ Method 1: Web Dashboard (Full Control)

Perfect for running comprehensive test suites with real-time monitoring.

```bash
# Start the server
python app.py

# Open browser to http://localhost:5000
# Configure and run tests through the UI
```

**Features:**
- Real-time progress bars
- Live log streaming
- Visual results dashboard
- Run history
- Screenshot gallery

---

### 💻 Method 2: Command Line (Quick & Direct)

Perfect for running individual test files or specific pillars.

#### Option A: Quick Test Runner (Simplest)
```bash
# Run a specific test file
python test.py test_site_structure.py --base-url https://example.com

# Run with options
python test.py test_ui_responsiveness.py --base-url https://example.com --browsers chromium firefox
```

#### Option B: Full CLI Runner (Most Control)
```bash
# Run all tests
python run_tests.py --base-url https://example.com

# Run specific test file
python run_tests.py tests/test_site_structure.py --base-url https://example.com

# Run specific pillar (1-6)
python run_tests.py --pillar 2 --base-url https://example.com

# Run with multiple browsers
python run_tests.py --base-url https://example.com --browsers chromium firefox webkit

# Run with multiple devices
python run_tests.py --base-url https://example.com --devices desktop tablet mobile
```

#### Option C: Direct Pytest (Advanced)
```bash
# Run specific test file
pytest tests/test_site_structure.py --base-url https://example.com -v

# Run all tests
pytest tests/ --base-url https://example.com -v
```

---

## Test Files Quick Reference

| Command | What It Does |
|---------|-------------|
| `python test.py test_site_structure.py --base-url https://example.com` | Run site structure tests |
| `python test.py test_ui_responsiveness.py --base-url https://example.com` | Run UI/responsiveness tests |
| `python test.py test_user_flows.py --base-url https://example.com` | Run user flow tests |
| `python test.py test_browser_health.py --base-url https://example.com` | Run browser health checks |
| `python test.py test_compatibility.py --base-url https://example.com` | Run cross-browser tests |
| `python test.py test_seo_metadata.py --base-url https://example.com` | Run SEO validation tests |

---

## Common Use Cases

### Run Just One Pillar
```bash
python run_tests.py --pillar 2 --base-url https://example.com
```

### Test on Multiple Browsers
```bash
python run_tests.py tests/test_compatibility.py --base-url https://example.com --browsers chromium firefox webkit
```

### Test on Multiple Devices
```bash
python run_tests.py tests/test_ui_responsiveness.py --base-url https://example.com --devices desktop tablet mobile
```

### Generate HTML Report
```bash
python run_tests.py --base-url https://example.com --html-report report.html
```

### Verbose Output
```bash
python run_tests.py --base-url https://example.com -v
```

---

## Dashboard: Running Individual Modules

In the dashboard, you can select specific pillars to run:

1. Open the dashboard at `http://localhost:5000`
2. In the "Test Pillars" section, **uncheck** the pillars you don't want to run
3. Only the checked pillars will execute
4. Each pillar corresponds to a test file:
   - Pillar 1 → `test_ui_responsiveness.py`
   - Pillar 2 → `test_site_structure.py`
   - Pillar 3 → `test_user_flows.py`
   - Pillar 4 → `test_browser_health.py`
   - Pillar 5 → `test_compatibility.py`
   - Pillar 6 → `test_seo_metadata.py`

---

## Tips

- **Quick testing**: Use `test.py` for fastest execution
- **Full control**: Use `run_tests.py` for advanced options
- **Monitoring**: Use dashboard for real-time progress
- **CI/CD**: Use `run_tests.py` with `--junit-xml` for integration
