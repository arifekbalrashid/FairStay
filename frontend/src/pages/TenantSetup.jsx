import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { getScenarioDefaults, getProperty, negotiateProperty } from '../api/client';
import { SettingsIcon, ChevronDownIcon, ChevronUpIcon, PlayIcon, ShieldIcon, TargetIcon, AlertCircleIcon } from '../components/Icons';

function TenantForm({ variables, values, onChange }) {
  const prefs = values || {};
  const [showAdvanced, setShowAdvanced] = useState(false);

  const updateField = (section, key, value) => {
    const updated = { ...prefs };
    if (!updated[section]) updated[section] = {};
    updated[section][key] = value;
    onChange(updated);
  };

  const updateTopLevel = (key, value) => {
    onChange({ ...prefs, [key]: value });
  };

  // Safe accessors for basic fields
  const idealPrice = prefs.ideal_values?.nightly_price ?? '';
  const maxPrice = prefs.hard_constraints?.max_nightly_price ?? '';
  const stayNights = prefs.ideal_values?.stay_nights ?? '';
  const privateInfo = prefs.private_information || '';
  const negStyle = prefs.negotiation_style || 'moderate';

  return (
    <div className="card party-config party-a" style={{ maxWidth: '600px', margin: '0 auto', padding: '2rem' }}>
      <div className="party-config-header" style={{ marginBottom: '1.5rem', textAlign: 'center' }}>
        <span className="badge badge-party-a" style={{ fontSize: '0.9rem', padding: '0.4rem 1rem' }}>Your Booking Request</span>
      </div>
      
      <p style={{ color: 'var(--text-secondary)', marginBottom: '2rem', fontSize: '0.95rem', textAlign: 'center' }}>
        Set your target budget and dates. Your AI agent will handle the haggling on your behalf to get the best deal possible without crossing your maximum budget.
      </p>

      {/* Basic Setup */}
      <div className="constraints-section" style={{ borderBottom: showAdvanced ? '1px solid var(--border)' : 'none', paddingBottom: showAdvanced ? '1.5rem' : '0' }}>
        <div style={{ display: 'grid', gap: '1.2rem' }}>
          <div className="form-group">
            <label className="form-label" style={{ fontWeight: 600 }}>Target Nightly Price</label>
            <input 
              className="form-input" 
              type="number" 
              value={idealPrice} 
              onChange={(e) => updateField('ideal_values', 'nightly_price', Number(e.target.value))}
              placeholder="e.g. 2000"
            />
            <small style={{ color: 'var(--text-muted)', display: 'block', marginTop: '4px' }}>The price you ideally want to pay.</small>
          </div>

          <div className="form-group">
            <label className="form-label" style={{ fontWeight: 600 }}>Absolute Maximum Price</label>
            <input 
              className="form-input" 
              type="number" 
              value={maxPrice} 
              onChange={(e) => {
                const val = e.target.value;
                if (val === '') { 
                  const u = {...prefs}; 
                  if(u.hard_constraints) delete u.hard_constraints.max_nightly_price; 
                  onChange(u); 
                } else {
                  updateField('hard_constraints', 'max_nightly_price', Number(val));
                }
              }}
              placeholder="e.g. 2500"
            />
            <small style={{ color: 'var(--text-muted)', display: 'block', marginTop: '4px' }}>The AI will walk away if the price goes above this limit.</small>
          </div>

          <div className="form-group">
            <label className="form-label" style={{ fontWeight: 600 }}>Length of Stay (Nights)</label>
            <input 
              className="form-input" 
              type="number" 
              value={stayNights} 
              onChange={(e) => updateField('ideal_values', 'stay_nights', Number(e.target.value))}
              placeholder="e.g. 5"
            />
          </div>

          <div className="form-group">
            <label className="form-label" style={{ fontWeight: 600 }}>Private Instructions</label>
            <textarea 
              className="form-input" 
              rows={3}
              value={privateInfo}
              onChange={(e) => updateTopLevel('private_information', e.target.value)}
              placeholder="e.g. I need parking. I'm a quiet professional..."
            />
          </div>
          
          <div className="form-group">
            <label className="form-label" style={{ fontWeight: 600 }}>Negotiation Style</label>
            <select className="form-input" value={negStyle} onChange={(e) => updateTopLevel('negotiation_style', e.target.value)}>
              <option value="aggressive">Aggressive (Haggles hard, risks deal falling through)</option>
              <option value="firm">Firm (Stands ground)</option>
              <option value="moderate">Moderate (Balanced approach)</option>
              <option value="flexible">Flexible (Willing to compromise easily)</option>
            </select>
          </div>
        </div>
      </div>

      {/* Advanced Toggle */}
      <button 
        type="button" 
        onClick={() => setShowAdvanced(!showAdvanced)}
        style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', fontWeight: 600, padding: '1rem 0', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.5rem', width: '100%', justifyContent: 'center', marginTop: '1rem', transition: 'color 0.2s', fontSize: '0.9rem' }}
        onMouseOver={e => e.currentTarget.style.color = 'var(--accent-primary)'}
        onMouseOut={e => e.currentTarget.style.color = 'var(--text-secondary)'}
      >
        <SettingsIcon size={16} />
        {showAdvanced ? 'Hide Advanced Settings' : 'Show Advanced Settings'}
        {showAdvanced ? <ChevronUpIcon size={16} /> : <ChevronDownIcon size={16} />}
      </button>

      {/* Advanced Setup (Progressive Disclosure) */}
      {showAdvanced && (
        <div style={{ marginTop: '1.5rem', borderTop: '1px solid var(--border)', paddingTop: '1.5rem' }}>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginBottom: '1.5rem', textAlign: 'center' }}>
            These granular constraints will be strictly followed by the AI during negotiation.
          </p>
          
          <div className="constraints-section">
            <h4 style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <TargetIcon size={14} /> Ideal Values (Best Case)
            </h4>
            {variables.filter(v => v.type !== 'boolean').map((v) => (
              <div className="form-group" key={`ideal-${v.name}`}>
                <label className="form-label">
                  {v.display_name} {v.unit && <span style={{ color: 'var(--text-muted)' }}>({v.unit})</span>}
                </label>
                <input
                  className="form-input"
                  type="number"
                  value={prefs.ideal_values?.[v.name] ?? ''}
                  onChange={(e) => updateField('ideal_values', v.name, Number(e.target.value))}
                  placeholder={v.description}
                />
              </div>
            ))}
            {variables.filter(v => v.type === 'boolean').map((v) => (
              <div className="form-group" key={`ideal-${v.name}`}>
                <label className="form-checkbox">
                  <input
                    type="checkbox"
                    checked={prefs.ideal_values?.[v.name] ?? false}
                    onChange={(e) => updateField('ideal_values', v.name, e.target.checked)}
                  />
                  {v.display_name}
                </label>
              </div>
            ))}
          </div>

          <div className="constraints-section">
            <h4 style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <AlertCircleIcon size={14} /> Acceptable Values (Worst Case)
            </h4>
            {variables.filter(v => v.type !== 'boolean').map((v) => (
              <div className="form-group" key={`accept-${v.name}`}>
                <label className="form-label">{v.display_name}</label>
                <input className="form-input" type="number"
                  value={prefs.acceptable_values?.[v.name] ?? ''}
                  onChange={(e) => updateField('acceptable_values', v.name, Number(e.target.value))}
                />
              </div>
            ))}
          </div>

          <div className="constraints-section">
            <h4 style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <ShieldIcon size={14} /> Hard Constraints (Never Violate)
            </h4>
            {variables.filter(v => v.type === 'number').map((v) => (
              <div className="constraint-row" key={`hard-${v.name}`}>
                <div className="form-group">
                  <label className="form-label">Min {v.display_name}</label>
                  <input className="form-input" type="number"
                    value={prefs.hard_constraints?.[`min_${v.name}`] ?? ''}
                    onChange={(e) => {
                      const val = e.target.value;
                      if (val === '') { const u = {...prefs}; if(u.hard_constraints) delete u.hard_constraints[`min_${v.name}`]; onChange(u); }
                      else updateField('hard_constraints', `min_${v.name}`, Number(val));
                    }}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Max {v.display_name}</label>
                  <input className="form-input" type="number"
                    value={prefs.hard_constraints?.[`max_${v.name}`] ?? ''}
                    onChange={(e) => {
                      const val = e.target.value;
                      if (val === '') { const u = {...prefs}; if(u.hard_constraints) delete u.hard_constraints[`max_${v.name}`]; onChange(u); }
                      else updateField('hard_constraints', `max_${v.name}`, Number(val));
                    }}
                  />
                </div>
              </div>
            ))}
          </div>

          <div className="constraints-section">
            <h4>Priorities (most important first)</h4>
            <div className="form-group">
              <input className="form-input"
                value={(prefs.priorities || []).join(', ')}
                onChange={(e) => updateTopLevel('priorities', e.target.value.split(',').map(s => s.trim()).filter(Boolean))}
                placeholder="nightly_price, cancellation_policy, parking"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function TenantSetup() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [property, setProperty] = useState(null);
  const [meta, setMeta] = useState(null);
  const [prefs, setPrefs] = useState({});
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    Promise.all([getProperty(id), getScenarioDefaults()])
      .then(([propData, metaData]) => {
        setProperty(propData);
        setMeta(metaData);
        if (metaData.default_party_a) setPrefs(metaData.default_party_a);
        setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });
  }, [id]);

  const handleSubmit = async () => {
    setActionLoading(true);
    setError(null);
    try {
      const result = await negotiateProperty(id, { party_a_preferences: prefs });
      // Redirect to the tenant dashboard!
      navigate(`/tenant/${result.id}`);
    } catch (err) {
      setError(err.message);
      setActionLoading(false);
    }
  };

  if (loading) return <div className="page"><div className="loading-container"><div className="spinner" /></div></div>;
  if (error && !property) return <div className="page"><div className="container" style={{ textAlign: 'center', paddingTop: '4rem' }}><h2>Error</h2><p>{error}</p></div></div>;

  return (
    <div className="page" style={{ paddingTop: '80px', backgroundColor: '#f9fafb', minHeight: '100vh', paddingBottom: '4rem' }}>
      <div className="container">
        <div style={{ textAlign: 'center', marginBottom: '2.5rem' }}>
          <h2 style={{ marginBottom: '0.5rem', fontSize: '2.2rem', color: '#111827' }}>Negotiate: {property.title}</h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '1.1rem' }}>Set your boundaries. Your AI agent will handle the haggling.</p>
        </div>

        {meta && (
          <TenantForm
            variables={meta.variables || []}
            values={prefs}
            onChange={setPrefs}
          />
        )}

        <div style={{ textAlign: 'center', marginTop: '2rem' }}>
          {error && (
            <div style={{ padding: '1rem', background: '#fef2f2', color: '#dc2626', borderRadius: '8px', marginBottom: '1.5rem', maxWidth: '600px', margin: '0 auto 1.5rem', border: '1px solid #f87171' }}>
              {error}
            </div>
          )}
          <button 
            className="btn btn-primary" 
            onClick={handleSubmit} 
            disabled={actionLoading} 
            style={{ 
              width: '100%', 
              maxWidth: '400px', 
              padding: '1.2rem', 
              fontSize: '1.1rem', 
              fontWeight: 700, 
              borderRadius: '12px',
              boxShadow: '0 10px 15px -3px rgba(225, 29, 72, 0.2)',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '0.5rem',
            }}
          >
            {actionLoading ? (
              <>
                <div className="spinner" style={{ width: '18px', height: '18px', borderWidth: '2px' }} />
                Activating Agent...
              </>
            ) : (
              <>
                <PlayIcon size={18} /> Start Negotiation
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
