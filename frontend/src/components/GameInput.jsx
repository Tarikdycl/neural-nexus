import { useState } from 'react';

export default function GameInput({ onSubmit, disabled }) {
  const [draft, setDraft] = useState('');
  function submit(event) {
    event.preventDefault();
    const value = draft.trim();
    if (!value || disabled) return;
    if (onSubmit(value)) setDraft('');
  }
  return (
    <form className="game-composer" onSubmit={submit}>
      <label className="sr-only" htmlFor="player-action">Your next action</label>
      <input id="player-action" value={draft} onChange={e => setDraft(e.target.value)} placeholder="What will you do next?" disabled={disabled} autoComplete="off" />
      <button type="submit" aria-label="Send action" disabled={disabled || !draft.trim()}>↑</button>
    </form>
  );
}
