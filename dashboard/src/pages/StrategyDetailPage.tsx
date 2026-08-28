import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api, LifecycleState } from '../lib/api';
import type { Strategy } from '../lib/api';
import { StateBadge, ErrorBanner } from '../components/UI';

const ALL_STATES: LifecycleState[] = [
  'DRAFT', 'PBT', 'KTEST', 'PAPER', 'TESTNET', 'LIVE_ELIGIBLE', 'LIVE', 'PAUSED', 'STOPPED', 'KILLED',
];

const STATE_DESC: Record<string, string> = {
  DRAFT: 'Working version, not yet backtested',
  PBT: 'Passing backtest',
  KTEST: 'Validated against historical data',
  PAPER: 'Running on paper exchange',
  TESTNET: 'Running on testnet',
  LIVE_ELIGIBLE: 'Ready for live, awaiting approval',
  LIVE: 'Executing real money',
  PAUSED: 'Temporarily stopped',
  STOPPED: 'Halted by operator',
  KILLED: 'Permanently shut down',
};

export default function StrategyDetailPage() {
  const { id } = useParams<{ id: string }>();
  const nav = useNavigate();
  const [strategy, setStrategy] = useState<Strategy | null>(null);
  const [error, setError] = useState('');
  const [confirmText, setConfirmText] = useState('');
  const [target, setTarget] = useState<LifecycleState | ''>('');
  const [busy, setBusy] = useState(false);

  const load = () => { if (id) api.getStrategy(id).then(setStrategy).catch(e => setError(e.message)); };
  useEffect(() => { load(); }, [id]);

  const onTransition = async () => {
    if (!target || !strategy) return;
    const needsLiveConfirm = target === 'LIVE';
    if (needsLiveConfirm && confirmText !== 'GO LIVE') {
      setError('Type "GO LIVE" to confirm live deployment');
      return;
    }
    setError(''); setBusy(true);
    try {
      const updated = await api.transitionStrategy(strategy.id, target, {
        confirm_live: needsLiveConfirm,
        confirmation_string: needsLiveConfirm ? confirmText : undefined,
      });
      setStrategy(updated);
      setTarget('');
      setConfirmText('');
    } catch (e) { setError(String(e)); }
    finally { setBusy(false); }
  };

  if (!strategy) return <div style={{ color: 'var(--muted)' }}>Loading…</div>;

  return (
    <>
      <div className="page-header">
        <div>
          <h1 className="page-title">{strategy.name}</h1>
          <div style={{ color: 'var(--muted)', fontSize: 13, marginTop: 4 }}>
            {strategy.market} · {strategy.timeframe} · {strategy.execution_mode}
          </div>
        </div>
        <button className="btn btn-ghost" onClick={() => nav('/strategies')}>← Back</button>
      </div>
      {error && <ErrorBanner>{error}</ErrorBanner>}

      <div className="card">
        <div className="card-title">Lifecycle</div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
          Current: <StateBadge state={strategy.lifecycle_state} />
        </div>
        <div className="form-row">
          <div className="form-group">
            <label className="form-label">Transition to</label>
            <select className="form-select" value={target} onChange={e => setTarget(e.target.value as LifecycleState)}>
              <option value="">— select target state —</option>
              {ALL_STATES.map(s => <option key={s} value={s}>{s}{STATE_DESC[s] ? ` — ${STATE_DESC[s]}` : ''}</option>)}
            </select>
          </div>
          <div className="form-group">
            <label className="form-label">Confirmation (only for LIVE)</label>
            <input className="form-input" value={confirmText} onChange={e => setConfirmText(e.target.value)} placeholder='Type "GO LIVE"' />
          </div>
        </div>
        <button className="btn btn-primary" onClick={onTransition} disabled={!target || busy}>
          {busy ? 'Transitioning…' : 'Apply transition'}
        </button>
      </div>

      <div className="card">
        <div className="card-title">Configuration</div>
        <div className="form-row">
          <div>
            <div className="stat-label">Entry Config</div>
            <pre style={{ fontSize: 11, color: 'var(--muted)', background: 'var(--bg)', padding: 12, borderRadius: 4, marginTop: 6, overflow: 'auto' }}>
              {JSON.stringify(strategy.entry_config, null, 2)}
            </pre>
          </div>
          <div>
            <div className="stat-label">Exit Config</div>
            <pre style={{ fontSize: 11, color: 'var(--muted)', background: 'var(--bg)', padding: 12, borderRadius: 4, marginTop: 6, overflow: 'auto' }}>
              {JSON.stringify(strategy.exit_config, null, 2)}
            </pre>
          </div>
        </div>
        <div className="form-row" style={{ marginTop: 12 }}>
          <div>
            <div className="stat-label">Risk Config</div>
            <pre style={{ fontSize: 11, color: 'var(--muted)', background: 'var(--bg)', padding: 12, borderRadius: 4, marginTop: 6, overflow: 'auto' }}>
              {JSON.stringify(strategy.risk_config, null, 2)}
            </pre>
          </div>
          <div>
            <div className="stat-label">Metadata</div>
            <pre style={{ fontSize: 11, color: 'var(--muted)', background: 'var(--bg)', padding: 12, borderRadius: 4, marginTop: 6, overflow: 'auto' }}>
{`version: ${strategy.version}
created_at: ${strategy.created_at}
updated_at: ${strategy.updated_at}
template: ${strategy.template_name || '—'}`}
            </pre>
          </div>
        </div>
      </div>
    </>
  );
}
