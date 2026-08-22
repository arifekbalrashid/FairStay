/**
 * SSE (Server-Sent Events) connection manager.
 */

const API_BASE = 'http://localhost:8000';

export function subscribeToEvents(negotiationId, onEvent, onError, onComplete) {
  const url = `/api/negotiations/${negotiationId}/events`;
  const source = new EventSource(url);

  source.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);

      if (data.event_type === 'NEGOTIATION_COMPLETE') {
        if (onComplete) onComplete();
        source.close();
        return;
      }

      if (onEvent) onEvent(data);
    } catch (err) {
      console.error('SSE parse error:', err);
    }
  };

  source.onerror = (err) => {
    console.error('SSE connection error:', err);
    if (onError) onError(err);
    // Don't close — EventSource auto-reconnects
  };

  // Return cleanup function
  return () => {
    source.close();
  };
}
