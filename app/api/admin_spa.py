"""Admin SPA — single-file React-style admin UI.

Uses the same auth as the user UI but with admin role.
"""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

ADMIN_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>MK Trader · Admin</title>
<style>
  :root {
    --bg: #060812; --surface: #0d1220; --surface2: #1a2138;
    --border: #2a3148; --text: #e6e8f0; --muted: #8b93a7;
    --primary: #6366f1; --primary-hover: #4f46e5;
    --success: #10b981; --warning: #f59e0b; --danger: #ef4444;
    --critical: #dc2626;
  }
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  html, body, #root { height: 100%; background: var(--bg); color: var(--text); font-family: system-ui, -apple-system, sans-serif; font-size: 14px; line-height: 1.5; }
  a { color: var(--primary); text-decoration: none; }
  a:hover { text-decoration: underline; }

  .layout { display: flex; height: 100vh; }
  .sidebar {
    width: 240px; background: var(--surface); border-right: 1px solid var(--border);
    display: flex; flex-direction: column; flex-shrink: 0;
  }
  .sidebar-logo { padding: 16px 20px; font-size: 18px; font-weight: 700; color: var(--primary); border-bottom: 1px solid var(--border); }
  .sidebar-logo .badge { display: inline-block; background: var(--critical); color: #fff; font-size: 9px; font-weight: 700; padding: 2px 5px; border-radius: 3px; vertical-align: super; margin-left: 4px; }
  .sidebar-nav { flex: 1; padding: 8px; overflow-y: auto; }
  .nav-section { font-size: 10px; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: var(--muted); padding: 10px 12px 4px; }
  .nav-item { display: flex; align-items: center; gap: 8px; padding: 7px 12px; border-radius: 6px; color: var(--muted); cursor: pointer; font-weight: 500; margin-bottom: 1px; }
  .nav-item:hover { background: var(--surface2); color: var(--text); text-decoration: none; }
  .nav-item.active { background: var(--primary); color: #fff; }
  .nav-item.danger-zone { color: var(--danger); }
  .nav-item.danger-zone:hover { background: rgba(239,68,68,0.1); color: var(--danger); }

  .main { flex: 1; overflow-y: auto; padding: 20px 28px; }
  .page-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; }
  .page-title { font-size: 22px; font-weight: 700; }
  .page-sub { color: var(--muted); font-size: 13px; margin-top: 2px; }

  .card { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 18px; margin-bottom: 14px; }
  .card-title { font-size: 14px; font-weight: 600; margin-bottom: 12px; }

  .stat-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(170px, 1fr)); gap: 12px; margin-bottom: 18px; }
  .stat-card { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 14px 16px; }
  .stat-label { font-size: 11px; color: var(--muted); margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.05em; }
  .stat-value { font-size: 26px; font-weight: 700; }
  .stat-value.green { color: var(--success); }
  .stat-value.yellow { color: var(--warning); }
  .stat-value.red { color: var(--danger); }

  table { width: 100%; border-collapse: collapse; }
  th { text-align: left; font-size: 10px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); padding: 8px 12px; border-bottom: 1px solid var(--border); }
  td { padding: 9px 12px; border-bottom: 1px solid var(--surface2); font-size: 13px; }
  tr:hover td { background: var(--surface2); }

  .btn { display: inline-flex; align-items: center; gap: 5px; padding: 6px 14px; border-radius: 6px; font-size: 12px; font-weight: 600; cursor: pointer; border: none; transition: background 0.15s; }
  .btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .btn-primary { background: var(--primary); color: #fff; }
  .btn-primary:hover:not(:disabled) { background: var(--primary-hover); }
  .btn-success { background: var(--success); color: #fff; }
  .btn-danger { background: var(--danger); color: #fff; }
  .btn-critical { background: var(--critical); color: #fff; }
  .btn-ghost { background: transparent; color: var(--muted); border: 1px solid var(--border); }
  .btn-ghost:hover { background: var(--surface2); color: var(--text); }
  .btn-sm { padding: 4px 10px; font-size: 11px; }

  .badge { display: inline-flex; align-items: center; padding: 2px 8px; border-radius: 12px; font-size: 10px; font-weight: 700; letter-spacing: 0.05em; text-transform: uppercase; }
  .badge-gray { background: var(--surface2); color: var(--muted); }
  .badge-green { background: rgba(16,185,129,0.15); color: var(--success); }
  .badge-blue { background: rgba(99,102,241,0.15); color: var(--primary); }
  .badge-red { background: rgba(239,68,68,0.15); color: var(--danger); }
  .badge-yellow { background: rgba(245,158,11,0.15); color: var(--warning); }

  .form-group { margin-bottom: 14px; }
  .form-label { display: block; font-size: 11px; font-weight: 700; color: var(--muted); margin-bottom: 5px; text-transform: uppercase; letter-spacing: 0.05em; }
  .form-input, .form-select, .form-textarea {
    width: 100%; padding: 7px 11px; background: var(--bg); border: 1px solid var(--border);
    border-radius: 6px; color: var(--text); font-size: 13px; font-family: inherit;
  }
  .form-input:focus, .form-select:focus, .form-textarea:focus { outline: none; border-color: var(--primary); }
  .form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }

  .error-banner { background: rgba(239,68,68,0.1); border: 1px solid var(--danger); border-radius: 6px; padding: 10px 14px; color: var(--danger); font-size: 12px; margin-bottom: 14px; }
  .success-banner { background: rgba(16,185,129,0.1); border: 1px solid var(--success); border-radius: 6px; padding: 10px 14px; color: var(--success); font-size: 12px; margin-bottom: 14px; }
  .warning-banner { background: rgba(245,158,11,0.1); border: 1px solid var(--warning); border-radius: 6px; padding: 10px 14px; color: var(--warning); font-size: 12px; margin-bottom: 14px; }

  .empty { text-align: center; padding: 40px 20px; color: var(--muted); font-size: 13px; }

  .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
  .grid-3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }

  ::-webkit-scrollbar { width: 6px; height: 6px; }
  ::-webkit-scrollbar-track { background: var(--bg); }
  ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
  ::-webkit-scrollbar-thumb:hover { background: var(--muted); }
</style>
</head>
<body>
<div class="layout">
  <aside class="sidebar">
    <div class="sidebar-logo">MK Trader<span class="badge">ADMIN</span></div>
    <nav class="sidebar-nav">
      <div class="nav-section">Overview</div>
      <a class="nav-item" data-route="overview">▦ Overview</a>

      <div class="nav-section">Users</div>
      <a class="nav-item" data-route="users">◉ Users</a>
      <a class="nav-item" data-route="audit">≡ Audit Log</a>

      <div class="nav-section">Trading</div>
      <a class="nav-item" data-route="strategies">◎ All Strategies</a>
      <a class="nav-item" data-route="executions">▶ Executions</a>
      <a class="nav-item" data-route="signals">◈ All Signals</a>

      <div class="nav-section">Operations</div>
      <a class="nav-item" data-route="operations"><span id="nav-status-dot" style="display:inline-block;width:7px;height:7px;border-radius:50%;background:#6b7280;margin-right:6px;vertical-align:middle"></span>◈ Bot Operations</a>
      <a class="nav-item" data-route="health">♥ System Health</a>
      <a class="nav-item" data-route="logs">☰ Logs &amp; Events</a>
      <a class="nav-item" data-route="alerts">⚠ Alerts</a>

      <div class="nav-section">Settings</div>
      <a class="nav-item" data-route="settings">⚙ Settings</a>

      <div class="nav-section">Danger Zone</div>
      <a class="nav-item danger-zone" data-route="emergency">⛔ Emergency</a>
    </nav>
    <div style="padding: 12px 16px; border-top: 1px solid var(--border); font-size: 12px;">
      <div id="me-name" style="font-weight: 600;"></div>
      <div id="me-role" style="color: var(--muted); font-size: 10px;"></div>
      <a href="/ui" class="btn btn-ghost btn-sm" style="margin-top: 8px; width: 100%; justify-content: center;">User UI →</a>
    </div>
  </aside>
  <main class="main">
    <div id="debug-log" style="background:#1a2138;color:#f59e0b;font-size:11px;padding:6px 12px;border-radius:4px;margin-bottom:8px;font-family:monospace;"></div>
    <div id="root">Loading…</div>
  </main>
</div>

<script>
/* Admin SPA — minimal vanilla JS, no build step. */

// ── WebSocket client for live bot events ─────────────────────────────

const eventLog = [];
let _botRunning = false;
let _eventFeed = null;   // ref to live-feed div in the operations page
let _statusBadge = null; // ref to status badge in sidebar

function connectWS() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  const ws = new WebSocket(proto + '://' + location.host + '/ws');
  ws.addEventListener('message', ev => {
    try {
      const msg = JSON.parse(ev.data);
      if (msg.type === 'status') {
        _botRunning = !!msg.running;
        updateBotStatusBadge(msg);
        if (_eventFeed) renderEventFeed();
      } else if (['bot_started', 'bot_stopped', 'bot_stop_requested', 'events', 'error', 'ping'].includes(msg.type)) {
        if (msg.type !== 'ping') {
          eventLog.unshift({ ...msg, ts: new Date().toLocaleTimeString() });
          if (eventLog.length > 50) eventLog.pop();
        }
        if (_eventFeed) renderEventFeed();
      }
    } catch (_) {}
  });
  ws.addEventListener('close', () => { setTimeout(connectWS, 3000); });
}

function updateBotStatusBadge(status) {
  // Sidebar dot
  const dot = document.getElementById('nav-status-dot');
  if (dot) dot.style.background = status.running ? '#22c55e' : '#6b7280';
  // Operations page badge
  if (_statusBadge) {
    const d = _statusBadge.querySelector('.status-dot');
    const t = _statusBadge.querySelector('.status-text');
    if (!d || !t) return;
    d.style.background = status.running ? '#22c55e' : '#6b7280';
    t.textContent = status.running ? 'Running' : 'Stopped';
    t.style.color = status.running ? '#22c55e' : '#6b7280';
  }
}

function renderEventFeed() {
  if (!_eventFeed) return;
  _eventFeed.innerHTML = '';
  for (const ev of eventLog.slice(0, 30)) {
    const row = document.createElement('div');
    row.style.cssText = 'display:flex;align-items:center;gap:8px;padding:6px 0;border-bottom:1px solid var(--border)';
    const dot = document.createElement('span');
    dot.style.cssText = 'width:6px;height:6px;border-radius:50%;flex-shrink:0;background=' + (ev.type === 'error' ? '#ef4444' : ev.type.startsWith('bot_') ? '#22c55e' : '#60a5fa');
    const meta = document.createElement('span');
    meta.style.cssText = 'font-size:11px;color:var(--muted);flex-shrink:0;min-width:70px';
    meta.textContent = ev.ts;
    const type = document.createElement('span');
    type.style.cssText = 'font-size:11px;font-weight:600;color=' + (ev.type === 'error' ? '#ef4444' : '#a78bfa') + ';min-width:120px';
    type.textContent = ev.type;
    const msg = document.createElement('span');
    msg.style.cssText = 'font-size:12px;color:var(--text)';
    msg.textContent = ev.message || '';
    row.appendChild(dot); row.appendChild(meta); row.appendChild(type); row.appendChild(msg);
    _eventFeed.appendChild(row);
  }
  if (!eventLog.length) {
    const empty = document.createElement('div');
    empty.style.cssText = 'color:var(--muted);font-size:12px;text-align:center;padding:16px';
    empty.textContent = 'No events yet — start the bot to see live activity.';
    _eventFeed.appendChild(empty);
  }
}

connectWS();
function headers() {
  const session = localStorage.getItem('mk_token');
  if (session) return { 'Authorization': 'Bearer ' + session, 'Content-Type': 'application/json' };
  const adminKey = sessionStorage.getItem('mk_admin_token');
  if (adminKey) return { 'X-Admin-Token': adminKey, 'Content-Type': 'application/json' };
  return { 'Content-Type': 'application/json' };
}

function hasToken() {
  return !!(localStorage.getItem('mk_token') || sessionStorage.getItem('mk_admin_token'));
}

async function api(method, path, body) {
  const res = await fetch(path, {
    method,
    headers: headers(),
    body: body ? JSON.stringify(body) : undefined,
  });
  if (res.status === 401) { location.href = '/admin/login'; throw new Error('not authenticated'); }
  if (!res.ok) {
    const msg = await res.text().catch(() => res.statusText);
    throw new Error(msg);
  }
  return res.json();
}

function h(tag, props={}, children=[]) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === 'class') el.className = v;
    else if (k === 'onClick') el.addEventListener('click', v);
    else if (k === 'html') el.innerHTML = v;
    else if (k === 'style') el.style.cssText = v;
    else el.setAttribute(k, v);
  }
  for (const c of [].concat(children)) {
    if (c == null) continue;
    el.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
  }
  return el;
}

const root = document.getElementById('root');
let me = null;
let currentRoute = 'overview';

async function loadMe() {
  try {
    me = await api('GET', '/me');
    document.getElementById('me-name').textContent = me.display_name || me.email;
    document.getElementById('me-role').textContent = me.role + ' · ' + me.status;
    if (me.role !== 'admin') {
      root.innerHTML = '<div class="error-banner">Admin role required. <a href="/admin/login">Sign in as admin</a></div>';
      return false;
    }
    return true;
  } catch (e) {
    root.innerHTML = '<div class="error-banner">Could not load admin context. <a href="/admin/login">Sign in</a></div>';
    return false;
  }
}

// ── Page renderers ────────────────────────────────────────────────

const pages = {
  overview: async () => {
    const [users, strategies, signals, health] = await Promise.all([
      api('GET', '/admin/users').catch(() => []),
      api('GET', '/admin/strategies').catch(() => []),
      api('GET', '/signals?limit=10').catch(() => []),
      api('GET', '/health/system').catch(() => null),
    ]);
    const live = strategies.filter(s => s.lifecycle_state === 'LIVE').length;
    const paper = strategies.filter(s => s.lifecycle_state === 'PAPER').length;
    return [
      h('div', { class: 'page-header' }, [
        h('h1', { class: 'page-title' }, 'Admin Overview'),
        h('div', { class: 'page-sub' }, 'System-wide view across all users'),
      ]),
      h('div', { class: 'stat-grid' }, [
        h('div', { class: 'stat-card' }, [h('div', { class: 'stat-label' }, 'Users'), h('div', { class: 'stat-value' }, String(users.length))]),
        h('div', { class: 'stat-card' }, [h('div', { class: 'stat-label' }, 'Total Strategies'), h('div', { class: 'stat-value' }, String(strategies.length))]),
        h('div', { class: 'stat-card' }, [h('div', { class: 'stat-label' }, 'Live'), h('div', { class: 'stat-value green' }, String(live))]),
        h('div', { class: 'stat-card' }, [h('div', { class: 'stat-label' }, 'Paper'), h('div', { class: 'stat-value yellow' }, String(paper))]),
        h('div', { class: 'stat-card' }, [h('div', { class: 'stat-label' }, 'Signals (10)'), h('div', { class: 'stat-value' }, String(signals.length))]),
        h('div', { class: 'stat-card' }, [
          h('div', { class: 'stat-label' }, 'System'),
          h('div', { class: 'stat-value ' + (health?.status === 'healthy' ? 'green' : 'yellow') }, health?.status || '—'),
        ]),
      ]),
    ];
  },

  users: async () => {
    const users = await api('GET', '/admin/users');
    const table = h('table', { style: 'width:100%;border-collapse:collapse' });
    const thead = h('thead', {}, h('tr', {}, [
      h('th', { style: 'text-align:left;padding:10px 12px;border-bottom:1px solid var(--border);color:var(--muted);font-size:11px;font-weight:600' }, 'Email'),
      h('th', { style: 'text-align:left;padding:10px 12px;border-bottom:1px solid var(--border);color:var(--muted);font-size:11px;font-weight:600' }, 'Name'),
      h('th', { style: 'text-align:left;padding:10px 12px;border-bottom:1px solid var(--border);color:var(--muted);font-size:11px;font-weight:600' }, 'Role'),
      h('th', { style: 'text-align:left;padding:10px 12px;border-bottom:1px solid var(--border);color:var(--muted);font-size:11px;font-weight:600' }, 'Status'),
      h('th', { style: 'text-align:left;padding:10px 12px;border-bottom:1px solid var(--border);color:var(--muted);font-size:11px;font-weight:600' }, 'Created'),
      h('th', { style: 'text-align:right;padding:10px 12px;border-bottom:1px solid var(--border);color:var(--muted);font-size:11px;font-weight:600' }, ''),
    ]));
    const tbody = h('tbody', {});
    for (const u of users) {
      const roleBadge = h('span', { class: 'badge ' + (u.role === 'admin' ? 'badge-red' : 'badge-blue') }, u.role);
      const statusBadge = h('span', { class: 'badge ' + (u.status === 'active' ? 'badge-green' : 'badge-yellow') }, u.status);
      const actionCell = u.status === 'active'
        ? h('button', { class: 'btn btn-ghost btn-sm', onClick: () => suspendUser(u.id) }, 'Suspend')
        : h('span', { class: 'badge badge-gray' }, 'suspended');
      tbody.appendChild(h('tr', { style: 'border-bottom:1px solid var(--border)' }, [
        h('td', { style: 'padding:8px 12px' }, u.email),
        h('td', { style: 'padding:8px 12px' }, u.display_name || ''),
        h('td', { style: 'padding:8px 12px' }, [roleBadge]),
        h('td', { style: 'padding:8px 12px' }, [statusBadge]),
        h('td', { style: 'padding:8px 12px' }, u.created_at ? new Date(u.created_at).toLocaleDateString() : '—'),
        h('td', { style: 'padding:8px 12px;text-align:right' }, [actionCell]),
      ]));
    }
    table.appendChild(thead);
    table.appendChild(tbody);
    return [
      h('div', { class: 'page-header' }, [h('h1', { class: 'page-title' }, 'Users')]),
      h('div', { class: 'card', style: 'padding:0;overflow:auto' }, [table]),
    ];
  },

  audit: async () => {
    const rows = await api('GET', '/admin/audit?limit=100');
    const table = h('table', { style: 'width:100%;border-collapse:collapse' });
    const thead = h('thead', {}, h('tr', {}, [
      h('th', { style: 'text-align:left;padding:10px 12px;border-bottom:1px solid var(--border);color:var(--muted);font-size:11px;font-weight:600' }, 'When'),
      h('th', { style: 'text-align:left;padding:10px 12px;border-bottom:1px solid var(--border);color:var(--muted);font-size:11px;font-weight:600' }, 'Actor'),
      h('th', { style: 'text-align:left;padding:10px 12px;border-bottom:1px solid var(--border);color:var(--muted);font-size:11px;font-weight:600' }, 'Role'),
      h('th', { style: 'text-align:left;padding:10px 12px;border-bottom:1px solid var(--border);color:var(--muted);font-size:11px;font-weight:600' }, 'Action'),
      h('th', { style: 'text-align:left;padding:10px 12px;border-bottom:1px solid var(--border);color:var(--muted);font-size:11px;font-weight:600' }, 'Target'),
      h('th', { style: 'text-align:left;padding:10px 12px;border-bottom:1px solid var(--border);color:var(--muted);font-size:11px;font-weight:600' }, 'Result'),
    ]));
    const tbody = h('tbody', {});
    for (const r of rows) {
      const badge = h('span', { class: 'badge ' + (r.result === 'ok' ? 'badge-green' : 'badge-red') }, r.result || 'ok');
      tbody.appendChild(h('tr', { style: 'border-bottom:1px solid var(--border)' }, [
        h('td', { style: 'padding:8px 12px;font-size:11px;color:var(--muted)' }, new Date(r.created_at).toLocaleString()),
        h('td', { style: 'padding:8px 12px' }, r.actor_user_id || '—'),
        h('td', { style: 'padding:8px 12px' }, [h('span', { class: 'badge badge-gray' }, r.actor_role)]),
        h('td', { style: 'padding:8px 12px' }, r.action),
        h('td', { style: 'padding:8px 12px;font-size:11px' }, r.target_id || r.target_type || '—'),
        h('td', { style: 'padding:8px 12px' }, [badge]),
      ]));
    }
    table.appendChild(thead);
    table.appendChild(tbody);
    return [
      h('div', { class: 'page-header' }, [h('h1', { class: 'page-title' }, 'Audit Log')]),
      h('div', { class: 'card', style: 'padding:0;overflow:auto' }, [table]),
    ];
  },

  strategies: async () => {
    const strategies = await api('GET', '/admin/strategies');
    const table = h('table', { style: 'width:100%;border-collapse:collapse' });
    const thead = h('thead', {}, h('tr', {}, [
      h('th', { style: 'text-align:left;padding:10px 12px;border-bottom:1px solid var(--border);color:var(--muted);font-size:11px;font-weight:600' }, 'Name'),
      h('th', { style: 'text-align:left;padding:10px 12px;border-bottom:1px solid var(--border);color:var(--muted);font-size:11px;font-weight:600' }, 'User'),
      h('th', { style: 'text-align:left;padding:10px 12px;border-bottom:1px solid var(--border);color:var(--muted);font-size:11px;font-weight:600' }, 'Market'),
      h('th', { style: 'text-align:left;padding:10px 12px;border-bottom:1px solid var(--border);color:var(--muted);font-size:11px;font-weight:600' }, 'Mode'),
      h('th', { style: 'text-align:left;padding:10px 12px;border-bottom:1px solid var(--border);color:var(--muted);font-size:11px;font-weight:600' }, 'State'),
      h('th', { style: 'text-align:left;padding:10px 12px;border-bottom:1px solid var(--border);color:var(--muted);font-size:11px;font-weight:600' }, 'Updated'),
    ]));
    const tbody = h('tbody', {});
    for (const s of strategies) {
      tbody.appendChild(h('tr', { style: 'border-bottom:1px solid var(--border)' }, [
        h('td', { style: 'padding:8px 12px' }, h('strong', {}, s.name)),
        h('td', { style: 'padding:8px 12px;font-size:11px;color:var(--muted)' }, (s.user_id || '').slice(0, 8)),
        h('td', { style: 'padding:8px 12px' }, s.market || '—'),
        h('td', { style: 'padding:8px 12px' }, s.execution_mode || '—'),
        h('td', { style: 'padding:8px 12px' }, [h('span', { class: 'badge ' + stateClass(s.lifecycle_state) }, s.lifecycle_state || '—')]),
        h('td', { style: 'padding:8px 12px;font-size:11px;color:var(--muted)' }, s.updated_at ? new Date(s.updated_at).toLocaleString() : '—'),
      ]));
    }
    table.appendChild(thead);
    table.appendChild(tbody);
    return [
      h('div', { class: 'page-header' }, [
        h('h1', { class: 'page-title' }, 'All Strategies'),
        h('div', { class: 'page-sub' }, strategies.length + ' total across all users'),
      ]),
      h('div', { class: 'card', style: 'padding:0;overflow:auto' }, [table]),
    ];
  },

  executions: async () => {
    return [
      h('div', { class: 'page-header' }, [h('h1', { class: 'page-title' }, 'Executions')]),
      h('div', { class: 'card' }, [h('div', { class: 'empty' }, 'Execution history: orders + trades. Use the controls API: /orders, /trades, /positions, /balances')]),
    ];
  },

  signals: async () => {
    const signals = await api('GET', '/signals?limit=50');
    const table = h('table', { style: 'width:100%;border-collapse:collapse' });
    const thead = h('thead', {}, h('tr', {}, [
      h('th', { style: 'text-align:left;padding:10px 12px;border-bottom:1px solid var(--border);color:var(--muted);font-size:11px;font-weight:600' }, 'Symbol'),
      h('th', { style: 'text-align:left;padding:10px 12px;border-bottom:1px solid var(--border);color:var(--muted);font-size:11px;font-weight:600' }, 'Side'),
      h('th', { style: 'text-align:left;padding:10px 12px;border-bottom:1px solid var(--border);color:var(--muted);font-size:11px;font-weight:600' }, 'Confidence'),
      h('th', { style: 'text-align:left;padding:10px 12px;border-bottom:1px solid var(--border);color:var(--muted);font-size:11px;font-weight:600' }, 'Strategy'),
      h('th', { style: 'text-align:left;padding:10px 12px;border-bottom:1px solid var(--border);color:var(--muted);font-size:11px;font-weight:600' }, 'Entry'),
      h('th', { style: 'text-align:left;padding:10px 12px;border-bottom:1px solid var(--border);color:var(--muted);font-size:11px;font-weight:600' }, 'TP / SL'),
      h('th', { style: 'text-align:left;padding:10px 12px;border-bottom:1px solid var(--border);color:var(--muted);font-size:11px;font-weight:600' }, 'Trade'),
      h('th', { style: 'text-align:left;padding:10px 12px;border-bottom:1px solid var(--border);color:var(--muted);font-size:11px;font-weight:600' }, 'When'),
    ]));
    const tbody = h('tbody', {});
    for (const s of signals) {
      const sideCls = s.side === 'BUY' ? 'badge-green' : s.side === 'SELL' ? 'badge-red' : 'badge-gray';
      const tradeBadge = s.trading_status === 'EXECUTED' ? 'badge-green'
        : s.trading_status === 'PENDING' ? 'badge-yellow'
        : s.trading_status ? 'badge-gray' : '—';
      const row = h('tr', {
        style: 'border-bottom:1px solid var(--border);cursor:pointer;background:' +
          (s.trading_status === 'EXECUTED' ? '#064e3b33' : 'transparent')
      }, [
        h('td', { style: 'padding:8px 12px' }, h('strong', {}, s.symbol || '—')),
        h('td', { style: 'padding:8px 12px' }, [h('span', { class: 'badge ' + sideCls }, s.side || '—')]),
        h('td', { style: 'padding:8px 12px' }, s.confidence != null ? (s.confidence * 100).toFixed(0) + '%' : '—'),
        h('td', { style: 'padding:8px 12px;font-size:11px;color:var(--muted)' }, s.strategy || s.strategy_name || '—'),
        h('td', { style: 'padding:8px 12px;font-size:12px' }, s.entry_price != null ? '$' + s.entry_price : '—'),
        h('td', { style: 'padding:8px 12px;font-size:11px;color:var(--muted)' },
          (s.tp1 ? 'TP $' + s.tp1 : '—') + (s.stop_loss ? ' · SL $' + s.stop_loss : '')),
        h('td', { style: 'padding:8px 12px' }, [h('span', { class: 'badge ' + tradeBadge }, s.trading_status || '—')]),
        h('td', { style: 'padding:8px 12px;font-size:11px;color:var(--muted)' },
          s.created_at ? new Date(s.created_at).toLocaleString() : s.timestamp ? new Date(s.timestamp).toLocaleString() : '—'),
      ]);
      row.addEventListener('click', () => viewSignal(s.id));
      tbody.appendChild(row);
    }
    table.appendChild(thead);
    table.appendChild(tbody);

    const detail = h('div', { class: 'card', style: 'margin-top:16px;padding:0;overflow:auto' });
    const detailBody = h('div', { style: 'padding:24px' });
    detailBody.appendChild(h('p', { style: 'color:var(--muted);font-size:13px' }, 'Click any signal row to view details and paper trade it.'));
    detail.appendChild(detailBody);

    let _active = null;
    async function viewSignal(id) {
      if (_active === id) return;
      _active = id;
      try {
        const sig = await api('GET', '/signals/' + id);
        detailBody.innerHTML = '';
        const header = h('div', { style: 'display:flex;justify-content:space-between;align-items:center;margin-bottom:16px' }, [
          h('h2', { style: 'margin:0;font-size:18px' }, sig.symbol + ' · ' + sig.side),
          h('button', { class: 'btn btn-ghost', onclick: 'location.hash="signals"' }, '✕ Close'),
        ]);
        detailBody.appendChild(header);

        const fields = [
          ['Side', sig.side],
          ['Confidence', sig.confidence != null ? (sig.confidence * 100).toFixed(0) + '%' : '—'],
          ['Entry', sig.entry_price != null ? '$' + sig.entry_price : '—'],
          ['TP1', sig.tp1 != null ? '$' + sig.tp1 : '—'],
          ['TP2', sig.tp2 != null ? '$' + sig.tp2 : '—'],
          ['Stop Loss', sig.stop_loss != null ? '$' + sig.stop_loss : '—'],
          ['Mode', sig.mode],
          ['Strategy', sig.strategy || sig.strategy_name || '—'],
          ['Signal Status', sig.signal_status],
          ['Trading Status', sig.trading_status || '—'],
          ['Telegram Status', sig.telegram_status || '—'],
          ['Square Status', sig.square_status || '—'],
        ];
        const grid = h('div', { style: 'display:grid;grid-template-columns:repeat(2,1fr);gap:8px 16px;font-size:13px' });
        for (const [k, v] of fields) {
          const row = h('div', {}, [
            h('span', { style: 'color:var(--muted);font-size:12px' }, k + ': '),
            h('span', { style: 'font-weight:600' }, String(v || '—')),
          ]);
          grid.appendChild(row);
        }
        detailBody.appendChild(grid);

        if (sig.reason) {
          const reason = h('div', { class: 'card', style: 'margin-top:12px;padding:12px;font-size:12px;color:var(--muted)' });
          reason.appendChild(h('div', { style: 'font-weight:600;color:var(--text);margin-bottom:4px' }, 'Reason'));
          reason.appendChild(h('div', {}, Array.isArray(sig.reason) ? sig.reason.join(' · ') : String(sig.reason)));
          detailBody.appendChild(reason);
        }

        const actions = h('div', { style: 'margin-top:16px;display:flex;gap:8px' });
        const tradeBtn = h('button', { class: 'btn btn-primary' }, '📈 Paper Trade This Signal');
        tradeBtn.onclick = async () => {
          tradeBtn.disabled = true; tradeBtn.textContent = 'Trading…';
          try {
            const r = await api('POST', '/dev/signals/' + sig.id + '/paper-trade', {});
            tradeBtn.textContent = '✓ Trade ' + (r.trade_id || '').slice(0, 8);
            tradeBtn.classList.remove('btn-primary'); tradeBtn.classList.add('btn-ghost');
            setTimeout(() => viewSignal(sig.id), 400);
          } catch (e) {
            tradeBtn.disabled = false; tradeBtn.textContent = '❌ ' + e.message;
          }
        };
        actions.appendChild(tradeBtn);
        detailBody.appendChild(actions);
      } catch (e) {
        detailBody.innerHTML = '<p style="color:var(--danger)">Failed to load: ' + e.message + '</p>';
      }
    }

    return [
      h('div', { class: 'page-header' }, [h('h1', { class: 'page-title' }, 'All Signals')]),
      h('div', { class: 'card', style: 'padding:0;overflow:auto' }, [table]),
      detail,
    ];
  },

  operations: async () => {
    const status = await api('GET', '/control/status');
    const adminStatus = await api('GET', '/admin/status');
    _botRunning = !!status.running;

    const card = h('div', { class: 'card' });
    card.appendChild(h('div', { class: 'card-title' }, 'Bot Control'));

    const statusRow = h('div', { style: 'display:flex;align-items:center;gap:16px;margin-bottom:16px' });
    const statusDot = h('span', { style: 'width:10px;height:10px;border-radius:50%;background:' + (_botRunning ? '#22c55e' : '#6b7280') });
    const statusTxt = h('span', { style: 'font-weight:700;font-size:14px;color:' + (_botRunning ? '#22c55e' : '#6b7280') }, _botRunning ? 'RUNNING' : 'STOPPED');
    statusRow.appendChild(statusDot);
    statusRow.appendChild(statusTxt);
    statusRow.appendChild(h('span', { style: 'color:var(--muted);font-size:12px' }, '— ' + (adminStatus.mode || 'paper').toUpperCase() + ' mode · ' + (adminStatus.symbol || 'BTCUSDT') + ' ' + (adminStatus.timeframe || '15m')));
    if (status.completed_cycles !== undefined) {
      statusRow.appendChild(h('span', { style: 'color:var(--muted);font-size:12px' }, '· ' + status.completed_cycles + ' cycles'));
    }
    card.appendChild(statusRow);

    const ctrls = h('div', { style: 'display:flex;gap:8px;flex-wrap:wrap' });
    const startBtn = h('button', { class: 'btn btn-primary' }, '▶ Start Bot');
    const stopBtn  = h('button', { class: 'btn btn-danger' }, '⏹ Stop Bot');
    const refreshBtn = h('button', { class: 'btn btn-ghost' }, '↻ Refresh Status');

    const setRunning = (r) => {
      startBtn.disabled = r; startBtn.style.opacity = r ? 0.5 : 1;
      stopBtn.disabled = !r; stopBtn.style.opacity = !r ? 0.5 : 1;
    };
    setRunning(_botRunning);

    startBtn.addEventListener('click', async () => {
      startBtn.disabled = true; startBtn.textContent = 'Starting…';
      try {
        const cycles = parseInt(prompt('Cycles (0 = infinite, default 0):', '0') || '0', 10);
        if (isNaN(cycles) || cycles < 0) { alert('Invalid cycles'); startBtn.disabled = false; startBtn.textContent = '▶ Start Bot'; return; }
        const r = await api('POST', '/control/start?cycles=' + cycles, {});
        eventLog.unshift({ type: 'bot_started', message: r.status, ts: new Date().toLocaleTimeString() });
        _botRunning = true; setRunning(true);
        statusDot.style.background = '#22c55e'; statusTxt.textContent = 'RUNNING'; statusTxt.style.color = '#22c55e';
        renderEventFeed();
      } catch (e) { alert('Start failed: ' + e.message); startBtn.disabled = false; startBtn.textContent = '▶ Start Bot'; }
    });

    stopBtn.addEventListener('click', async () => {
      if (!confirm('Stop the trading bot?')) return;
      stopBtn.disabled = true; stopBtn.textContent = 'Stopping…';
      try {
        const r = await api('POST', '/control/stop', {});
        eventLog.unshift({ type: 'bot_stop_requested', message: r.status, ts: new Date().toLocaleTimeString() });
        _botRunning = false; setRunning(false);
        statusDot.style.background = '#6b7280'; statusTxt.textContent = 'STOPPING…'; statusTxt.style.color = '#fbbf24';
        renderEventFeed();
      } catch (e) { alert('Stop failed: ' + e.message); stopBtn.disabled = false; stopBtn.textContent = '⏹ Stop Bot'; }
    });

    refreshBtn.addEventListener('click', async () => {
      try {
        const s = await api('GET', '/control/status');
        _botRunning = !!s.running;
        statusDot.style.background = _botRunning ? '#22c55e' : '#6b7280';
        statusTxt.textContent = _botRunning ? 'RUNNING' : 'STOPPED';
        statusTxt.style.color = _botRunning ? '#22c55e' : '#6b7280';
        setRunning(_botRunning);
      } catch (e) { alert('Refresh failed: ' + e.message); }
    });

    ctrls.appendChild(startBtn); ctrls.appendChild(stopBtn); ctrls.appendChild(refreshBtn);
    card.appendChild(ctrls);

    // Live event feed
    const feedCard = h('div', { class: 'card' });
    feedCard.appendChild(h('div', { class: 'card-title', style: 'display:flex;align-items:center;justify-content:space-between' }, [
      h('span', {}, 'Live Event Feed'),
      h('span', { style: 'color:var(--muted);font-size:11px' }, 'WebSocket · auto-updates'),
    ]));
    _eventFeed = h('div', { style: 'max-height:380px;overflow-y:auto;padding:0 4px' });
    feedCard.appendChild(_eventFeed);
    renderEventFeed();

    return [
      h('div', { class: 'page-header' }, [
        h('h1', { class: 'page-title' }, 'Bot Operations'),
        h('div', { class: 'page-sub' }, 'Start/stop the trading engine and watch events live'),
      ]),
      card,
      feedCard,
    ];
  },

  health: async () => {
    const h_ = await api('GET', '/health/system');
    const grid = h('div', { class: 'grid-3' });
    for (const [name, svc] of Object.entries(h_.services || {})) {
      const cls = svc.status === 'healthy' ? 'green' : svc.status === 'degraded' ? 'yellow' : 'red';
      grid.appendChild(h('div', { class: 'card' }, [
        h('div', { class: 'card-title' }, name),
        h('div', { class: 'stat-value ' + cls, style: 'font-size:18px' }, svc.status),
        svc.detail ? h('div', { style: 'color:var(--muted);font-size:11px;margin-top:6px' }, svc.detail) : null,
      ]));
    }
    return [
      h('div', { class: 'page-header' }, [
        h('h1', { class: 'page-title' }, 'System Health'),
        h('div', { class: 'page-sub' }, 'Aggregate of 8 service checks'),
      ]),
      grid,
    ];
  },

  logs: async () => {
    return [
      h('div', { class: 'page-header' }, [h('h1', { class: 'page-title' }, 'Logs &amp; Events')]),
      h('div', { class: 'card' }, [h('div', { class: 'empty' }, 'GET /events?limit=200 — bot_events table. GET /errors?limit=200 — errors table.')]),
    ];
  },

  alerts: async () => {
    return [
      h('div', { class: 'page-header' }, [h('h1', { class: 'page-title' }, 'Alerts')]),
      h('div', { class: 'card' }, [h('div', { class: 'empty' }, 'Configured via /emergency/* routes. Active pauses are visible on the Emergency page.')]),
    ];
  },

  emergency: async () => {
    const pauses = await api('GET', '/emergency/status');
    return [
      h('div', { class: 'page-header' }, [
        h('h1', { class: 'page-title' }, 'Emergency Controls'),
        h('div', { class: 'page-sub' }, 'Pause trading globally, by user, or by strategy'),
      ]),
      h('div', { class: 'warning-banner' }, '⚠ Pausing affects live trading immediately. Use with care.'),
      pauseForm(),
      h('div', { class: 'card' }, [
        h('div', { class: 'card-title' }, 'Active Pauses (' + (pauses.length || 0) + ')'),
        pauses.length === 0
          ? h('div', { class: 'empty' }, 'No active pauses')
          : (() => {
              const table = h('table', { style: 'width:100%;border-collapse:collapse' });
              table.appendChild(h('thead', {}, h('tr', {}, [
                h('th', { style: 'text-align:left;padding:10px 12px;border-bottom:1px solid var(--border);color:var(--muted);font-size:11px;font-weight:600' }, 'Scope'),
                h('th', { style: 'text-align:left;padding:10px 12px;border-bottom:1px solid var(--border);color:var(--muted);font-size:11px;font-weight:600' }, 'Target'),
                h('th', { style: 'text-align:left;padding:10px 12px;border-bottom:1px solid var(--border);color:var(--muted);font-size:11px;font-weight:600' }, 'Reason'),
                h('th', { style: 'text-align:left;padding:10px 12px;border-bottom:1px solid var(--border);color:var(--muted);font-size:11px;font-weight:600' }, 'When'),
                h('th', { style: 'text-align:right;padding:10px 12px;border-bottom:1px solid var(--border);color:var(--muted);font-size:11px;font-weight:600' }, ''),
              ])));
              const tbody = h('tbody', {});
              for (const p of pauses) {
                tbody.appendChild(h('tr', { style: 'border-bottom:1px solid var(--border)' }, [
                  h('td', { style: 'padding:8px 12px' }, [h('span', { class: 'badge badge-red' }, p.scope)]),
                  h('td', { style: 'padding:8px 12px;font-size:11px' }, p.scope_target || '—'),
                  h('td', { style: 'padding:8px 12px;font-size:12px' }, p.reason || '—'),
                  h('td', { style: 'padding:8px 12px;font-size:11px;color:var(--muted)' }, p.created_at ? new Date(p.created_at).toLocaleString() : '—'),
                  h('td', { style: 'padding:8px 12px;text-align:right' }, [h('button', { class: 'btn btn-success btn-sm', onClick: () => resumePause(p.id) }, 'Resume')]),
                ]));
              }
              table.appendChild(tbody);
              return table;
            })(),
      ]),
    ];
  },

  settings: async () => {
    const cfg = await api('GET', '/admin/config');
    const cfgEl = h('div', { class: 'card' });
    cfgEl.appendChild(h('div', { class: 'card-title' }, 'Paper Trading Config'));
    cfgEl.appendChild(h('div', { style: 'color:var(--muted);font-size:12px;margin-bottom:16px' }, 'Changes apply to the next bot cycle. Current values are highlighted below.'));

    const fields = [
      { key: 'paper_starting_balance', label: 'Starting Balance (USD)', step: '100', min: 100 },
      { key: 'paper_position_notional', label: 'Position Notional per Trade (USD)', step: '1', min: 1 },
      { key: 'max_leverage', label: 'Max Leverage (x)', step: '1', min: 1, max: 125, int: true },
      { key: 'risk_per_trade', label: 'Risk per Trade (% of balance)', step: '0.005', min: 0.001, max: 0.05 },
      { key: 'max_open_positions', label: 'Max Open Positions', step: '1', min: 1, max: 10, int: true },
      { key: 'min_signal_confidence', label: 'Min Signal Confidence (0–1)', step: '0.05', min: 0, max: 1 },
    ];

    const inputs = {};
    const form = h('div', { class: 'form-grid' });
    for (const f of fields) {
      const group = h('div', { class: 'form-group' });
      group.appendChild(h('label', { class: 'form-label' }, f.label));
      const input = h('input', {
        class: 'form-input',
        type: 'number',
        step: f.step,
        min: f.min,
        max: f.max,
        value: String(cfg[f.key]),
      });
      inputs[f.key] = input;
      group.appendChild(input);
      form.appendChild(group);
    }
    cfgEl.appendChild(form);

    const status = h('div', { style: 'margin-top:16px;padding:10px;border-radius:6px;font-size:12px;display:none' });

    const saveBtn = h('button', { class: 'btn btn-primary' }, '💾 Save Config');
    saveBtn.addEventListener('click', async () => {
      saveBtn.disabled = true;
      const body = {};
      for (const f of fields) {
        const v = parseFloat(inputs[f.key].value);
        if (isNaN(v)) { status.textContent = 'Invalid value for ' + f.label; status.style.display = 'block'; status.style.background = 'rgba(239,68,68,0.1)'; status.style.color = '#ef4444'; saveBtn.disabled = false; return; }
        body[f.key] = f.int ? Math.round(v) : v;
      }
      try {
        const r = await api('POST', '/admin/config', body);
        status.textContent = '✓ Saved. New values will apply on next bot cycle.';
        status.style.display = 'block';
        status.style.background = 'rgba(34,197,94,0.1)';
        status.style.color = '#22c55e';
        // Refresh current values
        setTimeout(() => navigate('settings'), 800);
      } catch (e) {
        status.textContent = 'Failed: ' + e.message;
        status.style.display = 'block';
        status.style.background = 'rgba(239,68,68,0.1)';
        status.style.color = '#ef4444';
      }
      saveBtn.disabled = false;
    });

    const resetBtn = h('button', { class: 'btn btn-ghost', style: 'margin-left:8px' }, 'Reset to Defaults');
    resetBtn.addEventListener('click', async () => {
      if (!confirm('Reset all paper config to defaults?')) return;
      const defaults = { paper_starting_balance: 10000, paper_position_notional: 10, max_leverage: 10, risk_per_trade: 0.01, max_open_positions: 3, min_signal_confidence: 0.10 };
      try {
        await api('POST', '/admin/config', defaults);
        status.textContent = '✓ Reset to defaults.';
        status.style.display = 'block';
        status.style.background = 'rgba(34,197,94,0.1)';
        status.style.color = '#22c55e';
        setTimeout(() => navigate('settings'), 800);
      } catch (e) { status.textContent = 'Failed: ' + e.message; status.style.display = 'block'; }
    });

    cfgEl.appendChild(h('div', { style: 'margin-top:16px;display:flex;align-items:center' }, [saveBtn, resetBtn, status]));

    return [
      h('div', { class: 'page-header' }, [
        h('h1', { class: 'page-title' }, 'System Settings'),
        h('div', { class: 'page-sub' }, 'Runtime configuration for paper trading'),
      ]),
      cfgEl,
      h('div', { class: 'card' }, [
        h('div', { class: 'card-title' }, 'Runtime Mode'),
        h('div', { style: 'font-size:12px;color:var(--muted)' }, 'Controlled by TRADING_MODE env var: paper | testnet | live. Use /ready to check current state.'),
      ]),
    ];
  },
};

function stateClass(s) {
  if (!s) return 'badge-gray';
  if (['LIVE', 'LIVE_ELIGIBLE', 'TESTNET', 'PAPER', 'KTEST', 'PBT'].includes(s)) return 'badge-green';
  if (s === 'PAUSED') return 'badge-yellow';
  return 'badge-gray';
}

function pauseForm() {
  const sel = h('select', { class: 'form-select' }, [
    h('option', { value: 'global' }, 'Global (everything)'),
    h('option', { value: 'user' }, 'By user (user_id)'),
    h('option', { value: 'strategy' }, 'By strategy (strategy_id)'),
    h('option', { value: 'venue' }, 'By venue (binance / bybit / ...)'),
  ]);
  const target = h('input', { class: 'form-input', placeholder: 'Target id (for non-global)' });
  const reason = h('input', { class: 'form-input', placeholder: 'Reason (required for audit)' });
  const close = h('input', { type: 'checkbox' });
  const btn = h('button', { class: 'btn btn-critical' }, '⛔ Activate Pause');
  btn.addEventListener('click', async () => {
    if (!reason.value.trim()) { alert('Reason required'); return; }
    btn.disabled = true;
    try {
      await api('POST', '/emergency/pause', {
        scope: sel.value, scope_target: target.value || null,
        reason: reason.value, close_positions: close.checked,
      });
      reason.value = ''; target.value = '';
      navigate('emergency');
    } catch (e) { alert('Failed: ' + e.message); }
    finally { btn.disabled = false; }
  });
  return h('div', { class: 'card' }, [
    h('div', { class: 'card-title' }, 'New Pause'),
    h('div', { class: 'form-row' }, [
      h('div', { class: 'form-group' }, [h('label', { class: 'form-label' }, 'Scope'), sel]),
      h('div', { class: 'form-group' }, [h('label', { class: 'form-label' }, 'Target id'), target]),
    ]),
    h('div', { class: 'form-group' }, [h('label', { class: 'form-label' }, 'Reason'), reason]),
    h('div', { class: 'form-group' }, [h('label', { style: 'display:flex;align-items:center;gap:6px;font-size:12px' }, [close, ' Close open positions on pause'])]),
    btn,
  ]);
}

async function suspendUser(userId) {
  if (!confirm('Suspend this user?')) return;
  try {
    await api('POST', '/admin/users/' + userId + '/suspend', {});
    navigate('users');
  } catch (e) { alert('Failed: ' + e.message); }
}

async function resumePause(pauseId) {
  if (!confirm('Resume?')) return;
  try {
    await api('POST', '/emergency/resume/' + pauseId, {});
    navigate('emergency');
  } catch (e) { alert('Failed: ' + e.message); }
}

// ── Router ────────────────────────────────────────────────────────

async function navigate(route) {
  if (route) currentRoute = route;
  // Highlight active nav
  document.querySelectorAll('.nav-item').forEach(el => {
    el.classList.toggle('active', el.getAttribute('data-route') === currentRoute);
  });
  // Render
  root.innerHTML = '<div style="color:var(--muted);padding:40px;text-align:center">Loading…</div>';
  try {
    const renderer = pages[currentRoute];
    if (!renderer) { root.innerHTML = '<div class="empty">Unknown route</div>'; return; }
    const els = await renderer();
    root.innerHTML = '';
    for (const el of els) root.appendChild(el);
  } catch (e) {
    root.innerHTML = '<div class="error-banner">Error: ' + e.message + '</div>';
  }
}

// Nav click handlers
document.querySelectorAll('.nav-item[data-route]').forEach(el => {
  el.addEventListener('click', e => { e.preventDefault(); navigate(el.getAttribute('data-route')); });
});

// ── Debug overlay (visible until everything works) ──────────────────
function debug(msg) {
  console.debug('[admin-spa]', msg);
  const el = document.getElementById('debug-log');
  if (el) el.textContent = msg;
}

// Init
(async () => {
  debug('init: hasToken=' + hasToken());
  if (!hasToken()) {
    debug('no token → redirecting to /admin/login');
    location.href = '/admin/login';
    return;
  }
  debug('token found, calling loadMe...');
  const ok = await loadMe();
  debug('loadMe → ' + ok + ', role=' + (me ? me.role : 'null'));
  if (ok) {
    debug('authenticated → navigating to overview');
    navigate('overview');
  } else {
    debug('loadMe failed — check error above');
  }
})();
</script>
</body>
</html>"""


@router.get("/admin/login", include_in_schema=False)
def admin_login():
    """Admin login page — sets sessionStorage token then redirects."""
    return HTMLResponse(
        content="""<!doctype html>
<html><head><title>Admin Login</title><style>
body { background:#060812; color:#e6e8f0; font-family:system-ui; display:flex; align-items:center; justify-content:center; height:100vh; margin:0; }
.card { background:#0d1220; border:1px solid #2a3148; border-radius:10px; padding:32px; width:360px; }
h1 { color:#6366f1; margin-bottom:6px; }
.muted { color:#8b93a7; font-size:13px; margin-bottom:20px; }
input, select { width:100%; padding:9px 12px; background:#060812; border:1px solid #2a3148; color:#e6e8f0; border-radius:6px; margin-bottom:12px; font-size:13px; }
.btn { width:100%; padding:10px; background:#6366f1; color:#fff; border:none; border-radius:6px; font-weight:600; cursor:pointer; }
.btn:hover { background:#4f46e5; }
.error { background:rgba(239,68,68,0.1); border:1px solid #ef4444; color:#ef4444; padding:10px; border-radius:6px; font-size:12px; margin-bottom:12px; display:none; }
.tabs { display:flex; border-bottom:1px solid #2a3148; margin-bottom:18px; }
.tab { flex:1; padding:8px; text-align:center; cursor:pointer; color:#8b93a7; font-size:12px; font-weight:600; border-bottom:2px solid transparent; }
.tab.active { color:#6366f1; border-bottom-color:#6366f1; }
</style></head><body>
<div class="card">
  <h1>MK Trader · Admin</h1>
  <div class="muted">Sign in to access the admin console</div>
  <div class="tabs"><div class="tab active" data-mode="login">Sign in</div><div class="tab" data-mode="token">Admin token</div></div>
  <div id="err" class="error"></div>
  <form id="f-login">
    <input type="email" id="email" placeholder="email" required />
    <input type="password" id="password" placeholder="password" required />
    <button class="btn" type="submit">Sign in</button>
  </form>
  <form id="f-token" style="display:none">
    <input type="text" id="token" placeholder="ADMIN_API_TOKEN" required />
    <button class="btn" type="submit">Use token</button>
  </form>
</div>
<script>
const err = document.getElementById('err');
function showError(m) { err.textContent = m; err.style.display = 'block'; }

document.querySelectorAll('.tab').forEach(t => t.addEventListener('click', e => {
  document.querySelectorAll('.tab').forEach(x => x.classList.remove('active'));
  t.classList.add('active');
  const mode = t.getAttribute('data-mode');
  document.getElementById('f-login').style.display = mode === 'login' ? 'block' : 'none';
  document.getElementById('f-token').style.display = mode === 'token' ? 'block' : 'none';
}));

document.getElementById('f-login').addEventListener('submit', async e => {
  e.preventDefault();
  try {
    const r = await fetch('/auth/login', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({email: document.getElementById('email').value, password: document.getElementById('password').value}),
    });
    if (!r.ok) throw new Error(await r.text());
    const d = await r.json();
    localStorage.setItem('mk_token', d.token);
    location.href = '/admin';
  } catch (e) { showError(e.message); }
});

document.getElementById('f-token').addEventListener('submit', async e => {
  e.preventDefault();
  const t = document.getElementById('token').value;
  // Validate
  try {
    const r = await fetch('/admin/status', { headers: {'X-Admin-Token': t} });
    if (!r.ok) throw new Error('Invalid admin token');
    sessionStorage.setItem('mk_admin_token', t);
    location.href = '/admin';
  } catch (e) { showError(e.message); }
});
</script>
</body></html>""")


@router.get("/admin", include_in_schema=False)
def admin_dashboard():
    return HTMLResponse(
        content=ADMIN_HTML,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )
