import { useAuth } from '../context/AuthContext';

export default function SettingsPage() {
  const { user } = useAuth();
  if (!user) return null;

  return (
    <>
      <div className="page-header"><h1 className="page-title">Settings</h1></div>
      <div className="card">
        <div className="card-title">Profile</div>
        <div className="form-row">
          <div className="form-group">
            <label className="form-label">Email</label>
            <input className="form-input" value={user.email} disabled />
          </div>
          <div className="form-group">
            <label className="form-label">Display name</label>
            <input className="form-input" value={user.display_name} disabled />
          </div>
        </div>
        <div className="form-row">
          <div className="form-group">
            <label className="form-label">Role</label>
            <input className="form-input" value={user.role} disabled />
          </div>
          <div className="form-group">
            <label className="form-label">Status</label>
            <input className="form-input" value={user.status} disabled />
          </div>
        </div>
      </div>
    </>
  );
}
