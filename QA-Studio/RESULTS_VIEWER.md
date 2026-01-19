# Results Viewer Feature

## Overview
Added a **Results Viewer Modal** that shows test results with screenshots and links when you click on any run in the Run History.

**Note:** The `baselines` folder is now hidden from the Run History list but is still accessible through the results viewer popup via a "View Baseline Screenshots" button.

## What's New

### 1. Results Modal Popup
- Click on any run in the "Run History" section
- A modal popup appears showing:
  - Run ID and timestamp
  - Screenshot count
  - All screenshots from the test run (in a grid with device icons)
  - Click any screenshot to view full size
  - **Baseline Images Section** - Link to view reference baseline screenshots
  - Direct link to open the full report folder

### 2. Baselines Folder Hidden
- The `baselines` folder no longer appears in Run History
- Baselines are still accessible via the "View Baseline Screenshots" button in any results popup
- Keeps the history clean and focused on actual test runs

### 3. New API Endpoint
- **GET** `/api/run/{run_id}/screenshots`
- Returns list of all screenshots for a specific run
- Automatically filters for image files (.png, .jpg, .jpeg)

### 4. UI Improvements
- Screenshots displayed in a responsive grid (3 columns)
- Device type indicators (🖥️ Desktop, 📟 Tablet, 📱 Mobile)
- Click any screenshot to open full size in new tab
- Baseline images accessible via dedicated button
- Link to open full report directory
- Clean modal design with close button
- Error handling with fallback image placeholders

## How to Use

1. **Run a test** from the dashboard
2. **Wait for completion** (or minimize the progress modal)
3. **Go to Run History** section
4. **Click on any run** (e.g., "20260118_171100")
5. **View results** in the popup:
   - See all screenshots
   - Click screenshots to enlarge
   - Open full report folder

## Files Modified

### Frontend
- **templates/index.html**: Added results modal HTML structure
- **static/js/client.js**: 
  - Implemented `loadRun()` function to fetch and display results
  - Added `initializeResultsModal()` for event handlers
  - Integrated with existing click handlers

### Backend
- **app.py**: 
  - Added `/api/run/{run_id}/screenshots` endpoint
  - Returns list of screenshots with count

### Styling
- **static/css/style.css**: Modal styles already exist, reused for results modal

## Example Usage

```javascript
// When user clicks on a run
loadRun('20260118_171100');

// Modal shows:
// - Run ID: 20260118_171100
// - Screenshots: 
//   * desktop_milestoneinternet.com__20260118_171100_viewport.png
//   * mobile_milestoneinternet.com__20260118_171100_viewport.png
//   * tablet_milestoneinternet.com__20260118_171100_viewport.png
// - Link: Open Full Report Directory
```

## Benefits

✅ **Quick Results Review**: See all screenshots at a glance
✅ **No File Navigation**: No need to manually browse folders
✅ **Visual Comparison**: Compare screenshots side-by-side
✅ **Easy Access**: One click from run history
✅ **Full Details**: Link to complete report folder for deeper analysis

## Technical Details

### Screenshot Loading
1. Fetch from `/api/run/{run_id}/screenshots`
2. API scans `static/reports/{run_id}/screenshots/` directory
3. Returns sorted list of image files
4. Frontend displays in grid with thumbnails
5. Click to view full size in new tab

### Error Handling
- If screenshots not found: Shows error message with folder link
- If API fails: Shows error with fallback link
- Graceful degradation: Always provides manual folder access

## Next Steps

Future enhancements could include:
- Visual diff comparison between baseline and current
- Test pass/fail indicators on each screenshot
- Filter by device type (desktop/tablet/mobile)
- Download all screenshots as ZIP
- Side-by-side comparison view
- Test metrics and statistics display
