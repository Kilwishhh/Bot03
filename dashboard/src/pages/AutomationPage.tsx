import { useEffect, useState } from 'react';
import { api, AutomationRule } from '../lib/api';
import { ErrorBanner } from '../components/UI';

const TRIGGERS = ['signal_generated', 'tp1_hit', 'tp2_hit', 'stopped_out', 'followup_created'];
const ACTION_TYPES = ['webhook', 'telegram', 'binance_square', 'create_followup'];

export default function AutomationPage() {
  const [rules, setRules] = useState<AutomationRule[]>([]);
  const [error, setError] = useState('');
  const [name, setName] = useState('');
  const [trigger, setTrigger] = useState(TRIGGERS[0]);
  const [action, setAction] = useState(ACTION_TYPES[0]);
  const [actionParams, setActionParams] = useState('{}');
  const [busy, setBusy] = useState(false);

  const load = () => { api.listAutomationRules().then(setRules).catch(e => setError(e.message)); };
  useEffect(() => { load(); }, []);

  const onAdd = async (e: React.FormEvent) => {
    e.preventDefault(); setError(''); setBusy(true);
    try {
      let params = {};
      try { params = JSON.parse(actionParams); } catch { throw new Error('Invalid JSON in params'); }
      await api.createAutomationRule({
        name, trigger,
        conditions: [],
        actions: [{ type: action, params }],
        enabled: true,
      } as any);
      setName(''); setActionParams('{}');
      load();
    } catch (e) { setError(String(e)); }
    finally { setBusy(false); }
  };

  const onToggle = async (rule: AutomationRule) => {
    try {
      await api.updateAutomationRule(rule.id, { enabled: !rule.enabled });
      load();
    } catch (e) { setError(String(e)); }
  };

  const onDelete = async (id: string) => {
    if (!confirm('Delete rule?')) return;
    try { await api.deleteAutomationRule(id); load(); }
    catch (e) { setError(String(e)); }
  };

  return (
    <>
      <div className="page-header"><h1 className="page-title">Automation</h1></div>
      {error && <ErrorBanner>{error}</ErrorBanner>}
      <form className="card" onSubmit={onAdd}>
        <div className="card-title">New Rule</div>
        <div className="form-row">
          <div className="form-group">
            <label className="form-label">Name</label>
            <input className="form-input" value={name} onChange={e => setName(e.target.value)} required />
          </div>
          <div className="form-group">
            <label className="form-label">Trigger</label>
            <select className="form-select" value={trigger} onChange={e => setTrigger(e.target.value)}>
              {TRIGGERS.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
        </div>
        <div className="form-row">
          <div className="form-group">
            <label className="form-label">Action</label>
            <select className="form-select" value={action} onChange={e => setAction(e.target.value)}>
              {ACTION_TYPES.map(a => <option key={a} value={a}>{a}</option>)}
            </select>
          </div>
          <div className="form-group">
            <label className="form-label">Action params (JSON)</label>
            <input className="form-input" value={actionParams} onChange={e => setActionParams(e.target.value)} placeholder='{"chat_id": "@channel"}' />
          </div>
        </div>
        <button className="btn btn-primary" type="submit" disabled={busy}>{busy ? 'Adding…' : '+ Add Rule'}</button>
      </form>

      <div className="card" style={{ padding: 0 }}>
        <table>
          <thead>
            <tr><th>Name</th><th>Trigger</th><th>Actions</th><th>Enabled</th><th></th></tr>
          </thead>
          <tbody>
            {rules.length === 0 ? (
              <tr><td colSpan={5}><div className="empty-state">No automation rules</div></td></tr>
            ) : rules.map(r => (
              <tr key={r.id}>
                <td><strong>{r.name}</strong></td>
                <td>{r.trigger}</td>
                <td style={{ fontSize: 12 }}>{(r.actions || []).map(a => a.type).join(', ')}</td>
                <td>
                  <button className="btn btn-ghost btn-sm" onClick={() => onToggle(r)}>
                    {r.enabled ? 'ON' : 'OFF'}
                  </button>
                </td>
                <td><button className="btn btn-ghost btn-sm" onClick={() => onDelete(r.id)}>Delete</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
