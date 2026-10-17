"""In-memory store: the doc's fallback "load the content into a Python dictionary".

Used when the database is unreachable, for laptop demos, and for fast tests.
It has exactly the same methods as MySQLStore, so the engine cannot tell
which one it is talking to. Play data is lost when the server restarts.
"""

from __future__ import annotations

import copy
import threading
from contextlib import contextmanager
from typing import Any, Iterator

from app.content import load_story


class MemoryStore:
    kind = "memory"

    def __init__(self, story: dict[str, Any] | None = None):
        story = story or load_story()
        self._variants = {
            v["variant_id"]: {
                "variant_id": v["variant_id"],
                "culprit": v["culprit"],
                "culprit_words": list(v["culprit_words"]),
                "ending_text": v["ending_text"],
            }
            for v in story["variants"]
        }
        self._realms = sorted((dict(r) for r in story["realms"]), key=lambda r: r["display_order"])
        self._pearls = sorted((dict(p) for p in story["pearls"]), key=lambda p: p["true_order"])
        self._signs = {(s["pearl_id"], s["variant_id"]): s["sign_text"] for s in story["pearl_signs"]}
        self._rounds = {(r["round_no"], r["variant_id"]): dict(r) for r in story["duel_rounds"]}
        self._hints = {(h["puzzle_key"], h["level_no"]): h["hint_text"] for h in story["hints"]}
        self._items = [dict(i) for i in story["assessment"]["items"]]
        self._lock = threading.RLock()   # re-entrant, so atomic() can hold it while methods run
        self._sessions: dict[str, dict[str, Any]] = {}
        self._actions: list[dict[str, Any]] = []
        self._unlocks: list[dict[str, Any]] = []
        self._timeline: list[dict[str, Any]] = []
        self._duel: list[dict[str, Any]] = []
        self._hint_uses: list[dict[str, Any]] = []
        self._verdicts: list[dict[str, Any]] = []
        self._assessment: list[dict[str, Any]] = []

    # ------------------------------------------------------- transactions
    _PLAY = ("_sessions", "_actions", "_unlocks", "_timeline", "_duel", "_hint_uses", "_verdicts", "_assessment")

    @contextmanager
    def atomic(self) -> Iterator[None]:
        """Same promise as MySQLStore.atomic(): all of the block is saved, or none of it."""
        with self._lock:
            if getattr(self, "_in_tx", False):
                yield
                return
            snapshot = {name: copy.deepcopy(getattr(self, name)) for name in self._PLAY}
            self._in_tx = True
            try:
                yield
            except BaseException:
                for name, value in snapshot.items():
                    setattr(self, name, value)
                raise
            finally:
                self._in_tx = False

    # ------------------------------------------------------------ content
    def lock_session(self, session_id: str) -> None:
        """atomic() already holds the store's lock, so clicks are saved one after the other."""

    def schema_version(self) -> None:
        return None   # no tables to upgrade

    def ping(self) -> bool:
        return True

    def variant_ids(self) -> list[str]:
        return sorted(self._variants)

    def variant(self, variant_id: str) -> dict[str, Any] | None:
        v = self._variants.get(variant_id)
        return dict(v) if v else None

    def realms(self) -> list[dict[str, Any]]:
        return [dict(r) for r in self._realms]

    def pearls(self) -> list[dict[str, Any]]:
        return [dict(p) for p in self._pearls]

    def sign(self, pearl_id: str, variant_id: str) -> str | None:
        return self._signs.get((pearl_id, variant_id))

    def duel_round(self, round_no: int, variant_id: str) -> dict[str, Any] | None:
        r = self._rounds.get((round_no, variant_id)) or self._rounds.get((round_no, "ALL"))
        return dict(r) if r else None

    def hint(self, puzzle_key: str, level_no: int) -> str | None:
        return self._hints.get((puzzle_key, level_no))

    def assessment_items(self, phase: str) -> list[dict[str, Any]]:
        return [dict(i) for i in self._items if i["phase"] == phase]

    # ----------------------------------------------------------- sessions
    def create_session(self, session_id: str, nickname: str, variant_id: str, pearl_salt: str,
                       stage: str = "pretest") -> None:
        with self._lock:
            self._sessions[session_id] = {
                "session_id": session_id, "nickname": nickname, "variant_id": variant_id,
                "hairs_left": 3, "stage": stage, "legend_step": 0, "pearl_salt": pearl_salt,
            }

    def session(self, session_id: str) -> dict[str, Any] | None:
        s = self._sessions.get(session_id)
        return dict(s) if s else None

    def update_session(self, session_id: str, **fields: Any) -> None:
        allowed = {"hairs_left", "stage", "legend_step"}
        bad = set(fields) - allowed
        if bad:
            raise ValueError(f"cannot update {bad}")
        with self._lock:
            self._sessions[session_id].update(fields)

    # --------------------------------------------------------------- play
    def log_action(self, session_id: str, realm_id: str, action: str) -> None:
        with self._lock:
            self._actions.append({"session_id": session_id, "realm_id": realm_id, "action": action})

    def actions(self, session_id: str) -> list[dict[str, Any]]:
        return [dict(a) for a in self._actions if a["session_id"] == session_id]

    def add_unlock(self, session_id: str, pearl_id: str, predicted_ok: bool, actions_before: int) -> None:
        with self._lock:
            if any(u["session_id"] == session_id and u["pearl_id"] == pearl_id for u in self._unlocks):
                raise KeyError("pearl already opened")  # same as the PRIMARY KEY in MySQL
            self._unlocks.append({"session_id": session_id, "pearl_id": pearl_id,
                                  "predicted_ok": int(predicted_ok), "actions_before": actions_before})

    def unlocks(self, session_id: str) -> list[dict[str, Any]]:
        return [dict(u) for u in self._unlocks if u["session_id"] == session_id]

    def _next_try(self, rows: list[dict[str, Any]], session_id: str, **match: Any) -> int:
        tries = [r["try_no"] for r in rows if r["session_id"] == session_id
                 and all(r[k] == v for k, v in match.items())]
        return max(tries, default=0) + 1

    def add_timeline_try(self, session_id: str, order_given: str, is_correct: bool) -> int:
        with self._lock:
            try_no = self._next_try(self._timeline, session_id)
            self._timeline.append({"session_id": session_id, "try_no": try_no,
                                   "order_given": order_given, "is_correct": int(is_correct)})
            return try_no

    def timeline_tries(self, session_id: str) -> list[dict[str, Any]]:
        return [dict(t) for t in self._timeline if t["session_id"] == session_id]

    def add_duel_answer(self, session_id: str, round_no: int, said_lie: bool, proof: str, reason: str,
                        is_correct: bool) -> int:
        with self._lock:
            try_no = self._next_try(self._duel, session_id, round_no=round_no)
            self._duel.append({"session_id": session_id, "round_no": round_no, "try_no": try_no,
                               "said_lie": int(said_lie), "proof": proof, "reason": reason,
                               "is_correct": int(is_correct)})
            return try_no

    def duel_answers(self, session_id: str) -> list[dict[str, Any]]:
        return [dict(d) for d in self._duel if d["session_id"] == session_id]

    def add_hint_use(self, session_id: str, puzzle_key: str, level_no: int) -> None:
        with self._lock:
            self._hint_uses.append({"session_id": session_id, "puzzle_key": puzzle_key,
                                    "level_no": level_no})

    def hint_uses(self, session_id: str) -> list[dict[str, Any]]:
        return [dict(h) for h in self._hint_uses if h["session_id"] == session_id]

    def add_verdict(self, session_id: str, named: str, proof: str, is_correct: bool) -> int:
        with self._lock:
            try_no = self._next_try(self._verdicts, session_id)
            self._verdicts.append({"session_id": session_id, "try_no": try_no, "named": named,
                                   "proof": proof, "is_correct": int(is_correct), "legend_text": None})
            return try_no

    def set_legend(self, session_id: str, legend_text: str) -> None:
        with self._lock:
            correct = [v for v in self._verdicts if v["session_id"] == session_id and v["is_correct"]]
            if correct:
                correct[-1]["legend_text"] = legend_text

    def verdicts(self, session_id: str) -> list[dict[str, Any]]:
        return [dict(v) for v in self._verdicts if v["session_id"] == session_id]

    def add_assessment_answer(self, session_id: str, item_id: str, choice: str, is_correct: bool) -> None:
        with self._lock:
            if any(a["session_id"] == session_id and a["item_id"] == item_id for a in self._assessment):
                raise KeyError("already answered")  # same as the PRIMARY KEY in MySQL
            self._assessment.append({"session_id": session_id, "item_id": item_id, "choice": choice,
                                     "is_correct": int(is_correct)})

    def assessment_answers(self, session_id: str) -> list[dict[str, Any]]:
        return [dict(a) for a in self._assessment if a["session_id"] == session_id]

    # ------------------------------------------------------------ teacher
    def all_play_data(self) -> dict[str, list[dict[str, Any]]]:
        with self._lock:
            return {
                "sessions": [dict(s) for s in self._sessions.values()],
                "actions": [dict(a) for a in self._actions],
                "unlocks": [dict(u) for u in self._unlocks],
                "timeline_tries": [dict(t) for t in self._timeline],
                "duel_answers": [dict(d) for d in self._duel],
                "hint_uses": [dict(h) for h in self._hint_uses],
                "verdicts": [dict(v) for v in self._verdicts],
                "assessment_answers": [dict(a) for a in self._assessment],
            }
