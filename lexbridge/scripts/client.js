/* ============================================================
   LexBridge — scripts/client.js
   Client dashboard logic
   Requires: db.js, main.js
   ============================================================ */

/* ── Auth guard ───────────────────────────────────────────── */
(function() {
  if (!localStorage.getItem('user_id') && !localStorage.getItem('access_token')) {
    window.location.href = 'login.html';
  }
})();

/* ── State ────────────────────────────────────────────────── */
let _caseFilter   = 'all';
let _activeConvId = null;
const ALLOWED_MIME = [
  'application/pdf',
  'application/msword',
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
function statusColor(s) {
  return { active: 'success', in_progress: 'info', pending: 'gold', closed: '', dismissed: 'danger' }[s] || '';
}

/* ── Init ─────────────────────────────────────────────────── */
function initClientDashboard() {
  const user   = DB.getUser();
  const name   = user?.full_name || localStorage.getItem('user_name') || '';
  const initials = name ? name.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase() : '?';
  const hr     = new Date().getHours();
  const greet  = hr < 12 ? 'Good Morning' : hr < 17 ? 'Good Afternoon' : 'Good Evening';

  _set('sidebarName',   name || 'My Account');
  _set('sidebarAvatar', initials);
  _set('topbarAvatar',  initials);
  _set('greetingText',  `${greet}, ${name.split(' ')[0] || 'there'} 👋`);

  renderStats();
  renderOverviewCases();
  renderActivityFeed();
  renderNotifications();
}

function _set(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

/* ── Stats ────────────────────────────────────────────────── */
function renderStats() {
  const s = DB.getStats();
  _set('statActive',   s.activeCases);
  _set('statDocs',     s.totalDocs);
  _set('statResolved', s.resolvedCases);
  _set('statHearing',  s.nextHearing
    ? new Date(s.nextHearing).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })
    : '—');
  _set('badgeCases', DB.getCases().length);
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
        <td><span class="badge badge-${statusColor(c.status)}">${c.status}</span></td>
        <td>${c.next_hearing ? fmtDate(c.next_hearing) : '—'}</td>
        <td><button class="btn btn-outline btn-sm" onclick="showTab('cases')">View</button></td>
      </tr>`).join('')
    : `<tr><td colspan="4" style="text-align:center;padding:1.5rem;color:var(--text-muted)">
        No active cases yet. <a href="#" onclick="showTab('newcase');return false">Submit one →</a>
       </td></tr>`;
}

/* ── Cases tab ────────────────────────────────────────────── */
function filterCases(filter, chip, query = '') {
  if (filter !== 'search') {
    _caseFilter = filter;
    document.querySelectorAll('#tab-cases .filter-chip').forEach(c => c.classList.remove('active'));
    if (chip) chip.classList.add('active');
  }
  renderCasesTab(query);
}

function renderCasesTab(query = '') {
  let cases = DB.getCases();
  if (_caseFilter !== 'all') cases = cases.filter(c => c.status === _caseFilter);
  if (query) cases = cases.filter(c => c.title.toLowerCase().includes(query.toLowerCase()));

  const el = document.getElementById('casesCards');
  if (!el) return;

  if (!cases.length) {
    el.innerHTML = `<div style="text-align:center;padding:3rem;color:var(--text-muted)">
      No cases found. <a href="#" onclick="showTab('newcase');return false">Submit a new case →</a></div>`;
    return;
  }
  el.innerHTML = cases.map(c => `
    <div class="dash-panel" style="margin-bottom:1rem">
      <div class="panel-body">
        <div style="display:flex;justify-content:space-between;flex-wrap:wrap;gap:.5rem;align-items:flex-start">
          <div>
            <div style="font-weight:600;font-size:1rem">${esc(c.title)}</div>
            <div style="font-size:.78rem;color:var(--text-muted);margin-top:2px">
              ${esc(c.case_number)} · ${esc(c.case_type || '')} · Filed ${fmtDate(c.created_at)}
            </div>
          </div>
          <div style="display:flex;gap:.5rem;align-items:center">
            <span class="badge badge-${statusColor(c.status)}">${c.status}</span>
            <button class="btn btn-outline btn-sm" onclick="deleteCaseEntry('${c.id}')">🗑</button>
          </div>
        </div>
        <p style="margin-top:.75rem;font-size:.875rem;color:var(--text-secondary)">${esc(c.description)}</p>
        <div style="margin-top:.6rem;display:flex;gap:1.5rem;font-size:.8rem;color:var(--text-muted);flex-wrap:wrap">
          ${c.next_hearing ? `<span>📅 Hearing: ${fmtDate(c.next_hearing)}</span>` : ''}
          ${c.preferred_lawyer ? `<span>⚖ ${esc(c.preferred_lawyer)}</span>` : ''}
          <span>Priority: ${c.priority}</span>
        </div>
        <div style="margin-top:.75rem">
          <select class="form-select" style="width:auto;font-size:.8rem;padding:.3rem .6rem"
            onchange="changeCaseStatus('${c.id}',this.value)">
            <option value="pending"     ${c.status === 'pending'     ? 'selected' : ''}>Pending</option>
            <option value="active"      ${c.status === 'active'      ? 'selected' : ''}>Active</option>
            <option value="in_progress" ${c.status === 'in_progress' ? 'selected' : ''}>In Progress</option>
            <option value="closed"      ${c.status === 'closed'      ? 'selected' : ''}>Closed / Resolved</option>
          </select>
        </div>
      </div>
    </div>`).join('');
}

function changeCaseStatus(id, status) {
  DB.updateCase(id, { status });
  DB.addActivity(`Case status changed to "${status}"`, 'case');
  renderCasesTab(); renderStats(); renderOverviewCases();
  showToast('Status updated', 'success');
}

function deleteCaseEntry(id) {
  if (!confirm('Delete this case permanently?')) return;
  DB.deleteCase(id);
  renderCasesTab(); renderStats(); renderOverviewCases();
  showToast('Case deleted', 'info');
}

/* ── New case form ────────────────────────────────────────── */
async function submitCase(e) {
  e.preventDefault();
  const data = {};
  new FormData(e.target).forEach((v, k) => { data[k] = v; });

  try {
    const res = await API.client.openCase(data);
    if (res && res.case) {
      DB.addCase({
        id: res.case.id,
        case_number: res.case.case_number,
        title: res.case.title,
        description: res.case.description || data.description || '',
        case_type: res.case.case_type,
        priority: res.case.priority,
        status: res.case.status,
        created_at: res.case.opened_at,
        next_hearing: res.case.next_hearing || data.next_hearing || null,
        preferred_lawyer: data.preferred_lawyer || '',
      });
      DB.addNotification(`Case submitted: ${res.case.title}`);
      showToast('Case submitted!', 'success');
    } else {
      throw new Error('Unexpected server response.');
    }
  } catch (err) {
    DB.addCase(data);
    DB.addNotification(`New case submitted: ${data.title}`);
    showToast('Saved locally — case submitted offline.', 'info');
  }

  e.target.reset();
  renderStats(); renderOverviewCases(); renderActivityFeed();
  showTab('cases');
}

/* ── Documents ────────────────────────────────────────────── */
function handleFileUpload(e) {
  let count = 0;
  for (const f of e.target.files) {
    if (!ALLOWED_MIME.includes(f.type)) { showToast(`${f.name}: unsupported type`, 'error'); continue; }
    if (f.size > 10 * 1024 * 1024)     { showToast(`${f.name}: exceeds 10 MB`, 'error'); continue; }
    DB.addDocument({ original_name: f.name, mime_type: f.type, file_size_bytes: f.size });
    count++;
  }
  e.target.value = '';
  if (count) { renderDocuments(); renderStats(); renderNotifications(); showToast(`${count} file(s) saved`, 'success'); }
}

function renderDocuments() {
  const docs = DB.getDocuments();
  const el   = document.getElementById('documentsList');
  if (!el) return;

  if (!docs.length) {
    el.innerHTML = `<div style="text-align:center;padding:2rem;color:var(--text-muted)">
      No documents uploaded yet.</div>`;
    return;
  }
  el.innerHTML = `<div class="dash-panel"><div class="panel-body" style="padding:0">
    <table class="dash-table">
      <thead><tr><th>Name</th><th>Type</th><th>Size</th><th>Uploaded</th><th>Status</th><th></th></tr></thead>
      <tbody>${docs.map(d => `
        <tr>
          <td>📄 ${esc(d.original_name)}</td>
          <td>${esc((d.mime_type || '').split('/')[1] || '').toUpperCase()}</td>
          <td>${(d.file_size_bytes / 1024).toFixed(1)} KB</td>
          <td>${fmtDate(d.uploaded_at)}</td>
          <td><span class="badge badge-gold">${d.status}</span></td>
          <td><button class="btn btn-outline btn-sm" onclick="deleteDocEntry('${d.id}')">🗑</button></td>
        </tr>`).join('')}
      </tbody>
    </table></div></div>`;
}

function deleteDocEntry(id) {
  DB.deleteDocument(id); renderDocuments(); renderStats();
  showToast('Document removed', 'info');
}

/* ── Messages ─────────────────────────────────────────────── */
function renderConversations() {
  const convs = DB.getConversations();
  const el    = document.getElementById('conversationList');
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
          ${esc(c.last_msg || 'No messages yet')}
        </div>
      </div>`).join('')
    : `<div style="padding:1rem;font-size:.82rem;color:var(--text-muted)">No conversations yet.</div>`;
}

function openConv(id, name) {
  _activeConvId = id;
  const nameEl = document.getElementById('activeChatName');
  if (nameEl) nameEl.textContent = name;
  renderMessages(); renderConversations();
}

function renderMessages() {
  if (!_activeConvId) return;
  const msgs = DB.getMessages(_activeConvId);
  const el   = document.getElementById('messageList');
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
}

function sendMsg() {
  if (!_activeConvId) { showToast('Select a conversation first', 'error'); return; }
  const inp = document.getElementById('msgInput');
  if (!inp) return;
  const txt = inp.value.trim(); if (!txt) return;
  DB.sendMessage(_activeConvId, txt, true);
  inp.value = ''; renderMessages(); renderConversations();
}

function startNewConversation() {
  const inp  = document.getElementById('newConvName');
  if (!inp) return;
  const name = inp.value.trim(); if (!name) { showToast('Enter lawyer name', 'error'); return; }
  const c    = DB.getOrCreateConversation(name);
  inp.value  = ''; openConv(c.id, name); renderConversations();
}

/* ── Billing ──────────────────────────────────────────────── */
function renderBilling() {
  const payments = DB.getPayments();
  const paid    = payments.filter(p => p.status === 'completed').reduce((s, p) => s + Number(p.amount), 0);
  const pending  = payments.filter(p => p.status === 'pending').reduce((s, p) => s + Number(p.amount), 0);

  _set('billingPaid',  '₹' + paid.toLocaleString('en-IN'));
  _set('billingDue',   '₹' + pending.toLocaleString('en-IN'));
  _set('billingCount', payments.length);

  const tbody = document.getElementById('billingTable');
  if (!tbody) return;

  tbody.innerHTML = payments.length
    ? payments.map((p, i) => `
      <tr>
        <td>#INV-${String(i + 1).padStart(3, '0')}</td>
        <td>${esc(p.description)}${p.lawyer_name ? `<br><small style="color:var(--text-muted)">${esc(p.lawyer_name)}</small>` : ''}</td>
        <td>${fmtDate(p.created_at)}</td>
        <td>₹${Number(p.amount).toLocaleString('en-IN')}</td>
        <td><span class="badge badge-${p.status === 'completed' ? 'success' : 'gold'}">${p.status === 'completed' ? 'Paid' : 'Pending'}</span></td>
        <td>${p.status === 'pending' ? `<button class="btn btn-primary btn-sm" onclick="markPaid('${p.id}')">Mark Paid</button>` : ''}</td>
      </tr>`).join('')
    : `<tr><td colspan="6" style="text-align:center;padding:1.5rem;color:var(--text-muted)">
        No invoices yet. Click "+ Add Invoice" to begin.</td></tr>`;
}

function openAddPayment() {
  const m = document.getElementById('payModal');
  if (m) m.style.display = 'flex';
}
function closeAddPayment() {
  const m = document.getElementById('payModal');
  if (m) m.style.display = 'none';
}
function addPaymentEntry(e) {
  e.preventDefault();
  const data = {};
  new FormData(e.target).forEach((v, k) => { data[k] = v; });
  DB.addPayment(data); e.target.reset(); closeAddPayment(); renderBilling();
  showToast('Invoice saved', 'success');
}
function markPaid(id) {
  const uid = localStorage.getItem('user_id') || 'guest';
  const key = `lb_${uid}_payments`;
  const p   = JSON.parse(localStorage.getItem(key) || '[]').map(x =>
    x.id === id ? { ...x, status: 'completed', paid_at: new Date().toISOString() } : x);
  localStorage.setItem(key, JSON.stringify(p));
  renderBilling(); showToast('Marked as paid', 'success');
}

/* ── Settings / profile ───────────────────────────────────── */
function loadSettingsForm() {
  const u = DB.getUser() || {};
  const parts = (u.full_name || '').split(' ');
  const set = (id, val) => { const el = document.getElementById(id); if (el) el.value = val; };
  set('settFirst', parts[0] || '');
  set('settLast',  parts.slice(1).join(' ') || '');
  set('settEmail', u.email || '');
  set('settPhone', u.phone || '');
  set('settCity',  u.city  || '');
}

function saveProfile(e) {
  e.preventDefault();
  const g = id => { const el = document.getElementById(id); return el ? el.value.trim() : ''; };
  const first = g('settFirst'), last = g('settLast');
  const updated = {
    ...(DB.getUser() || {}),
    full_name: `${first} ${last}`.trim(),
    email: g('settEmail'), phone: g('settPhone'), city: g('settCity'),
  };
  DB.saveUser(updated);
  const ini = updated.full_name.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();
  _set('sidebarName',   updated.full_name);
  _set('sidebarAvatar', ini);
  _set('topbarAvatar',  ini);
  _set('greetingText',  `Hello, ${first} 👋`);
  showToast('Profile updated!', 'success');
}

/* ── Notifications ────────────────────────────────────────── */
function renderNotifications() {
  const notifs = DB.getNotifications();
  const unread  = notifs.filter(n => !n.is_read).length;
  const dot     = document.getElementById('notifDot');
  if (dot) dot.style.display = unread ? 'block' : 'none';

  const el = document.getElementById('notifList');
  if (!el) return;
  el.innerHTML = notifs.length
    ? notifs.slice(0, 10).map(n => `
      <div class="notif-item ${n.is_read ? '' : 'unread'}">
        <div class="notif-msg">${esc(n.msg)}</div>
        <div class="notif-time">${fmtTime(n.at)}</div>
      </div>`).join('')
    : `<div style="padding:1rem;color:var(--text-muted);font-size:.85rem">No notifications yet</div>`;
}

function markNotifsRead() {
  DB.markAllNotificationsRead(); renderNotifications();
}

/* ── Activity feed ────────────────────────────────────────── */
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

/* ── showTab override to trigger renders ──────────────────── */
const _baseShowTab = window.showTab;
window.showTab = function(name) {
  if (_baseShowTab) _baseShowTab(name);
  if (name === 'cases')     renderCasesTab();
  if (name === 'documents') renderDocuments();
  if (name === 'messages')  renderConversations();
  if (name === 'billing')   renderBilling();
  if (name === 'settings')  loadSettingsForm();
};

/* ── Boot ─────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', initClientDashboard);
