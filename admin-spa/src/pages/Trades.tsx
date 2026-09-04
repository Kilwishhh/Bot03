import { useState, useEffect } from 'react'
import { api } from '../api'
import { absoluteTime, relativeTime, useCurrentTime } from '../utils/time'

export default function Trades() {
  const [trades, setTrades] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [limit, setLimit] = useState(50)
  const [symbol, setSymbol] = useState('')
  const now = useCurrentTime()

  const load = async () => {
    setLoading(true)
    try {
      const data = await api('/admin/trades', { query: { limit: 100 } })
      setTrades(Array.isArray(data) ? data : [])
    } catch { setTrades([]) }
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  const filtered = trades.filter(t => !symbol || t.symbol?.includes(symbol)).slice(0, limit)

  const fmtPnl = (v: any) => {
    const n = parseFloat(v)
    return <span style={{color: n >= 0 ? 'var(--green)' : 'var(--red)'}}>
      {n != null ? n.toFixed(4) : '—'}
    </span>
  }

  return (
    <div>
      <h2 className="page-title">Trades</h2>
      <div className="toolbar">
        <input placeholder="Symbol filter..." value={symbol} onChange={e => setSymbol(e.target.value)} />
        <input type="number" style={{width:70}} value={limit} onChange={e => setLimit(parseInt(e.target.value)||20)} />
        <span className="muted">rows</span>
        <button onClick={load}>Refresh</button>
        <span className="muted" style={{marginLeft:'auto'}}>{filtered.length} trades</span>
      </div>
      {loading ? <p className="muted">Loading...</p> : (
        <table>
          <thead>
            <tr><th>Symbol</th><th>Side</th><th>Qty</th><th>Entry</th><th>Exit</th><th>PnL</th><th>Fees</th><th>Strategy</th><th>Entry Time</th><th>Exit Time</th></tr>
          </thead>
          <tbody>
            {filtered.map(t => (
              <tr key={t.trade_id}>
                <td><span className="badge blue">{t.symbol}</span></td>
                <td><span className={`badge ${t.side === 'BUY' || t.side === 'LONG' ? 'green' : 'red'}`}>{t.side}</span></td>
                <td>{t.quantity}</td>
                <td>{t.entry_price}</td>
                <td>{t.exit_price || '—'}</td>
                <td>{fmtPnl(t.realized_pnl)}</td>
                <td>{t.fees ?? '—'}</td>
                <td className="muted">{t.strategy || '—'}</td>
                <td className="muted" title={absoluteTime(t.entry_time)}>{relativeTime(t.entry_time, now)}</td>
                <td className="muted" title={absoluteTime(t.exit_time)}>{relativeTime(t.exit_time, now)}</td>
              </tr>
            ))}
            {filtered.length === 0 && <tr><td colSpan={10} className="empty">No trades</td></tr>}
          </tbody>
        </table>
      )}
    </div>
  )
}
