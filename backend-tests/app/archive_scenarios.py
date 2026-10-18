"""Data-driven historical cases. Claims here are authored educational summaries."""
import re

BOSTON = {
 "id":"boston_tea_party_1773","title":"The Tea in the Harbor",
 "place":"Boston Harbor · December 16, 1773",
 "intro":"Boston Harbor, December 16, 1773. Lanterns flicker beside three tea ships. Merchants argue over the cargo. Ask someone what is happening, examine the ships, or look around.",
 "scene":"Three tea ships lie at anchor in Boston Harbor in December 1773, amid a colonial protest.",
 "evidence":{
  "shipping_manifest":"The tea cargo was connected to the East India Company.",
  "taxation_dispute":"Colonists protested taxation by Parliament without elected colonial representation.",
  "tea_act":"The Tea Act of 1773 intensified disputes about tea trade and Parliament's authority."
 },
 "topics":[
  ("Taxation and representation","taxation_dispute"),
  ("Trade and the East India Company","shipping_manifest"),
  ("The Tea Act","tea_act")
 ],
 "rubric":[
  ("taxation and representation",["represent","no say","consent"],["tax","parliament","british"]),
  ("Tea trade and East India Company",["tea act","east india","company","monopoly"],[]),
  ("Destruction of tea cargo",["destroy","dump","throw","threw","overboard"],["tea","cargo"])
 ],
 "question":"Why did the colonists destroy the tea, and what was their dispute with Parliament?",
 "npcs":["merchant","dockworker"]
}
PARIS = {
 "id":"storming_bastille_1789","title":"Storming the Bastille",
 "place":"Paris · July 14, 1789",
 "intro":"Paris, July 14, 1789. A crowd gathers outside the Bastille fortress. Rumors spread, and people are searching for arms and gunpowder. Question a citizen, inspect the gates, or listen to the crowd.",
 "scene":"Paris on July 14, 1789: a crowd converges on the Bastille, a fortress-prison and royal symbol, seeking ammunition amid political unrest.",
 "evidence":{
  "royal_authority":"The Bastille was widely seen as a symbol of royal power and arbitrary imprisonment.",
  "gunpowder_search":"People seeking weapons and ammunition approached the Bastille for its gunpowder stores.",
  "political_crisis":"Economic hardship, distrust of royal authority and the political crisis surrounding the Estates-General fueled unrest.",
  "necker_dismissal":"King Louis XVI dismissed finance minister Jacques Necker on July 11, 1789; news of his dismissal intensified unrest in Paris."
 },
 "topics":[
  ("Royal authority","royal_authority"),
  ("The search for gunpowder","gunpowder_search"),
  ("Political and economic crisis","political_crisis"),
  ("Dismissal of Jacques Necker","necker_dismissal")
 ],
 "rubric":[
  ("Royal authority",["bastille","king","royal","monarchy","prison"],["power","symbol","authority","fear"]),
  ("Arms and gunpowder",["gunpowder","ammunition","weapons","arms"],[]),
  ("Revolutionary political crisis",["economic","bread","hunger","estates","inequality","political","crisis"],[])
 ],
 "question":"Why did the crowd target the Bastille, and what political tensions made the event significant?",
 "npcs":["citizen","guard"]
}
SCENARIOS={item["id"]:item for item in (BOSTON,PARIS)}

def get_scenario(sid):
    return SCENARIOS.get(sid)

def score_case(case, found, testimony="", answer=""):
    """100-point provisional rubric: 60 discovery + 40 historical concept coverage."""
    review = evaluate(case, testimony, answer, found)
    evidence_score = round(60 * len(found) / len(case["evidence"]))
    concept_score = round(30 * sum(review["checks"].values()) / len(case["rubric"]))
    response_score = 10 if answer.strip() and len(answer.strip().split()) >= 5 else 0
    return {"score": min(100, evidence_score + concept_score + response_score),
            "evidence_score": evidence_score, "court_score": concept_score + response_score,
            "score_max": 100}


def evaluate(case, testimony, answer, found):
    combined=(testimony+" "+answer).lower()
    checks={}
    for label, cues, context in case["rubric"]:
        checks[label]=any(term in combined for term in cues) and (not context or any(term in combined for term in context))
    strengths=[label for label, ok in checks.items() if ok]
    improvements=["Explain the historical connection: "+label+"." for label, ok in checks.items() if not ok]
    if not found: improvements.append("Recover an observation or document during the historical crisis.")
    if not answer.strip(): improvements.append("Answer the Archivist's follow-up question.")
    approved=bool(found) and bool(answer.strip()) and len(strengths)>=2
    return {"decision":"APPROVED" if approved else "NEEDS_REVISION",
            "checks":checks,"strengths":strengths,"improvements":improvements,
            "feedback":"You connected several historically relevant ideas." if approved else "The Archivist needs more specific historical connections.",
            "decision_basis":"Provisional rule-based evidence and concept review; not a verified historical accuracy judgment."}


def resolve_case(case, text, already, last_npc=None):
    """Natural questions trigger contextual NPC dialogue; evidence comes only from validated topics."""
    value=text.lower().strip()
    base={"ok":True,"discovered":None,"npc":None,"facts":[case["scene"]]}
    question=bool(re.search(r"\b(why|how|what|who|when|where|tell|explain)\b",value)) or "?" in value
    ask=bool(re.search(r"\b(ask|talk|speak|question|interview)\b",value))
    observe=bool(re.search(r"\b(look around|describe|observe|surroundings|what do i see)\b",value))
    inspect=bool(re.search(r"\b(inspect|examine|look at|check|search|read)\b",value))
    def clue(key,reply,npc=None):
        return {**base,"reply":reply,"npc":npc,
                "discovered":key if key not in already else None,
                "facts":[case["scene"],case["evidence"][key]]}
    def scene(reply):
        return {**base,"reply":reply}
    if observe:
        return scene(case["intro"])
    if case["id"]==BOSTON["id"]:
        if inspect and re.search(r"\b(ship|cargo|crate|manifest|record)\b",value):
            return clue("shipping_manifest","The cargo records connect the tea to the East India Company.")
        if re.search(r"\b(tea act|tax law|legislation)\b",value):
            return clue("tea_act","The Tea Act is central to the dispute over the East India Company.")
        if ask or question or last_npc=="merchant":
            return clue("taxation_dispute","The merchant explains that Parliament taxes the colonies without elected colonial representatives, and the tea cargo has become a focus of protest.","merchant")
    else:
        if re.search(r"\b(necker|finance minister|minister dismiss|king.s dismissal|last straw|last drop|final straw|triggered the unrest)\b",value):
            return clue("necker_dismissal","King Louis XVI dismissed the popular finance minister Jacques Necker on July 11. News of this decision inflamed anger in Paris.","citizen")
        if inspect and re.search(r"\b(gate|fortress|prison|bastille|wall)\b",value):
            return clue("royal_authority","The Bastille is a prison-fortress associated with royal authority.")
        if re.search(r"\b(gunpowder|powder|ammunition|weapons|arms|arsenal|why.*running|what.*running|run|rush|crowd.*going)\b",value):
            return clue("gunpowder_search","A nearby Parisian says the crowd is rushing toward the Bastille to seek gunpowder and ammunition.","citizen")
        if ask or question or (last_npc=="citizen"):
            return clue("political_crisis","A Parisian explains the uncertainty: bread shortages, fears of royal troops and distrust of the monarchy are fueling unrest.","citizen")
    if re.search(r"\b(hey|hello|hi|running|crowd|happening)\b",value):
        return scene(case["intro"])
    return {**base,"ok":False,"reply":"Describe what you want to investigate, or ask someone nearby what is happening."}


# The narrated historical information, not merely the user's wording, determines discoveries.
# Require distinctive combinations, avoiding awards for generic greetings or invented claims.
EVIDENCE_SIGNALS = {
 "boston_tea_party_1773": {
  "taxation_dispute": (("tax","taxation","parliament"),("represent","no say","without a voice")),
  "shipping_manifest": (("tea","cargo","ship","manifest"),("east india company",)),
  "tea_act": (("tea act",),("parliament","company","trade","tax")),
 },
 "storming_bastille_1789": {
  "royal_authority": (("bastille","fortress","prison"),("royal","king","monarch","symbol","imprison")),
  "gunpowder_search": (("bastille","fortress","crowd","people"),("gunpowder","ammunition","powder","weapons")),
  "political_crisis": (("bread","hunger","economic","political","estates-general","unrest","troops"),
                       ("royal","monarch","king","crisis","shortage","distrust","fear","political")),
  "necker_dismissal": (("necker",),("dismiss","removed","fired","ousted")),
 }
}

def detect_discoveries(case, reply, already=()):
    """Match a narrated fact to curated, scenario-specific evidence; unique ids only."""
    t=reply.lower()
    signals=EVIDENCE_SIGNALS[case["id"]]
    return [key for key in case["evidence"]
            if key not in already and
            key in signals and all(any(term in t for term in group) for group in signals[key])]
