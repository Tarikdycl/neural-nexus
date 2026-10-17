import React from 'react';

export default function LandingPage({ onBegin }) {
  return (
    <main className="landing landing-cinematic">
      <div className="landing-atmosphere" aria-hidden="true">
        <div className="landing-sky" />
        <div className="landing-haze" />
      </div>
      <div className="landing-content">
        <h1>Dwell Into<br /><em>the Realms.</em></h1>
        <button className="primary-button" onClick={onBegin}>Begin Your Journey <span aria-hidden="true">→</span></button>
      </div>
    </main>
  );
}
