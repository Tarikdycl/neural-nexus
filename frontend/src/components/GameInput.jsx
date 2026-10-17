import React, { useState } from 'react';

export default function GameInput({ onSubmit, disabled }) {
  const [draft, setDraft] = useState('');
  async function submit(event) {
    event.preventDefault();
    const value = draft.trim();
    if (!value || disabled) return;
    setDraft('');
    const accepted = await onSubmit(value);
    if (!accepted) setDraft(previous => previous || value);
  }
  return (
    <form className="game-composer" onSubmit={submit}>
      <label className="sr-only" htmlFor="player-action">Your next action</label>
      <input id="player-action" value={draft} onChange={e => setDraft(e.target.value)} placeholder="What will you do next?" disabled={disabled} autoComplete="off" />
      <button type="submit" aria-label="Send action" disabled={disabled || !draft.trim()}>↑</button>
    </form>
  );
}
