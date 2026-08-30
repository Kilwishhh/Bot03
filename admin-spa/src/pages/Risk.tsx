import { useState, useEffect } from 'react'
import { api } from '../api'

export default function Risk() {
  const [risk, setRisk] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [action, setAction] = useState('')

  const load = async () => {
    setLoading(true)
    try { setRisk(await api('/admin/risk')) }
    catch { setRisk(null) }
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  const doAction = async (a: string) => {
    setAction(a)
    try { await api(`/admin/risk/${a}`, { method: 'POST' }); await load() }
    catch {}
    setAction('')
  }

  const fmt = (v: any) => {
    if (v == null) return '—'
    const n = parseFloat(v)
    return n.toFixed ? n.toFixed(4) : v
  }

  return (
    <div>
      <h2 className="page-title">Risk Monitor</h2>
      <div className="toolbar">
        <button onClick={load} disabled={!!action}>Refresh</button>
        <button className="danger" onClick={() => doAction('reset-daily-loss')} disabled={!!action}>
          Reset Daily Loss
        </button>
        <button className="danger" onClick={() => doAction('reset-drawdown')} disabled={!!action}>
          Reset Drawdown
        </button>
      </div>
      {loading ? <p className="muted">Loading...</p> : !risk ? <p className="muted">No risk data</p> : (
        <div className="row">
          {[
            ['Daily PnL', risk.daily_pnl, risk.daily_pnl >= 0 ? 'green' : 'red'],
            ['Daily Loss Limit', risk.daily_loss_limit, 'gray'],
            ['Max Drawdown %', risk.max_drawdown_pct, parseFloat(risk.max_drawdown_pct) > 20 ? 'red' : 'gray'],
            ['Open Positions', risk.open_positions, 'gray'],
            ['Max Positions', risk.max_positions, 'gray'],
            ['Circuit Breaker', risk.circuit_breaker_triggered ? 'red' : 'green', ''],
            ['Total PnL', risk.total_pnl, parseFloat(risk.total_pnl) >= 0 ? 'green' : 'red'],
            ['Total Trades', risk.total_trades, 'gray'],
          ].map(([label, value, color]) => (
            <div key={String(label)} className="col card">
              <h3>{String(label)}</h3>
              <div className="value" style={{color: color ? `var(--${color})` : undefined}}>
                {String(value ?? '—')}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
