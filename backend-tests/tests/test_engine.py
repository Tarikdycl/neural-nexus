"""Every game rule (design doc sections 3, 5, 9 and the review fixes), run on BOTH stores."""

import re

import pytest

from app.engine import GameError
from tests.conftest import (CULPRIT, DUEL_ANSWERS, ITEMS, REASON_OK, REASONS, TRUE, answer_assessment, code,
                            codes, duel_right, explore_all, play_to)


def err(fn, *args):
    with pytest.raises(GameError) as e:
        fn(*args)
    return e.value


def ready(engine, nickname="Kid"):
    """A new game, past the before-questions, ready to explore."""
    sid = engine.start(nickname)["session_id"]
    answer_assessment(engine, sid, "pre")
    return sid


# ---------------------------------------------------------------- start

def test_start_picks_one_of_three_variants_and_all_three_happen(make_engine):
    engine = make_engine()
    seen = {engine.store.session(engine.start("Kid")["session_id"])["variant_id"] for _ in range(40)}
    assert seen == {"V1", "V2", "V3"}


def test_start_returns_prologue_but_no_hidden_truth(make_engine, story):
    r = make_engine().start("Kid")
    assert r["prologue"] == story["prologue"] and r["state"]["stage"] == "pretest"
    assert "variant_id" not in r["state"] and "pearl_salt" not in str(r)


@pytest.mark.parametrize("nick, ok", [
    ("Brave Bamboo", True), ("", False), ("   ", False), ("me@mail.com", False),
    ("1234567890", False), ("stupid", False),
])
def test_nickname_rules(make_engine, nick, ok):
    engine = make_engine()
    if ok:
        assert engine.start(nick)["state"]["nickname"] == nick
    else:
        assert err(engine.start, nick).code == "bad_nickname"


def test_unknown_session_is_404(make_engine):
    assert err(make_engine().state, "no-such-session").status == 404


# ------------------------------------------------ before/after questions

def test_before_questions_come_first_and_reveal_no_answer(make_engine):
    engine = make_engine()
    sid = engine.start("Kid")["session_id"]
    assert err(engine.action, sid, "bamboo", "look").code == "wrong_stage"
    a = engine.assessment(sid, "pre")
    assert [i["item_id"] for i in a["items"]] == ["PRE1", "PRE2"]
    for i in a["items"]:
        assert set(i) == {"item_id", "question", "choices"}
        assert sorted(i["choices"]) == sorted([ITEMS[i["item_id"]][k] for k in ("choice_ok", "choice_no1", "choice_no2")])
    assert err(engine.assessment, sid, "post").code == "wrong_stage"


def test_before_questions_must_all_be_answered_once(make_engine):
    engine = make_engine()
    sid = engine.start("Kid")["session_id"]
    assert err(engine.submit_assessment, sid, "pre", {"PRE1": ITEMS["PRE1"]["choice_ok"]}).code == "answer_all"
    assert err(engine.submit_assessment, sid, "pre", {"PRE1": "Teatime", "PRE2": ITEMS["PRE2"]["choice_ok"]}).code == "bad_choice"
    r = answer_assessment(engine, sid, "pre", correct=False)
    assert r["state"]["stage"] == "prologue"
    assert "is_correct" not in str(r)          # no score is shown to the child
    assert err(answer_assessment, engine, sid, "pre").code == "wrong_stage"
    stored = {a["item_id"]: a["is_correct"] for a in engine.store.assessment_answers(sid)}
    assert stored == {"PRE1": 0, "PRE2": 0}


def test_after_questions_come_after_the_verdict_then_legend(make_engine, story):
    engine = make_engine("V2")
    sid = play_to(engine, story, "posttest")
    s = engine.state(sid)
    assert s["stage"] == "posttest" and s["ending"]
    assert err(engine.legend, sid, "story", False).code == "wrong_stage"
    assert answer_assessment(engine, sid, "post")["state"]["stage"] == "legend"


# ------------------------------------------------- look, listen, unlock

def test_pearl_opens_only_after_look_and_listen(make_engine):
    engine = make_engine()
    sid = ready(engine)
    assert err(engine.open_pearl, sid, "bamboo").code == "look_and_listen_first"
    r = engine.action(sid, "bamboo", "look")
    assert r["text"].startswith("The bamboo shadows are very long.") and r["can_open_pearl"] is False
    assert err(engine.open_pearl, sid, "bamboo").code == "look_and_listen_first"
    assert engine.action(sid, "bamboo", "listen")["can_open_pearl"] is True
    assert engine.open_pearl(sid, "bamboo")["pearl"] == code(engine, sid, "P1")
    assert err(engine.open_pearl, sid, "sea").code == "look_and_listen_first"


def test_bad_realm_and_bad_action(make_engine):
    engine = make_engine()
    sid = ready(engine)
    assert err(engine.action, sid, "mars", "look").status == 404
    assert err(engine.action, sid, "bamboo", "open").code == "bad_action"


def test_first_action_moves_prologue_to_explore(make_engine):
    engine = make_engine()
    sid = ready(engine)
    assert engine.state(sid)["stage"] == "prologue"
    engine.action(sid, "sea", "look")
    assert engine.state(sid)["stage"] == "explore"


# ------------------------------------------------------ predict first

def test_open_shows_question_and_three_shuffled_choices(make_engine, story):
    engine = make_engine()
    sid = ready(engine)
    engine.action(sid, "bamboo", "look"); engine.action(sid, "bamboo", "listen")
    r = engine.open_pearl(sid, "bamboo")
    p1 = story["pearls"][0]
    assert r["question"] == p1["predict_q"]
    assert sorted(r["choices"]) == sorted([p1["predict_ok"], p1["predict_no1"], p1["predict_no2"]])
    assert set(r) == {"pearl", "question", "choices"}


def test_predict_stores_result_and_reveals_pearl_with_picture(make_engine):
    engine = make_engine()
    sid = ready(engine)
    engine.action(sid, "bamboo", "look"); engine.action(sid, "bamboo", "listen")
    wrong = engine.predict(sid, code(engine, sid, "P1"), "Midnight")
    assert wrong["prediction_matches"] is False
    assert wrong["pearl"]["text"].startswith("The sun is just rising")
    assert wrong["pearl"]["visual"] == {"kind": "sun", "sun": "low-east"}
    assert engine.predict(sid, code(engine, sid, "P2"), "Midday")["prediction_matches"] is True
    unlocks = {u["pearl_id"]: u for u in engine.store.unlocks(sid)}
    assert unlocks["P1"]["predicted_ok"] == 0 and unlocks["P2"]["predicted_ok"] == 1
    assert unlocks["P1"]["actions_before"] == 2


def test_predict_guards(make_engine):
    engine = make_engine()
    sid = ready(engine)
    assert err(engine.predict, sid, code(engine, sid, "P1"), "Early morning").code == "look_and_listen_first"
    engine.action(sid, "bamboo", "look"); engine.action(sid, "bamboo", "listen")
    assert err(engine.predict, sid, code(engine, sid, "P2"), "Midday").code == "not_this_pearl"
    assert err(engine.predict, sid, code(engine, sid, "P1"), "Teatime").code == "bad_choice"
    assert err(engine.predict, sid, "P1", "Early morning").status == 404       # raw ids are not accepted
    engine.predict(sid, code(engine, sid, "P1"), "Early morning")
    assert err(engine.predict, sid, code(engine, sid, "P1"), "Early morning").code == "already_opened"


def test_codes_from_another_game_do_not_work(make_engine):
    engine = make_engine()
    a, b = ready(engine, "A"), ready(engine, "B")
    engine.action(b, "bamboo", "look"); engine.action(b, "bamboo", "listen")
    assert err(engine.predict, b, code(engine, a, "P1"), "Early morning").status == 404


@pytest.mark.parametrize("variant", ["V1", "V2", "V3"])
def test_sign_pearls_show_this_variants_sign_only(make_engine, story, variant):
    engine = make_engine(variant)
    sid = ready(engine)
    explore_all(engine, sid, story)
    by_title = {p["title"]: p["text"] for p in engine.state(sid)["opened"]}
    titles = {p["pearl_id"]: p["title"] for p in story["pearls"]}
    signs = {(s["pearl_id"], s["variant_id"]): s["sign_text"] for s in story["pearl_signs"]}
    for pid in ("P2", "P5"):
        assert signs[(pid, variant)] in by_title[titles[pid]]
        for other in {"V1", "V2", "V3"} - {variant}:
            assert signs[(pid, other)] not in by_title[titles[pid]]
    assert not any("[variant sign]" in t for t in by_title.values())


def test_six_pearls_move_game_to_timeline(make_engine, story):
    engine = make_engine()
    sid = play_to(engine, story, "timeline")
    s = engine.state(sid)
    assert s["stage"] == "timeline" and s["pearls_found"] == 6
    assert err(engine.open_pearl, sid, "bamboo").code == "wrong_stage"


# ------------------------------------------------------ stage gating

def test_cannot_skip_ahead(make_engine, story):
    engine = make_engine()
    sid = ready(engine)
    assert err(engine.timeline, sid, codes(engine, sid, TRUE)).code == "wrong_stage"
    assert err(engine.duel_claim, sid, 1).code == "wrong_stage"
    assert err(engine.duel, sid, 1, True, codes(engine, sid, ["P2"]), REASON_OK[1]).code == "wrong_stage"
    assert err(engine.verdict, sid, "Sun Wukong", codes(engine, sid, ["P2", "P5"])).code == "wrong_stage"
    assert err(engine.legend, sid, "story", False).code == "wrong_stage"
    explore_all(engine, sid, story)
    assert err(engine.duel, sid, 1, True, codes(engine, sid, ["P2"]), REASON_OK[1]).code == "wrong_stage"


# ------------------------------------------------------- timeline board

def test_timeline_wrong_then_right(make_engine, story):
    engine = make_engine()
    sid = play_to(engine, story, "timeline")
    wrong = engine.timeline(sid, codes(engine, sid, ["P1", "P3", "P2", "P4", "P5", "P6"]))
    assert wrong["correct"] is False and wrong["pair"] == codes(engine, sid, ["P3", "P2"]) and wrong["try_no"] == 1
    assert "Pearl of the Far Sea" in wrong["scroll"]["text"] and "Pearl of the Cracked Glass" in wrong["scroll"]["text"]
    assert engine.state(sid)["stage"] == "timeline"
    right = engine.timeline(sid, codes(engine, sid, TRUE))
    assert right["correct"] is True and right["try_no"] == 2
    s = engine.state(sid)
    assert s["stage"] == "duel" and s["hairs_left"] == 3 and s["duel_round"] == 1
    tries = engine.store.timeline_tries(sid)
    assert [(t["try_no"], t["is_correct"], t["order_given"]) for t in tries] == [
        (1, 0, "P1,P3,P2,P4,P5,P6"), (2, 1, "P1,P2,P3,P4,P5,P6")]


@pytest.mark.parametrize("order", [
    ["P1", "P2", "P3", "P4", "P5"], ["P1", "P1", "P3", "P4", "P5", "P6"], [],
])
def test_timeline_rejects_bad_boards(make_engine, story, order):
    engine = make_engine()
    sid = play_to(engine, story, "timeline")
    assert err(engine.timeline, sid, codes(engine, sid, order)).code == "bad_order"
    assert err(engine.timeline, sid, TRUE).code == "bad_order"          # raw ids are not codes
    assert engine.store.timeline_tries(sid) == []


# ---------------------------------------------------------------- duel

@pytest.mark.parametrize("variant", ["V1", "V2", "V3"])
def test_duel_claims_per_variant_never_leak_answers(make_engine, story, variant):
    engine = make_engine(variant)
    sid = play_to(engine, story, "duel")
    c1 = engine.duel_claim(sid, 1)
    assert set(c1) == {"round", "form_name", "claim", "hairs_left", "copies", "proof_count", "reasons"}
    assert c1["form_name"] == CULPRIT[variant] and c1["proof_count"] == 1
    assert sorted(c1["reasons"]) == sorted(REASONS[1])
    duel_right(engine, sid, 1)
    c2 = engine.duel_claim(sid, 2)
    assert c2["form_name"] != CULPRIT[variant] and c2["proof_count"] == 2
    assert c2["claim"] == "The full moon rose right after the sun set."
    duel_right(engine, sid, 2)
    c3 = engine.duel_claim(sid, 3)
    assert c3["form_name"] == "Sun Wukong" and c3["proof_count"] == 2


@pytest.mark.parametrize("variant", ["V1", "V2", "V3"])
def test_duel_correct_answers_take_three_hairs(make_engine, story, variant):
    engine = make_engine(variant)
    sid = play_to(engine, story, "duel")
    for rnd, hairs in ((1, 2), (2, 1), (3, 0)):
        r = duel_right(engine, sid, rnd)
        assert r["correct"] is True and r["hairs_left"] == hairs and r["taunt"]["text"]
    assert r["duel_over"] is True and engine.state(sid)["stage"] == "verdict"
    stored = engine.store.duel_answers(sid)
    assert [(d["round_no"], d["proof"], d["reason"]) for d in stored] == [
        (1, "P2", REASON_OK[1]), (2, "P4,P5", REASON_OK[2]), (3, "P2,P3", REASON_OK[3])]


@pytest.mark.parametrize("rnd, said_lie, pids, reason", [
    (1, False, ["P2"], "ok"),                   # wrong Truth/Lie
    (1, True, ["P3"], "ok"),                    # wrong pearl
    (1, True, ["P2"], "no1"),                   # wrong reason
])
def test_wrong_duel_answer_gives_hint_and_keeps_hairs(make_engine, story, rnd, said_lie, pids, reason):
    engine = make_engine("V1")
    sid = play_to(engine, story, "duel")
    reason_text = REASONS[rnd][0] if reason == "ok" else REASONS[rnd][1]
    r = engine.duel(sid, rnd, said_lie, codes(engine, sid, pids), reason_text)
    assert r["correct"] is False and r["hairs_left"] == 3 and r["copies"] == 1
    assert r["hint"]["puzzle"] == "DUEL" and r["hint"]["level"] == 1 and r["hint"]["source"] == "table"
    assert r["taunt"]["text"] == "Ha! One more of me! Look again at your pearls."
    assert set(r) == {"correct", "hairs_left", "taunt", "hint", "copies"}   # never says which part was wrong


def test_round_two_trust_test_and_two_pearls(make_engine, story):
    engine = make_engine("V3")
    sid = play_to(engine, story, "duel")
    duel_right(engine, sid, 1)
    p45 = codes(engine, sid, ["P4", "P5"])
    assert engine.duel(sid, 2, True, p45, REASON_OK[2])["correct"] is False              # called the truth a lie
    assert err(engine.duel, sid, 2, False, codes(engine, sid, ["P5"]), REASON_OK[2]).code == "bad_proof"
    assert engine.duel(sid, 2, False, codes(engine, sid, ["P4", "P6"]), REASON_OK[2])["correct"] is False
    assert engine.duel(sid, 2, False, list(reversed(p45)), REASON_OK[2])["correct"] is True


def test_round_three_needs_crack_and_sand_and_the_order_reason(make_engine, story):
    engine = make_engine("V2")
    sid = play_to(engine, story, "duel")
    duel_right(engine, sid, 1); duel_right(engine, sid, 2)
    assert err(engine.duel, sid, 3, True, codes(engine, sid, ["P2"]), REASON_OK[3]).code == "bad_proof"
    assert engine.duel(sid, 3, True, codes(engine, sid, ["P2", "P4"]), REASON_OK[3])["correct"] is False
    wrong_order = next(x for x in REASONS[3] if "sand came first" in x)
    assert engine.duel(sid, 3, True, codes(engine, sid, ["P2", "P3"]), wrong_order)["correct"] is False
    assert duel_right(engine, sid, 3)["correct"] is True


def test_duel_guards(make_engine, story):
    engine = make_engine("V1")
    sid = play_to(engine, story, "duel")
    assert err(engine.duel, sid, 2, False, codes(engine, sid, ["P4", "P5"]), REASON_OK[2]).code == "wrong_round"
    assert err(engine.duel_claim, sid, 3).code == "wrong_round"
    assert err(engine.duel, sid, 1, True, ["nope"], REASON_OK[1]).code == "bad_proof"
    assert err(engine.duel, sid, 1, True, codes(engine, sid, ["P2"]), "Because I said so").code == "bad_reason"


def test_child_can_never_lose_the_duel(make_engine, story):
    engine = make_engine("V1")
    sid = play_to(engine, story, "duel")
    for _ in range(10):
        assert engine.duel(sid, 1, False, codes(engine, sid, ["P1"]), REASONS[1][1])["correct"] is False
    assert duel_right(engine, sid, 1)["correct"] is True
    assert [d["try_no"] for d in engine.store.duel_answers(sid) if d["round_no"] == 1] == list(range(1, 12))


# ------------------------------------------------------------- verdict

@pytest.mark.parametrize("variant", ["V1", "V2", "V3"])
def test_verdict_and_ending_per_variant(make_engine, story, variant):
    engine = make_engine(variant)
    sid = play_to(engine, story, "verdict")
    signs = codes(engine, sid, ["P2", "P5"])
    for other in set(CULPRIT.values()) - {CULPRIT[variant]}:
        wrong = engine.verdict(sid, other, signs)
        assert wrong["correct"] is False and wrong["hint"]["puzzle"] == "VERDICT"
    assert engine.verdict(sid, CULPRIT[variant], codes(engine, sid, ["P2", "P4"]))["correct"] is False
    right = engine.verdict(sid, CULPRIT[variant], list(reversed(signs)))
    ending = next(v["ending_text"] for v in story["variants"] if v["variant_id"] == variant)
    assert right["correct"] is True and right["ending"] == ending.split("\n")   # one narration turn each
    assert len(right["ending"]) >= 2 and engine.state(sid)["ending"] == right["ending"]
    assert engine.state(sid)["stage"] == "posttest"


def test_verdict_guards(make_engine, story):
    engine = make_engine("V1")
    sid = play_to(engine, story, "verdict")
    p2 = code(engine, sid, "P2")
    assert err(engine.verdict, sid, "Grandmother Lin", codes(engine, sid, ["P2", "P5"])).code == "bad_suspect"
    assert err(engine.verdict, sid, "Sun Wukong", [p2, p2]).code == "bad_proof"
    assert err(engine.verdict, sid, "Sun Wukong", [p2]).code == "bad_proof"
    assert err(engine.verdict, sid, "Sun Wukong", ["P2", "P5"]).code == "bad_proof"


# ------------------------------------------------------------ legend

def test_legend_scroll_asks_three_questions_then_finishes(make_engine, story):
    engine = make_engine()
    sid = play_to(engine, story, "legend")
    asked = [engine.legend(sid, f"Wukong part {i}", False)["scroll"]["text"] for i in range(3)]
    assert asked == story["legend"]["questions"]
    last = engine.legend(sid, "Wukong finds a new home in the clouds.", False)
    assert last["done"] is True and last["words"] == 8
    assert engine.state(sid)["stage"] == "done"
    assert engine.state(sid)["legend_text"] == "Wukong finds a new home in the clouds."
    assert err(engine.legend, sid, "more", False).code == "wrong_stage"


def test_legend_can_finish_early_and_rejects_empty_save(make_engine, story):
    engine = make_engine()
    sid = play_to(engine, story, "legend")
    assert err(engine.legend, sid, "   ", False).code == "empty_legend"
    assert engine.legend(sid, "", True)["done"] is True


# ---------------------------------------------------------- hint ladder

def test_hint_ladder_is_table_text_and_stops_at_three(make_engine, story):
    engine = make_engine()
    sid = play_to(engine, story, "timeline")
    hints = [engine.hint(sid, "TIMELINE")["hint"] for _ in range(5)]
    assert [h["level"] for h in hints] == [1, 2, 3, 3, 3]
    table = {h["level_no"]: h["hint_text"] for h in story["hints"] if h["puzzle_key"] == "TIMELINE"}
    assert [h["text"] for h in hints] == [table[1], table[2], table[3], table[3], table[3]]
    assert all(h["source"] == "table" for h in hints)
    assert len([h for h in engine.store.hint_uses(sid) if h["puzzle_key"] == "TIMELINE"]) == 3


def test_hints_only_for_the_puzzle_on_screen(make_engine, story):
    engine = make_engine()
    sid = ready(engine)
    assert err(engine.hint, sid, "PREDICT", "bamboo").code == "not_now"       # not unlocked yet
    engine.action(sid, "bamboo", "look"); engine.action(sid, "bamboo", "listen")
    h = engine.hint(sid, "PREDICT", "bamboo")["hint"]
    assert h["puzzle"] == "PREDICT" and h["text"] == next(x["hint_text"] for x in story["hints"]
                                                         if x["puzzle_key"] == "P1" and x["level_no"] == 1)
    assert err(engine.hint, sid, "TIMELINE").code == "wrong_stage"
    assert err(engine.hint, sid, "P1").status == 404             # internal keys are not accepted
    sid2 = play_to(engine, story, "duel")
    assert engine.hint(sid2, "DUEL")["hint"]["text"] == next(x["hint_text"] for x in story["hints"]
                                                            if x["puzzle_key"] == "R1" and x["level_no"] == 1)


# ------------------------------------------------------- teacher numbers

def test_teacher_numbers_are_honest_with_sample_sizes(make_engine, story):
    engine = make_engine("V2")
    a = play_to(engine, story, "legend", "Ada")          # all right; post questions right, pre right
    engine.legend(a, "Wukong goes to the moon to dance", True)
    b = engine.start("Bo")["session_id"]                 # all predictions wrong, pre wrong
    answer_assessment(engine, b, "pre", correct=False)
    explore_all(engine, b, story, correct_predictions=False)
    engine.hint(b, "TIMELINE")
    engine.timeline(b, codes(engine, b, ["P2", "P1", "P3", "P4", "P5", "P6"]))
    engine.timeline(b, codes(engine, b, TRUE))
    duel_right(engine, b, 1)
    engine.duel(b, 2, True, codes(engine, b, ["P4", "P5"]), REASON_OK[2])   # fails the trust test (+ auto hint)
    duel_right(engine, b, 2)
    duel_right(engine, b, 3)
    engine.verdict(b, "Jade Rabbit", codes(engine, b, ["P2", "P5"]))
    answer_assessment(engine, b, "post")                 # wrong before, right after
    c = engine.start("Cy")["session_id"]                 # opened ONE pearl, right: must NOT count as 6/6
    answer_assessment(engine, c, "pre")
    engine.action(c, "bamboo", "look"); engine.action(c, "bamboo", "listen")
    engine.predict(c, code(engine, c, "P1"), "Early morning")

    t = engine.teacher()
    assert t["players"] == 3 and t["nicknames"] == ["Ada", "Bo", "Cy"] and t["finished"] == 2
    cards = t["cards"]
    assert cards["predict"] == {"avg_out_of_6": 3.0, "n": 2, "correct_so_far": 7, "answered_so_far": 13}
    assert cards["timeline_first_try"] == {"pct": 50, "n": 2}
    assert cards["duel_proof"] == {"avg_out_of_2": 2.0, "n": 2}
    assert cards["trust_test"] == {"pct": 50, "n": 2}
    assert cards["hints"] == {"avg": 1.0, "n": 2}                     # (0 + 2) / 2 finished students
    assert cards["pre_post"] == {"pre_pct": 50, "post_pct": 100, "n": 2}
    chart = {row["puzzle"]: row["hints"] for row in t["hints_per_puzzle"]}
    assert chart["Timeline board"] == 1 and chart["Duel round 2"] == 1
    assert t["extra"]["avg_legend_words"] == 7.0


def test_one_right_prediction_is_not_shown_as_six_out_of_six(make_engine):
    """The exact bug from the review."""
    engine = make_engine()
    sid = ready(engine)
    engine.action(sid, "bamboo", "look"); engine.action(sid, "bamboo", "listen")
    engine.predict(sid, code(engine, sid, "P1"), "Early morning")
    p = engine.teacher()["cards"]["predict"]
    assert p == {"avg_out_of_6": None, "n": 0, "correct_so_far": 1, "answered_so_far": 1}


def test_teacher_chart_reveals_no_order_or_answer(make_engine, story):
    t = make_engine().teacher()
    labels = [row["puzzle"] for row in t["hints_per_puzzle"]]
    assert labels == sorted(labels)                       # all zero -> alphabetical, not puzzle order
    assert not any(re.search(r"true|lie|truth", l, re.I) for l in labels)


def test_teacher_numbers_with_no_players(make_engine):
    t = make_engine().teacher()
    assert t["players"] == 0
    assert t["cards"]["predict"]["avg_out_of_6"] is None and t["cards"]["pre_post"]["n"] == 0


# ------------------------------------------------ nothing hidden leaks

HIDDEN_KEYS = {"culprit", "culprit_words", "true_order", "time_label", "is_lie", "proof_pearls", "proof_mode",
               "reason_ok", "variant_id", "pearl_id", "pearl_salt", "choice_ok", "is_correct"}


def _walk(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield ("key", k)
            yield from _walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk(v)
    else:
        yield ("value", obj)


@pytest.mark.parametrize("variant", ["V1", "V2", "V3"])
def test_no_child_facing_response_contains_hidden_data(make_engine, story, variant):
    engine = make_engine(variant)
    r0 = engine.start("Kid")
    sid = r0["session_id"]
    responses = [r0, engine.assessment(sid, "pre"), answer_assessment(engine, sid, "pre")]
    for realm in ("bamboo", "sea", "moon"):
        responses += [engine.action(sid, realm, "look"), engine.action(sid, realm, "listen")]
        for _ in range(2):
            o = engine.open_pearl(sid, realm)
            responses += [o, engine.hint(sid, "PREDICT", realm), engine.predict(sid, o["pearl"], o["choices"][0])]
        responses.append(engine.ask(sid, realm, "Who did it?"))
    responses += [engine.timeline(sid, codes(engine, sid, list(reversed(TRUE)))),
                  engine.timeline(sid, codes(engine, sid, TRUE))]
    for rnd in (1, 2, 3):
        lie, pids, reason = DUEL_ANSWERS[rnd]
        responses += [engine.duel_claim(sid, rnd), engine.hint(sid, "DUEL"),
                      engine.duel(sid, rnd, not lie, codes(engine, sid, pids), reason), duel_right(engine, sid, rnd)]
    responses.append(engine.verdict(sid, CULPRIT[variant], codes(engine, sid, ["P2", "P5"])))
    responses += [engine.assessment(sid, "post"), answer_assessment(engine, sid, "post"),
                  engine.legend(sid, "The end", True), engine.state(sid)]
    for r in responses:
        for kind, item in _walk(r):
            if kind == "key":
                assert item not in HIDDEN_KEYS, f"hidden field {item!r} in {r}"
            elif isinstance(item, str):
                assert not re.fullmatch(r"P[1-6]", item), f"raw pearl id {item!r} in {r}"


# --------------------------------------------- persistence across a restart

def test_a_game_survives_a_server_restart(mysql_db, story):
    """Review fix: the variant, pearls and progress must still be there after a restart (MySQL only)."""
    import random

    from app.engine import Engine
    from app.narrator import Narrator
    from tests.conftest import FixedVariant, new_mysql_store

    first = Engine(new_mysql_store(mysql_db), Narrator(None, story["fallbacks"]), story, rng=FixedVariant("V3"))
    sid = play_to(first, story, "duel")
    duel_right(first, sid, 1)
    before = first.state(sid)

    restarted = Engine(new_mysql_store(mysql_db), Narrator(None, story["fallbacks"]), story, rng=random.Random())
    after = restarted.state(sid)
    assert after == before                                   # same stage, pearls, codes, hairs
    assert restarted.store.session(sid)["variant_id"] == "V3"
    duel_right(restarted, sid, 2)
    duel_right(restarted, sid, 3)
    assert restarted.verdict(sid, "Dragon King", codes(restarted, sid, ["P2", "P5"]))["correct"] is True


# ------------------------------------------- review 2: the storyteller

def _storyteller_lines(obj, found):
    """Collect every Scroll / narration line in a response (Wukong's lines are his own)."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in ("narration", "scroll", "hint", "reply", "stage_line") and isinstance(value, dict) \
                    and "text" in value:
                found.append(value["text"])
            elif key == "enter_text" and isinstance(value, str):
                found.append(value)
            elif key == "ending" and isinstance(value, list):
                found.extend(value)
            else:
                _storyteller_lines(value, found)
    elif isinstance(obj, list):
        for v in obj:
            _storyteller_lines(v, found)
    return found


@pytest.mark.parametrize("variant", ["V1", "V2", "V3"])
def test_every_storyteller_line_in_a_whole_game_is_two_or_three_sentences(make_engine, story, variant):
    from app.safety import count_sentences
    from tests.conftest import DUEL_ANSWERS
    engine = make_engine(variant)          # AI off: every line is a team-written line or fallback
    seen = []
    sid = engine.start("Teller")["session_id"]
    seen += _storyteller_lines(answer_assessment(engine, sid, "pre"), [])
    answers = {p["predict_q"]: p for p in story["pearls"]}
    for n, realm in enumerate(("bamboo", "sea", "moon")):
        seen += _storyteller_lines(engine.action(sid, realm, "look"), [])
        seen += _storyteller_lines(engine.action(sid, realm, "listen"), [])
        seen += _storyteller_lines(engine.ask(sid, realm, "What is here?"), [])
        for i in range(2):
            opened = engine.open_pearl(sid, realm)
            seen += _storyteller_lines(engine.hint(sid, "PREDICT", realm), [])
            p = answers[opened["question"]]
            r = engine.predict(sid, opened["pearl"], p["predict_ok"] if (n + i) % 2 else p["predict_no1"])
            seen += _storyteller_lines(r, [])
    seen += _storyteller_lines(engine.hint(sid, "TIMELINE"), [])
    seen += _storyteller_lines(engine.timeline(sid, codes(engine, sid, ["P2", "P1", "P3", "P4", "P5", "P6"])), [])
    seen += _storyteller_lines(engine.timeline(sid, codes(engine, sid, TRUE)), [])
    seen += _storyteller_lines(engine.duel(sid, 1, False, codes(engine, sid, ["P1"]), DUEL_ANSWERS[1][2]), [])
    for rnd in (1, 2, 3):
        seen += _storyteller_lines(duel_right(engine, sid, rnd), [])
    wrong_suspect = next(x for x in story["suspects"] if x != CULPRIT[variant])
    seen += _storyteller_lines(engine.verdict(sid, wrong_suspect, codes(engine, sid, ["P1", "P3"])), [])
    seen += _storyteller_lines(engine.verdict(sid, CULPRIT[variant], codes(engine, sid, ["P2", "P5"])), [])
    seen += _storyteller_lines(answer_assessment(engine, sid, "post"), [])
    for _ in range(4):
        seen += _storyteller_lines(engine.legend(sid, "Wukong went to the sea."), [])
    seen += _storyteller_lines(engine.state(sid), [])
    assert len(seen) > 40
    for line in seen:
        assert 2 <= count_sentences(line) <= 3, line


def test_narration_comes_with_each_story_beat(make_engine, story):
    n = story["narration"]
    engine = make_engine("V1")
    sid = play_to(engine, story, "explore")
    state = engine.state(sid)
    assert [r["enter_text"] for r in state["realms"]] == [n["realm_enter"][r] for r in ("bamboo", "sea", "moon")]
    assert "stage_line" not in state
    engine.action(sid, "bamboo", "look")
    engine.action(sid, "bamboo", "listen")
    first = engine.open_pearl(sid, "bamboo")
    assert engine.predict(sid, first["pearl"], "Early morning")["narration"]["text"] == n["predict_match"]
    second = engine.open_pearl(sid, "bamboo")
    assert engine.predict(sid, second["pearl"], "Dawn")["narration"]["text"] == n["predict_differ"]
    sid = play_to(engine, story, "timeline")
    assert engine.state(sid)["stage_line"]["text"] == n["all_found"]
    assert engine.timeline(sid, codes(engine, sid, TRUE))["narration"]["text"] == n["timeline_solved"]
    assert engine.state(sid)["stage_line"]["text"] == n["duel_intro"]
    sid = play_to(engine, story, "verdict")
    assert engine.state(sid)["stage_line"] == {"text": n["verdict_intro"], "source": "table"}
