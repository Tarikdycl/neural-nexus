"""Shared test helpers.

Every engine test runs twice: once on the in-memory store, and once on a real
MySQL database IF one is configured. To include MySQL, set these before pytest:

    MK_TEST_DB_HOST=127.0.0.1 MK_TEST_DB_USER=admin MK_TEST_DB_PASSWORD=... pytest

The MySQL tests use their own database (monkey_king_test), never the game's.
"""

from __future__ import annotations

import os
import random
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.content import load_story  # noqa: E402
from app.engine import Engine, pearl_code  # noqa: E402
from app.narrator import Narrator  # noqa: E402
from app.store_memory import MemoryStore  # noqa: E402

TEST_DB = "monkey_king_test"
PLAY_TABLES = ["assessment_answers", "verdicts", "hint_uses", "duel_answers", "timeline_tries", "unlocks",
               "actions_log", "sessions"]
STORY = load_story()
TRUE = ["P1", "P2", "P3", "P4", "P5", "P6"]
REASON_OK = {r["round_no"]: r["reason_ok"] for r in STORY["duel_rounds"]}
REASONS = {r["round_no"]: [r["reason_ok"], r["reason_no1"], r["reason_no2"]] for r in STORY["duel_rounds"]}
# round -> (said_lie, proof pearls, reason): what a careful child works out from the pearls
DUEL_ANSWERS = {1: (True, ["P2"], REASON_OK[1]), 2: (False, ["P4", "P5"], REASON_OK[2]),
                3: (True, ["P2", "P3"], REASON_OK[3])}
CULPRIT = {"V1": "Sun Wukong", "V2": "Jade Rabbit", "V3": "Dragon King"}
ITEMS = {i["item_id"]: i for i in STORY["assessment"]["items"]}


# ------------------------------------------------------------ fake pieces

class FakeModel:
    """Stands in for OCI Generative AI. Records every call so tests can read the prompts."""

    def __init__(self, reply="The forest has gone quiet. What do you notice here?", delay=0.0, error=None):
        self.reply = reply
        self.delay = delay
        self.error = error
        self.calls = []

    def chat(self, system, user, temperature, max_tokens):
        self.calls.append({"system": system, "user": user, "temperature": temperature, "max_tokens": max_tokens})
        if self.delay:
            time.sleep(self.delay)
        if self.error:
            raise self.error
        return self.reply(system, user) if callable(self.reply) else self.reply


class FixedVariant(random.Random):
    """A random source whose choice() of variant is forced, so a test can pick V1, V2 or V3."""

    def __init__(self, variant):
        super().__init__(7)
        self.variant = variant

    def choice(self, seq):
        if self.variant in seq:
            return self.variant
        return super().choice(seq)


# ---------------------------------------------------------------- stores

def mysql_settings():
    host = os.getenv("MK_TEST_DB_HOST")
    if not host:
        return None
    return dict(host=host, port=int(os.getenv("MK_TEST_DB_PORT", "3306")),
                user=os.getenv("MK_TEST_DB_USER", "admin"), password=os.getenv("MK_TEST_DB_PASSWORD", ""))


@pytest.fixture(scope="session")
def story():
    return STORY


@pytest.fixture(scope="session")
def mysql_db():
    """Create a fresh test database with the real schema.sql and seed.sql (once per test run)."""
    cfg = mysql_settings()
    if not cfg:
        pytest.skip("MySQL not configured (set MK_TEST_DB_HOST to include MySQL tests)")
    import mysql.connector
    from app.migrations import migrate

    conn = mysql.connector.connect(autocommit=True, **cfg)
    cur = conn.cursor()
    cur.execute(f"DROP DATABASE IF EXISTS {TEST_DB}")
    cur.execute(f"CREATE DATABASE {TEST_DB} CHARACTER SET utf8mb4")
    cur.execute(f"USE {TEST_DB}")
    migrate(cur, log=lambda _: None)   # exactly what scripts/setup_db.py does
    migrate(cur, log=lambda _: None)   # twice: it must be safe to re-run
    cur.close()
    conn.close()
    yield cfg


def new_mysql_store(cfg):
    from app.store_mysql import MySQLStore
    return MySQLStore(cfg["host"], cfg["port"], cfg["user"], cfg["password"], TEST_DB)


@pytest.fixture(params=["memory", "mysql"])
def store(request, story):
    if request.param == "memory":
        yield MemoryStore(story)
        return
    cfg = request.getfixturevalue("mysql_db")
    import mysql.connector

    conn = mysql.connector.connect(autocommit=True, database=TEST_DB, **cfg)
    cur = conn.cursor()
    for t in PLAY_TABLES:  # clean play data between tests, keep the story tables
        cur.execute(f"DELETE FROM {t}")
    cur.close()
    conn.close()
    yield new_mysql_store(cfg)


@pytest.fixture
def make_engine(store, story):
    """make_engine(variant='V2', model=FakeModel(...)) -> Engine on the current store."""

    def _make(variant=None, model=None, timeout_s=2.0):
        rng = FixedVariant(variant) if variant else random.Random(1)
        return Engine(store, Narrator(model, story["fallbacks"], timeout_s=timeout_s), story, rng=rng)

    return _make


# --------------------------------------------------------- play helpers

def code(engine, sid, pid):
    """The per-game code the browser would use for pearl pid."""
    return pearl_code(engine.store.session(sid)["pearl_salt"], pid)


def codes(engine, sid, pids):
    return [code(engine, sid, p) for p in pids]


def answer_assessment(engine, sid, phase, correct=True):
    items = [i for i in ITEMS.values() if i["phase"] == phase]
    answers = {i["item_id"]: (i["choice_ok"] if correct else i["choice_no1"]) for i in items}
    return engine.submit_assessment(sid, phase, answers)


def explore_all(engine, sid, story, correct_predictions=True):
    """Look, Listen and open every pearl, as a child would."""
    answers = {p["predict_q"]: (p["predict_ok"] if correct_predictions else p["predict_no1"]) for p in story["pearls"]}
    for realm in ("bamboo", "sea", "moon"):
        engine.action(sid, realm, "look")
        engine.action(sid, realm, "listen")
        for _ in range(2):
            opened = engine.open_pearl(sid, realm)
            engine.predict(sid, opened["pearl"], answers[opened["question"]])


def duel_right(engine, sid, rnd):
    lie, pids, reason = DUEL_ANSWERS[rnd]
    return engine.duel(sid, rnd, lie, codes(engine, sid, pids), reason)


def play_to(engine, story, stage, nickname="Tester"):
    """Start a game and play correctly up to the given stage. Returns the session id."""
    sid = engine.start(nickname)["session_id"]
    if stage == "pretest":
        return sid
    answer_assessment(engine, sid, "pre")
    if stage in ("prologue", "explore"):
        return sid
    explore_all(engine, sid, story)
    if stage == "timeline":
        return sid
    engine.timeline(sid, codes(engine, sid, TRUE))
    if stage == "duel":
        return sid
    for rnd in (1, 2, 3):
        duel_right(engine, sid, rnd)
    if stage == "verdict":
        return sid
    variant = engine.store.session(sid)["variant_id"]
    engine.verdict(sid, CULPRIT[variant], codes(engine, sid, ["P2", "P5"]))
    if stage == "posttest":
        return sid
    answer_assessment(engine, sid, "post")
    if stage == "legend":
        return sid
    engine.legend(sid, "The moon kept the hours safe.", finish=True)
    if stage == "done":
        return sid
    raise ValueError(stage)
