import React, { useState } from 'react';

const artifacts = [
  { id:'sword', name:'The Sword', role:'Warrior', description:'Learn by doing', symbol:'⚔' },
  { id:'staff', name:'The Staff', role:'Mage', description:'Learn by experimenting', symbol:'♜' },
  { id:'book', name:'The Book', role:'Scholar', description:'Learn by investigating', symbol:'▤' },
  { id:'compass', name:'The Compass', role:'Explorer', description:'Learn by discovering', symbol:'✥' },
];

export default function GuardianChoice({ busy, error, onChoose }) {
  const [selected, setSelected] = useState(null);
  return (
    <div className="guardian-screen">
      <div className="guardian-intro">
        <span className="eyebrow">THE GUARDIAN'S CHOICE</span>
        <h1>Who will you become?</h1>
        <p>An ancient guardian waits. Four relics rest on the altar. One path will be yours.</p>
      </div>
      <>
          <div className="guardian-grid">
            {artifacts.map(item => (
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
