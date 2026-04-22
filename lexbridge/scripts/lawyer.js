/* ============================================================
   LexBridge — scripts/lawyer.js
   Lawyer dashboard logic
   Requires: db.js, main.js
   ============================================================ */

/* ── Auth guard ───────────────────────────────────────────── */
(function() {
  if (!localStorage.getItem('user_id') && !localStorage.getItem('access_token')) {
    window.location.href = 'login.html';
  }
})();

/* ── State ────────────────────────────────────────────────── */
let _activeConvId = null;
const ALLOWED_MIME = [
  'application/pdf', 'application/msword',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'image/jpeg', 'image/png',
];

/* ── Helpers ──────────────────────────────────────────────── */
function esc(s = '') {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
function fmtDate(iso) {
  return iso ? new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }) : '—';
}
function fmtTime(iso) {
  if (!iso) return '';
  const d = new Date(iso), now = new Date(), diff = Math.floor((now - d) / 1000);
  if (diff < 60)    return 'Just now';
  if (diff < 3600)  return Math.floor(diff / 60) + ' min ago';
  if (diff < 86400) return Math.floor(diff / 3600) + ' hr ago';
  return fmtDate(iso);
}
function sColor(s) {
  return { active: 'success', in_progress: 'info', pending: 'gold', closed: '', dismissed: 'danger' }[s] || '';
}
function _set(id, val) { const el = document.getElementById(id); if (el) el.textContent = val; }

/* ── Init ─────────────────────────────────────────────────── */
function initLawyerDashboard() {
  const lp   = DB.getLawyerProfile() || {};
  const user = DB.getUser() || {};
  const name = lp.full_name || user.full_name || localStorage.getItem('user_name') || '';
  const ini  = name ? name.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase() : '?';
  const hr   = new Date().getHours();
  const gr   = hr < 12 ? 'Good Morning' : hr < 17 ? 'Good Afternoon' : 'Good Evening';

  _set('sidebarName',   name || '—');
  _set('sidebarAvatar', ini);
  _set('topbarAvatar',  ini);
  _set('sidebarSpec',   lp.specialization || 'Lawyer');
  _set('greetingText',  `${gr}, ${name.split(' ')[0] || 'Advocate'} ⚖`);

  renderStats();
  renderOverviewCases();
  renderActivityFeed();
  renderNotifications();
}

/* ── Stats ────────────────────────────────────────────────── */
function renderStats() {
  const cases    = DB.getCases();
  const docs     = DB.getDocuments();
  const payments = DB.getPayments();
  const active   = cases.filter(c => ['active', 'in_progress', 'pending'].includes(c.status)).length;
  const resolved = cases.filter(c => c.status === 'closed').length;
  const earned   = payments.filter(p => p.status === 'completed').reduce((s, p) => s + Number(p.amount), 0);

  _set('statCases',     active);
  _set('statResolved',  resolved);
  _set('statDocs',      docs.length);
  _set('statEarnings',  '₹' + earned.toLocaleString('en-IN'));
  _set('pStatCases',    cases.length);
  _set('pStatEarnings', '₹' + earned.toLocaleString('en-IN'));
  _set('pStatDocs',     docs.length);
}

/* ── Overview cases ───────────────────────────────────────── */
function renderOverviewCases() {
  const cases = DB.getCases().filter(c => c.status !== 'closed').slice(0, 5);
  const tbody = document.getElementById('overviewCasesBody');
  if (!tbody) return;

  tbody.innerHTML = cases.length
    ? cases.map(c => `
      <tr>
        <td><strong>${esc(c.title)}</strong><br>
          <small style="color:var(--text-muted)">${esc(c.case_number)}</small></td>
        <td>${esc(c.client_name || '—')}</td>
        <td>${c.next_hearing ? fmtDate(c.next_hearing) : '—'}</td>
        <td><span class="badge badge-${sColor(c.status)}">${c.status}</span></td>
      </tr>`).join('')
    : `<tr><td colspan="4" style="text-align:center;padding:1.5rem;color:var(--text-muted)">
        No active cases yet. <a href="#" onclick="openAddCase();return false">Add one →</a>
       </td></tr>`;
}

/* ── Cases tab ────────────────────────────────────────────── */
function renderLawyerCases() {
  const cases = DB.getCases();
  const el    = document.getElementById('lawyerCasesCards');
  if (!el) return;

  if (!cases.length) {
    el.innerHTML = `<div style="text-align:center;padding:3rem;color:var(--text-muted)">
      No cases yet. <button class="btn btn-primary btn-sm" onclick="openAddCase()">Add your first case</button></div>`;
    return;
  }
  el.innerHTML = cases.map(c => `
    <div class="dash-panel" style="margin-bottom:1rem">
      <div class="panel-body">
        <div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:.5rem;align-items:flex-start">
          <div>
            <div style="font-weight:600;font-size:1rem">${esc(c.title)}</div>
            <div style="font-size:.78rem;color:var(--text-muted);margin-top:2px">
              ${esc(c.case_number)} · ${esc(c.case_type || '')} · Client: ${esc(c.client_name || '—')}
            </div>
          </div>
          <div style="display:flex;gap:.5rem;align-items:center">
            <span class="badge badge-${sColor(c.status)}">${c.status}</span>
            <button class="btn btn-outline btn-sm" onclick="deleteCaseEntry('${c.id}')">🗑</button>
          </div>
        </div>
        ${c.description ? `<p style="margin-top:.6rem;font-size:.875rem;color:var(--text-secondary)">${esc(c.description)}</p>` : ''}
        <div style="margin-top:.6rem;display:flex;gap:1.5rem;font-size:.8rem;color:var(--text-muted);flex-wrap:wrap">
          ${c.next_hearing ? `<span>📅 ${fmtDate(c.next_hearing)}</span>` : ''}
        </div>
        <div style="margin-top:.75rem">
          <select class="form-select" style="width:auto;font-size:.8rem;padding:.3rem .6rem"
            onchange="changeCaseStatus('${c.id}',this.value)">
            <option value="pending"     ${c.status === 'pending'     ? 'selected' : ''}>Pending</option>
            <option value="active"      ${c.status === 'active'      ? 'selected' : ''}>Active</option>
            <option value="in_progress" ${c.status === 'in_progress' ? 'selected' : ''}>In Progress</option>
            <option value="closed"      ${c.status === 'closed'      ? 'selected' : ''}>Closed</option>
          </select>
        </div>
      </div>
    </div>`).join('');
}

function openAddCase()  { const m = document.getElementById('addCaseModal'); if (m) m.style.display = 'flex'; }
function closeAddCase() { const m = document.getElementById('addCaseModal'); if (m) m.style.display = 'none'; }

function addCase(e) {
  e.preventDefault();
  const data = {};
  new FormData(e.target).forEach((v, k) => { data[k] = v; });
  DB.addCase(data);
  DB.addActivity(`Case added: ${data.title}`, 'case');
  e.target.reset(); closeAddCase();
  renderLawyerCases(); renderStats(); renderOverviewCases(); renderActivityFeed();
  showToast('Case added', 'success');
}

function changeCaseStatus(id, status) {
  DB.updateCase(id, { status });
  DB.addActivity(`Case status → "${status}"`, 'case');
  renderLawyerCases(); renderStats(); renderOverviewCases(); renderActivityFeed();
  showToast('Status updated', 'success');
}

function deleteCaseEntry(id) {
  if (!confirm('Delete this case?')) return;
  DB.deleteCase(id); renderLawyerCases(); renderStats(); renderOverviewCases();
  showToast('Deleted', 'info');
}

/* ── Messages ─────────────────────────────────────────────── */
function renderConversations() {
  const convs = DB.getConversations();
  const el    = document.getElementById('lawyerConversationList');
  if (!el) return;

  el.innerHTML = convs.length
    ? convs.map(c => `
      <div onclick="openConv('${c.id}','${esc(c.other_name)}')"
        style="padding:.75rem 1rem;cursor:pointer;border-bottom:1px solid var(--border);
               ${_activeConvId === c.id ? 'background:var(--bg-elevated)' : ''}">
        <div style="display:flex;justify-content:space-between;align-items:center">
          <span style="font-weight:500;font-size:.88rem">${esc(c.other_name)}</span>
          ${c.unread ? `<span style="background:var(--gold);color:#000;font-size:.7rem;border-radius:10px;padding:1px 7px">${c.unread}</span>` : ''}
        </div>
        <div style="font-size:.77rem;color:var(--text-muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;margin-top:2px">
          ${esc(c.last_msg || 'No messages')}
        </div>
      </div>`).join('')
    : `<div style="padding:1rem;font-size:.82rem;color:var(--text-muted)">No conversations yet.</div>`;
}

function openConv(id, name) {
  _activeConvId = id;
  const nameEl = document.getElementById('activeChatName');
  if (nameEl) nameEl.textContent = name;
  const msgs = DB.getMessages(id);
  const el   = document.getElementById('lawyerMessageList');
  if (!el) return;

  el.innerHTML = msgs.length
    ? msgs.map(m => `
      <div style="display:flex;justify-content:${m.from_self ? 'flex-end' : 'flex-start'}">
        <div style="max-width:72%;padding:.55rem .9rem;border-radius:12px;font-size:.875rem;
          background:${m.from_self ? 'var(--gold)' : 'var(--bg-elevated)'};
          color:${m.from_self ? '#000' : 'var(--text-primary)'}">
          ${esc(m.content)}
          <div style="font-size:.68rem;opacity:.55;margin-top:3px;text-align:right">${fmtTime(m.sent_at)}</div>
        </div>
      </div>`).join('')
    : `<div style="text-align:center;color:var(--text-muted);font-size:.85rem;margin-top:2rem">Say hello!</div>`;
  el.scrollTop = el.scrollHeight;
  renderConversations();
}

function sendMsg() {
  if (!_activeConvId) { showToast('Select a conversation first', 'error'); return; }
  const inp = document.getElementById('lawyerMsgInput');
  if (!inp) return;
  const txt = inp.value.trim(); if (!txt) return;
  DB.sendMessage(_activeConvId, txt, true);
  inp.value = '';
  openConv(_activeConvId, document.getElementById('activeChatName')?.textContent || '');
}

function startNewConversation() {
  const inp  = document.getElementById('newConvName');
  if (!inp) return;
  const name = inp.value.trim(); if (!name) { showToast('Enter client name', 'error'); return; }
  const c    = DB.getOrCreateConversation(name);
  inp.value  = ''; openConv(c.id, name); renderConversations();
}

/* ── Documents ────────────────────────────────────────────── */
function handleFileUpload(e) {
  let count = 0;
  for (const f of e.target.files) {
    if (!ALLOWED_MIME.includes(f.type)) { showToast(`${f.name}: unsupported`, 'error'); continue; }
    if (f.size > 10 * 1024 * 1024)     { showToast(`${f.name}: too large`, 'error'); continue; }
    DB.addDocument({ original_name: f.name, mime_type: f.type, file_size_bytes: f.size }); count++;
  }
  e.target.value = '';
  if (count) { renderDocuments(); renderStats(); showToast(`${count} file(s) saved`, 'success'); }
}

function renderDocuments() {
  const docs = DB.getDocuments();
  const el   = document.getElementById('lawyerDocsList');
  if (!el) return;

  if (!docs.length) {
    el.innerHTML = `<div style="text-align:center;padding:2rem;color:var(--text-muted)">No documents yet.</div>`;
    return;
  }
  el.innerHTML = `<div class="dash-panel"><div class="panel-body" style="padding:0">
    <table class="dash-table">
      <thead><tr><th>Name</th><th>Type</th><th>Size</th><th>Uploaded</th><th></th></tr></thead>
      <tbody>${docs.map(d => `
        <tr>
          <td>📄 ${esc(d.original_name)}</td>
          <td>${esc((d.mime_type || '').split('/')[1] || '').toUpperCase()}</td>
          <td>${(d.file_size_bytes / 1024).toFixed(1)} KB</td>
          <td>${fmtDate(d.uploaded_at)}</td>
          <td><button class="btn btn-outline btn-sm" onclick="deleteDocEntry('${d.id}')">🗑</button></td>
        </tr>`).join('')}
      </tbody>
    </table></div></div>`;
}

function deleteDocEntry(id) { DB.deleteDocument(id); renderDocuments(); renderStats(); }

/* ── Earnings ─────────────────────────────────────────────── */
function renderEarnings() {
  const p        = DB.getPayments();
  const received = p.filter(x => x.status === 'completed').reduce((s, x) => s + Number(x.amount), 0);
  const pending  = p.filter(x => x.status === 'pending').reduce((s, x) => s + Number(x.amount), 0);

  _set('earnTotal',   '₹' + received.toLocaleString('en-IN'));
  _set('earnPending', '₹' + pending.toLocaleString('en-IN'));
  _set('earnCount',   p.length);

  const tbody = document.getElementById('earningsTable');
  if (!tbody) return;

  tbody.innerHTML = p.length
    ? p.map(x => `
      <tr>
        <td>${fmtDate(x.created_at)}</td>
        <td>${esc(x.client_name || '—')}</td>
        <td>${esc(x.description)}</td>
        <td>₹${Number(x.amount).toLocaleString('en-IN')}</td>
        <td><span class="badge badge-${x.status === 'completed' ? 'success' : 'gold'}">${x.status === 'completed' ? 'Received' : 'Pending'}</span></td>
        <td><button class="btn btn-outline btn-sm" onclick="deleteEarning('${x.id}')">🗑</button></td>
      </tr>`).join('')
    : `<tr><td colspan="6" style="text-align:center;padding:1.5rem;color:var(--text-muted)">
        No payments recorded yet.</td></tr>`;
}

function openAddEarning()  { const m = document.getElementById('addEarnModal'); if (m) m.style.display = 'flex'; }
function closeAddEarning() { const m = document.getElementById('addEarnModal'); if (m) m.style.display = 'none'; }

function addEarning(e) {
  e.preventDefault();
  const data = {};
  new FormData(e.target).forEach((v, k) => { data[k] = v; });
  DB.addPayment(data); e.target.reset(); closeAddEarning(); renderEarnings(); renderStats();
  showToast('Payment recorded', 'success');
}

function deleteEarning(id) {
  const uid = localStorage.getItem('user_id') || 'guest';
  const key = `lb_${uid}_payments`;
  localStorage.setItem(key, JSON.stringify(
    JSON.parse(localStorage.getItem(key) || '[]').filter(x => x.id !== id)
  ));
  renderEarnings(); renderStats();
}

/* ── Profile ──────────────────────────────────────────────── */
function loadProfile() {
  const lp = DB.getLawyerProfile() || {};
  const g  = id => { const el = document.getElementById(id); if (el) el.value = lp[id.replace('prof', '').toLowerCase()] || ''; };
  const set = (id, val) => { const el = document.getElementById(id); if (el) el.value = val || ''; };
  set('profName',   lp.full_name || DB.getUser()?.full_name || '');
  set('profSpec',   lp.specialization || '');
  set('profBio',    lp.bio || '');
  set('profFee',    lp.consultation_fee || '');
  set('profExp',    lp.experience_years || '');
  set('profLangs',  lp.languages || '');
  set('profCourts', lp.courts || '');
  set('profBar',    lp.bar_council_no || '');
  set('profAvail',  lp.availability_status || 'available');
}

function saveProfile(e) {
  e.preventDefault();
  const g = id => { const el = document.getElementById(id); return el ? el.value.trim() : ''; };
  const lp = {
    full_name:           g('profName'),
    specialization:      g('profSpec'),
    bio:                 g('profBio'),
    consultation_fee:    g('profFee'),
    experience_years:    g('profExp'),
    languages:           g('profLangs'),
    courts:              g('profCourts'),
    bar_council_no:      g('profBar'),
    availability_status: g('profAvail'),
  };
  DB.saveLawyerProfile(lp);
  const ini = lp.full_name.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();
  _set('sidebarName',   lp.full_name);
  _set('sidebarSpec',   lp.specialization || 'Lawyer');
  _set('sidebarAvatar', ini);
  _set('topbarAvatar',  ini);
  _set('greetingText',  `Hello, ${lp.full_name.split(' ')[0]} ⚖`);
  showToast('Profile saved!', 'success');
}

/* ── Settings ─────────────────────────────────────────────── */
function loadSettings() {
  const u = DB.getUser() || {};
  const set = (id, val) => { const el = document.getElementById(id); if (el) el.value = val || ''; };
  set('settEmail', u.email || '');
  set('settPhone', u.phone || '');
}

function saveSettings(e) {
  e.preventDefault();
  const g = id => { const el = document.getElementById(id); return el ? el.value.trim() : ''; };
  DB.saveUser({ ...(DB.getUser() || {}), email: g('settEmail'), phone: g('settPhone') });
  showToast('Settings saved!', 'success');
}

/* ── Notifications ────────────────────────────────────────── */
function renderNotifications() {
  const n  = DB.getNotifications();
  const ur = n.filter(x => !x.is_read).length;
  const dot = document.getElementById('notifDot');
  if (dot) dot.style.display = ur ? 'block' : 'none';
  const el = document.getElementById('notifList');
  if (!el) return;
  el.innerHTML = n.length
    ? n.slice(0, 10).map(x => `
      <div class="notif-item ${x.is_read ? '' : 'unread'}">
        <div class="notif-msg">${esc(x.msg)}</div>
        <div class="notif-time">${fmtTime(x.at)}</div>
      </div>`).join('')
    : `<div style="padding:1rem;color:var(--text-muted);font-size:.85rem">No notifications</div>`;
}

function markNotifsRead() { DB.markAllNotificationsRead(); renderNotifications(); }

/* ── Activity ─────────────────────────────────────────────── */
function renderActivityFeed() {
  const feed = DB.getActivity();
  const el   = document.getElementById('activityList');
  if (!el) return;
  el.innerHTML = feed.length
    ? feed.slice(0, 8).map(a => `
      <div style="display:flex;gap:.75rem;padding:.5rem 0;border-bottom:1px solid var(--border)">
        <span>${a.type === 'case' ? '📋' : a.type === 'document' ? '📁' : '🔔'}</span>
        <div>
          <div style="font-size:.85rem">${esc(a.text)}</div>
          <div style="font-size:.73rem;color:var(--text-muted)">${fmtTime(a.at)}</div>
        </div>
      </div>`).join('')
    : `<div style="color:var(--text-muted);font-size:.85rem;padding:.5rem 0">No activity yet.</div>`;
}

/* ── Logout ───────────────────────────────────────────────── */
function logout() {
  ['access_token', 'refresh_token', 'user_role'].forEach(k => localStorage.removeItem(k));
  window.location.href = 'index.html';
}

/* ── showTab override ─────────────────────────────────────── */
const _baseShowTab = window.showTab;
window.showTab = function(name) {
  if (_baseShowTab) _baseShowTab(name);
  if (name === 'cases')     renderLawyerCases();
  if (name === 'messages')  renderConversations();
  if (name === 'documents') renderDocuments();
  if (name === 'earnings')  renderEarnings();
  if (name === 'profile')   loadProfile();
  if (name === 'settings')  loadSettings();
};

/* ── Boot ─────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', initLawyerDashboard);
