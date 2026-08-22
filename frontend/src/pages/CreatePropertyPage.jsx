import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { createProperty } from '../api/client';
import { SparklesIcon } from '../components/Icons';

export default function CreatePropertyPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  
  // Basic property info
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [location, setLocation] = useState('');
  const [price, setPrice] = useState('3000');
  
  // AI Config
  const [minPrice, setMinPrice] = useState('2500');
  const [cancellation, setCancellation] = useState('strict');
  const [privateInfo, setPrivateInfo] = useState('I want responsible guests. No parties. Price is somewhat flexible if they stay longer.');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    
    const payload = {
      host_id: user.id,
      title,
      description,
      location,
      property_type: 'apartment',
      bedrooms: 1,
      beds: 1,
      bathrooms: 1,
      base_price: parseFloat(price),
      currency: 'INR',
      cleaning_fee: 500,
      deposit: 2000,
      minimum_stay: 1,
      maximum_stay: 30,
      images: ['https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?auto=format&fit=crop&q=80&w=800'],
      amenities: ['wifi', 'kitchen'],
      negotiation_config: {
        private_information: privateInfo,
        negotiation_style: 'moderate',
        hard_constraints: {
          min_nightly_price: parseFloat(minPrice),
          min_stay_nights: 1
        },
        soft_preferences: {
          cancellation_policy: cancellation
        },
        ideal_values: {
          nightly_price: parseFloat(price),
          cleaning_fee: 500,
          deposit: 2000,
          cancellation_policy: cancellation,
          stay_nights: 5
        },
        acceptable_values: {
          nightly_price: parseFloat(minPrice),
          cleaning_fee: 0,
          deposit: 1000,
          cancellation_policy: cancellation === 'strict' ? 'moderate' : 'flexible',
          stay_nights: 2
        },
        priorities: ['nightly_price', 'cancellation_policy']
      }
    };
    
    try {
      await createProperty(payload);
      navigate('/host/dashboard');
    } catch (err) {
      console.error(err);
      alert('Failed to create property');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page" style={{ paddingTop: '80px', backgroundColor: '#f7f7f7', minHeight: '100vh' }}>
      <div className="container" style={{ maxWidth: '800px' }}>
        <h1 style={{ marginBottom: '2rem', fontSize: '2rem' }}>List New Property & AI Config</h1>
        
        <form className="card" onSubmit={handleSubmit} style={{ padding: '2rem', display: 'flex', flexDirection: 'column', gap: '2rem' }}>
          
          <section>
            <h2 style={{ fontSize: '1.4rem', borderBottom: '1px solid var(--border)', paddingBottom: '0.5rem', marginBottom: '1rem' }}>Property Details</h2>
            <div style={{ display: 'grid', gap: '1rem' }}>
              <div>
                <label style={{ display: 'block', fontWeight: 600, marginBottom: '0.5rem' }}>Title</label>
                <input required type="text" className="input" value={title} onChange={e => setTitle(e.target.value)} placeholder="e.g. Sunny Loft in Downtown" />
              </div>
              
              <div>
                <label style={{ display: 'block', fontWeight: 600, marginBottom: '0.5rem' }}>Location</label>
                <input required type="text" className="input" value={location} onChange={e => setLocation(e.target.value)} placeholder="e.g. New York, NY" />
              </div>

              <div>
                <label style={{ display: 'block', fontWeight: 600, marginBottom: '0.5rem' }}>Description</label>
                <textarea required className="input" rows={3} value={description} onChange={e => setDescription(e.target.value)} placeholder="Describe your property..." />
              </div>
              
              <div>
                <label style={{ display: 'block', fontWeight: 600, marginBottom: '0.5rem' }}>Listed Price (per night)</label>
                <input required type="number" className="input" value={price} onChange={e => setPrice(e.target.value)} />
              </div>
            </div>
          </section>

          <section>
            <h2 style={{ fontSize: '1.4rem', borderBottom: '1px solid var(--border)', paddingBottom: '0.5rem', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <SparklesIcon size={20} color="var(--accent-primary)" /> Host AI Constraints
            </h2>
            <p style={{ color: 'var(--text-secondary)', marginBottom: '1rem' }}>This information is kept strictly private. Your AI agent will use this to negotiate with guests on your behalf.</p>
            
            <div style={{ display: 'grid', gap: '1rem' }}>
              <div>
                <label style={{ display: 'block', fontWeight: 600, marginBottom: '0.5rem' }}>Absolute Minimum Price (per night)</label>
                <input required type="number" className="input" value={minPrice} onChange={e => setMinPrice(e.target.value)} placeholder="The lowest you'll accept" />
                <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>The AI will never agree to a price lower than this.</p>
              </div>

              <div>
                <label style={{ display: 'block', fontWeight: 600, marginBottom: '0.5rem' }}>Preferred Cancellation Policy</label>
                <select className="input" value={cancellation} onChange={e => setCancellation(e.target.value)}>
                  <option value="strict">Strict</option>
                  <option value="moderate">Moderate</option>
                  <option value="flexible">Flexible</option>
                </select>
              </div>

              <div>
                <label style={{ display: 'block', fontWeight: 600, marginBottom: '0.5rem' }}>Private Instructions for AI</label>
                <textarea className="input" rows={4} value={privateInfo} onChange={e => setPrivateInfo(e.target.value)} placeholder="e.g. I prefer guests who stay longer than 3 days, and I'm willing to give a 10% discount for week-long stays." />
              </div>
            </div>
          </section>
          
          <button type="submit" className="btn btn-primary" disabled={loading} style={{ padding: '1rem', fontSize: '1.1rem', marginTop: '1rem', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem' }}>
            {loading ? (
              <>
                <div className="spinner" style={{ width: '18px', height: '18px', borderWidth: '2px' }} />
                Creating...
              </>
            ) : (
              <>
                <SparklesIcon size={18} /> Create Property & Activate AI
              </>
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
