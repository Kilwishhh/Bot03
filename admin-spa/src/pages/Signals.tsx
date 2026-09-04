import { useState, useEffect } from 'react'
import { api } from '../api'

const SIDE_BADGE = (s: string) => {
  const map: Record<string,string> = { LONG: 'green', SHORT: 'red', BUY: 'green', SELL: 'red' }
  return <span className={`badge ${map[s] || 'gray'}`}>{s}</span>
}

const STATUS_BADGE = (s: string) => {
  const map: Record<string,string> = {
    active: 'green', pending: 'yellow', filled: 'blue', cancelled: 'gray',
    executed: 'blue', closed: 'green', expired: 'gray', tp_hit: 'green', sl_hit: 'red'
  }
  return <span className={`badge ${map[s] || 'gray'}`}>{s}</span>
}

export default function Signals() {
  const [signals, setSignals] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [limit, setLimit] = useState(50)
  const [symbol, setSymbol] = useState('')
  const [status, setStatus] = useState('')

  const load = async () => {
    setLoading(true)
    try {
      const data = await api('/admin/signals', { query: { limit: 100 } })
      setSignals(Array.isArray(data) ? data : [])
    } catch { setSignals([]) }
    setLoading(false)
  }

  useEffect(() => { load() }, [])
  useEffect(() => {
    const id = setInterval(load, 15000)
    return () => clearInterval(id)
  }, [])

  const filtered = signals.filter(s => {
    if (symbol && !s.symbol?.includes(symbol)) return false
    if (status && s.signal_status !== status && s.status !== status) return false
    return true
  }).slice(0, limit)

  const fmt = (v: any) => v ? new Date(v).toLocaleString() : '—'
  const fmtPrice = (v: any) => v != null ? parseFloat(v).toFixed(6) : '—'

  // Confidence: display as N/M (hits/total). Fall back to legacy float only when
  // the new columns are absent (very old rows).
  const fmtConfidence = (s: any) => {
    const hits = s.confidence_hits
    const total = s.confidence_total
    if (hits != null && total != null && total > 0) {
      return `${hits}/${total}`
    }
    if (s.confidence != null) {
      // Legacy rows: 0.65 → "6.5/10" only as a degraded fallback.
      const pct = Math.round(parseFloat(s.confidence) * 100)
      return `${pct}/100`
    }
    return '—'
  }

  return (
    <div>
      <h2 className="page-title">Signals</h2>
      <div className="toolbar">
        <input placeholder="Symbol filter..." value={symbol} onChange={e => setSymbol(e.target.value)} />
        <select value={status} onChange={e => setStatus(e.target.value)}>
          <option value="">All statuses</option>
          <option value="active">Active</option>
          <option value="pending">Pending</option>
          <option value="filled">Filled</option>
          <option value="cancelled">Cancelled</option>
          <option value="expired">Expired</option>
        </select>
        <input type="number" style={{width:70}} value={limit} onChange={e => setLimit(parseInt(e.target.value)||20)} />
        <span className="muted">rows</span>
        <button onClick={load}>Refresh</button>
        <span className="muted" style={{marginLeft:'auto'}}>{filtered.length} signals (auto-refresh 15s)</span>
      </div>
      {loading ? <p className="muted">Loading...</p> : (
        <table>
          <thead>
            <tr><th>Symbol</th><th>Side</th><th>Entry</th><th>TP</th><th>SL</th><th>Signal Status</th><th>Trade Status</th><th>Confidence</th><th>Created</th></tr>
          </thead>
          <tbody>
            {filtered.map(s => (
             <tr key={s.signal_id || s.id || `${s.symbol}-${s.created_at || s.timestamp}`}>
                <td><span className="badge blue">{s.symbol || '—'}</span></td>
                <td>{s.side ? SIDE_BADGE(s.side) : '—'}</td>
                <td>{fmtPrice(s.entry_price)}</td>
                <td>{fmtPrice(s.tp1 || s.tp)}</td>
                <td>{fmtPrice(s.stop_loss)}</td>
                <td>{STATUS_BADGE(String(s.signal_status || s.status || '').toLowerCase())}</td>
                <td>{STATUS_BADGE(String(s.trading_status || '').toLowerCase())}</td>
                <td className="mono">{fmtConfidence(s)}</td>
                <td className="muted">{fmt(s.created_at)}</td>
              </tr>
            ))}
            {filtered.length === 0 && <tr><td colSpan={9} className="empty">No signals</td></tr>}
          </tbody>
        </table>
      )}
    </div>
  )
}
