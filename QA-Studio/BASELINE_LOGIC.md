# Baseline Logic - Updated Implementation

## 🎯 Overview

The baseline system has been updated to match the correct workflow:

1. **Baselines are manually uploaded** (from Figma designs) - NOT auto-created
2. **If no baselines exist**, tests perform **UI health checks** instead of visual regression
3. **If baselines exist**, tests perform **visual regression comparison**

---

## 📤 Uploading Baselines

### Via Dashboard

1. **Go to Test Configuration** section
2. **Click "📤 Choose Figma Images"** button
3. **Select your baseline images** from Figma
4. **Name files correctly:**
   - `desktop_{url}.png` - Desktop viewport baseline
   - `tablet_{url}.png` - Tablet viewport baseline  
   - `mobile_{url}.png` - Mobile viewport baseline
5. **Run tests** - Baselines will be uploaded automatically before test execution

### File Naming Convention

For URL `http://example.com/`:
- `desktop_example.com_viewport.png`
- `tablet_example.com_viewport.png`
- `mobile_example.com_viewport.png`

The system will match baselines to test screenshots based on device type and URL pattern.

---

## 🔍 Two Testing Modes

### Mode 1: Visual Regression (Baselines Exist)

**When:** Baseline images have been uploaded

**What it does:**
- Takes screenshots of the website
- Compares pixel-by-pixel with uploaded Figma baselines
- Calculates difference percentage
- Generates diff images if differences found
- Reports visual regressions

**Result in Report:**
- ✅ "All screenshots match baselines perfectly!"
- ⚠️ "X visual difference(s) detected!"

---

### Mode 2: UI Health Check (No Baselines)

**When:** No baseline images uploaded

**What it does:**
- Takes screenshots of the website
- Performs UI health checks:
  1. **Viewport Meta Tag** - Checks for responsive meta tag
  2. **Horizontal Overflow** - Detects layout overflow issues
  3. **Critical Elements** - Verifies header, main, nav, footer exist
  4. **Broken Images** - Detects images that failed to load
  5. **Text Readability** - Flags very small text (< 10px)
- Reports UI issues found

**Result in Report:**
- ✅ "All UI health checks passed!"
- ⚠️ "X UI issue(s) detected!"

---

## 📊 Report Display

### Visual Regression Mode

```
🔍 Test Results
📊 Visual Regression Comparison
Comparing screenshots with uploaded Figma baseline images.

Comparison Results: 2/3 matches
⚠️ 1 visual difference(s) detected!

View Detailed Results:
  ✅ Desktop - http://example.com/
    Visual Match - Difference: 0.00%
  ⚠️ Tablet - http://example.com/
    Visual Difference - Difference: 5.23%
  ✅ Mobile - http://example.com/
    Visual Match - Difference: 0.00%
```

### UI Health Check Mode

```
🔍 Test Results
🔍 UI Health Check Mode
No baseline images were provided. Tests performed UI health checks 
instead of visual regression comparison.

Checks Performed:
  • Viewport meta tag validation
  • Responsive layout (horizontal overflow detection)
  • Critical elements visibility (header, main, nav, footer)
  • Broken image detection
  • Text readability (very small text detection)

✅ All UI health checks passed!

View Detailed Results:
  🔍 Desktop - http://example.com/
    UI Health Check - No baseline - UI checks performed
  🔍 Tablet - http://example.com/
    UI Health Check - No baseline - UI checks performed
  🔍 Mobile - http://example.com/
    UI Health Check - No baseline - UI checks performed
```

---

## 🔧 Technical Implementation

### Image Processor (`utils/image_processor.py`)

**Before (Old Logic):**
```python
# Auto-created baselines if missing
if not os.path.exists(baseline_path):
    self._save_baseline(actual_path, baseline_path)
    return {'is_baseline': True, ...}
```

**After (New Logic):**
```python
# Returns None if baseline missing
if not os.path.exists(baseline_path):
    return {
        'match': None,  # None = no baseline available
        'message': 'No baseline image found - skipping visual regression'
    }
```

### Test Logic (`tests/test_ui_responsiveness.py`)

**Checks for baseline existence:**
```python
comparison_result = image_processor.compare_images(...)

if comparison_result.get('match') is None:
    # No baseline - perform UI health checks
    # Check viewport meta, overflow, elements, images, text
else:
    # Baseline exists - perform visual regression
    # Compare pixels and report differences
```

---

## 📁 File Structure

```
static/reports/
├── baselines/                          # Manually uploaded Figma images
│   ├── desktop_example.com_viewport.png
│   ├── tablet_example.com_viewport.png
│   └── mobile_example.com_viewport.png
│
└── {run_id}/                           # Test run results
    ├── screenshots/
    │   ├── desktop_example.com_{run_id}_viewport.png
    │   ├── tablet_example.com_{run_id}_viewport.png
    │   └── mobile_example.com_{run_id}_viewport.png
    └── visual_regression_results.json
```

---

## 🎯 Workflow Examples

### Example 1: First Time Testing (No Baselines)

1. **Designer provides Figma designs** → Export as PNG
2. **Upload baselines** via dashboard
3. **Run tests** → Visual regression comparison
4. **Review results** → See if website matches Figma designs

### Example 2: Quick UI Check (No Baselines)

1. **Don't upload baselines**
2. **Run tests** → UI health checks only
3. **Review results** → See if any UI issues found
4. **No visual comparison** → Just functional/responsive checks

### Example 3: Regular Testing (With Baselines)

1. **Baselines already uploaded**
2. **Run tests** → Visual regression comparison
3. **Review results** → See if anything changed from baselines
4. **Update baselines** if changes are intentional

---

## ✅ Benefits

1. **Flexible Testing**
   - Can test without baselines (UI health checks)
   - Can test with baselines (visual regression)

2. **No Auto-Creation**
   - Baselines are intentional (from Figma)
   - No accidental baseline creation

3. **Clear Separation**
   - Visual regression = pixel-perfect comparison
   - UI health check = functional/responsive validation

4. **Better Reporting**
   - Clear indication of which mode was used
   - Appropriate results for each mode

---

## 🔄 Updating Baselines

If you want to update baselines after a test run:

1. **Open the test report** (`/reports/{run_id}`)
2. **Review the visual differences**
3. **If changes are intentional**, click **"🔄 Update Baselines"**
4. **Confirm** → Baselines updated with current screenshots

**Note:** Only available in Visual Regression mode (when baselines exist)

---

## 📝 Summary

- ✅ **Baselines = Manual upload** (from Figma)
- ✅ **No baselines = UI health checks** (responsive, broken elements, etc.)
- ✅ **With baselines = Visual regression** (pixel-perfect comparison)
- ✅ **Clear reporting** for both modes
