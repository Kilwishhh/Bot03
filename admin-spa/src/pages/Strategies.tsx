import { useState, useEffect } from 'react'
import { api } from '../api'

export default function Strategies() {
  const [strats, setStrats] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [ctrl, setCtrl] = useState<any>(null)
  const [ctrlAction, setCtrlAction] = useState('')
  const [search, setSearch] = useState('')

  const load = async () => {
    setLoading(true)
    try {
      const [s, c] = await Promise.all([
        api('/admin/strategies'),
        api('/admin/control'),
      ])
      setStrats(Array.isArray(s) ? s : [])
      setCtrl(c)
    } catch { setStrats([]) }
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  const doCtrl = async (action: string) => {
    setCtrlAction(action)
    try { await api(`/admin/control/${action}`, { method: 'POST' }); await load() }
    finally { setCtrlAction('') }
  }

  const filtered = strats.filter(s =>
    !search || s.name?.includes(search) || s.market?.includes(search)
  )

  const fmt = (v: string) => v ? new Date(v).toLocaleString() : '—'

  return (
    <div>
      <h2 className="page-title">Strategies</h2>

      <div className="toolbar">
        <input placeholder="Search name or symbol..." value={search} onChange={e => setSearch(e.target.value)} />
        <button onClick={load}>Refresh</button>
        <div style={{marginLeft:'auto', display:'flex', gap:8}}>
          <span className="muted">Bot: </span>
          <span className={`badge ${ctrl?.bot_running ? 'green' : 'gray'}`}>{ctrl?.bot_running ? 'Running' : 'Stopped'}</span>
          <button className="success" onClick={() => doCtrl('resume')} disabled={!!ctrlAction}>Resume</button>
          <button className="warn" onClick={() => doCtrl('pause')} disabled={!!ctrlAction}>Pause</button>
          <button className="danger" onClick={() => doCtrl('stop')} disabled={!!ctrlAction}>Stop</button>
        </div>
      </div>

      {loading ? <p className="muted">Loading...</p> : (
        <table>
          <thead>
            <tr><th>Name</th><th>ID</th><th>Market</th><th>Mode</th><th>Lifecycle</th><th>Updated</th></tr>
          </thead>
          <tbody>
            {filtered.map(s => (
              <tr key={s.id}>
                <td>{s.name}</td>
                <td className="muted" style={{maxWidth:120, overflow:'hidden', textOverflow:'ellipsis'}}>{s.id}</td>
                <td><span className="badge blue">{s.market || '—'}</span></td>
                <td><span className="badge purple">{s.execution_mode || s.lifecycle_state}</span></td>
                <td><span className="badge gray">{s.lifecycle_state}</span></td>
                <td className="muted">{fmt(s.updated_at)}</td>
              </tr>
            ))}
            {filtered.length === 0 && <tr><td colSpan={6} className="empty">No strategies</td></tr>}
          </tbody>
        </table>
      )}
    </div>
  )
}
