import React, { useEffect, useState } from 'react';
import './LandingPage.css';

export default function LandingPage({ onArchive, onSavedVisits }) {
  const [hasVisits, setHasVisits] = useState(false);

  useEffect(() => {
    let active = true;
    fetch('/archive/saves?limit=1')
      .then(response => {
        if (!response.ok) throw new Error('Unable to load visits');
        return response.json();
      })
      .then(data => { if (active) setHasVisits(Array.isArray(data.saves) && data.saves.length > 0); })
      .catch(() => { if (active) setHasVisits(false); });
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
          {hasVisits && <button type="button" className="history-hero-saved" onClick={onSavedVisits}>
            Saved Visits <span aria-hidden="true">→</span>
          </button>}
        </div>
      </section>
      <footer className="history-landing-footer">
        <span>RECOVER THE PAST</span>
        <span>EXPLORE · DISCOVER · RESTORE</span>
      </footer>
    </main>
  );
}
