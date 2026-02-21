(function () {
  const BASE = '/qa-studio';
  const API = BASE + '/api';
  let allProjects = [];

  const el = (id) => document.getElementById(id);
  const loading = el('loading');
  const table = el('project-table');
  const tbody = el('project-tbody');
  const empty = el('empty');
  const errorBanner = el('error-banner');
  const projectCount = el('project-count');
  const searchInput = el('search');
  const phaseFilter = el('phase-filter');
  const modalBackdrop = el('modal-backdrop');
  const modalClose = el('modal-close');
  const modalError = el('modal-error');
  const formNew = el('form-new-project');
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

  function formatDate(iso) {
    const d = new Date(iso);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  }
  function scoreColor(score) {
    if (score >= 85) return 'var(--score-high)';
    if (score >= 70) return 'var(--score-mid)';
    return 'var(--score-low)';
  }
  function badgeClass(phase) {
    if (phase === 'Live') return 'badge-live';
    if (phase === 'Test Link') return 'badge-test';
    return 'badge-dev';
  }

  async function fetchProjects() {
    const phase = phaseFilter.value || '';
    const url = phase ? API + '/projects?phase=' + encodeURIComponent(phase) : API + '/projects';
    const res = await fetch(url);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || res.statusText);
    }
    return res.json();
  }

  function renderTable(projects) {
    const search = (searchInput.value || '').trim().toLowerCase();
    const list = search
      ? projects.filter(function (p) {
          return p.name.toLowerCase().includes(search) || p.domain_url.toLowerCase().includes(search);
        })
      : projects;

    projectCount.textContent = list.length + ' project' + (list.length !== 1 ? 's' : '');

    if (list.length === 0) {
      setTableVisible(false);
      return;
    }
    setTableVisible(true);

    tbody.innerHTML = list.map(function (p) {
      const color = scoreColor(p.qa_score);
      const badge = badgeClass(p.phase);
      const projectLink = BASE + '/project/' + encodeURIComponent(p.id);
      return (
        '<tr data-project-href="' + escapeHtml(projectLink) + '" class="project-row">' +
        '<td class="cell-project"><div class="project-name">' + escapeHtml(p.name) + '</div><div class="project-url">' + escapeHtml(p.domain_url) + '</div></td>' +
        '<td><span class="badge ' + badge + '">' + escapeHtml(p.phase) + '</span></td>' +
        '<td><div class="score-cell"><div class="score-ring" style="--score:' + p.qa_score + ';--score-color:' + color + '"></div><span class="score-text">' + p.qa_score + '/100</span></div></td>' +
        '<td class="cell-date">' + formatDate(p.last_run) + '</td>' +
        '<td class="cell-actions"><div class="actions">' +
        '<button type="button" class="action-btn action-btn-play" title="Run QA" data-run-id="' + escapeHtml(p.id) + '">&#9654;</button>' +
        '<a href="' + escapeHtml(projectLink) + '" class="action-btn" title="View details">&#8505;</a>' +
        '<a href="' + escapeHtml(p.domain_url) + '" target="_blank" rel="noopener" class="action-btn" title="Open URL">🔗</a>' +
        '<button type="button" class="action-btn" title="Delete" data-delete-id="' + escapeHtml(p.id) + '">🗑</button>' +
        '</div></td>' +
        '</tr>'
      );
    }).join('');

    tbody.querySelectorAll('[data-run-id]').forEach(function (btn) {
      btn.addEventListener('click', function (e) {
        e.stopPropagation();
        var id = btn.getAttribute('data-run-id');
        runProject(id);
      });
    });
    tbody.querySelectorAll('[data-delete-id]').forEach(function (btn) {
      btn.addEventListener('click', function (e) {
        e.stopPropagation();
        const id = btn.getAttribute('data-delete-id');
        if (confirm('Delete this project?')) deleteProject(id);
      });
    });
  }

  function runProject(id) {
    // Placeholder: run QA for this project (e.g. call API or show message)
    var p = allProjects.find(function (x) { return x.id === id; });
    if (p) alert('Run QA for: ' + (p.name || id));
  }

  function escapeHtml(s) {
    const div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
  }

  function loadProjects() {
    showError('');
    showLoading(true);
    fetchProjects()
      .then(function (data) {
        allProjects = data;
        renderTable(data);
      })
      .catch(function (err) {
        showError(err.message || 'Failed to load projects');
        setTableVisible(false);
      })
      .finally(function () {
        showLoading(false);
      });
  }

  function deleteProject(id) {
    fetch(API + '/projects/' + encodeURIComponent(id), { method: 'DELETE' })
      .then(function (res) {
        if (!res.ok) throw new Error('Delete failed');
        loadProjects();
      })
      .catch(function (err) {
        showError(err.message || 'Failed to delete');
      });
  }

  function openModal() {
    modalError.style.display = 'none';
    modalError.textContent = '';
    formNew.reset();
    modalBackdrop.style.display = 'flex';
  }
  function closeModal() {
    modalBackdrop.style.display = 'none';
  }

  formNew.addEventListener('submit', function (e) {
    e.preventDefault();
    const name = el('project-name').value.trim();
    const domainUrl = el('domain-url').value.trim();
    const phase = el('phase').value;
    if (!domainUrl) return;
    btnCreate.disabled = true;
    modalError.style.display = 'none';
    fetch(API + '/projects', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: name, domain_url: domainUrl, phase: phase })
    })
      .then(function (res) {
        return res.json().then(function (data) {
          if (!res.ok) throw new Error(data.detail || res.statusText);
          closeModal();
          loadProjects();
        });
      })
      .catch(function (err) {
        modalError.textContent = err.message || 'Failed to create project';
        modalError.style.display = 'block';
      })
      .finally(function () {
        btnCreate.disabled = false;
      });
  });

  el('btn-new-project').addEventListener('click', openModal);
  modalClose.addEventListener('click', closeModal);
  modalBackdrop.addEventListener('click', function (e) {
    if (e.target === modalBackdrop) closeModal();
  });
  searchInput.addEventListener('input', function () { renderTable(allProjects); });
  phaseFilter.addEventListener('change', loadProjects);

  tbody.addEventListener('click', function (e) {
    var tr = e.target.closest('tr.project-row');
    if (!tr) return;
    var href = tr.getAttribute('data-project-href');
    if (!href) return;
    if (e.target.closest('.actions')) return;
    window.location = href;
  });

  loadProjects();
})();
