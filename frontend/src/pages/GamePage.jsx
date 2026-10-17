import React, { useState } from 'react';
import Inventory from '../components/Inventory.jsx';
import StoryChat from '../components/StoryChat.jsx';
import GameInput from '../components/GameInput.jsx';

export default function GamePage({ session, messages, busy, error, onAction, onBack, onSave }) {
  const [showDetails, setShowDetails] = useState(false);
  const world = session.world;
  const exits = world.exits && typeof world.exits === 'object' ? Object.entries(world.exits) : [];
  return (
    <main className="game-page">
      <header className="game-topbar">
        <button className="text-button back-link" onClick={onBack}>← Realms</button>
        <div className="topbar-brand"><span className="small-eyebrow">THE ODYSSEY</span><span className="topbar-divider">/</span><span>Neural Nexus</span></div>
        <div className="topbar-actions"><button className="text-button mobile-details" onClick={() => setShowDetails(v => !v)} aria-expanded={showDetails}>Details</button><button className="save-button" onClick={onSave}>Save Game</button></div>
      </header>
      <div className={'game-layout ' + (showDetails ? 'details-open' : '')}>
        <section className="game-main">
          <div className="chapter-header"><span className="eyebrow">CURRENT LOCATION · TURN {world.turn}</span><h1>{world.location}</h1><p>{world.description}</p></div>
          <StoryChat messages={messages} busy={busy} />
          <div className="game-input-area">
            {error && <div className="inline-error" role="alert">{error}</div>}
            <div className="quick-actions">
              <button disabled={busy} onClick={() => onAction('look')}>Look around</button>
              <button disabled={busy} onClick={() => onAction('search')}>Search</button>
              {exits.map(([direction, place]) => <button disabled={busy} key={direction} onClick={() => onAction('move', direction)}>Go: {place}</button>)}
            </div>
            <GameInput disabled={busy} onSubmit={onAction} />
            <p className="input-hint">Try “look”, “search”, “take [item]”, or “move [direction]”. AI free-form actions are coming soon.</p>
          </div>
        </section>
        <Inventory world={world} onTake={id => onAction('take', id)} busy={busy} />
      </div>
    </main>
  );
}
