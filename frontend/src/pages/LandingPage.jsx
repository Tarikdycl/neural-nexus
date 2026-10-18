import React from 'react';
import './LandingPage.css';

export default function LandingPage({ onArchive, onSavedVisits }) {
  return () => { active = false; };
  }, []);

  return (
    <main className="history-landing">
      <div className="history-landing-art" aria-hidden="true" />
      <div className="history-landing-shade" aria-hidden="true" />
      <header className="history-landing-header">
        <span className="history-brand"><span className="history-brand-symbol">◈</span> NEURAL NEXUS</span>
        <span className="history-header-note">CHRONO BUREAU · 2978</span>
      </header>
      <section className="history-landing-hero">
        <h1>The Last <em>Archive.</em></h1>
        <p>Help restore the missing pieces of history from the year 2978.</p>
        <div className="history-landing-actions">
          <button type="button" className="history-hero-cta" onClick={onArchive}>
            Enter the archive <span aria-hidden="true">↗</span>
          </button>
          <button type="button" className="history-hero-saved" onClick={onSavedVisits}>
            Saved Visits <span aria-hidden="true">→</span>
          </button>
        </div>
      </section>
      <footer className="history-landing-footer">
        <span>RECOVER THE PAST</span>
        <span>EXPLORE · DISCOVER · RESTORE</span>
      </footer>
    </main>
  );
}
