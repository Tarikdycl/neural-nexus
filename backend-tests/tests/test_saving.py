"""Review 2, problem 1: a failed save must never leave a player stuck.

Every player action is ONE transaction: either everything it writes is kept, or
nothing is. These tests break the database in the middle of an action (the
exact cases from the review), then retry the same click and check the game moves
on with no duplicate rows. They run on the in-memory store and on real MySQL.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from conftest import CULPRIT, DUEL_ANSWERS, ITEMS, STORY, TRUE, answer_assessment, codes, play_to


class DatabaseDown(Exception):
    pass


def fail_once(monkeypatch, store, method, when=lambda *a, **k: True):
    """Make store.<method> raise once, the first time when(...) is true."""
    real = getattr(store, method)
    state = {"failed": False}

    def broken(*args, **kwargs):
        if not state["failed"] and when(*args, **kwargs):
            state["failed"] = True
            raise DatabaseDown(f"{method} failed")
        return real(*args, **kwargs)

    monkeypatch.setattr(store, method, broken)
    return state


def test_assessment_half_saved_then_retry_works(make_engine, monkeypatch):
    """Review case: 'An assessment saves only some answers. Retrying returns already answered.'"""
    engine = make_engine()
    sid = engine.start("Tester")["session_id"]
    calls = {"n": 0}

    def second_answer(*a, **k):
        calls["n"] += 1
        return calls["n"] == 2

    state = fail_once(monkeypatch, engine.store, "add_assessment_answer", second_answer)
    with pytest.raises(DatabaseDown):
        answer_assessment(engine, sid, "pre")
    assert state["failed"]
    assert engine.store.assessment_answers(sid) == []          # the first answer was NOT kept
    assert engine.state(sid)["stage"] == "pretest"

    answer_assessment(engine, sid, "pre")                      # the same click again
    assert engine.state(sid)["stage"] == "prologue"
    assert len(engine.store.assessment_answers(sid)) == 2


def test_assessment_answers_saved_but_stage_change_fails(make_engine, monkeypatch):
    engine = make_engine()
    sid = engine.start("Tester")["session_id"]
    fail_once(monkeypatch, engine.store, "update_session", lambda *a, **k: k.get("stage") == "prologue")
    with pytest.raises(DatabaseDown):
        answer_assessment(engine, sid, "pre")
    assert engine.store.assessment_answers(sid) == []
    answer_assessment(engine, sid, "pre")
    assert engine.state(sid)["stage"] == "prologue"


def _open_five(engine, sid):
    """Open five pearls; return (code, right answer) for the sixth, shown but not yet predicted."""
    answers = {p["predict_q"]: p["predict_ok"] for p in STORY["pearls"]}
    for realm in ("bamboo", "sea", "moon"):
        engine.action(sid, realm, "look")
        engine.action(sid, realm, "listen")
        for _ in range(2):
            opened = engine.open_pearl(sid, realm)
            if len(engine.store.unlocks(sid)) == 5:
                return opened["pearl"], answers[opened["question"]]
            engine.predict(sid, opened["pearl"], answers[opened["question"]])
    raise AssertionError("did not reach the sixth pearl")


def test_sixth_pearl_saved_but_move_to_timeline_fails(make_engine, monkeypatch):
    """Review case: 'The 6th pearl saves, the timeline transition fails, retry says already opened.'"""
    engine = make_engine()
    sid = play_to(engine, STORY, "explore")
    pearl, answer = _open_five(engine, sid)
    fail_once(monkeypatch, engine.store, "update_session", lambda *a, **k: k.get("stage") == "timeline")
    with pytest.raises(DatabaseDown):
        engine.predict(sid, pearl, answer)
    assert len(engine.store.unlocks(sid)) == 5                 # the sixth pearl was rolled back too
    assert engine.state(sid)["stage"] == "explore"

    result = engine.predict(sid, pearl, answer)                # retry: no "already opened"
    assert result["pearls_found"] == 6 and result["all_found"]
    assert engine.state(sid)["stage"] == "timeline"
    assert len(engine.store.unlocks(sid)) == 6


def test_correct_timeline_saved_but_move_to_duel_fails(make_engine, monkeypatch):
    engine = make_engine()
    sid = play_to(engine, STORY, "timeline")
    fail_once(monkeypatch, engine.store, "update_session", lambda *a, **k: k.get("stage") == "duel")
    with pytest.raises(DatabaseDown):
        engine.timeline(sid, codes(engine, sid, TRUE))
    assert engine.store.timeline_tries(sid) == []
    assert engine.timeline(sid, codes(engine, sid, TRUE))["try_no"] == 1   # first try still counts as first
    assert engine.state(sid)["stage"] == "duel"


@pytest.mark.parametrize("rnd", [1, 2, 3])
def test_duel_answer_saved_but_hair_fails(make_engine, monkeypatch, rnd):
    engine = make_engine()
    sid = play_to(engine, STORY, "duel")
    for earlier in range(1, rnd):
        lie, pids, reason = DUEL_ANSWERS[earlier]
        engine.duel(sid, earlier, lie, codes(engine, sid, pids), reason)
    fail_once(monkeypatch, engine.store, "update_session", lambda *a, **k: "hairs_left" in k)
    lie, pids, reason = DUEL_ANSWERS[rnd]
    with pytest.raises(DatabaseDown):
        engine.duel(sid, rnd, lie, codes(engine, sid, pids), reason)
    assert [d for d in engine.store.duel_answers(sid) if d["round_no"] == rnd] == []
    assert engine.duel(sid, rnd, lie, codes(engine, sid, pids), reason)["correct"]
    assert engine.state(sid)["hairs_left"] == 3 - rnd
    assert sum(d["round_no"] == rnd for d in engine.store.duel_answers(sid)) == 1


def test_wrong_duel_answer_and_its_hint_are_saved_together(make_engine, monkeypatch):
    engine = make_engine()
    sid = play_to(engine, STORY, "duel")
    fail_once(monkeypatch, engine.store, "add_hint_use")
    with pytest.raises(DatabaseDown):
        engine.duel(sid, 1, False, codes(engine, sid, ["P2"]), DUEL_ANSWERS[1][2])
    assert engine.store.duel_answers(sid) == []
    wrong = engine.duel(sid, 1, False, codes(engine, sid, ["P2"]), DUEL_ANSWERS[1][2])
    assert wrong["hint"]["level"] == 1 and len(engine.store.duel_answers(sid)) == 1


def test_verdict_saved_but_move_to_posttest_fails(make_engine, monkeypatch):
    engine = make_engine(variant="V2")
    sid = play_to(engine, STORY, "verdict")
    fail_once(monkeypatch, engine.store, "update_session", lambda *a, **k: k.get("stage") == "posttest")
    with pytest.raises(DatabaseDown):
        engine.verdict(sid, CULPRIT["V2"], codes(engine, sid, ["P2", "P5"]))
    assert engine.store.verdicts(sid) == []
    assert engine.verdict(sid, CULPRIT["V2"], codes(engine, sid, ["P2", "P5"]))["correct"]
    assert engine.state(sid)["stage"] == "posttest" and len(engine.store.verdicts(sid)) == 1


def test_legend_chapter_saved_but_progress_fails(make_engine, monkeypatch):
    engine = make_engine()
    sid = play_to(engine, STORY, "legend")
    fail_once(monkeypatch, engine.store, "update_session", lambda *a, **k: "legend_step" in k)
    with pytest.raises(DatabaseDown):
        engine.legend(sid, "The moon kept the hours safe.")
    assert engine.legend(sid, "The moon kept the hours safe.")["done"] is False
    assert engine.store.session(sid)["legend_step"] == 1


def test_browser_gets_a_try_again_message_and_the_retry_works(make_engine, monkeypatch):
    """Over HTTP: the failed click returns 503 save_failed; the same click again succeeds."""
    engine = make_engine()
    client = TestClient(create_app(engine, teacher_code=""), raise_server_exceptions=False)
    sid = client.post("/api/start", json={"nickname": "Tester"}).json()["session_id"]
    items = [i for i in ITEMS.values() if i["phase"] == "pre"]
    body = {"session_id": sid, "phase": "pre", "answers": {i["item_id"]: i["choice_ok"] for i in items}}
    fail_once(monkeypatch, engine.store, "update_session", lambda *a, **k: k.get("stage") == "prologue")
    first = client.post("/api/assessment", json=body)
    assert first.status_code == 503 and first.json()["error"] == "save_failed"
    assert "try again" in first.json()["message"]
    second = client.post("/api/assessment", json=body)
    assert second.status_code == 200, second.text
    assert client.get(f"/api/state/{sid}").json()["stage"] == "prologue"


def _stale(monkeypatch, engine, sid):
    """The next action reads the game as it is NOW, as a second click would have."""
    snapshot = dict(engine.store.session(sid))
    real = engine._session
    calls = {"n": 0}

    def once(session_id):
        calls["n"] += 1
        return dict(snapshot) if calls["n"] == 1 else real(session_id)

    return lambda: monkeypatch.setattr(engine, "_session", once)


def test_double_clicked_duel_answer_is_saved_once(make_engine, monkeypatch):
    engine = make_engine()
    sid = play_to(engine, STORY, "duel")
    second_click = _stale(monkeypatch, engine, sid)
    lie, pids, reason = DUEL_ANSWERS[1]
    assert engine.duel(sid, 1, lie, codes(engine, sid, pids), reason)["correct"]
    second_click()
    with pytest.raises(Exception) as e:
        engine.duel(sid, 1, lie, codes(engine, sid, pids), reason)
    assert getattr(e.value, "code", None) == "already_saved"
    assert sum(d["round_no"] == 1 for d in engine.store.duel_answers(sid)) == 1
    assert engine.state(sid)["hairs_left"] == 2


def test_double_clicked_timeline_and_legend_are_saved_once(make_engine, monkeypatch):
    engine = make_engine()
    sid = play_to(engine, STORY, "timeline")
    second_click = _stale(monkeypatch, engine, sid)
    engine.timeline(sid, codes(engine, sid, TRUE))
    second_click()
    with pytest.raises(Exception, match="already saved"):
        engine.timeline(sid, codes(engine, sid, TRUE))
    assert len(engine.store.timeline_tries(sid)) == 1

    monkeypatch.undo()
    sid = play_to(engine, STORY, "legend")
    second_click = _stale(monkeypatch, engine, sid)
    engine.legend(sid, "One.")
    second_click()
    with pytest.raises(Exception, match="already saved"):
        engine.legend(sid, "One.")
    assert engine.store.session(sid)["legend_step"] == 1      # no question was skipped


def test_two_simultaneous_answers_are_saved_once(make_engine):
    """Real threads, real database connections: two identical clicks at the same moment."""
    import threading
    from app.engine import GameError
    engine = make_engine()
    for _ in range(5):
        sid = play_to(engine, STORY, "duel")
        lie, pids, reason = DUEL_ANSWERS[1]
        proof = codes(engine, sid, pids)
        gate = threading.Barrier(2)
        results = []

        def click():
            gate.wait()
            try:
                results.append(engine.duel(sid, 1, lie, proof, reason)["correct"])
            except GameError as e:
                results.append(e.code)

        threads = [threading.Thread(target=click) for _ in range(2)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        assert results.count(True) == 1 and len(results) == 2, results
        assert set(results) - {True} <= {"already_saved", "wrong_round"}
        assert sum(d["round_no"] == 1 for d in engine.store.duel_answers(sid)) == 1
        assert engine.state(sid)["hairs_left"] == 2
