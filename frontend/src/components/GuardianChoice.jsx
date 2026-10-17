import React, { useState } from 'react';

const REALM_CHOICES = {
  odyssey_island: {
    prompt: 'Four paths await beneath the olive trees. Which will you follow?',
    items: [
      { id: 'helm', name: 'The Helm', role: 'Ship Captain', description: 'Navigate and lead', symbol: '⚓' },
      { id: 'sword', name: 'The Sword', role: 'Warrior', description: 'Courage in action', symbol: '⚔' },
      { id: 'banner', name: 'The Banner', role: 'General', description: 'Plan and command', symbol: '⚑' },
      { id: 'bow', name: 'The Bow', role: 'Archer', description: 'Observe and aim', symbol: '➶' },
    ],
  },
  monkey_king: {
    prompt: 'A mountain spirit offers four paths. Which calls to you?',
    items: [
      { id: 'staff', name: 'The Staff', role: 'Staff Adept', description: 'Skill through practice', symbol: '♜' },
      { id: 'scroll', name: 'The Scroll', role: 'Sage', description: 'Study ancient wisdom', symbol: '▤' },
      { id: 'cloud', name: 'The Cloud', role: 'Cloud Wanderer', description: 'Explore the unknown', symbol: '☁' },
      { id: 'seal', name: 'The Seal', role: 'Guardian', description: 'Protect and endure', symbol: '◇' },
    ],
  },
  demi_demon: {
    prompt: 'Four relics lie in the shadows. Choose carefully.',
    items: [
      { id: 'blade', name: 'The Blade', role: 'Hunter', description: 'Face the unknown', symbol: '⚔' },
      { id: 'grimoire', name: 'The Grimoire', role: 'Occultist', description: 'Uncover old magic', symbol: '▤' },
      { id: 'mask', name: 'The Mask', role: 'Infiltrator', description: 'Read hidden intentions', symbol: '◈' },
      { id: 'lantern', name: 'The Lantern', role: 'Seeker', description: 'Find what is lost', symbol: '✥' },
    ],
  },
};

export default function GuardianChoice({ realmId = 'odyssey_island', busy, error, onChoose }) {
  const realm = REALM_CHOICES[realmId] || REALM_CHOICES.odyssey_island;
  const [selected, setSelected] = useState(null);
  return (
    <div className="guardian-screen">
      <div className="guardian-intro">
        <span className="eyebrow">THE GUARDIAN'S CHOICE</span>
        <h1>Who will you become?</h1>
        <p>{realm.prompt}</p>
      </div>
      <>
          <div className="guardian-grid">
            {realm.items.map(item => (
              <button type="button" key={item.id} disabled={busy} className={'guardian-artifact' + (selected === item.id ? ' is-selected' : '')} onClick={() => setSelected(item.id)}>
                <span className="guardian-symbol" aria-hidden="true">{item.symbol}</span>
                <strong>{item.name}</strong>
                <span className="guardian-role">{item.role}</span>
                <small>{item.description}</small>
              </button>
            ))}
          </div>
          <button className="guardian-confirm" type="button" disabled={!selected || busy} onClick={() => onChoose(selected)}>
            {busy ? 'Choosing…' : selected ? 'Choose my path →' : 'Select a relic'}
          </button>
      </>
      {error && <p className="inline-error" role="alert">{error}</p>}
    </div>
  );
}
