import React, { useEffect, useMemo, useRef, useState } from 'react';

// Presentation contract: journal.storyEntries / learningEntries / decisionEntries.
// These are populated only from actual saved game data; no achievements are fabricated.
function toPages(journal) {
  const groups = [
    ['STORY', journal?.storyEntries],
    ['LEARNING', journal?.learningEntries],
    ['DECISIONS', journal?.decisionEntries],
  ];
  const entries = groups.flatMap(([section, items]) =>
    (Array.isArray(items) ? items : []).filter(item => item && typeof item.body === 'string' && item.body.trim())
      .map(item => ({ ...item, section }))
  );
  if (!entries.length) return [
    { section: 'CHAPTER I · THE ODYSSEY', title: 'The First Shore', subtitle: 'Moonlit Clearing', body: 'The island is quiet. For now.', note: 'A quiet beginning.', opening: true },
    { section: 'FIELD NOTES', title: '', empty: true, note: '' },
  ];
  return entries;
}

function JournalPage({ entry, number, customNote, onNoteChange }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState('');
  const hasCustomNote = typeof customNote === 'string';
  const note = hasCustomNote ? customNote : (entry?.note || '');
  function beginEdit() { setDraft(note); setEditing(true); }
  function saveEdit() { onNoteChange(number, draft.slice(0, 500)); setEditing(false); }
  return (
    <section className={'journal-page' + (entry?.empty || !entry ? ' journal-page-empty' : '')}>

      {entry ? (
        <div className="journal-page-content">
          <span className="journal-page-eyebrow">{entry.section}</span>
          {!entry.empty && <h3>{entry.title || 'A new chapter'}</h3>}
          {!entry.empty && (
            <>
              {entry.subtitle && <p className="journal-page-subtitle">{entry.subtitle}</p>}
              <p className="journal-page-body">{entry.body}</p>
              {Array.isArray(entry.tags) && entry.tags.length > 0 && (
                <div className="journal-tag-list">{entry.tags.map(tag => <span className="journal-tag" key={tag}>{tag}</span>)}</div>
              )}
            </>
          )}

        </div>
      ) : (
        <div className="journal-page-content journal-unwritten"><span className="journal-page-eyebrow">FIELD NOTES</span></div>
      )}
      <div className={'journal-personal-note' + (entry?.empty ? ' journal-personal-note--inline' : '')}>
        {entry?.empty ? (
          <textarea
            className="journal-inline-editor"
            aria-label="Field notes"
            placeholder="Write a note…"
            value={hasCustomNote ? customNote : ''}
            maxLength={500}
            rows={7}
            onChange={event => onNoteChange(number, event.target.value)}
          />
        ) : editing ? (
          <>
            <label className="journal-note-label" htmlFor={'journal-note-' + number}>Personal note</label>
            <textarea id={'journal-note-' + number} value={draft} maxLength={500} rows={3} onChange={e => setDraft(e.target.value)} />
            <div className="journal-note-actions"><button type="button" onClick={saveEdit}>Save</button><button type="button" onClick={() => setEditing(false)}>Cancel</button></div>
          </>
        ) : (
          <>
            {note && <p className="journal-page-note">{note}</p>}
            <button className="journal-edit-note" type="button" onClick={beginEdit}>{hasCustomNote ? 'Edit note' : 'Write a note…'}</button>
          </>
        )}
      </div>
      <span className="journal-page-number">{number}</span>
    </section>
  );
}

export default function JournalBook({ open, onClose, journal, sessionId }) {
  const [spread, setSpread] = useState(0);
  const closeRef = useRef(null);
  const storageKey = 'neural-nexus-journal-notes:' + (sessionId || 'preview');
  const [notes, setNotes] = useState({});
  useEffect(() => {
    try {
      const stored = JSON.parse(localStorage.getItem(storageKey) || '{}');
      setNotes(stored && typeof stored === 'object' && !Array.isArray(stored) ? stored : {});
    } catch { setNotes({}); }
  }, [storageKey]);
  function changeNote(number, note) {
    setNotes(previous => {
      const next = { ...previous, [number]: note };
      try { localStorage.setItem(storageKey, JSON.stringify(next)); } catch { /* Storage might be disabled. */ }
      return next;
    });
  }
  const entries = useMemo(() => toPages(journal), [journal]);
  const totalSpreads = Math.max(1, Math.ceil(entries.length / 2));
  useEffect(() => {
    if (!open) { setSpread(0); return; }
    const previousFocus = document.activeElement;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    closeRef.current?.focus();
    function onKey(event) {
      if (event.key === 'Escape') onClose();
      if (event.key === 'ArrowRight') setSpread(v => Math.min(v + 1, totalSpreads - 1));
      if (event.key === 'ArrowLeft') setSpread(v => Math.max(0, v - 1));
      if (event.key === 'Tab') {
        const buttons = [...document.querySelectorAll('.journal-dialog button:not(:disabled)')];
        if (!buttons.length) return;
        const i = buttons.indexOf(document.activeElement);
        if (event.shiftKey && i === 0) { event.preventDefault(); buttons[buttons.length - 1].focus(); }
        if (!event.shiftKey && i === buttons.length - 1) { event.preventDefault(); buttons[0].focus(); }
      }
    }
    document.addEventListener('keydown', onKey);
    return () => { document.removeEventListener('keydown', onKey); document.body.style.overflow = previousOverflow; previousFocus?.focus?.(); };
  }, [open, onClose, totalSpreads]);
  if (!open) return null;
  return (
    <div className="journal-backdrop" onMouseDown={event => { if (event.target === event.currentTarget) onClose(); }}>
      <div className="journal-dialog" role="dialog" aria-modal="true" aria-label="The Traveler's Journal">
        <header className="journal-dialog-top">
          <div><span className="journal-dialog-eyebrow">THE ODYSSEY</span><h2>The Traveler's Journal</h2></div>
          <button ref={closeRef} type="button" className="journal-close" onClick={onClose} aria-label="Close journal">×</button>
        </header>
        <div className="journal-book-spread" key={spread}>
          <JournalPage entry={entries[spread * 2]} number={spread * 2 + 1} customNote={notes[spread * 2 + 1]} onNoteChange={changeNote} />
          <JournalPage entry={entries[spread * 2 + 1]} number={spread * 2 + 2} customNote={notes[spread * 2 + 2]} onNoteChange={changeNote} />
        </div>
        <footer className="journal-controls">
          <button type="button" onClick={() => setSpread(v => Math.max(0, v - 1))} disabled={spread === 0}>← Previous</button>
          <span>{spread + 1} / {totalSpreads}</span>
          <button type="button" onClick={() => setSpread(v => Math.min(totalSpreads - 1, v + 1))} disabled={spread >= totalSpreads - 1}>Next →</button>
        </footer>
      </div>
    </div>
  );
}
