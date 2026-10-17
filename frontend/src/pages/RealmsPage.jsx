import React from 'react';

const realms = [
  { id: 'odyssey_island', name: 'The Odyssey', description: 'Ancient Greek mythology.', image: '/realms/odyssey.png', available: true },
  { id: 'monkey_king', name: "The Monkey King's Realm", description: 'Legends and magic.', image: '/realms/monkey-king.png', available: false },
  { id: 'demi_demon', name: 'The Demi-Demon Mystery', description: 'A world of secrets.', image: '/realms/demi-demon.png', available: false },
];

export default function RealmsPage({ onBack, onEnter, busy }) {
  return (
    <main className="realms-page page-wrap">
      <button className="text-button" onClick={onBack}>← Back</button>
      <div className="section-intro"><h1>Choose a realm.</h1></div>
      <div className="realm-grid">
        {realms.map(realm => (
          <article className={'realm-card' + (realm.available ? ' realm-card-active' : ' realm-card-upcoming')} key={realm.id}>
            {realm.available ? (
              <button className="realm-card-surface" disabled={busy} onClick={() => onEnter(realm.id)} aria-label={'Enter ' + realm.name}>
                <img className="realm-cover" src={realm.image} alt="" />
                <span className="realm-card-copy">
                  <span className="realm-card-title">{realm.name}</span>
                  <span className="realm-card-description">{realm.description}</span>
                </span>
                <span className="realm-card-action">Enter realm <span aria-hidden="true">→</span></span>
              </button>
            ) : (
              <div className="realm-card-surface">
                <img className="realm-cover" src={realm.image} alt="" loading="lazy" />
                <span className="realm-card-copy">
                  <span className="realm-card-title">{realm.name}</span>
                  <span className="realm-card-description">{realm.description}</span>
                </span>
                <span className="realm-card-action realm-card-disabled">Coming soon</span>
              </div>
            )}
          </article>
        ))}
      </div>
    </main>
  );
}
