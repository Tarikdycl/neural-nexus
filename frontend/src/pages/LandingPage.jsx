import React from 'react';

export default function LandingPage({ onBegin, onArchive }) {
  return (
    <main className="landing landing-cinematic">
      <div className="landing-atmosphere" aria-hidden="true">
        <div className="landing-sky" />
        <div className="landing-haze" />
      </div>
      <div className="landing-content">
        <h1>Dwell Into<br /><em>the Realms.</em></h1>
        <button className="primary-button" onClick={onArchive}>Play The Last Archive · 60 Seconds <span aria-hidden="true">→</span></button>
        <div style={{marginTop:16}}><button className="text-button" onClick={onBegin}>Explore original realms →</button></div>
      </div>
    </main>
  );
}
