// db.js — LexBridge client-side database (localStorage)
// All data entered by users is persisted here.
// Keys are namespaced by user ID so multiple accounts don't collide.

const DB = (() => {

  // ── helpers ──────────────────────────────────────────────────────────────
  function uid() {
    return Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
  }

  function ns(key) {
    const userId = localStorage.getItem('user_id') || 'guest';
    return `lb_${userId}_${key}`;
  }

  function load(key, def = []) {
    try { return JSON.parse(localStorage.getItem(ns(key))) ?? def; }
    catch { return def; }
  }

  function save(key, value) {
    localStorage.setItem(ns(key), JSON.stringify(value));
  }

  // ── current user ─────────────────────────────────────────────────────────
  function getUser() {
    return load('profile', null);
  }

  function saveUser(data) {
    save('profile', data);
    // Keep top-level keys in sync for quick access
    if (data.id)        localStorage.setItem('user_id',   data.id);
    if (data.role)      localStorage.setItem('user_role', data.role);
    if (data.full_name) localStorage.setItem('user_name', data.full_name);
  }

  // ── cases ─────────────────────────────────────────────────────────────────
  function getCases() { return load('cases', []); }

  function addCase(caseData) {
    const cases = getCases();
    const entry = {
      id:           caseData.id ?? uid(),
      case_number:  caseData.case_number ?? 'LC-' + Date.now().toString().slice(-6),
      status:       caseData.status || 'pending',
      created_at:   caseData.created_at || caseData.opened_at || new Date().toISOString(),
      ...caseData,
    };
    cases.unshift(entry);
    save('cases', cases);
    addActivity(`New case submitted: ${entry.title}`, 'case');
    return entry;
  }

  function updateCase(id, patch) {
    const cases = getCases().map(c => c.id === id ? { ...c, ...patch } : c);
    save('cases', cases);
  }

  function deleteCase(id) {
    save('cases', getCases().filter(c => c.id !== id));
  }

  // ── documents ─────────────────────────────────────────────────────────────
  function getDocuments() { return load('documents', []); }

  function addDocument(docData) {
    const docs = getDocuments();
    const entry = {
      id:          uid(),
      status:      'pending',
      uploaded_at: new Date().toISOString(),
      ...docData,
    };
    docs.unshift(entry);
    save('documents', docs);
    addActivity(`Document uploaded: ${entry.original_name}`, 'document');
    return entry;
  }

  function deleteDocument(id) {
    save('documents', getDocuments().filter(d => d.id !== id));
  }

  // ── messages ──────────────────────────────────────────────────────────────
  function getConversations() { return load('conversations', []); }
  function getMessages(convId) { return load(`msgs_${convId}`, []); }

  function getOrCreateConversation(otherName, caseTitle = '') {
    const convs = getConversations();
    let conv = convs.find(c => c.other_name === otherName);
    if (!conv) {
      conv = { id: uid(), other_name: otherName, case_title: caseTitle, last_msg: '', last_at: new Date().toISOString(), unread: 0 };
      convs.unshift(conv);
      save('conversations', convs);
    }
    return conv;
  }

  function sendMessage(convId, content, fromSelf = true) {
    const msgs = getMessages(convId);
    const msg = { id: uid(), content, from_self: fromSelf, sent_at: new Date().toISOString() };
    msgs.push(msg);
    save(`msgs_${convId}`, msgs);
    // update conversation preview
    const convs = getConversations().map(c =>
      c.id === convId ? { ...c, last_msg: content, last_at: msg.sent_at, unread: fromSelf ? 0 : c.unread + 1 } : c
    );
    save('conversations', convs);
    return msg;
  }

  // ── notifications ─────────────────────────────────────────────────────────
  function getNotifications() { return load('notifications', []); }

  function addNotification(msg, type = 'info') {
    const notifs = getNotifications();
    notifs.unshift({ id: uid(), msg, type, is_read: false, at: new Date().toISOString() });
    save('notifications', notifs.slice(0, 50));
  }

  function markAllNotificationsRead() {
    save('notifications', getNotifications().map(n => ({ ...n, is_read: true })));
  }

  // ── activity feed ─────────────────────────────────────────────────────────
  function getActivity() { return load('activity', []); }

  function addActivity(text, type = 'info') {
    const feed = getActivity();
    feed.unshift({ id: uid(), text, type, at: new Date().toISOString() });
    save('activity', feed.slice(0, 30));
  }

  // ── payments ──────────────────────────────────────────────────────────────
  function getPayments() { return load('payments', []); }

  function addPayment(data) {
    const payments = getPayments();
    const entry = { id: uid(), created_at: new Date().toISOString(), status: 'pending', ...data };
    payments.unshift(entry);
    save('payments', payments);
    return entry;
  }

  // ── lawyer profile ────────────────────────────────────────────────────────
  function getLawyerProfile() { return load('lawyer_profile', null); }

  function saveLawyerProfile(data) { save('lawyer_profile', data); }

  // ── stats helpers ─────────────────────────────────────────────────────────
  function getStats() {
    const cases   = getCases();
    const docs    = getDocuments();
    const active  = cases.filter(c => ['active','in_progress','pending'].includes(c.status));
    const resolved = cases.filter(c => c.status === 'closed');
    const nextHearing = cases
      .filter(c => c.next_hearing)
      .sort((a, b) => new Date(a.next_hearing) - new Date(b.next_hearing))[0];
    return { activeCases: active.length, totalDocs: docs.length, resolvedCases: resolved.length, nextHearing: nextHearing?.next_hearing || null };
  }

  // ── clear all (for dev/testing) ───────────────────────────────────────────
  function clearAll() {
    const userId = localStorage.getItem('user_id') || 'guest';
    Object.keys(localStorage)
      .filter(k => k.startsWith(`lb_${userId}_`))
      .forEach(k => localStorage.removeItem(k));
  }

  return {
    uid, getUser, saveUser,
    getCases, addCase, updateCase, deleteCase,
    getDocuments, addDocument, deleteDocument,
    getConversations, getMessages, getOrCreateConversation, sendMessage,
    getNotifications, addNotification, markAllNotificationsRead,
    getActivity, addActivity,
    getPayments, addPayment,
    getLawyerProfile, saveLawyerProfile,
    getStats, clearAll,
  };
})();
