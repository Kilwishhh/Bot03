import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api, Strategy } from '../lib/api';
import { StateBadge, EmptyState, ErrorBanner } from '../components/UI';

export default function StrategiesPage() {
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [stateFilter, setStateFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const nav = useNavigate();

  const load = () => {
    setLoading(true);
    api.listStrategies(stateFilter ? { state: stateFilter } : undefined)
      .then(setStrategies)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(load, [stateFilter]);

  const onDelete = async (id: string) => {
    if (!confirm('Delete this strategy?')) return;
    try { await api.deleteStrategy(id); load(); }
    catch (e) { setError(String(e)); }
  };

  return (
    <>
      <div className="page-header">
        <h1 className="page-title">Strategies</h1>
        <button className="btn btn-primary" onClick={() => nav('/strategies/create')}>+ New Strategy</button>
      </div>
      {error && <ErrorBanner>{error}</ErrorBanner>}
      <div className="tab-bar">
        {(['', 'DRAFT', 'PAPER', 'TESTNET', 'LIVE', 'PAUSED', 'STOPPED'] as const).map(s => (
          <div key={s} className={`tab${stateFilter === s ? ' active' : ''}`} onClick={() => setStateFilter(s)}>
            {s || 'All'}
          </div>
        ))}
      </div>
      {loading ? <div style={{ color: 'var(--muted)' }}>Loading…</div> :
        strategies.length === 0 ? <EmptyState title="No strategies" hint="Create your first strategy" /> : (
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <table>
            <thead>
              <tr><th>Name</th><th>Market</th><th>Timeframe</th><th>Mode</th><th>State</th><th>Updated</th><th></th></tr>
            </thead>
            <tbody>
              {strategies.map(s => (
                <tr key={s.id}>
                  <td><Link to={`/strategies/${s.id}`}><strong>{s.name}</strong></Link></td>
                  <td>{s.market}</td>
                  <td>{s.timeframe}</td>
                  <td>{s.execution_mode}</td>
                  <td><StateBadge state={s.lifecycle_state} /></td>
                  <td style={{ color: 'var(--muted)', fontSize: 12 }}>{new Date(s.updated_at).toLocaleString()}</td>
                  <td>
                    <button className="btn btn-ghost btn-sm" onClick={() => onDelete(s.id)}>Delete</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
