import { useState, useEffect } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { getProperty } from '../api/client';
import { StarIcon, CheckIcon, ArrowRightIcon, SparklesIcon } from '../components/Icons';

export default function PropertyPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [property, setProperty] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    getProperty(id)
      .then(data => {
        setProperty(data);
        setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });
  }, [id]);

  if (loading) {
    return <div className="page"><div className="loading-container"><div className="spinner" /></div></div>;
  }

  if (error || !property) {
    return (
      <div className="page">
        <div className="container" style={{ textAlign: 'center', paddingTop: '4rem' }}>
          <h2>Property Not Found</h2>
          <p style={{ color: 'var(--text-muted)' }}>{error}</p>
          <Link to="/" className="btn btn-secondary" style={{ marginTop: '1rem' }}>Back to Listings</Link>
        </div>
      </div>
    );
  }

  return (
    <div className="page" style={{ paddingTop: '80px', paddingBottom: '4rem', backgroundColor: '#fff' }}>
      <div className="container">
        <h1 style={{ fontSize: '2rem', fontWeight: 600, marginBottom: '0.5rem', color: '#222' }}>{property.title}</h1>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', color: '#222', marginBottom: '1.5rem', fontWeight: 500 }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <StarIcon size={16} color="#f59e0b" /> {property.rating} <span style={{ textDecoration: 'underline', color: '#666' }}>({property.review_count} reviews)</span>
          </span>
          <span>·</span>
          <span style={{ textDecoration: 'underline' }}>{property.location}</span>
        </div>

        {/* Property Hero Image */}
        <div style={{ 
          width: '100%', 
          height: '50vh',
          minHeight: '400px',
          backgroundImage: `url(${property.images?.[0] || '/placeholder.jpg'})`,
          backgroundSize: 'cover',
          backgroundPosition: 'center',
          borderRadius: '16px',
          marginBottom: '3rem'
        }} />

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '4rem' }}>
          
          <div style={{ flex: '1 1 500px' }}>
            <h2 style={{ fontSize: '1.5rem', fontWeight: 600, marginBottom: '0.5rem' }}>
              {property.property_type.charAt(0).toUpperCase() + property.property_type.slice(1)} hosted by AI
            </h2>
            <p style={{ fontSize: '1rem', color: '#222', paddingBottom: '2rem', borderBottom: '1px solid #eaeaea' }}>
              {property.bedrooms} bedrooms · {property.beds} beds · {property.bathrooms} baths
            </p>
            
            <div style={{ paddingTop: '2rem', paddingBottom: '2rem', borderBottom: '1px solid #eaeaea' }}>
              <h3 style={{ fontSize: '1.25rem', fontWeight: 600, marginBottom: '1rem' }}>About this space</h3>
              <p style={{ fontSize: '1rem', color: '#222', lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>
                {property.description}
              </p>
            </div>

            <div style={{ paddingTop: '2rem' }}>
              <h3 style={{ fontSize: '1.25rem', fontWeight: 600, marginBottom: '1.5rem' }}>What this place offers</h3>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '1rem' }}>
                {property.amenities?.map(amenity => (
                  <div key={amenity} style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', fontSize: '1rem', color: '#222' }}>
                    <CheckIcon size={18} color="var(--success)" /> {amenity}
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div style={{ width: '360px', flexShrink: 0, position: 'sticky', top: '100px' }}>
            <div className="card" style={{ padding: '1.5rem', border: '1px solid #dddddd', borderRadius: '12px', boxShadow: '0 6px 16px rgba(0,0,0,0.12)' }}>
              <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.5rem', marginBottom: '1.5rem' }}>
                <span style={{ fontSize: '1.5rem', fontWeight: 600, color: '#222' }}>₹{property.base_price.toLocaleString('en-IN')}</span>
                <span style={{ fontSize: '1rem', color: '#222' }}>night</span>
              </div>
              
              <div style={{ border: '1px solid #b0b0b0', borderRadius: '8px', marginBottom: '1.5rem', padding: '1rem', display: 'flex', alignItems: 'flex-start', gap: '0.75rem' }}>
                <SparklesIcon size={20} color="var(--accent-primary)" style={{ marginTop: '1px', flexShrink: 0 }} />
                <div>
                  <p style={{ margin: 0, fontSize: '0.85rem', fontWeight: 600, textTransform: 'uppercase', color: '#222', marginBottom: '0.25rem', letterSpacing: '0.02em' }}>AI Host Online</p>
                  <p style={{ margin: 0, fontSize: '0.85rem', color: '#666', lineHeight: 1.4 }}>
                    This host uses an AI agent to negotiate dates, prices, and terms.
                  </p>
                </div>
              </div>

              <button 
                className="btn btn-primary btn-lg" 
                style={{ width: '100%', background: 'linear-gradient(90deg, #e11d48, #f43f5e)', border: 'none', color: '#fff', fontSize: '1.05rem', fontWeight: 600, padding: '1rem', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem' }}
                onClick={() => navigate(`/property/${property.id}/negotiate`)}
              >
                Start Negotiation <ArrowRightIcon size={18} />
              </button>
              
              <p style={{ textAlign: 'center', fontSize: '0.85rem', color: '#666', marginTop: '1rem' }}>
                You won't be charged yet
              </p>
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}
