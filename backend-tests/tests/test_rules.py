"""The pure rules from design doc section 9 (and the review fixes), tested on their own."""

import itertools

import pytest

from app.engine import (TRUE_ORDER, check_duel_answer, check_timeline, check_verdict, pearl_code, pearl_text,
                        proof_count)

# ------------------------------------------------------------- timeline

def test_timeline_true_order_is_correct():
    assert check_timeline(["P1", "P2", "P3", "P4", "P5", "P6"]) == {"correct": True}


@pytest.mark.parametrize("order, pair", [
    (["P2", "P1", "P3", "P4", "P5", "P6"], ["P2", "P1"]),
    (["P1", "P2", "P4", "P3", "P5", "P6"], ["P4", "P3"]),
    (["P1", "P2", "P3", "P4", "P6", "P5"], ["P6", "P5"]),
    (["P6", "P5", "P4", "P3", "P2", "P1"], ["P6", "P5"]),   # fully reversed: first pair is reported
    (["P1", "P3", "P2", "P5", "P4", "P6"], ["P3", "P2"]),   # two mistakes: only the FIRST is reported
])
def test_timeline_reports_first_pair_out_of_order(order, pair):
    assert check_timeline(order) == {"correct": False, "pair": pair}


def test_timeline_every_possible_order():
    """All 720 orders: exactly one is correct; every other one names a real out-of-order pair."""
    correct = 0
    for order in itertools.permutations(TRUE_ORDER):
        result = check_timeline(list(order))
        if result["correct"]:
            correct += 1
            continue
        a, b = result["pair"]
        i = order.index(a)
        assert order[i + 1] == b, "the pair must be neighbours on the board"
        assert TRUE_ORDER.index(a) > TRUE_ORDER.index(b), "a must really belong after b"
        assert all(TRUE_ORDER.index(x) < TRUE_ORDER.index(y) for x, y in zip(order[:i], order[1:i + 1]))
    assert correct == 1


# ---------------------------------------------------------------- duel

R1 = dict(is_lie=1, proof_pearls="P2", proof_mode="any", reason_ok="sign at shrine")
R2 = dict(is_lie=0, proof_pearls="P4,P5", proof_mode="all", reason_ok="sun set then moon rose")
R3 = dict(is_lie=1, proof_pearls="P2,P3", proof_mode="all", reason_ok="crack first")


@pytest.mark.parametrize("said_lie, proofs, reason, rnd, expected", [
    (True, ["P2"], "sign at shrine", R1, True),
    (False, ["P2"], "sign at shrine", R1, False),       # wrong Truth/Lie
    (True, ["P3"], "sign at shrine", R1, False),        # wrong pearl
    (True, ["P2"], "something else", R1, False),        # wrong reason
    (True, ["P2", "P5"], "sign at shrine", R1, False),  # 'any' means exactly one pearl
    (False, ["P4", "P5"], "sun set then moon rose", R2, True),
    (False, ["P5", "P4"], "sun set then moon rose", R2, True),   # any order
    (False, ["P5"], "sun set then moon rose", R2, False),        # 'all' needs both
    (False, ["P4", "P6"], "sun set then moon rose", R2, False),
    (True, ["P4", "P5"], "sun set then moon rose", R2, False),   # calling the true claim a lie
    (True, ["P2", "P3"], "crack first", R3, True),
    (True, ["P2"], "crack first", R3, False),                    # one pearl is not enough
    (True, ["P2", "P3"], "sand first", R3, False),
])
def test_duel_needs_every_part_right(said_lie, proofs, reason, rnd, expected):
    assert check_duel_answer(said_lie, proofs, reason, **rnd) is expected


def test_proof_count():
    assert proof_count("P2", "any") == 1
    assert proof_count("P4,P5", "any") == 1
    assert proof_count("P4,P5", "all") == 2


# -------------------------------------------------------------- verdict

def test_verdict_needs_culprit_and_both_sign_pearls_in_any_order():
    assert check_verdict("Jade Rabbit", ["P2", "P5"], "Jade Rabbit")
    assert check_verdict("Jade Rabbit", ["P5", "P2"], "Jade Rabbit")
    assert not check_verdict("Sun Wukong", ["P2", "P5"], "Jade Rabbit")
    assert not check_verdict("Jade Rabbit", ["P2", "P4"], "Jade Rabbit")
    assert not check_verdict("Jade Rabbit", ["P2", "P2"], "Jade Rabbit")
    assert not check_verdict("Jade Rabbit", ["P2", "P5", "P1"], "Jade Rabbit")


# ---------------------------------------------------------- pearl text

def test_pearl_text_fills_sign_slot():
    assert pearl_text("A crack. [variant sign]", "A golden hair.") == "A crack. A golden hair."


def test_pearl_text_without_sign_has_no_leftover_slot_or_double_space():
    assert pearl_text("A crack. [variant sign]", None) == "A crack."


# ---------------------------------------------------------- pearl codes

def test_pearl_codes_hide_the_order():
    """Review fix: sorting the browser's ids used to solve the timeline. Codes must not."""
    codes = [pearl_code("salt-one", p) for p in TRUE_ORDER]
    assert len(set(codes)) == 6
    assert all(set(c) <= set("0123456789abcdef") and len(c) == 10 for c in codes)   # nothing like "P3"
    # Across many games, sorting the codes almost never gives the true order (1 in 720 by chance).
    hits = sum(sorted(TRUE_ORDER, key=lambda p, s=s: pearl_code(s, p)) == TRUE_ORDER for s in map(str, range(300)))
    assert hits <= 3


def test_pearl_codes_differ_between_games():
    assert pearl_code("game-a", "P1") != pearl_code("game-b", "P1")
