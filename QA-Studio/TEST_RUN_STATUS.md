# Test Run Status - How to Monitor Tests

## ✅ Status Visibility Features (Now Implemented)

### 1. **Connection Status Indicator** ✅
- **Location**: Top of the page, in the header
- **Shows**: 
  - 🟢 Green dot = Connected to server
  - 🔴 Red dot = Disconnected
- **Updates**: Automatically when connection changes

### 2. **Active Run View** ✅
- **When it appears**: Automatically shows when a test run starts
- **What it shows**:
  - Run ID
  - Overall status badge (Running/Completed/Failed)
  - Elapsed time (updates every second)
  - Progress bars for each pillar
  - Live log output

### 3. **Status Polling** ✅
- **How it works**: Checks run status every 2 seconds
- **Purpose**: Ensures status updates even if WebSocket events are missed
- **Automatic**: Starts when a run begins, stops when it completes

### 4. **Page Load Status Check** ✅
- **What it does**: On page load, checks if there's an active run
- **If active run found**: 
  - Shows the active run view
  - Resumes monitoring
  - Joins the run room for log streaming

## 📊 How to See Test Status

### Method 1: Active Run View (Automatic)
1. Click "Run Tests"
2. The configuration form disappears
3. **Active Run View** appears showing:
   - Run ID
   - Status badge
   - Elapsed time
   - Progress bars
   - Live logs

### Method 2: Check Connection Status
- Look at the top of the page
- Green dot = Connected (ready to receive updates)
- Red dot = Disconnected (refresh page)

### Method 3: Browser Console
- Open Developer Tools (F12)
- Check console for:
  - "Run started: [run_id]"
  - "Run completed: [status]"
  - Log messages

### Method 4: Run History
- Scroll to bottom of page
- See list of recent runs
- Click on a run to view details (coming soon)

## 🔍 Troubleshooting

### "I don't see the active run view"
**Possible causes:**
1. WebSocket not connected - Check connection status indicator
2. Event not received - Status polling will catch it (wait 2 seconds)
3. Page not refreshed - Try refreshing the page

**Solutions:**
- Check connection status (green/red dot)
- Wait a few seconds for status polling
- Refresh the page
- Check browser console for errors

### "Status shows 'Running' but nothing happens"
**Possible causes:**
1. Tests are actually running (may take time)
2. Logs not streaming (check log viewer)
3. Tests failed silently

**Solutions:**
- Check the log viewer for output
- Wait - tests can take several minutes
- Check browser console for errors
- Look for pytest output in logs

### "I see logs but no progress bars updating"
**Status**: Partially implemented
- Progress bars show initial state
- Real-time pillar status updates need backend integration
- This is a known limitation (see UI_STATUS.md)

## 🎯 Current Status Features

| Feature | Status | Notes |
|---------|--------|-------|
| Connection Indicator | ✅ Working | Shows green/red dot |
| Active Run View | ✅ Working | Shows when run starts |
| Elapsed Timer | ✅ Working | Updates every second |
| Status Polling | ✅ Working | Checks every 2 seconds |
| Live Logs | ⚠️ Partial | Depends on backend streaming |
| Progress Bars | ⚠️ Partial | Shows but may not update in real-time |
| Run History | ✅ Working | Shows list of runs |

## 💡 Tips

1. **Always check connection status** - Green dot means you're connected
2. **Watch the log viewer** - This shows what's actually happening
3. **Be patient** - Tests can take 1-5 minutes depending on site size
4. **Check console** - Browser console shows detailed events
5. **Refresh if stuck** - If status seems frozen, refresh the page

## 🚀 What Happens When You Click "Run Tests"

1. ✅ Form submits to `/api/run`
2. ✅ Server creates run and starts background thread
3. ✅ Server emits `run_started` event
4. ✅ Client receives event and shows active run view
5. ✅ Status polling starts (every 2 seconds)
6. ✅ Logs stream via WebSocket (if working)
7. ✅ Tests execute in background
8. ✅ Server emits `run_completed` when done
9. ✅ Client updates status and shows results

---

**If you're still not seeing status updates, check:**
- Browser console for errors
- Network tab for WebSocket connection
- Server terminal for pytest output
- Connection status indicator (green/red dot)
