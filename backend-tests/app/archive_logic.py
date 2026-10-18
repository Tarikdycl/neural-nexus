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

def resolve(text: str, already: set[str]):
    value=text.lower().strip()
    if len(value)>1000:
        return {"ok":False,"reply":"Please describe a shorter action.","discovered":None,"facts":[SCENE]}
    # Deliberate, narrow intent recognition. No LLM is permitted to grant evidence.
    if re.search(r"\b(inspect|examine|read|search|check|look at)\b",value) and re.search(r"\b(cargo|document|manifest|crate|shipping|paper|ship)\b",value):
        key="shipping_manifest"
        return {"ok":True,"reply":CLUES[key] if key not in already else "You have already examined these records.","discovered":key if key not in already else None,"facts":[SCENE, CLUES[key]]}
    if re.search(r"\b(ask|talk|speak|question|interview)\b",value) and re.search(r"\b(merchant|dockworker|protest|tax|colonist)\b",value):
        key="taxation_dispute"
        return {"ok":True,"reply":"A dockworker describes a dispute over taxation and representation.","discovered":key if key not in already else None,"facts":[SCENE, CLUES[key]]}
    if re.search(r"\b(inspect|examine|ask|read|study|investigate)\b",value) and re.search(r"\b(tea act|tax law|legislation)\b",value):
        key="tea_act"
        return {"ok":True,"reply":CLUES[key],"discovered":key if key not in already else None,"facts":[SCENE, CLUES[key]]}
    if re.search(r"\b(look|observe|listen|wait)\b",value):
        return {"ok":True,"reply":"Lanterns flicker across the harbor. The ships remain anchored as the crowd grows.","discovered":None,"facts":[SCENE]}
    return {"ok":False,"reply":"You can look around, ask a dockworker, or inspect the ships' cargo records. Describe what you want to do.","discovered":None,"facts":[SCENE]}
