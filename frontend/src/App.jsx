import React, { useState } from 'react';
const API = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';
export default function App() {
  const [session, setSession] = useState(null);
  const [messages, setMessages] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function request(path, body) {
    setBusy(true); setError('');
    try {
      const response = await fetch(`${API}${path}`, { method: 'POST', headers: {'Content-Type': 'application/json'}, ...(body ? {body: JSON.stringify(body)} : {}) });
      if (!response.ok) throw new Error(`API error ${response.status}`);
      const data = await response.json();
      setSession(data);
      setMessages(prev => [...prev, {by: 'story', text: data.narration}]);
    } catch (err) { setError(err.message + ' — Is the backend running?'); }
    finally {setBusy(false);}
  }
  const act = (action, target) => request('/game/action', {session_id: session.session_id, action, target});
  return <main><header><span className="eyebrow">NEURAL NEXUS PRESENTS</span><h1>MYTHOS <span>✦</span></h1><p>Step inside the legend. Every choice matters.</p></header><section className="panel">
  {!session ? <><h2>The Island of Lost Stars</h2><p>Begin an Odyssey-inspired adventure of courage, curiosity and discovery.</p><button onClick={() => request('/game/start')} disabled={busy}>Start adventure →</button></> : <><div className="top"><div><span className="eyebrow">CURRENT LOCATION</span><h2>{session.world.location}</h2><p>{session.world.description}</p></div><span className="turn">TURN {session.world.turn}</span></div><div className="story">{messages.map((m,i) => <p key={i}>{m.text}</p>)}</div><div className="actions"><button disabled={busy} onClick={() => act('look')}>👁 Look</button><button disabled={busy} onClick={() => act('search')}>🔎 Search</button>{Object.entries(session.world.exits).map(([direction,location]) => <button key={direction} disabled={busy} onClick={() => act('move',direction)}>↗ {location}</button>)}</div><h3>Visible items</h3><div className="actions">{session.world.visible_objects.length ? session.world.visible_objects.map(o => <button key={o.id} disabled={busy} onClick={() => act('take',o.id)}>＋ Take {o.name}</button>) : <p>Nothing visible. Perhaps you should search?</p>}</div><h3>Inventory</h3><p>{session.world.inventory.map(i => i.name).join(', ') || 'Empty'}</p><button className="subtle" onClick={() => {setSession(null);setMessages([]);}}>New story</button></>}
{error && <p className="error">{error}</p>}
</section><footer>AI-friendly context · Engine-validated actions · Hidden discoveries</footer></main>;
}
