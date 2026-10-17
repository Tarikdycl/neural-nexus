import React, { useState } from 'react';
import Inventory from '../components/Inventory.jsx';
import GuardianChoice from '../components/GuardianChoice.jsx';
import JournalBook from '../components/JournalBook.jsx';
import StoryChat from '../components/StoryChat.jsx';
import GameInput from '../components/GameInput.jsx';

export default function GamePage({ session, messages, busy, error, onAction, onBack, onSave, onChoose, onChallenge }) {
  const [showDetails, setShowDetails] = useState(false);
  const [showJournal, setShowJournal] = useState(false);
  const world = session.world;
  const exits = world.exits && typeof world.exits === 'object' ? Object.entries(world.exits) : [];

  if (!world.challenge_solved) return <main className="game-page guardian-game-page"><header className="game-topbar"><button className="text-button back-link" onClick={onBack}>← Realms</button><span className="game-realm-name">The Odyssey</span><div className="topbar-actions"><button className="journal-open-button" onClick={() => setShowJournal(true)}>Journal</button></div></header><GuardianChoice world={world} busy={busy} error={error} onChoose={onChoose} onChallenge={onChallenge} /><JournalBook open={showJournal} onClose={() => setShowJournal(false)} journal={world.journal} sessionId={session.session_id} /></main>;

  return (
    <main className="game-page">
      <header className="game-topbar">
        <button className="text-button back-link" onClick={onBack}>← Realms</button>
        <span className="game-realm-name">The Odyssey</span>
        <div className="topbar-actions">
          <button className="text-button mobile-details" onClick={() => setShowDetails(value => !value)} aria-expanded={showDetails} aria-controls="game-details">Details</button>
          <button className="journal-open-button" type="button" onClick={() => setShowJournal(true)} aria-label="Open traveler journal"><span aria-hidden="true">▤</span> Journal</button>
          <button className="save-button" onClick={onSave} title="Remember this session in your browser">Save</button>
        </div>
      </header>

      <div className={'game-layout' + (showDetails ? ' details-open' : '')}>
        <section className="game-main" aria-label="Interactive story">
          <div className="chapter-header">
            <span className="eyebrow">THE ODYSSEY <span aria-hidden="true">·</span> TURN {world.turn}</span>
            <h1>{world.location}</h1>
            {world.description && <p>{world.description}</p>}
          </div>

          <StoryChat messages={messages} busy={busy} />

          <div className="game-input-area">
            {error && <div className="inline-error" role="alert">{error}</div>}
            <div className="quick-actions" aria-label="Available actions">
              <button disabled={busy} onClick={() => onAction('look')}>Look around</button>
              <button disabled={busy} onClick={() => onAction('search')}>Search</button>
              {exits.map(([direction, place]) =>
                <button disabled={busy} key={direction} onClick={() => onAction('move', direction)}>Go to {place} →</button>
              )}
            </div>
            <GameInput disabled={busy} onSubmit={onAction} />
            <p className="input-hint">Enter to send · Available commands: look, search, take, move</p>
          </div>
        </section>

        <div className="game-details-panel" id="game-details">
          <Inventory world={world} busy={busy} onTake={id => onAction('take', id)} />
        </div>
      </div>
      <JournalBook open={showJournal} onClose={() => setShowJournal(false)} journal={world.journal} sessionId={session.session_id} />
    </main>
  );
}
