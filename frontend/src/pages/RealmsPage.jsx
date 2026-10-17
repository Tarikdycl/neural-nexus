const realms = [
  { id: 'odyssey_island', number: '01', name: 'The Odyssey', category: 'ANCIENT MYTHOLOGY', description: 'Sail into ancient Greek mythology, where distant shores hold forgotten secrets.', available: true, art: 'odyssey' },
  { id: 'monkey_king', number: '02', name: "The Monkey King's Realm", category: 'LEGEND & WONDER', description: 'Journey through a magical land inspired by the legendary monkey heroes.', available: false, art: 'monkey' },
  { id: 'demi_demon', number: '03', name: 'The Demi-Demon Mystery', category: 'MYSTERY & FANTASY', description: 'Uncover the secrets waiting within a strange and unfamiliar world.', available: false, art: 'demon' },
];

export default function RealmsPage({ onBack, onEnter, busy }) {
  return (
    <main className="realms-page page-wrap">
      <button className="text-button" onClick={onBack}>← Back</button>
      <div className="section-intro"><div className="eyebrow">YOUR NEXT CHAPTER</div><h1>Choose a realm.</h1><p>Every world has a story. Where will yours begin?</p></div>
      <div className="realm-grid">
        {realms.map(realm => (
          <article className="realm-card" key={realm.id}>
            <div className={'realm-art ' + realm.art} aria-hidden="true"><span className="realm-orb" /><span className="realm-hill" /></div>
            <div className="realm-card-body">
              <div className="realm-metadata"><span>{realm.category}</span><span>{realm.number} / 03</span></div>
              <h2>{realm.name}</h2><p>{realm.description}</p>
              <button className={realm.available ? 'card-link' : 'card-link unavailable'} disabled={!realm.available || busy} onClick={() => onEnter(realm.id)}>
                {realm.available ? 'Enter Realm →' : 'Coming soon'}
              </button>
            </div>
          </article>
        ))}
      </div>
      <p className="realms-note">The Odyssey is currently playable. More realms are on their way.</p>
    </main>
  );
}
