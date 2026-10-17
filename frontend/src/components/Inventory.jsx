import React, { useMemo, useState } from 'react';

function StatusIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M12 21s-6.5-4.35-9-8.1C1.08 9.95 2.03 6.5 5.2 5.15c2.07-.88 4.2-.2 5.38 1.46 1.18-1.66 3.31-2.34 5.38-1.46 3.17 1.35 4.12 4.8 2.2 7.75C18.5 16.65 12 21 12 21z"
        fill="currentColor"
      />
    </svg>
  );
}

function BagIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M8 8V7a4 4 0 1 1 8 0v1h2.2c.94 0 1.72.73 1.79 1.67l.87 10A1.8 1.8 0 0 1 19.07 21H4.93a1.8 1.8 0 0 1-1.79-1.33l.87-10C4.08 8.73 4.86 8 5.8 8H8zm2 0h4V7a2 2 0 1 0-4 0v1z"
        fill="currentColor"
      />
    </svg>
  );
}

function JournalIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M6 4.5A2.5 2.5 0 0 1 8.5 2H19v18H8.5A2.5 2.5 0 0 0 6 22V4.5zm2.5-.5A.5.5 0 0 0 8 4.5v13.05c.5-.35 1.1-.55 1.75-.55H17V4H8.5zM6 18.75c.46-.48 1.03-.75 1.75-.75H17v2H7.75A.75.75 0 0 0 7 20.75c0 .14.04.27.1.39l-1.1.86A2.73 2.73 0 0 1 5 20.75c0-.76.31-1.44 1-2z"
        fill="currentColor"
      />
    </svg>
  );
}

export default function Inventory({ world, onTake, busy }) {
  const [activeTab, setActiveTab] = useState('status');

  const inventory = Array.isArray(world?.inventory) ? world.inventory : [];
  const visible = Array.isArray(world?.visible_objects) ? world.visible_objects : [];
  const exits = world?.exits && typeof world.exits === 'object' ? Object.entries(world.exits) : [];

  const mockStatus = useMemo(
    () => [
      { label: 'Health', value: 88 },
      { label: 'Energy', value: 72 },
      { label: 'Courage', value: 81 },
    ],
    []
  );

  return (
    <aside className="game-sidebar" aria-label="Journey details">
      <div className="journey-card">
        <div className="journey-label">YOUR JOURNEY</div>
        <div className="journey-location">{world?.location || 'Unknown Location'}</div>
        <div className="journey-meta">Turn {world?.turn ?? 0}</div>
      </div>

      <div className="sidebar-tabs" role="tablist" aria-label="Journey panels">
        <button
          className={`sidebar-tab ${activeTab === 'status' ? 'active' : ''}`}
          onClick={() => setActiveTab('status')}
          role="tab"
          aria-selected={activeTab === 'status'}
        >
          <span className="sidebar-tab-icon"><StatusIcon /></span>
          <span>Status</span>
        </button>

        <button
          className={`sidebar-tab ${activeTab === 'inventory' ? 'active' : ''}`}
          onClick={() => setActiveTab('inventory')}
          role="tab"
          aria-selected={activeTab === 'inventory'}
        >
          <span className="sidebar-tab-icon"><BagIcon /></span>
          <span>Inventory</span>
        </button>

        <button
          className={`sidebar-tab ${activeTab === 'journal' ? 'active' : ''}`}
          onClick={() => setActiveTab('journal')}
          role="tab"
          aria-selected={activeTab === 'journal'}
        >
          <span className="sidebar-tab-icon"><JournalIcon /></span>
          <span>Journal</span>
        </button>
      </div>

      {activeTab === 'status' && (
        <section className="sidebar-panel">
          <div className="sidebar-heading">CHARACTER STATUS</div>

          <div className="status-list">
            {mockStatus.map(stat => (
              <div className="status-row" key={stat.label}>
                <div className="status-top">
                  <span>{stat.label}</span>
                  <span>{stat.value}</span>
                </div>
                <div className="status-bar">
                  <div className="status-fill" style={{ width: `${stat.value}%` }} />
                </div>
              </div>
            ))}
          </div>

          <div className="sidebar-subsection">
            <div className="sidebar-heading">PATHS AHEAD</div>
            {exits.length ? (
              <div className="exit-list">
                {exits.map(([direction, place]) => (
                  <div className="exit-row" key={direction}>
                    <span>{direction}</span>
                    <span>{place}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="muted-detail">No visible exits.</p>
            )}
          </div>
        </section>
      )}

      {activeTab === 'inventory' && (
        <section className="sidebar-panel">
          <div className="sidebar-heading">
            YOUR INVENTORY <span>{inventory.length}</span>
          </div>

          {inventory.length ? (
            <ul className="plain-list">
              {inventory.map((item, i) => (
                <li key={item.id || i}>
                  <span className="item-dot" />
                  {item.name}
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted-detail">Your bag is empty.</p>
          )}

          <div className="sidebar-subsection">
            <div className="sidebar-heading">NEARBY OBJECTS</div>
            {visible.length ? (
              <ul className="plain-list">
                {visible.map((item, i) => (
                  <li key={item.id || i}>
                    <span className="item-dot" />
                    <span className="item-name">{item.name}</span>
                    <button className="mini-link" disabled={busy} onClick={() => onTake(item.id)}>
                      Take
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted-detail">Nothing in sight. Try searching.</p>
            )}
          </div>
        </section>
      )}

      {activeTab === 'journal' && (
        <section className="sidebar-panel">
          <div className="sidebar-heading">ADVENTURE JOURNAL</div>

          <div className="journal-book">
            <div className="journal-book-cover">
              <div className="journal-book-badge">DAY 1</div>
              <div className="journal-book-title">Traveler’s Journal</div>
              <div className="journal-book-subtitle">The beginning of a story.</div>
            </div>
          </div>

          <div className="journal-entry">
            <div className="journal-entry-title">The First Steps</div>
            <p>
              I arrived in an unfamiliar clearing, with only the breeze through the olive trees
              to welcome me.
            </p>
          </div>

          <div className="journal-entry">
            <div className="journal-entry-title">More entries soon</div>
            <p>
              Important discoveries, milestones, and turning points will be recorded here.
            </p>
          </div>
        </section>
      )}
    </aside>
  );
}