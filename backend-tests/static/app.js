/* The Stolen Hours of the Monkey King - the 10 screens (design doc section 6).
 *
 * React, written with htm (JSX-like templates that run without a build step),
 * so the server only has to hand out static files.
 *
 * The browser never decides anything. Every button calls the engine's API and
 * shows what comes back. The browser is never told the answers, and pearls
 * only have per-game random codes, so reading this file or the network
 * traffic cannot reveal the culprit or the order.
 */
(function () {
  "use strict";
  const { useState, useEffect, useMemo, useRef } = React;
  const html = htm.bind(React.createElement);

  const FORM_IMAGES = {
    "Sun Wukong": "/static/img/wukong.svg",
    "Jade Rabbit": "/static/img/rabbit.svg",
    "Dragon King": "/static/img/dragon.svg",
  };
  const SLOT_NAMES = ["First", "Second", "Third", "Fourth", "Fifth", "Last"];

  // ---------------------------------------------------------------- helpers
  async function api(path, body) {
    const opts = body === undefined
      ? { method: "GET" }
      : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
    let res;
    try {
      res = await fetch(path, opts);
    } catch (e) {
      throw { code: "network", message: "The Scroll cannot reach the server. Check the internet and try again." };
    }
    let data = {};
    try { data = await res.json(); } catch (e) { /* empty body */ }
    if (!res.ok) {
      const detail = Array.isArray(data.detail) ? "Something in that answer was not right." : null;
      throw { code: data.error || "error", message: data.message || detail || "Something went wrong. Please try again." };
    }
    return data;
  }

  const saved = {
    get() { try { return localStorage.getItem("mk_session"); } catch (e) { return null; } },
    set(v) { try { localStorage.setItem("mk_session", v); } catch (e) { /* private mode */ } },
    clear() { try { localStorage.removeItem("mk_session"); } catch (e) { /* private mode */ } },
  };

  // ------------------------------------------------------- the spoken voice
  // Review 2: the narrator speaks. It uses the browser's own speech (Web Speech API):
  // free, no server, no audio files, and it works offline. Captions always show first,
  // so if speech is missing, muted or fails, the game is exactly the same, just silent.
  //
  // Deep, warm, unhurried: we prefer these voices (first match on this laptop wins),
  // then lower the pitch and slow the rate a little. The team picked the order with a
  // listening test (docs/validation.md); anyone can choose another in "Voice settings".
  const VOICE_PREFERENCE = [
    /Microsoft (Guy|Davis|Andrew|Christopher|Brian|Roger|Eric).*Online/i,  // Edge "Natural" voices
    /Google UK English Male/i,                                          // Chrome
    /^Daniel\b/i, /^Arthur\b/i, /^Aaron\b/i, /^Fred\b/i, /^Alex\b/i, /^Ralph\b/i,  // macOS / Safari
    /Microsoft (George|David|Mark|James|Richard)\b/i,                   // Windows desktop voices
    /\bmale\b/i,
  ];
  const ROLES = {
    narrator: { pitch: 0.8, rate: 0.88 },   // deep, calm, nonchalant
    grandma:  { pitch: 1.0, rate: 0.9 },
    wukong:   { pitch: 1.25, rate: 1.02 },  // the Monkey King is a bit quicker and brighter
  };
  const SAMPLE_LINE = "The forest has gone quiet. Someone has misplaced an hour. Let's see where it went.";

  const Voice = (() => {
    const synth = typeof window !== "undefined" && "speechSynthesis" in window
      && typeof window.SpeechSynthesisUtterance === "function" ? window.speechSynthesis : null;
    let settings = { muted: false, voiceURI: "", slow: false };
    try { settings = { ...settings, ...JSON.parse(localStorage.getItem("mk_voice") || "{}") }; } catch (e) { /* private mode */ }
    let voices = [];
    let speaking = false;
    let failed = false;
    let current = null;   // the text being spoken, for the "Speaking" note
    let generation = 0;   // Skip and Mute bump this, so lines scheduled earlier are dropped too
    const spoken = new Set();
    const listeners = new Set();
    const snapshot = () => ({ supported: !!synth, muted: settings.muted, slow: settings.slow, speaking, failed, current,
      voices, chosen: pick(), voiceURI: settings.voiceURI });
    const emit = () => { const snap = snapshot(); listeners.forEach((f) => f(snap)); };
    const save = () => { try { localStorage.setItem("mk_voice", JSON.stringify(settings)); } catch (e) { /* ok */ } };

    function loadVoices() {
      if (!synth) return;
      try { voices = synth.getVoices().filter((v) => /^en([-_]|$)/i.test(v.lang)); } catch (e) { voices = []; }
      emit();
    }
    function pick() {
      if (!voices.length) return null;
      const own = voices.find((v) => v.voiceURI === settings.voiceURI);
      if (own) return own;
      for (const re of VOICE_PREFERENCE) {
        const v = voices.find((x) => re.test(x.name));
        if (v) return v;
      }
      return voices.find((v) => v.default) || voices[0];
    }
    function queue(items, gen) {
      if (gen !== generation || settings.muted) return;   // skipped or muted while waiting
      const v = pick();
      for (const item of items) {
        const { text, role } = typeof item === "string" ? { text: item, role: "narrator" } : item;
        if (!text) continue;
        const u = new SpeechSynthesisUtterance(text);
        const r = ROLES[role] || ROLES.narrator;
        if (v) { u.voice = v; u.lang = v.lang; }
        u.pitch = r.pitch;
        u.rate = r.rate * (settings.slow ? 0.85 : 1);
        u.onstart = () => { speaking = true; current = text; emit(); };
        u.onend = () => { if (!synth.pending) { speaking = false; current = null; emit(); } };
        u.onerror = (e) => {
          // "interrupted"/"canceled" just mean Skip or a newer line; anything else means speech is not working here.
          if (e && e.error && !["interrupted", "canceled"].includes(e.error)) failed = true;
          speaking = false; current = null; emit();
        };
        synth.speak(u);
      }
    }
    function say(items, { interrupt = true } = {}) {
      if (!synth || settings.muted) return;
      try {
        if (interrupt && (synth.speaking || synth.pending)) {
          synth.cancel();
          const gen = ++generation;
          setTimeout(() => { try { queue(items, gen); } catch (e) { failed = true; emit(); } }, 60);  // Chrome drops a speak() right after cancel()
        } else queue(items, generation);
      } catch (e) { failed = true; emit(); }   // never let speech break the game
    }
    if (synth) {
      loadVoices();
      try { synth.addEventListener("voiceschanged", loadVoices); } catch (e) { synth.onvoiceschanged = loadVoices; }
      window.addEventListener("pagehide", () => { try { synth.cancel(); } catch (e) { /* ok */ } });
    }
    return {
      say,
      sayOnce(id, items, opts) { if (spoken.has(id)) return; spoken.add(id); say(items, opts); },  // each new line once
      skip() { generation += 1; if (synth) { try { synth.cancel(); } catch (e) { /* ok */ } } speaking = false; current = null; emit(); },
      setMuted(m) { settings.muted = m; save(); if (m) this.skip(); emit(); },
      setSlow(x) { settings.slow = x; save(); emit(); },
      setVoice(uri) { settings.voiceURI = uri; save(); emit(); },
      test() { say([SAMPLE_LINE]); },
      reset() { spoken.clear(); this.skip(); },
      subscribe(f) { listeners.add(f); return () => listeners.delete(f); },
      snapshot,
    };
  })();

  function useVoice() {
    const [snap, setSnap] = useState(Voice.snapshot);
    useEffect(() => Voice.subscribe(setSnap), []);
    return snap;
  }

  function shuffled(list) {
    const a = list.slice();
    for (let i = a.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
  }

  function useFlash() {
    // Adds a CSS class for a moment (shake, wobble, glow), then removes it.
    const [cls, setCls] = useState("");
    const flash = (name, ms) => { setCls(""); requestAnimationFrame(() => setCls(name)); setTimeout(() => setCls(""), ms || 600); };
    return [cls, flash];
  }

  // ------------------------------------------------------------ small parts
  function Scenery({ src, alt }) {
    return html`<div class="scenery"><img src=${src} alt=${alt} /></div>`;
  }

  // A small picture of each pearl's time clue (review fix: let players SEE the evidence).
  // Left of every picture is East, right is West, so "rising in the east" can be checked by eye.
  const SUN_POS = { "low-east": [26, 66], "high": [100, 16], "mid-west": [150, 40], "setting-west": [178, 56] };
  const MOON_POS = { "low-east": [28, 64], "high": [100, 16] };
  function PearlVisual({ v, small }) {
    if (!v) return null;
    const night = v.kind === "moon";
    const sky = night ? "#2B2A33" : "#FFF8E8";
    const ink = night ? "#F4EDE0" : "#1C1B19";
    const parts = [];
    const sunDot = () => {
      const [sx, sy] = SUN_POS[v.sun] || SUN_POS.high;
      return html`<circle key="sun" cx=${sx} cy=${sy} r="9" fill=${v.sun === "setting-west" ? "#B23A2B" : "#E2B44C"} />`;
    };
    if (v.kind === "sun") parts.push(sunDot());
    if (v.kind === "sun") {
      // a pole, and its shadow on the far side from the sun; a lower sun makes a longer shadow
      const [sx, sy] = SUN_POS[v.sun] || SUN_POS.high;
      const altitude = 92 - sy;                                   // higher sun -> shorter shadow
      const len = Math.min(85, Math.max(5, 1800 / altitude - 18));
      const dir = sx < 100 ? 1 : sx > 100 ? -1 : 0;              // shadow points away from the sun
      const x = dir === 1 ? 100 : dir === -1 ? 100 - len : 100 - len / 2;
      parts.push(html`<rect key="shadow" x=${x} y="89" width=${len} height="4" rx="2" fill="#1C1B19" opacity="0.4" />`);
      parts.push(html`<rect key="pole" x="98" y="58" width="4" height="33" fill="#3E7C6B" />`);
    }
    if (v.kind === "tide") {
      const top = v.water === "high" ? 66 : 82;
      parts.push(html`<rect key="sea" x="0" y=${top} width="200" height=${110 - top} fill="#9DC3B4" />`);
      parts.push(html`<rect key="stone" x="18" y="58" width="44" height="34" rx="6" fill="#1C1B19" opacity="0.8" />`);
      parts.push(html`<line key="mark" x1="18" y1="66" x2="62" y2="66" stroke="#E2B44C" stroke-width="2.5" stroke-dasharray="4 3" />`);
      if (v.sun) parts.push(sunDot());   // drawn last so the water never hides it
    }
    if (v.kind === "moon") {
      const [mx, my] = MOON_POS[v.moon] || MOON_POS.high;
      parts.push(html`<circle key="moon" cx=${mx} cy=${my} r="10" fill="#F4EDE0" />`);
    }
    const label = { sun: "Sun and shadow", tide: "Water level (gold line = high stone line)", moon: "Moon in the night sky" }[v.kind];
    return html`<figure class=${"clue" + (small ? " small" : "")} aria-label=${label}>
      <svg viewBox="0 0 200 110" role="img">
        <rect width="200" height="110" fill=${sky} />
        <line x1="0" y1="92" x2="200" y2="92" stroke=${ink} stroke-width="1.5" />
        ${parts}
        <text x="6" y="106" font-size="10" fill=${ink}>East</text>
        <text x="194" y="106" font-size="10" fill=${ink} text-anchor="end">West</text>
      </svg>
      ${small ? null : html`<figcaption>${label}</figcaption>`}
    </figure>`;
  }

  // Section 11: every Scroll and Wukong line says where it came from. "AI narrator" only
  // when the AI really wrote it; lines written by our team are labelled as such.
  const SOURCE_NOTE = { ai: "AI narrator", table: "written by our team", fallback: "pre-written line (AI not used)" };

  function Message({ m, speakId }) {
    const voice = useVoice();
    const role = m.who === "wukong" ? "wukong" : "narrator";
    // A new line is spoken once, as it appears; the caption is already on screen.
    // m.queue: wait for the line before it (a taunt, then a hint) instead of cutting it off.
    useEffect(() => { if (speakId && m.text) Voice.sayOnce(speakId, [{ text: m.text, role }], { interrupt: !m.queue && role !== "wukong" }); }, [speakId]);
    if (m.who === "child") return html`<div class="msg child">${m.text}</div>`;
    const name = m.who === "wukong" ? "Wukong" : "The Scroll";
    return html`<div class=${"msg " + (m.who === "wukong" ? "wukong" : "scroll")}>
      <div class="ai-label">${name} · ${SOURCE_NOTE[m.source] || SOURCE_NOTE.table}
        ${voice.supported && !voice.muted ? html`<button class="replay" type="button" aria-label="Hear this again"
          onClick=${() => Voice.say([{ text: m.text, role }])}>Replay</button>` : null}</div>
      <div>${m.text}</div>
    </div>`;
  }

  let msgSeq = 0;
  const mk = (m) => ({ ...m, id: "m" + (++msgSeq) });   // every chat line gets an id, so it is spoken once

  function SpeakButton({ text, role }) {
    const v = useVoice();
    if (!v.supported || v.muted) return null;
    return html`<button class="replay" type="button" aria-label="Hear this again"
      onClick=${() => Voice.say([{ text, role: role || "narrator" }])}>Replay</button>`;
  }

  // Skip, mute and voice choice, always in the same corner (review 2: mute, skip, replay).
  function VoiceBar() {
    const v = useVoice();
    const [open, setOpen] = useState(false);
    if (!v.supported) return html`<div class="voicebar" role="status"><span class="muted">Captions only: this browser cannot speak.</span></div>`;
    return html`<div class="voicebar" role="region" aria-label="Narrator voice">
      ${v.failed && !v.muted ? html`<span class="muted">Voice not working here. Captions show everything.</span>` : null}
      ${v.speaking ? html`<span class="speaking" aria-hidden="true">Narrator speaking</span>` : null}
      <button class="btn small" type="button" disabled=${!v.speaking} onClick=${() => Voice.skip()}>Skip</button>
      <button class="btn small" type="button" aria-pressed=${v.muted ? "true" : "false"}
        onClick=${() => Voice.setMuted(!v.muted)}>${v.muted ? "Unmute" : "Mute"}</button>
      <button class="btn small" type="button" onClick=${() => setOpen(true)}>Voice settings</button>
      ${open ? html`<${VoiceSettings} v=${v} onClose=${() => setOpen(false)} />` : null}
    </div>`;
  }

  function VoiceSettings({ v, onClose }) {
    const chosen = v.chosen ? v.chosen.voiceURI : "";
    return html`<div class="modal-back" onClick=${onClose}>
      <div class="modal stack" role="dialog" aria-modal="true" aria-label="Narrator voice" onClick=${(e) => e.stopPropagation()}>
        <h2>Narrator voice</h2>
        <p class="muted">Pick the deepest, calmest voice on this laptop, then press Test. The game remembers it.</p>
        ${v.voices.length ? html`<label for="voice"><strong>Voice</strong></label>
          <select id="voice" value=${chosen} onChange=${(e) => Voice.setVoice(e.target.value)}>
            ${v.voices.map((x) => html`<option key=${x.voiceURI} value=${x.voiceURI}>${x.name} (${x.lang})</option>`)}
          </select>` : html`<p>No English voices were found on this computer, so the game shows captions only.</p>`}
        <label class="row"><input type="checkbox" checked=${v.slow} onChange=${(e) => Voice.setSlow(e.target.checked)} /> Speak more slowly</label>
        <div class="row">
          <button class="btn" type="button" disabled=${v.muted || !v.voices.length} onClick=${() => Voice.test()}>Test voice</button>
          ${v.voiceURI ? html`<button class="btn link" type="button" onClick=${() => Voice.setVoice("")}>Use the recommended voice</button>` : null}
          <button class="btn primary" type="button" onClick=${onClose}>Done</button>
        </div>
        ${v.muted ? html`<p class="muted">The narrator is muted. Press Unmute to hear it.</p>` : null}
      </div>
    </div>`;
  }

  function ErrorLine({ error }) {
    return error ? html`<p class="error" role="alert">${error}</p>` : null;
  }

  function ScrollInfo({ text, onClose }) {
    return html`<div class="modal-back" onClick=${onClose}>
      <div class="modal" role="dialog" aria-modal="true" aria-label="How the Scroll works" onClick=${(e) => e.stopPropagation()}>
        <h2>How the Scroll works</h2>
        <p>${text}</p>
        <button class="btn primary" onClick=${onClose}>Got it</button>
      </div>
    </div>`;
  }

  function TopBar({ state, onInfo, onMap }) {
    return html`<div class="topbar">
      <div class="brand">The Stolen Hours</div>
      <div class="row">
        ${state ? html`<span class="counter"><span class="pearl" style=${{ width: "22px", height: "22px", margin: 0 }}></span>
          Pearls: ${state.pearls_found} of ${state.pearls_total}</span>` : null}
        ${onMap ? html`<button class="btn small" onClick=${onMap}>Back to map</button>` : null}
        ${onInfo ? html`<button class="btn small" onClick=${onInfo}>How the Scroll works</button>` : null}
      </div>
    </div>`;
  }

  // ---------------------------------------------- before / after questions
  function Assessment({ sid, phase, onDone }) {
    const [data, setData] = useState(null);
    const [answers, setAnswers] = useState({});
    const [error, setError] = useState(null);
    const [busy, setBusy] = useState(false);
    useEffect(() => {
      api(`/api/assessment/${phase}?session_id=${encodeURIComponent(sid)}`).then(setData).catch((e) => setError(e.message));
    }, [phase]);
    const submit = async () => {
      setBusy(true); setError(null);
      try { onDone((await api("/api/assessment", { session_id: sid, phase, answers })).state); }
      catch (e) { setError(e.message); setBusy(false); }
    };
    if (!data) return html`<div class="panel"><p>Loading...</p><${ErrorLine} error=${error} /></div>`;
    const done = data.items.every((i) => answers[i.item_id]);
    return html`<div class="panel stack">
      <h2>${phase === "pre" ? "Before the adventure" : "Two last questions"}</h2>
      <p class="muted">${data.intro}</p>
      ${data.items.map((item, n) => html`<fieldset class="card question" key=${item.item_id}>
        <legend><strong>${n + 1}. ${item.question}</strong></legend>
        <div class="choices">
          ${item.choices.map((c) => html`<button key=${c} class=${"btn" + (answers[item.item_id] === c ? " selected" : "")}
            aria-pressed=${answers[item.item_id] === c ? "true" : "false"}
            onClick=${() => setAnswers({ ...answers, [item.item_id]: c })}>${c}</button>`)}
        </div>
      </fieldset>`)}
      <div><button class="btn primary" disabled=${!done || busy} onClick=${submit}>Done</button></div>
      <${ErrorLine} error=${error} />
    </div>`;
  }

  // ------------------------------------------------------- 1. title screen
  function Title({ onStart, onResume, canResume }) {
    const [nick, setNick] = useState("");
    const [error, setError] = useState(null);
    const [busy, setBusy] = useState(false);
    const begin = async (e) => {
      e.preventDefault();
      setBusy(true); setError(null);
      try { await onStart(nick); } catch (err) { setError(err.message); } finally { setBusy(false); }
    };
    return html`<div class="title-screen">
      <${Scenery} src="/static/img/mountain.svg" alt="Five Elements Mountain in the mist" />
      <div class="center">
        <h1>The Stolen Hours of the Monkey King</h1>
        <p class="muted">An adventure where the narrator cannot cheat for you, and the Monkey King lies to you.</p>
      </div>
      <form class="title-form" onSubmit=${begin}>
        <label for="nick"><strong>Your nickname</strong> <span class="muted">(not your real name)</span></label>
        <input id="nick" type="text" maxlength="30" autocomplete="off" value=${nick}
          onInput=${(e) => setNick(e.target.value)} placeholder="For example: Brave Bamboo" />
        <${ErrorLine} error=${error} />
        <button class="btn primary" type="submit" disabled=${busy || !nick.trim()}>Begin</button>
        ${canResume ? html`<button class="btn" type="button" onClick=${onResume}>Continue my adventure</button>` : null}
      </form>
      <p class="center"><a class="btn link" href="/teacher">Teacher view</a></p>
    </div>`;
  }

  // ----------------------------------------------------------- 2. prologue
  function Prologue({ lines, grandma, onDone }) {
    const [shown, setShown] = useState(1);
    const total = lines.length + 1; // 5 lines, then Grandmother Lin gives the Scroll
    const next = () => setShown((n) => Math.min(n + 1, total));
    const current = shown <= lines.length ? { text: lines[shown - 1], role: "narrator" } : { text: grandma, role: "grandma" };
    useEffect(() => { Voice.sayOnce("prologue:" + shown, [current]); }, [shown]);
    return html`<div class="prologue" onClick=${shown < total ? next : undefined}>
      <${Scenery} src="/static/img/mountain.svg" alt="" />
      <div class="lines" aria-live="polite">
        ${lines.slice(0, shown).map((l, i) => html`<p class="line" key=${i}>${l}</p>`)}
        ${shown === total ? html`<p class="line grandma"><strong>Grandmother Lin: </strong>${grandma}</p>` : null}
      </div>
      <div class="tap">
        <${SpeakButton} text=${current.text} role=${current.role} />
        ${shown < total
          ? html`<button class="btn" onClick=${(e) => { e.stopPropagation(); next(); }}>Tap to continue</button>`
          : html`<button class="btn primary" onClick=${onDone}>Take the Scroll</button>`}
      </div>
    </div>`;
  }

  // ---------------------------------------------------------- 3. realm map
  function RealmMap({ state, onPick, onTimeline }) {
    const all = state.pearls_found === state.pearls_total;
    return html`<div class="stack">
      <h2>Choose a realm</h2>
      ${all && state.stage_line ? html`<${Message} m=${{ who: "scroll", queue: true, ...state.stage_line }} speakId="stage:timeline" />` : null}
      ${all ? html`<div class="card row" style=${{ justifyContent: "space-between" }}>
        <p style=${{ margin: 0 }}><strong>You found all six Memory Pearls!</strong> Now put them in time order.</p>
        <button class="btn primary" onClick=${onTimeline}>Go to the Timeline Board</button>
      </div>` : html`<p class="muted">All three realms are open. Visit them in any order.</p>`}
      <div class="realm-grid">
        ${state.realms.map((r) => html`<button class="realm-card" key=${r.realm_id} onClick=${() => onPick(r.realm_id)}>
          <${Scenery} src=${r.image_url} alt=${r.name} />
          <h3>${r.name}</h3>
          <p class="muted">Pearls found: ${r.pearls_found} of ${r.pearls_total}</p>
        </button>`)}
      </div>
    </div>`;
  }

  // -------------------------------------------------------- 4. realm scene
  function RealmScene({ sid, state, realmId, chat, addChat, onOpen, onChange }) {
    const realm = state.realms.find((r) => r.realm_id === realmId);
    const [question, setQuestion] = useState("");
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState(null);
    const inputRef = useRef(null);
    const logRef = useRef(null);
    const messages = chat[realmId] || [];

    useEffect(() => { if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight; }, [messages.length]);

    const doAction = async (action) => {
      setError(null);
      try {
        const r = await api("/api/action", { session_id: sid, realm: realmId, action });
        Voice.say([r.text]);   // the caption appears at the same moment
        onChange(r.state);
      }
      catch (e) { setError(e.message); }
    };
    const ask = async (e) => {
      e.preventDefault();
      const q = question.trim();
      if (!q) return;
      setBusy(true); setError(null);
      addChat(realmId, mk({ who: "child", text: q }));
      setQuestion("");
      try {
        const r = await api("/api/ask", { session_id: sid, realm: realmId, question: q });
        addChat(realmId, mk({ who: "scroll", text: r.reply.text, source: r.reply.source }));
      } catch (err) { setError(err.message); } finally { setBusy(false); }
    };
    const open = async () => {
      setError(null);
      try { onOpen({ ...(await api("/api/open", { session_id: sid, realm: realmId })), realm: realmId }); }
      catch (e) { setError(e.message); }
    };

    const looked = realm.done_actions.includes("look");
    const listened = realm.done_actions.includes("listen");
    const allFound = realm.pearls_found === realm.pearls_total;
    const openLabel = allFound ? "All pearls found here" : (looked && listened ? "Open pearl" : "Open pearl (Look and Listen first)");

    return html`<div class="realm-layout">
      <div>
        <h2>${realm.name}</h2>
        <${Scenery} src=${realm.image_url} alt=${realm.name} />
        <div class="actions">
          <button class=${"btn" + (looked ? " selected" : "")} onClick=${() => doAction("look")}>Look</button>
          <button class=${"btn" + (listened ? " selected" : "")} onClick=${() => doAction("listen")}>Listen</button>
          <button class="btn" onClick=${() => inputRef.current && inputRef.current.focus()}>Ask the Scroll</button>
          <button class="btn primary" disabled=${!realm.can_open_pearl} onClick=${open}>${openLabel}</button>
        </div>
        <div class="seen" aria-live="polite">
          ${realm.seen.look ? html`<p><strong>You look: </strong>${realm.seen.look} <${SpeakButton} text=${realm.seen.look} /></p>` : null}
          ${realm.seen.listen ? html`<p><strong>You listen: </strong>${realm.seen.listen} <${SpeakButton} text=${realm.seen.listen} /></p>` : null}
        </div>
        <${ErrorLine} error=${error} />
      </div>
      <div class="card chat">
        <h3>The Torn Scroll</h3>
        <div class="chat-log" ref=${logRef} aria-live="polite">
          <${Message} m=${{ who: "scroll", source: "table", text: realm.enter_text }} speakId=${"enter:" + realmId} />
          <p class="muted small-note">Look and Listen first. Ask me anything, but I only know the pages you find.</p>
          ${messages.map((m) => html`<${Message} key=${m.id} m=${m} speakId=${m.who === "child" ? null : m.id} />`)}
        </div>
        <form class="chat-form" onSubmit=${ask}>
          <input ref=${inputRef} type="text" maxlength="200" value=${question} aria-label="Ask the Scroll a question"
            onInput=${(e) => setQuestion(e.target.value)} placeholder="Ask the Scroll..." />
          <button class="btn primary" type="submit" disabled=${busy || !question.trim()}>${busy ? "..." : "Send"}</button>
        </form>
      </div>
    </div>`;
  }

  // ------------------------------------------------------ 5. predict first
  function Predict({ sid, pending, onPredicted }) {
    const [error, setError] = useState(null);
    const [hint, setHint] = useState(null);
    const [busy, setBusy] = useState(false);
    const pick = async (choice) => {
      setBusy(true); setError(null);
      try { onPredicted(await api("/api/predict", { session_id: sid, pearl: pending.pearl, choice }), choice); }
      catch (e) { setError(e.message); setBusy(false); }
    };
    useEffect(() => { Voice.sayOnce("predict:" + pending.pearl, [pending.question]); }, [pending.pearl]);
    const askHint = async () => {
      setError(null);
      try { setHint((await api("/api/hint", { session_id: sid, puzzle: "PREDICT", realm: pending.realm })).hint); }
      catch (e) { setError(e.message); }
    };
    return html`<div class="panel center stack">
      <div class="pearl"></div>
      <h2>Predict first</h2>
      <p style=${{ fontSize: "22px" }}>${pending.question}</p>
      <div><${SpeakButton} text=${pending.question} /></div>
      <div class="choices">
        ${pending.choices.map((c) => html`<button class="btn" key=${c} disabled=${busy} onClick=${() => pick(c)}>${c}</button>`)}
      </div>
      <div>
        <button class="btn small" onClick=${askHint} disabled=${hint && hint.level >= hint.max_level}>
          ${hint ? "Ask for another hint" : "Ask the Scroll for a hint"}
        </button>
      </div>
      ${hint ? html`<div style=${{ textAlign: "left" }}><${Message} m=${{ who: "scroll", text: hint.text, source: hint.source }}
        speakId=${"hint:" + pending.pearl + ":" + hint.level} /></div>` : null}
      <${ErrorLine} error=${error} />
    </div>`;
  }

  // -------------------------------------------------------- 6. pearl reveal
  function Reveal({ result, choice, onKeep }) {
    const p = result.pearl;
    // The memory, then the storyteller's reaction, one after the other.
    useEffect(() => { Voice.sayOnce("reveal:" + p.pearl, [p.text, result.narration.text]); }, [p.pearl]);
    return html`<div class="panel center stack">
      <div class="pearl big"></div>
      <h2>${p.title}</h2>
      <${PearlVisual} v=${p.visual} />
      <p class="memory" style=${{ textAlign: "left" }}>${p.text} <${SpeakButton} text=${p.text} /></p>
      <p>You guessed: <strong>${choice}</strong>.
</p>
      <div style=${{ textAlign: "left" }}><${Message} m=${{ who: "scroll", ...result.narration }} /></div>
      <div><button class="btn primary" onClick=${onKeep}>Keep the pearl</button></div>
    </div>`;
  }

  // ------------------------------------------------------ 7. timeline board
  function PearlCard({ p, picked, onClick, draggable, onDragStart }) {
    return html`<button class=${"pearl-card" + (picked ? " picked" : "")} onClick=${onClick}
      draggable=${draggable} onDragStart=${onDragStart} aria-pressed=${picked ? "true" : "false"}>
      <strong><span class="dot"></span>${p.title}</strong>
      <${PearlVisual} v=${p.visual} small=${true} />
      ${p.text}
    </button>`;
  }

  function Timeline({ sid, state, onSolved }) {
    const deck = useMemo(() => shuffled(state.opened), []); // fixed random order for this visit
    const [slots, setSlots] = useState([null, null, null, null, null, null]);
    const [picked, setPicked] = useState(null);
    const [messages, setMessages] = useState([]);
    const [error, setError] = useState(null);
    const [busy, setBusy] = useState(false);
    const [solved, setSolved] = useState(null);   // the storyteller's line once the board is right
    const [fx, flash] = useFlash();
    const [over, setOver] = useState(-1);

    const placed = new Set(slots.filter(Boolean));
    const byId = Object.fromEntries(state.opened.map((p) => [p.pearl, p]));
    const place = (id, i) => {
      setSlots((s) => { const n = s.map((x) => (x === id ? null : x)); n[i] = id; return n; });
      setPicked(null);
    };
    const tapSlot = (i) => {
      if (picked) return place(picked, i);
      if (slots[i]) setSlots((s) => { const n = s.slice(); n[i] = null; return n; }); // tap a placed pearl to take it back
    };
    const check = async () => {
      setBusy(true); setError(null);
      try {
        const r = await api("/api/timeline", { session_id: sid, order: slots });
        if (r.correct) {
          setSolved(r.narration); flash("glow", 2400);
          setTimeout(() => onSolved(r.state), 4000);
        } else {
          flash("wobble", 500);
          setMessages((m) => [...m, mk({ who: "scroll", text: r.scroll.text, source: r.scroll.source })]);
        }
      } catch (e) { setError(e.message); } finally { setBusy(false); }
    };
    const hint = async () => {
      try {
        const h = (await api("/api/hint", { session_id: sid, puzzle: "TIMELINE" })).hint;
        setMessages((m) => [...m, mk({ who: "scroll", text: h.text, source: h.source })]);
      } catch (e) { setError(e.message); }
    };

    return html`<div class=${"board " + fx}>
      <h2>The Timeline Board</h2>
      <p class="muted">Put the six pearls in time order, from first to last. Tap a pearl, then tap a slot. You can also drag. Tap a placed pearl to take it back.</p>
      <div class="board-section pearl-cards">
        ${deck.filter((p) => !placed.has(p.pearl)).map((p) => html`<${PearlCard} key=${p.pearl} p=${p}
          picked=${picked === p.pearl} draggable=${true}
          onDragStart=${(e) => e.dataTransfer.setData("text/plain", p.pearl)}
          onClick=${() => setPicked(picked === p.pearl ? null : p.pearl)} />`)}
      </div>
      <div class="board-section slots">
        ${slots.map((id, i) => html`<div key=${i} class=${"slot" + (over === i ? " over" : "")}
          onClick=${() => tapSlot(i)}
          onDragOver=${(e) => { e.preventDefault(); setOver(i); }}
          onDragLeave=${() => setOver(-1)}
          onDrop=${(e) => { e.preventDefault(); setOver(-1); place(e.dataTransfer.getData("text/plain"), i); }}>
          <span class="slot-label">${SLOT_NAMES[i]}</span>
          ${id ? html`<${PearlCard} p=${byId[id]} onClick=${(e) => { e.stopPropagation(); setSlots((s) => { const n = s.slice(); n[i] = null; return n; }); }}
            draggable=${true} onDragStart=${(e) => e.dataTransfer.setData("text/plain", id)} />`
            : html`<span class="muted">${picked ? "Tap to place here" : "Empty"}</span>`}
        </div>`)}
      </div>
      <div class="row">
        <button class="btn primary" disabled=${busy || solved || slots.some((s) => !s)} onClick=${check}>Check</button>
        <button class="btn" onClick=${hint} disabled=${solved}>Ask the Scroll for a hint</button>
      </div>
      ${solved ? html`<p class="feedback-ok" style=${{ fontSize: "22px" }}>The board glows! Time flows in the right order. Wukong is coming...</p>
        <${Message} m=${{ who: "scroll", ...solved }} speakId="timeline_solved" />` : null}
      <div class="stack" style=${{ marginTop: "12px" }}>${messages.map((m) => html`<${Message} key=${m.id} m=${m} speakId=${m.id} />`)}</div>
      <${ErrorLine} error=${error} />
    </div>`;
  }

  // ---------------------------------------------------------------- 8. duel
  function Hairs({ left }) {
    return html`<div class="hairs" aria-label=${left + " magic hairs left"}>
      ${[0, 1, 2].map((i) => html`<span key=${i} class=${"hair" + (i < left ? "" : " gone")}></span>`)}
    </div>`;
  }

  function Duel({ sid, state, onChange }) {
    const [claim, setClaim] = useState(null);
    const [saidLie, setSaidLie] = useState(null);
    const [proofs, setProofs] = useState([]);
    const [reason, setReason] = useState(null);
    const [messages, setMessages] = useState([]);
    const [error, setError] = useState(null);
    const [busy, setBusy] = useState(false);
    const [fx, flash] = useFlash();
    const [changing, setChanging] = useState(false);
    const [hairs, setHairs] = useState(state.hairs_left);
    const round = state.duel_round;
    useEffect(() => setHairs(state.hairs_left), [state.hairs_left]);

    useEffect(() => {
      let live = true;
      setChanging(true);
      api(`/api/duel/${round}?session_id=${encodeURIComponent(sid)}`)
        .then((c) => {
          if (!live) return;
          setClaim(c); setSaidLie(null); setProofs([]); setReason(null);
          Voice.sayOnce("claim:" + round, [{ text: c.claim, role: "wukong" }], { interrupt: false });  // Wukong says his claim
        })
        .catch((e) => live && setError(e.message))
        .finally(() => setTimeout(() => live && setChanging(false), 600));
      return () => { live = false; };
    }, [round]);

    const answer = async () => {
      setBusy(true); setError(null);
      try {
        const r = await api("/api/duel", { session_id: sid, round, said_lie: saidLie, proofs, reason });
        setMessages((m) => [...m, mk({ who: "wukong", text: r.taunt.text, source: r.taunt.source })]);
        if (r.correct) {
          flash("shake", 500);
          setHairs(r.hairs_left); // the hair fades right away
          setTimeout(() => onChange(r.state), 1400);
        } else {
          flash("wobble", 500);
          setClaim((c) => ({ ...c, copies: r.copies }));
          setMessages((m) => [...m, mk({ who: "scroll", text: r.hint.text, source: r.hint.source, queue: true })]);
        }
      } catch (e) { setError(e.message); } finally { setBusy(false); }
    };

    if (!claim) return html`<p>Wukong is breaking free of the mountain...</p><${ErrorLine} error=${error} />`;
    const need = claim.proof_count;
    const toggleProof = (code) => setProofs((ps) => ps.includes(code) ? ps.filter((x) => x !== code)
      : need === 1 ? [code] : ps.length < need ? [...ps, code] : [...ps.slice(1), code]);
    const askHint = async () => {
      try {
        const h = (await api("/api/hint", { session_id: sid, puzzle: "DUEL" })).hint;
        setMessages((m) => [...m, mk({ who: "scroll", text: h.text, source: h.source })]);
      } catch (e) { setError(e.message); }
    };
    return html`<div class=${"duel " + fx}>
      <div class=${"wukong-stage" + (changing ? " changing" : "")}>
        <h2>Duel with Wukong: round ${round} of 3</h2>
        ${state.stage_line ? html`<div class="stage-line"><${Message} m=${{ who: "scroll", queue: true, ...state.stage_line }} speakId="stage:duel" /></div>` : null}
        <img src=${FORM_IMAGES[claim.form_name] || FORM_IMAGES["Sun Wukong"]} alt=${"Wukong in the form of " + claim.form_name} />
        <p><strong>Wukong takes the shape of: ${claim.form_name}</strong></p>
        <${Hairs} left=${hairs} />
        <div class="copies" aria-label=${claim.copies + " copies of Wukong"}>
          ${Array.from({ length: Math.min(claim.copies, 8) }, (_, i) => html`<img key=${i} src="/static/img/wukong.svg" alt="" />`)}
        </div>
      </div>
      <div class="stack">
        <div class="claim">"${claim.claim}" <${SpeakButton} text=${claim.claim} role="wukong" /></div>
        <div>
          <p><strong>1. Is this the truth or a lie?</strong></p>
          <div class="row">
            <button class=${"btn" + (saidLie === false ? " selected" : "")} onClick=${() => setSaidLie(false)}>Truth</button>
            <button class=${"btn" + (saidLie === true ? " selected" : "")} onClick=${() => setSaidLie(true)}>Lie</button>
          </div>
        </div>
        <div>
          <p><strong>2. Pick ${need === 1 ? "one pearl" : need + " pearls"} as your proof.</strong>
            <span class="muted"> (${proofs.length} of ${need})</span></p>
          <div class="picker">
            ${state.opened.map((p) => html`<${PearlCard} key=${p.pearl} p=${p} picked=${proofs.includes(p.pearl)}
              onClick=${() => toggleProof(p.pearl)} />`)}
          </div>
        </div>
        <div>
          <p><strong>3. Why? Pick the reason your pearls show.</strong></p>
          <div class="choices" style=${{ margin: 0, maxWidth: "none" }}>
            ${claim.reasons.map((r) => html`<button key=${r} class=${"btn reason" + (reason === r ? " selected" : "")}
              aria-pressed=${reason === r ? "true" : "false"} onClick=${() => setReason(r)}>${r}</button>`)}
          </div>
        </div>
        <div class="row">
          <button class="btn primary" disabled=${busy || saidLie === null || proofs.length !== need || !reason}
            onClick=${answer}>Answer Wukong</button>
          <button class="btn" onClick=${askHint}>Ask the Scroll for a hint</button>
        </div>
        <div class="stack">${messages.slice(-4).map((m) => html`<${Message} key=${m.id} m=${m} speakId=${m.id} />`)}</div>
        <${ErrorLine} error=${error} />
      </div>
    </div>`;
  }

  // -------------------------------------------------- 8b. the final verdict
  function Verdict({ sid, state, onChange }) {
    const [named, setNamed] = useState(null);
    const [proof, setProof] = useState([]);
    const [messages, setMessages] = useState([]);
    const [error, setError] = useState(null);
    const [busy, setBusy] = useState(false);
    const [fx, flash] = useFlash();
    const toggle = (id) => setProof((p) => (p.includes(id) ? p.filter((x) => x !== id) : p.length < 2 ? [...p, id] : [p[1], id]));
    const submit = async () => {
      setBusy(true); setError(null);
      try {
        const r = await api("/api/verdict", { session_id: sid, named, proof });
        if (r.correct) onChange(r.state);
        else { flash("wobble", 500); setMessages((m) => [...m, mk({ who: "scroll", text: r.hint.text, source: r.hint.source })]); }
      } catch (e) { setError(e.message); } finally { setBusy(false); }
    };
    return html`<div class=${"stack " + fx}>
      <h2>Final verdict</h2>
      ${state.stage_line ? html`<${Message} m=${{ who: "scroll", queue: true, ...state.stage_line }} speakId="stage:verdict" />` : null}
      <p>Wukong has lost all three hairs. Now name who stole the hours, and attach <strong>two pearls</strong> as proof.</p>
      <div class="row">
        ${state.suspects.map((s) => html`<button key=${s} class=${"btn" + (named === s ? " selected" : "")} onClick=${() => setNamed(s)}>
          <img src=${FORM_IMAGES[s]} alt="" style=${{ width: "36px", height: "36px", verticalAlign: "middle", marginRight: "6px" }} />${s}
        </button>`)}
      </div>
      <p><strong>Proof pearls (${proof.length} of 2):</strong></p>
      <div class="picker">
        ${state.opened.map((p) => html`<${PearlCard} key=${p.pearl} p=${p} picked=${proof.includes(p.pearl)} onClick=${() => toggle(p.pearl)} />`)}
      </div>
      <div class="row">
        <button class="btn primary" disabled=${busy || !named || proof.length !== 2} onClick=${submit}>Name the culprit</button>
        <button class="btn" onClick=${async () => {
          try { const h = (await api("/api/hint", { session_id: sid, puzzle: "VERDICT" })).hint;
            setMessages((m) => [...m, mk({ who: "scroll", text: h.text, source: h.source })]); } catch (e) { setError(e.message); }
        }}>Ask the Scroll for a hint</button>
      </div>
      <div class="stack">${messages.slice(-3).map((m) => html`<${Message} key=${m.id} m=${m} speakId=${m.id} />`)}</div>
      <${ErrorLine} error=${error} />
    </div>`;
  }

  // -------------------------------------------- 9. ending and next legend
  function EndingText({ turns }) {
    // Told as a few short narration turns, one after the other.
    useEffect(() => { Voice.sayOnce("ending", turns); }, []);
    return html`<div class="ending">${turns.map((t, i) => html`<p key=${i}>${t}</p>`)}
      <${SpeakButton} text=${turns.join(" ")} /></div>`;
  }

  function Ending({ sid, state, onChange, onPlayAgain }) {
    if (state.stage === "posttest") {
      return html`<div class="panel stack">
        <h2>The hours return</h2>
        <${EndingText} turns=${state.ending} />
        <${Assessment} sid=${sid} phase="post" onDone=${onChange} />
      </div>`;
    }
    return html`<${Legend} sid=${sid} state=${state} onChange=${onChange} onPlayAgain=${onPlayAgain} />`;
  }

  function Legend({ sid, state, onChange, onPlayAgain }) {
    const [text, setText] = useState(state.legend_text || "");
    const [scroll, setScroll] = useState({ text: state.legend_prompt, source: "table" });
    const [error, setError] = useState(null);
    const [busy, setBusy] = useState(false);
    const done = state.stage === "done";
    const save = async (finish) => {
      setBusy(true); setError(null);
      try {
        const r = await api("/api/legend", { session_id: sid, text, finish });
        setScroll(r.scroll);
        if (r.done) onChange({ ...state, stage: "done" });
      } catch (e) { setError(e.message); } finally { setBusy(false); }
    };
    const words = text.trim() ? text.trim().split(/\s+/).length : 0;
    return html`<div class="panel stack">
      <h2>The hours return</h2>
      <${EndingText} turns=${state.ending} />
      <h3>Write the next legend</h3>
      <${Message} m=${{ who: "scroll", text: scroll.text, source: scroll.source, queue: true }} speakId=${"legend:" + scroll.text} />
      ${done ? html`<div><button class="btn primary" onClick=${onPlayAgain}>Play again</button></div>` : html`
        <textarea value=${text} onInput=${(e) => setText(e.target.value)} maxlength="3000"
          aria-label="Your legend chapter" placeholder="Wukong..."></textarea>
        <p class="muted">${words} words. The Scroll will ask questions, but you write the story.</p>
        <div class="row">
          <button class="btn primary" disabled=${busy || !text.trim()} onClick=${() => save(false)}>Save and ask the Scroll</button>
          <button class="btn" disabled=${busy} onClick=${() => save(true)}>Finish my legend</button>
        </div>`}
      <${ErrorLine} error=${error} />
    </div>`;
  }

  // -------------------------------------------------------- 10. teacher view
  function Teacher() {
    const [data, setData] = useState(null);
    const [error, setError] = useState(null);
    const [showTable, setShowTable] = useState(false);
    const [code, setCode] = useState(() => { try { return sessionStorage.getItem("mk_teacher") || ""; } catch (e) { return ""; } });
    const [needCode, setNeedCode] = useState(false);
    const load = (c) => api("/api/teacher?code=" + encodeURIComponent(c === undefined ? code : c))
      .then((d) => { setData(d); setNeedCode(false); setError(null); try { sessionStorage.setItem("mk_teacher", c === undefined ? code : c); } catch (e) { /* ok */ } })
      .catch((e) => { if (e.code === "teacher_code") setNeedCode(true); else setError(e.message); });
    useEffect(() => { load(); }, []);
    if (needCode) return html`<form class="panel stack" onSubmit=${(e) => { e.preventDefault(); load(code); }}>
      <h1>Teacher view</h1>
      <label for="tcode"><strong>Teacher code</strong></label>
      <input id="tcode" type="text" value=${code} onInput=${(e) => setCode(e.target.value)} autocomplete="off" />
      <div><button class="btn primary" type="submit">Show class numbers</button></div>
    </form>`;
    if (error) return html`<${ErrorLine} error=${error} />`;
    if (!data) return html`<p>Loading class numbers...</p>`;
    const c = data.cards;
    const has = (v) => v !== null && v !== undefined;
    const students = (n) => `based on ${n} student${n === 1 ? "" : "s"}`;
    // Every card shows HOW MANY students it is based on (review fix: report the sample size).
    const cards = [
      [has(c.predict.avg_out_of_6) ? c.predict.avg_out_of_6 + " / 6" : "–", "Predict-first accuracy",
        `${students(c.predict.n)} who answered all 6. So far: ${c.predict.correct_so_far} of ${c.predict.answered_so_far} predictions right.`],
      [has(c.timeline_first_try.pct) ? c.timeline_first_try.pct + "%" : "–", "Timeline right on the first try", students(c.timeline_first_try.n)],
      [has(c.duel_proof.avg_out_of_2) ? c.duel_proof.avg_out_of_2 + " / 2" : "–", "Spotting contradictions in the duel (first try)", students(c.duel_proof.n)],
      [has(c.trust_test.pct) ? c.trust_test.pct + "%" : "–", "Passed the trust test (first try)", students(c.trust_test.n)],
      [has(c.hints.avg) ? String(c.hints.avg) : "–", "Average hints used", students(c.hints.n) + " who finished"],
      [has(c.pre_post.pre_pct) ? `${c.pre_post.pre_pct}% → ${c.pre_post.post_pct}%` : "–", "Before vs after questions (% right)",
        students(c.pre_post.n) + ". Early evidence only, not proof."],
    ];
    const bars = data.hints_per_puzzle;
    const max = Math.max(1, ...bars.map((b) => b.hints));
    return html`<div class="stack">
      <div class="topbar"><h1 style=${{ margin: 0 }}>Teacher view</h1>
        <div class="row"><button class="btn small" onClick=${() => load()}>Refresh</button><a class="btn small" href="/">Back to the game</a></div></div>
      <p class="muted">Class totals only. ${data.players} players, ${data.finished} finished. We do not measure if students finish. We measure if they reason.</p>
      <div class="cards6">${cards.map(([v, l, n]) => html`<div class="stat" key=${l}>
        <div class="value">${v}</div><div class="label">${l}</div><div class="n">${n}</div></div>`)}</div>
      <div class="card chart">
        <h3>Hints used for each puzzle (all players)</h3>
        <p class="muted">Sorted from most hints to fewest. The top puzzle is the hardest idea for this class.</p>
        <div class="hbars" role="img" aria-label="Bar chart of hints used per puzzle">
          ${bars.map((b) => html`<div class="hbar-row" key=${b.puzzle}>
            <span class="hbar-label">${b.puzzle}</span>
            <span class="hbar-track"><span class="hbar" style=${{ width: (b.hints / max) * 100 + "%" }}></span></span>
            <span class="hbar-value">${b.hints}</span>
          </div>`)}
        </div>
        <p><button class="btn link" onClick=${() => setShowTable(!showTable)}>${showTable ? "Hide" : "Show"} the numbers as a table</button></p>
        ${showTable ? html`<table class="data"><thead><tr><th>Puzzle</th><th>Hints used</th></tr></thead><tbody>
          ${bars.map((b) => html`<tr key=${b.puzzle}><td>${b.puzzle}</td><td>${b.hints}</td></tr>`)}</tbody></table>` : null}
      </div>
      ${data.nicknames.length ? html`<p class="muted">Nicknames in this class: ${data.nicknames.join(", ")}</p>` : null}
    </div>`;
  }

  // ------------------------------------------------------------- the app
  function App() {
    const isTeacher = location.pathname.replace(/\/+$/, "") === "/teacher";
    const [sid, setSid] = useState(null);
    const [state, setState] = useState(null);
    const [screen, setScreen] = useState("title");  // title | pretest | prologue | map | realm | predict | reveal | game
    const [intro, setIntro] = useState(null);
    const [realmId, setRealmId] = useState(null);
    const [pending, setPending] = useState(null);
    const [reveal, setReveal] = useState(null);
    const [chat, setChat] = useState({});
    const [info, setInfo] = useState(false);
    const [canResume, setCanResume] = useState(false);

    useEffect(() => {
      if (isTeacher) return;
      const old = saved.get();
      if (old) api(`/api/state/${encodeURIComponent(old)}`).then(() => setCanResume(true)).catch(() => saved.clear());
    }, []);

    const addChat = (realm, m) => setChat((c) => ({ ...c, [realm]: [...(c[realm] || []), m] }));

    if (isTeacher) return html`<div class="app"><${Teacher} /></div>`;

    const start = async (nickname) => {
      const r = await api("/api/start", { nickname });
      saved.set(r.session_id);
      setSid(r.session_id); setState(r.state); setIntro(r); setChat({}); setScreen("pretest");
    };
    const resume = async () => {
      const id = saved.get();
      try {
        const s = await api(`/api/state/${encodeURIComponent(id)}`); setSid(id); setState(s);
        setScreen(s.stage === "pretest" ? "pretest" : ["prologue", "explore"].includes(s.stage) ? "map" : "game");
      }
      catch (e) { saved.clear(); setCanResume(false); }
    };
    const playAgain = () => { Voice.reset(); saved.clear(); setSid(null); setState(null); setCanResume(false); setScreen("title"); };
    const update = (s) => { setState(s); if (!["prologue", "explore"].includes(s.stage)) setScreen("game"); };

    let body;
    if (screen === "title") body = html`<${Title} onStart=${start} onResume=${resume} canResume=${canResume} />`;
    else if (screen === "pretest") body = html`<${Assessment} sid=${sid} phase="pre"
      onDone=${(s) => { setState(s); setScreen(intro ? "prologue" : "map"); }} />`;
    else if (screen === "prologue") body = html`<${Prologue} lines=${intro.prologue} grandma=${intro.grandmother_line} onDone=${() => setScreen("map")} />`;
    else if (screen === "map") body = html`<${RealmMap} state=${state} onPick=${(r) => { setRealmId(r); setScreen("realm"); }}
      onTimeline=${() => setScreen("game")} />`;
    else if (screen === "realm") body = html`<${RealmScene} sid=${sid} state=${state} realmId=${realmId} chat=${chat} addChat=${addChat}
      onChange=${setState} onOpen=${(p) => { setPending(p); setScreen("predict"); }} />`;
    else if (screen === "predict") body = html`<${Predict} sid=${sid} pending=${pending}
      onPredicted=${(r, choice) => { setReveal({ result: r, choice }); setState(r.state); setScreen("reveal"); }} />`;
    else if (screen === "reveal") body = html`<${Reveal} result=${reveal.result} choice=${reveal.choice}
      onKeep=${() => setScreen(reveal.result.all_found ? "map" : "realm")} />`;
    else if (state.stage === "timeline") body = html`<${Timeline} sid=${sid} state=${state} onSolved=${update} />`;
    else if (state.stage === "duel") body = html`<${Duel} key=${"duel"} sid=${sid} state=${state} onChange=${update} />`;
    else if (state.stage === "verdict") body = html`<${Verdict} sid=${sid} state=${state} onChange=${update} />`;
    else body = html`<${Ending} sid=${sid} state=${state} onChange=${setState} onPlayAgain=${playAgain} />`;

    const inGame = !["title", "prologue", "pretest"].includes(screen);
    return html`<div class="app">
      <div class="topline">
        ${inGame ? html`<${TopBar} state=${state} onInfo=${() => setInfo(true)}
          onMap=${["realm"].includes(screen) ? () => setScreen("map") : null} />` : html`<span></span>`}
        <${VoiceBar} />
      </div>
      ${body}
      ${info ? html`<${ScrollInfo} text=${state.scroll_info} onClose=${() => setInfo(false)} />` : null}
    </div>`;
  }

  ReactDOM.createRoot(document.getElementById("root")).render(html`<${App} />`);
})();
