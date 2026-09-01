import { useState, useEffect } from 'react'
import { api } from '../api'

export default function Strategies() {
  const [strats, setStrats] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [ctrl, setCtrl] = useState<any>(null)
  const [ctrlAction, setCtrlAction] = useState('')
  const [search, setSearch] = useState('')
  const [edit, setEdit] = useState<any>(null)
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')

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

  const doTransition = async (id: string, target: string) => {
    setBusy(true); setMsg('')
    try {
      await api(`/admin/strategies/${id}/transition`, { method: 'POST', body: { target_state: target } })
      setMsg(`transitioned ${id.slice(0,8)}… → ${target}`)
      await load()
    } catch (e: any) { setMsg(`error: ${e.detail}`) }
    finally { setBusy(false) }
  }

  const doPatch = async (id: string, body: any) => {
    setBusy(true); setMsg('')
    try {
      await api(`/admin/strategies/${id}`, { method: 'PATCH', body })
      setMsg(`updated ${id.slice(0,8)}…`)
      await load(); setEdit(null)
    } catch (e: any) { setMsg(`error: ${e.detail}`) }
    finally { setBusy(false) }
  }

  const filtered = strats.filter(s =>
    !search || s.name?.includes(search) || s.market?.includes(search)
  )

  const fmt = (v: string) => v ? new Date(v).toLocaleString() : '—'
  const stateColor = (st: string) => st === 'paper' || st === 'live' ? 'green' : 'gray'

  return (
    <div>
      <h2 className="page-title">Strategies</h2>

      <div className="toolbar">
        <input placeholder="Search name or symbol..." value={search} onChange={e => setSearch(e.target.value)} />
        <button onClick={load} disabled={loading}>Refresh</button>
        <div style={{marginLeft:'auto', display:'flex', gap:8, alignItems:'center'}}>
          <span className="muted">Bot: </span>
          <span className={`badge ${ctrl?.bot_running ? 'green' : 'gray'}`}>{ctrl?.bot_running ? 'Running' : 'Stopped'}</span>
          <button className="success" onClick={() => doCtrl('resume')} disabled={!!ctrlAction}>Resume</button>
          <button className="warn" onClick={() => doCtrl('pause')} disabled={!!ctrlAction}>Pause</button>
          <button className="danger" onClick={() => doCtrl('stop')} disabled={!!ctrlAction}>Stop</button>
        </div>
      </div>

      {msg && <div className={msg.startsWith('error') ? 'error' : 'ok'}>{msg}</div>}

      {loading ? <p className="muted">Loading...</p> : (
        <table>
          <thead>
            <tr><th>Name</th><th>ID</th><th>Market</th><th>Lifecycle</th><th>Updated</th><th>Actions</th></tr>
          </thead>
          <tbody>
            {filtered.map(s => (
              <tr key={s.id}>
                <td>
                  <a href="#" onClick={e => { e.preventDefault(); setEdit(s) }} style={{color:'inherit'}}>{s.name}</a>
                </td>
                <td className="muted" style={{maxWidth:120, overflow:'hidden', textOverflow:'ellipsis'}}>{s.id}</td>
                <td><span className="badge blue">{s.market || '—'}</span></td>
                <td><span className={`badge ${stateColor(s.lifecycle_state)}`}>{s.lifecycle_state}</span></td>
                <td className="muted">{fmt(s.updated_at)}</td>
                <td>
                  <div style={{display:'flex', gap:4, flexWrap:'wrap', minWidth:140}}>
                    {s.lifecycle_state !== 'paused' && s.lifecycle_state !== 'stopped' && (
                      <button className="warn" onClick={() => doTransition(s.id, 'paused')} disabled={busy}>Pause</button>
                    )}
                    {s.lifecycle_state === 'paused' && (
                      <button className="success" onClick={() => doTransition(s.id, 'paper')} disabled={busy}>Resume</button>
                    )}
                    {s.lifecycle_state === 'draft' && (
                      <button className="success" onClick={() => doTransition(s.id, 'paper')} disabled={busy}>→ Paper</button>
                    )}
                    {s.lifecycle_state === 'paper' && (
                      <button className="danger" onClick={() => doTransition(s.id, 'live')} disabled={busy}>→ Live</button>
                    )}
                    {(s.lifecycle_state === 'live' || s.lifecycle_state === 'live_eligible') && (
                      <button className="warn" onClick={() => doTransition(s.id, 'stopped')} disabled={busy}>Stop</button>
                    )}
                    {s.lifecycle_state === 'stopped' && (
                      <button className="success" onClick={() => doTransition(s.id, 'paper')} disabled={busy}>Restart</button>
                    )}
                    <button onClick={() => setEdit(s)} disabled={busy}>Edit</button>
                  </div>
                </td>
              </tr>
            ))}
            {filtered.length === 0 && <tr><td colSpan={6} className="empty">No strategies</td></tr>}
          </tbody>
        </table>
      )}

      {edit && (
        <div className="modal-overlay" onClick={() => setEdit(null)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h3>Edit Strategy: {edit.name}</h3>
            <label>Name</label>
            <input value={edit.name || ''} onChange={e => setEdit({ ...edit, name: e.target.value })} />
            <label>Market</label>
            <input value={edit.market || ''} onChange={e => setEdit({ ...edit, market: e.target.value })} />
            <div style={{display:'flex', gap:8, marginTop:16, justifyContent:'flex-end'}}>
              <button onClick={() => setEdit(null)}>Cancel</button>
              <button className="success" onClick={() => doPatch(edit.id, { name: edit.name, market: edit.market })} disabled={busy}>Save</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}