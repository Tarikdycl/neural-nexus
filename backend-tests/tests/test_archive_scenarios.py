"""No database or OCI credentials required for these Archive contract tests."""
from app.archive_scenarios import BOSTON, PARIS, SCENARIOS, evaluate, resolve_case, score_case


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


def test_natural_paris_questions_and_followup():
    first=resolve_case(PARIS,"yo why are we running ?",set())
    assert first["ok"] and first["npc"]=="citizen"
    assert first["discovered"]=="gunpowder_search"
    follow=resolve_case(PARIS,"where are the authorities ?",{"gunpowder_search"},"citizen")
    assert follow["ok"] and follow["discovered"]=="political_crisis"
    repeat=resolve_case(PARIS,"where are the authorities ?",{"gunpowder_search","political_crisis"},"citizen")
    assert repeat["discovered"] is None


def test_100_point_score_and_no_duplicate_discovery():
    found={key:"evidence" for key in PARIS["evidence"]}
    full=score_case(PARIS,found,"The Bastille symbolized royal power; the crowd wanted gunpowder amid economic crisis.","They challenged royal authority during the revolution.")
    assert full["score"]==100
    assert full["evidence_score"]==60
    assert full["court_score"]==40
    assert score_case(PARIS,{}, "", "")["score"]==0
    assert score_case(PARIS,{"gunpowder_search":"found"}, "", "")["score"]==20
