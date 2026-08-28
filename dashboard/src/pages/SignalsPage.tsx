import { useEffect, useState } from 'react';
import { api, Signal, Followup } from '../lib/api';
import { SideBadge, EmptyState, ErrorBanner } from '../components/UI';

export default function SignalsPage() {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [error, setError] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [expanded, setExpanded] = useState<string | null>(null);
  const [followups, setFollowups] = useState<Record<string, Followup[]>>({});

  const load = () => {
    api.listSignals(statusFilter ? { status: statusFilter, limit: 100 } : { limit: 100 })
      .then(setSignals)
      .catch(e => setError(e.message));
  };

  useEffect(load, [statusFilter]);

  const loadFollowups = async (signalId: string) => {
    if (followups[signalId]) {
      setExpanded(expanded === signalId ? null : signalId);
      return;
    }
    try {
      const f = await api.listFollowups(signalId);
      setFollowups({ ...followups, [signalId]: f });
      setExpanded(signalId);
    } catch (e) { setError(String(e)); }
  };

  return (
    <>
      <div className="page-header"><h1 className="page-title">Signals</h1></div>
      {error && <ErrorBanner>{error}</ErrorBanner>}
      <div className="tab-bar">
        {['', 'PENDING', 'ACTIVE', 'TP1_HIT', 'TP2_HIT', 'STOPPED_OUT', 'EXPIRED', 'CANCELLED'].map(s => (
          <div key={s} className={`tab${statusFilter === s ? ' active' : ''}`} onClick={() => setStatusFilter(s)}>
            {s || 'All'}
          </div>
        ))}
      </div>
      {signals.length === 0 ? <EmptyState title="No signals" /> : (
        <div className="card" style={{ padding: 0 }}>
          <table>
            <thead>
              <tr><th>Symbol</th><th>Side</th><th>Confidence</th><th>Entry</th><th>TP1</th><th>SL</th><th>Strategy</th><th>When</th><th></th></tr>
            </thead>
            <tbody>
              {signals.map(s => (
                <>
                  <tr key={s.id}>
                    <td><strong>{s.symbol}</strong></td>
                    <td><SideBadge side={s.side} /></td>
                    <td>{(s.confidence * 100).toFixed(0)}%</td>
                    <td style={{ color: 'var(--muted)' }}>{s.entry_price || '—'}</td>
                    <td style={{ color: 'var(--success)' }}>{s.tp1 || '—'}</td>
                    <td style={{ color: 'var(--danger)' }}>{s.stop_loss || '—'}</td>
                    <td>{s.strategy_name}</td>
                    <td style={{ color: 'var(--muted)', fontSize: 12 }}>{new Date(s.created_at).toLocaleString()}</td>
                    <td>
                      <button className="btn btn-ghost btn-sm" onClick={() => loadFollowups(s.id)}>
                        {expanded === s.id ? 'Hide' : 'Timeline'}
                      </button>
                    </td>
                  </tr>
                  {expanded === s.id && (
                    <tr key={s.id + '-fu'}>
                      <td colSpan={9} style={{ background: 'var(--bg)', padding: 16 }}>
                        <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--muted)', marginBottom: 8 }}>TIMELINE</div>
                        {(followups[s.id] || []).length === 0 ? <div style={{ color: 'var(--muted)', fontSize: 13 }}>No follow-ups yet</div> :
                          (followups[s.id] || []).map(f => (
                            <div key={f.id} style={{ fontSize: 12, padding: '6px 0', borderBottom: '1px solid var(--border)' }}>
                              <span style={{ color: 'var(--primary)', fontWeight: 600, marginRight: 8 }}>{f.event_type}</span>
                              <span style={{ color: 'var(--muted)' }}>{new Date(f.created_at).toLocaleString()}</span>
                              {f.detail && Object.keys(f.detail).length > 0 && (
                                <div style={{ color: 'var(--muted)', fontSize: 11, marginTop: 2 }}>{JSON.stringify(f.detail)}</div>
                              )}
                            </div>
                          ))
                        }
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
