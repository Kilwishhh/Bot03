import { useState, useEffect, useCallback, useMemo } from 'react'
import { api } from '../api'
import { absoluteTime, relativeTime, useCurrentTime } from '../utils/time'

type LifecycleState =
  | 'draft' | 'backtest' | 'paper' | 'testnet'
  | 'live_eligible' | 'live' | 'paused' | 'stopped'

type UniverseType = 'all_binance_futures' | 'top_n_futures' | 'custom_watchlist'

type Timeframe = '1m' | '5m' | '15m' | '1h' | '4h' | '1d'
type ExecutionMode = 'paper' | 'testnet' | 'live'
type ExecutionVenue = 'binance' | 'hyperliquid' | 'walletconnect'

interface StrategyForm {
  name: string
  description: string
  execution_mode: ExecutionMode
  execution_venue: ExecutionVenue
  market: string
  timeframe: Timeframe
  universe_type: UniverseType
  universe_config: {
    top_n?: number
    symbols?: string[]
  }
  indicators_config: Array<{ name: string; params: Record<string, number> }>
  conditions_config: {
    logic: 'all' | 'any'
    groups: Array<{
      logic: 'all' | 'any'
      conditions: Array<{ field: string; op: string; value?: number; ref?: string }>
    }>
  }
  exit_config: {
    take_profit_pct: number
    stop_loss_pct: number
    trailing_stop: boolean
    trailing_pct: number
  }
  risk_config: {
    max_per_trade: number
    max_daily_loss: number
    max_open_positions: number
    max_leverage: number
    max_exposure: number
  }
  confidence_config: { mode: 'automatic' | 'fixed'; base_confidence: number }
  notes: string
}

const EMPTY: StrategyForm = {
  name: '',
  description: '',
  execution_mode: 'paper',
  execution_venue: 'binance',
  market: 'binance_futures',
  timeframe: '15m',
  universe_type: 'all_binance_futures',
  universe_config: { top_n: 20 },
  indicators_config: [
    { name: 'RSI', params: { period: 14 } },
    { name: 'EMA', params: { period: 21 } },
  ],
  conditions_config: {
    logic: 'all',
    groups: [{
      logic: 'all',
      conditions: [
        { field: 'RSI_14', op: '<', value: 30 },
        { field: 'PRICE', op: '>', value: 0 },
      ],
    }],
  },
  exit_config: { take_profit_pct: 1.5, stop_loss_pct: 0.8, trailing_stop: false, trailing_pct: 0 },
  risk_config: { max_per_trade: 0.02, max_daily_loss: 0.05, max_open_positions: 3, max_leverage: 10, max_exposure: 0.5 },
  confidence_config: { mode: 'automatic', base_confidence: 0.5 },
  notes: '',
}

const INDICATOR_TYPES = ['RSI', 'EMA', 'SMA', 'MACD', 'BOLLINGER', 'VOLUME']
const INDICATOR_DEFAULTS: Record<string, Record<string, number>> = {
  RSI: { period: 14 },
  EMA: { period: 21 },
  SMA: { period: 50 },
  MACD: { fast_period: 12, slow_period: 26, signal_period: 9 },
  BOLLINGER: { period: 20, std_multiplier: 2 },
  VOLUME: {},
}

// ── Timeframe helpers ────────────────────────────────────────────────────────
type TfUnit = 'minutes' | 'hours' | 'days'

const PRESETS: { label: string; value: number; unit: TfUnit }[] = [
  { label: '1m',  value: 1,  unit: 'minutes' },
  { label: '3m',  value: 3,  unit: 'minutes' },
  { label: '5m',  value: 5,  unit: 'minutes' },
  { label: '7m',  value: 7,  unit: 'minutes' },
  { label: '10m', value: 10, unit: 'minutes' },
  { label: '15m', value: 15, unit: 'minutes' },
  { label: '30m', value: 30, unit: 'minutes' },
  { label: '1h',  value: 1,  unit: 'hours'   },
  { label: '2h',  value: 2,  unit: 'hours'   },
  { label: '4h',  value: 4,  unit: 'hours'   },
  { label: '1d',  value: 1,  unit: 'days'    },
]

function unitChar(unit: TfUnit): string {
  return unit === 'minutes' ? 'm' : unit === 'hours' ? 'h' : 'd'
}

export function normalizeTimeframe(value: number, unit: TfUnit): string {
  return `${value}${unitChar(unit)}`
}

export function parseTimeframe(tf: string): { value: number; unit: TfUnit } {
  const m = tf.match(/^(\d+)([mhd])$/)
  if (!m) return { value: 15, unit: 'minutes' }
  const v = parseInt(m[1])
  const u = m[2]
  if (u === 'm') return { value: v, unit: 'minutes' }
  if (u === 'h') return { value: v, unit: 'hours' }
  return { value: v, unit: 'days' }
}

export function isValidTimeframe(value: number, unit: TfUnit): boolean {
  if (!value || value <= 0) return false
  return true
}
const OPS = ['>', '<', '>=', '<=', '==', 'CROSSES_ABOVE', 'CROSSES_BELOW']
const TIMEFRAMES: Timeframe[] = ['1m', '5m', '15m', '1h', '4h', '1d']

function exportTemplate(s: any): string {
  // Export a strategy as a pasteable template (YAML-ish key:value lines)
  const lines: string[] = []
  lines.push(`# MK Trader Strategy Template`)
  lines.push(`name: ${s.name}`)
  if (s.description) lines.push(`description: ${s.description}`)
  lines.push(`market: ${s.market}`)
  lines.push(`timeframe: ${s.timeframe}`)
  lines.push(`universe_type: ${s.universe_type ?? 'all_binance_futures'}`)
  if (s.universe_config && Object.keys(s.universe_config).length) {
    lines.push('universe_config:')
    for (const [k, v] of Object.entries(s.universe_config)) {
      lines.push(`  ${k}: ${JSON.stringify(v)}`)
    }
  }
  const inds = s.indicators_config ?? s.entry_config?.indicators ?? []
  if (Array.isArray(inds) && inds.length) {
    lines.push('indicators:')
    inds.forEach((i: any) => {
      const params = i.params ? Object.entries(i.params).map(([k, v]) => `${k}=${v}`).join(' ') : ''
      lines.push(`  - ${i.name}${params ? ' ' + params : ''}`)
    })
  }
  const conds = s.conditions_config ?? s.entry_config?.conditions ?? {}
  if (conds && (conds.groups || conds.logic)) {
    lines.push('conditions:')
    lines.push(`  logic: ${conds.logic || 'all'}`)
    ;(conds.groups ?? []).forEach((g: any, gi: number) => {
      lines.push(`  - logic: ${g.logic || 'all'}`)
      ;(g.conditions ?? []).forEach((c: any) => {
        const rhs = c.ref ? ` ref:${c.ref}` : (c.value != null ? ` ${c.value}` : '')
        lines.push(`    - ${c.field} ${c.op}${rhs}`)
      })
    })
  }
  const ex = s.exit_config ?? {}
  if (ex) {
    lines.push('exit:')
    if (ex.take_profit_pct != null) lines.push(`  take_profit_pct: ${ex.take_profit_pct}`)
    if (ex.stop_loss_pct != null) lines.push(`  stop_loss_pct: ${ex.stop_loss_pct}`)
    if (ex.trailing_stop) lines.push(`  trailing_stop: true`)
    if (ex.trailing_pct) lines.push(`  trailing_pct: ${ex.trailing_pct}`)
  }
  const rk = s.risk_config ?? {}
  if (rk) {
    lines.push('risk:')
    if (rk.max_per_trade != null) lines.push(`  max_per_trade: ${rk.max_per_trade}`)
    if (rk.max_daily_loss != null) lines.push(`  max_daily_loss: ${rk.max_daily_loss}`)
    if (rk.max_open_positions != null) lines.push(`  max_open_positions: ${rk.max_open_positions}`)
    if (rk.max_leverage != null) lines.push(`  max_leverage: ${rk.max_leverage}`)
    if (rk.max_exposure != null) lines.push(`  max_exposure: ${rk.max_exposure}`)
  }
  return lines.join('\n')
}

function parseTemplate(text: string): Partial<StrategyForm> {
  // Minimal parser: key: value, and -list items. Returns a form partial.
  const out: any = { indicators_config: [], conditions_config: { logic: 'all', groups: [] } }
  const lines = text.split('\n').map(l => l.replace(/^#.*/, '').trim()).filter(Boolean)
  let section: 'indicators' | 'conditions' | 'exit' | 'risk' | 'universe' | null = null
  let currentGroup: any = null
  for (const raw of lines) {
    const indent = raw.match(/^\s*/)?.[0].length ?? 0
    const line = raw.trim()
    if (line.startsWith('- ')) {
      const item = line.slice(2)
      if (section === 'indicators') {
        const [name, ...rest] = item.split(/\s+/)
        const params: Record<string, number> = {}
        for (const r of rest) {
          const [k, v] = r.split('=')
          if (k && v) params[k] = parseFloat(v) || 0
        }
        out.indicators_config.push({ name, params })
      } else if (section === 'conditions') {
        if (item.startsWith('logic:')) {
          // group header
          currentGroup = { logic: item.split(':')[1].trim(), conditions: [] }
          out.conditions_config.groups.push(currentGroup)
        } else {
          // condition "- FIELD OP [value|ref:NAME]"
          const m = item.match(/^(\S+)\s+(\S+)(?:\s+(.*))?$/)
          if (m && currentGroup) {
            const [, field, op, rhs] = m
            const cond: any = { field, op }
            if (rhs) {
              if (rhs.startsWith('ref:')) cond.ref = rhs.slice(4)
              else if (!isNaN(parseFloat(rhs))) cond.value = parseFloat(rhs)
            }
            currentGroup.conditions.push(cond)
          }
        }
      }
      continue
    }
    const [k, ...vrest] = line.split(':')
    const key = k.trim()
    const val = vrest.join(':').trim()
    if (line.endsWith(':')) {
      section = key as any
      if (section === 'conditions' && !out.conditions_config.groups.length) {
        out.conditions_config.groups = []
      }
      continue
    }
    section = null
    if (key === 'name') out.name = val
    else if (key === 'description') out.description = val
    else if (key === 'market') out.market = val
    else if (key === 'timeframe') out.timeframe = val
    else if (key === 'universe_type') out.universe_type = val
    else if (key === 'universe_config') {
      out.universe_config = out.universe_config ?? {}
    } else if (key === 'logic') {
      if (out.conditions_config.groups.length) {
        out.conditions_config.groups[out.conditions_config.groups.length - 1].logic = val
      } else {
        out.conditions_config.logic = val as any
      }
    } else if (key === 'take_profit_pct') out.exit_config = { ...(out.exit_config ?? EMPTY.exit_config), take_profit_pct: parseFloat(val) }
    else if (key === 'stop_loss_pct') out.exit_config = { ...(out.exit_config ?? EMPTY.exit_config), stop_loss_pct: parseFloat(val) }
    else if (key === 'trailing_stop') out.exit_config = { ...(out.exit_config ?? EMPTY.exit_config), trailing_stop: val === 'true' }
    else if (key === 'trailing_pct') out.exit_config = { ...(out.exit_config ?? EMPTY.exit_config), trailing_pct: parseFloat(val) }
    else if (key === 'max_per_trade') out.risk_config = { ...(out.risk_config ?? EMPTY.risk_config), max_per_trade: parseFloat(val) }
    else if (key === 'max_daily_loss') out.risk_config = { ...(out.risk_config ?? EMPTY.risk_config), max_daily_loss: parseFloat(val) }
    else if (key === 'max_open_positions') out.risk_config = { ...(out.risk_config ?? EMPTY.risk_config), max_open_positions: parseInt(val) }
    else if (key === 'max_leverage') out.risk_config = { ...(out.risk_config ?? EMPTY.risk_config), max_leverage: parseInt(val) }
    else if (key === 'max_exposure') out.risk_config = { ...(out.risk_config ?? EMPTY.risk_config), max_exposure: parseFloat(val) }
  }
  return out
}

function strategyToForm(s: any): StrategyForm {
  return {
    name: s.name ?? '',
    description: s.description ?? '',
    execution_mode: s.execution_mode ?? 'paper',
    execution_venue: s.execution_venue ?? 'binance',
    market: s.market ?? 'binance_futures',
    timeframe: s.timeframe ?? '15m',
    universe_type: s.universe_type ?? 'all_binance_futures',
    universe_config: s.universe_config ?? { top_n: 20 },
    indicators_config: s.indicators_config ?? s.entry_config?.indicators ?? EMPTY.indicators_config,
    conditions_config: s.conditions_config ?? (s.entry_config?.conditions ? { logic: 'all', groups: [{ logic: 'all', conditions: s.entry_config.conditions }] } : EMPTY.conditions_config),
    exit_config: s.exit_config ?? EMPTY.exit_config,
    risk_config: s.risk_config ?? EMPTY.risk_config,
    confidence_config: s.confidence_config ?? EMPTY.confidence_config,
    notes: s.notes ?? '',
  }
}

export default function Strategies() {
  const now = useCurrentTime()
  const [strats, setStrats] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [showNew, setShowNew] = useState(false)
  const [editing, setEditing] = useState<{ id: string; form: StrategyForm } | null>(null)
  const [newForm, setNewForm] = useState<StrategyForm>(EMPTY)
  const [importing, setImporting] = useState(false)
  const [importText, setImportText] = useState('')
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState<{ ok?: string; err?: string } | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const s = await api<any[]>('/admin/strategies')
      setStrats(Array.isArray(s) ? s : [])
    } catch { setStrats([]) }
    setLoading(false)
  }, [])

  useEffect(() => { load() }, [load])

  const filtered = useMemo(() => strats.filter(s =>
    !search || s.name?.toLowerCase().includes(search.toLowerCase())
    || s.market?.toLowerCase().includes(search.toLowerCase())
    || s.universe_type?.toLowerCase().includes(search.toLowerCase())
  ), [strats, search])

  const selected = strats.find(s => s.id === selectedId) || null

  const doTransition = async (id: string, target: string) => {
    setBusy(true); setMsg(null)
    try {
      await api(`/admin/strategies/${id}/transition`, { method: 'POST', body: { target_state: target } })
      setMsg({ ok: `Transitioned → ${target}` })
      await load()
    } catch (e: any) { setMsg({ err: e.detail || 'transition failed' }) }
    setBusy(false)
  }

  const doSaveNew = async () => {
    setBusy(true); setMsg(null)
    try {
      const created = await api<any>('/admin/strategies', { method: 'POST', body: newForm })
      setMsg({ ok: `Created ${created.name}` })
      setShowNew(false)
      setNewForm(EMPTY)
      await load()
    } catch (e: any) { setMsg({ err: e.detail || 'create failed' }) }
    setBusy(false)
  }

  const doSaveEdit = async () => {
    if (!editing) return
    setBusy(true); setMsg(null)
    try {
      await api(`/admin/strategies/${editing.id}`, { method: 'PATCH', body: editing.form })
      setMsg({ ok: `Saved ${editing.form.name}` })
      setEditing(null)
      await load()
    } catch (e: any) { setMsg({ err: e.detail || 'save failed' }) }
    setBusy(false)
  }

  const doDelete = async (id: string, name: string) => {
    if (!confirm(`Delete strategy "${name}"? This cannot be undone.`)) return
    setBusy(true); setMsg(null)
    try {
      await api(`/admin/strategies/${id}`, { method: 'DELETE' })
      setMsg({ ok: `Deleted ${name}` })
      if (selectedId === id) setSelectedId(null)
      await load()
    } catch (e: any) { setMsg({ err: e.detail || 'delete failed' }) }
    setBusy(false)
  }

  const doImport = async () => {
    setBusy(true); setMsg(null)
    try {
      const partial = parseTemplate(importText)
      const created = await api<any>('/admin/strategies', { method: 'POST', body: { ...EMPTY, ...partial } })
      setMsg({ ok: `Imported "${created.name}"` })
      setImporting(false)
      setImportText('')
      await load()
    } catch (e: any) { setMsg({ err: e.detail || 'import failed' }) }
    setBusy(false)
  }

  const exportSelected = () => {
    if (!selected) return
    const tpl = exportTemplate(selected)
    const blob = new Blob([tpl], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${selected.name || 'strategy'}.mks`
    a.click()
    URL.revokeObjectURL(url)
  }

  const stateColor = (st: string) => {
    if (st === 'live') return 'green'
    if (st === 'paper' || st === 'testnet') return 'blue'
    if (st === 'paused') return 'yellow'
    if (st === 'stopped') return 'red'
    return 'gray'
  }

  return (
    <div>
      <h2 className="page-title">Strategies</h2>

      <div className="toolbar">
        <input
          placeholder="Search strategies..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          style={{ minWidth: 220 }}
        />
        <button onClick={load} disabled={loading}>Refresh</button>
        <button className="success" onClick={() => setShowNew(true)}>+ New Strategy</button>
        <button onClick={() => setImporting(true)}>Import Template</button>
        {selected && <button onClick={exportSelected}>Export Selected</button>}
        <span className="muted" style={{ marginLeft: 'auto' }}>{filtered.length} strategies</span>
      </div>

      {msg && <div className={msg.err ? 'error' : 'ok'}>{msg.err || msg.ok}</div>}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        {/* ── List (Card view) ── */}
        <div>
          <h3>Available Strategies</h3>
          {loading ? <p className="muted">Loading…</p> : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {filtered.map(s => (
                <div
                  key={s.id}
                  onClick={() => setSelectedId(s.id)}
                  style={{
                    border: `2px solid ${selectedId === s.id ? '#3b82f6' : '#333'}`,
                    borderRadius: 6, padding: 12, cursor: 'pointer',
                    background: selectedId === s.id ? '#1a2332' : '#1c1c1c',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <strong>{s.name}</strong>
                    <span className={`badge ${stateColor(s.lifecycle_state)}`}>{s.lifecycle_state}</span>
                  </div>
                  <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>
                    {s.market || '—'} · {s.timeframe} · {s.universe_type || 'all_binance_futures'}
                  </div>
                  {s.description && (
                    <div style={{ fontSize: 13, marginTop: 4, color: '#bbb' }}>{s.description}</div>
                  )}
                </div>
              ))}
              {filtered.length === 0 && <p className="muted">No strategies. Click "+ New Strategy" to create one.</p>}
            </div>
          )}
        </div>

        {/* ── Detail / Edit panel ── */}
        <div>
          <h3>Strategy Detail</h3>
          {!selected ? (
            <p className="muted">Select a strategy to view details, or create a new one.</p>
          ) : (
            <div style={{ border: '1px solid #333', borderRadius: 6, padding: 16, background: '#1c1c1c' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <div>
                  <strong style={{ fontSize: 18 }}>{selected.name}</strong>
                  <span className={`badge ${stateColor(selected.lifecycle_state)}`} style={{ marginLeft: 8 }}>
                    {selected.lifecycle_state}
                  </span>
                </div>
                <span className="muted" style={{ fontSize: 12 }}>v{selected.version}</span>
              </div>

              <div className="muted" style={{ fontSize: 12, marginBottom: 12 }}>
                ID: {selected.id}<br />
                <span title={absoluteTime(selected.created_at)}>Created: {relativeTime(selected.created_at, now)}</span><br />
                <span title={absoluteTime(selected.updated_at)}>Updated: {relativeTime(selected.updated_at, now)}</span>
              </div>

              {selected.description && <p>{selected.description}</p>}

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, fontSize: 13, marginBottom: 12 }}>
                <div><span className="muted">Market:</span> {selected.market}</div>
                <div><span className="muted">Mode:</span> {selected.execution_mode}</div>
                <div><span className="muted">Venue:</span> {selected.execution_venue}</div>
                <div><span className="muted">Timeframe:</span> {selected.timeframe}</div>
                <div><span className="muted">Universe:</span> {selected.universe_type}</div>
                {selected.exit_config && (
                  <>
                    <div><span className="muted">TP:</span> {selected.exit_config.take_profit_pct ?? selected.exit_config.tp1_pct}%</div>
                    <div><span className="muted">SL:</span> {selected.exit_config.stop_loss_pct}%</div>
                  </>
                )}
              </div>

              {selected.indicators_config && selected.indicators_config.length > 0 && (
                <div style={{ marginBottom: 12 }}>
                  <div className="muted" style={{ fontSize: 12, marginBottom: 4 }}>Indicators:</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                    {selected.indicators_config.map((i: any, idx: number) => (
                      <span key={idx} className="badge blue">
                        {i.name} {i.params ? Object.entries(i.params).map(([k, v]) => `${k}=${v}`).join(' ') : ''}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {selected.conditions_config?.groups && selected.conditions_config.groups.length > 0 && (
                <div style={{ marginBottom: 12 }}>
                  <div className="muted" style={{ fontSize: 12, marginBottom: 4 }}>Entry conditions ({selected.conditions_config.logic || 'all'}):</div>
                  {selected.conditions_config.groups.map((g: any, gi: number) => (
                    <div key={gi} style={{ marginLeft: 8, fontSize: 12 }}>
                      <span className="muted">group {gi + 1} ({g.logic || 'all'}):</span>{' '}
                      {g.conditions.map((c: any, ci: number) => (
                        <span key={ci} className="badge gray" style={{ marginRight: 4 }}>
                          {c.field} {c.op} {c.ref ? `ref:${c.ref}` : c.value}
                        </span>
                      ))}
                    </div>
                  ))}
                </div>
              )}

              {/* Action buttons */}
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 12 }}>
                {selected.lifecycle_state === 'draft' && (
                  <button className="success" onClick={() => doTransition(selected.id, 'paper')} disabled={busy}>→ Paper</button>
                )}
                {selected.lifecycle_state === 'paper' && (
                  <>
                    <button className="warn" onClick={() => doTransition(selected.id, 'paused')} disabled={busy}>Pause</button>
                    <button className="danger" onClick={() => doTransition(selected.id, 'stopped')} disabled={busy}>Stop</button>
                  </>
                )}
                {selected.lifecycle_state === 'paused' && (
                  <>
                    <button className="success" onClick={() => doTransition(selected.id, 'paper')} disabled={busy}>Resume</button>
                    <button className="danger" onClick={() => doTransition(selected.id, 'stopped')} disabled={busy}>Stop</button>
                  </>
                )}
                {selected.lifecycle_state === 'stopped' && (
                  <button className="success" onClick={() => doTransition(selected.id, 'draft')} disabled={busy}>Restart (→ Draft)</button>
                )}
                <button onClick={() => setEditing({ id: selected.id, form: strategyToForm(selected) })} disabled={busy}>Edit</button>
                <button onClick={exportSelected}>Export</button>
                <button className="danger" onClick={() => doDelete(selected.id, selected.name)} disabled={busy}>Delete</button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── New Strategy modal ── */}
      {showNew && (
        <StrategyBuilder
          title="New Strategy"
          form={newForm}
          setForm={setNewForm}
          onClose={() => setShowNew(false)}
          onSave={doSaveNew}
          busy={busy}
        />
      )}

      {/* ── Edit modal ── */}
      {editing && (
        <StrategyBuilder
          title={`Edit: ${editing.form.name}`}
          form={editing.form}
          setForm={(f) => setEditing({ ...editing, form: f })}
          onClose={() => setEditing(null)}
          onSave={doSaveEdit}
          busy={busy}
        />
      )}

      {/* ── Import modal ── */}
      {importing && (
        <div className="modal-overlay" onClick={() => setImporting(false)}>
          <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 720 }}>
            <h3>Import Strategy Template</h3>
            <p className="muted" style={{ fontSize: 12 }}>
              Paste a strategy template in the MK Trader format (see Export for an example).
              The parser supports: name, market, timeframe, universe_type, indicators (name period=N),
              conditions (groups with logic + field op value), exit (TP/SL), risk.
            </p>
            <textarea
              value={importText}
              onChange={e => setImportText(e.target.value)}
              style={{ width: '100%', minHeight: 280, fontFamily: 'monospace', fontSize: 12 }}
              placeholder={`# MK Trader Strategy Template
name: My Strategy
market: binance_futures
timeframe: 15m
universe_type: all_binance_futures
indicators:
  - RSI period=14
  - EMA period=21
conditions:
  logic: all
  - logic: all
    - RSI_14 < 30
    - PRICE > 0
exit:
  take_profit_pct: 1.5
  stop_loss_pct: 0.8
risk:
  max_per_trade: 0.02
  max_leverage: 10`}
            />
            <div style={{ display: 'flex', gap: 8, marginTop: 16, justifyContent: 'flex-end' }}>
              <button onClick={() => setImporting(false)}>Cancel</button>
              <button className="success" onClick={doImport} disabled={busy || !importText.trim()}>
                {busy ? 'Importing…' : 'Import'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

/* ──────────────────────────────────────────────────────────────────────
   StrategyBuilder — full strategy form (New + Edit)
   ────────────────────────────────────────────────────────────────────── */
function StrategyBuilder(props: {
  title: string
  form: StrategyForm
  setForm: (f: StrategyForm) => void
  onClose: () => void
  onSave: () => void
  busy: boolean
}) {
  const { title, form, setForm, onClose, onSave, busy } = props
  const f = form

  // Local timeframe UI state derived from form.timeframe
  const tfParsed = useMemo(() => parseTimeframe(f.timeframe), [f.timeframe])
  const [tfValue, setTfValue] = useState(tfParsed.value)
  const [tfUnit, setTfUnit] = useState<TfUnit>(tfParsed.unit)

  // Sync when form.timeframe changes externally (e.g. import / template parse)
  useEffect(() => {
    const p = parseTimeframe(f.timeframe)
    setTfValue(p.value)
    setTfUnit(p.unit)
  }, [f.timeframe])

  const [tfError, setTfError] = useState('')

  const applyTfChange = (v: number, u: TfUnit) => {
    setTfValue(v)
    setTfUnit(u)
    if (!isValidTimeframe(v, u)) {
      setTfError('Timeframe must be > 0')
    } else {
      setTfError('')
      setField('timeframe', normalizeTimeframe(v, u) as any)
    }
  }

  const setField = <K extends keyof StrategyForm>(k: K, v: StrategyForm[K]) =>
    setForm({ ...f, [k]: v })

  const setIndicator = (idx: number, patch: Partial<{ name: string; params: Record<string, number> }>) => {
    const arr = [...f.indicators_config]
    arr[idx] = { ...arr[idx], ...patch }
    setField('indicators_config', arr)
  }
  const addIndicator = () =>
    setField('indicators_config', [...f.indicators_config, { name: 'RSI', params: { period: 14 } }])
  const removeIndicator = (idx: number) =>
    setField('indicators_config', f.indicators_config.filter((_, i) => i !== idx))
  const indicatorFields = f.indicators_config.flatMap(ind => {
    const period = ind.params.period
    if (ind.name === 'MACD') return ['MACD_LINE', 'MACD_SIGNAL', 'MACD_HIST']
    if (ind.name === 'BOLLINGER') return ['BB_UPPER', 'BB_MIDDLE', 'BB_LOWER']
    if (ind.name === 'VOLUME') return ['VOLUME']
    return period ? [`${ind.name}_${period}`] : [ind.name]
  })
  const availableFields = ['PRICE', ...indicatorFields]

  const setGroup = (gi: number, patch: any) => {
    const groups = [...f.conditions_config.groups]
    groups[gi] = { ...groups[gi], ...patch }
    setField('conditions_config', { ...f.conditions_config, groups })
  }
  const setCondition = (gi: number, ci: number, patch: any) => {
    const groups = [...f.conditions_config.groups]
    const conds = [...groups[gi].conditions]
    conds[ci] = { ...conds[ci], ...patch }
    groups[gi] = { ...groups[gi], conditions: conds }
    setField('conditions_config', { ...f.conditions_config, groups })
  }
  const addGroup = () =>
    setField('conditions_config', {
      ...f.conditions_config,
      groups: [...f.conditions_config.groups, { logic: 'all', conditions: [{ field: 'PRICE', op: '>', value: 0 }] }],
    })
  const removeGroup = (gi: number) =>
    setField('conditions_config', {
      ...f.conditions_config,
      groups: f.conditions_config.groups.filter((_, i) => i !== gi),
    })
  const addCondition = (gi: number) =>
    setGroup(gi, { conditions: [...f.conditions_config.groups[gi].conditions, { field: 'PRICE', op: '>', value: 0 }] })
  const removeCondition = (gi: number, ci: number) =>
    setGroup(gi, { conditions: f.conditions_config.groups[gi].conditions.filter((_, i) => i !== ci) })

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 880, maxHeight: '90vh', overflow: 'auto' }}>
        <h3>{title}</h3>
        <p className="muted" style={{marginTop:-6}}>
          Build your strategy in four steps: choose the market, add indicators, define when to enter, then protect the trade.
        </p>
        <div style={{display:'flex', gap:6, flexWrap:'wrap', marginBottom:14}}>
          {['1 Basics', '2 Indicators', '3 Entry rules', '4 Exits & risk'].map(step =>
            <span key={step} className="badge blue">{step}</span>
          )}
        </div>

        {/* Basic info */}
        <fieldset>
          <legend>Basic</legend>
          <label>Name *</label>
          <input value={f.name} onChange={e => setField('name', e.target.value)} style={{ width: '100%' }} />
          <label>Description</label>
          <textarea value={f.description} onChange={e => setField('description', e.target.value)} style={{ width: '100%', minHeight: 50 }} />
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: 8 }}>
            <div>
              <label>Market</label>
              <select value={f.market} onChange={e => setField('market', e.target.value)}>
                <option value="binance_futures">Binance Futures</option>
                <option value="binance_spot">Binance Spot</option>
                <option value="hyperliquid">Hyperliquid</option>
              </select>
            </div>
            <div>
              <label>Venue</label>
              <select value={f.execution_venue} onChange={e => setField('execution_venue', e.target.value as any)}>
                <option value="binance">Binance (CEX)</option>
                <option value="hyperliquid">Hyperliquid (DEX)</option>
                <option value="walletconnect">WalletConnect (DEX)</option>
              </select>
            </div>
            <div>
              <label>Mode</label>
              <select value={f.execution_mode} onChange={e => setField('execution_mode', e.target.value as any)}>
                <option value="paper">Paper (real data, simulated fills)</option>
                <option value="testnet">Testnet</option>
                <option value="live">Live</option>
              </select>
            </div>
            <div>
              <label>Timeframe</label>
              <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
                <input
                  type="number"
                  min={1}
                  style={{ width: 80 }}
                  value={tfValue}
                  onChange={e => applyTfChange(parseInt(e.target.value) || 0, tfUnit)}
                />
                <select value={tfUnit} onChange={e => applyTfChange(tfValue, e.target.value as TfUnit)}>
                  <option value="minutes">Minutes</option>
                  <option value="hours">Hours</option>
                  <option value="days">Days</option>
                </select>
                <span style={{ marginLeft: 4, color: tfError ? 'var(--red)' : 'var(--green)', fontSize: 12 }}>
                  {tfError
                    ? `✗ ${tfError}`
                    : `✓ ${normalizeTimeframe(tfValue, tfUnit)}`}
                </span>
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 6 }}>
                {PRESETS.map(p => {
                  const active = p.value === tfValue && p.unit === tfUnit
                  return (
                    <button
                      key={p.label}
                      type="button"
                      onClick={() => applyTfChange(p.value, p.unit)}
                      style={{
                        fontSize: 11,
                        padding: '2px 6px',
                        border: '1px solid var(--border)',
                        background: active ? 'var(--accent)' : 'transparent',
                        color: active ? '#fff' : 'var(--text)',
                        borderRadius: 3,
                        cursor: 'pointer',
                      }}
                    >{p.label}</button>
                  )
                })}
              </div>
            </div>
          </div>
        </fieldset>

        {/* Universe */}
        <fieldset>
          <legend>Symbol Universe</legend>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 8 }}>
            <div>
              <label>Universe</label>
              <select value={f.universe_type} onChange={e => setField('universe_type', e.target.value as any)}>
                <option value="all_binance_futures">All Binance Futures USDT</option>
                <option value="top_n_futures">Top N by volume</option>
                <option value="custom_watchlist">Custom watchlist</option>
              </select>
            </div>
            {f.universe_type === 'top_n_futures' && (
              <div>
                <label>Top N</label>
                <input
                  type="number" min={1} max={500}
                  value={f.universe_config.top_n ?? 20}
                  onChange={e => setField('universe_config', { ...f.universe_config, top_n: parseInt(e.target.value) || 20 })}
                />
              </div>
            )}
            {f.universe_type === 'custom_watchlist' && (
              <div>
                <label>Symbols (comma-separated)</label>
                <input
                  value={(f.universe_config.symbols ?? []).join(',')}
                  onChange={e => setField('universe_config', {
                    ...f.universe_config,
                    symbols: e.target.value.split(',').map(s => s.trim().toUpperCase()).filter(Boolean),
                  })}
                />
              </div>
            )}
          </div>
        </fieldset>

        {/* Indicators */}
        <fieldset>
          <legend>2. Indicators — what should the strategy measure?</legend>
          <p className="muted" style={{fontSize:12}}>Add as many indicators as you need. Their values become available in the Entry rules section.</p>
          {f.indicators_config.map((ind, idx) => (
            <div key={idx} style={{ display: 'grid', gridTemplateColumns: '1fr 2fr auto', gap: 8, marginBottom: 8, alignItems: 'center', border:'1px solid #333', borderRadius:6, padding:8 }}>
              <select value={ind.name} onChange={e => setIndicator(idx, { name: e.target.value, params: INDICATOR_DEFAULTS[e.target.value] })}>
                {INDICATOR_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
              <div style={{display:'flex', gap:6, flexWrap:'wrap'}}>
                {Object.entries(ind.params).map(([pk, pv]) => (
                <label key={pk} style={{display:'flex', alignItems:'center', gap:4, fontSize:12}}>
                  <span className="muted">{pk}</span>
                  <input
                    type="number" min={1} style={{ width: 68 }} value={pv}
                    onChange={e => setIndicator(idx, { params: { ...ind.params, [pk]: parseFloat(e.target.value) || 0 } })}
                  />
                </label>
              ))}
              </div>
              <button className="danger" onClick={() => removeIndicator(idx)}>×</button>
            </div>
          ))}
          <button onClick={addIndicator}>+ Add Indicator</button>
        </fieldset>

        {/* Conditions */}
        <fieldset>
          <legend>3. Entry rules — when should it open a trade?</legend>
          <p className="muted" style={{fontSize:12}}>A condition compares a live indicator with a number or another indicator. Use groups to create advanced AND/OR logic.</p>
          <div style={{ marginBottom: 8 }}>
            <label>Top-level logic: </label>
            <select value={f.conditions_config.logic} onChange={e => setField('conditions_config', { ...f.conditions_config, logic: e.target.value as any })}>
              <option value="all">ALL groups must pass (AND)</option>
              <option value="any">ANY group may pass (OR)</option>
            </select>
          </div>
          {f.conditions_config.groups.map((g, gi) => (
            <div key={gi} style={{ border: '1px solid #333', padding: 8, marginBottom: 8, borderRadius: 4 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                <strong>Group {gi + 1}</strong>
                <span className="muted">logic:</span>
                <select value={g.logic} onChange={e => setGroup(gi, { logic: e.target.value as any })}>
                  <option value="all">ALL (AND)</option>
                  <option value="any">ANY (OR)</option>
                </select>
                <button className="danger" onClick={() => removeGroup(gi)} style={{ marginLeft: 'auto' }}>Remove group</button>
              </div>
              {g.conditions.map((c, ci) => (
                <div key={ci} style={{ display: 'flex', gap: 4, marginBottom: 4, alignItems: 'center' }}>
                  <select value={c.field} onChange={e => setCondition(gi, ci, { field: e.target.value })}>
                    {availableFields.map(field => <option key={field} value={field}>{field}</option>)}
                  </select>
                  <select value={c.op} onChange={e => setCondition(gi, ci, { op: e.target.value })}>
                    {OPS.map(o => <option key={o} value={o}>{o}</option>)}
                  </select>
                  <input
                    placeholder="number or ref:EMA_21" value={c.ref ? `ref:${c.ref}` : (c.value ?? '')}
                    onChange={e => {
                      const v = e.target.value
                      if (v.startsWith('ref:')) setCondition(gi, ci, { ref: v.slice(4), value: undefined })
                      else setCondition(gi, ci, { value: parseFloat(v), ref: undefined })
                    }} style={{ width: 110 }}
                  />
                  <button className="danger" onClick={() => removeCondition(gi, ci)}>×</button>
                </div>
              ))}
              <button onClick={() => addCondition(gi)}>+ Add Condition</button>
            </div>
          ))}
          <button onClick={addGroup}>+ Add Group</button>
        </fieldset>

        {/* Exit / TP / SL */}
        <fieldset>
          <legend>4. Exits — take profit, stop loss & trailing protection</legend>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: 8 }}>
            <div>
              <label>TP %</label>
              <input type="number" step="0.1" value={f.exit_config.take_profit_pct}
                onChange={e => setField('exit_config', { ...f.exit_config, take_profit_pct: parseFloat(e.target.value) || 0 })} />
            </div>
            <div>
              <label>SL %</label>
              <input type="number" step="0.1" value={f.exit_config.stop_loss_pct}
                onChange={e => setField('exit_config', { ...f.exit_config, stop_loss_pct: parseFloat(e.target.value) || 0 })} />
            </div>
            <div>
              <label>Trailing %</label>
              <input type="number" step="0.1" value={f.exit_config.trailing_pct}
                onChange={e => setField('exit_config', { ...f.exit_config, trailing_pct: parseFloat(e.target.value) || 0 })} />
            </div>
            <div>
              <label>Trailing</label>
              <select value={f.exit_config.trailing_stop ? 'yes' : 'no'} onChange={e => setField('exit_config', { ...f.exit_config, trailing_stop: e.target.value === 'yes' })}>
                <option value="no">No</option>
                <option value="yes">Yes</option>
              </select>
            </div>
          </div>
        </fieldset>

        {/* Risk */}
        <fieldset>
          <legend>Risk guardrails — keep the account protected</legend>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
            <div>
              <label>Max per trade (fraction of balance)</label>
              <input type="number" step="0.01" value={f.risk_config.max_per_trade}
                onChange={e => setField('risk_config', { ...f.risk_config, max_per_trade: parseFloat(e.target.value) || 0 })} />
            </div>
            <div>
              <label>Max daily loss</label>
              <input type="number" step="0.01" value={f.risk_config.max_daily_loss}
                onChange={e => setField('risk_config', { ...f.risk_config, max_daily_loss: parseFloat(e.target.value) || 0 })} />
            </div>
            <div>
              <label>Max open positions</label>
              <input type="number" min={1} value={f.risk_config.max_open_positions}
                onChange={e => setField('risk_config', { ...f.risk_config, max_open_positions: parseInt(e.target.value) || 1 })} />
            </div>
            <div>
              <label>Max leverage</label>
              <input type="number" min={1} max={125} value={f.risk_config.max_leverage}
                onChange={e => setField('risk_config', { ...f.risk_config, max_leverage: parseInt(e.target.value) || 1 })} />
            </div>
            <div>
              <label>Max exposure</label>
              <input type="number" step="0.05" value={f.risk_config.max_exposure}
                onChange={e => setField('risk_config', { ...f.risk_config, max_exposure: parseFloat(e.target.value) || 0 })} />
            </div>
          </div>
        </fieldset>

        {/* Confidence */}
        <fieldset>
          <legend>Confidence</legend>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
            <div>
              <label>Mode</label>
              <select value={f.confidence_config.mode} onChange={e => setField('confidence_config', { ...f.confidence_config, mode: e.target.value as any })}>
                <option value="automatic">Automatic (from conditions matched)</option>
                <option value="fixed">Fixed</option>
              </select>
            </div>
            <div>
              <label>Base confidence (0-1)</label>
              <input type="number" step="0.05" min={0} max={1} value={f.confidence_config.base_confidence}
                onChange={e => setField('confidence_config', { ...f.confidence_config, base_confidence: parseFloat(e.target.value) || 0 })} />
            </div>
          </div>
        </fieldset>

        <div style={{ display: 'flex', gap: 8, marginTop: 16, justifyContent: 'flex-end' }}>
          <button onClick={onClose}>Cancel</button>
          <button className="success" onClick={onSave} disabled={busy || !f.name.trim()}>
            {busy ? 'Saving…' : 'Save Strategy'}
          </button>
        </div>
      </div>
    </div>
  )
}
