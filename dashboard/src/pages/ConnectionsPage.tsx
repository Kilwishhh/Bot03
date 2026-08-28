import { useEffect, useState } from 'react';
import { api, Connection } from '../lib/api';
import { ErrorBanner } from '../components/UI';

export default function ConnectionsPage() {
  const [conns, setConns] = useState<Connection[]>([]);
  const [error, setError] = useState('');
  const [venue, setVenue] = useState('binance');
  const [label, setLabel] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [apiSecret, setApiSecret] = useState('');
  const [testnet, setTestnet] = useState(true);
  const [busy, setBusy] = useState(false);

  const load = () => { api.listConnections().then(setConns).catch(e => setError(e.message)); };
  useEffect(() => { load(); }, []);

  const onAdd = async (e: React.FormEvent) => {
    e.preventDefault(); setError(''); setBusy(true);
    try {
      await api.createConnection({ venue, label, api_key: apiKey, api_secret: apiSecret, testnet } as any);
      setLabel(''); setApiKey(''); setApiSecret('');
      load();
    } catch (e) { setError(String(e)); }
    finally { setBusy(false); }
  };

  const onTest = async (id: string) => {
    try {
      const r = await api.testConnection(id);
      alert(r.message || (r.success ? 'Connection OK' : 'Connection failed'));
    } catch (e) { setError(String(e)); }
  };

  const onDelete = async (id: string) => {
    if (!confirm('Delete this connection?')) return;
    try { await api.deleteConnection(id); load(); }
    catch (e) { setError(String(e)); }
  };

  return (
    <>
      <div className="page-header"><h1 className="page-title">Exchange Connections</h1></div>
      {error && <ErrorBanner>{error}</ErrorBanner>}
      <form className="card" onSubmit={onAdd}>
        <div className="card-title">Add Connection</div>
        <div className="form-row">
          <div className="form-group">
            <label className="form-label">Venue</label>
            <select className="form-select" value={venue} onChange={e => setVenue(e.target.value)}>
              {['binance', 'bybit', 'kraken', 'coinbase'].map(v => <option key={v}>{v}</option>)}
            </select>
          </div>
          <div className="form-group">
            <label className="form-label">Label</label>
            <input className="form-input" value={label} onChange={e => setLabel(e.target.value)} placeholder="My Binance Spot" required />
          </div>
        </div>
        <div className="form-row">
          <div className="form-group">
            <label className="form-label">API Key</label>
            <input className="form-input" value={apiKey} onChange={e => setApiKey(e.target.value)} required />
          </div>
          <div className="form-group">
            <label className="form-label">API Secret</label>
            <input className="form-input" type="password" value={apiSecret} onChange={e => setApiSecret(e.target.value)} required />
          </div>
        </div>
        <div className="form-group">
          <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, color: 'var(--text)' }}>
            <input type="checkbox" checked={testnet} onChange={e => setTestnet(e.target.checked)} />
            Testnet (paper / demo endpoint)
          </label>
        </div>
        <button className="btn btn-primary" type="submit" disabled={busy}>{busy ? 'Saving…' : '+ Add'}</button>
      </form>

      <div className="card" style={{ padding: 0 }}>
        <table>
          <thead>
            <tr><th>Label</th><th>Venue</th><th>Status</th><th>Created</th><th></th></tr>
          </thead>
          <tbody>
            {conns.length === 0 ? (
              <tr><td colSpan={5}><div className="empty-state">No connections yet</div></td></tr>
            ) : conns.map(c => (
              <tr key={c.id}>
                <td><strong>{c.label}</strong></td>
                <td>{c.venue}</td>
                <td>{c.status}</td>
                <td style={{ color: 'var(--muted)', fontSize: 12 }}>{new Date(c.created_at).toLocaleString()}</td>
                <td style={{ display: 'flex', gap: 6 }}>
                  <button className="btn btn-ghost btn-sm" onClick={() => onTest(c.id)}>Test</button>
                  <button className="btn btn-ghost btn-sm" onClick={() => onDelete(c.id)}>Delete</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
