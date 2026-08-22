import { useState, useEffect, useRef } from 'react';
import { useParams } from 'react-router-dom';
import { getPartyDashboard, approveNegotiation } from '../api/client';
import { subscribeToEvents } from '../api/sse';
import {
  ZapIcon, HandIcon, CheckCircleIcon, XCircleIcon, RefreshCwIcon, ClockIcon,
  LockIcon, PlayIcon, HandshakeIcon, CheckIcon, XIcon, BriefcaseIcon, BuildingIcon,
} from '../components/Icons';

function formatTermKey(key) {
  return key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatTermValue(value) {
  if (typeof value === 'boolean') {
    return (
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: '3px' }}>
        {value ? <CheckIcon size={14} color="var(--success)" /> : <XIcon size={14} color="var(--error)" />}
        {value ? 'Yes' : 'No'}
      </span>
    );
  }
  if (typeof value === 'number') {
    if (value >= 10000) return `₹${value.toLocaleString('en-IN')}`;
    return value.toLocaleString('en-IN');
  }
  return String(value);
}

// ─── Status Banner ────────────────────────────────────────────────────────

function StatusBanner({ data }) {
  const s = data?.status;
  const statusMap = {
    'in_progress': { Icon: ZapIcon, title: 'AI Agents Negotiating...', desc: 'Your agent is working to get you the best deal.', color: 'var(--accent-primary)' },
    'awaiting_approval': { Icon: HandIcon, title: 'Agreement Reached', desc: 'Review the proposed terms and decide.', color: 'var(--warning)' },
    'approved': { Icon: CheckCircleIcon, title: 'Deal Finalized', desc: 'Both parties approved the agreement.', color: 'var(--success)' },
    'failed': { Icon: XCircleIcon, title: 'No Agreement', desc: 'Agents could not find mutually acceptable terms.', color: 'var(--error)' },
    'rejected': { Icon: RefreshCwIcon, title: 'Deal Rejected', desc: 'A party rejected the agreement.', color: 'var(--warning)' },
    'pending': { Icon: ClockIcon, title: 'Starting...', desc: 'Preparing negotiation.', color: 'var(--text-muted)' },
  };
  const status = statusMap[s] || statusMap['pending'];
  const StatusIcon = status.Icon;

  return (
    <div className="status-banner" style={{ borderLeft: `3px solid ${status.color}` }}>
      <div className="status-info">
        <div className="status-icon" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: '40px', height: '40px', borderRadius: '10px', background: `${status.color}12` }}>
          <StatusIcon size={22} color={status.color} />
        </div>
        <div className="status-text">
          <h3>{status.title}</h3>
          <p>{status.desc}</p>
        </div>
      </div>
      <div className="status-meta">
        <div className="meta-item">
          <div className="meta-value">{data?.current_round || 0}</div>
          <div className="meta-label">Round</div>
        </div>
        <div className="meta-item">
          <div className="meta-value" style={{ color: 'var(--text-muted)', fontSize: '1rem' }}>/</div>
        </div>
        <div className="meta-item">
          <div className="meta-value">{data?.max_rounds || 10}</div>
          <div className="meta-label">Max</div>
        </div>
      </div>
    </div>
  );
}

// ─── My Preferences Sidebar ───────────────────────────────────────────────

function PreferencesSidebar({ data }) {
  const prefs = data?.my_preferences || {};

  return (
    <div className="card sidebar-card">
      <h4 style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
        <LockIcon size={14} /> Your Private Preferences
      </h4>
      {prefs.hard_constraints && Object.keys(prefs.hard_constraints).length > 0 && (
        <div style={{ marginBottom: '0.75rem' }}>
          <div style={{ fontSize: '0.72rem', color: 'var(--error)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.3rem' }}>
            Hard Constraints
          </div>
          {Object.entries(prefs.hard_constraints).map(([k, v]) => (
            <div className="cost-row" key={k}>
              <span className="cost-label">{formatTermKey(k)}</span>
              <span className="cost-value">{formatTermValue(v)}</span>
            </div>
          ))}
        </div>
      )}
      {prefs.ideal_values && Object.keys(prefs.ideal_values).length > 0 && (
        <div style={{ marginBottom: '0.75rem' }}>
          <div style={{ fontSize: '0.72rem', color: 'var(--success)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.3rem' }}>
            Ideal Values
          </div>
          {Object.entries(prefs.ideal_values).map(([k, v]) => (
            <div className="cost-row" key={k}>
              <span className="cost-label">{formatTermKey(k)}</span>
              <span className="cost-value">{formatTermValue(v)}</span>
            </div>
          ))}
        </div>
      )}
      {prefs.priorities?.length > 0 && (
        <div style={{ marginBottom: '0.5rem' }}>
          <div style={{ fontSize: '0.72rem', color: 'var(--accent-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.3rem' }}>
            Priorities
          </div>
          <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
            {prefs.priorities.join(' → ')}
          </div>
        </div>
      )}
      {prefs.negotiation_style && (
        <div className="cost-row">
          <span className="cost-label">Style</span>
          <span className="cost-value" style={{ textTransform: 'capitalize' }}>{prefs.negotiation_style}</span>
        </div>
      )}
    </div>
  );
}

// ─── Offer Timeline ───────────────────────────────────────────────────────

function OfferTimeline({ offers, events, partyRole }) {
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [offers?.length, events?.length]);

  // Merge offers and important events into a chronological feed
  const feedItems = [];

  // Add system events
  for (const e of (events || [])) {
    if (['NEGOTIATION_STARTED', 'AGREEMENT_REACHED', 'NEGOTIATION_FAILED',
         'HUMAN_APPROVED', 'HUMAN_REJECTED', 'NEGOTIATION_RESUMED'].includes(e.event_type)) {
      feedItems.push({ type: 'event', data: e });
    }
  }

  // Add offers
  for (const o of (offers || [])) {
    feedItems.push({ type: 'offer', data: o });
  }

  // Sort by time
  feedItems.sort((a, b) => {
    const timeA = a.data.created_at || a.data.timestamp || '';
    const timeB = b.data.created_at || b.data.timestamp || '';
    return timeA.localeCompare(timeB);
  });

  const getDotClass = (item) => {
    if (item.type === 'event') {
      if (item.data.event_type === 'AGREEMENT_REACHED') return 'success';
      if (item.data.event_type === 'NEGOTIATION_FAILED') return 'error';
      return 'system';
    }
    return item.data.is_mine ? 'party-a' : 'party-b';
  };

  const getEventLabel = (eventType) => {
    const map = {
      'NEGOTIATION_STARTED': { Icon: PlayIcon, label: 'Negotiation Started', color: 'var(--accent-primary)' },
      'AGREEMENT_REACHED': { Icon: HandshakeIcon, label: 'Agreement Reached', color: 'var(--success)' },
      'NEGOTIATION_FAILED': { Icon: XCircleIcon, label: 'Negotiation Failed', color: 'var(--error)' },
      'HUMAN_APPROVED': { Icon: CheckCircleIcon, label: 'Approved', color: 'var(--success)' },
      'HUMAN_REJECTED': { Icon: XCircleIcon, label: 'Rejected', color: 'var(--error)' },
      'NEGOTIATION_RESUMED': { Icon: RefreshCwIcon, label: 'Resumed', color: 'var(--warning)' },
    };
    return map[eventType] || { Icon: ClockIcon, label: eventType, color: 'var(--text-muted)' };
  };

  return (
    <div className="timeline">
      {feedItems.map((item, i) => (
        <div className="timeline-item" key={i} style={{ animationDelay: `${i * 0.05}s` }}>
          <div className={`timeline-dot ${getDotClass(item)}`} />
          <div className="card timeline-content">
            {item.type === 'event' ? (
              <>
                <div className="timeline-header">
                  {(() => {
                    const { Icon, label, color } = getEventLabel(item.data.event_type);
                    return (
                      <span className="timeline-round" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontWeight: 600, color }}>
                        <Icon size={15} color={color} /> {label}
                      </span>
                    );
                  })()}
                </div>
                {item.data.data?.message && (
                  <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '0.3rem' }}>
                    {item.data.data.message}
                  </div>
                )}
                {item.data.data?.final_terms && (
                  <div className="timeline-terms">
                    {Object.entries(item.data.data.final_terms).map(([k, v]) => (
                      <div className="term-pill" key={k}>
                        <span className="term-label">{formatTermKey(k)}</span>
                        <span className="term-value">{formatTermValue(v)}</span>
                      </div>
                    ))}
                  </div>
                )}
              </>
            ) : (
              <>
                <div className="timeline-header">
                  <span className={`badge ${item.data.is_mine ? 'badge-party-a' : 'badge-party-b'}`}>
                    {item.data.party_label}
                  </span>
                  <span className="timeline-round">Round {item.data.round}</span>
                </div>

                <div className="timeline-terms">
                  {item.data.terms && Object.entries(item.data.terms).map(([k, v]) => (
                    <div className="term-pill" key={k}>
                      <span className="term-label">{formatTermKey(k)}</span>
                      <span className="term-value">{formatTermValue(v)}</span>
                    </div>
                  ))}
                </div>

                {item.data.reasoning && (
                  <div className="timeline-reasoning">
                    "{item.data.reasoning}"
                  </div>
                )}

                {item.data.concessions?.length > 0 && (
                  <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '0.4rem' }}>
                    Concessions: {item.data.concessions.join(', ')}
                  </div>
                )}

                {!item.data.is_mine && !item.data.reasoning && (
                  <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', fontStyle: 'italic', marginTop: '0.3rem', display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
                    <LockIcon size={12} /> Other party's reasoning is private
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      ))}
      <div ref={endRef} />
    </div>
  );
}

// ─── Agreement Panel ──────────────────────────────────────────────────────

function AgreementPanel({ data, onApprove, onReject, actionLoading }) {
  const agreement = data?.agreement;
  if (!agreement) return null;

  const isApproved = data.status === 'approved';
  const isAwaiting = data.status === 'awaiting_approval';
  const isRejected = data.status === 'rejected';
  const canApprove = isAwaiting && agreement.my_approved === null;

  const panelStyle = isApproved
    ? { borderColor: 'var(--success)', background: 'var(--success-bg)' }
    : isRejected
    ? { borderColor: 'var(--error)', background: 'var(--error-bg)' }
    : { borderColor: 'var(--warning)', background: 'var(--warning-bg)' };

  const StatusIcon = isApproved ? CheckCircleIcon : isRejected ? XCircleIcon : HandshakeIcon;
  const statusColor = isApproved ? 'var(--success)' : isRejected ? 'var(--error)' : 'var(--warning)';

  return (
    <div className="agreement-panel" style={panelStyle}>
      <div className="agreement-title">
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '0.75rem' }}>
          <div style={{ width: '48px', height: '48px', borderRadius: '50%', background: `${statusColor}18`, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <StatusIcon size={24} color={statusColor} />
          </div>
        </div>
        <h2 style={{ color: statusColor }}>
          {isApproved ? 'Deal Finalized' : isRejected ? 'Deal Rejected' : 'Agreement Reached'}
        </h2>
      </div>

      <div className="agreement-terms">
        {Object.entries(agreement.final_terms).map(([k, v]) => (
          <div className="agreement-term" key={k}>
            <div className="agreement-term-label">{formatTermKey(k)}</div>
            <div className="agreement-term-value">{formatTermValue(v)}</div>
          </div>
        ))}
      </div>

      <div className="scores-grid">
        <div className="score-card">
          <div className="score-value" style={{ color: agreement.my_satisfaction >= 70 ? 'var(--success)' : agreement.my_satisfaction >= 50 ? 'var(--warning)' : 'var(--error)' }}>
            {agreement.my_satisfaction}%
          </div>
          <div className="score-label">Your Satisfaction</div>
        </div>
        <div className="score-card">
          <div className="score-value" style={{ color: 'var(--text-secondary)' }}>
            {agreement.fairness_score}%
          </div>
          <div className="score-label">Fairness Score</div>
        </div>
        <div className="score-card">
          <div className="score-value" style={{ color: 'var(--text-secondary)' }}>
            {agreement.total_rounds}
          </div>
          <div className="score-label">Rounds</div>
        </div>
      </div>

      {/* Approval status */}
      <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center', marginBottom: '1rem' }}>
        <div className={`badge ${agreement.my_approved === true ? 'badge-success' : agreement.my_approved === false ? 'badge-error' : 'badge-warning'}`}
             style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
          {agreement.my_approved === true ? <CheckIcon size={13} /> : agreement.my_approved === false ? <XIcon size={13} /> : <ClockIcon size={13} />}
          You: {agreement.my_approved === true ? 'Approved' : agreement.my_approved === false ? 'Rejected' : 'Pending'}
        </div>
        <div className={`badge ${agreement.other_approved === true ? 'badge-success' : agreement.other_approved === false ? 'badge-error' : 'badge-warning'}`}
             style={{ display: 'flex', alignItems: 'center', gap: '0.3rem' }}>
          {agreement.other_approved === true ? <CheckIcon size={13} /> : agreement.other_approved === false ? <XIcon size={13} /> : <ClockIcon size={13} />}
          {data.other_label}: {agreement.other_approved === true ? 'Approved' : agreement.other_approved === false ? 'Rejected' : 'Pending'}
        </div>
      </div>

      {canApprove && (
        <div className="approval-actions">
          <button className="btn btn-success btn-lg" onClick={onApprove} disabled={actionLoading} style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <CheckCircleIcon size={18} /> Approve This Deal
          </button>
          <button className="btn btn-danger" onClick={onReject} disabled={actionLoading} style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <XCircleIcon size={18} /> Reject
          </button>
        </div>
      )}
    </div>
  );
}

// ─── Main Dashboard ───────────────────────────────────────────────────────

export default function Dashboard({ party }) {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [showRejectModal, setShowRejectModal] = useState(false);
  const [rejectReason, setRejectReason] = useState('');
  const [message, setMessage] = useState('');

  const isTenant = party === 'tenant';
  const accentColor = isTenant ? 'var(--party-a)' : 'var(--party-b)';
  const partyRole = isTenant ? 'party_a' : 'party_b';
  const DashIcon = isTenant ? BriefcaseIcon : BuildingIcon;

  const load = () => {
    getPartyDashboard(id, party)
      .then((d) => { setData(d); setLoading(false); })
      .catch((err) => { console.error(err); setLoading(false); });
  };

  useEffect(() => { load(); }, [id, party]);

  // SSE — live updates
  useEffect(() => {
    if (data?.status === 'approved' || data?.status === 'failed') return;

    let debounceTimer;
    const debouncedLoad = () => {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        load();
      }, 500);
    };

    const cleanup = subscribeToEvents(
      id,
      () => debouncedLoad(), // Refresh on each event (debounced)
      (err) => console.error('SSE error:', err),
      () => debouncedLoad(), // Refresh on complete
    );

    // Also poll every 3s for resilience
    const interval = setInterval(load, 3000);

    return () => {
      cleanup();
      clearInterval(interval);
    };
  }, [id, data?.status]);

  const handleApprove = async () => {
    setActionLoading(true);
    try {
      const result = await approveNegotiation(id, partyRole, true);
      setMessage(result.message);
      load();
    } catch (err) {
      setMessage(`Error: ${err.message}`);
    }
    setActionLoading(false);
  };

  const handleReject = async () => {
    setActionLoading(true);
    try {
      const result = await approveNegotiation(id, partyRole, false, rejectReason);
      setMessage(result.message);
      setShowRejectModal(false);
      setRejectReason('');
      load();
    } catch (err) {
      setMessage(`Error: ${err.message}`);
    }
    setActionLoading(false);
  };

  if (loading) {
    return (
      <div className="page">
        <div className="container">
          <div className="loading-container">
            <div className="spinner" />
            <div className="loading-text">Loading {isTenant ? 'Guest' : 'Host'} dashboard...</div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="page" style={{ paddingTop: '80px' }}>
      <div className="container">
        {/* Dashboard header */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.5rem' }}>
          <div style={{ width: '36px', height: '36px', borderRadius: '10px', background: isTenant ? 'var(--party-a-bg)' : 'var(--party-b-bg)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <DashIcon size={20} color={accentColor} />
          </div>
          <div>
            <h2 style={{ margin: 0, borderBottom: `3px solid ${accentColor}`, display: 'inline-block', paddingBottom: '0.2rem' }}>
              {isTenant ? 'Guest' : 'Host'} Dashboard
            </h2>
            <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)', margin: '0.2rem 0 0' }}>
              Your private negotiation view
            </p>
          </div>
        </div>

        {message && (
          <div className="card" style={{ marginBottom: '1rem', padding: '0.75rem 1rem', background: 'var(--success-bg)', borderColor: 'var(--success)' }}>
            {message}
          </div>
        )}

        <StatusBanner data={data} />

        <div className="negotiation-layout">
          <div className="negotiation-main">
            {/* Agreement Panel */}
            {data?.agreement && (
              <div style={{ marginBottom: '1.5rem' }}>
                <AgreementPanel
                  data={data}
                  onApprove={handleApprove}
                  onReject={() => setShowRejectModal(true)}
                  actionLoading={actionLoading}
                />
              </div>
            )}

            {/* Offer Timeline */}
            {(data?.offers?.length > 0 || data?.events?.length > 0) ? (
              <OfferTimeline
                offers={data.offers}
                events={data.events}
                partyRole={data.party_role}
              />
            ) : (
              <div className="loading-container">
                <div className="spinner" />
                <div className="loading-text">Waiting for negotiation to begin...</div>
              </div>
            )}
          </div>

          {/* Sidebar */}
          <div className="negotiation-sidebar">
            <PreferencesSidebar data={data} />
          </div>
        </div>
      </div>

      {/* Rejection Modal */}
      {showRejectModal && (
        <div className="modal-overlay" onClick={() => setShowRejectModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>Reject Agreement</h3>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: '1rem' }}>
              Provide a reason for rejection.
            </p>
            <div className="form-group">
              <textarea className="form-input" rows={3} value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                placeholder="e.g., Rent is still too high."
                autoFocus
              />
            </div>
            <div className="modal-actions">
              <button className="btn btn-secondary" onClick={() => setShowRejectModal(false)}>Cancel</button>
              <button className="btn btn-danger" onClick={handleReject} disabled={actionLoading || !rejectReason.trim()}>Reject</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
