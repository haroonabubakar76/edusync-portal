/* ═══════════════════════════════════════════════════════
   EduSync Portal — Shared Utilities
   api.js · auth · storage · offline queue
═══════════════════════════════════════════════════════ */

const API_BASE =
  window.EDUSYNC_API || 'https://edusync-portal-48db.onrender.com';

/* ── Token Storage ─────────────────────────────────── */
const Auth = {
  save(token, user) {
    localStorage.setItem('es_token', token);
    localStorage.setItem('es_user', JSON.stringify(user));
  },
  token() { return localStorage.getItem('es_token'); },
  user() {
    try { return JSON.parse(localStorage.getItem('es_user')); }
    catch { return null; }
  },
  clear() {
    localStorage.removeItem('es_token');
    localStorage.removeItem('es_user');
  },
  isLoggedIn() { return !!this.token() && !!this.user(); },
  redirectIfLoggedIn() {
    if (!this.isLoggedIn()) { window.location.href = 'index.html'; return; }
    const user = this.user();
    if (!user) { window.location.href = 'index.html'; }
  }
};

/* ── API Client ────────────────────────────────────── */
const API = {
  async request(method, path, body = null) {
    const headers = { 'Content-Type': 'application/json' };
    const token = Auth.token();
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const opts = { method, headers };
    if (body) opts.body = JSON.stringify(body);

    try {
      const res = await fetch(`${API_BASE}${path}`, opts);
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Request failed');
      return { ok: true, data };
    } catch (err) {
      return { ok: false, error: err.message };
    }
  },
  get(path)         { return this.request('GET', path); },
  post(path, body)  { return this.request('POST', path, body); },
  patch(path, body) { return this.request('PATCH', path, body); },
};

/* ── Offline Queue (SQLite-like via localStorage) ──── */
const OfflineQueue = {
  _key: 'es_offline_queue',
  all() {
    try { return JSON.parse(localStorage.getItem(this._key)) || []; }
    catch { return []; }
  },
  add(entry) {
    const q = this.all();
    q.push({ ...entry, id: Date.now(), ts: new Date().toISOString() });
    localStorage.setItem(this._key, JSON.stringify(q));
  },
  remove(id) {
    const q = this.all().filter(e => e.id !== id);
    localStorage.setItem(this._key, JSON.stringify(q));
  },
  async flush() {
    if (!navigator.onLine) return;
    const queue = this.all();
    for (const entry of queue) {
      const result = await API.post(entry.path, entry.body);
      if (result.ok) this.remove(entry.id);
    }
  }
};

/* ── Auto-flush on connection ──────────────────────── */
window.addEventListener('online', () => OfflineQueue.flush());

/* ── Helpers ───────────────────────────────────────── */
function formatTerm(t) {
  return { first: 'First Term', second: 'Second Term', third: 'Third Term' }[t] || t;
}

function gradeColor(grade) {
  return { A: '#1B7B4B', B: '#2E75B6', C: '#D4A017', D: '#E67E22', F: '#C0392B' }[grade] || '#666';
}

function showToast(msg, type = 'success') {
  const existing = document.querySelector('.es-toast');
  if (existing) existing.remove();

  const toast = document.createElement('div');
  toast.className = 'es-toast';
  toast.style.cssText = `
    position:fixed; bottom:24px; left:50%; transform:translateX(-50%);
    background:${type === 'success' ? '#1B7B4B' : '#C0392B'};
    color:#fff; padding:12px 20px; border-radius:10px;
    font-size:14px; font-weight:600; z-index:9999;
    box-shadow:0 4px 16px rgba(0,0,0,0.2);
    animation: slideUp 0.3s ease;
    white-space: nowrap;
  `;
  toast.textContent = msg;

  const style = document.createElement('style');
  style.textContent = `@keyframes slideUp { from { opacity:0; transform:translateX(-50%) translateY(16px); } to { opacity:1; transform:translateX(-50%) translateY(0); } }`;
  document.head.appendChild(style);
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 3000);
}
