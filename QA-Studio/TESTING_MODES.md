# Testing Modes: Visual Regression vs UI Health Checks

## 🎯 Two Testing Modes

QA Studio now supports two distinct testing modes depending on whether you provide baseline images:

### Mode 1: 📸 Visual Regression Testing (with Figma baselines)
**When**: You upload baseline images from Figma designs  
**What it does**: Pixel-perfect comparison between current site and design mockups  
**Use case**: Ensure development matches approved designs exactly

### Mode 2: 🔍 UI Health Check (without baselines)  
**When**: No baseline images uploaded  
**What it does**: Checks for broken UI elements and responsiveness issues  
**Use case**: Quick check that site is functioning properly across devices

---

## 📸 Mode 1: Visual Regression Testing

### Setup
1. Export your Figma designs as PNG images
2. Name them appropriately:
   - `desktop_{url_slug}.png` (e.g., `desktop_homepage.png`)
   - `tablet_{url_slug}.png`
   - `mobile_{url_slug}.png`
3. Upload via the dashboard

### What It Tests
✅ Pixel-perfect comparison with Figma designs  
✅ Detects any visual differences > 1%  
✅ Generates diff images showing changes  
✅ Reports which specific pages/devices have differences  

### Results
- **Match**: Design implementation matches Figma perfectly
- **Difference**: X% visual difference detected
- **Diff Image**: Highlights exactly what changed

### Example Use Cases
- "Does my homepage match the approved Figma design?"
- "Did the developer implement the mobile design correctly?"
- "Have any visual regressions been introduced since last deploy?"

---

## 🔍 Mode 2: UI Health Check

### Setup
Simply run tests without uploading baseline images.

### What It Tests
✅ **Page Content**: Ensures pages have actual content (not blank/error pages)  
✅ **Broken Images**: Detects images with missing/invalid src attributes  
✅ **Horizontal Overflow**: Checks for content wider than viewport (causes horizontal scrolling)  
✅ **Viewport Meta Tag**: Ensures mobile-friendly viewport is set  
✅ **Navigation Elements**: Verifies navigation is accessible on all devices  
✅ **Viewport Dimensions**: Confirms correct viewport sizes for each device  
✅ **Responsive Behavior**: Tests that UI adapts appropriately to different screen sizes  

### Results
- **Pass**: No UI issues detected
- **Warning**: Minor issues that don't break functionality
- **Fail**: Critical issues found (broken elements, overflow, missing content)

### Issues Detected

#### 1. **Content Issues**
- No body element
- Very little content on page
- Main content not visible

#### 2. **Image Issues**
- Broken images (no src attribute)
- Images pointing to invalid URLs
- Missing alt text (accessibility)

#### 3. **Responsiveness Issues**
- Horizontal overflow (content wider than viewport)
- Missing viewport meta tag
- Incorrect viewport dimensions
- Elements not adapting to screen size

#### 4. **Navigation Issues**
- No navigation elements on mobile
- Hamburger menu not accessible
- Header/nav missing

### Example Use Cases
- "Is my site responsive on mobile?"
- "Are there any broken images?"
- "Does the site work properly on tablet?"
- "Is there any horizontal scrolling on mobile?"

---

## 🔄 How to Upload Baseline Images

### Via Dashboard UI

1. Open QA Studio dashboard
2. In the "Test Configuration" section, find "Upload Baseline Images"
3. Click "📤 Choose Figma Images"
4. Select PNG/JPG files from your computer
5. See file list update with selected files
6. Click "Run Tests"

The system will:
- Upload images to `static/reports/baselines/`
- Use them for visual regression testing
- Compare all future test runs against these baselines

### File Naming Convention

```
desktop_homepage.png          → Homepage desktop design
tablet_homepage.png           → Homepage tablet design  
mobile_homepage.png           → Homepage mobile design

desktop_products.png          → Products page desktop
tablet_products.png           → Products page tablet
mobile_products.png           → Products page mobile
```

**Pattern**: `{device}_{page}_{run_id}_viewport.png`

---

## 📊 Comparison: Visual Regression vs UI Health Check

| Feature | Visual Regression | UI Health Check |
|---------|------------------|-----------------|
| **Baseline Required** | ✅ Yes (Figma images) | ❌ No |
| **Pixel-Perfect** | ✅ Yes | ❌ No |
| **Detects Design Drift** | ✅ Yes | ❌ No |
| **Checks Broken UI** | ⚠️ Indirect | ✅ Yes |
| **Checks Responsiveness** | ⚠️ Limited | ✅ Yes |
| **Speed** | Slower (image comparison) | Faster (DOM checks) |
| **Use Case** | Design QA | Functional QA |

---

## 🎯 Recommended Workflow

### For New Features
1. **Design Phase**: Get Figma mockups approved
2. **Upload Baselines**: Add Figma exports to QA Studio
3. **Development**: Developers build the feature
4. **Visual Regression Test**: Ensure implementation matches design
5. **Fix Differences**: Iterate until pixel-perfect
6. **UI Health Check**: Run without baselines to verify responsiveness

### For Existing Sites
1. **Initial Audit**: Run UI Health Check (no baselines)
2. **Fix Issues**: Address any broken UI or responsiveness problems
3. **Create Baselines**: Take screenshots of "correct" state
4. **Ongoing Testing**: Use baselines to catch visual regressions

### For Maintenance
1. **Before Deploy**: Run visual regression to catch unintended changes
2. **After Deploy**: Run UI health check to ensure nothing broke
3. **Update Baselines**: When designs intentionally change

---

## 🔧 API Endpoints

### Upload Baselines
```http
POST /api/baselines/upload
Content-Type: multipart/form-data

files: [image1.png, image2.png, ...]
```

**Response**:
```json
{
  "success": true,
  "uploaded": 3,
  "message": "Uploaded 3 baseline image(s)",
  "errors": []
}
```

### List Baselines
```http
GET /api/baselines/list
```

**Response**:
```json
{
  "success": true,
  "count": 3,
  "baselines": [
    {
      "filename": "desktop_homepage.png",
      "url": "/static/reports/baselines/desktop_homepage.png",
      "size": 1234567
    }
  ]
}
```

---

## 💡 Best Practices

### Baseline Images
1. **Export at correct resolutions**:
   - Desktop: 1920x1080 or 1440x900
   - Tablet: 1024x768 or 768x1024
   - Mobile: 375x667 or 414x896

2. **Use consistent naming**: Follow the `device_page.png` pattern

3. **Update when designs change**: Re-upload baselines after approved design updates

### Testing Strategy
1. **Run UI Health Checks frequently**: Quick smoke tests
2. **Run Visual Regression before deploys**: Catch unexpected changes
3. **Review differences manually**: Not all differences are bugs!

### Performance
- Limit URLs tested (use sitemap smartly)
- Run visual regression on critical pages only
- Use UI health checks for comprehensive coverage

---

## 🐛 Troubleshooting

### "No baselines found" but I uploaded them
- Check file names match expected pattern
- Verify files are in `static/reports/baselines/`
- Ensure files are PNG/JPG format

### False positives in visual regression
- Dynamic content (ads, dates) will always differ
- Animations captured at different frames
- Font rendering differences
- Solution: Use UI Health Check mode or mask dynamic areas

### UI Health Check passing but site looks broken
- Health checks are basic - they don't catch everything
- Use visual regression for comprehensive testing
- Manual QA still important!

---

## 📝 Summary

**With Baselines** → Pixel-perfect visual regression testing  
**Without Baselines** → UI health and responsiveness checks

Choose the mode that fits your needs, or use both for comprehensive testing!
