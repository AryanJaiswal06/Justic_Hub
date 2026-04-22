/* ============================================================
   LexBridge — scripts/api.js
   Thin wrapper around fetch() with JWT + graceful-offline fallback.
   Exposes window.API with methods for every server endpoint used
   by the dashboards.
   ============================================================ */

(function() {
  const BASE = window.LEXBRIDGE_API_BASE || ''; // same-origin by default

  // ── core fetch ──────────────────────────────────────────────
  async function request(path, { method = 'GET', body = null, params = null, headers = {} } = {}) {
    let url = BASE + path;
    if (params) {
      const qs = new URLSearchParams(
        Object.fromEntries(Object.entries(params).filter(([, v]) => v !== '' && v != null))
      ).toString();
      if (qs) url += (url.includes('?') ? '&' : '?') + qs;
    }

    const token = localStorage.getItem('access_token');
    const opts = {
      method,
      headers: {
        'Accept': 'application/json',
        ...(body && !(body instanceof FormData) ? { 'Content-Type': 'application/json' } : {}),
        ...(token && !String(token).startsWith('local_') ? { Authorization: 'Bearer ' + token } : {}),
        ...headers,
      },
    };
    if (body) opts.body = body instanceof FormData ? body : JSON.stringify(body);

    let res;
    try {
      res = await fetch(url, opts);
    } catch (err) {
      const e = new Error('Network unavailable — running in offline mode.');
      e.offline = true;
      throw e;
    }

    let data = null;
    try { data = await res.json(); } catch { /* non-JSON response */ }

    if (!res.ok) {
      const err = new Error((data && data.error) || `Request failed (${res.status})`);
      err.status = res.status; err.data = data;
      throw err;
    }
    return data ?? {};
  }

  // ── Auth ────────────────────────────────────────────────────
  const auth = {
    login:           (email, password)        => request('/api/auth/login',         { method: 'POST', body: { email, password } }),
    register:        (payload)                => request('/api/auth/register',      { method: 'POST', body: payload }),
    me:              ()                       => request('/api/auth/me'),
    forgotPassword:  (email)                  => request('/api/auth/forgot-password', { method: 'POST', body: { email } }),
    resetPassword:   (token, password)        => request('/api/auth/reset-password',  { method: 'POST', body: { token, password } }),
  };

  // ── Client-side case APIs ──────────────────────────────────
  const client = {
    listCases:       (status)                  => request('/api/client/cases',       { params: { status } }),
    openCase:        (payload)                 => request('/api/client/cases',       { method: 'POST', body: payload }),
    getCase:         (id)                      => request('/api/client/cases/' + id),
    uploadDocument:  (caseId, formData)        => request(`/api/client/cases/${caseId}/documents`, { method: 'POST', body: formData }),
    listDocuments:   ()                        => request('/api/client/documents'),
    notifications:   ()                        => request('/api/client/notifications'),
    markNotifsRead:  ()                        => request('/api/client/notifications/read-all', { method: 'POST' }),
  };

  // ── Lawyer-side APIs ───────────────────────────────────────
  const lawyer = {
    profile:         ()                        => request('/api/lawyer/profile'),
    updateProfile:   (payload)                 => request('/api/lawyer/profile',     { method: 'PUT', body: payload }),
    myCases:         (status)                  => request('/api/lawyer/cases',       { params: { status } }),
    getCase:         (id)                      => request('/api/lawyer/cases/' + id),
    addCaseUpdate:   (id, payload)             => request(`/api/lawyer/cases/${id}/update`, { method: 'POST', body: payload }),
    closeCase:       (id)                      => request(`/api/lawyer/cases/${id}/close`, { method: 'POST' }),
    pendingRequests: ()                        => request('/api/lawyer/requests'),
    listMyDocuments: ()                        => request('/api/lawyer/documents'),
    uploadProfileDocument: (formData)          => request('/api/lawyer/documents',    { method: 'POST', body: formData }),
    deleteMyDocument:(docId)                   => request(`/api/lawyer/documents/${docId}`, { method: 'DELETE' }),
  };

  // ── Match / request workflow ───────────────────────────────
  const match = {
    listLawyers:     (params = {})             => request('/api/match/lawyers',   { params }),
    getLawyer:       (userId)                  => request('/api/match/lawyers/' + userId),
    getLawyerProfile:(userId)                  => request(`/api/match/lawyers/${userId}/profile`),
    openCases:       (params = {})             => request('/api/match/open-cases',{ params }),

    // Create a request.
    //   clients: { case_id, lawyer_id, message }
    //   lawyers: { case_id, message }
    createRequest:   (payload)                 => request('/api/match/requests',  { method: 'POST', body: payload }),
    myRequests:      (status)                  => request('/api/match/requests',  { params: { status } }),
    respond:         (reqId, action)           => request(`/api/match/requests/${reqId}/respond`,  { method: 'POST', body: { action } }),
    withdraw:        (reqId)                   => request(`/api/match/requests/${reqId}/withdraw`, { method: 'POST' }),

    // Ratings
    createRating:    (payload)                 => request('/api/match/ratings',   { method: 'POST', body: payload }),
    listRatings:     (lawyer_id)               => request('/api/match/ratings',   { params: { lawyer_id } }),
  };

  // ── Messaging ──────────────────────────────────────────────
  const messages = {
    send:            (recipient_id, content, case_id = null) =>
                     request('/api/messages/send', { method: 'POST', body: { recipient_id, content, case_id } }),
    get:             (conversation_id, before_id = null) =>
                     request('/api/messages/' + conversation_id, { params: { before_id } }),
  };

  window.API = { request, auth, client, lawyer, match, messages };
})();
