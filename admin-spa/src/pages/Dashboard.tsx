import { useState, useEffect } from 'react'
import { api } from '../api'

export default function Dashboard() {
  const [ctrl, setCtrl] = useState<any>(null)
  const [stats, setStats] = useState<any>(null)
  const [ctrlAction, setCtrlAction] = useState('')

  const load = async () => {
    try {
      const [c, s] = await Promise.all([
        api('/admin/control'),
        api('/admin/stats'),
      ])
      setCtrl(c)
      setStats(s)
    } catch {}
  }

  useEffect(() => { load() }, [])

  const doCtrl = async (action: string) => {
    setCtrlAction(action)
    try {
      await api(`/admin/control/${action}`, { method: 'POST' })
      await load()
    } finally {
      setCtrlAction('')
    }
  }

  return (
    <div>
      <h2 className="page-title">Dashboard</h2>

      <div className="control-status">
        <span className="state">
          <span className={`badge ${ctrl?.bot_running ? 'green' : 'gray'}`}>
            {ctrl?.bot_running ? 'Running' : 'Stopped'}
          </span>
          {' '}
          <span className={`badge ${ctrl?.paused ? 'yellow' : 'green'}`}>
            {ctrl?.paused ? 'Paused' : 'Active'}
          </span>
        </span>
        <button className="success" onClick={() => doCtrl('resume')} disabled={!!ctrlAction}>Resume</button>
        <button className="warn" onClick={() => doCtrl('pause')} disabled={!!ctrlAction}>Pause</button>
        <button className="danger" onClick={() => doCtrl('stop')} disabled={!!ctrlAction}>Stop</button>
      </div>

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
              <div className="value" style={{color: (stats.daily_pnl ?? 0) >= 0 ? 'var(--green)' : 'var(--red)'}}>
                ${(stats.daily_pnl ?? 0).toFixed(4)}
              </div>
            </div>
            <div className="card">
              <h3>Total PnL</h3>
              <div className="value" style={{color: (stats.total_pnl ?? 0) >= 0 ? 'var(--green)' : 'var(--red)'}}>
                ${(stats.total_pnl ?? 0).toFixed(4)}
              </div>
            </div>
          </>
        ) : (
          <p className="muted">Loading stats...</p>
        )}
      </div>
    </div>
  )
}
