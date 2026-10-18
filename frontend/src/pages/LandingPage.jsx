import React from 'react';
import './LandingPage.css';

export default function LandingPage({ onArchive }) {
  return (
    <main className="history-landing">
      <div className="history-landing-art" aria-hidden="true" />
      <div className="history-landing-shade" aria-hidden="true" />
      <header className="history-landing-header">
        <span className="history-brand"><span className="history-brand-symbol">◈</span> NEURAL NEXUS</span>
        <span className="history-header-note">THE LAST ARCHIVE · 2847</span>
      </header>
      <section className="history-landing-hero">
        <div className="history-hero-kicker">THE PAST IS WAITING</div>
        <h1>History isn't written.<br /><em>It's witnessed.</em></h1>
        <p>Enter the moments that changed the world.</p>
        <button type="button" className="history-hero-cta" onClick={onArchive}>
          Explore history <span aria-hidden="true">↗</span>
        </button>
      </section>
      <footer className="history-landing-footer">
        <span>TRAVEL THROUGH TIME</span>
        <span>DISCOVER · QUESTION · REMEMBER</span>
      </footer>
    </main>
  );
}
