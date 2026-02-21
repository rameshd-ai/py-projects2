(function () {
  const BASE = '/qa-studio';
  const API = BASE + '/api';
  const pathParts = window.location.pathname.split('/').filter(Boolean);
  // URL: /qa-studio/project/<projectId>  => pathParts[0]=qa-studio, [1]=project, [2]=id
  const projectId = pathParts.length >= 3 && pathParts[0] === 'qa-studio' && pathParts[1] === 'project'
    ? pathParts[2] : null;

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
      var urlEl = el('detail-url');
      urlEl.innerHTML = '<a href="' + escapeHtml(data.domain_url) + '" target="_blank" rel="noopener">' + escapeHtml(data.domain_url) + '</a>';
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
        var pillarUrl = BASE + '/project/' + encodeURIComponent(data.id) + '/pillar/' + encodeURIComponent(slug);
        var enabled = p.enabled !== false;
        var tag = enabled ? 'a' : 'div';
        var attrs = enabled ? ' href="' + escapeHtml(pillarUrl) + '" class="pillar-card pillar-card-link"' : ' class="pillar-card pillar-card-disabled"';
        var playBtn = enabled ? '<button type="button" class="pillar-play-btn" title="Run QA" data-pillar-slug="' + escapeHtml(slug) + '">&#9654;</button>' : '<span class="pillar-play-placeholder"></span>';
        return (
          '<' + tag + attrs + '>' +
          '<div class="pillar-header">' +
          '<span class="pillar-name">' + escapeHtml(p.name) + '</span>' +
          '<div class="pillar-header-right">' + playBtn +
          '<div class="pillar-score-ring" style="--score:' + p.score + ';--score-color:' + color + '"></div>' +
          '</div></div>' +
          '<div class="pillar-score ' + (p.score >= 90 ? 'score-high' : p.score >= 80 ? 'score-mid' : '') + '">' + p.score + '/100</div>' +
          '<div class="pillar-checks">' +
          '<span class="check passed">&#10003; ' + p.passed + '</span> ' +
          '<span class="check failed">&#215; ' + p.failed + '</span> ' +
          '<span class="check warning">&#9650; ' + p.warning + '</span>' +
          '</div>' +
          '<div class="pillar-date">Last run: ' + formatDate(p.last_run) + '</div>' +
          '</' + tag + '>'
        );
      }).join('');

      pillarsGrid.querySelectorAll('.pillar-play-btn').forEach(function (btn) {
        btn.addEventListener('click', function (e) {
          e.preventDefault();
          e.stopPropagation();
          var slug = btn.getAttribute('data-pillar-slug');
          var pillar = pillars.find(function (p) { return (p.slug || '') === slug; }) || {};
          if (slug === 'ada-accessibility' || slug === 'responsiveness' || slug === 'content-quality') {
            window.location.href = BASE + '/project/' + encodeURIComponent(data.id) + '/pillar/' + encodeURIComponent(slug) + '?run=1';
          } else if (pillar.enabled !== false) {
            window.location.href = BASE + '/project/' + encodeURIComponent(data.id) + '/pillar/' + encodeURIComponent(slug);
          } else {
            alert('Coming soon: ' + (pillar.name || slug));
          }
        });
      });
    })
    .catch(function (err) {
      showLoading(false);
      showError(err.message || 'Failed to load project');
    });
})();
