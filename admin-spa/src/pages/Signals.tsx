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
  const [selected, setSelected] = useState<any | null>(null)
  const [now, setNow] = useState(Date.now())

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
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(id)
  }, [])

  const filtered = signals.filter(s => {
    if (symbol && !s.symbol?.includes(symbol)) return false
    if (status && s.signal_status !== status && s.status !== status) return false
    return true
  }).slice(0, limit)

  const fmtRelative = (v: any) => {
    if (!v) return '—'
    const seconds = Math.max(0, Math.floor((now - new Date(v).getTime()) / 1000))
    if (seconds < 10) return 'just now'
    if (seconds < 60) return `${seconds} sec ago`
    const minutes = Math.floor(seconds / 60)
    if (minutes < 60) return `${minutes} min ago`
    const hours = Math.floor(minutes / 60)
    if (hours < 24) return `${hours} hour${hours === 1 ? '' : 's'} ago`
    const days = Math.floor(hours / 24)
    if (days < 7) return `${days} day${days === 1 ? '' : 's'} ago`
    return `${Math.floor(days / 7)} week${Math.floor(days / 7) === 1 ? '' : 's'} ago`
  }
  const fmtAbsolute = (v: any) => v ? new Date(v).toLocaleString() : ''
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
      return `${Math.round(parseFloat(s.confidence) * 100)}%`
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
            <tr><th>Symbol</th><th>Strategy</th><th>Side</th><th>Entry</th><th>TP</th><th>SL</th><th>Signal Status</th><th>Trade Status</th><th>Confidence</th><th>Created</th></tr>
          </thead>
          <tbody>
            {filtered.map(s => (
             <tr key={s.signal_id || s.id || `${s.symbol}-${s.created_at || s.timestamp}`}
                 onClick={async () => {
                   const id = s.signal_id || s.id
                   if (id) setSelected(await api(`/admin/signals/${id}`))
                 }}
                 style={{cursor:'pointer'}}>
                <td><span className="badge blue">{s.symbol || '—'}</span></td>
                <td>{s.strategy_name || s.strategy || '—'}</td>
                <td>{s.side ? SIDE_BADGE(s.side) : '—'}</td>
                <td>{fmtPrice(s.entry_price ?? s.entry)}</td>
                <td>{fmtPrice(s.tp1 ?? s.take_profit)}</td>
                <td>{fmtPrice(s.stop_loss)}</td>
                <td>{STATUS_BADGE(String(s.signal_status || s.status || '').toLowerCase())}</td>
                <td>{STATUS_BADGE(String(s.trading_status || '').toLowerCase())}</td>
                <td className="mono">{fmtConfidence(s)}</td>
                <td className="muted" title={fmtAbsolute(s.created_at || s.timestamp)}>{fmtRelative(s.created_at || s.timestamp)}</td>
              </tr>
            ))}
            {filtered.length === 0 && <tr><td colSpan={10} className="empty">No signals yet. Signals generated by active strategies will appear here.</td></tr>}
          </tbody>
        </table>
      )}
      {selected && <div className="drawer-backdrop" onClick={() => setSelected(null)}>
        <aside className="drawer" onClick={e => e.stopPropagation()}>
          <button className="drawer-close" onClick={() => setSelected(null)}>Close</button>
          <h2>{selected.symbol} {selected.side === 'BUY' ? 'LONG' : 'SHORT'}</h2>
          <p className="muted">{selected.strategy_name || selected.strategy || '—'} · {selected.timeframe || '—'}</p>
          <h3>Signal Data</h3>
          <p>Status: {selected.signal_status || selected.status || '—'}</p>
          <p>Entry: {fmtPrice(selected.entry_price ?? selected.entry)}</p>
          <p>Take Profit: {fmtPrice(selected.tp1 ?? selected.take_profit)}</p>
          <p>Stop Loss: {fmtPrice(selected.stop_loss)}</p>
          <p>Confidence: {fmtConfidence(selected)}</p>
          <p>Mode: {selected.mode || '—'}</p>
          <p>Created: {fmtAbsolute(selected.created_at || selected.timestamp)}</p>
          <p>Candle close: {fmtAbsolute(selected.candle_close_time)}</p>
          <h3>Publish Status</h3>
          <p>Telegram: {selected.telegram_status || '—'}</p>
          <h3>Conditions / Indicators</h3>
          <pre>{selected.reasons || selected.reason || '—'}</pre>
          <pre>{selected.indicators || '—'}</pre>
          <h3>Telegram Post</h3>
          <pre>{selected.telegram_preview || '—'}</pre>
          {selected.trade && <><h3>Execution</h3><pre>{JSON.stringify(selected.trade, null, 2)}</pre></>}
        </aside>
      </div>}
    </div>
  )
}
