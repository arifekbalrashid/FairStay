import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { getProperties } from '../api/client';
import { StarIcon, SparklesIcon } from '../components/Icons';

export default function HomePage() {
  const [properties, setProperties] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getProperties()
      .then(data => {
        setProperties(data);
        setLoading(false);
      })
      .catch(err => {
        console.error(err);
        setLoading(false);
      });
  }, []);

  return (
    <div className="page" style={{ backgroundColor: '#f7f7f7', minHeight: '100vh' }}>
      <div className="hero" style={{ padding: '6rem 2rem', backgroundColor: '#fff', borderBottom: '1px solid #eaeaea', textAlign: 'center' }}>
        <div className="hero-badge" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', padding: '0.5rem 1rem', background: '#ffe4e6', color: '#e11d48', borderRadius: '20px', fontWeight: 'bold', marginBottom: '1.5rem' }}>
          <SparklesIcon size={16} color="#e11d48" /> FairStay Marketplace
        </div>
        <h1 style={{ fontSize: '3.5rem', fontWeight: 800, color: '#111', marginBottom: '1.5rem', letterSpacing: '-0.02em' }}>
          Find your next getaway.<br />
          <span style={{ background: 'linear-gradient(90deg, #e11d48, #f43f5e)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
            Let AI negotiate the price.
          </span>
        </h1>
        <p className="hero-subtitle" style={{ fontSize: '1.25rem', color: '#666', maxWidth: '600px', margin: '0 auto', lineHeight: 1.6 }}>
          Browse premium listings. Submit your terms. Our AI agents will negotiate 
          with the host's AI on your behalf to find a fair deal.
        </p>
      </div>

      <div className="container" style={{ marginTop: '4rem', paddingBottom: '4rem' }}>
        <h2 style={{ marginBottom: '2rem', fontSize: '2rem', fontWeight: 700, color: '#222' }}>Recommended Stays</h2>
        
        {loading ? (
          <div className="loading-container">
            <div className="spinner" />
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: '2.5rem' }}>
            {properties.map(p => (
              <Link to={`/property/${p.id}`} key={p.id} style={{ textDecoration: 'none', color: 'inherit' }}>
                <div className="card property-card" style={{ padding: 0, overflow: 'hidden', display: 'flex', flexDirection: 'column', borderRadius: '16px', border: 'none', boxShadow: '0 10px 25px rgba(0,0,0,0.05)', transition: 'transform 0.2s ease, box-shadow 0.2s ease', cursor: 'pointer' }}>
                  <div style={{ position: 'relative' }}>
                    <img src={p.images?.[0] || '/placeholder.jpg'} alt={p.title} style={{ width: '100%', height: '240px', objectFit: 'cover' }} />
                    <div style={{ position: 'absolute', top: '16px', right: '16px', background: 'rgba(255,255,255,0.95)', padding: '6px 12px', borderRadius: '20px', fontSize: '0.85rem', fontWeight: 'bold', color: '#111', boxShadow: '0 2px 10px rgba(0,0,0,0.1)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <StarIcon size={14} color="#f59e0b" /> {p.rating} ({p.review_count})
                    </div>
                  </div>
                  <div style={{ padding: '1.5rem', flex: 1, display: 'flex', flexDirection: 'column', background: '#fff' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.5rem' }}>
                      <h3 style={{ margin: 0, fontSize: '1.2rem', fontWeight: 600, color: '#222', lineHeight: 1.3 }}>{p.location}</h3>
                    </div>
                    <p style={{ margin: '0 0 0.5rem', fontSize: '1rem', color: '#666' }}>{p.title}</p>
                    <p style={{ margin: '0 0 1rem', fontSize: '0.9rem', color: '#888' }}>{p.property_type.charAt(0).toUpperCase() + p.property_type.slice(1)} · {p.bedrooms} beds</p>
                    <div style={{ marginTop: 'auto', paddingTop: '1rem', borderTop: '1px solid #f0f0f0' }}>
                      <span style={{ fontSize: '1.25rem', fontWeight: 700, color: '#111' }}>₹{p.base_price.toLocaleString('en-IN')}</span>
                      <span style={{ color: '#666', fontSize: '0.95rem' }}> / night</span>
                    </div>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
