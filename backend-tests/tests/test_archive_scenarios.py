"""No database or OCI credentials required for these Archive contract tests."""
from app.archive_scenarios import BOSTON, PARIS, BERLIN, SCENARIOS, evaluate, resolve_case, score_case, detect_discoveries


def test_cases_have_unique_ids_and_evidence():
    assert len(SCENARIOS) == 3
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
    assert score_case(PARIS,{"gunpowder_search":"found"}, "", "")["score"]==15


def test_paris_necker_discovery_only_once():
    first=resolve_case(PARIS,"why what was the last drop?",{"political_crisis"},"citizen")
    assert first["discovered"]=="necker_dismissal"
    assert "Necker" in first["reply"]
    repeat=resolve_case(PARIS,"What was the last drop?",{"political_crisis","necker_dismissal"},"citizen")
    assert repeat["discovered"] is None


def test_evidence_is_based_on_npc_statement_not_player_greeting():
    assert detect_discoveries(BOSTON,"Not much, just looking at the ships.")==[]
    text="Parliament is taxing us, though we have no elected representatives there."
    assert detect_discoveries(BOSTON,text)==["taxation_dispute"]
    assert detect_discoveries(BOSTON,text,{"taxation_dispute"})==[]


def test_paris_necker_claim_recognized_from_npc_reply():
    reply="The king dismissed Jacques Necker, the finance minister, worsening unrest."
    assert detect_discoveries(PARIS,reply)==["necker_dismissal"]
    assert detect_discoveries(PARIS,"Someone mentioned Jacques Necker yesterday.")==[]


def test_npc_casual_followup_is_accepted():
    first=resolve_case(BOSTON,"yo what's up?",set())
    follow=resolve_case(BOSTON,"hmm that's very interesting",{"taxation_dispute"},"merchant")
    assert first["npc"]=="merchant"
    assert follow["ok"] and follow["npc"]=="merchant"


def test_berlin_evidence_and_dialogue():
    announcement=resolve_case(BERLIN,"What did Schabowski announce?",set())
    assert announcement["npc"]=="resident"
    assert announcement["discovered"]=="travel_announcement"
    crowd=resolve_case(BERLIN,"Why are the crowds at the checkpoint?",set(),"resident")
    assert crowd["discovered"]=="checkpoint_pressure"
    opening=resolve_case(BERLIN,"Did the border open?",set(),"border_guard")
    assert opening["discovered"]=="border_opening"


def test_berlin_narrated_evidence_validation():
    opening="The border guard says the Bornholmer Strasse checkpoint opened and crowds are passing into West Berlin."
    assert "border_opening" in detect_discoveries(BERLIN,opening)
    announcement="Schabowski announced travel regulations, apparently effective immediately."
    assert detect_discoveries(BERLIN,announcement)==["travel_announcement"]
    assert detect_discoveries(BERLIN,"Hello, how are you?")==[]


def test_berlin_score_and_verdict():
    found={key:"fact" for key in BERLIN["evidence"]}
    testimony="Schabowski's announcement was confusing about travel rules effective immediately. Peaceful protests demanded freedom of movement."
    answer="Crowds pressured checkpoint guards and the border opened for East Germans."
    report=score_case(BERLIN,found,testimony,answer)
    assert report["score"]==100
    assert evaluate(BERLIN,testimony,answer,found)["decision"]=="APPROVED"
