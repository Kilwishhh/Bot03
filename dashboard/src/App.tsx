import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import AppShell from './components/AppShell';
import LoginPage from './pages/LoginPage';
import OverviewPage from './pages/OverviewPage';
import StrategiesPage from './pages/StrategiesPage';
import StrategyCreatePage from './pages/StrategyCreatePage';
import StrategyDetailPage from './pages/StrategyDetailPage';
import SignalsPage from './pages/SignalsPage';
import AutomationPage from './pages/AutomationPage';
import ConnectionsPage from './pages/ConnectionsPage';
import PublishingPage from './pages/PublishingPage';
import SettingsPage from './pages/SettingsPage';

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="app-shell" style={{ alignItems: 'center', justifyContent: 'center' }}><span style={{ color: 'var(--muted)' }}>Loading…</span></div>;
  return user ? <>{children}</> : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/*"
            element={
              <ProtectedRoute>
                <AppShell>
                  <Routes>
                    <Route path="/" element={<OverviewPage />} />
                    <Route path="/strategies" element={<StrategiesPage />} />
                    <Route path="/strategies/create" element={<StrategyCreatePage />} />
                    <Route path="/strategies/:id" element={<StrategyDetailPage />} />
                    <Route path="/signals" element={<SignalsPage />} />
                    <Route path="/automation" element={<AutomationPage />} />
                    <Route path="/connections" element={<ConnectionsPage />} />
                    <Route path="/publishing" element={<PublishingPage />} />
                    <Route path="/settings" element={<SettingsPage />} />
                  </Routes>
                </AppShell>
              </ProtectedRoute>
            }
          />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
