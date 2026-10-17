import React, { useEffect, useRef, useState } from 'react';

const pages = [
  {
    left: { eyebrow: 'CHAPTER I · THE ODYSSEY', title: 'The First Shore', body: 'The island is quiet. For now.', note: 'A journey begins not with certainty, but with a step.' },
    right: { eyebrow: 'FIELD NOTES', title: 'A Blank Map', body: 'The pages ahead have yet to be written.', note: 'Significant discoveries and lessons will find their place here.' },
  },
  {
    left: { eyebrow: 'REFLECTIONS', title: 'What I Have Learned', body: 'Every choice leaves a trace.', note: 'Concepts practiced during your journey will appear here once the learning system is connected.' },
    right: { eyebrow: 'MILESTONES', title: 'Still Unwritten', body: 'Some stories take time.', note: 'Verified story milestones will be preserved here in future updates.' },
  },
];

function Page({ entry, side }) {
  return (
    <section className={'journal-page journal-page-' + side}>
      <div className="journal-page-ornament" aria-hidden="true">✦</div>
      <span className="journal-page-eyebrow">{entry.eyebrow}</span>
      <h3>{entry.title}</h3>
      <p className="journal-page-body">{entry.body}</p>
      <div className="journal-page-rule" />
      <p className="journal-page-note">{entry.note}</p>
      <span className="journal-page-number">{side === 'left' ? 'I' : 'II'}</span>
    </section>
  );
}

export default function JournalBook({ open, onClose }) {
  const [spread, setSpread] = useState(0);
  const closeRef = useRef(null);
  useEffect(() => {
    if (!open) return;
    const previouslyFocused = document.activeElement;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    closeRef.current?.focus();
    function onKey(event) {
      if (event.key === 'Escape') onClose();
      if (event.key === 'ArrowRight') setSpread(s => Math.min(s + 1, pages.length - 1));
      if (event.key === 'ArrowLeft') setSpread(s => Math.max(0, s - 1));
      if (event.key === 'Tab') {
        const focusables = Array.from(document.querySelectorAll('.journal-dialog button:not(:disabled)'));
        const index = focusables.indexOf(document.activeElement);
        if (event.shiftKey && index === 0) { event.preventDefault(); focusables[focusables.length - 1]?.focus(); }
        else if (!event.shiftKey && index === focusables.length - 1) { event.preventDefault(); focusables[0]?.focus(); }
      }
    }
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = previousOverflow;
      previouslyFocused?.focus?.();
    };
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="journal-backdrop" onMouseDown={event => { if (event.target === event.currentTarget) onClose(); }}>
      <div className="journal-dialog" role="dialog" aria-modal="true" aria-label="The Traveler's Journal">
        <header className="journal-dialog-top">
          <div><span className="journal-dialog-eyebrow">THE ODYSSEY</span><h2>The Traveler's Journal</h2></div>
          <button ref={closeRef} type="button" className="journal-close" onClick={onClose} aria-label="Close journal">×</button>
        </header>
        <div className="journal-book-spread" key={spread}>
          <Page entry={pages[spread].left} side="left" />
          <Page entry={pages[spread].right} side="right" />
        </div>
        <footer className="journal-controls">
          <button type="button" onClick={() => setSpread(s => Math.max(0, s - 1))} disabled={spread === 0}>← Previous</button>
          <span>{spread + 1} / {pages.length}</span>
          <button type="button" onClick={() => setSpread(s => Math.min(pages.length - 1, s + 1))} disabled={spread === pages.length - 1}>Next →</button>
        </footer>
        <p className="journal-demo-note">A preview of your journal. AI milestone entries and learning records are not connected yet.</p>
      </div>
    </div>
  );
}
