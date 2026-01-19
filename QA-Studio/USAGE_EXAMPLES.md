# QA Studio - Usage Examples

## Overview

QA Studio supports **two ways** to run tests:

1. **Web Dashboard** - Full-featured UI with real-time monitoring
2. **Command Line** - Quick execution of individual test files

Both methods support running individual modules/pillars.

---

## Method 1: Web Dashboard

### Running All Tests
1. Start server: `python app.py`
2. Open `http://localhost:5000`
3. Fill in base URL
4. Keep all 6 pillars checked
5. Click "Run Tests"

### Running Individual Modules
1. Start server: `python app.py`
2. Open `http://localhost:5000`
3. Fill in base URL
4. **Uncheck** the pillars you don't want to run
   - Example: Only check "2. Site Architecture & Navigation" to run just `test_site_structure.py`
5. Click "Run Tests"

### Example: Run Only Site Structure Tests
- ✅ Check: Pillar 2 (Site Architecture & Navigation)
- ❌ Uncheck: Pillars 1, 3, 4, 5, 6
- Result: Only `tests/test_site_structure.py` runs

---

## Method 2: Command Line

### Quick Test Runner (Simplest)

Run a specific test file directly:

```bash
# Run site structure tests
python test.py test_site_structure.py --base-url https://example.com

# Run UI responsiveness tests
python test.py test_ui_responsiveness.py --base-url https://example.com

# Run SEO tests
python test.py test_seo_metadata.py --base-url https://example.com
```

### Full CLI Runner (More Options)

```bash
# Run specific test file
python run_tests.py tests/test_site_structure.py --base-url https://example.com

# Run by pillar number (1-6)
python run_tests.py --pillar 2 --base-url https://example.com

# Run with specific browsers
python run_tests.py tests/test_compatibility.py --base-url https://example.com --browsers chromium firefox

# Run with specific devices
python run_tests.py tests/test_ui_responsiveness.py --base-url https://example.com --devices desktop mobile
```

### Direct Pytest (Advanced)

```bash
# Run specific test file
pytest tests/test_site_structure.py --base-url https://example.com -v

# Run all tests in a file
pytest tests/test_site_structure.py::test_sitemap_exists --base-url https://example.com -v
```

---

## Test File to Pillar Mapping

| Pillar | Test File | Description |
|--------|-----------|-------------|
| 1 | `test_ui_responsiveness.py` | Rendering & Responsiveness |
| 2 | `test_site_structure.py` | Site Architecture & Navigation |
| 3 | `test_user_flows.py` | Functional & Business Logic |
| 4 | `test_browser_health.py` | Console & Technical Checks |
| 5 | `test_compatibility.py` | Cross-Browser & Device Testing |
| 6 | `test_seo_metadata.py` | Content, SEO & Schema Validation |

---

## Real-World Examples

### Example 1: Quick Site Structure Check
**Goal**: Just verify sitemap and links work

**Dashboard Method:**
- Check only Pillar 2
- Run tests

**CLI Method:**
```bash
python test.py test_site_structure.py --base-url https://example.com
```

---

### Example 2: Full SEO Audit
**Goal**: Complete SEO validation

**Dashboard Method:**
- Check only Pillar 6
- Run tests

**CLI Method:**
```bash
python test.py test_seo_metadata.py --base-url https://example.com
```

---

### Example 3: Cross-Browser Testing
**Goal**: Test UI on all browsers

**Dashboard Method:**
- Check Pillar 1 (UI) and Pillar 5 (Compatibility)
- Select all browsers
- Run tests

**CLI Method:**
```bash
python run_tests.py --pillar 1 --pillar 5 --base-url https://example.com --browsers chromium firefox webkit
```

---

### Example 4: Responsive Design Check
**Goal**: Verify mobile/tablet/desktop rendering

**Dashboard Method:**
- Check Pillar 1
- Select all devices
- Run tests

**CLI Method:**
```bash
python run_tests.py tests/test_ui_responsiveness.py --base-url https://example.com --devices desktop tablet mobile
```

---

## Comparison: Dashboard vs CLI

| Feature | Dashboard | CLI |
|---------|-----------|-----|
| Real-time progress | ✅ Yes | ❌ No |
| Live logs | ✅ Yes | ⚠️ Terminal output |
| Visual results | ✅ Yes | ❌ No |
| Quick execution | ⚠️ Setup required | ✅ Instant |
| CI/CD friendly | ❌ No | ✅ Yes |
| Individual modules | ✅ Checkboxes | ✅ Direct file |
| Screenshot gallery | ✅ Yes | ⚠️ Files only |

**Recommendation:**
- Use **Dashboard** for comprehensive runs and monitoring
- Use **CLI** for quick checks and automation

---

## Tips

1. **Quick checks**: Use `test.py` for fastest execution
2. **Full control**: Use `run_tests.py` for advanced options  
3. **Monitoring**: Use dashboard for real-time progress
4. **Automation**: Use CLI in scripts and CI/CD pipelines
5. **Debugging**: Use CLI with `-v` flag for verbose output
