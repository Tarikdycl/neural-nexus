import React from 'react';

export default function LandingPage({ onBegin }) {
  return (
    <main className="landing">
      <div className="landing-content">
        <div className="eyebrow">NEURAL NEXUS <span className="landing-separator">/</span> INTERACTIVE STORYTELLING</div>
        <h1>Dwell Into<br /><em>the Realms.</em></h1>
        <p>Step beyond the page. Explore extraordinary worlds where every choice becomes part of your story.</p>
        <button className="primary-button" onClick={onBegin}>Begin Your Journey <span aria-hidden="true">→</span></button>
      </div>
      <div className="landing-footnote">A STORY ONLY YOU CAN TELL</div>
    </main>
  );
}
