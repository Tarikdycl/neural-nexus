"""Constrained historical action resolver and OCI narrator for the first Archive case.

The engine decides what can be discovered. The AI only verbalizes allowed facts.
"""
from __future__ import annotations
import os
import re
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from app.narrator import OCIChatModel

SCENE = "Boston Harbor, December 16, 1773. Three tea ships are in port. Crowds have gathered near the docks."
CLUES = {
    "shipping_manifest": "A cargo record connects the ships' tea to the East India Company.",
    "taxation_dispute": "Colonial protesters objected to taxation by a Parliament where they lacked elected representation.",
    "tea_act": "The Tea Act of 1773 changed arrangements for East India Company tea and intensified existing disputes."
}
_executor = ThreadPoolExecutor(max_workers=3)

@lru_cache(maxsize=1)
def model():
    from app.config import load_settings
    s=load_settings()
    if not s.ai_enabled or not s.oci_compartment_id:
        return None
    try:
        return OCIChatModel(s.oci_config_file,s.oci_profile,s.oci_compartment_id,
                            s.oci_genai_endpoint,s.oci_genai_model,s.ai_timeout_s)
    except Exception:
        return None

def narrate(approved_facts: list[str], player_text: str, fallback: str, court: bool=False):
    client=model()
    if not client:
        return {"text":fallback,"source":"fallback"}
    system=(
        "You are the Archivist in an educational history game. "
        "Use ONLY the supplied verified historical facts and allowed scene observations. "
        "Do not reveal hidden clues, invent events, claim actions succeeded without confirmation, or decide the player's score. "
        "For court mode, ask ONE concise probing question challenging the player's historical explanation. "
        "For scene mode, reply as a believable narrator/NPC in 1-2 short sentences. "
        "Do not give the player the correct final answer. "
        "Facts you may use: "+ " | ".join(approved_facts)
    )
    if court:
        system += " Court mode."
    else:
        system += " Scene mode."
    future=_executor.submit(client.chat,system,player_text,0.2,140)
    try:
        out=future.result(timeout=5)
        out=(out or "").strip()
        if out and len(out)<=900:
            return {"text":out,"source":"ai"}
    except (Exception, FutureTimeout):
        pass
    return {"text":fallback,"source":"fallback"}

def resolve(text: str, already: set[str], last_npc: str | None = None):
    """Resolve allowed actions, with conversational follow-ups for the current NPC."""
    value = text.lower().strip()
    base = {"discovered": None, "facts": [SCENE], "npc": None}
    if len(value) > 1000:
        return {**base, "ok": False, "reply": "Please describe a shorter action."}

    # Explicit inspection takes priority over ongoing dialogue.
    if re.search(r"\b(inspect|examine|read|search|check|look at)\b", value) and re.search(
        r"\b(cargo|document|manifest|crate|shipping|paper|ship)\b", value
    ):
        key = "shipping_manifest"
        return {**base, "ok": True,
                "reply": CLUES[key] if key not in already else "You have already checked these cargo records.",
                "discovered": key if key not in already else None, "facts": [SCENE, CLUES[key]]}

    if re.search(r"\b(inspect|examine|ask|read|study|investigate)\b", value) and re.search(
        r"\b(tea act|tax law|legislation)\b", value
    ):
        key = "tea_act"
        return {**base, "ok": True, "reply": CLUES[key],
                "discovered": key if key not in already else None, "facts": [SCENE, CLUES[key]]}

    speaking = re.search(r"\b(ask|talk|speak|question|interview)\b", value)
    person = re.search(r"\b(merchant|dockworker|protest|tax|colonist|someone|person|people|anyone|man|woman|crowd)\b", value)
    if speaking and person:
        key = "taxation_dispute"
        return {**base, "ok": True, "npc": "merchant",
                "reply": "The merchant looks toward the ships. 'That tea belongs to the East India Company. Folks are angry because Parliament makes rules and taxes us without any representatives from the colonies.'",
                "discovered": key if key not in already else None,
                "facts": [SCENE, CLUES[key]]}

    # Continue the established conversation rather than requiring 'ask a merchant' again.
    followup = re.search(
        r"\b(why|how|what|who|when|where|really|explain|more|then|continue|go on|mean|tea|tax)\b",
        value
    )
    if last_npc == "merchant" and (followup or value.endswith("?")):
        key = "taxation_dispute"
        return {**base, "ok": True, "npc": "merchant",
                "reply": "The merchant continues, 'It is not just the cost of tea. The Tea Act favored the East India Company, and Parliament claims the right to tax us though we elect no representatives there.'",
                "discovered": key if key not in already else None,
                "facts": [SCENE, CLUES[key], CLUES["tea_act"]]}

    if re.search(r"\b(look|observe|listen|wait|describe|surroundings|around|where am i|what do i see)\b", value):
        return {**base, "ok": True,
                "reply": "Lanterns tremble in the harbor wind. Three tea ships are anchored nearby, and a tense crowd murmurs on the docks."}

    if re.search(r"\b(hey|hello|hi|what.s happening|what.s going on|what is happening)\b", value):
        return {**base, "ok": True,
                "reply": "Boston Harbor, late evening. A crowd gathers beside three tea ships. A nearby merchant seems willing to talk."}

    return {**base, "ok": False,
            "reply": "The harbor is busy tonight. You could question a merchant, look around, or examine the ships' cargo."}
