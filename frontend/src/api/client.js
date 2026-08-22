/**
 * API client for FairDeal backend.
 */

const API_BASE = '';  // Uses Vite proxy

async function request(path, options = {}) {
  const url = `${API_BASE}${path}`;
  const config = {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  };

  const res = await fetch(url, config);

  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || `Request failed: ${res.status}`);
  }

  return res.json();
}

// ─── Health ────────────────────────────────────────────────────────────────

export function getHealth() {
  return request('/health');
}

// ─── Scenarios ─────────────────────────────────────────────────────────────

export function getScenarioDefaults(scenario = 'rental') {
  return request(`/api/scenarios/${scenario}/defaults`);
}

// ─── Properties (Marketplace) ────────────────────────────────────────────

export function getProperties(hostId = null) {
  const url = hostId ? `/api/properties?host_id=${hostId}` : '/api/properties';
  return request(url);
}

export function getProperty(id) {
  return request(`/api/properties/${id}`);
}

export function createProperty(data) {
  return request('/api/properties', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function negotiateProperty(id, data) {
  return request(`/api/properties/${id}/negotiate`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function getPropertyNegotiations(id) {
  return request(`/api/properties/${id}/negotiations`);
}

// ─── Negotiations ──────────────────────────────────────────────────────────

export function createNegotiation(data) {
  return request('/api/negotiations', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function getNegotiation(id) {
  return request(`/api/negotiations/${id}`);
}

export function startNegotiation(id) {
  return request(`/api/negotiations/${id}/start`, { method: 'POST' });
}

export function getPartyDashboard(id, party) {
  return request(`/api/negotiations/${id}/dashboard/${party}`);
}

export function approveNegotiation(id, party, approved, reason = '') {
  return request(`/api/negotiations/${id}/approve`, {
    method: 'POST',
    body: JSON.stringify({ party, approved, reason }),
  });
}

export function resumeNegotiation(id) {
  return request(`/api/negotiations/${id}/resume`, { method: 'POST' });
}
