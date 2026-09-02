import { useState, useEffect } from 'react'
import { api } from '../api'

export default function PaperConfig() {
  const [config, setConfig] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [msg, setMsg] = useState('')
  const [form, setForm] = useState({
    balance: '10000', leverage: '10', trade_size_pct: '1', max_positions: '5',
    max_daily_loss: '500', max_drawdown_pct: '20', tp_pct: '0.30', sl_pct: '0.50',
    minimum_hits: '1',
  })

  const load = async () => {
    setLoading(true)
    try {
      const data = await api('/paper-config')
      setConfig(data)
      if (data.config) {
        const c = data.config
        setForm(f => ({
          balance: String(c.balance ?? 10000),
          leverage: String(c.leverage ?? 10),
          trade_size_pct: String(c.trade_size_pct ?? 1),
          max_positions: String(c.max_positions ?? 5),
          max_daily_loss: String(c.max_daily_loss ?? 500),
          max_drawdown_pct: String(c.max_drawdown_pct ?? 20),
          tp_pct: String(c.tp_pct ?? 0.30),
          sl_pct: String(c.sl_pct ?? 0.50),
          minimum_hits: String(c.minimum_hits ?? 1),
        }))
      }
    } catch {}
    setLoading(false)
  }

  useEffect(() => { load() }, [])

  const save = async () => {
    setSaving(true)
    setMsg('')
    try {
      const payload = {
        balance: parseFloat(form.balance),
        leverage: parseInt(form.leverage),
        trade_size_pct: parseFloat(form.trade_size_pct),
        max_positions: parseInt(form.max_positions),
        max_daily_loss: parseFloat(form.max_daily_loss),
        max_drawdown_pct: parseFloat(form.max_drawdown_pct),
        tp_pct: parseFloat(form.tp_pct),
        sl_pct: parseFloat(form.sl_pct),
        minimum_hits: parseInt(form.minimum_hits),
      }
      await api('/paper-config', { method: 'POST', body: payload })
      setMsg('Saved!')
      await load()
    } catch (e: any) {
      setMsg(e.detail || 'Error saving')
    }
    setSaving(false)
    setTimeout(() => setMsg(''), 3000)
  }

  const set = (k: string, v: string) => setForm(f => ({ ...f, [k]: v }))

  if (loading) return <p className="muted">Loading...</p>

  return (
    <div>
      <h2 className="page-title">Paper Trading Config</h2>
      <div className="row">
        <div className="col card">
          <h3>Account</h3>
          <label className="muted">Balance ($)</label>
          <input style={{width:'100%'}} value={form.balance} onChange={e => set('balance', e.target.value)} />
          <label className="muted">Leverage (x)</label>
          <input style={{width:'100%'}} value={form.leverage} onChange={e => set('leverage', e.target.value)} />
        </div>
        <div className="col card">
          <h3>Risk</h3>
          <label className="muted">Trade size %</label>
          <input style={{width:'100%'}} value={form.trade_size_pct} onChange={e => set('trade_size_pct', e.target.value)} />
          <label className="muted">Max positions</label>
          <input style={{width:'100%'}} value={form.max_positions} onChange={e => set('max_positions', e.target.value)} />
          <label className="muted">Max daily loss ($)</label>
          <input style={{width:'100%'}} value={form.max_daily_loss} onChange={e => set('max_daily_loss', e.target.value)} />
          <label className="muted">Max drawdown %</label>
          <input style={{width:'100%'}} value={form.max_drawdown_pct} onChange={e => set('max_drawdown_pct', e.target.value)} />
        </div>
        <div className="col card">
          <h3>Trade Rules</h3>
          <label className="muted">Take Profit %</label>
          <input style={{width:'100%'}} value={form.tp_pct} onChange={e => set('tp_pct', e.target.value)} />
          <label className="muted">Stop Loss %</label>
          <input style={{width:'100%'}} value={form.sl_pct} onChange={e => set('sl_pct', e.target.value)} />
          <label className="muted">Min conditions pass (N/M)</label>
          <input style={{width:'100%'}} value={form.minimum_hits} onChange={e => set('minimum_hits', e.target.value)} placeholder="1" type="number" min="1" />
        </div>
      </div>
      <div style={{marginTop:16, display:'flex', gap:8, alignItems:'center'}}>
        <button onClick={save} disabled={saving}>{saving ? 'Saving...' : 'Save Config'}</button>
        {msg && <span style={{color: msg === 'Saved!' ? 'var(--green)' : 'var(--red)'}}>{msg}</span>}
        {config?.current_balance != null && (
          <span className="muted" style={{marginLeft:'auto'}}>Current balance: <strong>${config.current_balance}</strong></span>
        )}
      </div>
    </div>
  )
}
