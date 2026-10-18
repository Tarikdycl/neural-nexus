import React, { useCallback, useEffect, useRef, useState } from 'react';
import './LastArchive.css';

const INTRO = 'Boston Harbor, December 16, 1773. Lanterns flicker on the docks. Three tea ships are anchored. A crowd gathers by the water, and merchants argue over the cargo. Ask someone what is happening, examine the ships, or look around.';
const EVIDENCE = {
  taxation_dispute: { title: 'Taxation dispute', description: 'Protesters object to taxation without elected representation in Parliament.' },
  shipping_manifest: { title: 'Shipping manifest', description: 'Cargo records tie the tea to the East India Company.' },
  tea_act: { title: 'Tea Act of 1773', description: 'Parliament\'s tea policy intensified a dispute over trade and taxation.' },
};
const PARIS = 'storming_bastille_1789';
const MISSIONS = {
  boston_tea_party_1773: { title:'The Tea in the Harbor', place:'BOSTON · 1773', image:'/images/missions/boston-tea-party.png', intro:INTRO, scene:'/images/scenes/boston-harbor.png', evidence:EVIDENCE },
  [PARIS]: { title:'Storming the Bastille', place:'PARIS · 1789', image:'/images/missions/storming-bastille.png', intro:'Paris, July 14, 1789. A crowd gathers outside the Bastille. People seek ammunition as unrest grows. Ask a citizen, inspect the fortress or look around.', scene:'/images/missions/storming-bastille.png', evidence:{
    royal_authority:{title:'Royal authority',description:'The Bastille was a symbol of royal power and arbitrary imprisonment.'},
    gunpowder_search:{title:'Gunpowder stores',description:'The crowd sought arms and ammunition at the fortress.'},
    political_crisis:{title:'Political crisis',description:'Economic pressures, political conflict and distrust of royal authority fueled unrest.'}
  }}
};
const api = async (path, body) => {
  const response = await fetch('/archive' + path, {
    method: body === undefined ? 'GET' : 'POST',
    headers: { 'Content-Type': 'application/json' },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(response.status === 404 && path === '/verdict' ? 'Verdict endpoint not found. Restart the backend on port 8002 with the latest code.' : (typeof result.detail === 'string' ? result.detail : 'The Archive is temporarily unavailable.'));
  return result;
};
const initialMessages = [{ by: 'archive', text: INTRO }];
const titleFor = key => EVIDENCE[key]?.title || key.replaceAll('_', ' ');

export default function LastArchive({ onExit }) {
  const [phase, setPhase] = useState('brief');
  const [scenarioId, setScenarioId] = useState('boston_tea_party_1773');
  const [savedGames, setSavedGames] = useState([]);
  const [selectedSave, setSelectedSave] = useState(null);
  const [sessionId, setSessionId] = useState('');
  const [remaining, setRemaining] = useState(60);
  const [courtRemaining, setCourtRemaining] = useState(90);
  const [evidence, setEvidence] = useState([]);
  const [score, setScore] = useState(0);
  const [messages, setMessages] = useState(initialMessages);
  const [input, setInput] = useState('');
  const [testimony, setTestimony] = useState('');
  const [question, setQuestion] = useState('');
  const [courtAnswer, setCourtAnswer] = useState('');
  const [report, setReport] = useState(null);
  const [showRecords, setShowRecords] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [source, setSource] = useState('');
  const mission = MISSIONS[scenarioId] || MISSIONS.boston_tea_party_1773;
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
        setScore(state.score ?? 0);
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
        if (state.phase === 'REVIEW') { await loadVerdict(); }
      } catch (err) { if (!disposed) setError(err.message); }
    };
    refresh();
    const tick = window.setInterval(refresh, 1000);
    return () => { disposed = true; window.clearInterval(tick); };
  }, [phase, sessionId]);

  async function loadVerdict(answer = '') {
    try {
      const result = await api('/verdict', { session_id: sessionId, response: answer });
      setReport(result);
      currentPhase.current = 'verdict';
      setPhase('verdict');
    } catch (err) { setError(err.message); }
  }

  async function submitCourtAnswer(event) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    await loadVerdict(courtAnswer.trim());
    setBusy(false);
  }

  async function openSaved() {
    setError('');setBusy(true);
    try { const data=await api('/saves');setSavedGames(data.saves||[]);setPhase('saved'); }
    catch(err){setError(err.message);}finally{setBusy(false);}
  }
  async function openSavedDetail(id) {
    setError('');setBusy(true);
    try {const data=await api('/saves/'+encodeURIComponent(id));setSelectedSave(data);setPhase('savedDetail');}
    catch(err){setError(err.message);}finally{setBusy(false);}
  }

  async function saveAndReturn() {
    if (busy) return;
    setError('');
    try {
      if (sessionId) await api('/save', { session_id: sessionId });
      setSessionId('');
      currentPhase.current = 'brief'; setPhase('brief');
    } catch (err) { setError(err.message); }
  }

  async function begin(selected='boston_tea_party_1773') {
    if (busy) return;
    setBusy(true); setError('');
    try {
      const result = await api('/start', { nickname: 'Chrono Agent', scenario_id:selected });
      setScenarioId(selected);
      extractionLock.current = false;
      setSessionId(result.session_id);
      setRemaining(result.duration_seconds || 60); setCourtRemaining(90);
      setEvidence([]); setScore(0); setMessages([{by:'archive',text:MISSIONS[selected]?.intro || INTRO}]); setInput(''); setTestimony(''); setCourtAnswer(''); setReport(null); setShowRecords(false); setQuestion(''); setSource('');
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
      if (typeof response.total_score === 'number') setScore(response.total_score);
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
      <span className="archive-header-right"><button className="archive-saved-link" type="button" onClick={openSaved} disabled={busy}>▤ Saved Visits →</button><span className="archive-tag">CHRONO BUREAU · CASE 001</span></span>
    </header>
    {phase === 'brief' && <section className="archive-selection archive-fade">
      <div className="archive-kicker">CHOOSE YOUR ASSIGNMENT</div>
      <h1>Select your destination.</h1>
      <div className="archive-mission-gallery">
        <button type="button" className="archive-mission-card" disabled={busy} onClick={()=>begin('boston_tea_party_1773')} aria-label="Jump into The Tea in the Harbor">
          <img className="archive-mission-art" src="/images/missions/boston-tea-party.png" alt="Moonlit Boston Harbor" />
          <span className="archive-mission-details">
            <strong>The Tea in the Harbor</strong>
            <span className="archive-mission-meta">BOSTON · 1773 <span className="archive-mission-action">{busy ? 'Opening…' : 'Jump in →'}</span></span>
          </span>
        </button>
        <button type="button" className="archive-mission-card" disabled={busy} onClick={()=>begin(PARIS)} aria-label="Jump into Storming the Bastille"><img className="archive-mission-art" src={MISSIONS[PARIS].image} alt="Bastille fortress"/><span className="archive-mission-details"><strong>Storming the Bastille</strong><span className="archive-mission-meta">PARIS · 1789 <span className="archive-mission-action">Jump in →</span></span></span></button>
        {[
          
          { id:'berlin', title:'The Wall Opens', place:'BERLIN · 1989', image:'/images/missions/berlin-wall.png' },
          { id:'independence', title:'The Independence Debate', place:'PHILADELPHIA · 1776', image:'/images/missions/independence-debate.png' },
          { id:'missile', title:'Thirteen Days', place:'CUBA / WASHINGTON · 1962', image:'/images/missions/cuban-missile-crisis.png' }
        ].slice(0, 1).map(mission => (
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
      <div className="archive-status"><span>{mission.place}</span><span className={'archive-count archive-digital-clock '+(remaining <= 10 ? 'urgent' : '')} role="timer" aria-label={remaining + ' seconds remaining'}><span className="archive-clock-dot">●</span>00:{String(remaining).padStart(2, '0')}</span></div>
      <div className="archive-live-layout">
        <section className="archive-story">
          <div className="archive-scenery archive-live-scene" style={{backgroundImage:`linear-gradient(180deg,transparent,rgba(8,16,27,.65)),url("${mission.scene}")`}}><span>{mission.place}</span></div>
          <div className="archive-chat-head"><div className="archive-kicker">LIVE HISTORICAL SIMULATION</div><h1>{mission.title}</h1><p>Ask. Investigate. Remember.</p></div>
          <div className="archive-messages" aria-live="polite">{messages.map((m,i)=><div key={i} className={'archive-message archive-msg-'+m.by}><span>{m.by === 'player' ? 'YOU' : 'THE ARCHIVE'}{m.source === 'fallback' ? ' · BACKUP' : ''}</span><p>{m.text}</p></div>)}<div ref={logEnd}/></div>
          <form className="archive-chat-form" onSubmit={sendAction}><input aria-label="Describe your action" placeholder={scenarioId === PARIS ? "I ask a citizen why the crowd is here…" : "I ask a merchant why the colonists are protesting…"} value={input} onChange={e=>setInput(e.target.value)} disabled={busy} maxLength={1000}/><button type="submit" disabled={busy || !input.trim()}>Send ↗</button></form>
          <div className="archive-chat-foot"><span>{busy ? 'Reconstructing the moment…' : 'Natural-language actions · OCI AI'}</span><span className="archive-crisis-actions"><button className="archive-link" onClick={saveAndReturn} disabled={busy}>Save and Return to the Portal ↗</button><button className="archive-link" onClick={()=>extract(sessionId,true)} disabled={busy}>Extract now →</button></span></div>
        </section>
        <aside className="archive-evidence archive-casefile"><div className="archive-kicker">FIELD NOTES · AUTOMATICALLY RECORDED</div><h2>Recovered evidence <span>{evidence.length}</span></h2><div className="archive-score-counter">✦ {score} / 100</div>{evidence.length ? evidence.map(id => <div className="archive-evidence-entry" key={id}><b>◈ {mission.evidence[id]?.title || titleFor(id)}</b><p>{mission.evidence[id]?.description || 'Historical evidence recovered.'}</p></div>) : <div className="archive-empty-evidence">No evidence recovered yet. Start investigating through chat.</div>}</aside>
      </div>
    </section>}
    {phase === 'fracture' && <section className="archive-center archive-break"><div className="archive-ring">◈</div><div className="archive-kicker">TEMPORAL EXTRACTION</div><h1>TIME IS CALLED.</h1><p>Your discoveries have been preserved in the archive.</p></section>}
    {(phase === 'court' || phase === 'question') && <section className="archive-container archive-fade archive-court-simple">
      <div className="archive-court-timer"><span>THE COURT OF TIME</span><span className={'archive-count archive-digital-clock '+(courtRemaining <= 10 ? 'urgent' : '')} role="timer">{String(Math.floor(courtRemaining/60)).padStart(2,'0')}:{String(courtRemaining%60).padStart(2,'0')}</span></div>
      <div className="archive-court-hero"><div className="archive-kicker">{mission.place}</div><h1>{phase === 'question' ? 'One final question.' : 'Present your testimony.'}</h1></div>
      <div className="archive-court-minimal">
        <div className="archive-court-intro"><span className="archive-kicker">THE ARCHIVIST</span><p>{phase === 'question' ? question.replace(/^\*\*Question:\*\*\s*/,'') : `What happened in ${mission.title}, and what did you discover?`}</p></div>
        <div className="archive-court-notes">
          <button className="archive-evidence-toggle" type="button" onClick={()=>setShowRecords(v=>!v)} aria-expanded={showRecords}>
            <span>📖 DIGITAL EVIDENCE ARCHIVE · {evidence.length}</span><span>{showRecords ? 'Hide records −' : 'View records +'}</span>
          </button>
          {showRecords && <div className="archive-digital-records">{evidence.length
            ? evidence.map(id=><div className="archive-digital-record" key={id}><strong>{mission.evidence[id]?.title || titleFor(id)}</strong><p>{mission.evidence[id]?.description || id}</p></div>)
            : <p className="archive-no-evidence">No evidence recovered. Your testimony will be evaluated without field observations.</p>}
          </div>}
        </div>
        {phase === 'court' ? <form onSubmit={submitTestimony}><textarea aria-label="Your testimony" rows={4} value={testimony} onChange={e=>setTestimony(e.target.value)} maxLength={2500} placeholder="What happened, and why?"/><button className="archive-primary" disabled={busy || testimony.trim().length < 5}>{busy ? 'The Archivist is reviewing…' : 'Present testimony →'}</button></form> : <form onSubmit={submitCourtAnswer}><textarea aria-label="Answer the Archivist" rows={4} value={courtAnswer} onChange={e=>setCourtAnswer(e.target.value)} maxLength={2500} placeholder="Your answer to the Archivist…"/><button className="archive-primary" disabled={busy}>{busy ? 'Rendering judgment…' : 'Receive verdict →'}</button></form>}
      </div>
    </section>}
    {phase === 'verdict' && report && <section className="archive-container archive-verdict-page archive-fade">
      <div className="archive-kicker">THE LAST ARCHIVE · {mission.place}</div>
      <h1>{report.decision === 'APPROVED' ? 'Testimony approved.' : 'The archive remains incomplete.'}</h1>
      <p className={'archive-decision archive-decision-'+report.decision}>{report.decision === 'APPROVED' ? '◈ ARCHIVIST APPROVED' : '◇ ARCHIVIST REQUESTS REVISION'}</p>
      <p className="archive-verdict-subtitle">Your discovery review</p>
      <div className="archive-verdict-score"><strong>{report.score ?? 0} <span>/ 100</span></strong><span>ARCHIVE SCORE · {report.evidence_count} / {report.evidence_total} HISTORICAL THREADS RECOVERED</span></div>
      <div className="archive-verdict-grid">
        <section className="archive-verdict-panel"><div className="archive-kicker">ARCHIVIST'S ASSESSMENT</div><p>{report.feedback}</p>{report.strengths?.length > 0 && <><div className="archive-kicker">WHAT YOU CONNECTED</div>{report.strengths.map(item=><p key={item}>✓ {item}</p>)}</>}{report.improvements?.length > 0 && <><div className="archive-kicker">WHAT TO INVESTIGATE NEXT</div>{report.improvements.map(item=><p key={item}>→ {item}</p>)}</>}<div className="archive-kicker">YOUR TESTIMONY</div><p>{report.testimony}</p>{report.court_answer && <><div className="archive-kicker">FINAL ANSWER</div><p>{report.court_answer}</p></>}</section>
        <section className="archive-verdict-panel"><div className="archive-kicker">HISTORICAL REVIEW</div>{report.historical_review.map(item=><div className="archive-verdict-topic" key={item.topic}><strong>{item.discovered ? '✓' : '○'} {item.topic}</strong><p>{item.fact}</p></div>)}</section>
      </div>
      <p className="archive-verdict-disclaimer">{report.decision_basis || "Provisional evidence review; historical accuracy scoring is not yet implemented."}</p>
      <button className="archive-primary" onClick={() => { setError(''); setReport(null); setSessionId(''); currentPhase.current = 'brief'; setPhase('brief'); }}>Save and Return to the Portal →</button>
    </section>}
    {phase === 'saved' && <section className="archive-container archive-saves archive-fade">
      <div className="archive-kicker">CHRONO BUREAU · PLAYER ARCHIVE</div><h1>Saved Visits</h1>
      <p>Review your investigations and the Archivist's decisions.</p>
      <div className="archive-saves-grid">{savedGames.length ? savedGames.map(game=><button type="button" className="archive-save-card" key={game.session_id} onClick={()=>openSavedDetail(game.session_id)}>
        <strong>{game.title}</strong><span>{game.started_at?.slice(0,16).replace('T',' ') || 'Previous run'}</span>
        <span>{game.score} POINTS / 100 · {game.evidence_count} EVIDENCE</span>
        <em>{game.decision==='APPROVED'?'APPROVED':game.decision==='NEEDS_REVISION'?'NEEDS REVISION':game.phase}</em>
      </button>):<p>No saved investigations yet.</p>}</div>
      <button className="archive-primary" onClick={()=>setPhase('brief')}>← Return to Portal</button>
    </section>}
    {phase === 'savedDetail' && selectedSave && <section className="archive-container archive-saves archive-fade">
      <div className="archive-kicker">SAVED CASE · ARCHIVIST RECORDS</div><h1>{selectedSave.title}</h1>
      <p>{selectedSave.score} / 100 points · {selectedSave.evidence.length} recovered evidence · {selectedSave.verdict?.decision || selectedSave.phase}</p>
      <div className="archive-verdict-grid">
        <section className="archive-verdict-panel"><div className="archive-kicker">RECOVERED EVIDENCE</div>{selectedSave.evidence.map(e=><p key={e.id}>◈ {e.fact}</p>)}<div className="archive-kicker">TRANSCRIPT</div>{selectedSave.transcript.map((entry,i)=><p key={i}><strong>{entry.type.replaceAll('_',' ').toUpperCase()}</strong>: {entry.data?.text || ''}</p>)}</section>
        <section className="archive-verdict-panel"><div className="archive-kicker">ARCHIVIST'S DECISION</div><h2>{selectedSave.verdict?.decision || 'Awaiting judgment'}</h2><p>{selectedSave.verdict?.feedback || 'This run has not reached a verdict.'}</p><div className="archive-kicker">WHAT TO IMPROVE</div>{selectedSave.verdict?.improvements?.map((item,i)=><p key={i}>→ {item}</p>)}<div className="archive-kicker">WHAT YOU CONNECTED</div>{selectedSave.verdict?.strengths?.map((item,i)=><p key={i}>✓ {item}</p>)}</section>
      </div>
      <button className="archive-primary" onClick={openSaved}>← All Saved Visits</button>
    </section>}
    {phase === 'expired' && <section className="archive-center archive-fade"><div className="archive-kicker">COURT OF TIME</div><h1>Time is up.</h1><p>Your testimony window has closed.</p><button className="archive-primary" onClick={()=>begin(scenarioId)}>Try again ↻</button></section>}
    {error && <div className="archive-alert" role="alert">{error}</div>}
  </main>;
}
