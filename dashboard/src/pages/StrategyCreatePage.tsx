import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../lib/api';
import { ErrorBanner } from '../components/UI';

export default function StrategyCreatePage() {
  const nav = useNavigate();
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [market, setMarket] = useState('BTCUSDT');
  const [timeframe, setTimeframe] = useState('15m');
  const [mode, setMode] = useState('paper');
  const [venue, setVenue] = useState('binance');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(''); setBusy(true);
    try {
      const s = await api.createStrategy({
        name, description, market, timeframe,
        execution_mode: mode, execution_venue: venue,
        entry_config: {}, exit_config: {}, risk_config: {},
      });
      nav(`/strategies/${s.id}`);
    } catch (e) { setError(String(e)); }
    finally { setBusy(false); }
  };

  return (
    <>
      <div className="page-header"><h1 className="page-title">New Strategy</h1></div>
      {error && <ErrorBanner>{error}</ErrorBanner>}
      <form className="card" onSubmit={onSubmit}>
        <div className="form-group">
          <label className="form-label">Name</label>
          <input className="form-input" value={name} onChange={e => setName(e.target.value)} required autoFocus placeholder="e.g. BTC 15m Scalp" />
        </div>
        <div className="form-group">
          <label className="form-label">Description</label>
          <textarea className="form-textarea" value={description} onChange={e => setDescription(e.target.value)} />
        </div>
        <div className="form-row">
          <div className="form-group">
            <label className="form-label">Market</label>
            <input className="form-input" value={market} onChange={e => setMarket(e.target.value.toUpperCase())} required />
          </div>
          <div className="form-group">
            <label className="form-label">Timeframe</label>
            <select className="form-select" value={timeframe} onChange={e => setTimeframe(e.target.value)}>
              {['1m', '5m', '15m', '1h', '4h', '1d'].map(t => <option key={t}>{t}</option>)}
            </select>
          </div>
        </div>
        <div className="form-row">
          <div className="form-group">
            <label className="form-label">Execution Mode</label>
            <select className="form-select" value={mode} onChange={e => setMode(e.target.value)}>
              <option value="paper">Paper</option>
              <option value="testnet">Testnet</option>
              <option value="live">Live (requires explicit approval)</option>
            </select>
          </div>
          <div className="form-group">
            <label className="form-label">Venue</label>
            <select className="form-select" value={venue} onChange={e => setVenue(e.target.value)}>
              <option value="binance">Binance</option>
              <option value="bybit">Bybit</option>
              <option value="kraken">Kraken</option>
              <option value="coinbase">Coinbase</option>
            </select>
          </div>
        </div>
        <button className="btn btn-primary" type="submit" disabled={busy}>{busy ? 'Creating…' : 'Create Strategy'}</button>
      </form>
    </>
  );
}
