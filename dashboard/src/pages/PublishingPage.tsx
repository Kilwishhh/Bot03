import { useEffect, useState } from 'react';
import { api, PublishingConfig, Publication } from '../lib/api';
import { ErrorBanner, SuccessBanner } from '../components/UI';

export default function PublishingPage() {
  const [config, setConfig] = useState<PublishingConfig | null>(null);
  const [pubs, setPubs] = useState<Publication[]>([]);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);

  const load = () => Promise.all([api.getPublishingConfig(), api.listPublications(50)])
    .then(([c, p]) => { setConfig(c); setPubs(p); })
    .catch(e => setError(e.message));
  useEffect(() => { load(); }, []);

  const onSave = async () => {
    if (!config) return;
    setError(''); setSaved(false);
    try {
      const c = await api.updatePublishingConfig(config);
      setConfig(c); setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e) { setError(String(e)); }
  };

  if (!config) return <div style={{ color: 'var(--muted)' }}>Loading…</div>;

  return (
    <>
      <div className="page-header"><h1 className="page-title">Publishing</h1></div>
      {error && <ErrorBanner>{error}</ErrorBanner>}
      {saved && <SuccessBanner>Settings saved</SuccessBanner>}

      <div className="card">
        <div className="card-title">Channels</div>
        <div className="form-row">
          <div className="form-group">
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--text)' }}>
              <input type="checkbox" checked={config.telegram_enabled} onChange={e => setConfig({ ...config, telegram_enabled: e.target.checked })} />
              Telegram enabled
            </label>
          </div>
          <div className="form-group">
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, color: 'var(--text)' }}>
              <input type="checkbox" checked={config.square_enabled} onChange={e => setConfig({ ...config, square_enabled: e.target.checked })} />
              Binance Square enabled
            </label>
          </div>
        </div>
        <div className="form-row">
          <div className="form-group">
            <label className="form-label">Square daily limit (3 posts/day max)</label>
            <input
              className="form-input"
              type="number"
              min={0}
              max={3}
              value={config.square_limit_daily}
              onChange={e => setConfig({ ...config, square_limit_daily: parseInt(e.target.value || '0', 10) })}
            />
          </div>
        </div>
        <button className="btn btn-primary" onClick={onSave}>Save settings</button>
      </div>

      <div className="card" style={{ padding: 0 }}>
        <div style={{ padding: '16px 20px' }}><div className="card-title">Recent Publications</div></div>
        <table>
          <thead>
            <tr><th>Channel</th><th>Signal</th><th>Template</th><th>Post ID</th><th>When</th></tr>
          </thead>
          <tbody>
            {pubs.length === 0 ? (
              <tr><td colSpan={5}><div className="empty-state">No publications yet</div></td></tr>
            ) : pubs.map(p => (
              <tr key={p.id}>
                <td><strong>{p.channel}</strong></td>
                <td style={{ fontSize: 12, color: 'var(--muted)' }}>{p.signal_id}</td>
                <td>{p.template}</td>
                <td style={{ fontSize: 12, color: 'var(--muted)' }}>{p.post_id || '—'}</td>
                <td style={{ fontSize: 12, color: 'var(--muted)' }}>{new Date(p.created_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
