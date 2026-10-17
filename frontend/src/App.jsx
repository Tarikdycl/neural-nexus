import { useRef, useState } from 'react';
import LandingPage from './pages/LandingPage.jsx';
import RealmsPage from './pages/RealmsPage.jsx';
import GamePage from './pages/GamePage.jsx';
import { gameAction, loadGame, startGame } from './services/api.js';

const STORAGE_KEY = 'neural-nexus-session';

function parseAction(input, world) {
  const value = input.trim();
  const lower = value.toLowerCase();
  if (/^(look|look around|inspect|observe|l)$/i.test(value)) return { action: 'look', target: null };
  if (/^(search|search around|explore|s)$/i.test(value)) return { action: 'search', target: null };
  const take = /^(take|pick up|grab)\s+(.+)$/i.exec(value);
  if (take) {
    const choice = take[2].trim().toLowerCase();
    const item = (world.visible_objects || []).find(o => o.id?.toLowerCase() === choice || o.name?.toLowerCase() === choice);
    if (item) return { action: 'take', target: item.id };
    return { error: 'That item is not visible. Try searching first, or use the item name shown in the sidebar.' };
  }
  const move = /^(move|go|walk|travel)(?:\s+to)?\s+(.+)$/i.exec(value);
  if (move) {
    const choice = move[2].trim().toLowerCase();
    const entry = Object.entries(world.exits || {}).find(([direction, location]) => direction.toLowerCase() === choice || String(location).toLowerCase() === choice);
    if (entry) return { action: 'move', target: entry[0] };
    return { error: 'That path is not available. Choose a visible exit.' };
  }
  return { error: 'For now, use look, search, take [visible item], or move [direction]. Natural-language actions will be enabled after AI integration.' };
}

export default function App() {
  const [page, setPage] = useState('landing');
  const [session, setSession] = useState(null);
  const [messages, setMessages] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const lock = useRef(false);

  async function enterRealm(realmId) {
    if (realmId !== 'odyssey_island' || lock.current) return;
    lock.current = true; setBusy(true); setError('');
    try {
      const data = await startGame(realmId);
      setSession(data);
      setMessages([{ by: 'story', text: data.narration }]);
      localStorage.setItem(STORAGE_KEY, data.session_id);
      setPage('game');
    } catch (err) { setError(err.message); }
    finally { lock.current = false; setBusy(false); }
  }

  async function performAction(input, explicitTarget = null) {
    if (!session || lock.current) return false;
    const parsed = explicitTarget !== null || ['look','search'].includes(input)
      ? { action: input, target: explicitTarget }
      : parseAction(input, session.world);
    if (parsed.error) { setError(parsed.error); return false; }
    lock.current = true; setBusy(true); setError('');
    const label = explicitTarget ? input + ' ' + explicitTarget : input;
    setMessages(prev => [...prev, { by: 'player', text: label }]);
    try {
      const data = await gameAction(session.session_id, parsed.action, parsed.target);
      setSession(data);
      setMessages(prev => [...prev, { by: 'story', text: data.narration }]);
      return true;
    } catch (err) { setError(err.message); return true; }
    finally { lock.current = false; setBusy(false); }
  }

  async function resumeGame() {
    const savedId = localStorage.getItem(STORAGE_KEY);
    if (!savedId || lock.current) return;
    lock.current = true; setBusy(true); setError('');
    try {
      const data = await loadGame(savedId);
      setSession(data);
      setMessages([{ by: 'story', text: data.world.description || 'Your adventure continues.' }]);
      setPage('game');
    } catch (err) {
      localStorage.removeItem(STORAGE_KEY);
      setError('Could not resume your previous session. ' + err.message);
    } finally { lock.current = false; setBusy(false); }
  }

  function saveGame() {
    if (session?.session_id) {
      localStorage.setItem(STORAGE_KEY, session.session_id);
      setError('Session reference saved in this browser. The server controls whether progress persists after a restart.');
    }
  }

  if (page === 'landing') return <LandingPage onBegin={() => { setError(''); setPage('realms'); }} />;
  if (page === 'realms') return <>
    <RealmsPage onBack={() => setPage('landing')} onEnter={enterRealm} busy={busy} />
    {error && <p className="page-error" role="alert">{error}</p>}
    {localStorage.getItem(STORAGE_KEY) && <div className="resume-wrap"><button className="secondary-button" disabled={busy} onClick={resumeGame}>Resume previous journey →</button></div>}
  </>;
  return <GamePage session={session} messages={messages} busy={busy} error={error}
    onAction={performAction} onBack={() => {setError('');setPage('realms');}}
    onSave={saveGame} />;
}
