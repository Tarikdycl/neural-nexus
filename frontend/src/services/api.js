const API_BASE = (import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');

async function apiRequest(path, options = {}) {
  let response;
  try {
    response = await fetch(API_BASE + path, {
      ...options,
      headers: { 'Content-Type': 'application/json', ...options.headers },
    });
  } catch {
    throw new Error('Cannot connect to the game server. Check that FastAPI is running.');
  }
  if (!response.ok) {
    let detail;
    try { detail = (await response.json()).detail; } catch { /* non-JSON response */ }
    throw new Error(typeof detail === 'string' ? detail : 'Game server returned error ' + response.status + '.');
  }
  return response.json();
}

export const startGame = (realmId = 'odyssey_island') =>
  apiRequest('/game/start', { method: 'POST', body: JSON.stringify({ realm_id: realmId, player_name: 'Explorer' }) });

export const gameAction = (sessionId, action, target = null) =>
  apiRequest('/game/action', { method: 'POST', body: JSON.stringify({ session_id: sessionId, action, target }) });

export const loadGame = (sessionId) =>
  apiRequest('/game/' + encodeURIComponent(sessionId));

export const healthCheck = () => apiRequest('/health');
