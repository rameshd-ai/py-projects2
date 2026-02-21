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

      el('pillar-total').textContent = pillar.total || (pillar.passed + pillar.failed + pillar.warning);
      el('pillar-passed').textContent = pillar.passed;
      el('pillar-failed').textContent = pillar.failed;
      el('pillar-warnings').textContent = pillar.warning;

      var total = pillar.total || (pillar.passed + pillar.failed + pillar.warning);
      var pct = total ? Math.round((pillar.passed / total) * 100) : 0;
      el('pillar-pass-rate-bar').style.width = pct + '%';
      el('pillar-pass-rate-pct').textContent = pct + '%';

      var issues = pillar.issues || [];
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
    })
    .catch(function (err) {
      showLoading(false);
      showError(err.message || 'Failed to load.');
    });
})();
