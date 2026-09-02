import { useState, useEffect, useRef } from 'react'
import { api } from '../api'

const LEVEL_COLORS: Record<string, string> = {
  DEBUG: 'gray',
  INFO: 'blue',
  WARNING: 'warn',
  ERROR: 'danger',
  CRITICAL: 'danger',
}

export default function Logs() {
  const [logs, setLogs] = useState<any[]>([])
  const [filter, setFilter] = useState('')
  const [auto, setAuto] = useState(true)
  const [error, setError] = useState('')
  const sinceRef = useRef<string | null>(null)
  const boxRef = useRef<HTMLDivElement>(null)

  const load = async () => {
    try {
      const data = await api<any[]>('/admin/logs', { query: { limit: 200, since: sinceRef.current ?? undefined } })
      sinceRef.current = data.length ? data[data.length - 1].ts : sinceRef.current
      setLogs(prev => [...prev, ...data].slice(-500))
      if (data.length) setError('')
    } catch (e: any) { setError(e.detail || 'failed to load') }
  }

  useEffect(() => {
    load()
    if (!auto) return
    const onVisibility = () => { if (!document.hidden) load() }
    document.addEventListener('visibilitychange', onVisibility)
    const id = setInterval(load, 15000)
    return () => { clearInterval(id); document.removeEventListener('visibilitychange', onVisibility) }
  }, [auto])

  useEffect(() => {
    if (boxRef.current && auto) {
      boxRef.current.scrollTop = boxRef.current.scrollHeight
    }
  }, [logs, auto])

  const filtered = filter
    ? logs.filter(l => l.logger.includes(filter) || l.msg.includes(filter) || l.level.includes(filter.toUpperCase()))
    : logs

  return (
    <div>
      <h2 className="page-title">Live Logs</h2>
      <div className="toolbar">
        <input placeholder="Filter (logger / message / level)..." value={filter} onChange={e => setFilter(e.target.value)} />
        <button onClick={() => { sinceRef.current = null; setLogs([]); load() }}>Clear</button>
        <button onClick={load}>Reload</button>
        <label style={{marginLeft:16, display:'flex', alignItems:'center', gap:6}}>
          <input type="checkbox" checked={auto} onChange={e => setAuto(e.target.checked)} />
          Auto-tail
        </label>
        <span className="muted" style={{marginLeft:'auto'}}>{filtered.length} lines</span>
      </div>
      {error && <div className="error">{error}</div>}
      <div ref={boxRef} className="log-box">
        {filtered.map((l, i) => (
          <div key={i} className="log-line">
            <span className="log-ts">{l.ts.split('T')[1]?.slice(0, 12) || l.ts}</span>
            <span className={`badge ${LEVEL_COLORS[l.level] || 'gray'}`} style={{minWidth:60, display:'inline-block', textAlign:'center'}}>{l.level}</span>
            <span className="log-logger">{l.logger}</span>
            <span className="log-msg">{l.msg}</span>
          </div>
        ))}
        {filtered.length === 0 && !error && <div className="muted" style={{padding:16}}>No log lines yet</div>}
      </div>
    </div>
  )
}