import { NavLink, Outlet } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function AppShell({ children }: { children?: React.ReactNode }) {
  const { user, logout } = useAuth();

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-logo">MK Trader</div>
        <nav className="sidebar-nav">
          <NavLink to="/" end className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}>
            <span>◈</span> Overview
          </NavLink>
          <div className="nav-section">Trading</div>
          <NavLink to="/strategies" className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}>
            <span>◎</span> Strategies
          </NavLink>
          <NavLink to="/signals" className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}>
            <span>◉</span> Signals
          </NavLink>
          <NavLink to="/connections" className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}>
            <span>⬡</span> Connections
          </NavLink>
          <div className="nav-section">Automation</div>
          <NavLink to="/automation" className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}>
            <span>⟳</span> Automation
          </NavLink>
          <NavLink to="/publishing" className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}>
            <span>✈</span> Publishing
          </NavLink>
          <div className="nav-section">Account</div>
          <NavLink to="/settings" className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}>
            <span>⚙</span> Settings
          </NavLink>
        </nav>
        {user && (
          <div style={{ padding: '12px 16px', borderTop: '1px solid var(--border)', fontSize: '12px' }}>
            <div style={{ color: 'var(--text)', fontWeight: 600 }}>{user.display_name}</div>
            <div style={{ color: 'var(--muted)', fontSize: '11px' }}>{user.email}</div>
            <button className="btn btn-ghost btn-sm" style={{ marginTop: '8px', width: '100%' }} onClick={logout}>
              Sign out
            </button>
          </div>
        )}
      </aside>
      <main className="main-content">
        {children || <Outlet />}
      </main>
    </div>
  );
}
