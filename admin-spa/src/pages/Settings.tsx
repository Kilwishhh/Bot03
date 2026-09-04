import { useState, useEffect } from 'react'
import { api } from '../api'

export default function Settings() {
  const [status, setStatus] = useState<any>(null)
  const [mode, setMode] = useState('')
  const [live, setLive] = useState(false)
  const [restarting, setRestarting] = useState(false)
  const [msg, setMsg] = useState<{ok?:string; err?:string}>({})
  const [loading, setLoading] = useState(true)

  const load = async () => {
    try {
      const [sys, ctrl] = await Promise.all([
        api('/health'),
        api('/control/status'),
      ])
      setStatus({ ...sys, trading_mode: sys.mode })
      setMode(ctrl.desired_state || 'unknown')
      setLive(Boolean(sys.live_trading_enabled))
    } catch { setStatus(null) } finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const restart = async () => {
    if (!confirm('Restart the FastAPI server now?')) return
    setRestarting(true)
    setMsg({})
    try {
      await api('/admin/server-restart', { method: 'POST' })
      setMsg({ ok: 'Server restarting… refresh in ~10s.' })
      // poll until it comes back
      for (let i = 0; i < 15; i++) {
        await new Promise(r => setTimeout(r, 1000))
        try {
          await api('/health')
          window.location.reload()
          return
        } catch { /* still down */ }
      }
      setMsg({ err: 'Server did not restart. Check terminal.' })
    } catch (e: any) {
      setMsg({ err: e.detail || String(e) })
    } finally { setRestarting(false) }
  }

  if (loading) return <div className="page"><div className="loading">Loading…</div></div>

  return (
    <div className="page">
      <h2>Settings</h2>

      <div className="card">
        <h3>Server Status</h3>
        <table className="info-table">
          <tbody>
            <tr><td>API healthy</td><td>{status ? '✅' : '❌'}</td></tr>
            <tr><td>Bot state</td><td><code>{mode}</code></td></tr>
            <tr><td>Trading mode</td><td>{status?.trading_mode || '?'}</td></tr>
            <tr><td>Live trading</td><td>{live ? '⚠️ Enabled' : 'Disabled'}</td></tr>
          </tbody>
        </table>
      </div>

      <div className="card">
        <h3>Actions</h3>
        <div style={{display:'flex',gap:12,flexWrap:'wrap'}}>
          <button className="btn-primary" onClick={restart} disabled={restarting}>
            {restarting ? '⏳ Restarting…' : '🔄 Restart Server'}
          </button>
          <button className="btn" onClick={load}>Refresh</button>
        </div>
        {msg.ok && <div className="success">{msg.ok}</div>}
        {msg.err && <div className="error">{msg.err}</div>}
        <p style={{marginTop:12,fontSize:12,color:'var(--muted)'}}>
          Restart kills the current FastAPI process and starts a fresh one.
          Takes ~5–10 seconds. WebSocket reconnects automatically.
        </p>
      </div>

      <div className="card">
        <h3>About</h3>
        <table className="info-table">
          <tbody>
            <tr><td>Admin SPA</td><td>v1.0</td></tr>
            <tr><td>Build</td><td>{import.meta.env.MODE}</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  )
}
