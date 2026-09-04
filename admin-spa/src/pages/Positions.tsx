import { useState, useEffect } from 'react'
import { api } from '../api'
import { absoluteTime, relativeTime, useCurrentTime } from '../utils/time'

export default function Positions() {
  const [positions, setPositions] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState('')
  const [partial, setPartial] = useState<any | null>(null)
  const [partialValue, setPartialValue] = useState('')
  const [brackets, setBrackets] = useState<any | null>(null)
  const now = useCurrentTime()

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

  const action = async (path: string, body?: any) => {
    setBusy(path)
    try { await api(path, { method: 'POST', body }); await load() }
    catch (e: any) { alert(e.detail || 'Position action failed') }
    finally { setBusy('') }
  }

  const fmtPnl = (v: any) => {
    const n = parseFloat(v)
    return <span style={{color: n >= 0 ? 'var(--green)' : 'var(--red)', fontWeight:600}}>
      {n != null ? n.toFixed(4) : '—'}
    </span>
  }

  return (
    <div>
      <h2 className="page-title">Open Positions</h2>
      <div className="toolbar">
        <button onClick={load}>Refresh</button>
        {positions.length > 0 && <button className="danger" onClick={() => confirm('Close every open position?') && action('/admin/positions/close-all')}>Close All</button>}
        <span className="muted" style={{marginLeft:'auto'}}>{positions.length} open positions (auto-refresh 10s)</span>
      </div>
      {loading ? <p className="muted">Loading...</p> : (
        <table>
          <thead>
            <tr><th>Symbol</th><th>Side</th><th>Size</th><th>Entry</th><th>Current</th><th>Unrealized PnL</th><th>TP / SL</th><th>Open for</th><th>Manage</th></tr>
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
                <td className="muted">{p.tp_status || '—'} / {p.sl_status || '—'}</td>
                <td>{p.leverage ? `${p.leverage}x` : '—'}</td>
                <td className="muted" title={absoluteTime(p.opened_at)}>{relativeTime(p.opened_at, now)}</td>
                <td style={{display:'flex', gap:4}}>
                  <button className="danger" disabled={!!busy} onClick={() => confirm(`Close ${p.symbol}?`) && action(`/admin/positions/${p.symbol}/close`)}>Close</button>
                  <button disabled={!!busy} onClick={() => { setPartial(p); setPartialValue('') }}>Partial</button>
                  <button disabled={!!busy} onClick={() => setBrackets(p)}>TP/SL</button>
                </td>
              </tr>
            ))}
            {positions.length === 0 && <tr><td colSpan={9} className="empty">No open positions</td></tr>}
          </tbody>
        </table>
      )}
      {partial && <div className="drawer-backdrop" onClick={() => setPartial(null)}><aside className="drawer" onClick={e => e.stopPropagation()}>
        <button className="drawer-close" onClick={() => setPartial(null)}>Close</button>
        <h2>Book Profit — {partial.symbol}</h2>
        <p>Remaining size: <strong>{partial.quantity}</strong></p>
        <label>Quantity or percent</label>
        <input value={partialValue} onChange={e => setPartialValue(e.target.value)} placeholder="e.g. 0.01 or 25%" />
        <button className="success" onClick={() => {
          const isPercent = partialValue.trim().endsWith('%')
          const value = parseFloat(partialValue)
          if (!value || value <= 0) return
          action(`/admin/positions/${partial.symbol}/partial-close`, isPercent ? { percent: value } : { quantity: value })
          setPartial(null)
        }}>Close Partial</button>
      </aside></div>}
      {brackets && <BracketEditor position={brackets} onClose={() => setBrackets(null)} onSave={async body => { await action(`/admin/positions/${brackets.symbol}/brackets`, body); setBrackets(null) }} />}
    </div>
  )
}

function BracketEditor({ position, onClose, onSave }: { position: any; onClose: () => void; onSave: (body: any) => Promise<void> }) {
  const [levels, setLevels] = useState([1, 2, 3].map(i => ({ enabled: i === 1, percent: i === 1 ? 50 : i === 2 ? 30 : 20, price: '' })))
  const [sl, setSl] = useState('')
  return <div className="drawer-backdrop" onClick={onClose}><aside className="drawer" onClick={e => e.stopPropagation()}>
    <button className="drawer-close" onClick={onClose}>Close</button>
    <h2>TP / SL — {position.symbol}</h2>
    <p className="muted">Each TP closes its allocation. SL protects the remaining position.</p>
    {levels.map((level, i) => <div key={i} style={{display:'grid', gridTemplateColumns:'auto 1fr 1fr', gap:6, marginBottom:8}}>
      <label><input type="checkbox" checked={level.enabled} onChange={e => setLevels(levels.map((x,j) => j === i ? {...x, enabled:e.target.checked} : x))} /> TP{i + 1}</label>
      <input type="number" min={0} max={100} value={level.percent} onChange={e => setLevels(levels.map((x,j) => j === i ? {...x, percent:parseFloat(e.target.value) || 0} : x))} placeholder="% size" />
      <input value={level.price} onChange={e => setLevels(levels.map((x,j) => j === i ? {...x, price:e.target.value} : x))} placeholder="trigger price" />
    </div>)}
    <label>Stop-loss trigger price</label><input value={sl} onChange={e => setSl(e.target.value)} placeholder="e.g. 65000" />
    <button className="success" onClick={() => onSave({ take_profits: levels, stop_loss: sl ? { price: sl } : null })}>Save TP / SL</button>
  </aside></div>
}
