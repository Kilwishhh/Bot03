"""Admin SPA — single-file React-style admin UI.

Uses the same auth as the user UI but with admin role.
"""

import os
import json
import time
import secrets
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse

from app.api.dependencies import get_access_context
from app.core.rbac import AccessContext

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
      <a class="nav-item" data-route="integrations">⬡ Integrations</a>
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
    <div id="root">Loading…</div>
  </main>
</div>

<script>
/* Admin SPA — minimal vanilla JS, no build step. */

const token = localStorage.getItem('mk_token') || sessionStorage.getItem('mk_admin_token') || '';

// Auth headers: Bearer if we have a token, else fallback to X-Admin-Token
function headers() {
  if (token) return { 'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json' };
  const adminTok = sessionStorage.getItem('mk_admin_token') || '';
  if (adminTok) return { 'X-Admin-Token': adminTok, 'Content-Type': 'application/json' };
  return { 'Content-Type': 'application/json' };
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
    const tbody = h('tbody');
    for (const u of users) {
      tbody.appendChild(h('tr', {}, [
        h('td', {}, u.email),
        h('td', {}, u.display_name || ''),
        h('td', {}, [h('span', { class: 'badge ' + (u.role === 'admin' ? 'badge-red' : 'badge-blue') }, u.role)]),
        h('td', {}, [h('span', { class: 'badge ' + (u.status === 'active' ? 'badge-green' : 'badge-yellow') }, u.status)]),
        h('td', {}, new Date(u.created_at).toLocaleDateString()),
        h('td', {}, [
          u.status === 'active'
            ? h('button', { class: 'btn btn-ghost btn-sm', onClick: () => suspendUser(u.id) }, 'Suspend')
            : h('span', { class: 'badge badge-gray' }, 'suspended'),
        ]),
      ]));
    }
    return [
      h('div', { class: 'page-header' }, [h('h1', { class: 'page-title' }, 'Users')]),
      h('div', { class: 'card', style: 'padding:0' }, [h('table', {}, [h('thead', {}, h('tr', {}, [
        h('th', {}, 'Email'), h('th', {}, 'Name'), h('th', {}, 'Role'),
        h('th', {}, 'Status'), h('th', {}, 'Created'), h('th', {}, ''),
      ])), tbody])]),
    ];
  },

  audit: async () => {
    const rows = await api('GET', '/admin/audit?limit=100');
    return [
      h('div', { class: 'page-header' }, [h('h1', { class: 'page-title' }, 'Audit Log')]),
      h('div', { class: 'card', style: 'padding:0' }, [h('table', {}, [h('thead', {}, h('tr', {}, [
        h('th', {}, 'When'), h('th', {}, 'Actor'), h('th', {}, 'Role'),
        h('th', {}, 'Action'), h('th', {}, 'Target'), h('th', {}, 'Result'),
      ])), h('tbody', {}, rows.map(r => h('tr', {}, [
        h('td', { style: 'font-size:11px;color:var(--muted)' }, new Date(r.created_at).toLocaleString()),
        h('td', {}, r.actor_user_id || '—'),
        h('td', {}, [h('span', { class: 'badge badge-gray' }, r.actor_role)]),
        h('td', {}, r.action),
        h('td', { style: 'font-size:11px' }, r.target_id || r.target_type || '—'),
        h('td', {}, [h('span', { class: 'badge ' + (r.result === 'ok' ? 'badge-green' : 'badge-red') }, r.result || 'ok')]),
      ])))]))]),
    ];
  },

  strategies: async () => {
    const strategies = await api('GET', '/admin/strategies');
    return [
      h('div', { class: 'page-header' }, [
        h('h1', { class: 'page-title' }, 'All Strategies'),
        h('div', { class: 'page-sub' }, strategies.length + ' total across all users'),
      ]),
      h('div', { class: 'card', style: 'padding:0' }, [h('table', {}, [
        h('thead', {}, h('tr', {}, [
          h('th', {}, 'Name'), h('th', {}, 'User'),
          h('th', {}, 'Market'), h('th', {}, 'Mode'), h('th', {}, 'State'),
          h('th', {}, 'Updated'),
        ])),
        h('tbody', {}, strategies.map(s => h('tr', {}, [
          h('td', {}, h('strong', {}, s.name)),
          h('td', { style: 'font-size:11px;color:var(--muted)' }, (s.user_id || '').slice(0, 8)),
          h('td', {}, s.market),
          h('td', {}, s.execution_mode),
          h('td', {}, [h('span', { class: 'badge ' + stateClass(s.lifecycle_state) }, s.lifecycle_state)]),
          h('td', { style: 'font-size:11px;color:var(--muted)' }, new Date(s.updated_at).toLocaleString()),
        ]))),
      ])]),
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
    return [
      h('div', { class: 'page-header' }, [h('h1', { class: 'page-title' }, 'All Signals')]),
      h('div', { class: 'card', style: 'padding:0' }, [h('table', {}, [
        h('thead', {}, h('tr', {}, [
          h('th', {}, 'Symbol'), h('th', {}, 'Side'),
          h('th', {}, 'Confidence'), h('th', {}, 'Strategy'), h('th', {}, 'When'),
        ])),
        h('tbody', {}, signals.map(s => h('tr', {}, [
          h('td', {}, h('strong', {}, s.symbol)),
          h('td', {}, [h('span', { class: 'badge ' + (s.side === 'BUY' ? 'badge-green' : s.side === 'SELL' ? 'badge-red' : 'badge-gray') }, s.side)]),
          h('td', {}, (s.confidence * 100).toFixed(0) + '%'),
          h('td', {}, s.strategy_name),
          h('td', { style: 'font-size:11px;color:var(--muted)' }, new Date(s.created_at).toLocaleString()),
        ]))),
      ])]),
    ];
  },

  integrations: async () => {
    return [
      h('div', { class: 'page-header' }, [h('h1', { class: 'page-title' }, 'Integrations')]),
      h('div', { class: 'card' }, [
        h('div', { class: 'card-title' }, 'Binance Square'),
        h('div', { style: 'color:var(--muted);font-size:12px' }, 'POST /admin/square/enqueue, /flush, /status, /toggle — auto-dedup, 3 posts/day limit'),
      ]),
      h('div', { class: 'card' }, [
        h('div', { class: 'card-title' }, 'Telegram'),
        h('div', { style: 'color:var(--muted);font-size:12px' }, 'POST /admin/telegram/send — channel poster'),
      ]),
      h('div', { class: 'card' }, [
        h('div', { class: 'card-title' }, 'DEX (disabled)'),
        h('div', { style: 'color:var(--muted);font-size:12px' }, 'POST /admin/dex/preview, /approve, /place — Phase 6 scaffold only'),
      ]),
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
          : h('table', {}, [
              h('thead', {}, h('tr', {}, [
                h('th', {}, 'Scope'), h('th', {}, 'Target'),
                h('th', {}, 'Reason'), h('th', {}, 'When'), h('th', {}, ''),
              ])),
              h('tbody', {}, pauses.map(p => h('tr', {}, [
                h('td', {}, [h('span', { class: 'badge badge-red' }, p.scope)]),
                h('td', { style: 'font-size:11px' }, p.scope_target || '—'),
                h('td', { style: 'font-size:12px' }, p.reason || '—'),
                h('td', { style: 'font-size:11px;color:var(--muted)' }, new Date(p.created_at).toLocaleString()),
                h('td', {}, h('button', { class: 'btn btn-success btn-sm', onClick: () => resumePause(p.id) }, 'Resume')),
              ]))),
            ]),
      ]),
    ];
  },

  settings: async () => {
    return [
      h('div', { class: 'page-header' }, [h('h1', { class: 'page-title' }, 'System Settings')]),
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

// Init
(async () => {
  if (!token && !sessionStorage.getItem('mk_admin_token')) {
    location.href = '/admin/login';
    return;
  }
  if (await loadMe()) navigate('overview');
})();
</script>
</body>
</html>"""


@router.get("/admin/login", include_in_schema=False)
def admin_login():
    """Admin login page — sets sessionStorage token then redirects."""
    return HTMLResponse("""<!doctype html>
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
    location.href = '/admin/dashboard';
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
    location.href = '/admin/dashboard';
  } catch (e) { showError(e.message); }
});
</script>
</body></html>""")


@router.get("/admin/dashboard", include_in_schema=False)
def admin_dashboard():
    return HTMLResponse(ADMIN_HTML)


@router.get("/admin/old", include_in_schema=False)
def admin_legacy():
    """Keep the old admin.html for backward compat."""
    return FileResponse(Path(__file__).with_name("admin.html"))
