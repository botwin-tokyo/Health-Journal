// Browser memory only. This module never uses local/session storage, IndexedDB or a service worker.
export function createAuthClient(apiOrigin) {
  const api = new URL(apiOrigin);
  if (api.protocol !== 'https:' || api.origin !== apiOrigin) throw new Error('Invalid API origin');
  let csrf = null, session = null, epoch = null, lastActivity = 0, generation = 0;
  const requests = new Set(), cache = new Map(), listeners = new Set(), cleaners = new Set();
  const emit = () => listeners.forEach(fn => fn(session));
  function clear() {
    generation += 1;
    requests.forEach(controller => controller.abort()); requests.clear();
    cache.clear(); cleaners.forEach(fn => fn()); session = null; epoch = null; emit();
  }
  async function send(path, {method = 'GET', body, publicAuth = false, headers = {}} = {}) {
    if (!path.startsWith('/') || path.startsWith('//')) throw new Error('Invalid API route');
    if (!publicAuth && !session) throw new Error('authentication_required');
    const startedGeneration = generation;
    const controller = new AbortController(); requests.add(controller);
    try {
      const binary = body instanceof Blob || body instanceof ArrayBuffer || ArrayBuffer.isView(body);
      const response = await fetch(apiOrigin + path, {method, credentials: 'include', cache: 'no-store',
        redirect: 'error', referrerPolicy: 'no-referrer', signal: controller.signal,
        headers: {...(body === undefined ? {} : {'Content-Type': binary ? (body instanceof Blob && body.type || 'application/octet-stream') : 'application/json'}),
          ...(method === 'GET' ? {} : {'X-CSRFToken': csrf || ''}), ...headers},
        ...(body === undefined ? {} : {body: binary ? body : JSON.stringify(body)})});
      const value = response.headers.get("Content-Type")?.includes("json") ? await response.json() : await response.arrayBuffer();
      if (response.status === 401 || response.status === 403) { clear(); throw new Error(value.code || 'authentication_required'); }
      if (!response.ok) throw new Error(value.error?.code || value.code || 'request_failed');
      if (!publicAuth && startedGeneration !== generation) throw new Error('permission_context_changed');
      const next = response.headers.get('X-Permission-Epoch');
      if (value.context_reset_required === true) { clear(); await refreshSession(); return {status: value.status, context_reset_required: true}; }
      if (!publicAuth && epoch && next && next !== epoch) { clear(); await refreshSession(); throw new Error('permission_context_changed'); }
      return value;
    } finally { requests.delete(controller); }
  }
  async function bootstrap() { const value = await send('/api/v1/auth/bootstrap', {publicAuth: true}); csrf = value.csrf_token; }
  async function refreshSession() {
    const value = await send('/api/v1/session', {publicAuth: true});
    if (epoch && value.permission_epoch !== epoch) clear();
    session = value; epoch = value.permission_epoch; csrf = value.csrf_token; emit(); return value;
  }
  async function authenticate(path, body) {
    await bootstrap(); await send('/_allauth/browser/v1/' + path, {method: 'POST', body, publicAuth: true});
    await bootstrap(); return refreshSession();
  }
  async function activity(event) {
    if (!event.isTrusted || document.visibilityState !== 'visible' || !session || Date.now() - lastActivity < 60000) return;
    lastActivity = Date.now();
    try { const value = await send('/api/v1/session/activity', {method: 'POST', body: {}}); if (session && value.idle_expires_at) session.idle_expires_at = value.idle_expires_at; } catch { /* send clears invalid state */ }
  }
  const recheck = async () => { clear(); try { await bootstrap(); await refreshSession(); } catch { clear(); } };
  const visibility = () => { if (document.visibilityState === 'hidden') clear(); else void recheck(); };
  ['pointerdown', 'keydown', 'touchstart'].forEach(name => window.addEventListener(name, activity, {passive: true}));
  document.addEventListener('visibilitychange', visibility);
  window.addEventListener('pageshow', recheck);
  const timer = setInterval(async () => {
    if (!session || document.visibilityState !== 'visible') return;
    const deadline = Math.min(Date.parse(session.idle_expires_at), Date.parse(session.absolute_expires_at));
    if (Date.now() >= deadline) { clear(); return; }
    try { await refreshSession(); } catch { clear(); }
  }, 30000);
  return {
    bootstrap, refreshSession, clear,
    request(path, options) { return send(path, options); },
    subscribe(fn) { listeners.add(fn); return () => listeners.delete(fn); },
    registerSensitiveCleanup(fn) { cleaners.add(fn); return () => cleaners.delete(fn); },
    login(email, password) { return authenticate('auth/login', {email, password}); },
    reauthenticate(password) { return authenticate('auth/reauthenticate', {password}); },
    async enroll(token, email, password) {
      history.replaceState(null, '', location.pathname);
      await bootstrap(); await send('/api/v1/auth/invitation', {method: 'POST', body: {token}, publicAuth: true});
      return send('/_allauth/browser/v1/auth/signup', {method: 'POST', body: {email, password}, publicAuth: true});
    },
    async resetRequest(email) { await bootstrap(); return send('/_allauth/browser/v1/auth/password/request', {method: 'POST', body: {email}, publicAuth: true}); },
    async resetPassword(key, password) { history.replaceState(null, '', location.pathname); await bootstrap(); const result = await send('/_allauth/browser/v1/auth/password/reset', {method: 'POST', body: {key, password}, publicAuth: true}); clear(); return result; },
    async verifyEmail(key) { history.replaceState(null, '', location.pathname); await bootstrap(); return send('/_allauth/browser/v1/auth/email/verify', {method: 'POST', body: {key}, publicAuth: true}); },
    async logout() { try { await send('/_allauth/browser/v1/auth/session', {method: 'DELETE', publicAuth: true}); } finally { clear(); } },
    async switchContext(grant_id) { return send('/api/v1/session/context', {method: 'POST', body: {grant_id}}); },
    async query(path) { const value = await send(path); cache.set(path, value); return value; },
    mutation(path, body) { return send(path, {method: 'POST', body}); },
    resumeUploader(id) { if (!/^[0-9a-f]{8}-[0-9a-f-]{27}$/.test(id) || !session) throw new Error('Invalid continuation'); location.assign(apiOrigin + '/o/continue/' + id + '/'); },
    dispose() { clear(); clearInterval(timer); listeners.clear(); cleaners.clear(); ['pointerdown', 'keydown', 'touchstart'].forEach(name => window.removeEventListener(name, activity)); document.removeEventListener('visibilitychange', visibility); window.removeEventListener('pageshow', recheck); }
  };
}
