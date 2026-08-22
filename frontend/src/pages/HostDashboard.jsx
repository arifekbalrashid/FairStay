import { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { getProperties, getPropertyNegotiations } from '../api/client';
import { PlusIcon, EyeIcon, ZapIcon, MapPinIcon, InboxIcon, XIcon, ArrowRightIcon } from '../components/Icons';

export default function HostDashboard() {
  const [properties, setProperties] = useState([]);
  const [loading, setLoading] = useState(true);
  
  // Modal State
  const [selectedProperty, setSelectedProperty] = useState(null);
  const [negotiations, setNegotiations] = useState([]);
  const [loadingDeals, setLoadingDeals] = useState(false);
  
  const { user } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    getProperties(user?.id)
      .then(data => {
        setProperties(data);
        setLoading(false);
      })
      .catch(err => {
        console.error(err);
        setLoading(false);
      });
  }, [user?.id]);

  const openDealsModal = async (property) => {
    setSelectedProperty(property);
    setLoadingDeals(true);
    try {
      const data = await getPropertyNegotiations(property.id);
      setNegotiations(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingDeals(false);
    }
  };

  const closeDealsModal = () => {
    setSelectedProperty(null);
    setNegotiations([]);
  };

  const getStatusBadge = (status) => {
    switch (status) {
      case 'in_progress':
        return <span style={{ ...badgeStyle, backgroundColor: '#eef2ff', color: '#4f46e5' }}>● In Progress</span>;
      case 'awaiting_approval':
        return <span style={{ ...badgeStyle, backgroundColor: '#fffbeb', color: '#d97706' }}>● Awaiting Approval</span>;
      case 'approved':
        return <span style={{ ...badgeStyle, backgroundColor: '#f0fdf4', color: '#16a34a' }}>● Approved</span>;
      case 'failed':
      case 'rejected':
        return <span style={{ ...badgeStyle, backgroundColor: '#fef2f2', color: '#dc2626' }}>● Failed</span>;
      default:
        return <span style={{ ...badgeStyle, backgroundColor: '#f3f4f6', color: '#4b5563' }}>● Pending</span>;
    }
  };

  if (loading) {
    return <div className="page"><div className="loading-container"><div className="spinner" /></div></div>;
  }

  return (
    <div className="page" style={{ paddingTop: '80px', backgroundColor: '#f4f7fa', minHeight: '100vh', paddingBottom: '4rem' }}>
      <div className="container">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '3rem' }}>
          <div>
            <h1 style={{ fontSize: '2.5rem', fontWeight: 800, margin: '0 0 0.5rem', color: '#111827' }}>Host Dashboard</h1>
            <p style={{ color: '#6b7280', margin: 0, fontSize: '1.1rem' }}>Manage your properties and AI negotiations in real-time.</p>
          </div>
          <Link to="/host/create" className="btn btn-primary" style={{ padding: '0.8rem 1.5rem', fontWeight: 600, borderRadius: '8px', boxShadow: '0 4px 6px -1px rgba(225, 29, 72, 0.2)', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <PlusIcon size={18} /> Create New Property
          </Link>
        </div>
        
        {properties.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '5rem 2rem', backgroundColor: 'white', borderRadius: '16px', boxShadow: '0 10px 15px -3px rgba(0,0,0,0.05)' }}>
            <h2 style={{ color: '#374151', marginBottom: '1rem', fontSize: '1.8rem' }}>No properties found</h2>
            <p style={{ marginBottom: '2rem', color: '#6b7280', fontSize: '1.1rem' }}>You haven't listed any properties yet. Click the button above to set up your first AI agent.</p>
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: '2rem' }}>
            {properties.map(p => (
              <div key={p.id} className="card property-card" style={{ 
                padding: 0, 
                display: 'flex', 
                flexDirection: 'column', 
                borderRadius: '16px', 
                overflow: 'hidden', 
                transition: 'transform 0.2s, box-shadow 0.2s',
                boxShadow: '0 10px 15px -3px rgba(0,0,0,0.05)',
                border: '1px solid #e5e7eb'
              }}>
                <div style={{ height: '200px', backgroundColor: '#e5e7eb', position: 'relative' }}>
                   {p.images && p.images.length > 0 ? (
                     <img src={p.images[0]} alt={p.title} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                   ) : (
                     <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#9ca3af' }}>No Image</div>
                   )}
                   <div style={{ position: 'absolute', top: '12px', right: '12px', backgroundColor: 'rgba(255,255,255,0.9)', padding: '4px 10px', borderRadius: '20px', fontSize: '0.8rem', fontWeight: 600, color: '#374151', backdropFilter: 'blur(4px)' }}>
                     {p.property_type.charAt(0).toUpperCase() + p.property_type.slice(1)}
                   </div>
                </div>
                
                <div style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', flex: 1 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.5rem' }}>
                    <h3 style={{ margin: 0, fontSize: '1.3rem', color: '#111827', fontWeight: 700, lineHeight: 1.3 }}>{p.title}</h3>
                  </div>
                  <p style={{ color: '#6b7280', fontSize: '0.95rem', marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <MapPinIcon size={14} color="#6b7280" /> {p.location}
                  </p>
                  
                  <div style={{ marginTop: 'auto', display: 'flex', gap: '0.8rem' }}>
                    <button className="btn" style={{ flex: 1, backgroundColor: '#f3f4f6', color: '#374151', border: '1px solid #e5e7eb', borderRadius: '8px', fontWeight: 600, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.3rem' }} onClick={() => navigate(`/property/${p.id}`)}>
                      <EyeIcon size={16} /> Preview
                    </button>
                    <button className="btn btn-primary" style={{ flex: 1.5, borderRadius: '8px', fontWeight: 600, boxShadow: '0 4px 6px -1px rgba(225, 29, 72, 0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.3rem' }} onClick={() => openDealsModal(p)}>
                      <ZapIcon size={16} /> Active Deals
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Interactive Deals Modal */}
      {selectedProperty && (
        <div style={modalOverlayStyle} onClick={closeDealsModal}>
          <div style={modalContentStyle} onClick={e => e.stopPropagation()}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid #e5e7eb', paddingBottom: '1rem', marginBottom: '1.5rem' }}>
              <div>
                <h2 style={{ margin: 0, fontSize: '1.5rem', color: '#111827' }}>Active Negotiations</h2>
                <p style={{ margin: '0.2rem 0 0', color: '#6b7280', fontSize: '0.95rem' }}>{selectedProperty.title}</p>
              </div>
              <button onClick={closeDealsModal} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#9ca3af', padding: '0.5rem', display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: '8px', transition: 'background 0.2s' }}
                onMouseOver={e => e.currentTarget.style.background = '#f3f4f6'}
                onMouseOut={e => e.currentTarget.style.background = 'none'}
              >
                <XIcon size={20} />
              </button>
            </div>

            {loadingDeals ? (
              <div style={{ textAlign: 'center', padding: '3rem' }}><div className="spinner" style={{ margin: '0 auto' }} /></div>
            ) : negotiations.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '3rem 1rem' }}>
                <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '1rem' }}>
                  <div style={{ width: '56px', height: '56px', borderRadius: '50%', background: '#f3f4f6', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                    <InboxIcon size={24} color="#9ca3af" />
                  </div>
                </div>
                <h3 style={{ margin: '0 0 0.5rem', color: '#374151' }}>No active deals</h3>
                <p style={{ color: '#6b7280', margin: 0 }}>There are currently no guests negotiating for this property.</p>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', maxHeight: '60vh', overflowY: 'auto', paddingRight: '0.5rem' }}>
                {negotiations.map(neg => (
                  <div key={neg.id} style={{ border: '1px solid #e5e7eb', borderRadius: '12px', padding: '1.2rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center', backgroundColor: '#f9fafb', transition: 'border-color 0.2s' }}>
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.8rem', marginBottom: '0.5rem' }}>
                        <strong style={{ fontSize: '1.1rem', color: '#111827' }}>{neg.guest_name}</strong>
                        {getStatusBadge(neg.status)}
                      </div>
                      <p style={{ margin: 0, color: '#6b7280', fontSize: '0.9rem' }}>
                        Round {neg.current_round} · Started {new Date(neg.created_at).toLocaleDateString()}
                      </p>
                    </div>
                    <button 
                      className="btn btn-primary" 
                      style={{ padding: '0.6rem 1.2rem', borderRadius: '8px', fontSize: '0.95rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.3rem' }}
                      onClick={() => navigate(`/host/${neg.id}`)}
                    >
                      Enter Room <ArrowRightIcon size={16} />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

const badgeStyle = {
  padding: '4px 10px',
  borderRadius: '20px',
  fontSize: '0.75rem',
  fontWeight: 700,
  letterSpacing: '0.025em',
  textTransform: 'uppercase',
};

const modalOverlayStyle = {
  position: 'fixed',
  top: 0,
  left: 0,
  right: 0,
  bottom: 0,
  backgroundColor: 'rgba(17, 24, 39, 0.6)',
  backdropFilter: 'blur(4px)',
  display: 'flex',
  justifyContent: 'center',
  alignItems: 'center',
  zIndex: 1000,
  padding: '1rem',
};

const modalContentStyle = {
  backgroundColor: 'white',
  borderRadius: '20px',
  padding: '2rem',
  width: '100%',
  maxWidth: '700px',
  maxHeight: '90vh',
  boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
  display: 'flex',
  flexDirection: 'column',
};
