(function () {
  const API = '/api';
  const pathParts = window.location.pathname.split('/').filter(Boolean);
  const projectId = pathParts[pathParts.length - 1];

  const el = (id) => document.getElementById(id);
  const loading = el('detail-loading');
  const errorEl = el('detail-error');
  const content = el('detail-content');
  const pillarsGrid = el('pillars-grid');

  function showLoading(show) {
    loading.style.display = show ? 'block' : 'none';
  }
  function showError(msg) {
    errorEl.textContent = msg || '';
    errorEl.style.display = msg ? 'block' : 'none';
  }
  function showContent(show) {
    content.style.display = show ? 'block' : 'none';
  }

  function formatDate(iso) {
    const d = new Date(iso);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  }
  function scoreColor(score) {
    if (score >= 90) return '#22c55e';
    if (score >= 80) return '#0d9488';
    if (score >= 70) return '#3b82f6';
    return '#f59e0b';
  }

  function escapeHtml(s) {
    const div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
  }

  if (!projectId) {
    showLoading(false);
    showError('Project not found.');
    return;
  }

  fetch(API + '/projects/' + encodeURIComponent(projectId))
    .then(function (res) {
      if (!res.ok) throw new Error('Project not found');
      return res.json();
    })
    .then(function (data) {
      showLoading(false);
      showError('');
      showContent(true);

      document.title = escapeHtml(data.name) + ' - QA Studio';

      el('detail-name').textContent = data.name;
      el('detail-url').textContent = data.domain_url;
      el('detail-url').href = data.domain_url;
      el('detail-url').target = '_blank';
      el('detail-phase').textContent = data.phase;
      el('detail-phase').className = 'badge badge-' + (data.phase === 'Live' ? 'live' : data.phase === 'Test Link' ? 'test' : 'dev');

      const score = data.qa_score;
      const color = scoreColor(score);
      el('detail-score-ring').style.background = 'conic-gradient(' + color + ' calc(' + score + ' * 1%), #e2e8f0 0)';
      el('detail-score-value').textContent = score;

      const pillars = data.pillars || [];
      pillarsGrid.innerHTML = pillars.map(function (p) {
        const color = scoreColor(p.score);
        const slug = p.slug || ('pillar-' + p.name.toLowerCase().replace(/\s+/g, '-').replace(/\//g, '-'));
        const pillarUrl = '/project/' + encodeURIComponent(data.id) + '/pillar/' + encodeURIComponent(slug);
        return (
          '<a href="' + escapeHtml(pillarUrl) + '" class="pillar-card pillar-card-link">' +
          '<div class="pillar-header">' +
          '<span class="pillar-name">' + escapeHtml(p.name) + '</span>' +
          '<div class="pillar-header-right">' +
          '<button type="button" class="pillar-play-btn" title="Run QA" data-pillar-slug="' + escapeHtml(slug) + '">&#9654;</button>' +
          '<div class="pillar-score-ring" style="--score:' + p.score + ';--score-color:' + color + '"></div>' +
          '</div></div>' +
          '<div class="pillar-score ' + (p.score >= 90 ? 'score-high' : p.score >= 80 ? 'score-mid' : '') + '">' + p.score + '/100</div>' +
          '<div class="pillar-checks">' +
          '<span class="check passed">&#10003; ' + p.passed + '</span> ' +
          '<span class="check failed">&#215; ' + p.failed + '</span> ' +
          '<span class="check warning">&#9650; ' + p.warning + '</span>' +
          '</div>' +
          '<div class="pillar-date">Last run: ' + formatDate(p.last_run) + '</div>' +
          '</a>'
        );
      }).join('');

      pillarsGrid.querySelectorAll('.pillar-play-btn').forEach(function (btn) {
        btn.addEventListener('click', function (e) {
          e.preventDefault();
          e.stopPropagation();
          var slug = btn.getAttribute('data-pillar-slug');
          var pillarName = (pillars.find(function (p) { return (p.slug || '') === slug; }) || {}).name || slug;
          alert('Run QA for pillar: ' + pillarName);
        });
      });
    })
    .catch(function (err) {
      showLoading(false);
      showError(err.message || 'Failed to load project');
    });
})();
