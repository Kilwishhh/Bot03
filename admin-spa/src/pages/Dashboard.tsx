import { useState, useEffect, useCallback, useRef } from 'react'
import { api } from '../api'

type BotState = 'stopped' | 'running' | 'paused'

function stateLabel(s: BotState) { return s.toUpperCase() }
function stateClass(s: BotState) {
  if (s === 'running') return 'green'
  if (s === 'paused') return 'yellow'
  return 'gray'
}

export default function Dashboard() {
  const [ctrl, setCtrl] = useState<any>(null)
  const [stats, setStats] = useState<any>(null)
  const [ctrlAction, setCtrlAction] = useState('')
  const [refreshLoading, setRefreshLoading] = useState(false)
  const [resetLoading, setResetLoading] = useState(false)
  const [resetConfirm, setResetConfirm] = useState(false)
  const [resetMsg, setResetMsg] = useState<{ok?: string; err?: string} | null>(null)

  // Derive effective state from backend
  const state: BotState = (() => {
    if (!ctrl) return 'stopped'
    return (ctrl.state as BotState) || 'stopped'
  })()

  const load = useCallback(async () => {
    try {
      const [c, s] = await Promise.all([
        api<any>('/admin/control'),
        api<any>('/dev/stats'),
      ])
      setCtrl(c)
      setStats(s)
    } catch {}
  }, [])

  // Initial load
  useEffect(() => { load() }, [load])

  // Live refresh every 15s — pause when tab is hidden
  useEffect(() => {
    const onVisibility = () => {
      if (!document.hidden) load()
    }
    document.addEventListener('visibilitychange', onVisibility)
    const id = setInterval(load, 15000)
    return () => { clearInterval(id); document.removeEventListener('visibilitychange', onVisibility) }
  }, [load])

  const doCtrl = async (action: string) => {
    setCtrlAction(action)
    try {
      await api(`/admin/control/${action}`, { method: 'POST' })
      await load()
    } catch (e: any) {
      alert(`Action failed: ${e.detail || e.message || action}`)
    } finally {
      setCtrlAction('')
    }
  }

  const handleRefresh = async () => {
    setRefreshLoading(true)
    try { await load() } finally { setRefreshLoading(false) }
  }

  const handleResetPaper = async () => {
    if (!resetConfirm) { setResetConfirm(true); return }
    setResetLoading(true)
    setResetMsg(null)
    try {
      const r = await api<any>('/admin/reset/paper', { method: 'POST', query: { confirm: true } })
      setResetMsg({ ok: `Cleared: signals=${r.counts?.signals_deleted ?? 0} trades=${r.counts?.trades_deleted ?? 0}` })
      setResetConfirm(false)
      await load()
    } catch (e: any) {
      setResetMsg({ err: e.detail || e.message || 'Reset failed' })
    } finally {
      setResetLoading(false)
    }
  }

  const pnl = (v: number | undefined | null) =>
    v == null ? '—' : `$${v.toFixed(4)}`

  return (
    <div>
      <h2 className="page-title">Dashboard</h2>

      {/* ── Bot state & controls ── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
        <span style={{ fontWeight: 700, fontSize: 14 }}>STATUS:</span>
        <span className={`badge ${stateClass(state)}`}>{stateLabel(state)}</span>
      </div>

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 20 }}>
        {/* START — only when stopped */}
        <button
          className="success"
          disabled={ctrlAction !== '' || state !== 'stopped'}
          onClick={() => doCtrl('start')}
        >
          {ctrlAction === 'start' ? 'Starting…' : 'START BOT'}
        </button>

        {/* PAUSE — only when running */}
        <button
          className="warn"
          disabled={ctrlAction !== '' || state !== 'running'}
          onClick={() => doCtrl('pause')}
        >
          {ctrlAction === 'pause' ? 'Pausing…' : 'PAUSE'}
        </button>

        {/* RESUME — only when paused */}
        <button
          className="success"
          disabled={ctrlAction !== '' || state !== 'paused'}
          onClick={() => doCtrl('resume')}
        >
          {ctrlAction === 'resume' ? 'Resuming…' : 'RESUME'}
        </button>

        {/* STOP — only when running or paused */}
        <button
          className="danger"
          disabled={ctrlAction !== '' || state === 'stopped'}
          onClick={() => doCtrl('stop')}
        >
          {ctrlAction === 'stop' ? 'Stopping…' : 'STOP'}
        </button>

        {/* REFRESH */}
        <button
          disabled={refreshLoading || ctrlAction !== ''}
          onClick={handleRefresh}
          style={{ background: '#334', color: '#fff', border: '1px solid #445' }}
        >
          {refreshLoading ? 'Refreshing…' : 'REFRESH'}
        </button>
      </div>

      {/* ── Reset paper data ── */}
      <div style={{ border: '1px solid #444', borderRadius: 6, padding: 12, marginBottom: 20 }}>
        <div style={{ fontWeight: 600, marginBottom: 8, color: '#ccc' }}>Reset Paper Data</div>
        {!resetConfirm ? (
          <button
            className="danger"
            disabled={resetLoading || ctrlAction !== '' || state !== 'stopped'}
            onClick={() => setResetConfirm(true)}
          >
            RESET PAPER DATA
          </button>
        ) : (
          <div>
            <p style={{ color: '#fca', fontSize: 13, marginBottom: 8 }}>
              This will permanently remove all Paper-mode test data including paper trades,
              positions, signals, and related runtime records. Testnet and Live data will not be affected.
            </p>
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                className="danger"
                disabled={resetLoading}
                onClick={handleResetPaper}
              >
                {resetLoading ? 'Resetting…' : 'CONFIRM RESET'}
              </button>
              <button
                disabled={resetLoading}
                onClick={() => setResetConfirm(false)}
                style={{ background: '#333', color: '#fff', border: '1px solid #555', borderRadius: 4, padding: '4px 12px', cursor: 'pointer' }}
              >
                CANCEL
              </button>
            </div>
          </div>
        )}
        {resetMsg && (
          <p style={{ marginTop: 8, color: resetMsg.err ? '#f66' : '#6f6', fontSize: 13 }}>
            {resetMsg.err || resetMsg.ok}
          </p>
        )}
      </div>

      {/* ── Stats grid ── */}
      <div className="stat-grid">
        {stats ? (
          <>
            <div className="card">
              <h3>Strategies</h3>
              <div className="value">{stats.total_strategies ?? '—'}</div>
            </div>
            <div className="card">
              <h3>Signals</h3>
              <div className="value">{stats.total_signals ?? '—'}</div>
            </div>
            <div className="card">
              <h3>Open Positions</h3>
              <div className="value">{stats.open_positions ?? '—'}</div>
            </div>
            <div className="card">
              <h3>Closed Trades</h3>
              <div className="value">{stats.closed_trades ?? '—'}</div>
            </div>
            <div className="card">
              <h3>Daily PnL</h3>
              <div className="value" style={{ color: (stats.daily_pnl ?? 0) >= 0 ? 'var(--green)' : 'var(--red)' }}>
                {pnl(stats.daily_pnl)}
              </div>
            </div>
            <div className="card">
              <h3>Total PnL</h3>
              <div className="value" style={{ color: (stats.total_pnl ?? 0) >= 0 ? 'var(--green)' : 'var(--red)' }}>
                {pnl(stats.total_pnl)}
              </div>
            </div>
          </>
        ) : (
          <p className="muted">Loading stats…</p>
        )}
      </div>
    </div>
  )
}
