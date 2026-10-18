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
  "political_crisis":"Economic hardship, distrust of royal authority and the political crisis surrounding the Estates-General fueled unrest."
 },
 "topics":[
  ("Royal authority","royal_authority"),
  ("The search for gunpowder","gunpowder_search"),
  ("Political and economic crisis","political_crisis")
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
            "decision_basis":"Provisional concept coverage only; not a fact-checked AI grading certification."}

def resolve_case(case, text, already, last_npc=None):
    value=text.lower().strip()
    base={"ok":True,"discovered":None,"npc":None,"facts":[case["scene"]]}
    def clue(key, reply, npc=None):
        return {**base,"reply":reply,"npc":npc,"discovered":key if key not in already else None,
                "facts":[case["scene"],case["evidence"][key]]}
    asking=bool(re.search(r"\b(ask|talk|speak|question|interview)\b",value))
    follow=bool(re.search(r"\b(why|how|what|who|when|where|explain|tell|more|mean)\b",value)) or value.endswith("?")
    if case["id"]==BOSTON["id"]:
        if re.search(r"\b(inspect|examine|read|search|check)\b",value) and re.search(r"\b(ship|cargo|crate|manifest|record)\b",value):
            return clue("shipping_manifest","The cargo manifests connect the tea to the East India Company.")
        if re.search(r"\b(tea act|tax law|legislation)\b",value):
            return clue("tea_act","You find references to Parliament's Tea Act and the East India Company.")
        if (asking and re.search(r"\b(merchant|dockworker|people|anyone|someone|crowd|colonist)\b",value)) or (last_npc=="merchant" and follow):
            return clue("taxation_dispute","The merchant explains that colonists oppose Parliament taxing them without representation.", "merchant")
    else:
        if re.search(r"\b(inspect|examine|look at|check|search)\b",value) and re.search(r"\b(gate|fortress|prison|bastille|walls)\b",value):
            return clue("royal_authority","Citizens describe the Bastille as a symbol of royal authority.")
        if re.search(r"\b(gunpowder|powder|ammunition|weapons|arms|arsenal)\b",value):
            return clue("gunpowder_search","People tell you they are seeking gunpowder and ammunition held at the fortress.")
        if (asking and re.search(r"\b(citizen|people|crowd|anyone|someone|guard|worker)\b",value)) or (last_npc=="citizen" and follow):
            return clue("political_crisis","A Parisian describes bread shortages, political upheaval and mounting distrust of royal power.","citizen")
    if re.search(r"\b(look|observe|listen|wait|describe|surroundings|around|see|happening|going on|hello|hey)\b",value):
        return {**base,"reply":case["intro"]}
    return {**base,"ok":False,"reply":"You can ask someone nearby, investigate an object, or describe your surroundings."}
