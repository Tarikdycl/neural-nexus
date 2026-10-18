import React, { useEffect, useState } from 'react';
import './LastArchive.css';

const CASE = {
  title: 'The Tea in the Harbor', place: 'BOSTON HARBOR', date: 'DECEMBER 16, 1773',
  intro: 'Three ships sit in Boston Harbor. Merchants argue, protesters gather, and the tea remains aboard. Your archive has lost the reason this night became famous.',
  fragments: [
    {id:'tax',title:'Taxation dispute',text:'Many colonists objected to taxation by a Parliament in which they had no elected representatives.'},
    {id:'tea',title:'The Tea Act',text:'The 1773 Tea Act altered how the East India Company could sell tea in the colonies; tensions over taxation and trade continued.'},
    {id:'ships',title:'The harbor',text:'On December 16, protesters boarded ships and destroyed large quantities of tea in Boston Harbor.'}
  ],
  actions: [
    {id:'inspect',label:'Inspect the cargo documents',outcome:'You preserve shipping evidence for the Archive. The political dispute remains unresolved.'},
    {id:'interview',label:'Interview people at the harbor',outcome:'You record conflicting perspectives from the harbor, preserving voices for future comparison.'},
    {id:'record',label:'Record the unfolding protest',outcome:'You document the destruction of tea and return with an eyewitness account.'}
  ]
};

export default function LastArchive({onExit}) {
  const [phase,setPhase]=useState('brief');
  const [seconds,setSeconds]=useState(60);
  const [found,setFound]=useState([]);
  const [choice,setChoice]=useState(null);
  const [testimony,setTestimony]=useState('');
  const [answer,setAnswer]=useState('');
  const [result,setResult]=useState(null);
  const [run,setRun]=useState(0);

  useEffect(()=>{
    if(phase!=='crisis')return;
    const id=setInterval(()=>setSeconds(s=>Math.max(0,s-1)),1000);
    return ()=>clearInterval(id);
  },[phase,run]);
  useEffect(()=>{if(phase==='crisis' && seconds===0)setPhase('fracture');},[seconds,phase]);
  useEffect(()=>{
    if(phase!=='fracture')return;
    const id=setTimeout(()=>setPhase('court'),1900);
    return ()=>clearTimeout(id);
  },[phase]);

  const selected=CASE.actions.find(x=>x.id===choice);
  function begin(){setSeconds(60);setFound([]);setChoice(null);setTestimony('');setAnswer('');setResult(null);setRun(n=>n+1);setPhase('crisis');}
  function collect(id){setFound(prev=>prev.includes(id)?prev:[...prev,id]);}
  function finalize(){setPhase('fracture');}
  function judge(){
    const combined=(testimony+' '+answer).toLowerCase();
    const rules=[
      {label:'Historical context',match:/tax|represent|parliament|tea act|east india|trade|colon|protest/,tip:'Explain the taxation, trade and representation dispute.'},
      {label:'Evidence',match:/ship|cargo|document|merchant|witness|harbor|tea|source/,tip:'Connect at least one observed source to your claim.'},
      {label:'Cause and effect',match:/because|therefore|led to|caused|so that|as a result|due to|since/,tip:'Explain why the evidence supports your interpretation.'}
    ];
    const hits=rules.map(r=>r.match.test(combined));
    setResult({hits,notes:rules.filter((r,i)=>!hits[i]).map(r=>r.tip)});
    setPhase('verdict');
  }
  return <main className={'archive-app archive-'+phase}>
    <header className="archive-header"><button onClick={onExit} className="archive-link">← Neural Nexus</button><span className="archive-mark">◈ THE LAST ARCHIVE</span><span className="archive-tag">PROTOTYPE · LOCAL DEMO</span></header>
    {phase==='brief' && <section className="archive-center archive-fade"><div className="archive-kicker">YEAR 2847 · THE GREAT ERASURE</div><h1>History has vanished.<br/><em>Recover what remains.</em></h1><p>You are a Chrono Agent. Enter a lost moment, collect evidence before extraction, then defend your historical account before the Archivist.</p><div className="archive-briefbox"><span>ARCHIVE CASE 001</span><strong>{CASE.title}</strong><small>{CASE.place} · {CASE.date}</small></div><button className="archive-primary" onClick={begin}>Begin 60-second mission →</button></section>}
    {phase==='crisis' && <section className="archive-container archive-fade">
      <div className="archive-status"><span>MISSION 001 · {CASE.place} · {CASE.date}</span><div className={'archive-count '+(seconds<=10?'urgent':'')}>{String(Math.floor(seconds/60)).padStart(2,'0')}:{String(seconds%60).padStart(2,'0')}</div></div>
      <div className="archive-grid"><div className="archive-story"><div className="archive-scenery"><span>THE HARBOR · NIGHTFALL</span><div className="archive-ship">⚓</div></div><div className="archive-panel"><div className="archive-kicker">RECOVER THE LOST MOMENT</div><h1>{CASE.title}</h1><p>{CASE.intro}</p><div className="archive-kicker">CHOOSE YOUR ACTION</div><div className="archive-actions">{CASE.actions.map(a=><button key={a.id} onClick={()=>setChoice(a.id)} className={choice===a.id?'active':''}>{a.label}{choice===a.id?' ✓':''}</button>)}</div><label className="archive-label" htmlFor="testimony">Why this action? (optional)</label><textarea id="testimony" maxLength={600} rows={2} placeholder="I chose this because..." value={testimony} onChange={e=>setTestimony(e.target.value)}/><button className="archive-primary" disabled={!choice} onClick={finalize}>Extract to the Court of Time →</button></div></div>
      <aside className="archive-evidence"><div className="archive-kicker">HISTORICAL FRAGMENTS</div><h2>Evidence recovered <span>{found.length}/3</span></h2><p>Investigate fragments before time expires. The Court will ask you to explain what happened.</p>{CASE.fragments.map(f=><button key={f.id} className={'archive-fragment '+(found.includes(f.id)?'opened':'')} onClick={()=>collect(f.id)}><b>{found.includes(f.id)?'◈':'◇'} {f.title}</b><span>{found.includes(f.id)?f.text:'Click to examine this historical clue'}</span></button>)}</aside></div>
    </section>}
    {phase==='fracture' && <section className="archive-center archive-break"><div className="archive-ring">◈</div><div className="archive-kicker">TEMPORAL EXTRACTION COMPLETE</div><h1>TIME IS CALLED.</h1><p>All testimony will now be examined.</p></section>}
    {phase==='court' && <section className="archive-container archive-fade"><div className="archive-court-hero"><div className="archive-kicker">THE COURT OF TIME · CASE 001</div><h1>Reconstruct the truth.</h1><p>Your mission is over. Your explanation begins.</p></div><div className="archive-court-layout"><div className="archive-panel archive-archivist"><div className="archive-avatar">◈</div><div className="archive-kicker">THE ARCHIVIST</div><h2>Agent, what happened in Boston Harbor?</h2><p>Explain what led to the destruction of tea in 1773. Distinguish what you observed from what you infer, and tell me why your evidence supports the explanation.</p><div className="archive-quote">“History cannot be restored by confidence alone. Show me your reasoning.”</div></div><div className="archive-panel"><div className="archive-kicker">YOUR CASE FILE</div><strong>{selected?.label || 'No action selected before extraction'}</strong><p>{selected?.outcome || 'The archive recorded an incomplete field mission.'}</p><small>{found.length} historical fragments recovered</small><div className="archive-evidence-list">{CASE.fragments.filter(f=>found.includes(f.id)).map(f=><details key={f.id}><summary>{f.title}</summary><p>{f.text}</p></details>)}</div><label className="archive-label" htmlFor="answer">Your defense</label><textarea id="answer" rows={5} maxLength={1500} value={answer} onChange={e=>setAnswer(e.target.value)} placeholder="The event happened because... I base this explanation on..."/><button className="archive-primary" onClick={judge} disabled={answer.trim().length<25}>Submit testimony →</button></div></div></section>}
    {phase==='verdict' && <section className="archive-center archive-fade"><div className="archive-kicker">ARCHIVE ASSESSMENT · CASE 001</div><h1>The record survives.</h1><p>This prototype checks for signs of historical context, evidence and causal explanation. It is <strong>not</strong> an AI-graded historical accuracy assessment yet.</p><div className="archive-report">{['Historical context','Evidence referenced','Cause-and-effect reasoning'].map((name,i)=><div key={name}><span>{name}</span><strong>{result?.hits[i]?'Recognized':'Needs elaboration'}</strong></div>)}</div>{result?.notes.length>0&&<p className="archive-guidance">{result.notes.join(' ')}</p>}<div className="archive-final"><b>Recovered fragments: {found.length}/3</b><span>Historical archive restoration will be connected to Oracle Database in the next integration.</span></div><button className="archive-primary" onClick={begin}>Replay mission ↻</button><button className="archive-link" onClick={onExit}>Return to Neural Nexus</button></section>}
  </main>;
}
