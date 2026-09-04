import { useState, useEffect } from 'react'
import { api } from '../api'

export default function Positions() {
  const [positions, setPositions] = useState<any[]>([])
  const [loading, setLoading] = useState(true)

  const load = async () => {
    setLoading(true)
    try {
      const data = await api('/admin/positions')
      setPositions(Array.isArray(data) ? data : [])
    } catch { setPositions([]) }
    setLoading(false)
  }

  useEffect(() => { load() }, [])
  useEffect(() => { const id = setInterval(load, 10000); return () => clearInterval(id) }, [])

  const fmtPnl = (v: any) => {
    const n = parseFloat(v)
    return <span style={{color: n >= 0 ? 'var(--green)' : 'var(--red)', fontWeight:600}}>
      {n != null ? n.toFixed(4) : '—'}
    </span>
  }
  const age = (v: any) => {
    if (!v) return '—'
    const seconds = Math.max(0, Math.floor((Date.now() - new Date(v).getTime()) / 1000))
    if (seconds < 60) return `${seconds}s`
    const minutes = Math.floor(seconds / 60)
    if (minutes < 60) return `${minutes}m`
    const hours = Math.floor(minutes / 60)
    if (hours < 24) return `${hours}h ${minutes % 60}m`
    return `${Math.floor(hours / 24)}d ${hours % 24}h`
  }

  return (
    <div>
      <h2 className="page-title">Open Positions</h2>
      <div className="toolbar">
        <button onClick={load}>Refresh</button>
        <span className="muted" style={{marginLeft:'auto'}}>{positions.length} open positions (auto-refresh 10s)</span>
      </div>
      {loading ? <p className="muted">Loading...</p> : (
        <table>
          <thead>
            <tr><th>Symbol</th><th>Side</th><th>Quantity</th><th>Entry</th><th>Mark</th><th>Unrealized PnL</th><th>Leverage</th><th>Open for</th></tr>
          </thead>
          <tbody>
            {positions.map((p, i) => (
              <tr key={i}>
                <td><span className="badge blue">{p.symbol}</span></td>
                <td><span className={`badge ${p.side === 'LONG' || p.side === 'BUY' ? 'green' : 'red'}`}>{p.side}</span></td>
                <td>{p.quantity}</td>
                <td>{p.entry_price}</td>
                <td>{p.mark_price || '—'}</td>
                <td>{fmtPnl(p.unrealized_pnl)}</td>
                <td>{p.leverage ? `${p.leverage}x` : '—'}</td>
                <td className="muted" title={p.opened_at ? new Date(p.opened_at).toLocaleString() : ''}>{age(p.opened_at)}</td>
              </tr>
            ))}
            {positions.length === 0 && <tr><td colSpan={8} className="empty">No open positions</td></tr>}
          </tbody>
        </table>
      )}
    </div>
  )
}
