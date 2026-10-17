import React from 'react';

const realms = [
  { id: 'odyssey_island', name: 'The Odyssey', description: 'A journey through ancient Greek mythology.', available: true },
  { id: 'monkey_king', name: "The Monkey King's Realm", description: 'A world of legends, magic, and adventure.', available: false },
  { id: 'demi_demon', name: 'The Demi-Demon Mystery', description: 'An unfamiliar world, full of secrets.', available: false },
];

export default function RealmsPage({ onBack, onEnter, busy }) {
  return (
    <main className="realms-page page-wrap">
      <button className="text-button" onClick={onBack}>← Back</button>
      <div className="section-intro"><h1>Choose a realm.</h1></div>
      <div className="realm-grid">
        {realms.map(realm => (
          <article className="realm-card" key={realm.id}>
            <div className="realm-card-body">
              <h2>{realm.name}</h2>
              <p>{realm.description}</p>
              <button className="card-link" disabled={!realm.available || busy} onClick={() => onEnter(realm.id)}>
                {realm.available ? 'Enter Realm →' : 'Coming soon'}
              </button>
            </div>
          </article>
        ))}
      </div>
    </main>
  );
}
