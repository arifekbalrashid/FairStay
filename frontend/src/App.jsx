import { useEffect, useState } from 'react';
import { Routes, Route, Link, Navigate } from 'react-router-dom';
import { useAuth } from './context/AuthContext';
import { getHealth } from './api/client';
import { ScaleIcon, LogOutIcon } from './components/Icons';
import HomePage from './pages/HomePage';
import PropertyPage from './pages/PropertyPage';
import TenantSetup from './pages/TenantSetup';
import Dashboard from './pages/Dashboard';
import HostDashboard from './pages/HostDashboard';
import LoginPage from './pages/LoginPage';
import CreatePropertyPage from './pages/CreatePropertyPage';

function Navbar({ health }) {
  const { user, logout } = useAuth();
  const getStatus = () => {
    if (!health) return { class: 'offline', text: 'Connecting...' };
    if (health.providers?.fallback_mode) return { class: 'fallback', text: 'Demo Mode (no API key)' };
    const providers = health.providers?.available_providers || [];
    return { class: '', text: providers.join(', ') || 'Ready' };
  };

  const status = getStatus();

  return (
    <nav className="navbar">
      <div style={{ display: 'flex', alignItems: 'center', gap: '2rem' }}>
        <Link to="/" className="navbar-brand" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <ScaleIcon size={22} color="#e11d48" />
          FairStay
        </Link>
        {user?.role === 'host' && (
          <Link to="/host/dashboard" style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-secondary)' }}>Host Dashboard</Link>
        )}
      </div>
      <div className="navbar-status" style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
        {user && (
          <>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
              Logged in as <strong style={{ color: 'var(--text-primary)' }}>{user.role === 'host' ? 'Host' : 'Guest'}</strong>
            </span>
            <button
              onClick={logout}
              style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.85rem', fontWeight: 500, padding: '0.3rem 0.5rem', borderRadius: '6px', transition: 'color 0.2s' }}
              onMouseOver={e => e.currentTarget.style.color = 'var(--error)'}
              onMouseOut={e => e.currentTarget.style.color = 'var(--text-muted)'}
            >
              <LogOutIcon size={15} />
              Logout
            </button>
            <span style={{ borderLeft: '1px solid var(--border)', height: '20px' }}></span>
          </>
        )}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span className={`status-dot ${status.class}`} />
          <span>{status.text}</span>
        </div>
      </div>
    </nav>
  );
}

export default function App() {
  const [health, setHealth] = useState(null);
  const { user } = useAuth();

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch(() => setHealth(null));
  }, []);

  // Protected Route Wrapper
  const RequireAuth = ({ children, role }) => {
    if (!user) return <Navigate to="/login" replace />;
    if (role && user.role !== role) {
      return <Navigate to={user.role === 'host' ? "/host/dashboard" : "/"} replace />;
    }
    return children;
  };

  return (
    <>
      {user && <Navbar health={health} />}
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        
        {/* Guest Routes */}
        <Route path="/" element={<RequireAuth role="guest"><HomePage /></RequireAuth>} />
        <Route path="/property/:id" element={<RequireAuth role="guest"><PropertyPage /></RequireAuth>} />
        <Route path="/property/:id/negotiate" element={<RequireAuth role="guest"><TenantSetup /></RequireAuth>} />
        <Route path="/tenant/:id" element={<RequireAuth role="guest"><Dashboard party="tenant" /></RequireAuth>} />
        
        {/* Host Routes */}
        <Route path="/host/dashboard" element={<RequireAuth role="host"><HostDashboard /></RequireAuth>} />
        <Route path="/host/create" element={<RequireAuth role="host"><CreatePropertyPage /></RequireAuth>} />
        <Route path="/host/:id" element={<RequireAuth role="host"><Dashboard party="host" /></RequireAuth>} />
        
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  );
}
