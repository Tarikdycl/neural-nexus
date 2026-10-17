import React from 'react';
export default function LandingPage({ onBegin }) {
  return (
    <main className="landing">
      <div className="landing-art" aria-hidden="true"><span className="sun-disc" /><span className="arch arch-outer" /><span className="arch arch-inner" /><span className="landscape" /></div>
      <div className="landing-content">
        <div className="eyebrow">NEURAL NEXUS · INTERACTIVE STORYTELLING</div>
        <h1>Dwell Into<br /><em>the Realms.</em></h1>
        <p>Step beyond the page. Explore extraordinary worlds where every choice becomes part of your story.</p>
        <button className="primary-button" onClick={onBegin}>Begin Your Journey <span aria-hidden="true">→</span></button>
        <div className="landing-footnote">A STORY ONLY YOU CAN TELL</div>
      </div>
    </main>
  );
}
