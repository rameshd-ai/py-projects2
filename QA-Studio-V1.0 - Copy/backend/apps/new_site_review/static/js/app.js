(function () {
  const BASE = '/new-site-review';
  const API = BASE + '/api';
  let allSites = [];
  let ga4Configured = false;

  const el = (id) => document.getElementById(id);
  const loading = el('loading');
  const table = el('site-table');
  const tbody = el('site-tbody');
  const empty = el('empty');
  const errorBanner = el('error-banner');
  const siteCount = el('site-count');
  const modalBackdrop = el('modal-backdrop');
  const modalClose = el('modal-close');
  const modalError = el('modal-error');
  const formNew = el('form-new-site');
  const btnCreate = el('btn-create');

  function showLoading(show) {
    loading.style.display = show ? 'block' : 'none';
  }
  function showError(msg) {
    errorBanner.textContent = msg || '';
    errorBanner.style.display = msg ? 'block' : 'none';
  }
  function setTableVisible(show) {
    table.style.display = show ? 'table' : 'none';
    empty.style.display = !show ? 'block' : 'none';
  }

  function escapeHtml(s) {
    var div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
  }

  function toast(message, type) {
    var container = el('toast-container');
    if (!container) return;
    var t = document.createElement('div');
    t.className = 'toast ' + (type || 'success');
    t.setAttribute('role', 'alert');
    t.textContent = message;
    container.appendChild(t);
    setTimeout(function () {
      if (t.parentNode) t.parentNode.removeChild(t);
    }, 4000);
  }

  function fetchSites() {
    return fetch(API + '/sites').then(function (res) {
      if (!res.ok) throw new Error(res.statusText);
      return res.json();
    });
  }

  function fetchGA4Settings() {
    return fetch(API + '/settings/ga4').then(function (res) {
      if (!res.ok) throw new Error(res.statusText);
      return res.json();
    });
  }

  function renderTable(sites) {
    siteCount.textContent = sites.length + ' site' + (sites.length !== 1 ? 's' : '');
    if (sites.length === 0) {
      setTableVisible(false);
      return;
    }
    setTableVisible(true);
    var playDisabled = !ga4Configured ? ' disabled' : '';
    var playTitle = ga4Configured ? 'Run' : 'Configure GA4 in Settings to run';
    tbody.innerHTML = sites.map(function (s) {
      var statusHtml = '';
      if (s.scan_status === 'success' && s.last_scan_at) {
        statusHtml = ' <span class="scan-status success">Scanned</span>';
      } else if (s.scan_status === 'failed') {
        statusHtml = ' <span class="scan-status failed">Failed</span>';
      } else if (s.scan_status === 'running') {
        statusHtml = ' <span class="scan-status running">Running…</span>';
      } else if (s.scan_status) {
        statusHtml = ' <span class="scan-status pending">' + escapeHtml(s.scan_status) + '</span>';
      }
      return (
        '<tr data-site-id="' + escapeHtml(s.id) + '">' +
        '<td class="cell-project"><div class="project-name">' + escapeHtml(s.name) + statusHtml + '</div></td>' +
        '<td><div class="project-url">' + escapeHtml(s.live_url) + '</div></td>' +
        '<td><select class="type-select" data-site-id="' + escapeHtml(s.id) + '" data-site-type>' +
        '<option value="External"' + (s.site_type === 'External' ? ' selected' : '') + '>External</option>' +
        '<option value="Milestone"' + (s.site_type === 'Milestone' ? ' selected' : '') + '>Milestone</option>' +
        '</select></td>' +
        '<td class="cell-actions"><div class="actions">' +
        '<button type="button" class="action-btn action-btn-play' + playDisabled + '" title="' + playTitle + '" data-run-id="' + escapeHtml(s.id) + '">&#9654;</button>' +
        '<a href="' + escapeHtml(s.live_url) + '" target="_blank" rel="noopener" class="action-btn" title="Open URL">&#128279;</a>' +
        '<button type="button" class="action-btn" title="Delete" data-delete-id="' + escapeHtml(s.id) + '">&#128465;</button>' +
        '</div></td></tr>'
      );
    }).join('');

    tbody.querySelectorAll('.type-select').forEach(function (sel) {
      sel.addEventListener('change', function () {
        var id = sel.getAttribute('data-site-id');
        var value = sel.value;
        fetch(API + '/sites/' + encodeURIComponent(id), {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ site_type: value })
        }).then(function (res) {
          if (!res.ok) throw new Error('Update failed');
          var site = allSites.find(function (x) { return x.id === id; });
          if (site) site.site_type = value;
        }).catch(function () {
          showError('Failed to update type');
        });
      });
    });
    tbody.querySelectorAll('[data-run-id]').forEach(function (btn) {
      if (btn.disabled) return;
      btn.addEventListener('click', function () {
        var id = btn.getAttribute('data-run-id');
        var site = allSites.find(function (x) { return x.id === id; });
        if (site) runSite(site, btn);
      });
    });
    tbody.querySelectorAll('[data-delete-id]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var id = btn.getAttribute('data-delete-id');
        if (confirm('Delete this site?')) deleteSite(id);
      });
    });
  }

  function runSite(site, playBtn) {
    if (!ga4Configured) {
      toast('Configure GA4 in Settings first', 'error');
      return;
    }
    if (playBtn) {
      playBtn.disabled = true;
      playBtn.textContent = '…';
    }
    var row = tbody.querySelector('[data-site-id="' + site.id + '"]');
    var statusEl = row ? row.querySelector('.scan-status') : null;
    if (statusEl) {
      statusEl.className = 'scan-status running';
      statusEl.textContent = 'Running…';
    }
    fetch(API + '/sites/' + encodeURIComponent(site.id) + '/run', { method: 'POST' })
      .then(function (res) {
        return res.json().then(function (data) {
          if (!res.ok) throw new Error(data.detail || res.statusText);
          var s = allSites.find(function (x) { return x.id === site.id; });
          if (s) {
            s.scan_status = data.scan_status;
            s.last_scan_at = data.last_scan_at;
            s.ga4_results = data.ga4_results;
          }
          renderTable(allSites);
          toast('Scan completed for ' + site.name, 'success');
        });
      })
      .catch(function (err) {
        if (statusEl) {
          statusEl.className = 'scan-status failed';
          statusEl.textContent = 'Failed';
        }
        if (playBtn) {
          playBtn.disabled = false;
          playBtn.textContent = '\u9654';
        }
        toast(err.message || 'Scan failed', 'error');
      });
  }

  function loadSites() {
    showError('');
    showLoading(true);
    fetchSites()
      .then(function (data) {
        allSites = data;
        renderTable(data);
      })
      .catch(function (err) {
        showError(err.message || 'Failed to load sites');
        setTableVisible(false);
      })
      .finally(function () {
        showLoading(false);
      });
  }

  function loadGA4AndSites() {
    fetchGA4Settings()
      .then(function (data) {
        ga4Configured = !!data.configured;
        loadSites();
      })
      .catch(function () {
        ga4Configured = false;
        loadSites();
      });
  }

  function deleteSite(id) {
    fetch(API + '/sites/' + encodeURIComponent(id), { method: 'DELETE' })
      .then(function (res) {
        if (!res.ok) throw new Error('Delete failed');
        loadSites();
      })
      .catch(function (err) {
        showError(err.message || 'Failed to delete');
      });
  }

  function openModal() {
    modalError.style.display = 'none';
    modalError.textContent = '';
    formNew.reset();
    el('site-type').value = 'External';
    modalBackdrop.style.display = 'flex';
  }
  function closeModal() {
    modalBackdrop.style.display = 'none';
  }

  formNew.addEventListener('submit', function (e) {
    e.preventDefault();
    var name = el('site-name').value.trim();
    var liveUrl = el('live-url').value.trim();
    var siteType = el('site-type').value;
    if (!name || !liveUrl) return;
    btnCreate.disabled = true;
    modalError.style.display = 'none';
    fetch(API + '/sites', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: name, live_url: liveUrl, site_type: siteType })
    })
      .then(function (res) {
        return res.json().then(function (data) {
          if (!res.ok) throw new Error(data.detail || res.statusText);
          closeModal();
          toast('Site added', 'success');
          loadSites();
        });
      })
      .catch(function (err) {
        modalError.textContent = err.message || 'Failed to add site';
        modalError.style.display = 'block';
      })
      .finally(function () {
        btnCreate.disabled = false;
      });
  });

  el('btn-new-site').addEventListener('click', openModal);
  modalClose.addEventListener('click', closeModal);
  modalBackdrop.addEventListener('click', function (e) {
    if (e.target === modalBackdrop) closeModal();
  });

  // ---- GA4 Settings modal ----
  var settingsBackdrop = el('settings-modal-backdrop');
  var settingsClose = el('settings-modal-close');
  var ga4PropertyId = el('ga4-property-id');
  var credentialsType = el('credentials-type');
  var serviceAccountGroup = el('service-account-group');
  var serviceAccountJson = el('service-account-json');
  var serviceAccountFile = el('service-account-file');
  var ga4PropertyIdError = el('ga4-property-id-error');
  var serviceAccountJsonError = el('service-account-json-error');
  var settingsModalError = el('settings-modal-error');
  var settingsTestResult = el('settings-test-result');
  var btnTestConnection = el('btn-test-connection');
  var btnSettingsCancel = el('btn-settings-cancel');
  var btnSettingsSave = el('btn-settings-save');
  var settingsHasExistingSA = false;

  function openSettingsModal() {
    settingsModalError.style.display = 'none';
    settingsTestResult.style.display = 'none';
    ga4PropertyIdError.textContent = '';
    serviceAccountJsonError.textContent = '';
    fetchGA4Settings().then(function (data) {
      ga4PropertyId.value = data.ga4_property_id || '';
      credentialsType.value = data.credentials_type || 'OAuth';
      serviceAccountJson.value = '';
      settingsHasExistingSA = !!data.has_service_account_json;
      if (credentialsType.value === 'Service Account') {
        serviceAccountGroup.style.display = 'block';
        serviceAccountJson.placeholder = settingsHasExistingSA ? '(saved – leave blank to keep)' : 'Paste JSON content or upload file below';
      } else {
        serviceAccountGroup.style.display = 'none';
      }
      settingsBackdrop.style.display = 'flex';
    }).catch(function () {
      ga4PropertyId.value = '';
      credentialsType.value = 'OAuth';
      serviceAccountGroup.style.display = 'none';
      settingsHasExistingSA = false;
      settingsBackdrop.style.display = 'flex';
    });
  }

  function closeSettingsModal() {
    settingsBackdrop.style.display = 'none';
  }

  credentialsType.addEventListener('change', function () {
    if (credentialsType.value === 'Service Account') {
      serviceAccountGroup.style.display = 'block';
    } else {
      serviceAccountGroup.style.display = 'none';
      serviceAccountJsonError.textContent = '';
    }
  });

  serviceAccountFile.addEventListener('change', function () {
    var f = serviceAccountFile.files[0];
    if (!f) return;
    var r = new FileReader();
    r.onload = function () {
      try {
        var j = JSON.parse(r.result);
        serviceAccountJson.value = JSON.stringify(j, null, 2);
        serviceAccountJsonError.textContent = '';
      } catch (e) {
        serviceAccountJsonError.textContent = 'Invalid JSON file';
      }
    };
    r.readAsText(f);
    serviceAccountFile.value = '';
  });

  function validateGA4Form() {
    var ok = true;
    ga4PropertyIdError.textContent = '';
    serviceAccountJsonError.textContent = '';
    var pid = (ga4PropertyId.value || '').trim();
    if (!pid) {
      ga4PropertyIdError.textContent = 'GA4 Property ID is required';
      ok = false;
    } else if (!/^\d{8,}$/.test(pid)) {
      ga4PropertyIdError.textContent = 'Must be numeric (8+ digits)';
      ok = false;
    }
    if (credentialsType.value === 'Service Account') {
      var sa = (serviceAccountJson.value || '').trim();
      if (!sa) {
        serviceAccountJsonError.textContent = 'Service Account JSON is required';
        ok = false;
      } else {
        try {
          JSON.parse(sa);
        } catch (e) {
          serviceAccountJsonError.textContent = 'Invalid JSON';
          ok = false;
        }
      }
    }
    return ok;
  }

  btnTestConnection.addEventListener('click', function () {
    settingsTestResult.style.display = 'none';
    ga4PropertyIdError.textContent = '';
    var pid = (ga4PropertyId.value || '').trim();
    if (!pid) {
      ga4PropertyIdError.textContent = 'GA4 Property ID is required';
      return;
    }
    if (!/^\d{8,}$/.test(pid)) {
      ga4PropertyIdError.textContent = 'Must be numeric (8+ digits)';
      return;
    }
    if (credentialsType.value === 'Service Account' && !(serviceAccountJson.value || '').trim()) {
      serviceAccountJsonError.textContent = 'Service Account JSON is required for test';
      return;
    }
    btnTestConnection.disabled = true;
    fetch(API + '/settings/ga4/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ga4_property_id: pid,
        credentials_type: credentialsType.value,
        service_account_json: credentialsType.value === 'Service Account' ? (serviceAccountJson.value || '').trim() : undefined
      })
    })
      .then(function (res) {
        return res.json().then(function (data) {
          settingsTestResult.style.display = 'block';
          if (data.success) {
            settingsTestResult.className = 'test-result success';
            settingsTestResult.textContent = data.message || 'Connection successful';
          } else {
            settingsTestResult.className = 'test-result error';
            settingsTestResult.textContent = data.message || 'Connection failed';
          }
        });
      })
      .catch(function () {
        settingsTestResult.style.display = 'block';
        settingsTestResult.className = 'test-result error';
        settingsTestResult.textContent = 'Connection test failed';
      })
      .finally(function () {
        btnTestConnection.disabled = false;
      });
  });

  btnSettingsSave.addEventListener('click', function () {
    settingsModalError.style.display = 'none';
    if (!validateGA4Form()) return;
    var payload = {
      ga4_property_id: (ga4PropertyId.value || '').trim(),
      credentials_type: credentialsType.value
    };
    if (credentialsType.value === 'Service Account') {
      var sa = (serviceAccountJson.value || '').trim();
      if (sa) payload.service_account_json = sa;
      else if (!settingsHasExistingSA) {
        serviceAccountJsonError.textContent = 'Service Account JSON is required';
        return;
      }
    }
    btnSettingsSave.disabled = true;
    fetch(API + '/settings/ga4', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
      .then(function (res) {
        return res.json().then(function (data) {
          if (!res.ok) throw new Error(data.detail || 'Save failed');
          ga4Configured = !!data.configured;
          closeSettingsModal();
          toast('Settings saved', 'success');
          renderTable(allSites);
        });
      })
      .catch(function (err) {
        settingsModalError.textContent = err.message || 'Failed to save';
        settingsModalError.style.display = 'block';
      })
      .finally(function () {
        btnSettingsSave.disabled = false;
      });
  });

  btnSettingsCancel.addEventListener('click', closeSettingsModal);
  settingsClose.addEventListener('click', closeSettingsModal);
  settingsBackdrop.addEventListener('click', function (e) {
    if (e.target === settingsBackdrop) closeSettingsModal();
  });

  el('btn-settings').addEventListener('click', openSettingsModal);

  loadGA4AndSites();
})();
