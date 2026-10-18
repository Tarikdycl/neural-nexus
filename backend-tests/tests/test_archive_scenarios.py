"""No database or OCI credentials required for these Archive contract tests."""
from app.archive_scenarios import BOSTON, PARIS, SCENARIOS, evaluate, resolve_case


def test_cases_have_unique_ids_and_evidence():
    assert len(SCENARIOS) == 2
    assert all(len(c["evidence"]) >= 3 for c in SCENARIOS.values())


def test_boston_merchant_followup_keeps_context_and_does_not_double_score():
    first = resolve_case(BOSTON, "I ask a merchant about the tax", set())
    assert first["npc"] == "merchant"
    assert first["discovered"] == "taxation_dispute"
    again = resolve_case(BOSTON, "why tea though?", {"taxation_dispute"}, "merchant")
    assert again["ok"]
    assert again["npc"] == "merchant"
    assert again["discovered"] is None


def test_paris_citizen_and_fortress():
    citizen = resolve_case(PARIS, "I ask a citizen what is happening", set())
    assert citizen["discovered"] == "political_crisis"
    fortress = resolve_case(PARIS, "I inspect the Bastille fortress", set())
    assert fortress["discovered"] == "royal_authority"
    powder = resolve_case(PARIS, "I look for gunpowder", set())
    assert powder["discovered"] == "gunpowder_search"


def test_paris_verdict_concept_rubric():
    complete = evaluate(
        PARIS, "The Bastille symbolized royal authority, and people sought gunpowder.",
        "The growing political crisis drove unrest.", {"royal_authority": "found"}
    )
    assert complete["decision"] == "APPROVED"
    weak = evaluate(PARIS, "It was bad.", "", {})
    assert weak["decision"] == "NEEDS_REVISION"
    assert weak["improvements"]
