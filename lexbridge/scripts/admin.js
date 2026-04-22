/* ============================================================
   LexBridge — scripts/admin.js
   Admin panel supplementary utilities.
   Core admin logic lives in admin_panel.html inline script
   because it references AdminDB which is also defined there.
   This file provides shared helpers and any future extensions.
   ============================================================ */

/* ── Auth guard ───────────────────────────────────────────── */
(function() {
  const role = localStorage.getItem('user_role');
  // Allow if no role set (local-only mode) or if role is admin
  if (role && role !== 'admin') {
    window.location.href = 'login.html?role=admin';
  }
})();

/* ── Logout ───────────────────────────────────────────────── */
function logout() {
  ['access_token', 'refresh_token', 'user_role'].forEach(k => localStorage.removeItem(k));
  window.location.href = 'index.html';
}

/* ── Utility: format file size ────────────────────────────── */
function fmtBytes(bytes) {
  if (bytes < 1024)        return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

/* ── Utility: debounce for search inputs ──────────────────── */
function debounce(fn, delay = 250) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), delay);
  };
}

/* ── Keyboard shortcut: Ctrl+K focuses search ─────────────── */
document.addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
    e.preventDefault();
    const search = document.querySelector('.dash-search input');
    if (search) { search.focus(); search.select(); }
  }
});

/* ── Auto-refresh overview every 30 s if on overview tab ─── */
setInterval(() => {
  const overview = document.getElementById('tab-overview');
  if (overview && overview.classList.contains('active') && typeof renderOverview === 'function') {
    renderOverview();
    if (typeof renderSystemStatus === 'function') renderSystemStatus();
  }
}, 30000);
