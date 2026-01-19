# Visual Regression Testing Guide

## 📊 Understanding Baselines vs Test Reports

### Baseline Screenshots
- **Purpose**: Reference images representing the "correct" state of your website
- **Created**: First test run OR manually updated
- **Location**: `static/reports/baselines/`
- **Stability**: Don't change unless intentionally updated

### Test Run Reports
- **Purpose**: Current test results to compare against baselines
- **Created**: Every test run
- **Location**: `static/reports/{timestamp}/`
- **Content**: Screenshots, comparison results, logs

---

## 🔍 How Visual Regression Works

### 1. First Run (Baseline Creation)
```
Run Tests → No baselines exist → Creates baselines
Result: "✨ Baseline Creation Run"
```

### 2. Subsequent Runs (Comparison)
```
Run Tests → Compare with baselines → Report differences
Result: "✅ All match" OR "⚠️ X differences detected"
```

### 3. Comparison Algorithm
- Pixel-by-pixel comparison using PIL (Python Imaging Library)
- Calculates difference percentage
- Threshold: 0.01 (1% difference)
- Generates diff images if differences found

---

## 📈 Viewing Comparison Results

### In the Report Page (`/reports/{run_id}`)

**🔍 Visual Regression Results Section** shows:

1. **Overall Status**
   - "Baseline Creation Run" (first run)
   - "X/Y matches" (comparison run)
   - "✅ All match" or "⚠️ Differences detected"

2. **Detailed Comparison** (expandable)
   - Per-device results (Desktop, Tablet, Mobile)
   - Per-URL results
   - Difference percentage for each comparison

3. **Update Baselines Button** (if not baseline run)
   - Click to replace baselines with current screenshots
   - Use when changes are intentional

### Visual Regression Results JSON

Located at: `static/reports/{run_id}/visual_regression_results.json`

```json
{
  "comparisons": [
    {
      "device": "desktop",
      "url": "http://example.com/",
      "match": true,
      "is_baseline": false,
      "difference": 0.0,
      "baseline_path": "path/to/baseline.png",
      "actual_path": "path/to/current.png",
      "diff_path": null
    }
  ]
}
```

---

## 🔄 Updating Baselines

### When to Update Baselines

✅ **You SHOULD update when:**
- Intentional design changes
- New features added
- Fixed visual bugs (and want to keep the fix)
- Layout improvements

❌ **You SHOULD NOT update when:**
- Unintentional visual changes
- Suspected bugs
- Investigating visual regressions
- Unclear what caused the change

### How to Update Baselines

**Method 1: Via Report Page**
1. Open the test run report: `/reports/{run_id}`
2. Review the "Visual Regression Results" section
3. Click "🔄 Update Baselines with These Screenshots"
4. Confirm the action

**Method 2: Via API**
```bash
POST /api/baselines/update/{run_id}
```

**What happens:**
- Copies all screenshots from test run to `baselines/`
- Overwrites existing baselines
- Future runs will compare against these new baselines

---

## 🎯 Workflow Example

### Scenario: Homepage Design Update

1. **Initial State** (Jan 1)
   ```
   Run tests → Creates baseline (blue button)
   Location: static/reports/baselines/
   ```

2. **Development** (Jan 15)
   ```
   Designer changes button to green
   ```

3. **Test Run** (Jan 15)
   ```
   Run tests → Compares with baseline
   Result: ⚠️ 3 differences detected (all devices)
   Difference: Desktop 5.2%, Tablet 4.8%, Mobile 5.1%
   ```

4. **Review Results**
   ```
   Open report → See "Visual Regression Results"
   Check screenshots → Green button vs Blue baseline
   Decision: Change is intentional ✓
   ```

5. **Update Baseline** (Jan 15)
   ```
   Click "Update Baselines" button
   Confirm action
   Result: ✅ Updated 3 baseline screenshots
   ```

6. **Future Runs** (Jan 20+)
   ```
   Run tests → Compares with NEW baseline (green button)
   Result: ✅ All screenshots match baselines
   ```

---

## 📁 File Structure

```
static/reports/
├── baselines/                          # Reference screenshots
│   ├── desktop_example.com_viewport.png
│   ├── tablet_example.com_viewport.png
│   └── mobile_example.com_viewport.png
│
└── 20260118_171100/                    # Test run
    ├── screenshots/
    │   ├── desktop_example.com_20260118_171100_viewport.png
    │   ├── tablet_example.com_20260118_171100_viewport.png
    │   └── mobile_example.com_20260118_171100_viewport.png
    ├── visual_regression_results.json
    └── logs/
```

---

## 🛠️ API Endpoints

### View Report
```
GET /reports/{run_id}
```
Opens HTML page with visual regression results and update button

### Get Screenshots List
```
GET /api/run/{run_id}/screenshots
```
Returns JSON array of screenshot filenames

### Update Baselines
```
POST /api/baselines/update/{run_id}
```
Copies screenshots from run to baselines folder

### Delete Run
```
DELETE /api/runs/{run_id}
```
Removes test run directory

---

## 💡 Best Practices

1. **Keep Baselines Up to Date**
   - Update after approved design changes
   - Document when and why baselines were updated

2. **Review Before Updating**
   - Always check what changed before updating baselines
   - Look at difference percentages
   - View screenshots side-by-side

3. **Don't Update Blindly**
   - If you see unexpected differences, investigate first
   - Could be a real bug!

4. **Test Across Devices**
   - Always test Desktop, Tablet, and Mobile
   - Visual regressions can be device-specific

5. **Regular Cleanup**
   - Delete old test runs to save space
   - Keep baselines and recent runs only

---

## 🔧 Troubleshooting

### "Baseline Creation Run" Every Time
- Baselines folder is missing or empty
- Screenshot filenames don't match expected pattern
- Check `static/reports/baselines/` exists

### False Positives (Differences When None Exist)
- Dynamic content (ads, dates, animations)
- Anti-aliasing differences
- Browser rendering variations
- Solution: Increase threshold or exclude dynamic elements

### No Comparison Results Shown
- `visual_regression_results.json` missing
- Test didn't complete successfully
- Check logs for errors

---

## 📝 Summary

**Baselines** = The "correct" reference images
**Test Reports** = Current test results
**Visual Regression** = Comparing test vs baseline
**Update Baselines** = Make current test the new reference

Always review changes before updating baselines!
