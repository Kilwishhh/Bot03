import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, Strategy, Signal, HealthStatus } from '../lib/api';
import { StateBadge, SideBadge, EmptyState } from '../components/UI';

export default function OverviewPage() {
  const [strategies, setStrategies] = useState<Strategy[]>([]);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api.listStrategies(), api.listSignals({ limit: 5 }), api.health()])
      .then(([s, sig, h]) => { setStrategies(s); setSignals(sig); setHealth(h); })
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div style={{ color: 'var(--muted)' }}>Loading…</div>;

  const liveCount = strategies.filter(s => s.lifecycle_state === 'LIVE').length;
  const paperCount = strategies.filter(s => s.lifecycle_state === 'PAPER').length;
  const signals24h = signals.length;

  return (
    <>
      <div className="page-header">
        <h1 className="page-title">Overview</h1>
        <Link to="/strategies/create" className="btn btn-primary">+ New Strategy</Link>
      </div>

      <div className="stat-grid">
        <div className="stat-card">
          <div className="stat-label">Total Strategies</div>
          <div className="stat-value">{strategies.length}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Live</div>
          <div className="stat-value" style={{ color: 'var(--primary)' }}>{liveCount}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Paper</div>
          <div className="stat-value" style={{ color: 'var(--success)' }}>{paperCount}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Recent Signals</div>
          <div className="stat-value">{signals24h}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">System Health</div>
          <div className="stat-value" style={{ color: health?.status === 'healthy' ? 'var(--success)' : 'var(--warning)' }}>
            {health?.status || '—'}
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-title">Active Strategies</div>
        {strategies.length === 0 ? <EmptyState title="No strategies yet" hint="Create one to get started" /> : (
          <table>
            <thead>
              <tr><th>Name</th><th>Market</th><th>Mode</th><th>State</th><th>Updated</th></tr>
            </thead>
            <tbody>
              {strategies.slice(0, 5).map(s => (
                <tr key={s.id}>
                  <td><Link to={`/strategies/${s.id}`}>{s.name}</Link></td>
                  <td>{s.market}</td>
                  <td>{s.execution_mode}</td>
                  <td><StateBadge state={s.lifecycle_state} /></td>
                  <td style={{ color: 'var(--muted)', fontSize: 12 }}>{new Date(s.updated_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="card">
        <div className="card-title">Recent Signals</div>
        {signals.length === 0 ? <EmptyState title="No signals yet" /> : (
          <table>
            <thead>
              <tr><th>Symbol</th><th>Side</th><th>Confidence</th><th>Strategy</th><th>When</th></tr>
            </thead>
            <tbody>
              {signals.map(s => (
                <tr key={s.id}>
                  <td><strong>{s.symbol}</strong></td>
                  <td><SideBadge side={s.side} /></td>
                  <td>{(s.confidence * 100).toFixed(0)}%</td>
                  <td>{s.strategy_name}</td>
                  <td style={{ color: 'var(--muted)', fontSize: 12 }}>{new Date(s.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}
