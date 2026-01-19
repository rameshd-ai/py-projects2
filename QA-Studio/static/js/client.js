/**
 * QA Studio - Client-side SocketIO and UI logic
 */

// Initialize SocketIO connection
const socket = io();

// State management
let currentRunId = null;
let startTime = null;
let elapsedInterval = null;
const pillarNames = {
    1: 'Rendering & Responsiveness',
    2: 'Site Architecture & Navigation',
    3: 'Functional & Business Logic',
    4: 'Console & Technical Checks',
    5: 'Cross-Browser & Device Testing',
    6: 'Content, SEO & Schema Validation'
};

// SocketIO event handlers
socket.on('connect', () => {
    console.log('Connected to QA Studio server');
    updateConnectionStatus(true);
    addLog('info', 'Connected to QA Studio');
});

socket.on('disconnect', () => {
    updateConnectionStatus(false);
    addLog('warning', 'Disconnected from server');
});

function updateConnectionStatus(connected) {
    const indicator = document.getElementById('status-indicator');
    const text = document.getElementById('status-text');
    if (indicator && text) {
        indicator.style.background = connected ? '#28a745' : '#dc3545';
        text.textContent = connected ? 'Connected' : 'Disconnected';
    }
}

socket.on('connected', (data) => {
    console.log('Server message:', data.message);
});

socket.on('joined', (data) => {
    console.log('Joined run room:', data.room);
});

socket.on('log', (data) => {
    addLog(data.level || 'info', data.message);
    addModalLog(data.level || 'info', data.message);
    
    // Extract current URL from log messages
    const message = data.message || '';
    
    // Update current URL display if log mentions a URL
    if (message.includes('Testing') && message.includes('viewport for:')) {
        const urlMatch = message.match(/for:\s*(https?:\/\/[^\s]+)/);
        if (urlMatch) {
            updateCurrentUrl(urlMatch[1]);
        }
    } else if (message.includes('Testing') && message.includes('URL:')) {
        const urlMatch = message.match(/URL:\s*(https?:\/\/[^\s]+)/);
        if (urlMatch) {
            updateCurrentUrl(urlMatch[1]);
        }
    } else if (message.includes('[PROGRESS]')) {
        // Keep showing last URL during progress updates
    } else if (message.includes('Starting pytest') || message.includes('Pytest process started')) {
        updateCurrentUrl('Starting test execution...');
    }
});

function updateCurrentUrl(url) {
    const urlEl = document.getElementById('modal-current-url');
    if (urlEl) {
        urlEl.textContent = url;
        urlEl.style.color = '#667eea';
    }
}

socket.on('run_started', (data) => {
    console.log('Run started:', data.run_id);
    currentRunId = data.run_id;
    startTime = new Date();
    showProgressModal(data.run_id);
    initializeProgressBars();
    startElapsedTimer();
    updateRunStatus('running');
    startStatusPolling(); // Start polling for status updates
    addLog('success', `Test run started: ${data.run_id}`);
    addModalLog('success', `Test run started: ${data.run_id}`);
});

socket.on('run_completed', (data) => {
    console.log('Run completed:', data);
    stopElapsedTimer();
    updateRunStatus(data.status);
    updateModalStatus(data.status);
    
    // Update all pillar progress bars to 100% with final status
    const pillars = [1, 2, 3, 4, 5, 6];
    pillars.forEach(pillarNum => {
        const finalStatus = data.status === 'completed' ? 'success' : 
                           data.status === 'failed' ? 'failed' : 
                           data.status === 'cancelled' ? 'cancelled' : 'pending';
        updatePillarStatus(pillarNum, finalStatus, `Test run ${data.status}`);
    });
    
    // Disable cancel button
    const cancelBtn = document.getElementById('modal-cancel-btn');
    if (cancelBtn) {
        cancelBtn.disabled = true;
        cancelBtn.textContent = 'Run Completed';
        cancelBtn.style.opacity = '0.6';
        cancelBtn.style.cursor = 'not-allowed';
    }
    
    // Also disable cancel button in main section
    const mainCancelBtn = document.getElementById('cancel-btn');
    if (mainCancelBtn) {
        mainCancelBtn.disabled = true;
    }
    
    // Stop status polling
    if (statusPollInterval) {
        clearInterval(statusPollInterval);
        statusPollInterval = null;
    }
    
    addLog(data.status === 'completed' ? 'success' : 'error', 
           `Test run ${data.status}: ${data.run_id}`);
    addModalLog(data.status === 'completed' ? 'success' : 'error', 
                `Test run ${data.status}: ${data.run_id}`);
    
    if (data.status === 'completed' || data.status === 'failed') {
        // Load bug report if test failed
        if (data.status === 'failed' && currentRunId) {
            loadBugReport(currentRunId);
        }
        
        setTimeout(() => {
            loadRunHistory();
        }, 1000);
    }
});

socket.on('pillar_status', (data) => {
    updatePillarStatus(data.pillar, data.status, data.message);
});

// File input handler for baseline images
const baselineImageInput = document.getElementById('baseline-images');
if (baselineImageInput) {
    baselineImageInput.addEventListener('change', (e) => {
        const files = e.target.files;
        const filesList = document.getElementById('baseline-files-list');
        
        if (files.length === 0) {
            filesList.textContent = 'No files selected';
        } else {
            filesList.innerHTML = `<strong>${files.length} file(s) selected:</strong><br>` + 
                Array.from(files).map(f => `• ${f.name}`).join('<br>');
        }
    });
}

// Form submission
document.getElementById('test-config-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const formData = new FormData(e.target);
    
    // Handle baseline images upload if provided
    const baselineInput = document.getElementById('baseline-images');
    const baselineFiles = baselineInput ? baselineInput.files : [];
    
    if (baselineFiles.length > 0) {
        console.log('[CLIENT] Uploading', baselineFiles.length, 'baseline images...');
        
        // Upload baseline images first
        const uploadFormData = new FormData();
        for (let i = 0; i < baselineFiles.length; i++) {
            uploadFormData.append('files', baselineFiles[i]);
        }
        
        try {
            const uploadResponse = await fetch('/api/baselines/upload', {
                method: 'POST',
                body: uploadFormData
            });
            
            const uploadResult = await uploadResponse.json();
            
            if (!uploadResult.success) {
                alert(`Failed to upload baseline images: ${uploadResult.error}`);
                return;
            }
            
            console.log(`[CLIENT] Uploaded ${uploadResult.uploaded} baseline images`);
        } catch (error) {
            console.error('[CLIENT] Error uploading baselines:', error);
            alert(`Error uploading baseline images: ${error.message}`);
            return;
        }
    } else {
        console.log('[CLIENT] No baseline images provided - will perform UI health checks only');
    }
    
    const config = {
        base_url: formData.get('base_url'),
        sitemap_url: formData.get('sitemap_url') || null,
        browsers: Array.from(document.querySelectorAll('input[name="browsers"]:checked')).map(cb => cb.value),
        devices: Array.from(document.querySelectorAll('input[name="devices"]:checked')).map(cb => cb.value),
        pillars: Array.from(document.querySelectorAll('input[name="pillars"]:checked')).map(cb => parseInt(cb.value))
    };
    
    // Validate
    if (!config.base_url) {
        alert('Please provide a base URL');
        return;
    }
    
    if (config.pillars.length === 0) {
        alert('Please select at least one test pillar');
        return;
    }
    
    // Disable form
    document.getElementById('run-btn').disabled = true;
    
    console.log('[CLIENT] Submitting test run with config:', config);
    
    try {
        console.log('[CLIENT] Sending POST to /api/run...');
        const response = await fetch('/api/run', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(config)
        });
        
        console.log('[CLIENT] Response status:', response.status);
        const result = await response.json();
        console.log('[CLIENT] Response data:', result);
        
        if (result.success) {
            console.log('[CLIENT] Test run started successfully:', result.run_id);
            // Join the run room
            socket.emit('join_run', { run_id: result.run_id });
            // Show modal immediately (don't wait for run_started event)
            showProgressModal(result.run_id);
            addModalLog('info', 'Test run submitted. Waiting for execution to start...');
            addLog('success', `Test run started: ${result.run_id}`);
        } else {
            console.error('[CLIENT] Test run failed:', result.error);
            alert(`Error: ${result.error}`);
            document.getElementById('run-btn').disabled = false;
        }
    } catch (error) {
        console.error('[CLIENT] Error starting run:', error);
        alert(`Error: ${error.message}`);
        document.getElementById('run-btn').disabled = false;
    }
});

// Cancel button
document.getElementById('cancel-btn').addEventListener('click', async () => {
    if (!currentRunId) return;
    
    if (confirm('Are you sure you want to cancel this test run?')) {
        try {
            const response = await fetch(`/api/run/${currentRunId}/cancel`, {
                method: 'POST'
            });
            
            const result = await response.json();
            if (result.success) {
                addLog('warning', 'Test run cancelled by user');
            }
        } catch (error) {
            console.error('Error cancelling run:', error);
            alert(`Error: ${error.message}`);
        }
    }
});

// Clear logs button
document.getElementById('clear-logs-btn').addEventListener('click', () => {
    document.getElementById('log-viewer').innerHTML = '';
});

// Modal Functions
function showProgressModal(runId) {
    const modal = document.getElementById('progress-modal');
    if (!modal) {
        console.error('Progress modal not found in DOM');
        return;
    }
    
    console.log('Showing progress modal for run:', runId);
    modal.style.display = 'block';
    updateCurrentRunId(runId);
    
    const runIdEl = document.getElementById('modal-run-id');
    if (runIdEl) runIdEl.textContent = runId;
    
    const statusEl = document.getElementById('modal-status');
    if (statusEl) {
        statusEl.textContent = 'Initializing...';
        statusEl.className = 'status-badge running';
    }
    
    const runStatusEl = document.getElementById('modal-run-status');
    if (runStatusEl) runStatusEl.textContent = 'Initializing...';
    
    const elapsedEl = document.getElementById('modal-elapsed-time');
    if (elapsedEl) elapsedEl.textContent = '00:00';
    
    const logViewer = document.getElementById('modal-log-viewer');
    if (logViewer) {
        logViewer.innerHTML = '';
        addModalLog('info', 'Test run initialized. Waiting for execution to start...');
    }
    
    // Reset current URL display
    updateCurrentUrl('Initializing...');
    
    initializeModalProgressBars();
    
    // Force a test message to confirm modal is visible
    setTimeout(() => {
        addModalLog('info', 'Modal is active. Waiting for test execution...');
    }, 500);
}

function hideProgressModal() {
    const modal = document.getElementById('progress-modal');
    if (modal) {
        modal.style.display = 'none';
    }
}

function minimizeModal() {
    const modal = document.getElementById('progress-modal');
    if (modal) {
        modal.classList.add('minimized');
    }
}

function maximizeModal() {
    const modal = document.getElementById('progress-modal');
    if (modal) {
        modal.classList.remove('minimized');
    }
}

function updateModalStatus(status) {
    const statusEl = document.getElementById('modal-status');
    const runStatusEl = document.getElementById('modal-run-status');
    
    if (statusEl) {
        statusEl.textContent = status.charAt(0).toUpperCase() + status.slice(1);
        statusEl.className = `status-badge ${status}`;
    }
    
    if (runStatusEl) {
        runStatusEl.textContent = status.charAt(0).toUpperCase() + status.slice(1);
    }
}

function addModalLog(level, message) {
    const logViewer = document.getElementById('modal-log-viewer');
    if (logViewer) {
        const logLine = document.createElement('div');
        logLine.className = `log-line ${level}`;
        logLine.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
        logViewer.appendChild(logLine);
        logViewer.scrollTop = logViewer.scrollHeight;
    }
}

function initializeModalProgressBars() {
    const container = document.getElementById('modal-pillar-progress');
    if (!container) return;
    
    container.innerHTML = '';
    
    const selectedPillars = Array.from(document.querySelectorAll('input[name="pillars"]:checked'))
        .map(cb => parseInt(cb.value));
    
    selectedPillars.forEach(pillarNum => {
        const item = document.createElement('div');
        item.className = 'pillar-progress-item';
        item.id = `modal-pillar-${pillarNum}`;
        item.innerHTML = `
            <div class="pillar-label">
                <span class="pillar-name">Pillar ${pillarNum}: ${pillarNames[pillarNum]}</span>
                <span class="pillar-status pending">Pending</span>
            </div>
            <div class="progress-bar">
                <div class="progress-fill" style="width: 0%">0%</div>
            </div>
        `;
        container.appendChild(item);
    });
}

// UI Helper Functions
function showActiveRunView() {
    document.getElementById('config-section').style.display = 'none';
    document.getElementById('active-run-section').style.display = 'block';
    document.getElementById('cancel-btn').disabled = false;
    document.getElementById('run-btn').disabled = true;
    
    // Clear and initialize log viewer
    const logViewer = document.getElementById('log-viewer');
    if (logViewer.innerHTML === '') {
        addLog('info', 'Waiting for test execution to start...');
    }
}

function hideActiveRunView() {
    document.getElementById('active-run-section').style.display = 'none';
    document.getElementById('config-section').style.display = 'block';
    document.getElementById('cancel-btn').disabled = true;
    document.getElementById('run-btn').disabled = false;
}

function initializeProgressBars() {
    const container = document.getElementById('pillar-progress');
    container.innerHTML = '';
    
    // Get selected pillars from form
    const selectedPillars = Array.from(document.querySelectorAll('input[name="pillars"]:checked'))
        .map(cb => parseInt(cb.value));
    
    selectedPillars.forEach(pillarNum => {
        const item = document.createElement('div');
        item.className = 'pillar-progress-item';
        item.id = `pillar-${pillarNum}`;
        item.innerHTML = `
            <div class="pillar-label">
                <span class="pillar-name">Pillar ${pillarNum}: ${pillarNames[pillarNum]}</span>
                <span class="pillar-status pending">Pending</span>
            </div>
            <div class="progress-bar">
                <div class="progress-fill" style="width: 0%">0%</div>
            </div>
        `;
        container.appendChild(item);
    });
}

function updatePillarStatus(pillarNum, status, message) {
    // Update regular progress bars
    const item = document.getElementById(`pillar-${pillarNum}`);
    if (item) {
        const statusEl = item.querySelector('.pillar-status');
        const progressFill = item.querySelector('.progress-fill');
        
        if (statusEl) {
            statusEl.textContent = status.charAt(0).toUpperCase() + status.slice(1);
            statusEl.className = `pillar-status ${status}`;
        }
        
        if (progressFill) {
            let width = 0;
            if (status === 'running') width = 50;
            else if (status === 'success' || status === 'completed') width = 100;
            else if (status === 'failed') width = 100;
            else if (status === 'cancelled') width = 0;
            
            progressFill.style.width = `${width}%`;
            progressFill.textContent = width > 0 ? width + '%' : '';
            progressFill.className = `progress-fill ${status}`;
        }
    }
    
    // Update modal progress bars
    const modalItem = document.getElementById(`modal-pillar-${pillarNum}`);
    if (modalItem) {
        const statusEl = modalItem.querySelector('.pillar-status');
        const progressFill = modalItem.querySelector('.progress-fill');
        
        if (statusEl) {
            statusEl.textContent = status.charAt(0).toUpperCase() + status.slice(1);
            statusEl.className = `pillar-status ${status}`;
        }
        
        if (progressFill) {
            let width = 0;
            if (status === 'running') width = 50;
            else if (status === 'success' || status === 'completed') width = 100;
            else if (status === 'failed') width = 100;
            else if (status === 'cancelled') width = 0;
            
            progressFill.style.width = `${width}%`;
            progressFill.textContent = width > 0 ? width + '%' : '';
            progressFill.className = `progress-fill ${status}`;
        }
    }
    
    if (message) {
        addLog(status === 'failed' ? 'error' : 'info', `Pillar ${pillarNum}: ${message}`);
        addModalLog(status === 'failed' ? 'error' : 'info', `Pillar ${pillarNum}: ${message}`);
    }
}

function updateRunStatus(status) {
    const statusEl = document.getElementById('overall-status');
    const runStatusEl = document.getElementById('run-status');
    
    statusEl.textContent = status.charAt(0).toUpperCase() + status.slice(1);
    statusEl.className = `status-badge ${status}`;
    runStatusEl.textContent = status.charAt(0).toUpperCase() + status.slice(1);
}

function startElapsedTimer() {
    startTime = new Date();
    elapsedInterval = setInterval(() => {
        if (startTime) {
            const elapsed = Math.floor((new Date() - startTime) / 1000);
            const minutes = Math.floor(elapsed / 60);
            const seconds = elapsed % 60;
            document.getElementById('elapsed-time').textContent = 
                `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
        }
    }, 1000);
}

function stopElapsedTimer() {
    if (elapsedInterval) {
        clearInterval(elapsedInterval);
        elapsedInterval = null;
    }
}

function addLog(level, message) {
    const logViewer = document.getElementById('log-viewer');
    const logLine = document.createElement('div');
    logLine.className = `log-line ${level}`;
    logLine.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
    logViewer.appendChild(logLine);
    
    // Auto-scroll to bottom
    logViewer.scrollTop = logViewer.scrollHeight;
}

function updateCurrentRunId(runId) {
    currentRunId = runId;
    document.getElementById('current-run-id').textContent = runId;
}

// Load run history on page load
async function loadRunHistory() {
    try {
        const response = await fetch('/api/runs');
        const result = await response.json();
        
        if (result.success) {
            const historyList = document.getElementById('history-list');
            
            if (result.runs.length === 0) {
                historyList.innerHTML = '<p class="empty-state">No previous runs</p>';
                return;
            }
            
            historyList.innerHTML = result.runs.map(run => {
                const sizeKB = Math.round((run.size || 0) / 1024);
                return `
                <div class="history-item">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div style="flex: 1; cursor: pointer;" onclick="loadRun('${run.run_id}')">
                            <strong>${run.run_id}</strong>
                            <div style="font-size: 0.85em; color: #666; margin-top: 5px;">
                                ${run.timestamp} • ${run.file_count || 0} files • ${sizeKB} KB
                            </div>
                        </div>
                        <div style="display: flex; gap: 8px; align-items: center;">
                            <button class="btn-action" onclick="viewBaseline('${run.run_id}', event)" title="View Baseline" style="background: #667eea; color: white; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 0.85em;">
                                📊 Baseline
                            </button>
                            <button class="btn-action" onclick="viewCompleteReport('${run.run_id}', event)" title="Complete Report" style="background: #28a745; color: white; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 0.85em;">
                                📋 Report
                            </button>
                            <button class="btn-delete" onclick="deleteRun('${run.run_id}', event)" title="Delete run">
                                🗑️
                            </button>
                        </div>
                    </div>
                </div>
            `;
            }).join('');
        }
    } catch (error) {
        console.error('Error loading history:', error);
    }
}

function viewBaseline(runId, event) {
    event.stopPropagation();
    window.open('/reports/baselines', '_blank');
}

async function viewCompleteReport(runId, event) {
    event.stopPropagation();
    console.log('[CLIENT] Loading complete report for run:', runId);
    
    const modal = document.getElementById('complete-report-modal');
    const runIdSpan = document.getElementById('complete-report-run-id');
    const content = document.getElementById('complete-report-content');
    
    if (!modal || !runIdSpan || !content) {
        console.error('[CLIENT] Complete report modal elements not found');
        return;
    }
    
    runIdSpan.textContent = runId;
    content.innerHTML = '<p style="text-align: center; padding: 20px;">Loading bug report...</p>';
    modal.style.display = 'block';
    
    try {
        const response = await fetch(`/api/run/${runId}/bug-report`);
        const result = await response.json();
        
        if (result.success && result.errors && result.errors.length > 0) {
            const categoryNames = {
                'viewport_meta': 'Viewport Meta Tag',
                'responsive_layout': 'Responsive Layout',
                'missing_elements': 'Missing Elements',
                'broken_images': 'Broken Images',
                'text_readability': 'Text Readability',
                'visual_diff': 'Visual Regression',
                'test_error': 'Test Error',
                'other': 'Other'
            };
            
            let html = `
                <div style="margin-bottom: 20px;">
                    <h3 style="color: #d9534f; margin-bottom: 10px;">
                        ⚠️ Total Issues: ${result.total_errors || result.errors.length}
                    </h3>
                </div>
                <div style="overflow-x: auto;">
                <table style="width: 100%; border-collapse: collapse; background: white; box-shadow: 0 2px 4px rgba(0,0,0,0.1); min-width: 800px;">
                    <thead>
                        <tr style="background: #667eea; color: white;">
                            <th style="padding: 12px; text-align: left; border: 1px solid #ddd;">Page Link</th>
                            <th style="padding: 12px; text-align: left; border: 1px solid #ddd;">Bug Type</th>
                            <th style="padding: 12px; text-align: left; border: 1px solid #ddd;">Bug Description</th>
                            <th style="padding: 12px; text-align: left; border: 1px solid #ddd;">Device</th>
                            <th style="padding: 12px; text-align: left; border: 1px solid #ddd;">Image Preview</th>
                        </tr>
                    </thead>
                    <tbody>
            `;
            
            // Flatten all errors for table display
            const allErrors = result.errors || [];
            
            for (const error of allErrors) {
                const device = error.device || 'unknown';
                const url = error.url || 'N/A';
                const message = error.message || 'No description';
                const category = error.category || 'other';
                const bugType = categoryNames[category] || category.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                
                // Get screenshot path for preview
                let screenshotUrl = null;
                if (error.actual_path) {
                    screenshotUrl = '/' + error.actual_path.replace(/\\/g, '/');
                } else if (error.diff_image_path) {
                    screenshotUrl = '/' + error.diff_image_path.replace(/\\/g, '/');
                } else {
                    // Try to find screenshot by device and URL
                    const urlSafe = url.replace(/https?:\/\//, '').replace(/[\/\:]/g, '_').replace(/[^a-zA-Z0-9_\-\.]/g, '').substring(0, 50);
                    const screenshotName = `${device}_${urlSafe}_${runId}_viewport.png`;
                    screenshotUrl = `/static/reports/${runId}/screenshots/${screenshotName}`;
                }
                
                html += `
                    <tr style="border-bottom: 1px solid #eee;">
                        <td style="padding: 10px; border: 1px solid #ddd;">
                            <a href="${url}" target="_blank" style="color: #667eea; text-decoration: none; word-break: break-all;">
                                ${url.length > 50 ? url.substring(0, 50) + '...' : url}
                            </a>
                        </td>
                        <td style="padding: 10px; border: 1px solid #ddd;">
                            <span style="background: #f0f7ff; color: #667eea; padding: 4px 8px; border-radius: 3px; font-size: 0.9em; display: inline-block;">
                                ${bugType}
                            </span>
                        </td>
                        <td style="padding: 10px; border: 1px solid #ddd; max-width: 300px;">
                            <div style="word-wrap: break-word; color: #333;">
                                ${message}
                            </div>
                            ${error.difference_percentage ? `<div style="color: #999; font-size: 0.85em; margin-top: 5px;">Difference: ${error.difference_percentage}%</div>` : ''}
                        </td>
                        <td style="padding: 10px; border: 1px solid #ddd; text-align: center;">
                            <span style="background: #e9ecef; padding: 4px 8px; border-radius: 3px; font-size: 0.9em; display: inline-block;">
                                ${device.charAt(0).toUpperCase() + device.slice(1)}
                            </span>
                        </td>
                        <td style="padding: 10px; border: 1px solid #ddd; text-align: center;">
                            <div style="position: relative;">
                                <img src="${screenshotUrl}" 
                                     onerror="this.style.display='none'; this.nextElementSibling.style.display='block';"
                                     style="max-width: 150px; max-height: 100px; border-radius: 4px; cursor: pointer; border: 1px solid #ddd; object-fit: contain;"
                                     onclick="window.open('${screenshotUrl}', '_blank')"
                                     title="Click to view full size">
                                <div style="display: none; color: #999; font-size: 0.85em; padding: 10px;">No image available</div>
                            </div>
                        </td>
                    </tr>
                `;
            }
            
            html += `
                    </tbody>
                </table>
                </div>
            `;
            
            content.innerHTML = html;
        } else {
            content.innerHTML = `
                <div style="text-align: center; padding: 40px;">
                    <h3 style="color: #5cb85c;">✅ No Issues Found</h3>
                    <p style="color: #666; margin-top: 10px;">This test run completed successfully with no bugs detected.</p>
                </div>
            `;
        }
    } catch (error) {
        console.error('[CLIENT] Error loading complete report:', error);
        content.innerHTML = `
            <div style="text-align: center; padding: 20px;">
                <h3>❌ Error Loading Report</h3>
                <p>${error.message}</p>
            </div>
        `;
    }
}

async function deleteRun(runId, event) {
    event.stopPropagation(); // Prevent triggering loadRun
    
    if (!confirm(`Are you sure you want to delete run ${runId}? This cannot be undone.`)) {
        return;
    }
    
    try {
        const response = await fetch(`/api/runs/${runId}`, {
            method: 'DELETE'
        });
        
        const result = await response.json();
        
        if (result.success) {
            // Remove from UI immediately
            const historyList = document.getElementById('history-list');
            const item = event.target.closest('.history-item');
            if (item) {
                item.style.opacity = '0.5';
                item.style.transition = 'opacity 0.3s';
                setTimeout(() => {
                    loadRunHistory(); // Reload list
                }, 300);
            }
        } else {
            alert(`Error: ${result.error}`);
        }
    } catch (error) {
        console.error('Error deleting run:', error);
        alert(`Error: ${error.message}`);
    }
}

// Function to load and display bug report in modal
async function loadBugReport(runId) {
    console.log('[CLIENT] Loading bug report for run:', runId);
    
    try {
        const response = await fetch(`/api/run/${runId}/bug-report`);
        const result = await response.json();
        
        const bugReportSection = document.getElementById('modal-bug-report');
        const bugReportContent = document.getElementById('modal-bug-report-content');
        
        if (!bugReportSection || !bugReportContent) {
            console.error('[CLIENT] Bug report elements not found');
            return;
        }
        
        if (result.success && result.errors && result.errors.length > 0) {
            // Show bug report section
            bugReportSection.style.display = 'block';
            
            const categoryNames = {
                'viewport_meta': 'Viewport Meta Tag Issues',
                'responsive_layout': 'Responsive Layout Issues',
                'missing_elements': 'Missing Elements',
                'broken_images': 'Broken Images',
                'text_readability': 'Text Readability Issues',
                'visual_diff': 'Visual Regression',
                'test_error': 'Test Errors',
                'other': 'Other Issues'
            };
            
            let html = `
                <p style="font-size: 1.1em; margin-bottom: 15px; color: #d9534f; font-weight: bold;">
                    ⚠️ ${result.total_errors || result.errors.length} Issue(s) Found
                </p>
            `;
            
            const errorsByCategory = result.errors_by_category || {};
            
            for (const [category, categoryErrors] of Object.entries(errorsByCategory)) {
                const categoryDisplay = categoryNames[category] || category.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                html += `
                    <div style="margin-bottom: 15px; background: white; padding: 12px; border-radius: 5px; border: 1px solid #ddd;">
                        <h4 style="color: #d9534f; margin-bottom: 8px; font-size: 1em;">
                            📋 ${categoryDisplay} (${categoryErrors.length})
                        </h4>
                        <div style="margin-left: 10px;">
                `;
                
                for (const error of categoryErrors.slice(0, 3)) { // Show first 3 per category
                    const device = error.device || 'unknown';
                    const url = error.url || 'N/A';
                    const message = error.message || 'No message';
                    
                    html += `
                        <div style="padding: 8px; margin-bottom: 5px; background: #f9f9f9; border-left: 3px solid #d9534f; border-radius: 3px; font-size: 0.9em;">
                            <div style="font-weight: bold; margin-bottom: 3px;">
                                🔴 ${device.charAt(0).toUpperCase() + device.slice(1)} - ${url.length > 40 ? url.substring(0, 40) + '...' : url}
                            </div>
                            <div style="color: #666;">
                                ${message.length > 100 ? message.substring(0, 100) + '...' : message}
                            </div>
                        </div>
                    `;
                }
                
                if (categoryErrors.length > 3) {
                    html += `<div style="color: #999; font-size: 0.85em; margin-top: 5px;">... and ${categoryErrors.length - 3} more issue(s)</div>`;
                }
                
                html += `
                        </div>
                    </div>
                `;
            }
            
            html += `
                <div style="margin-top: 15px; text-align: center;">
                    <a href="/reports/${runId}" target="_blank" style="color: #667eea; text-decoration: none; font-weight: bold;">
                        View Complete Bug Report →
                    </a>
                </div>
            `;
            
            bugReportContent.innerHTML = html;
        } else {
            // No errors or errors not available
            bugReportSection.style.display = 'none';
        }
    } catch (error) {
        console.error('[CLIENT] Error loading bug report:', error);
        const bugReportSection = document.getElementById('modal-bug-report');
        if (bugReportSection) {
            bugReportSection.style.display = 'none';
        }
    }
}

// Function to load a specific run and show results
async function loadRun(runId) {
    console.log('[CLIENT] Loading run:', runId);
    
    try {
        // Show the results modal
        const modal = document.getElementById('results-modal');
        const runIdSpan = document.getElementById('results-run-id');
        const content = document.getElementById('results-content-modal');
        
        runIdSpan.textContent = runId;
        content.innerHTML = '<p style="text-align: center; padding: 20px;">Loading results...</p>';
        modal.style.display = 'block';
        
        // Fetch screenshots list from API
        const dirResponse = await fetch(`/api/run/${runId}/screenshots`);
        
        if (dirResponse.ok) {
            const data = await dirResponse.json();
            
            // Build results HTML
            let html = `
                <div style="margin-bottom: 20px;">
                    <h3>📊 Test Run Summary</h3>
                    <p><strong>Run ID:</strong> ${runId}</p>
                    <p><strong>Screenshots:</strong> ${data.count || 0} files</p>
                    <p><strong>Results Location:</strong> <a href="/static/reports/${runId}/screenshots/" target="_blank">Open Folder</a></p>
                </div>
            `;
            
            if (data.screenshots && data.screenshots.length > 0) {
                html += `
                    <div style="margin-bottom: 20px;">
                        <h3>📸 Test Screenshots</h3>
                        <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 15px; margin-top: 15px;">
                `;
                
                data.screenshots.forEach(screenshot => {
                    const deviceType = screenshot.includes('mobile') ? '📱 Mobile' : 
                                      screenshot.includes('tablet') ? '📟 Tablet' : 
                                      screenshot.includes('desktop') ? '🖥️ Desktop' : '📸';
                    
                    html += `
                        <div style="border: 1px solid #ddd; padding: 10px; border-radius: 5px; background: #f9f9f9;">
                            <div style="font-size: 0.85em; margin-bottom: 5px; color: #667eea; font-weight: bold;">
                                ${deviceType}
                            </div>
                            <img src="/static/reports/${runId}/screenshots/${screenshot}" 
                                 style="width: 100%; height: auto; border-radius: 3px; cursor: pointer; border: 1px solid #ccc;"
                                 onclick="window.open('/static/reports/${runId}/screenshots/${screenshot}', '_blank')"
                                 title="Click to view full size"
                                 onerror="this.src='data:image/svg+xml,%3Csvg xmlns=\\'http://www.w3.org/2000/svg\\' width=\\'300\\' height=\\'200\\'%3E%3Crect fill=\\'%23f0f0f0\\' width=\\'300\\' height=\\'200\\'/%3E%3Ctext x=\\'50%25\\' y=\\'50%25\\' text-anchor=\\'middle\\' fill=\\'%23999\\'%3EImage not found%3C/text%3E%3C/svg%3E'">
                            <p style="margin: 8px 0 0; font-size: 0.8em; word-break: break-all; color: #666;">${screenshot}</p>
                        </div>
                    `;
                });
                
                html += `
                        </div>
                    </div>
                `;
            } else {
                html += `
                    <div style="text-align: center; padding: 40px; background: #f9f9f9; border-radius: 8px;">
                        <h3 style="color: #999;">No screenshots found</h3>
                        <p>This test run may not have completed or no screenshots were captured.</p>
                    </div>
                `;
            }
            
            // Add baseline comparison section
            html += `
                <div style="margin-top: 20px; padding: 15px; background: #f0f7ff; border-radius: 8px; border: 1px solid #d0e7ff;">
                    <h3>📊 Baseline Images</h3>
                    <p style="color: #666; margin-bottom: 10px;">View reference baseline images for comparison:</p>
                    <a href="/reports/baselines" target="_blank" class="btn btn-secondary" style="display: inline-block; padding: 8px 16px; background: #667eea; color: white; text-decoration: none; border-radius: 5px;">
                        View Baseline Screenshots
                    </a>
                </div>
                
                <div style="margin-top: 20px;">
                    <h3>📁 Full Report</h3>
                    <p>
                        <a href="/reports/${runId}" target="_blank" class="btn btn-primary" style="display: inline-block; padding: 10px 20px; background: #667eea; color: white; text-decoration: none; border-radius: 5px;">
                            View Complete Report
                        </a>
                    </p>
                </div>
            `;
            
            content.innerHTML = html;
        } else {
            // Handle error response
            const errorData = await dirResponse.json();
            content.innerHTML = `
                <div style="text-align: center; padding: 20px;">
                    <h3>❌ Results Not Found</h3>
                    <p>Could not load results for run ${runId}</p>
                    <p style="color: #666;">${errorData.error || 'Unknown error'}</p>
                    <p style="margin-top: 20px;">
                        <a href="/reports/${runId}" target="_blank" class="btn btn-primary" style="display: inline-block; padding: 10px 20px; background: #667eea; color: white; text-decoration: none; border-radius: 5px;">
                            View Report Page
                        </a>
                    </p>
                </div>
            `;
        }
        
    } catch (error) {
        console.error('[CLIENT] Error loading run:', error);
        const content = document.getElementById('results-content-modal');
        content.innerHTML = `
            <div style="text-align: center; padding: 20px;">
                <h3>❌ Error Loading Results</h3>
                <p>${error.message}</p>
                <p style="margin-top: 20px;">
                    <a href="/reports/${runId}" target="_blank" class="btn btn-primary" style="display: inline-block; padding: 10px 20px; background: #667eea; color: white; text-decoration: none; border-radius: 5px;">
                        View Report Page
                    </a>
                </p>
            </div>
        `;
    }
}

// Close results modal handlers
function initializeResultsModal() {
    const closeResultsBtn = document.getElementById('close-results-btn');
    const closeResultsModalBtn = document.getElementById('close-results-modal-btn');
    const resultsModal = document.getElementById('results-modal');
    
    if (closeResultsBtn) {
        closeResultsBtn.addEventListener('click', () => {
            resultsModal.style.display = 'none';
        });
    }
    
    if (closeResultsModalBtn) {
        closeResultsModalBtn.addEventListener('click', () => {
            resultsModal.style.display = 'none';
        });
    }
    
    // Close modal when clicking outside
    window.addEventListener('click', (e) => {
        if (e.target === resultsModal) {
            resultsModal.style.display = 'none';
        }
    });
}

// Check for active run on page load
async function checkActiveRun() {
    try {
        const response = await fetch('/api/runs');
        const result = await response.json();
        
        if (result.success && result.runs && result.runs.length > 0) {
            // Check the most recent run
            const latestRun = result.runs[0];
            const statusResponse = await fetch(`/api/run/${latestRun.run_id}/status`);
            const statusResult = await statusResponse.json();
            
            if (statusResult.success && statusResult.status === 'running') {
                // There's an active run, show the modal
                currentRunId = latestRun.run_id;
                updateCurrentRunId(latestRun.run_id);
                showProgressModal(latestRun.run_id);
                initializeProgressBars();
                initializeModalProgressBars();
                startElapsedTimer();
                updateRunStatus('running');
                updateModalStatus('running');
                startStatusPolling();
                socket.emit('join_run', { run_id: latestRun.run_id });
                addLog('info', `Resumed monitoring run: ${latestRun.run_id}`);
                addModalLog('info', `Resumed monitoring run: ${latestRun.run_id}`);
            }
        }
    } catch (error) {
        console.error('Error checking active run:', error);
    }
}

// Poll for status updates every 2 seconds if there's an active run
let statusPollInterval = null;

function startStatusPolling() {
    if (statusPollInterval) return; // Already polling
    
    statusPollInterval = setInterval(async () => {
        if (!currentRunId) {
            clearInterval(statusPollInterval);
            statusPollInterval = null;
            return;
        }
        
        try {
            const response = await fetch(`/api/run/${currentRunId}/status`);
            const result = await response.json();
            
            if (result.success) {
                if (result.status === 'completed' || result.status === 'failed' || result.status === 'cancelled') {
                    // Run finished, stop polling
                    clearInterval(statusPollInterval);
                    statusPollInterval = null;
                    updateRunStatus(result.status);
                    stopElapsedTimer();
                    loadRunHistory();
                } else if (result.status === 'running') {
                    // Still running, update status
                    updateRunStatus('running');
                }
            }
        } catch (error) {
            console.error('Error polling status:', error);
        }
    }, 2000); // Poll every 2 seconds
}

// Modal event handlers
document.addEventListener('DOMContentLoaded', () => {
    // Close modal button
    const closeBtn = document.getElementById('close-modal-btn');
    if (closeBtn) {
        closeBtn.addEventListener('click', () => {
            const modal = document.getElementById('progress-modal');
            const statusEl = document.getElementById('modal-status');
            if (statusEl && (statusEl.textContent === 'Completed' || statusEl.textContent === 'Failed' || statusEl.textContent === 'Cancelled')) {
                hideProgressModal();
            } else {
                if (confirm('Test is still running. Are you sure you want to close? You can still see status in the page.')) {
                    minimizeModal();
                }
            }
        });
    }
    
    // Minimize button
    const minimizeBtn = document.getElementById('modal-minimize-btn');
    if (minimizeBtn) {
        minimizeBtn.addEventListener('click', () => {
            minimizeModal();
        });
    }
    
    // Maximize minimized modal
    const modalHeader = document.querySelector('.modal-header');
    if (modalHeader) {
        modalHeader.addEventListener('click', () => {
            const modal = document.getElementById('progress-modal');
            if (modal && modal.classList.contains('minimized')) {
                maximizeModal();
            }
        });
    }
    
    // Cancel run from modal
    const modalCancelBtn = document.getElementById('modal-cancel-btn');
    if (modalCancelBtn) {
        modalCancelBtn.addEventListener('click', async () => {
            if (!currentRunId) return;
            
            if (confirm('Are you sure you want to cancel this test run?')) {
                try {
                    const response = await fetch(`/api/run/${currentRunId}/cancel`, {
                        method: 'POST'
                    });
                    
                    const result = await response.json();
                    if (result.success) {
                        addModalLog('warning', 'Test run cancelled by user');
                        updateModalStatus('cancelled');
                    }
                } catch (error) {
                    console.error('Error cancelling run:', error);
                    alert(`Error: ${error.message}`);
                }
            }
        });
    }
    
    // Clear modal logs
    const modalClearLogsBtn = document.getElementById('modal-clear-logs-btn');
    if (modalClearLogsBtn) {
        modalClearLogsBtn.addEventListener('click', () => {
            document.getElementById('modal-log-viewer').innerHTML = '';
        });
    }
    
    // View full report button in modal
    const modalViewFullReportBtn = document.getElementById('modal-view-full-report-btn');
    if (modalViewFullReportBtn) {
        modalViewFullReportBtn.addEventListener('click', () => {
            if (currentRunId) {
                window.open(`/reports/${currentRunId}`, '_blank');
            }
        });
    }
    
    // Initialize results modal
    initializeResultsModal();
    
    // Initialize complete report modal
    const closeCompleteReportBtn = document.getElementById('close-complete-report-btn');
    const closeCompleteReportModalBtn = document.getElementById('close-complete-report-modal-btn');
    const completeReportModal = document.getElementById('complete-report-modal');
    
    if (closeCompleteReportBtn) {
        closeCompleteReportBtn.addEventListener('click', () => {
            completeReportModal.style.display = 'none';
        });
    }
    
    if (closeCompleteReportModalBtn) {
        closeCompleteReportModalBtn.addEventListener('click', () => {
            completeReportModal.style.display = 'none';
        });
    }
    
    // Close modal when clicking outside
    window.addEventListener('click', (e) => {
        if (e.target === completeReportModal) {
            completeReportModal.style.display = 'none';
        }
    });
    
    loadRunHistory();
    checkActiveRun();
});
