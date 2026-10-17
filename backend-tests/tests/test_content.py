"""The content sheet is complete, consistent, scientifically sound, and matches seed.sql."""

import copy
import re
from pathlib import Path

import pytest

from app.content import SEED_PATH, build_seed_sql, validate_story

ROOT = Path(__file__).resolve().parent.parent


def test_seed_sql_matches_story_json(story):
    """If someone edits story.json but forgets to rebuild seed.sql, this fails."""
    assert SEED_PATH.read_text(encoding="utf-8") == build_seed_sql(story), \
        "sql/seed.sql is out of date - run: python scripts/build_seed.py"


def test_counts_match_the_doc(story):
    assert len(story["pearls"]) == 6
    assert len(story["pearl_signs"]) == 6
    assert len({r["claim_text"] for r in story["duel_rounds"]}) == 5
    assert len(story["variants"]) == 3
    assert len(story["prologue"]) == 5


def test_each_realm_has_two_pearls(story):
    for realm in story["realms"]:
        assert sum(p["realm_id"] == realm["realm_id"] for p in story["pearls"]) == 2


def test_duel_rounds(story):
    culprits = {v["variant_id"]: v["culprit"] for v in story["variants"]}
    r = {(d["round_no"], d["variant_id"]): d for d in story["duel_rounds"]}
    for vid, culprit in culprits.items():
        assert r[(1, vid)]["form_name"] == culprit
        assert (r[(1, vid)]["is_lie"], r[(1, vid)]["proof_pearls"], r[(1, vid)]["proof_mode"]) == (1, "P2", "any")
        # Section 4: round 2 is played by "the suspect who is NOT the culprit", and the claim is TRUE.
        assert r[(2, vid)]["form_name"] != culprit
        assert (r[(2, vid)]["is_lie"], r[(2, vid)]["proof_pearls"], r[(2, vid)]["proof_mode"]) == (0, "P4,P5", "all")
    shared = r[(3, "ALL")]
    # Review fix: the final round needs BOTH the crack pearl and the sand pearl, plus a reason.
    assert (shared["form_name"], shared["is_lie"], shared["proof_pearls"], shared["proof_mode"]) == \
        ("Sun Wukong", 1, "P2,P3", "all")
    for d in story["duel_rounds"]:
        assert len({d["reason_ok"], d["reason_no1"], d["reason_no2"]}) == 3


def test_wukong_is_the_obvious_suspect_but_wrong_in_two_of_three_variants(story):
    assert sum(v["culprit"] == "Sun Wukong" for v in story["variants"]) == 1


# ------------------------------------------------- science (review fixes)

def _pearl(story, pid):
    return next(p for p in story["pearls"] if p["pearl_id"] == pid)


def test_sun_never_sets_into_the_east_sea(story):
    """The sun sets in the WEST. An 'East Sea' shore cannot see it set into the sea."""
    for p in story["pearls"]:
        assert not re.search(r"sun (touches|sets into|sinks into) the sea", p["shared_text"], re.I), p["pearl_id"]
    assert "west" in _pearl(story, "P4")["shared_text"].lower()


def test_tide_question_uses_evidence_not_sunset(story):
    """A sunset does not cause high tide. The P4 question must rest on what the child observed."""
    q = _pearl(story, "P4")["predict_q"].lower()
    assert "sun" not in q and "closer" in q
    sea = next(r for r in story["realms"] if r["realm_id"] == "sea")
    assert "closer" in sea["listen_text"]          # the evidence the question relies on


def test_low_moon_is_rising_in_the_east(story):
    """A low full moon could also be SETTING at dawn. It must say rising in the east."""
    p5 = _pearl(story, "P5")
    assert "rising in the east" in p5["shared_text"] and "rising in the east" in p5["predict_q"]
    assert "sun has gone down" in p5["shared_text"]   # makes P5 clearly AFTER P4 (sunset)


def test_round_two_claim_matches_the_evidence(story):
    claim = next(r["claim_text"] for r in story["duel_rounds"] if r["round_no"] == 2)
    assert "after the sun set" in claim


def test_every_pearl_has_a_time_clue_for_the_timeline(story):
    clues = {"P1": "just rising", "P2": "highest", "P3": "afternoon", "P4": "setting", "P5": "sun has gone down",
             "P6": "highest point"}
    for pid, words in clues.items():
        assert words in _pearl(story, pid)["shared_text"], pid


# ---------------------------------------------------------- hints & text

def test_hint_text_never_states_an_answer(story):
    culprit_words = [w for v in story["variants"] for w in v["culprit_words"]]
    for h in story["hints"]:
        text = h["hint_text"].lower()
        assert " is a lie" not in text and " is true" not in text and " is the truth" not in text
        for w in culprit_words:
            assert w not in text, f"hint {h['puzzle_key']} {h['level_no']} names {w}"


def test_shared_scene_text_never_names_a_suspect(story):
    words = ["wukong", "monkey", "rabbit", "dragon"]
    texts = [r["look_text"] for r in story["realms"]] + [r["listen_text"] for r in story["realms"]]
    texts += [p["shared_text"] for p in story["pearls"]]
    for t in texts:
        assert not any(w in t.lower() for w in words), t


def narrator_turns(story):
    """Every line the storyteller speaks, as (label, text). Wukong's lines are his own, not narration."""
    from app.engine import pearl_text
    n = story["narration"]
    turns = [(f"prologue {i + 1}", t) for i, t in enumerate(story["prologue"])]
    turns += [(f"enter {k}", t) for k, t in n["realm_enter"].items()]
    for r in story["realms"]:
        turns += [(f"{r['realm_id']} look", r["look_text"]), (f"{r['realm_id']} listen", r["listen_text"])]
    signs = {(x["pearl_id"], x["variant_id"]): x["sign_text"] for x in story["pearl_signs"]}
    for p in story["pearls"]:
        turns.append((f"{p['pearl_id']} question", p["predict_q"]))
        for vid in ("V1", "V2", "V3"):   # the pearl as each variant shows it, sign included
            turns.append((f"{p['pearl_id']} {vid}", pearl_text(p["shared_text"], signs.get((p["pearl_id"], vid)))))
    turns += [(f"hint {h['puzzle_key']} {h['level_no']}", h["hint_text"]) for h in story["hints"]]
    turns += [(f"narration {k}", t) for k, t in n.items() if isinstance(t, str) and not k.startswith("_")]
    turns += [(f"fallback {k}", t) for k, t in story["fallbacks"].items() if k.startswith("scroll")]
    turns += [("legend opening", story["legend"]["opening"]), ("legend closing", story["legend"]["closing"])]
    turns += [(f"legend question {i + 1}", q) for i, q in enumerate(story["legend"]["questions"])]
    for v in story["variants"]:
        turns += [(f"ending {v['variant_id']} {i + 1}", t) for i, t in enumerate(v["ending_text"].split("\n"))]
    turns.append(("grandmother", story["grandmother_line"]))
    return turns


def test_every_narrator_turn_is_two_or_three_short_sentences(story):
    """Review 2: 'exactly 2-3 short sentences per narration turn.'"""
    from app.safety import _SENTENCE_RE, count_sentences
    turns = narrator_turns(story)
    assert len(turns) > 90
    for label, text in turns:
        assert 2 <= count_sentences(text) <= 3, f"{label}: {count_sentences(text)} sentences: {text}"
        for sentence in _SENTENCE_RE.findall(text):
            assert len(sentence.split()) <= 22, f"{label}: sentence too long: {sentence}"
        assert len(text.split()) <= 45, f"{label}: {len(text.split())} words"


def test_narration_never_names_a_suspect_or_tells_the_child_what_to_pick(story):
    """The storyteller's set lines say nothing the AI would not be allowed to say."""
    from app.safety import _INSTRUCTION_RE
    for label, text in narrator_turns(story):
        if label.startswith(("prologue", "ending", "legend", "grandmother")):
            continue   # the story itself may name Wukong; these come before or after the mystery
        assert not _INSTRUCTION_RE.search(text), f"{label}: {text}"
        if label.startswith(("enter", "narration", "fallback", "bamboo", "sea", "moon")):
            assert not re.search(r"rabbit|dragon", text, re.I), f"{label}: {text}"


def test_timeline_pair_line_fills_in_pearl_titles(story):
    from app.safety import count_sentences
    line = story["narration"]["timeline_pair"].format(a=story["pearls"][0]["title"], b=story["pearls"][1]["title"])
    assert story["pearls"][0]["title"] in line and count_sentences(line) == 2


def test_before_and_after_questions_are_parallel_but_different(story):
    items = story["assessment"]["items"]
    pre = sorted((i["skill"], i["question"]) for i in items if i["phase"] == "pre")
    post = sorted((i["skill"], i["question"]) for i in items if i["phase"] == "post")
    assert [s for s, _ in pre] == [s for s, _ in post]           # same skills
    assert not {q for _, q in pre} & {q for _, q in post}         # different situations


def test_all_images_exist(story):
    for realm in story["realms"]:
        assert (ROOT / realm["image_url"].lstrip("/")).is_file(), realm["image_url"]


@pytest.mark.parametrize("break_it, message", [
    (lambda s: s["hints"].pop(), "missing hint VERDICT level 3"),
    (lambda s: s["pearl_signs"].pop(), "missing sign"),
    (lambda s: s["pearls"][0].update(predict_no1=s["pearls"][0]["predict_ok"]), "must be different"),
    (lambda s: s["variants"][0].update(culprit="Nobody"), "not in suspects"),
    (lambda s: s["duel_rounds"][0].update(proof_mode="some"), "proof_mode"),
    (lambda s: s["pearls"][0].pop("visual"), "needs a visual"),
    (lambda s: s["assessment"]["items"].pop(), "same skills"),
    (lambda s: s["narration"].pop("duel_intro"), "narration needs 'duel_intro'"),
    (lambda s: s["narration"]["realm_enter"].pop("sea"), "realm_enter for sea"),
])
def test_validator_catches_broken_content(story, break_it, message):
    broken = copy.deepcopy(story)
    break_it(broken)
    with pytest.raises(ValueError, match=message):
        validate_story(broken)
