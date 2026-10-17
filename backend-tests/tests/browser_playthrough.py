"""Play the whole game in a real browser (Chromium via Playwright) and screenshot every screen.

Not part of the fast pytest suite, because it needs a running server and a browser:
    uvicorn app.main:app --port 8765          # in one terminal
    python tests/browser_playthrough.py http://127.0.0.1:8765 screenshots/

It finds the right duel answers from the content sheet. It never reads hidden
data from the server, so it plays exactly like a careful child would.

Laptop screens only (the game is for laptops). Three runs:
  * "record": the browser's speech engine is replaced by a recorder, so the test can
    check what the narrator SAYS: which voice, how deep and slow, each line once,
    every narration turn 2-3 sentences, and that Mute, Skip and Replay work.
  * "fail":   every spoken line fails. The game must carry on, with captions.
  * "none":   the browser has no speech at all. Captions only, game carries on.
"""

import json
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "screenshots")
OUT.mkdir(parents=True, exist_ok=True)
STORY = json.loads((Path(__file__).resolve().parent.parent / "content" / "story.json").read_text())
TITLES = {p["pearl_id"]: p["title"] for p in STORY["pearls"]}
CORRECT = {p["predict_q"]: p["predict_ok"] for p in STORY["pearls"]}
# Duel answers a child can work out from the pearls: round -> (lie?, proof pearls, reason).
REASON = {r["round_no"]: r["reason_ok"] for r in STORY["duel_rounds"]}
DUEL = {1: (True, ["P2"], REASON[1]), 2: (False, ["P4", "P5"], REASON[2]), 3: (True, ["P2", "P3"], REASON[3])}
SIGN_TO_CULPRIT = {"golden hair": "Sun Wukong", "paw prints": "Jade Rabbit", "puddle": "Dragon King"}
SENTENCE = re.compile(r"[^.!?]+[.!?]+[\"')\]]*|[^.!?]+$")   # the same rule as app/safety.py

# Stands in for window.speechSynthesis. "Google UK English Male" is in the game's preferred
# list, so the game should choose it over the default (US) and the female voice.
FAKE_SPEECH = """
(() => {
  const mode = "%s";
  if (mode === "none") { window.SpeechSynthesisUtterance = undefined; return; }
  const voices = [
    { name: "Google US English", lang: "en-US", voiceURI: "g-us", default: true },
    { name: "Google UK English Female", lang: "en-GB", voiceURI: "g-uk-f", default: false },
    { name: "Google UK English Male", lang: "en-GB", voiceURI: "g-uk-m", default: false },
    { name: "Google Deutsch", lang: "de-DE", voiceURI: "g-de", default: false },
  ];
  window.__spoken = []; window.__cancels = 0;
  window.SpeechSynthesisUtterance = function (text) { this.text = text; this.pitch = 1; this.rate = 1; this.voice = null; };
  const synth = {
    speaking: false, pending: false,
    getVoices() { return voices; },
    addEventListener() {},
    speak(u) {
      window.__spoken.push({ text: u.text, pitch: u.pitch, rate: u.rate, voice: u.voice && u.voice.name });
      setTimeout(() => {
        if (mode === "fail") { if (u.onerror) u.onerror({ error: "synthesis-failed" }); return; }
        synth.speaking = true; if (u.onstart) u.onstart();
        setTimeout(() => { synth.speaking = false; if (u.onend) u.onend(); }, 700);
      }, 0);
    },
    cancel() { window.__cancels += 1; synth.speaking = false; },
  };
  Object.defineProperty(window, "speechSynthesis", { value: synth, configurable: true });
})();
"""


def sentences(text):
    return len([x for x in SENTENCE.findall(" ".join(text.split())) if x.strip()])


def shot(page, name):
    page.wait_for_timeout(400)
    page.screenshot(path=str(OUT / f"{name}.png"), full_page=True)
    print("screenshot", name)


def spoken(page):
    return page.evaluate("window.__spoken || []")


def run(prefix, speech="record", full=True, wrong_first=True, width=1280, height=860):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": width, "height": height})
        page.add_init_script(FAKE_SPEECH % speech)
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        # Google Fonts may be unreachable offline; the page falls back to built-in fonts, so that is not a failure.
        offline = ("ERR_TUNNEL_CONNECTION_FAILED", "ERR_NAME_NOT_RESOLVED", "ERR_INTERNET_DISCONNECTED")
        page.on("console", lambda m: errors.append(m.text)
                if m.type == "error" and not any(o in m.text for o in offline) else None)

        page.goto(BASE + "/")
        page.get_by_label("Your nickname").fill("Brave Bamboo")
        shot(page, f"{prefix}01_title")
        if speech == "record":   # the listening test: choose a voice and hear the sample line
            page.get_by_role("button", name="Voice settings").click()
            page.get_by_role("button", name="Test voice").click()
            page.wait_for_timeout(200)
            assert "misplaced an hour" in spoken(page)[-1]["text"]
            shot(page, f"{prefix}01a_voice_settings")
            page.get_by_role("button", name="Done").click()
        page.get_by_role("button", name="Begin").click()

        page.get_by_role("heading", name="Before the adventure").wait_for()
        for q in page.locator("fieldset.question").all():
            q.locator(".choices .btn").first.click()
        shot(page, f"{prefix}01b_before_questions")
        page.get_by_role("button", name="Done").click()

        page.get_by_role("button", name="Tap to continue").wait_for()
        if speech == "record":
            page.get_by_role("button", name="Skip").click()          # enabled only while the narrator speaks
            assert page.evaluate("window.__cancels") >= 1, "Skip did not stop the voice"
        for _ in range(5):
            page.get_by_role("button", name="Tap to continue").click()
            page.wait_for_timeout(150)
        shot(page, f"{prefix}02_prologue")
        page.get_by_role("button", name="Take the Scroll").click()

        page.get_by_text("Choose a realm").wait_for()
        shot(page, f"{prefix}03_map")

        for i, realm in enumerate(["Bamboo Forest", "East Sea Shore", "Moon Palace Stairs"]):
            page.get_by_role("button", name=realm).click()
            if speech == "record" and i == 2:     # Mute: the next line is shown but not spoken
                page.get_by_role("button", name="Mute").click()
                before = len(spoken(page))
            page.get_by_role("button", name="Look", exact=True).click()
            page.get_by_role("button", name="Listen", exact=True).click()
            page.get_by_text("You listen:").wait_for()
            if speech == "record" and i == 2:
                page.wait_for_timeout(300)
                assert len(spoken(page)) == before, "a muted narrator still spoke"
                page.get_by_role("button", name="Unmute").click()
            if speech == "record" and i == 1:     # Replay says the line again, on request
                before = len(spoken(page))
                page.locator(".msg.scroll .replay").first.click()
                page.wait_for_timeout(200)
                assert spoken(page)[-1]["text"] == STORY["narration"]["realm_enter"]["sea"], spoken(page)[-1]
            if i == 0:
                page.get_by_label("Ask the Scroll a question").fill("Who broke the hourglass?")
                page.get_by_role("button", name="Send").click()
                page.locator(".msg.scroll").nth(1).wait_for()
                shot(page, f"{prefix}04_realm_scene")
            for k in range(2):
                page.get_by_role("button", name="Open pearl", exact=True).click()
                q = page.locator(".panel p").first.inner_text()
                if i == 0 and k == 0:
                    page.get_by_role("button", name="Ask the Scroll for a hint").click()
                    page.locator(".msg.scroll").wait_for()
                    shot(page, f"{prefix}05_predict")
                page.get_by_role("button", name=CORRECT[q], exact=True).click()
                page.get_by_role("button", name="Keep the pearl").wait_for()
                if i == 0 and k == 1:
                    shot(page, f"{prefix}06_reveal")
                if not full:
                    check_captions_only(page, speech, prefix, errors, browser)
                    return
                page.get_by_role("button", name="Keep the pearl").click()
            if i < 2:
                page.get_by_role("button", name="Back to map").click()

        page.get_by_role("button", name="Go to the Timeline Board").click()
        page.get_by_text("The Timeline Board").wait_for()
        order = ["P2", "P1", "P3", "P4", "P5", "P6"] if wrong_first else ["P1", "P2", "P3", "P4", "P5", "P6"]
        for slot, pid in enumerate(order):
            page.locator(".pearl-cards .pearl-card", has_text=TITLES[pid]).click()
            page.locator(".slot").nth(slot).click()
        page.get_by_role("button", name="Check").click()
        if wrong_first:
            page.locator(".msg.scroll").first.wait_for()
            shot(page, f"{prefix}07_timeline_wrong")
            # take back the first two and swap them
            page.locator(".slot").nth(0).locator(".pearl-card").click()
            page.locator(".slot").nth(1).locator(".pearl-card").click()
            for slot, pid in enumerate(["P1", "P2"]):
                page.locator(".pearl-cards .pearl-card", has_text=TITLES[pid]).click()
                page.locator(".slot").nth(slot).click()
            page.get_by_role("button", name="Check").click()
        page.get_by_text("The board glows").wait_for()
        shot(page, f"{prefix}07b_timeline_right")

        for rnd in (1, 2, 3):
            page.get_by_text(f"round {rnd} of 3").wait_for()
            page.wait_for_timeout(700)
            lie, proofs, reason = DUEL[rnd]
            if rnd == 2 and wrong_first:  # most people call round 2 a lie
                page.get_by_role("button", name="Lie", exact=True).click()
                for pid in proofs:
                    page.locator(".picker .pearl-card", has_text=TITLES[pid]).click()
                page.get_by_role("button", name=reason, exact=True).click()
                page.get_by_role("button", name="Answer Wukong").click()
                page.locator(".msg.wukong").last.wait_for()
                page.wait_for_timeout(300)
                shot(page, f"{prefix}08_duel_wrong")
                for pid in proofs:   # un-pick, so the right answer below starts clean
                    page.locator(".picker .pearl-card", has_text=TITLES[pid]).click()
            page.get_by_role("button", name="Lie" if lie else "Truth", exact=True).click()
            for pid in proofs:
                page.locator(".picker .pearl-card", has_text=TITLES[pid]).click()
            page.get_by_role("button", name=reason, exact=True).click()
            if rnd == 3:
                shot(page, f"{prefix}08_duel")
            page.get_by_role("button", name="Answer Wukong").click()
            page.wait_for_timeout(1600)

        page.get_by_text("Final verdict").wait_for()
        sign_text = page.locator(".picker .pearl-card", has_text=TITLES["P2"]).inner_text().lower()
        culprit = next(c for s, c in SIGN_TO_CULPRIT.items() if s in sign_text)
        page.get_by_role("button", name=culprit).click()
        page.locator(".picker .pearl-card", has_text=TITLES["P2"]).click()
        page.locator(".picker .pearl-card", has_text=TITLES["P5"]).click()
        shot(page, f"{prefix}08c_verdict")
        page.get_by_role("button", name="Name the culprit").click()

        page.get_by_role("heading", name="Two last questions").wait_for()
        for q in page.locator("fieldset.question").all():
            q.locator(".choices .btn").first.click()
        shot(page, f"{prefix}08d_after_questions")
        page.get_by_role("button", name="Done").click()

        page.get_by_text("Write the next legend").wait_for()
        page.get_by_label("Your legend chapter").fill("Wukong flies to the East Sea to help the Dragon King find rain clouds.")
        page.get_by_role("button", name="Save and ask the Scroll").click()
        page.get_by_text("Where does he go?").wait_for()
        shot(page, f"{prefix}09_ending_legend")
        page.get_by_role("button", name="Finish my legend").click()
        page.get_by_role("button", name="Play again").wait_for()

        said = spoken(page)          # before leaving the page: the recording lives in it
        page.goto(BASE + "/teacher")
        page.get_by_text("Teacher view").first.wait_for()
        page.wait_for_timeout(500)
        shot(page, f"{prefix}10_teacher")

        browser.close()
        if errors:
            print("BROWSER ERRORS:", errors)
            sys.exit(1)
        check_voice(said)
        print(f"{prefix}: full game played, culprit was {culprit}, {len(said)} lines spoken, no browser errors")


def check_voice(said):
    """What the narrator said during one whole game (speech replaced by a recorder)."""
    narrator = [x for x in said if x["pitch"] == 0.8]
    wukong = [x for x in said if x["pitch"] == 1.25]
    texts = [x["text"] for x in said]
    assert narrator and wukong, "both voices should be heard"
    for x in narrator:   # deep, unhurried, the preferred laptop voice
        assert (x["voice"], x["rate"]) == ("Google UK English Male", 0.88), x
    for line in STORY["prologue"] + list(STORY["narration"]["realm_enter"].values()):
        assert line in texts, f"never spoken: {line}"
    for line in STORY["prologue"] + [STORY["narration"]["realm_enter"]["bamboo"], STORY["narration"]["realm_enter"]["moon"]]:
        assert texts.count(line) == 1, f"spoken {texts.count(line)} times: {line}"   # each new line once
    for key in ("all_found", "timeline_solved", "duel_intro", "verdict_intro"):
        assert STORY["narration"][key] in texts, f"never spoken: {key}"
    for x in narrator:   # review 2: every narration turn is 2-3 sentences
        assert 2 <= sentences(x["text"]) <= 3, x["text"]
    print(f"voice: {len(narrator)} narrator lines, all 2-3 sentences, deep voice; {len(wukong)} Wukong lines")


def check_captions_only(page, speech, prefix, errors, browser):
    """Speech failed or is missing: the words are still on screen and the game goes on."""
    note = "Voice not working here" if speech == "fail" else "Captions only"
    page.get_by_text(note).wait_for()
    page.locator(".memory").wait_for()
    shot(page, f"{prefix}reveal_without_voice")
    page.get_by_role("button", name="Keep the pearl").click()
    page.get_by_role("button", name="Open pearl", exact=True).wait_for()
    browser.close()
    if errors:
        print("BROWSER ERRORS:", errors)
        sys.exit(1)
    print(f"{prefix}: speech '{speech}': captions shown, game carried on, no browser errors")


if __name__ == "__main__":
    run("laptop_", speech="record")
    run("laptop_voice_fails_", speech="fail", full=False)
    run("laptop_no_voice_", speech="none", full=False)
