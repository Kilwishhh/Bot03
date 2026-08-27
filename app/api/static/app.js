// Shared client-side helpers for MK Trader web pages.
// Loaded as a plain script; exposes window.mk.

(function () {
  "use strict";

  const api = {
    async get(path) {
      const res = await fetch(path, { credentials: "omit" });
      if (!res.ok) throw new Error(`GET ${path} → ${res.status}`);
      return res.json();
    },
    async post(path, body) {
      const token = localStorage.getItem("admin_api_token");
      const headers = { "Content-Type": "application/json" };
      if (token) headers.Authorization = `Bearer ${token}`;
      const res = await fetch(path, {
        method: "POST",
        headers,
        body: body ? JSON.stringify(body) : null,
      });
      const text = await res.text();
      let payload = {};
      try { payload = text ? JSON.parse(text) : {}; } catch (_) { payload = { detail: text }; }
      if (!res.ok) throw new Error(payload.detail || `POST ${path} → ${res.status}`);
      return payload;
    },
  };

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
  }

  function badge(side) {
    if (typeof side !== "string") return `<span class="badge">${escapeHtml(side)}</span>`;
    const lower = side.toLowerCase();
    return `<span class="badge ${lower}">${escapeHtml(side)}</span>`;
  }

  function confidenceBar(value) {
    const pct = Math.max(0, Math.min(1, Number(value) || 0));
    return `<span class="confidence-bar"><span style="width:${pct * 100}%"></span></span>${pct.toFixed(2)}`;
  }

  function relativeTime(iso) {
    if (!iso) return "";
    const t = new Date(iso).getTime();
    if (Number.isNaN(t)) return escapeHtml(iso);
    const diff = Date.now() - t;
    if (diff < 60_000) return `${Math.floor(diff / 1000)}s ago`;
    if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
    if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
    return new Date(t).toLocaleDateString();
  }

  function toast(message, kind = "info") {
    const el = document.createElement("div");
    el.className = `toast ${kind}`;
    el.textContent = message;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 3500);
  }

  function applyTheme(theme) {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("mk_theme", theme);
  }

  function initTheme() {
    const saved = localStorage.getItem("mk_theme") || "dark";
    applyTheme(saved);
  }

  function themeToggleButton() {
    const btn = document.createElement("button");
    btn.className = "theme-toggle";
    btn.title = "Toggle theme";
    btn.textContent = "◐";
    btn.addEventListener("click", () => {
      const next = (document.documentElement.dataset.theme === "light") ? "dark" : "light";
      applyTheme(next);
    });
    return btn;
  }

  // ---- Sparkline (pure SVG, no dependencies) ----
  function sparkline(values, opts = {}) {
    const width = opts.width || 80;
    const height = opts.height || 24;
    const stroke = opts.stroke || "var(--accent)";
    if (!values || values.length < 2) return `<svg class="spark" width="${width}" height="${height}"></svg>`;
    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = max - min || 1;
    const step = width / (values.length - 1);
    const points = values.map((v, i) => {
      const x = i * step;
      const y = height - ((v - min) / range) * height;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(" ");
    return `<svg class="spark" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">
      <polyline points="${points}" fill="none" stroke="${stroke}" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"/>
    </svg>`;
  }

  // ---- Candlestick/line chart (pure SVG) ----
  function priceChart(series, opts = {}) {
    const width = opts.width || 800;
    const height = opts.height || 240;
    const padX = 36;
    const padY = 20;
    if (!series || series.length < 2) {
      return `<svg width="100%" height="${height}" viewBox="0 0 ${width} ${height}"><text x="${width/2}" y="${height/2}" fill="var(--text-muted)" text-anchor="middle">No data</text></svg>`;
    }
    const closes = series.map((p) => p.close);
    const min = Math.min(...closes);
    const max = Math.max(...closes);
    const range = max - min || 1;
    const stepX = (width - padX * 2) / (series.length - 1);
    const points = closes.map((v, i) => {
      const x = padX + i * stepX;
      const y = height - padY - ((v - min) / range) * (height - padY * 2);
      return [x, y];
    });
    const path = points.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
    // grid lines (4 horizontal)
    const gridY = [];
    for (let i = 0; i <= 4; i++) {
      const y = padY + (i / 4) * (height - padY * 2);
      const v = max - (i / 4) * range;
      gridY.push(`<line x1="${padX}" x2="${width - padX}" y1="${y}" y2="${y}" stroke="var(--border)" stroke-dasharray="2 4"/>`);
      gridY.push(`<text x="${width - padX + 6}" y="${y + 4}" fill="var(--text-muted)" font-size="10">${v.toFixed(2)}</text>`);
    }
    // area fill
    const areaPath = `${path} L${points[points.length - 1][0].toFixed(1)},${(height - padY).toFixed(1)} L${points[0][0].toFixed(1)},${(height - padY).toFixed(1)} Z`;
    return `<svg viewBox="0 0 ${width} ${height}" width="100%" height="${height}" preserveAspectRatio="none">
      ${gridY.join("")}
      <path d="${areaPath}" fill="url(#areaGrad)" opacity="0.3"/>
      <defs>
        <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="var(--accent)" stop-opacity="0.6"/>
          <stop offset="100%" stop-color="var(--accent)" stop-opacity="0"/>
        </linearGradient>
      </defs>
      <path d="${path}" fill="none" stroke="var(--accent)" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>
    </svg>`;
  }

  // ---- Row rendering helper ----
  function renderRows(id, rows, columns) {
    const target = document.querySelector(`#${id}`);
    if (!target) return;
    if (!rows || !rows.length) {
      target.innerHTML = `<tr><td class="empty" colspan="${columns.length}">No records yet</td></tr>`;
      return;
    }
    target.innerHTML = rows.map((row) =>
      `<tr>${columns.map((c) => `<td>${escapeHtml(row[c])}</td>`).join("")}</tr>`
    ).join("");
  }

  // ---- Tabs ----
  function initTabs(containerSelector = ".tabs") {
    document.querySelectorAll(`${containerSelector} .tab`).forEach((tab) => {
      tab.addEventListener("click", () => {
        const group = tab.closest(".tabs") || document;
        group.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
        group.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
        tab.classList.add("active");
        const view = document.querySelector(`#${tab.dataset.view}View`);
        if (view) view.classList.add("active");
      });
    });
  }

  window.mk = {
    api,
    escapeHtml,
    badge,
    confidenceBar,
    relativeTime,
    toast,
    initTheme,
    themeToggleButton,
    sparkline,
    priceChart,
    renderRows,
    initTabs,
  };
})();
