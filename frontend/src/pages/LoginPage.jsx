import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { ScaleIcon, BriefcaseIcon, BuildingIcon, ArrowRightIcon, SparklesIcon } from '../components/Icons';

export default function LoginPage() {
  const { loginAsHost, loginAsGuest } = useAuth();
  const navigate = useNavigate();

  const handleHostLogin = () => {
    loginAsHost();
    navigate('/host/dashboard');
  };

  const handleGuestLogin = () => {
    loginAsGuest();
    navigate('/');
  };

  return (
    <div className="page" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh', background: 'linear-gradient(135deg, #f8fafc 0%, #eef2ff 100%)' }}>
      <div style={{ maxWidth: '520px', width: '100%', padding: '0 1.5rem' }}>
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: '2.5rem' }}>
          <div style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: '56px', height: '56px', background: 'var(--accent-gradient)', borderRadius: '14px', marginBottom: '1.25rem', boxShadow: '0 8px 24px rgba(225, 29, 72, 0.2)' }}>
            <ScaleIcon size={28} color="#fff" />
          </div>
          <h1 style={{ fontSize: '2rem', fontWeight: 800, color: 'var(--text-primary)', marginBottom: '0.5rem', letterSpacing: '-0.02em' }}>FairStay</h1>
          <p style={{ fontSize: '1rem', color: 'var(--text-secondary)', lineHeight: 1.6, maxWidth: '380px', margin: '0 auto' }}>
            AI-powered rental negotiations. Choose your role to get started.
          </p>
        </div>

        {/* Role Cards */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <button
            onClick={handleGuestLogin}
            style={{
              display: 'flex', alignItems: 'center', gap: '1.25rem', padding: '1.5rem',
              background: '#fff', border: '1px solid var(--border)', borderRadius: '14px',
              cursor: 'pointer', textAlign: 'left', transition: 'all 0.2s ease',
              boxShadow: 'var(--shadow-sm)',
            }}
            onMouseOver={e => { e.currentTarget.style.borderColor = 'var(--party-a)'; e.currentTarget.style.boxShadow = '0 4px 12px rgba(37, 99, 235, 0.1)'; }}
            onMouseOut={e => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.boxShadow = 'var(--shadow-sm)'; }}
          >
            <div style={{ width: '48px', height: '48px', borderRadius: '12px', background: 'var(--party-a-bg)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
              <BriefcaseIcon size={22} color="var(--party-a)" />
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: '1.05rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '0.2rem', fontFamily: 'inherit' }}>Continue as Guest</div>
              <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', fontFamily: 'inherit' }}>Browse properties and negotiate rental terms</div>
            </div>
            <ArrowRightIcon size={18} color="var(--text-muted)" />
          </button>

          <button
            onClick={handleHostLogin}
            style={{
              display: 'flex', alignItems: 'center', gap: '1.25rem', padding: '1.5rem',
              background: '#fff', border: '1px solid var(--border)', borderRadius: '14px',
              cursor: 'pointer', textAlign: 'left', transition: 'all 0.2s ease',
              boxShadow: 'var(--shadow-sm)',
            }}
            onMouseOver={e => { e.currentTarget.style.borderColor = 'var(--party-b)'; e.currentTarget.style.boxShadow = '0 4px 12px rgba(217, 119, 6, 0.1)'; }}
            onMouseOut={e => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.boxShadow = 'var(--shadow-sm)'; }}
          >
            <div style={{ width: '48px', height: '48px', borderRadius: '12px', background: 'var(--party-b-bg)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
              <BuildingIcon size={22} color="var(--party-b)" />
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: '1.05rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '0.2rem', fontFamily: 'inherit' }}>Continue as Host</div>
              <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', fontFamily: 'inherit' }}>List properties and manage AI negotiations</div>
            </div>
            <ArrowRightIcon size={18} color="var(--text-muted)" />
          </button>
        </div>

        {/* Footer note */}
        <p style={{ textAlign: 'center', fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '2rem', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.4rem' }}>
          <SparklesIcon size={14} /> Powered by multi-agent AI negotiation
        </p>
      </div>
    </div>
  );
}
