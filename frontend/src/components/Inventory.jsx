import React from 'react';
export default function Inventory({ world, onTake, busy }) {
  const inventory = Array.isArray(world?.inventory) ? world.inventory : [];
  const visible = Array.isArray(world?.visible_objects) ? world.visible_objects : [];
  const exits = world?.exits && typeof world.exits === 'object' ? Object.entries(world.exits) : [];
  return (
    <aside className="game-sidebar" aria-label="Journey details">
      <section className="sidebar-section">
        <div className="sidebar-heading">YOUR INVENTORY <span>{inventory.length}</span></div>
        {inventory.length ? <ul className="plain-list">{inventory.map((item, i) => <li key={item.id || i}><span className="item-dot" />{item.name}</li>)}</ul> : <p className="muted-detail">Your bag is empty.</p>}
      </section>
      <section className="sidebar-section">
        <div className="sidebar-heading">NEARBY OBJECTS</div>
        {visible.length ? <ul className="plain-list">{visible.map((item, i) => <li key={item.id || i}><span className="item-dot" /> <span className="item-name">{item.name}</span><button className="mini-link" disabled={busy} onClick={() => onTake(item.id)}>Take</button></li>)}</ul> : <p className="muted-detail">Nothing in sight. Try searching.</p>}
      </section>
      <section className="sidebar-section">
        <div className="sidebar-heading">PATHS AHEAD</div>
        {exits.length ? <div className="exit-list">{exits.map(([direction, place]) => <div className="exit-row" key={direction}><span>{direction}</span><span>{place}</span></div>)}</div> : <p className="muted-detail">No visible exits.</p>}
      </section>
      <section className="sidebar-section sidebar-bottom"><div className="sidebar-heading">JOURNEY</div><p className="muted-detail">Turn {world?.turn ?? 0}</p></section>
    </aside>
  );
}
