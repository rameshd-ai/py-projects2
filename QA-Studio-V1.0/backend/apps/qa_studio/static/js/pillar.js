(function () {
  const BASE = '/qa-studio';
  const API = BASE + '/api';
  const pathParts = window.location.pathname.split('/').filter(Boolean);
  // URL: /qa-studio/project/<projectId>/pillar/<pillarSlug>  => [qa-studio, project, id, pillar, slug]
  const projectId = pathParts.length >= 5 && pathParts[0] === 'qa-studio' && pathParts[1] === 'project' && pathParts[3] === 'pillar'
    ? pathParts[2] : null;
  const pillarSlug = pathParts.length >= 5 ? pathParts[4] : null;

  const el = (id) => document.getElementById(id);

  function showLoading(show) {
    el('pillar-loading').style.display = show ? 'block' : 'none';
  }
  function showError(msg) {
    var err = el('pillar-error');
    err.textContent = msg || '';
    err.style.display = msg ? 'block' : 'none';
  }
  function showContent(show) {
    el('pillar-content').style.display = show ? 'block' : 'none';
  }

  function scoreColor(score) {
    if (score >= 90) return '#22c55e';
    if (score >= 80) return '#0d9488';
    if (score >= 70) return '#3b82f6';
    return '#f59e0b';
  }

  function escapeHtml(s) {
    var div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
  }
  function escapeAttr(s) {
    return String(s || '').replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  if (!projectId || !pillarSlug) {
    showLoading(false);
    showError('Page not found.');
    return;
  }

  fetch(API + '/projects/' + encodeURIComponent(projectId) + '/pillars/' + encodeURIComponent(pillarSlug))
    .then(function (res) {
      if (!res.ok) throw new Error('Not found');
      return res.json();
    })
    .then(function (data) {
      showLoading(false);
      showError('');
      showContent(true);

      var project = data;
      var pillar = data.pillar;
      if (!pillar) throw new Error('Pillar not found');

      document.title = escapeHtml(pillar.name) + ' - ' + escapeHtml(project.name) + ' - QA Studio';

      el('pillar-back-link').href = BASE + '/project/' + encodeURIComponent(projectId);
      el('pillar-project-name').textContent = project.name;
      el('pillar-title').textContent = pillar.name;

      var score = pillar.score;
      var color = scoreColor(score);
      el('pillar-page-score-ring').style.background = 'conic-gradient(' + color + ' calc(' + score + ' * 1%), #e2e8f0 0)';
      el('pillar-page-score-value').textContent = score;

      var isScanPillar = pillarSlug === 'ada-accessibility' || pillarSlug === 'responsiveness' || pillarSlug === 'content-quality';
      var total = pillar.total || (pillar.passed + pillar.failed + pillar.warning);
      el('pillar-total').textContent = isScanPillar ? '—' : (total || 0);
      el('pillar-passed').textContent = isScanPillar ? '—' : (pillar.passed || 0);
      el('pillar-failed').textContent = isScanPillar ? '—' : (pillar.failed || 0);
      el('pillar-warnings').textContent = isScanPillar ? '—' : (pillar.warning || 0);

      var pct = total ? Math.round((pillar.passed / total) * 100) : 0;
      el('pillar-pass-rate-bar').style.width = (isScanPillar ? 0 : pct) + '%';
      el('pillar-pass-rate-pct').textContent = isScanPillar ? 'Run scan' : (pct + '%');

      var issues = pillar.issues || [];
      var issuesSection = el('pillar-issues-section');
      issuesSection.style.display = isScanPillar ? 'none' : 'block';
      el('pillar-issues-title').textContent = 'ISSUES (' + issues.length + ')';
      var list = el('pillar-issues-list');
      list.innerHTML = issues.map(function (issue) {
        var sev = (issue.severity || 'critical').toLowerCase();
        return (
          '<div class="issue-card">' +
          '<div class="issue-header">' +
          '<span class="issue-title">' + escapeHtml(issue.title) + '</span>' +
          '<span class="issue-tag issue-tag-' + sev + '">' + (sev === 'critical' ? '&#215; ' : '') + escapeHtml(issue.severity || '') + '</span>' +
          '<span class="issue-tag issue-tag-status">' + escapeHtml(issue.status || 'open') + '</span>' +
          '</div>' +
          '<p class="issue-desc">' + escapeHtml(issue.description || '') + '</p>' +
          (issue.page ? '<span class="issue-page">' + escapeHtml(issue.page) + '</span>' : '') +
          (issue.recommendation ? '<div class="issue-recommendation"><strong>RECOMMENDATION</strong> ' + escapeHtml(issue.recommendation) + '</div>' : '') +
          '</div>'
        );
      }).join('');

      if ((pillarSlug === 'ada-accessibility' || pillarSlug === 'responsiveness' || pillarSlug === 'content-quality') && project.domain_url) {
        var btnScan = el('btn-run-scan');
        var btnScanNew = el('btn-scan-new');
        var scanSection = el('pillar-scan-section');
        var urlListEl = el('pillar-scan-url-list');
        if (btnScan && scanSection && urlListEl) {
          btnScan.style.display = 'inline-block';
          if (btnScanNew) btnScanNew.style.display = 'inline-block';
          var btnInfo = el('btn-custom-tests-info');
          if (btnInfo) btnInfo.style.display = 'inline-block';
          var apiBase = pillarSlug === 'ada-accessibility' ? 'accessibility' : (pillarSlug === 'content-quality' ? 'content-quality' : 'responsiveness');
          var isResponsiveness = pillarSlug === 'responsiveness';
          var isContentQuality = pillarSlug === 'content-quality';
          var scanTitleEl = scanSection.querySelector('h2.pillar-issues-title');
          if (scanTitleEl) scanTitleEl.textContent = isContentQuality ? 'Content Quality scan report' : (isResponsiveness ? 'Responsiveness scan report' : 'axe-core scan report');
          var summaryLabels = document.querySelectorAll('.pillar-summary-cards .summary-card-label');
          if ((isResponsiveness || isContentQuality) && summaryLabels.length >= 4) {
            summaryLabels[2].textContent = 'FAILED';
            summaryLabels[3].textContent = 'WARNINGS';
          }

          function renderNode(n, idx) {
            var target = Array.isArray(n.target) ? n.target.join(', ') : (n.target || '');
            var rawHtml = String(n.html || '');
            var htmlPreview = rawHtml ? rawHtml.substring(0, 400) + (rawHtml.length > 400 ? '...' : '') : '';
            var label = target || n.failureSummary || ('Element ' + (idx + 1));
            var titleAttr = escapeAttr(rawHtml);
            var htmlBlock = htmlPreview
              ? '<code class="axe-node-html" title="' + titleAttr + '">' + escapeHtml(htmlPreview) + '</code>'
              : '<span class="axe-node-empty">No HTML available</span>';
            return '<div class="axe-node-item"><span class="axe-node-selector" title="' + titleAttr + '">' + escapeHtml(label) + '</span><div class="axe-node-body">' + htmlBlock + '</div></div>';
          }
          function renderViolation(v) {
            var nodes = (v.nodes || []).map(renderNode).join('');
            return '<div class="issue-card"><div class="issue-header"><span class="issue-title">' + escapeHtml(v.id || '') + '</span><span class="issue-tag issue-tag-' + (v.impact || 'minor') + '">' + escapeHtml((v.impact || '').toUpperCase()) + '</span></div><p class="issue-desc">' + escapeHtml(v.description || '') + '</p>' + (v.help ? '<div class="issue-recommendation"><strong>Help</strong> ' + escapeHtml(v.help) + (v.helpUrl ? ' <a href="' + escapeHtml(v.helpUrl) + '" target="_blank" rel="noopener">Learn more</a>' : '') + '</div>' : '') + (nodes ? '<div class="axe-nodes">' + nodes + '</div>' : '') + '</div>';
          }
          function renderIncomplete(inc) {
            var nodes = (inc.nodes || []).map(renderNode).join('');
            return '<div class="issue-card issue-card-incomplete"><div class="issue-header"><span class="issue-title">' + escapeHtml(inc.id || '') + '</span><span class="issue-tag issue-tag-incomplete">Needs review</span></div><p class="issue-desc">' + escapeHtml(inc.description || '') + '</p>' + (inc.help ? '<div class="issue-recommendation"><strong>Help</strong> ' + escapeHtml(inc.help) + (inc.helpUrl ? ' <a href="' + escapeHtml(inc.helpUrl) + '" target="_blank" rel="noopener">Learn more</a>' : '') + '</div>' : '') + (nodes ? '<div class="axe-nodes">' + nodes + '</div>' : '') + '</div>';
          }
          function reportDetailsHtmlResp(report) {
            var devices = report.devices || [];
            var html = '';
            devices.forEach(function (d) {
              var issues = d.issues || [];
              if (issues.length === 0 && !d.screenshot) return;
              html += '<div class="resp-device-block">';
              html += '<h3 class="resp-device-title">' + escapeHtml(d.label || '') + ' (' + (d.viewport && d.viewport.width ? d.viewport.width + '×' + d.viewport.height : '') + ')</h3>';
              if (d.screenshot) {
                html += '<div class="resp-screenshot-wrap"><img src="data:image/png;base64,' + d.screenshot + '" alt="Screenshot" class="resp-screenshot" /></div>';
              }
              issues.forEach(function (iss) {
                var sev = (iss.severity || 'warning').toLowerCase();
                html += '<div class="issue-card"><div class="issue-header"><span class="issue-title">' + escapeHtml(iss.title || iss.id || '') + '</span><span class="issue-tag issue-tag-' + sev + '">' + escapeHtml((iss.severity || '').toUpperCase()) + '</span></div>';
                html += '<p class="issue-desc">' + escapeHtml(iss.description || '') + '</p>';
                if (iss.recommendation) html += '<div class="issue-recommendation"><strong>Recommendation</strong> ' + escapeHtml(iss.recommendation) + '</div>';
                if (iss.helpUrl || iss.standard) html += '<div class="issue-standard-ref">' + (iss.standard ? '<strong>Standard</strong> ' + escapeHtml(iss.standard) + ' ' : '') + (iss.helpUrl ? '<a href="' + escapeAttr(iss.helpUrl) + '" target="_blank" rel="noopener">View standard →</a>' : '') + '</div>';
                if (iss.elements && iss.elements.length) {
                  html += '<div class="axe-nodes">';
                  iss.elements.slice(0, 5).forEach(function (el) {
                    var sel = el.selector || el.tag || '';
                    var rect = el.rect ? ' (' + Math.round(el.rect.w || 0) + '×' + Math.round(el.rect.h || 0) + ')' : '';
                    html += '<div class="axe-node-item"><span class="axe-node-selector">' + escapeHtml(sel + rect) + '</span></div>';
                  });
                  html += '</div>';
                }
                html += '</div>';
              });
              html += '</div>';
            });
            return html ? '<div class="accordion-body-violations">' + html + '</div>' : '<div class="accordion-body-violations"><p class="accordion-empty">No issues found.</p></div>';
          }
          function reportDetailsHtmlContentQuality(report) {
            var checks = report.checks || {};
            var html = '';
            if (checks._screenshot) {
              html += '<div class="resp-screenshot-wrap" style="margin-bottom:16px"><img src="data:image/png;base64,' + checks._screenshot + '" alt="Screenshot" class="resp-screenshot" /></div>';
            }
            var checkLabels = { broken_links: 'Broken links', broken_images: 'Broken images/media', empty_content: 'Empty content blocks', empty_content_info: 'Layout & decorative containers (informational)', duplicate_content: 'Duplicate content', duplicate_content_info: 'Component duplicates (informational)', truncated_text: 'Truncated/clipped text', truncated_text_info: 'Overlay, design & animation overflow (informational)', placeholder_content: 'Placeholder/dummy content' };
            for (var key in checks) {
              if (key.charAt(0) === '_') continue;
              var c = checks[key];
              var issues = c.issues || [];
              if (issues.length === 0) continue;
              var sev = (c.severity || 'minor').toLowerCase();
              var infoClass = (key === 'duplicate_content_info' || key === 'truncated_text_info' || key === 'empty_content_info') ? ' issue-card-informational' : '';
              if ((key === 'duplicate_content_info' || key === 'truncated_text_info' || key === 'empty_content_info') && c.message) {
                html += '<div class="resp-device-block resp-device-block-info"><p class="issue-informational-msg">' + escapeHtml(c.message) + '</p></div>';
              }
              var isInfo = key === 'duplicate_content_info' || key === 'truncated_text_info' || key === 'empty_content_info';
              html += '<div class="resp-device-block' + (isInfo ? ' resp-device-block-info' : '') + '"><h3 class="resp-device-title">' + escapeHtml(checkLabels[key] || key) + ' <span class="issue-tag issue-tag-' + sev + '">' + escapeHtml((c.severity || '').toUpperCase()) + '</span> (' + (c.count || 0) + ')</h3>';
              issues.slice(0, 8).forEach(function (iss) {
                html += '<div class="issue-card"><div class="issue-header">';
                if (iss.href) html += '<span class="issue-title" style="word-break:break-all">' + escapeHtml(iss.href) + (iss.status ? ' [' + iss.status + ']' : '') + '</span>';
                else if (iss.src) html += '<span class="issue-title" style="word-break:break-all">' + escapeHtml(iss.src) + '</span>';
                else if (iss.text) html += '<span class="issue-title">' + escapeHtml(iss.text.substring(0, 100)) + (iss.text.length > 100 ? '…' : '') + '</span>';
                else html += '<span class="issue-title">' + escapeHtml(iss.selector || '—') + '</span>';
                if (iss.duplicate_type) html += ' <span class="issue-tag issue-tag-' + (iss.severity || 'minor').toLowerCase() + '" style="font-size:0.7rem">' + escapeHtml(iss.duplicate_type) + '</span>';
                if (iss.clipping_type) html += ' <span class="issue-tag issue-tag-' + (iss.severity || 'minor').toLowerCase() + '" style="font-size:0.7rem">' + escapeHtml(iss.clipping_type) + '</span>';
                if (iss.empty_type) html += ' <span class="issue-tag issue-tag-' + (iss.severity || 'minor').toLowerCase() + '" style="font-size:0.7rem">' + escapeHtml(iss.empty_type) + '</span>';
                html += '</div>';
                if (iss.reasoning) html += '<p class="issue-desc">' + escapeHtml(iss.reasoning) + '</p>';
                if (iss.selector) html += '<div class="axe-node-item"><span class="axe-node-selector">' + escapeHtml(iss.selector) + (iss.parent_container_selector || iss.container_selector ? ' (container: ' + escapeHtml(iss.parent_container_selector || iss.container_selector || '') + ')' : '') + (iss.overlay_selector ? ' &bull; overlay: ' + escapeHtml(iss.overlay_selector) : '') + (iss.clipped ? ' &bull; ' + escapeHtml(iss.clipped) : '') + '</span></div>';
                html += '</div>';
              });
              html += '</div>';
            }
            return html ? '<div class="accordion-body-violations">' + html + '</div>' : '<div class="accordion-body-violations"><p class="accordion-empty">No issues found.</p></div>';
          }
          function reportDetailsHtml(report) {
            if (isContentQuality) return reportDetailsHtmlContentQuality(report);
            if (isResponsiveness) return reportDetailsHtmlResp(report);
            var vHtml = (report.violations || []).map(renderViolation).join('');
            var incList = report.incomplete || [];
            var incHtml = incList.length ? '<h3 class="accordion-incomplete-title">Incomplete (' + incList.length + ')</h3>' + incList.map(renderIncomplete).join('') : '';
            return '<div class="accordion-body-violations">' + (vHtml ? '<h3 class="accordion-violations-title">Violations</h3><div class="accordion-violations-list">' + vHtml + '</div>' : '') + incHtml + '</div>';
          }

          function truncateUrl(u, max) {
            if (!u || u.length <= max) return u || '';
            return u.substring(0, max) + '…';
          }

          var resultsByUrl = {};
          var aggregate = (isResponsiveness || isContentQuality)
            ? { total: 0, passed: 0, failed: 0, warning: 0 }
            : { total: 0, passed: 0, violations: 0, incomplete: 0 };

          function updateSummaryCards() {
            el('pillar-total').textContent = aggregate.total;
            if (isResponsiveness || isContentQuality) {
              el('pillar-passed').textContent = aggregate.passed;
              el('pillar-failed').textContent = aggregate.failed;
              el('pillar-warnings').textContent = aggregate.warning;
            } else {
              el('pillar-passed').textContent = aggregate.passed;
              el('pillar-failed').textContent = aggregate.violations;
              el('pillar-warnings').textContent = aggregate.incomplete;
            }
            var totalRules = isResponsiveness
              ? (aggregate.passed + aggregate.failed + aggregate.warning)
              : (aggregate.passed + aggregate.violations + aggregate.incomplete);
            var score = totalRules ? Math.round((aggregate.passed / totalRules) * 100) : 0;
            var pct = totalRules ? Math.round((aggregate.passed / totalRules) * 100) : 0;
            el('pillar-page-score-ring').style.background = 'conic-gradient(' + scoreColor(score) + ' calc(' + score + ' * 1%), #e2e8f0 0)';
            el('pillar-page-score-value').textContent = score;
            el('pillar-pass-rate-bar').style.width = pct + '%';
            el('pillar-pass-rate-pct').textContent = pct + '%';
          }

          function openReportModal(url, report) {
            var modal = el('scan-report-modal');
            var titleEl = el('scan-report-modal-title');
            var bodyEl = modal && modal.querySelector('.scan-report-popup-body');
            if (!modal || !titleEl || !bodyEl) return;
            titleEl.textContent = url;
            if (!report) {
              bodyEl.innerHTML = '<div class="accordion-pending">Waiting to scan…</div>';
            } else if (report.error) {
              bodyEl.innerHTML = '<div class="accordion-error">' + escapeHtml(report.error) + '</div>';
            } else if (report.scanning) {
              bodyEl.innerHTML = '<div class="accordion-pending">Scanning…</div>';
            } else {
              bodyEl.innerHTML = reportDetailsHtml(report);
            }
            modal.style.display = 'flex';
            modal.setAttribute('aria-hidden', 'false');
          }

          function closeReportModal() {
            var modal = el('scan-report-modal');
            if (modal) {
              modal.style.display = 'none';
              modal.setAttribute('aria-hidden', 'true');
            }
          }

          function renderUrlList() {
            var html = '';
            for (var i = 0; i < allUrls.length; i++) {
              var u = allUrls[i];
              var r = resultsByUrl[u];
              var status = !r ? 'pending' : (r.error ? 'error' : 'done');
              var statusLabel = !r ? 'Pending' : (r.error ? 'Error' : 'Done');
              var summary = '';
              if (r && !r.error && r.summary) {
                var s = r.summary;
                if (isContentQuality) {
                  var cqOk = s.checks_passed || 0, cqFail = s.checks_failed || 0, iss = s.total_issues || 0;
                  summary = '<span class="summary-p">OK:' + cqOk + '</span> <span class="summary-v">Fail:' + cqFail + '</span> <span class="summary-i">Issues:' + iss + '</span>';
                } else if (isResponsiveness) {
                  var devOk = s.devices_passed || 0, devFail = s.devices_failed || 0, iss = s.total_issues || 0;
                  summary = '<span class="summary-p">OK:' + devOk + '</span> <span class="summary-v">Fail:' + devFail + '</span> <span class="summary-i">Issues:' + iss + '</span>';
                } else {
                  var v = s.violations_count || 0, p = s.passes_count || 0, inc = s.incomplete_count || 0;
                  summary = '<span class="summary-v">V:' + v + '</span> <span class="summary-p">P:' + p + '</span> <span class="summary-i">I:' + inc + '</span>';
                }
              } else if (r && r.error) {
                summary = '<span class="summary-error">' + escapeHtml(r.error) + '</span>';
              } else if (r && r.scanning) {
                statusLabel = 'Scanning…';
              }
              html += '<button type="button" class="url-row-item" data-url="' + escapeAttr(u) + '" data-idx="' + i + '">';
              html += '<span class="accordion-url" style="flex:1;min-width:0;word-break:break-all;font-family:monospace;font-size:0.875rem">' + escapeHtml(truncateUrl(u, 70)) + '</span>';
              html += '<span class="accordion-status status-' + status + '">' + escapeHtml(statusLabel) + '</span>';
              if (summary) html += '<span class="accordion-summary">' + summary + '</span>';
              html += '</button>';
            }
            urlListEl.innerHTML = html;
            urlListEl.querySelectorAll('.url-row-item').forEach(function (btn) {
              btn.addEventListener('click', function () {
                var url = btn.getAttribute('data-url');
                if (url) openReportModal(url, resultsByUrl[url]);
              });
            });
          }

          var allUrls = [];
          var scanPaused = false;
          var scanStopped = false;
          var lastSitemapSource = '';

          function showScanControls(show) {
            var ctrl = el('pillar-scan-controls');
            if (ctrl) ctrl.style.display = show ? 'flex' : 'none';
            var btnPause = el('btn-scan-pause');
            var btnPlay = el('btn-scan-play');
            if (btnPause) btnPause.style.display = (show && !scanPaused) ? 'inline-block' : 'none';
            if (btnPlay) btnPlay.style.display = (show && scanPaused) ? 'inline-block' : 'none';
          }

          function saveScanProgress(sitemapSource) {
            var toSave = {};
            for (var k in resultsByUrl) {
              var r = resultsByUrl[k];
              if (r && !r.scanning) toSave[k] = r;
            }
            fetch(API + '/' + apiBase + '/save-report', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                project_id: projectId,
                urls: allUrls,
                results: toSave,
                aggregate: aggregate,
                sitemap_source: sitemapSource || ''
              })
            }).catch(function () {});
          }

          var runScanNew = function () {
            var base = project.domain_url.trim();
            if (!base.startsWith('http')) base = 'https://' + base;
            btnScan.disabled = true;
            if (btnScanNew) btnScanNew.disabled = true;
            scanSection.style.display = 'block';
            urlListEl.innerHTML = '<div class="accordion-loading">Checking for new URLs…</div>';
            fetch(API + '/' + apiBase + '/sitemap-urls?url=' + encodeURIComponent(base))
              .then(function (res) { return res.json(); })
              .then(function (data) {
                if (data.error) {
                  btnScan.disabled = false;
                  if (btnScanNew) btnScanNew.disabled = false;
                  el('pillar-scan-summary').innerHTML = '<div class="summary-row violations"><strong>Error</strong>' + escapeHtml(data.error) + '</div>';
                  urlListEl.innerHTML = '';
                  return;
                }
                var sitemapUrls = data.urls || [];
                var existingSet = {};
                for (var i = 0; i < allUrls.length; i++) existingSet[allUrls[i]] = true;
                var newUrls = [];
                for (var j = 0; j < sitemapUrls.length; j++) {
                  if (!existingSet[sitemapUrls[j]]) newUrls.push(sitemapUrls[j]);
                }
                btnScan.disabled = false;
                if (btnScanNew) btnScanNew.disabled = false;
                if (newUrls.length === 0) {
                  el('pillar-scan-summary').innerHTML = '<div class="summary-row"><strong>No new URLs</strong> Sitemap has no URLs not already in the list.</div>';
                  urlListEl.innerHTML = '<div class="accordion-empty">No new URLs found in sitemap.</div>';
                  if (allUrls.length > 0) renderUrlList();
                  return;
                }
                allUrls = allUrls.concat(newUrls);
                lastSitemapSource = base + '/sitemap.xml';
                scanPaused = false;
                scanStopped = false;
                var src = lastSitemapSource || '—';
                el('pillar-scan-summary').innerHTML = '<div class="summary-row"><strong>URLs from sitemap</strong>' + allUrls.length + '</div><div class="summary-row"><strong>Source</strong> <span style="word-break:break-all">' + escapeHtml(src) + '</span></div><div class="summary-row"><strong>Scanning</strong> ' + newUrls.length + ' new URL(s)</div>';
                renderUrlList();
                btnScan.disabled = true;
                if (btnScanNew) btnScanNew.disabled = true;
                showScanControls(true);
                var idx = allUrls.length - newUrls.length;
                var startIdx = idx;
                scanNextRef = function scanNext() {
                  if (scanStopped) {
                    btnScan.disabled = false;
                    if (btnScanNew) btnScanNew.disabled = false;
                    btnScan.textContent = 'Scan';
                    showScanControls(false);
                    saveScanProgress(lastSitemapSource);
                    return;
                  }
                  if (scanPaused) return;
                  if (idx >= allUrls.length) {
                    btnScan.disabled = false;
                    if (btnScanNew) btnScanNew.disabled = false;
                    btnScan.textContent = 'Scan';
                    showScanControls(false);
                    saveScanProgress(lastSitemapSource);
                    return;
                  }
                  var url = allUrls[idx];
                  resultsByUrl[url] = { scanning: true };
                  renderUrlList();
                  fetch(API + '/' + apiBase + '/scan', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url: url })
                  })
                    .then(function (res) { return res.json(); })
                    .then(function (report) {
                      if (scanStopped) return;
                      var r = report.error ? { error: report.error } : report;
                      resultsByUrl[url] = r;
                      if (!report.error && report.summary) {
                        aggregate.total++;
                        if (isResponsiveness) {
                          var s = report.summary;
                          if ((s.devices_failed || 0) === 0 && (s.total_issues || 0) === 0) aggregate.passed++;
                          else aggregate.failed++;
                        } else if (isContentQuality) {
                          var s = report.summary;
                          if ((s.total_issues || 0) === 0) aggregate.passed++;
                          else aggregate.failed++;
                        } else {
                          aggregate.passed += report.summary.passes_count || 0;
                          aggregate.violations += report.summary.violations_count || 0;
                          aggregate.incomplete += report.summary.incomplete_count || 0;
                        }
                      }
                      updateSummaryCards();
                      renderUrlList();
                    })
                    .catch(function (err) {
                      if (scanStopped) return;
                      resultsByUrl[url] = { error: err.message || 'Scan failed' };
                      renderUrlList();
                    })
                    .finally(function () {
                      idx++;
                      if (!scanStopped) scanNextRef();
                    });
                };
                scanNextRef();
              })
              .catch(function (err) {
                btnScan.disabled = false;
                if (btnScanNew) btnScanNew.disabled = false;
                el('pillar-scan-summary').innerHTML = '<div class="summary-row violations"><strong>Error</strong>' + escapeHtml(err.message || 'Failed to fetch sitemap') + '</div>';
                urlListEl.innerHTML = '';
              });
          };

          var runScan = function () {
            btnScan.disabled = true;
            if (btnScanNew) btnScanNew.disabled = true;
            btnScan.textContent = 'Fetching sitemap…';
            scanSection.style.display = 'block';
            urlListEl.innerHTML = '<div class="accordion-loading">Fetching sitemap…</div>';
            var base = project.domain_url.trim();
            if (!base.startsWith('http')) base = 'https://' + base;
            fetch(API + '/' + apiBase + '/sitemap-urls?url=' + encodeURIComponent(base))
              .then(function (res) { return res.json(); })
              .then(function (data) {
                if (data.error) {
                  btnScan.disabled = false;
                  if (btnScanNew) btnScanNew.disabled = false;
                  el('pillar-scan-summary').innerHTML = '<div class="summary-row violations"><strong>Error</strong>' + escapeHtml(data.error) + '</div>';
                  urlListEl.innerHTML = '';
                  return;
                }
                allUrls = data.urls || [];
                resultsByUrl = {};
                aggregate = (isResponsiveness || isContentQuality) ? { total: 0, passed: 0, failed: 0, warning: 0 } : { total: 0, passed: 0, violations: 0, incomplete: 0 };
                lastSitemapSource = base + '/sitemap.xml';
                scanPaused = false;
                scanStopped = false;
                el('pillar-scan-summary').innerHTML = '<div class="summary-row"><strong>URLs from sitemap</strong>' + allUrls.length + '</div><div class="summary-row"><strong>Source</strong> <span style="word-break:break-all">' + escapeHtml(base + '/sitemap.xml') + '</span></div>';
                if (!allUrls.length) {
                  btnScan.disabled = false;
                  if (btnScanNew) btnScanNew.disabled = false;
                  showScanControls(false);
                  urlListEl.innerHTML = '<div class="accordion-empty">No URLs found in sitemap.</div>';
                  return;
                }
                btnScan.textContent = 'Scanning…';
                showScanControls(true);
                renderUrlList();
                var idx = 0;
                scanNextRef = function scanNext() {
                  if (scanStopped) {
                    btnScan.disabled = false;
                    if (btnScanNew) btnScanNew.disabled = false;
                    btnScan.textContent = 'Scan';
                    showScanControls(false);
                    saveScanProgress(lastSitemapSource);
                    return;
                  }
                  if (scanPaused) return;
                  if (idx >= allUrls.length) {
                    btnScan.disabled = false;
                    if (btnScanNew) btnScanNew.disabled = false;
                    btnScan.textContent = 'Scan';
                    showScanControls(false);
                    saveScanProgress(lastSitemapSource);
                    return;
                  }
                  var url = allUrls[idx];
                  resultsByUrl[url] = { scanning: true };
                  renderUrlList();
                  fetch(API + '/' + apiBase + '/scan', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url: url })
                  })
                    .then(function (res) { return res.json(); })
                    .then(function (report) {
                      if (scanStopped) return;
                      var r = report.error ? { error: report.error } : report;
                      resultsByUrl[url] = r;
                      if (!report.error && report.summary) {
                        aggregate.total++;
                        if (isResponsiveness) {
                          var s = report.summary;
                          if ((s.devices_failed || 0) === 0 && (s.total_issues || 0) === 0) aggregate.passed++;
                          else aggregate.failed++;
                        } else if (isContentQuality) {
                          var s = report.summary;
                          if ((s.total_issues || 0) === 0) aggregate.passed++;
                          else aggregate.failed++;
                        } else {
                          aggregate.passed += report.summary.passes_count || 0;
                          aggregate.violations += report.summary.violations_count || 0;
                          aggregate.incomplete += report.summary.incomplete_count || 0;
                        }
                      }
                      updateSummaryCards();
                      renderUrlList();
                    })
                    .catch(function (err) {
                      if (scanStopped) return;
                      resultsByUrl[url] = { error: err.message || 'Scan failed' };
                      renderUrlList();
                    })
                    .finally(function () {
                      idx++;
                      if (!scanStopped) scanNextRef();
                    });
                }
                scanNextRef();
              })
              .catch(function (err) {
                btnScan.disabled = false;
                if (btnScanNew) btnScanNew.disabled = false;
                el('pillar-scan-summary').innerHTML = '<div class="summary-row violations"><strong>Error</strong>' + escapeHtml(err.message || 'Failed to fetch sitemap') + '</div>';
                urlListEl.innerHTML = '';
              });
          };
          btnScanNew.addEventListener('click', runScanNew);
          var scanNextRef = null;
          fetch(API + '/' + apiBase + '/load-report?project_id=' + encodeURIComponent(projectId))
            .then(function (res) { return res.json(); })
            .then(function (data) {
              var urls = data.urls || [];
              if (urls.length > 0) {
                allUrls = urls;
                resultsByUrl = data.results || {};
                aggregate = data.aggregate || ((isResponsiveness || isContentQuality) ? { total: 0, passed: 0, failed: 0, warning: 0 } : { total: 0, passed: 0, violations: 0, incomplete: 0 });
                lastSitemapSource = data.sitemap_source || '';
                scanSection.style.display = 'block';
                var src = lastSitemapSource || '—';
                el('pillar-scan-summary').innerHTML = '<div class="summary-row"><strong>URLs from sitemap</strong>' + urls.length + '</div><div class="summary-row"><strong>Source</strong> <span style="word-break:break-all">' + escapeHtml(src) + '</span></div><div class="summary-row"><strong>Last saved</strong> ' + escapeHtml(data.timestamp || '') + '</div>';
                updateSummaryCards();
                renderUrlList();
              }
            })
            .catch(function () {});
          btnScan.addEventListener('click', runScan);
          el('btn-scan-pause').addEventListener('click', function () { scanPaused = true; showScanControls(true); saveScanProgress(lastSitemapSource); });
          el('btn-scan-play').addEventListener('click', function () { scanPaused = false; showScanControls(true); if (scanNextRef) scanNextRef(); });
          el('btn-scan-stop').addEventListener('click', function () { scanStopped = true; showScanControls(false); btnScan.disabled = false; btnScan.textContent = 'Scan'; if (btnScanNew) btnScanNew.disabled = false; saveScanProgress(lastSitemapSource); });
          el('scan-report-modal').addEventListener('click', function (e) {
            if (e.target === el('scan-report-modal')) closeReportModal();
          });
          el('scan-report-modal').querySelector('.scan-report-close').addEventListener('click', closeReportModal);
          var customTestsModal = el('custom-tests-modal');
          var customTestsContent = [
            { id: 'tab-focus-visible-text', name: 'Tab focus on visible text', desc: 'Tab focus should reach all visible text elements (headings h1–h6, paragraphs, images with alt) for keyboard navigation.', fix: 'Add tabindex="0" to make them reachable via Tab, or ensure content is within focusable containers.', helpUrl: 'https://www.w3.org/WAI/WCAG21/Understanding/keyboard.html' }
          ];
          var contentQualityInfoHtml = '<div class="custom-test-card"><h3 class="custom-test-name">Checks performed</h3><ul style="margin:8px 0;padding-left:20px;line-height:1.6"><li><strong>Broken links</strong> — Anchors returning 4xx/5xx (major)</li><li><strong>Broken images/media</strong> — Failed to load or naturalWidth=0 (major)</li><li><strong>Empty content blocks</strong> — Headings/paragraphs with no text (moderate)</li><li><strong>Duplicate content</strong> — Editorial/label only. Component patterns shown as informational.</li><li><strong>Truncated text</strong> — Real clipping only. Design-intent overflow, overlay, ellipsis/line-clamp shown as informational or minor.</li><li><strong>Placeholder content</strong> — lorem ipsum, sample text, etc. (minor)</li></ul></div><div class="custom-test-card"><h3 class="custom-test-name">Duplicate classification</h3><p class="custom-test-desc"><strong>Component</strong> — Repeated UI (cards, lists, nav) → informational only. <strong>Label</strong> — Short text (≤5 words) → minor. <strong>Editorial</strong> — Duplicate across sections or long content → moderate/major.</p></div><div class="custom-test-card"><h3 class="custom-test-name">Status labels</h3><p class="custom-test-desc"><strong>OK</strong> — Checks that passed. <strong>Fail</strong> — Checks with issues. Component duplicates do not count as failures.</p></div>';
          var responsivenessInfoHtml = '<div class="custom-test-card"><h3 class="custom-test-name">Devices tested</h3><p class="custom-test-desc">Each URL is tested at three viewport sizes:</p><ul style="margin:8px 0;padding-left:20px;line-height:1.6"><li><strong>Mobile</strong> — 375×667 px</li><li><strong>Tablet</strong> — 768×1024 px</li><li><strong>Desktop</strong> — 1920×1080 px</li></ul></div>' +
            '<div class="custom-test-card"><h3 class="custom-test-name">Status labels (per URL)</h3><p class="custom-test-desc"><strong>OK</strong> — Number of device viewports with no issues (0–3). If OK:0, all three viewports had at least one finding.</p><p class="custom-test-desc"><strong>Fail</strong> — Number of device viewports that had at least one issue.</p><p class="custom-test-desc"><strong>Issues</strong> — Total number of issue findings across all viewports (e.g. horizontal overflow, touch targets, viewport meta).</p></div>' +
            '<div class="custom-test-card"><h3 class="custom-test-name">Checks performed</h3><ul style="margin:8px 0;padding-left:20px;line-height:1.6"><li>Horizontal overflow (content wider than viewport)</li><li>Viewport meta tag</li><li>Touch target size (44×44 px minimum, WCAG 2.5.5)</li><li>Layout overlap (sibling elements overlapping)</li><li>Hidden content (overflow:hidden clipping content)</li><li>Element clipping (elements extending beyond viewport)</li><li>Grid breakage (CSS Grid items overflowing)</li><li>Component collapse (flex items overly narrow)</li></ul><p class="custom-test-desc">Screenshots with red markers are captured when issues are found. Each issue links to the relevant standard.</p></div>';
          function openCustomTestsModal() {
            if (!customTestsModal) return;
            var titleEl = el('custom-tests-modal-title');
            if (titleEl) titleEl.textContent = isContentQuality ? 'Content Quality scan info' : (isResponsiveness ? 'Responsiveness scan info' : 'Custom test cases');
            var body = el('custom-tests-modal-body');
            if (body) {
              if (isContentQuality) {
                body.innerHTML = contentQualityInfoHtml;
              } else if (isResponsiveness) {
                body.innerHTML = responsivenessInfoHtml;
              } else {
                body.innerHTML = customTestsContent.map(function (t) {
                  return '<div class="custom-test-card"><h3 class="custom-test-name">' + escapeHtml(t.name) + '</h3><p class="custom-test-desc">' + escapeHtml(t.desc) + '</p><p class="custom-test-fix"><strong>Fix:</strong> ' + escapeHtml(t.fix) + '</p>' + (t.helpUrl ? '<a href="' + escapeHtml(t.helpUrl) + '" target="_blank" rel="noopener">Learn more</a>' : '') + '</div>';
                }).join('');
              }
            }
            customTestsModal.style.display = 'flex';
            customTestsModal.setAttribute('aria-hidden', 'false');
          }
          function closeCustomTestsModal() {
            if (customTestsModal) { customTestsModal.style.display = 'none'; customTestsModal.setAttribute('aria-hidden', 'true'); }
          }
          if (btnInfo) btnInfo.addEventListener('click', openCustomTestsModal);
          customTestsModal && customTestsModal.addEventListener('click', function (e) { if (e.target === customTestsModal) closeCustomTestsModal(); });
          var customTestsCloseBtn = customTestsModal && customTestsModal.querySelector('.custom-tests-close');
          if (customTestsCloseBtn) customTestsCloseBtn.addEventListener('click', closeCustomTestsModal);
          if (window.location.search.indexOf('run=1') !== -1) {
            history.replaceState(null, '', window.location.pathname + window.location.hash);
            runScan();
          }
        }
      }
    })
    .catch(function (err) {
      showLoading(false);
      showError(err.message || 'Failed to load.');
    });
})();
