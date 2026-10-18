import React, { useCallback, useEffect, useRef, useState } from 'react';
import './LastArchive.css';

const INTRO = 'December 16, 1773. Boston Harbor. Three tea ships sit at anchor, and a restless crowd gathers along the docks. You have sixty seconds to recover what history forgot.';
const EVIDENCE = {
  taxation_dispute: { title: 'Taxation dispute', description: 'Protesters object to taxation without elected representation in Parliament.' },
  shipping_manifest: { title: 'Shipping manifest', description: 'Cargo records tie the tea to the East India Company.' },
  tea_act: { title: 'Tea Act of 1773', description: 'Parliament\'s tea policy intensified a dispute over trade and taxation.' },
};
const api = async (path, body) => {
  const response = await fetch('/archive' + path, {
    method: body === undefined ? 'GET' : 'POST',
    headers: { 'Content-Type': 'application/json' },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(result.detail || 'The Archive is temporarily unavailable.');
  return result;
};
const initialMessages = [{ by: 'archive', text: INTRO }];
const titleFor = key => EVIDENCE[key]?.title || key.replaceAll('_', ' ');

export default function LastArchive({ onExit }) {
  const [phase, setPhase] = useState('brief');
  const [sessionId, setSessionId] = useState('');
  const [remaining, setRemaining] = useState(60);
  const [courtRemaining, setCourtRemaining] = useState(90);
  const [evidence, setEvidence] = useState([]);
  const [messages, setMessages] = useState(initialMessages);
  const [input, setInput] = useState('');
  const [testimony, setTestimony] = useState('');
  const [question, setQuestion] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [source, setSource] = useState('');
  const logEnd = useRef(null);
  const clockLock = useRef(false);
  const extractionLock = useRef(false);
  const currentPhase = useRef(phase);
  useEffect(() => { currentPhase.current = phase; }, [phase]);
  useEffect(() => { logEnd.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }); }, [messages, phase]);

  const extract = useCallback(async (id, force = false) => {
    if (!id || extractionLock.current || currentPhase.current !== 'crisis') return;
    extractionLock.current = true;
    setError('');
    try {
      if (force) await api('/extract', { session_id: id });
      else {
        const state = await api('/state/' + encodeURIComponent(id));
        if (state.phase !== 'COURT') { extractionLock.current = false; return; }
      }
      setCourtRemaining(90);
      currentPhase.current = 'fracture';
      setPhase('fracture');
      window.setTimeout(() => { currentPhase.current = 'court'; setPhase('court'); }, 1400);
    } catch (err) {
      setError(err.message);
      extractionLock.current = false;
    }
  }, []);

  useEffect(() => {
    if (phase !== 'crisis' || !sessionId) return undefined;
    let disposed = false;
    const refresh = async () => {
      if (clockLock.current || disposed) return;
      clockLock.current = true;
      try {
        const state = await api('/state/' + encodeURIComponent(sessionId));
        if (disposed) return;
        setRemaining(state.remaining_seconds ?? 60);
        setEvidence(state.evidence || []);
        if (state.phase === 'COURT') await extract(sessionId);
      } catch (err) { if (!disposed) setError(err.message); }
      finally { clockLock.current = false; }
    };
    refresh();
    const tick = window.setInterval(refresh, 1000);
    return () => { disposed = true; window.clearInterval(tick); };
  }, [phase, sessionId, extract]);

  useEffect(() => {
    if (!['court', 'question'].includes(phase) || !sessionId) return undefined;
    let disposed = false;
    const refresh = async () => {
      try {
        const state = await api('/state/' + encodeURIComponent(sessionId));
        if (disposed) return;
        setCourtRemaining(state.remaining_seconds ?? 90);
        if (state.phase === 'REVIEW') { currentPhase.current = 'expired'; setPhase('expired'); }
      } catch (err) { if (!disposed) setError(err.message); }
    };
    refresh();
    const tick = window.setInterval(refresh, 1000);
    return () => { disposed = true; window.clearInterval(tick); };
  }, [phase, sessionId]);

  async function begin() {
    if (busy) return;
    setBusy(true); setError('');
    try {
      const result = await api('/start', { nickname: 'Chrono Agent' });
      extractionLock.current = false;
      setSessionId(result.session_id);
      setRemaining(result.duration_seconds || 60); setCourtRemaining(90);
      setEvidence([]); setMessages(initialMessages); setInput(''); setTestimony(''); setQuestion(''); setSource('');
      currentPhase.current = 'crisis'; setPhase('crisis');
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  async function sendAction(event) {
    event.preventDefault();
    const text = input.trim();
    if (!text || busy || phase !== 'crisis') return;
    setInput(''); setBusy(true); setError('');
    setMessages(prev => [...prev, { by: 'player', text }]);
    try {
      const response = await api('/action', { session_id: sessionId, text });
      setMessages(prev => [...prev, { by: 'archive', text: response.reply, source: response.source }]);
      if (response.discovered) setEvidence(prev => [...new Set([...prev, response.discovered])]);
    } catch (err) {
      setError(err.message);
      if (String(err.message).includes('Crisis ended')) await extract(sessionId, true);
    } finally { setBusy(false); }
  }

  async function submitTestimony(event) {
    event.preventDefault();
    if (busy || testimony.trim().length < 5) return;
    setBusy(true); setError('');
    try {
      const result = await api('/court', { session_id: sessionId, testimony: testimony.trim() });
      setQuestion(result.archivist_question);
      setSource(result.source);
      setEvidence(result.evidence_ids || evidence);
      currentPhase.current = 'question'; setPhase('question');
    } catch (err) { setError(err.message); }
    finally { setBusy(false); }
  }

  return <main className={'archive-app archive-live archive-'+phase}>
    <header className="archive-header">
      <button className="archive-link" onClick={onExit}>← Neural Nexus</button>
      <span className="archive-mark">◈ THE LAST ARCHIVE</span>
      <span className="archive-tag">CHRONO BUREAU · CASE 001</span>
    </header>
    {phase === 'brief' && <section className="archive-selection archive-fade">
      <div className="archive-kicker">CHOOSE YOUR ASSIGNMENT</div>
      <h1>Select your destination.</h1>
      <div className="archive-mission-gallery">
        <button type="button" className="archive-mission-card" disabled={busy} onClick={begin} aria-label="Jump into The Tea in the Harbor">
          <img className="archive-mission-art" src="/images/missions/boston-tea-party.png" alt="Moonlit Boston Harbor" />
          <span className="archive-mission-details">
            <strong>The Tea in the Harbor</strong>
            <span className="archive-mission-meta">BOSTON · 1773 <span className="archive-mission-action">{busy ? 'Opening…' : 'Jump in →'}</span></span>
          </span>
        </button>
        {[
          { id:'bastille', title:'Storming the Bastille', place:'PARIS · 1789', image:'/images/missions/storming-bastille.png' },
          { id:'berlin', title:'The Wall Opens', place:'BERLIN · 1989', image:'/images/missions/berlin-wall.png' },
          { id:'independence', title:'The Independence Debate', place:'PHILADELPHIA · 1776', image:'/images/missions/independence-debate.png' },
          { id:'missile', title:'Thirteen Days', place:'CUBA / WASHINGTON · 1962', image:'/images/missions/cuban-missile-crisis.png' }
        ].slice(0, 2).map(mission => (
          <article className="archive-mission-card archive-mission-upcoming" key={mission.id} aria-label={mission.title + ' coming soon'}>
            <img className="archive-mission-art" src={mission.image} alt="" loading="lazy" />
            <div className="archive-mission-details">
              <strong>{mission.title}</strong>
              <span className="archive-mission-meta">{mission.place}<span className="archive-mission-soon">COMING SOON</span></span>
            </div>
          </article>
        ))}
      </div>
    </section>}
    {phase === 'crisis' && <section className="archive-container archive-fade">
      <div className="archive-status"><span>BOSTON HARBOR · DEC 16, 1773</span><span className={'archive-count archive-digital-clock '+(remaining <= 10 ? 'urgent' : '')} role="timer" aria-label={remaining + ' seconds remaining'}><span className="archive-clock-dot">●</span>00:{String(remaining).padStart(2, '0')}</span></div>
      <div className="archive-live-layout">
        <section className="archive-story">
          <div className="archive-scenery archive-live-scene"><span>THE HARBOR · 1773</span></div>
          <div className="archive-chat-head"><div className="archive-kicker">LIVE HISTORICAL SIMULATION</div><h1>The Tea in the Harbor</h1><p>Ask. Investigate. Remember.</p></div>
          <div className="archive-messages" aria-live="polite">{messages.map((m,i)=><div key={i} className={'archive-message archive-msg-'+m.by}><span>{m.by === 'player' ? 'YOU' : 'THE ARCHIVE'}{m.source === 'fallback' ? ' · BACKUP' : ''}</span><p>{m.text}</p></div>)}<div ref={logEnd}/></div>
          <form className="archive-chat-form" onSubmit={sendAction}><input aria-label="Describe your action" placeholder="I ask a merchant why the colonists are protesting…" value={input} onChange={e=>setInput(e.target.value)} disabled={busy} maxLength={1000}/><button type="submit" disabled={busy || !input.trim()}>Send ↗</button></form>
          <div className="archive-chat-foot"><span>{busy ? 'Chrono Bureau processing…' : 'Natural-language actions · OCI AI'}</span><button className="archive-link" onClick={()=>extract(sessionId,true)} disabled={busy}>Extract now →</button></div>
        </section>
        <aside className="archive-evidence archive-casefile"><div className="archive-kicker">FIELD NOTES · AUTOMATICALLY RECORDED</div><h2>Recovered evidence <span>{evidence.length}</span></h2>{evidence.length ? evidence.map(id => <div className="archive-evidence-entry" key={id}><b>◈ {titleFor(id)}</b><p>{EVIDENCE[id]?.description || 'Historical evidence recovered.'}</p></div>) : <div className="archive-empty-evidence">No evidence recovered yet. Start investigating through chat.</div>}</aside>
      </div>
    </section>}
    {phase === 'fracture' && <section className="archive-center archive-break"><div className="archive-ring">◈</div><div className="archive-kicker">TEMPORAL EXTRACTION</div><h1>TIME IS CALLED.</h1><p>Your discoveries have been preserved in the archive.</p></section>}
    {(phase === 'court' || phase === 'question') && <section className="archive-container archive-fade"><div className="archive-court-timer"><span>COURT OF TIME</span><span className={'archive-count archive-digital-clock '+(courtRemaining <= 10 ? 'urgent' : '')} role="timer">{String(Math.floor(courtRemaining/60)).padStart(2,'0')}:{String(courtRemaining%60).padStart(2,'0')}</span></div><div className="archive-court-hero"><div className="archive-kicker">THE COURT OF TIME · CASE 001</div><h1>Reconstruct the truth.</h1><p>Explain what happened and why. Your field discoveries form the basis of your testimony.</p></div><div className="archive-court-layout"><div className="archive-panel archive-archivist"><div className="archive-avatar">◈</div><div className="archive-kicker">THE ARCHIVIST</div><h2>{phase === 'question' ? 'Your testimony has been heard.' : 'Chrono Agent, present your account.'}</h2><p>{phase === 'question' ? 'The Archivist has one further challenge for your interpretation.' : 'What led to the Boston Tea Party? Which evidence supports your explanation?'}</p><div className="archive-quote">“A recovered memory is not yet an understood history.”</div></div><div className="archive-panel"><div className="archive-kicker">YOUR RECOVERED EVIDENCE</div><div className="archive-court-evidence">{evidence.length ? evidence.map(id=><div key={id} className="archive-evidence-entry"><b>◈ {titleFor(id)}</b><p>{EVIDENCE[id]?.description || id}</p></div>):<p>No field evidence was recovered. You may still explain your understanding, but your account has no recorded observations.</p>}</div>{phase === 'court' ? <form onSubmit={submitTestimony}><label className="archive-label" htmlFor="archive-testimony">Your historical testimony</label><textarea id="archive-testimony" rows={5} value={testimony} onChange={e=>setTestimony(e.target.value)} maxLength={2500} placeholder="I believe the protest happened because… The evidence I recovered suggests…"/><button className="archive-primary" disabled={busy || testimony.trim().length < 5}>{busy ? 'Consulting the Archivist…' : 'Submit testimony →'}</button></form> : <div className="archive-question"><div className="archive-kicker">ARCHIVIST'S QUESTION · {source === 'ai' ? 'OCI AI' : 'BACKUP'}</div><p>{question}</p><small>Your testimony and the Archivist's question were saved in Oracle Database. Follow-up answers and scoring are coming in the next sprint.</small><button className="archive-primary" onClick={begin} disabled={busy}>Play again ↻</button></div>}</div></div></section>}
    {phase === 'expired' && <section className="archive-center archive-fade"><div className="archive-kicker">COURT OF TIME</div><h1>Time is up.</h1><p>Your testimony window has closed.</p><button className="archive-primary" onClick={begin}>Try again ↻</button></section>}
    {error && <div className="archive-alert" role="alert">{error}</div>}
  </main>;
}
