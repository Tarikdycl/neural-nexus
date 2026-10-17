"""The game engine: fixed Python rules that make every decision (design rule 1).

It picks the hidden variant, unlocks pearls, checks the timeline, judges the
duel and the verdict, and picks the ending. The AI narrator is only asked to
put words around decisions that are already made, and it never writes hints.

Promises this file keeps, and the tests check:
  1. Hidden truth (culprit, true order, time labels, is_lie, proof pearls,
     reasons, variant id) never leaves the engine: not to the AI, not to the
     browser. Even pearl ids are hidden: the browser only sees per-game
     random codes, so sorting them cannot solve the timeline (review fix).
  2. The child can never lose. A wrong answer gives a hint and another try.
  3. Teacher numbers are honest: every number comes with how many students
     it is based on, and nothing is scaled up from partial answers.
  4. A player action is saved completely or not at all (store.atomic()), so
     a failed save can never leave a game stuck; retrying just works.
     Slow AI calls always happen OUTSIDE the transaction.
"""

from __future__ import annotations

import hashlib
import random
import secrets
import uuid
from typing import Any

from app import safety
from app.content import PEARL_IDS, SIGN_PLACEHOLDER
from app.narrator import Line, Narrator

TRUE_ORDER = list(PEARL_IDS)          # ["P1", ..., "P6"], from the content sheet
REALM_ACTIONS = ("look", "listen")
DUEL_ROUNDS = 3
MAX_HINT_LEVEL = 3
HINT_KEYS = PEARL_IDS + ["TIMELINE", "R1", "R2", "R3", "VERDICT"]
PUBLIC_PUZZLES = ("PREDICT", "TIMELINE", "DUEL", "VERDICT")   # what the browser may ask a hint for

# Stages, in play order. The engine refuses actions that do not fit the stage,
# so the browser cannot skip ahead (for example, duel before the timeline).
STAGES = ["pretest", "prologue", "explore", "timeline", "duel", "verdict", "posttest", "legend", "done"]


class GameError(Exception):
    """A request the rules do not allow. status: 400 bad input, 404 unknown, 409 wrong moment."""

    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


# --------------------------------------------------------------- pure rules
# Plain values in, plain values out, so they are easy to test on their own.

def check_timeline(order: list[str]) -> dict[str, Any]:
    """Compare an order of the 6 pearls with the true order (section 9).

    Wrong -> the FIRST neighbouring pair that is in the wrong order. Any order
    that is not fully correct always has at least one such pair.
    """
    if order == TRUE_ORDER:
        return {"correct": True}
    for a, b in zip(order, order[1:]):
        if TRUE_ORDER.index(a) > TRUE_ORDER.index(b):
            return {"correct": False, "pair": [a, b]}
    raise AssertionError("unreachable: a wrong permutation always has an out-of-order pair")


def proof_count(proof_pearls: str, proof_mode: str) -> int:
    """How many pearls the child must attach: 'all' -> every listed pearl, 'any' -> one of them."""
    return len(proof_pearls.split(",")) if proof_mode == "all" else 1


def check_duel_answer(said_lie: bool, proofs: list[str], reason: str, *, is_lie: int, proof_pearls: str,
                      proof_mode: str, reason_ok: str) -> bool:
    """Correct only if ALL three parts are right: Truth/Lie, the proof pearl(s), and the reason.

    proof_mode 'any': exactly one pearl, and it is one of proof_pearls (round 1).
    proof_mode 'all': exactly the pearls in proof_pearls, any order (rounds 2 and 3).
    """
    needed = proof_pearls.split(",")
    if bool(said_lie) != bool(is_lie) or reason != reason_ok:
        return False
    if proof_mode == "all":
        return len(proofs) == len(needed) and set(proofs) == set(needed)
    return len(proofs) == 1 and proofs[0] in needed


def check_verdict(named: str, proof_pair: list[str], culprit: str) -> bool:
    """Right culprit AND exactly the two sign pearls, P2 and P5, in any order."""
    return named == culprit and len(proof_pair) == 2 and set(proof_pair) == {"P2", "P5"}


def pearl_text(shared_text: str, sign: str | None) -> str:
    """Fill the [variant sign] slot. P1, P3, P4, P6 have no slot; their text is unchanged."""
    return " ".join(shared_text.replace(SIGN_PLACEHOLDER, sign or "").split())


def pearl_code(salt: str, pearl_id: str) -> str:
    """The code the browser sees for a pearl in one game. Different in every game, reveals no order."""
    return hashlib.sha256(f"{salt}:{pearl_id}".encode()).hexdigest()[:10]


# ------------------------------------------------------------------ engine

class Engine:
    def __init__(self, store: Any, narrator: Narrator, story: dict[str, Any],
                 rng: random.Random | None = None):
        self.store = store
        self.narrator = narrator
        self.story = story                  # UI-only text: prologue, legend questions, suspects
        self.rng = rng or random.SystemRandom()
        # Story tables never change while the game runs (the story locks), so
        # they are read once. Restart the server after editing the content.
        self._realms = {r["realm_id"]: r for r in store.realms()}
        self._realm_order = [r["realm_id"] for r in store.realms()]
        self._pearls = {p["pearl_id"]: p for p in store.pearls()}

    # ---------------------------------------------------------- helpers
    def _session(self, session_id: str) -> dict[str, Any]:
        s = self.store.session(session_id) if session_id else None
        if not s:
            raise GameError("unknown_session", "That adventure was not found. Please start a new one.", 404)
        return s

    def _realm(self, realm_id: str) -> dict[str, Any]:
        realm = self._realms.get(realm_id)
        if not realm:
            raise GameError("unknown_realm", "That place is not on the map.", 404)
        return realm

    def _require_stage(self, s: dict[str, Any], *stages: str) -> None:
        if s["stage"] not in stages:
            messages = {
                "pretest": "Answer the two quick questions first.",
                "prologue": "Explore the realms and find the pearls first.",
                "explore": "Find all six Memory Pearls first.",
                "timeline": "Put the pearls in time order on the Timeline Board first.",
                "duel": "Finish the duel with Wukong first.",
                "verdict": "Name the culprit first.",
                "posttest": "Answer the two last questions first.",
                "legend": "Your adventure is at the legend page.",
                "done": "This adventure is finished. Start a new one to play again.",
            }
            raise GameError("wrong_stage", messages.get(s["stage"], "Not now."), 409)

    # pearl codes: the browser never sees P1..P6
    def _code(self, s: dict[str, Any], pearl_id: str) -> str:
        return pearl_code(s["pearl_salt"], pearl_id)

    def _pearl_id(self, s: dict[str, Any], code: str) -> str | None:
        for pid in TRUE_ORDER:
            if self._code(s, pid) == code:
                return pid
        return None

    def _pearl_ids(self, s: dict[str, Any], codes: Any, error_code: str, message: str) -> list[str]:
        if not isinstance(codes, list) or not all(isinstance(c, str) for c in codes):
            raise GameError(error_code, message, 400)
        ids = [self._pearl_id(s, c) for c in codes]
        if None in ids:
            raise GameError(error_code, message, 400)
        return ids

    def _done_actions(self, session_id: str, realm_id: str) -> set[str]:
        return {a["action"] for a in self.store.actions(session_id) if a["realm_id"] == realm_id}

    def _can_open(self, session_id: str, realm_id: str) -> bool:
        # Section 9: a pearl opens only after Look AND Listen in that realm.
        return {"look", "listen"} <= self._done_actions(session_id, realm_id)

    def _opened_ids(self, session_id: str) -> list[str]:
        return [u["pearl_id"] for u in self.store.unlocks(session_id)]

    def _next_pearl_in_realm(self, session_id: str, realm_id: str) -> dict[str, Any] | None:
        opened = set(self._opened_ids(session_id))
        for pid in TRUE_ORDER:
            p = self._pearls[pid]
            if p["realm_id"] == realm_id and pid not in opened:
                return p
        return None

    def _pearl_view(self, s: dict[str, Any], pearl_id: str) -> dict[str, Any]:
        """What the browser may know about an opened pearl: a code, no id, no order, no time label."""
        p = self._pearls[pearl_id]
        sign = self.store.sign(pearl_id, s["variant_id"])
        return {"pearl": self._code(s, pearl_id), "realm_id": p["realm_id"], "title": p["title"],
                "text": pearl_text(p["shared_text"], sign), "visual": p.get("visual")}

    def _still_as_read(self, s: dict[str, Any]) -> None:
        """Call first inside atomic(). Locks this game, then checks nobody saved a step since we read it.

        Two clicks on "Answer" can arrive together. Both read the game before saving;
        without this, both would be saved. Now the second one waits, sees the first
        was saved, and stops without writing anything.
        """
        self.store.lock_session(s["session_id"])
        now = self.store.session(s["session_id"])
        if any(now[k] != s[k] for k in ("stage", "hairs_left", "legend_step")):
            raise GameError("already_saved", "That was already saved. The game has moved on.", 409)

    def _narration(self, key: str, **fill: str) -> dict[str, str]:
        """A storyteller line written by the team (story.json "narration"): 2-3 sentences, never AI."""
        return {"text": self.story["narration"][key].format(**fill), "source": "table"}

    def _ending_turns(self, s: dict[str, Any]) -> list[str]:
        """The ending, one narration turn (2-3 sentences) per line."""
        return [t.strip() for t in self.store.variant(s["variant_id"])["ending_text"].split("\n") if t.strip()]

    def _open_answer_phrases(self, session_id: str) -> list[str]:
        """Every answer choice of every prediction this player has NOT made yet.

        Review 2: the AI wrote "Select Early morning." An AI reply that repeats any of
        these choices is thrown away, so the Scroll can never answer a puzzle for the child.
        """
        done = {u["pearl_id"] for u in self.store.unlocks(session_id)}
        return [p[k] for pid, p in self._pearls.items() if pid not in done
                for k in ("predict_ok", "predict_no1", "predict_no2")]

    def _known_pages(self, s: dict[str, Any]) -> list[str]:
        """The ONLY story facts the AI may see: pearls this player already opened."""
        return [self._pearl_view(s, pid)["text"] for pid in self._opened_ids(s["session_id"])]

    def _scene(self, session_id: str, realm_id: str) -> tuple[str, str]:
        realm = self._realms[realm_id]
        done = self._done_actions(session_id, realm_id)
        seen = [realm["look_text"]] if "look" in done else []
        seen += [realm["listen_text"]] if "listen" in done else []
        return realm["name"], " ".join(seen)

    def _culprit_words(self, s: dict[str, Any]) -> list[str]:
        return self.store.variant(s["variant_id"])["culprit_words"]

    def _current_round(self, s: dict[str, Any]) -> int:
        return DUEL_ROUNDS - s["hairs_left"] + 1

    def _hint_level(self, session_id: str, puzzle_key: str) -> int:
        levels = [h["level_no"] for h in self.store.hint_uses(session_id) if h["puzzle_key"] == puzzle_key]
        return max(levels, default=0)

    def _give_hint(self, s: dict[str, Any], puzzle_key: str, public_name: str) -> dict[str, Any]:
        """Climb one step on the hint ladder (max 3).

        The words are shown EXACTLY as written in the hints table (review fix):
        the AI never rewrites a hint, so it can never make one stronger. Each
        new level is logged once, so "hints used" is 0 to 3 per puzzle.
        """
        sid = s["session_id"]
        current = self._hint_level(sid, puzzle_key)
        level = min(current + 1, MAX_HINT_LEVEL)
        if level > current:
            self.store.add_hint_use(sid, puzzle_key, level)
        return {"puzzle": public_name, "level": level, "max_level": MAX_HINT_LEVEL,
                "text": self.store.hint(puzzle_key, level), "source": "table"}

    @staticmethod
    def _line(line: Line) -> dict[str, str]:
        return {"text": line.text, "source": line.source}

    # ------------------------------------------------------- public state
    def state(self, session_id: str) -> dict[str, Any]:
        """Everything the browser needs to draw the current screen. Nothing hidden."""
        s = self._session(session_id)
        sid = s["session_id"]
        opened = self._opened_ids(sid)
        realms = []
        for rid in self._realm_order:
            r = self._realms[rid]
            done = self._done_actions(sid, rid)
            in_realm = [pid for pid in TRUE_ORDER if self._pearls[pid]["realm_id"] == rid]
            realms.append({
                "realm_id": rid, "name": r["name"], "image_url": r["image_url"],
                "enter_text": self.story["narration"]["realm_enter"][rid],
                "done_actions": sorted(done & set(REALM_ACTIONS)),
                "seen": {a: r[f"{a}_text"] for a in REALM_ACTIONS if a in done},
                "can_open_pearl": self._can_open(sid, rid) and any(p not in opened for p in in_realm),
                "pearls_total": len(in_realm),
                "pearls_found": sum(1 for p in in_realm if p in opened),
            })
        state: dict[str, Any] = {
            "session_id": sid,
            "nickname": s["nickname"],
            "stage": s["stage"],
            "hairs_left": s["hairs_left"],
            "pearls_found": len(opened),
            "pearls_total": len(TRUE_ORDER),
            "opened": [self._pearl_view(s, pid) for pid in opened],
            "realms": realms,
            "duel_round": self._current_round(s) if s["stage"] == "duel" else None,
            "suspects": list(self.story["suspects"]),
            "scroll_info": self.story["scroll_info"],
        }
        stage_lines = {"timeline": "all_found", "duel": "duel_intro", "verdict": "verdict_intro"}
        if s["stage"] in stage_lines:   # the storyteller's line for this part of the game
            state["stage_line"] = self._narration(stage_lines[s["stage"]])
        if s["stage"] in ("posttest", "legend", "done"):
            state["ending"] = self._ending_turns(s)
        if s["stage"] in ("legend", "done"):
            step = s["legend_step"]
            legend = self.story["legend"]
            if s["stage"] == "done":
                state["legend_prompt"] = legend["closing"]
            elif 0 < step <= len(legend["questions"]):
                state["legend_prompt"] = legend["questions"][step - 1]
            else:
                state["legend_prompt"] = legend["opening"]
            won = [v for v in self.store.verdicts(sid) if v["is_correct"]]
            state["legend_text"] = (won[-1]["legend_text"] or "") if won else ""
        return state

    # ---------------------------------------------------------- 1. start
    def start(self, nickname: str) -> dict[str, Any]:
        nick, problem = safety.check_nickname(nickname)
        if problem:
            raise GameError("bad_nickname", problem, 400)
        variant_id = self.rng.choice(self.store.variant_ids())   # the unpredictable part
        session_id = str(uuid.uuid4())
        self.store.create_session(session_id, nick, variant_id, secrets.token_hex(16))
        return {
            "session_id": session_id,
            "prologue": list(self.story["prologue"]),
            "grandmother_line": self.story["grandmother_line"],
            "scroll_info": self.story["scroll_info"],
            "state": self.state(session_id),
        }

    # --------------------------------------- before / after questions
    def assessment(self, session_id: str, phase: str) -> dict[str, Any]:
        """The short questions before play (pre) and after the verdict (post). No answers are sent."""
        s = self._session(session_id)
        if phase not in ("pre", "post"):
            raise GameError("bad_phase", "Unknown question set.", 404)
        self._require_stage(s, "pretest" if phase == "pre" else "posttest")
        items = []
        for i in self.store.assessment_items(phase):
            choices = [i["choice_ok"], i["choice_no1"], i["choice_no2"]]
            self.rng.shuffle(choices)
            items.append({"item_id": i["item_id"], "question": i["question"], "choices": choices})
        intro = self.story["assessment"]["pre_intro" if phase == "pre" else "post_intro"]
        return {"phase": phase, "intro": intro, "items": items}

    def submit_assessment(self, session_id: str, phase: str, answers: dict[str, str]) -> dict[str, Any]:
        s = self._session(session_id)
        if phase not in ("pre", "post"):
            raise GameError("bad_phase", "Unknown question set.", 404)
        self._require_stage(s, "pretest" if phase == "pre" else "posttest")
        items = {i["item_id"]: i for i in self.store.assessment_items(phase)}
        if not isinstance(answers, dict) or set(answers) != set(items):
            raise GameError("answer_all", "Please answer every question.", 400)
        for item_id, choice in answers.items():
            i = items[item_id]
            if choice not in (i["choice_ok"], i["choice_no1"], i["choice_no2"]):
                raise GameError("bad_choice", "Pick one of the three answers.", 400)
        try:
            with self.store.atomic():   # all answers + the stage change, or nothing
                for item_id, choice in answers.items():
                    self.store.add_assessment_answer(session_id, item_id, choice,
                                                     choice == items[item_id]["choice_ok"])
                self.store.update_session(session_id, stage="prologue" if phase == "pre" else "legend")
        except KeyError:
            raise GameError("already_answered", "You already answered these.", 409)
        # No score is shown to the child: this measures, it does not teach.
        return {"saved": True, "state": self.state(session_id)}

    # ------------------------------------------------- 2. look and listen
    def action(self, session_id: str, realm_id: str, action: str) -> dict[str, Any]:
        s = self._session(session_id)
        realm = self._realm(realm_id)
        if action not in REALM_ACTIONS:
            raise GameError("bad_action", "You can Look or Listen here.", 400)
        if s["stage"] in ("pretest", "done"):
            self._require_stage(s, "explore")
        with self.store.atomic():
            if s["stage"] == "prologue":
                self.store.update_session(session_id, stage="explore")
            self.store.log_action(session_id, realm_id, action)
        return {
            "text": realm[f"{action}_text"],
            "can_open_pearl": self._can_open(session_id, realm_id)
                              and self._next_pearl_in_realm(session_id, realm_id) is not None,
            "state": self.state(session_id),
        }

    # ------------------------------------------------- 3. ask the Scroll
    def ask(self, session_id: str, realm_id: str, question: str) -> dict[str, Any]:
        s = self._session(session_id)
        self._realm(realm_id)
        if s["stage"] == "pretest":
            self._require_stage(s, "explore")
        q = safety.clean_text(question, safety.MAX_QUESTION_CHARS)
        if not q:
            raise GameError("empty_question", "Type a question for the Scroll.", 400)
        self.store.log_action(session_id, realm_id, "ask")
        # Input checks happen BEFORE the AI call (section 11 + review fix).
        if safety.is_rude(q):
            return {"reply": {"text": self.story["fallbacks"]["scroll_kind_words"], "source": "fallback"}}
        if safety.is_injection(q):
            return {"reply": {"text": self.story["fallbacks"]["scroll_redirect"], "source": "fallback"}}
        scene_name, scene_text = self._scene(session_id, realm_id)
        line = self.narrator.scroll(
            scene_name=scene_name, scene_text=scene_text, known_pages=self._known_pages(s),
            question=q, culprit_words=self._culprit_words(s),
            answer_phrases=self._open_answer_phrases(session_id),
        )
        return {"reply": self._line(line)}

    # ---------------------------------------- 4. open pearl (predict first)
    def open_pearl(self, session_id: str, realm_id: str) -> dict[str, Any]:
        s = self._session(session_id)
        self._realm(realm_id)
        self._require_stage(s, "prologue", "explore")
        if not self._can_open(session_id, realm_id):
            raise GameError("look_and_listen_first", "Use Look and Listen here before you open a pearl.", 409)
        p = self._next_pearl_in_realm(session_id, realm_id)
        if p is None:
            raise GameError("realm_done", "You found every pearl in this place.", 409)
        choices = [p["predict_ok"], p["predict_no1"], p["predict_no2"]]
        self.rng.shuffle(choices)  # section 4: correct choice listed first in the sheet, shuffled on screen
        return {"pearl": self._code(s, p["pearl_id"]), "question": p["predict_q"], "choices": choices}

    # --------------------------------------------- 5. predict, then reveal
    def predict(self, session_id: str, pearl: str, choice: str) -> dict[str, Any]:
        s = self._session(session_id)
        self._require_stage(s, "prologue", "explore")
        pearl_id = self._pearl_id(s, pearl)
        if not pearl_id:
            raise GameError("unknown_pearl", "That pearl does not exist.", 404)
        p = self._pearls[pearl_id]
        if pearl_id in self._opened_ids(session_id):
            raise GameError("already_opened", "You already opened that pearl.", 409)
        if not self._can_open(session_id, p["realm_id"]):
            raise GameError("look_and_listen_first", "Use Look and Listen there before you open a pearl.", 409)
        nxt = self._next_pearl_in_realm(session_id, p["realm_id"])
        if nxt is None or nxt["pearl_id"] != pearl_id:
            raise GameError("not_this_pearl", "Open the pearl the Scroll shows you.", 409)
        if choice not in (p["predict_ok"], p["predict_no1"], p["predict_no2"]):
            raise GameError("bad_choice", "Pick one of the three answers.", 400)

        predicted_ok = choice == p["predict_ok"]
        actions_before = sum(1 for a in self.store.actions(session_id) if a["realm_id"] == p["realm_id"])
        try:
            with self.store.atomic():   # the pearl AND the stage change (6th pearl -> timeline), or nothing
                self.store.add_unlock(session_id, pearl_id, predicted_ok, actions_before)
                found = len(self._opened_ids(session_id))
                if found == len(TRUE_ORDER):
                    self.store.update_session(session_id, stage="timeline")
                elif s["stage"] == "prologue":
                    self.store.update_session(session_id, stage="explore")
        except KeyError:
            raise GameError("already_opened", "You already opened that pearl.", 409)
        return {
            "pearl": self._pearl_view(s, pearl_id),
            "prediction_matches": predicted_ok,
            "narration": self._narration("predict_match" if predicted_ok else "predict_differ"),
            "pearls_found": found,
            "all_found": found == len(TRUE_ORDER),
            "state": self.state(session_id),
        }

    # ---------------------------------------------------- hint ladder
    def hint(self, session_id: str, puzzle: str, realm_id: str | None = None) -> dict[str, Any]:
        """A hint for the puzzle on screen. The browser names the KIND of puzzle; the engine
        works out which one it is, so the request reveals nothing either."""
        s = self._session(session_id)
        if puzzle not in PUBLIC_PUZZLES:
            raise GameError("unknown_puzzle", "There is no puzzle with that name.", 404)
        if puzzle == "PREDICT":
            self._require_stage(s, "prologue", "explore")
            self._realm(realm_id or "")
            nxt = self._next_pearl_in_realm(session_id, realm_id)
            if not (self._can_open(session_id, realm_id) and nxt):
                raise GameError("not_now", "That puzzle is not open right now.", 409)
            key = nxt["pearl_id"]
        elif puzzle == "TIMELINE":
            self._require_stage(s, "timeline")
            key = "TIMELINE"
        elif puzzle == "DUEL":
            self._require_stage(s, "duel")
            key = f"R{self._current_round(s)}"
        else:
            self._require_stage(s, "verdict")
            key = "VERDICT"
        with self.store.atomic():
            return {"hint": self._give_hint(s, key, puzzle)}

    # ------------------------------------------------- 6. timeline board
    def timeline(self, session_id: str, order: list[str]) -> dict[str, Any]:
        s = self._session(session_id)
        self._require_stage(s, "timeline")
        ids = self._pearl_ids(s, order, "bad_order", "Place all six pearls, each one once.")
        if sorted(ids) != sorted(TRUE_ORDER):
            raise GameError("bad_order", "Place all six pearls, each one once.", 400)
        result = check_timeline(ids)
        with self.store.atomic():   # the try AND (if right) the move to the duel, or nothing
            self._still_as_read(s)
            try_no = self.store.add_timeline_try(session_id, ",".join(ids), result["correct"])
            if result["correct"]:
                self.store.update_session(session_id, stage="duel", hairs_left=DUEL_ROUNDS)
        if result["correct"]:
            return {"correct": True, "try_no": try_no, "narration": self._narration("timeline_solved"),
                    "state": self.state(session_id)}
        a, b = result["pair"]
        # Section 3: the Scroll asks about the first wrong pair, without saying which pearl is wrong.
        return {"correct": False, "try_no": try_no, "pair": [self._code(s, a), self._code(s, b)],
                "scroll": self._narration("timeline_pair", a=self._pearls[a]["title"], b=self._pearls[b]["title"])}

    # ------------------------------------------------------- 7. the duel
    def duel_claim(self, session_id: str, round_no: int) -> dict[str, Any]:
        s = self._session(session_id)
        self._require_stage(s, "duel")
        if round_no != self._current_round(s):
            raise GameError("wrong_round", f"Wukong is on round {self._current_round(s)}.", 409)
        r = self.store.duel_round(round_no, s["variant_id"])
        wrong_tries = sum(1 for d in self.store.duel_answers(session_id)
                          if d["round_no"] == round_no and not d["is_correct"])
        reasons = [r["reason_ok"], r["reason_no1"], r["reason_no2"]]
        self.rng.shuffle(reasons)
        # form, claim, how many pearls to attach, and shuffled reasons. Never is_lie, proofs or the right reason.
        return {"round": round_no, "form_name": r["form_name"], "claim": r["claim_text"],
                "hairs_left": s["hairs_left"], "copies": wrong_tries,
                "proof_count": proof_count(r["proof_pearls"], r["proof_mode"]), "reasons": reasons}

    def duel(self, session_id: str, round_no: int, said_lie: bool, proofs: list[str], reason: str) -> dict[str, Any]:
        s = self._session(session_id)
        self._require_stage(s, "duel")
        if round_no != self._current_round(s):
            raise GameError("wrong_round", f"Wukong is on round {self._current_round(s)}.", 409)
        r = self.store.duel_round(round_no, s["variant_id"])
        need = proof_count(r["proof_pearls"], r["proof_mode"])
        word = "one pearl" if need == 1 else f"{need} different pearls"
        ids = self._pearl_ids(s, proofs, "bad_proof", f"Pick {word} as proof.")
        if len(ids) != need or len(set(ids)) != need or not set(ids) <= set(self._opened_ids(session_id)):
            raise GameError("bad_proof", f"Pick {word} as proof.", 400)
        if reason not in (r["reason_ok"], r["reason_no1"], r["reason_no2"]):
            raise GameError("bad_reason", "Pick one of the reasons.", 400)
        correct = check_duel_answer(said_lie, ids, reason, is_lie=r["is_lie"], proof_pearls=r["proof_pearls"],
                                    proof_mode=r["proof_mode"], reason_ok=r["reason_ok"])
        hairs = s["hairs_left"] - 1 if correct else s["hairs_left"]
        with self.store.atomic():   # the answer AND the hair (or the hint), or nothing
            self._still_as_read(s)
            self.store.add_duel_answer(session_id, round_no, said_lie, ",".join(sorted(ids)), reason, correct)
            if correct:
                self.store.update_session(session_id, hairs_left=hairs,
                                          **({"stage": "verdict"} if hairs == 0 else {}))
            else:
                hint = self._give_hint(s, f"R{round_no}", "DUEL")
        # The AI is called only after the save is complete, never inside the transaction.
        if correct:
            taunt = self.narrator.wukong(event="correct", form_name=r["form_name"])
            return {"correct": True, "hairs_left": hairs, "taunt": self._line(taunt),
                    "next_round": round_no + 1 if hairs > 0 else None, "duel_over": hairs == 0,
                    "state": self.state(session_id)}
        taunt = self.narrator.wukong(event="wrong", form_name=r["form_name"])
        copies = sum(1 for d in self.store.duel_answers(session_id)
                     if d["round_no"] == round_no and not d["is_correct"])
        # We never say which part was wrong (Truth/Lie, pearl, or reason).
        return {"correct": False, "hairs_left": s["hairs_left"], "taunt": self._line(taunt),
                "hint": hint, "copies": copies}

    # ---------------------------------------------------- 8. the verdict
    def verdict(self, session_id: str, named: str, proof: list[str]) -> dict[str, Any]:
        s = self._session(session_id)
        self._require_stage(s, "verdict")
        if named not in self.story["suspects"]:
            raise GameError("bad_suspect", "Name one of the suspects.", 400)
        ids = self._pearl_ids(s, proof, "bad_proof", "Attach two different pearls as proof.")
        if len(ids) != 2 or len(set(ids)) != 2 or not set(ids) <= set(self._opened_ids(session_id)):
            raise GameError("bad_proof", "Attach two different pearls as proof.", 400)
        culprit = self.store.variant(s["variant_id"])["culprit"]
        correct = check_verdict(named, ids, culprit)
        with self.store.atomic():   # the verdict AND the stage change (or the hint), or nothing
            self._still_as_read(s)
            self.store.add_verdict(session_id, named, ",".join(sorted(ids)), correct)
            if correct:
                self.store.update_session(session_id, stage="posttest", legend_step=0)
            else:
                hint = self._give_hint(s, "VERDICT", "VERDICT")
        if correct:
            return {"correct": True, "ending": self._ending_turns(s),
                    "state": self.state(session_id)}
        return {"correct": False, "hint": hint}

    # --------------------------------------------- 9. write the next legend
    def legend(self, session_id: str, text: str, finish: bool = False) -> dict[str, Any]:
        s = self._session(session_id)
        self._require_stage(s, "legend")
        chapter = (text or "").strip()[:safety.MAX_LEGEND_CHARS]
        if not chapter and not finish:
            raise GameError("empty_legend", "Write a few words of your legend first.", 400)
        words = len(chapter.split())
        questions = self.story["legend"]["questions"]
        step = s["legend_step"]
        done = finish or step >= len(questions)
        with self.store.atomic():   # the chapter AND the progress, or nothing
            self._still_as_read(s)
            if chapter:
                self.store.set_legend(session_id, chapter)
            if done:
                self.store.update_session(session_id, stage="done")
            else:
                self.store.update_session(session_id, legend_step=step + 1)
        # The Scroll asks up to 3 questions and never writes the chapter itself.
        if done:
            return {"saved": bool(chapter), "words": words, "done": True,
                    "scroll": {"text": self.story["legend"]["closing"], "source": "table"}}
        return {"saved": True, "words": words, "done": False,
                "scroll": {"text": questions[step], "source": "table"}}

    # ----------------------------------------------- 10. teacher numbers
    def teacher(self) -> dict[str, Any]:
        labels = {pid: f"Predict: {p['title']}" for pid, p in self._pearls.items()}
        # Labels never hint at an answer (no "true claim"), in case a child opens the teacher page.
        labels.update({"TIMELINE": "Timeline board", "R1": "Duel round 1", "R2": "Duel round 2",
                       "R3": "Duel round 3", "VERDICT": "Final verdict"})
        return teacher_metrics(self.store.all_play_data(), labels)


def _avg(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 2) if values else None


def _pct(values: list[float]) -> int | None:
    return round(100 * sum(values) / len(values)) if values else None


FINISHED_STAGES = ("posttest", "legend", "done")


def teacher_metrics(data: dict[str, list[dict[str, Any]]], labels: dict[str, str]) -> dict[str, Any]:
    """Class totals for section 5. No per-student numbers leave this function.

    Every number comes with n, the number of students it is based on, and
    nothing is scaled up from partial answers (review fix: 1 right of 1 used
    to show as 6/6).

      predict           avg correct out of 6, ONLY over students who answered all 6;
                        plus the raw count of correct / answered predictions so far
      timeline_first_try % right on the first Check, over students who pressed Check
      duel_proof        rounds 1 and 3, right on the first try, out of 2, over students who answered both
      trust_test        round 2 (the true claim), right on the first try, over students who answered it
      hints             hints used per student, over students who FINISHED (verdict solved)
      pre_post          % right before vs after, over students who answered both sets
    """
    group = _group
    sessions = data["sessions"]
    unlocks, tl, duel = group(data["unlocks"]), group(data["timeline_tries"]), group(data["duel_answers"])
    hints, verdicts = group(data["hint_uses"]), group(data["verdicts"])
    assess = group(data.get("assessment_answers", []))

    complete = [rows for rows in unlocks.values() if len(rows) == 6]
    predict_scores = [float(sum(u["predicted_ok"] for u in rows)) for rows in complete]
    first_try = [1.0 if any(t["try_no"] == 1 and t["is_correct"] for t in rows) else 0.0
                 for rows in tl.values() if rows]

    proof_scores, trust = [], []
    for rows in duel.values():
        firsts = {d["round_no"]: d["is_correct"] for d in rows if d["try_no"] == 1}
        if 1 in firsts and 3 in firsts:
            proof_scores.append(float(firsts[1] + firsts[3]))
        if 2 in firsts:
            trust.append(float(firsts[2]))

    finished = [s["session_id"] for s in sessions if s["stage"] in FINISHED_STAGES]
    hint_counts = [float(len(hints.get(sid, []))) for sid in finished]
    per_puzzle: dict[str, int] = {key: 0 for key in labels}
    for h in data["hint_uses"]:
        if h["puzzle_key"] in per_puzzle:
            per_puzzle[h["puzzle_key"]] += 1
    # Sorted by count, never by puzzle order, so the chart cannot reveal the timeline.
    chart = sorted(({"puzzle": labels[k], "hints": v} for k, v in per_puzzle.items()),
                   key=lambda x: (-x["hints"], x["puzzle"]))

    pre, post = [], []
    for rows in assess.values():
        p_rows = [a for a in rows if a["item_id"].startswith("PRE")]
        q_rows = [a for a in rows if a["item_id"].startswith("POST")]
        if p_rows and q_rows:
            pre.append(sum(a["is_correct"] for a in p_rows) / len(p_rows))
            post.append(sum(a["is_correct"] for a in q_rows) / len(q_rows))

    observation = [float(u["actions_before"]) for u in data["unlocks"]]
    legend_words = [float(len((v["legend_text"] or "").split())) for rows in verdicts.values()
                    for v in rows if v["is_correct"] and v["legend_text"]]

    return {
        "players": len(sessions),
        "nicknames": sorted({s["nickname"] for s in sessions}),
        "finished": len(finished),
        "cards": {
            "predict": {"avg_out_of_6": _avg(predict_scores), "n": len(complete),
                        "correct_so_far": sum(u["predicted_ok"] for u in data["unlocks"]),
                        "answered_so_far": len(data["unlocks"])},
            "timeline_first_try": {"pct": _pct(first_try), "n": len(first_try)},
            "duel_proof": {"avg_out_of_2": _avg(proof_scores), "n": len(proof_scores)},
            "trust_test": {"pct": _pct(trust), "n": len(trust)},
            "hints": {"avg": _avg(hint_counts), "n": len(hint_counts)},
            "pre_post": {"pre_pct": _pct(pre), "post_pct": _pct(post), "n": len(pre)},
        },
        "hints_per_puzzle": chart,
        "extra": {
            "avg_actions_before_pearl": _avg(observation),
            "avg_legend_words": _avg(legend_words),
        },
    }


def _group(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        out.setdefault(r["session_id"], []).append(r)
    return out
