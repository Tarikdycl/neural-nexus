"""The HTTP API end to end, the way the browser uses it."""

import re

import pytest
from fastapi.testclient import TestClient

from app.config import load_settings
from app.main import build_store, create_app
from app.store_memory import MemoryStore
from tests.conftest import CULPRIT, DUEL_ANSWERS, ITEMS, FakeModel, TRUE


@pytest.fixture
def client_for(make_engine):
    def _client(variant=None, model=None, teacher_code=""):
        return TestClient(create_app(make_engine(variant, model), teacher_code=teacher_code))
    return _client


def answers(phase, correct=True):
    return {i: (x["choice_ok"] if correct else x["choice_no1"]) for i, x in ITEMS.items() if x["phase"] == phase}


def play_http(c, story):
    """Play like the browser: it only ever knows titles and codes, never P1..P6."""
    seen = []
    sid = c.post("/api/start", json={"nickname": "Kid"}).json()["session_id"]
    seen.append(c.get(f"/api/assessment/pre?session_id={sid}").json())
    assert c.post("/api/assessment", json={"session_id": sid, "phase": "pre", "answers": answers("pre")}).status_code == 200
    ok = {p["predict_q"]: p["predict_ok"] for p in story["pearls"]}
    for realm in ("bamboo", "sea", "moon"):
        for a in ("look", "listen"):
            assert c.post("/api/action", json={"session_id": sid, "realm": realm, "action": a}).status_code == 200
        for _ in range(2):
            o = c.post("/api/open", json={"session_id": sid, "realm": realm}).json()
            seen.append(o)
            seen.append(c.post("/api/predict", json={"session_id": sid, "pearl": o["pearl"],
                                                     "choice": ok[o["question"]]}).json())
    state = c.get(f"/api/state/{sid}").json()
    seen.append(state)
    by_title = {p["title"]: p["pearl"] for p in state["opened"]}
    title = {p["pearl_id"]: p["title"] for p in story["pearls"]}
    to_code = lambda pids: [by_title[title[p]] for p in pids]  # noqa: E731
    assert c.post("/api/timeline", json={"session_id": sid, "order": to_code(TRUE)}).json()["correct"] is True
    for rnd in (1, 2, 3):
        seen.append(c.get(f"/api/duel/{rnd}", params={"session_id": sid}).json())
        lie, pids, reason = DUEL_ANSWERS[rnd]
        r = c.post("/api/duel", json={"session_id": sid, "round": rnd, "said_lie": lie, "proofs": to_code(pids),
                                      "reason": reason}).json()
        assert r["correct"], r
        seen.append(r)
    return sid, to_code, seen


@pytest.mark.parametrize("variant", ["V1", "V2", "V3"])
def test_full_game_over_http(client_for, story, variant):
    c = client_for(variant)
    sid, to_code, seen = play_http(c, story)
    v = c.post("/api/verdict", json={"session_id": sid, "named": CULPRIT[variant], "proof": to_code(["P2", "P5"])}).json()
    assert v["correct"] is True and v["state"]["stage"] == "posttest"
    seen.append(c.get(f"/api/assessment/post?session_id={sid}").json())
    assert c.post("/api/assessment", json={"session_id": sid, "phase": "post", "answers": answers("post")}).json()["state"]["stage"] == "legend"
    leg = c.post("/api/legend", json={"session_id": sid, "text": "Wukong sails to the moon."}).json()
    assert leg["scroll"]["text"] == story["legend"]["questions"][0]
    assert c.post("/api/legend", json={"session_id": sid, "finish": True}).json()["done"] is True
    assert c.get(f"/api/state/{sid}").json()["stage"] == "done"
    t = c.get("/api/teacher").json()
    assert t["players"] == 1 and t["cards"]["timeline_first_try"] == {"pct": 100, "n": 1}
    # Review fix: sorting what the browser sees must not solve the board, so no raw ids anywhere.
    blob = str(seen)
    assert not re.search(r"'P[1-6]'", blob)


def test_errors_have_a_kind_message_and_right_status(client_for):
    c = client_for("V1")
    r = c.get("/api/state/nope")
    assert r.status_code == 404 and r.json() == {"error": "unknown_session",
                                                 "message": "That adventure was not found. Please start a new one."}
    sid = c.post("/api/start", json={"nickname": "Kid"}).json()["session_id"]
    r = c.post("/api/action", json={"session_id": sid, "realm": "bamboo", "action": "look"})
    assert r.status_code == 409 and r.json()["error"] == "wrong_stage"           # before-questions first
    c.post("/api/assessment", json={"session_id": sid, "phase": "pre", "answers": answers("pre")})
    r = c.post("/api/open", json={"session_id": sid, "realm": "bamboo"})
    assert r.status_code == 409 and r.json()["error"] == "look_and_listen_first"
    assert c.post("/api/start", json={"nickname": ""}).status_code == 400


def test_bad_request_shapes_are_rejected(client_for):
    c = client_for("V1")
    assert c.post("/api/start", json={}).status_code == 422
    assert c.post("/api/duel", json={"session_id": "x", "round": 9, "said_lie": True, "proofs": [], "reason": "r"}).status_code == 422
    assert c.post("/api/duel", json={"session_id": "x", "round": 1, "said_lie": True, "proofs": ["a", "b", "c"], "reason": "r"}).status_code == 422
    assert c.post("/api/timeline", json={"session_id": "x", "order": ["a"] * 7}).status_code == 422


def test_pages_and_static_files_are_served(client_for):
    c = client_for()
    for path in ("/", "/teacher"):
        r = c.get(path)
        assert r.status_code == 200 and "The Stolen Hours of the Monkey King" in r.text
    for path in ("/static/app.js", "/static/style.css", "/static/vendor/react.production.min.js",
                 "/static/vendor/react-dom.production.min.js", "/static/vendor/htm.umd.js",
                 "/static/img/wukong.svg", "/static/img/rabbit.svg", "/static/img/dragon.svg", "/static/img/mountain.svg"):
        assert c.get(path).status_code == 200, path


def test_health_separates_configured_from_working(client_for):
    h = client_for("V1").get("/api/health").json()
    assert h == {"ok": True, "store": h["store"], "db_ok": True,
                 "schema_version": None if h["store"] == "memory" else 2, "schema_version_needed": 2,
                 "ai_configured": False, "ai_last_call": {"ok": None, "error": None, "at": None}}
    c = client_for("V1", model=FakeModel(error=TimeoutError()))
    h = c.get("/api/health?check_ai=1").json()
    assert h["ai_configured"] is True and h["ai_check"]["ok"] is False and h["ai_last_call"]["ok"] is False
    c = client_for("V1", model=FakeModel(reply="ready"))
    assert c.get("/api/health?check_ai=1").json()["ai_check"]["ok"] is True


def test_teacher_code(client_for):
    c = client_for(teacher_code="owl42")
    r = c.get("/api/teacher")
    assert r.status_code == 403 and r.json()["error"] == "teacher_code"
    assert c.get("/api/teacher?code=wrong").status_code == 403
    assert c.get("/api/teacher?code=owl42").status_code == 200
    assert client_for(teacher_code="").get("/api/teacher").status_code == 200     # no code set = open


def test_db_down_falls_back_to_memory(monkeypatch, story):
    """Section 12: 'DB connection fails -> load the content into a Python dictionary.'"""
    for k, v in {"STORE": "mysql", "DB_HOST": "127.0.0.1", "DB_PORT": "1", "FALLBACK_TO_MEMORY": "1"}.items():
        monkeypatch.setenv(k, v)
    assert isinstance(build_store(load_settings(), story), MemoryStore)
    monkeypatch.setenv("FALLBACK_TO_MEMORY", "0")
    with pytest.raises(Exception):
        build_store(load_settings(), story)


def test_memory_store_is_used_when_no_db_host(monkeypatch, story):
    monkeypatch.setenv("STORE", "auto")
    monkeypatch.setenv("DB_HOST", "")
    assert isinstance(build_store(load_settings(), story), MemoryStore)


def test_health_says_503_when_the_database_is_down(client_for, monkeypatch):
    c = client_for("V1")
    store = c.app.state.engine.store

    def down():
        raise ConnectionError("database unreachable")

    monkeypatch.setattr(store, "ping", down)
    r = c.get("/api/health")
    assert r.status_code == 503 and r.json()["ok"] is False and r.json()["db_ok"] is False


def test_health_says_503_on_the_wrong_database_version(client_for, monkeypatch):
    c = client_for("V1")
    monkeypatch.setattr(c.app.state.engine.store, "schema_version", lambda: 1)
    r = c.get("/api/health")
    assert r.status_code == 503 and r.json()["schema_version"] == 1
