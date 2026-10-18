"""The Last Archive: isolated Oracle-backed MVP API.

Run: uvicorn app.archive_server:app --port 8002
Needs ARCHIVE_DB_USER, ARCHIVE_DB_PASSWORD, ORACLE_CLIENT_DIR in .env.
This API deliberately does not alter Monkey King routes or MySQL configuration.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import oracledb
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from app.archive_logic import narrate
from app.archive_scenarios import SCENARIOS, BOSTON, get_scenario, resolve_case, evaluate, score_case, detect_discoveries, court_question

BASE = Path(__file__).resolve().parent.parent
load_dotenv(BASE / ".env")
WALLET = BASE / ".secrets" / "wallet"
DB_OWNER = "ADMIN"
_client_started = False

app = FastAPI(title="Neural Nexus — The Last Archive API", version="0.1")

def connect():
    global _client_started
    if not _client_started:
        path = os.getenv("ORACLE_CLIENT_DIR", "")
        if not path:
            raise RuntimeError("ORACLE_CLIENT_DIR is missing")
        oracledb.init_oracle_client(lib_dir=path, config_dir=str(WALLET))
        _client_started = True
    user = os.getenv("ARCHIVE_DB_USER", "")
    password = os.getenv("ARCHIVE_DB_PASSWORD", "")
    if not user or not password:
        raise RuntimeError("ARCHIVE_DB_USER / ARCHIVE_DB_PASSWORD not configured")
    return oracledb.connect(user=user, password=password, dsn="neuralnexus_low")

class StartRequest(BaseModel):
    nickname: str = Field(default="Chrono Agent", max_length=100)
    scenario_id: str = "boston_tea_party_1773"

class ActionRequest(BaseModel):
    session_id: str
    text: str = Field(min_length=1, max_length=1000)

class ExtractRequest(BaseModel):
    session_id: str

class VerdictRequest(BaseModel):
    session_id: str
    response: str = Field(default="", max_length=2500)

class CourtRequest(BaseModel):
    session_id: str
    testimony: str = Field(min_length=5, max_length=2500)

def record(cursor, session_id: str, kind: str, payload: dict):
    cursor.execute(
        f"INSERT INTO {DB_OWNER}.NN_EVENTS (SESSION_ID, EVENT_TYPE, EVENT_DATA) VALUES (:sid, :kind, :payload)",
        sid=session_id, kind=kind, payload=json.dumps(payload, ensure_ascii=False)
    )

def session_events(cursor, sid):
    cursor.execute(
        f"SELECT EVENT_TYPE, EVENT_DATA FROM {DB_OWNER}.NN_EVENTS "
        "WHERE SESSION_ID=:sid ORDER BY EVENT_ID", sid=sid
    )
    return [(r[0], decode_event_data(r[1])) for r in cursor]

def archive_score(events, case=BOSTON):
    return score_case(case, evidence(events, case))["evidence_score"]

def evidence(events, case=BOSTON):
    keys = {data.get("key") for kind, data in events
            if kind == "evidence_discovered" and isinstance(data, dict)}
    return {key: case["evidence"][key] for key in case["evidence"] if key in keys}

def deadline(events):
    started = next((data.get("started_at") for kind, data in events
                    if kind == "scenario_started" and isinstance(data, dict)), None)
    if not started:
        return None  # Older sessions predate the server clock.
    start = datetime.fromisoformat(started.replace("Z", "+00:00"))
    return start + timedelta(seconds=60)

def expire_if_needed(cur, sid, phase, events):
    limit = deadline(events)
    if phase == "CRISIS" and limit and datetime.now(timezone.utc) >= limit:
        record(cur, sid, "temporal_extraction", {"reason": "deadline", "at": datetime.now(timezone.utc).isoformat()})
        cur.execute(f"UPDATE {DB_OWNER}.NN_SESSIONS SET CURRENT_PHASE='COURT' WHERE SESSION_ID=:sid", sid=sid)
        return "COURT"
    return phase

def court_deadline(events):
    extraction = next((data.get("at") for kind, data in events
                       if kind == "temporal_extraction" and isinstance(data, dict) and data.get("at")), None)
    if extraction:
        return datetime.fromisoformat(extraction.replace("Z", "+00:00")) + timedelta(seconds=90)
    return None  # Legacy court sessions did not store their start time.

def court_expire(cur, sid, phase, events):
    limit = court_deadline(events)
    if phase == "COURT" and limit and datetime.now(timezone.utc) >= limit:
        cur.execute(f"UPDATE {DB_OWNER}.NN_SESSIONS SET CURRENT_PHASE='REVIEW' WHERE SESSION_ID=:sid AND CURRENT_PHASE='COURT'", sid=sid)
        record(cur, sid, "court_time_expired", {"at": datetime.now(timezone.utc).isoformat()})
        return "REVIEW"
    return phase

def active_session(cursor, sid):
    cursor.execute(f"SELECT CURRENT_PHASE FROM {DB_OWNER}.NN_SESSIONS WHERE SESSION_ID=:sid", sid=sid)
    row = cursor.fetchone()
    if not row:
        raise HTTPException(404, "Session not found")
    return row[0]

@app.get("/archive/health")
def health():
    try:
        with connect() as db:
            with db.cursor() as cur:
                cur.execute("SELECT 1 FROM DUAL")
                cur.fetchone()
        return {"ok": True, "store": "oracle"}
    except Exception as exc:
        return {"ok": False, "store": "oracle", "error_type": type(exc).__name__}

def session_case(cur, sid):
    cur.execute(f"SELECT SCENARIO_ID FROM {DB_OWNER}.NN_SESSIONS WHERE SESSION_ID=:sid", sid=sid)
    row=cur.fetchone()
    if not row:
        raise HTTPException(404, "Session not found")
    case=get_scenario(row[0])
    if not case:
        raise HTTPException(409, "This saved scenario is not yet supported")
    return case


@app.get("/archive/scenarios")
def scenarios():
    return [{"scenario_id":s["id"],"title":s["title"],"place":s["place"]} for s in SCENARIOS.values()]


@app.post("/archive/start")
def start(body: StartRequest):
    case=get_scenario(body.scenario_id)
    if not case:
        raise HTTPException(404,"Scenario not supported")
    sid=str(uuid.uuid4())
    try:
        with connect() as db:
            with db.cursor() as cur:
                cur.execute(
                    f"INSERT INTO {DB_OWNER}.NN_SESSIONS (SESSION_ID, SCENARIO_ID, PLAYER_NAME, CURRENT_PHASE) "
                    "VALUES (:sid,:scenario,:nick,'CRISIS')",
                    sid=sid,scenario=case["id"],nick=body.nickname)
                record(cur,sid,"scenario_started",{"scenario_id":case["id"],"started_at":datetime.now(timezone.utc).isoformat()})
                db.commit()
        return {"session_id":sid,"phase":"CRISIS","scenario_id":case["id"],
                "title":case["title"],"intro":case["intro"],"duration_seconds":60}
    except oracledb.DatabaseError as exc:
        raise HTTPException(503,"Cannot start scenario. Check Oracle NN_SCENARIOS seed and app-user grants.") from exc


@app.post("/archive/action")
def action(body: ActionRequest):
    # Determine allowed narrative from the session; do not award based on player keywords.
    with connect() as db:
        with db.cursor() as cur:
            phase=active_session(cur,body.session_id)
            case=session_case(cur,body.session_id)
            prior=session_events(cur,body.session_id)
            phase=expire_if_needed(cur,body.session_id,phase,prior)
            if phase!="CRISIS":
                db.commit()
                raise HTTPException(409,"Crisis ended: proceed to the Court of Time")
            already=set(evidence(prior,case))
            npc=next((data.get("npc") for kind,data in reversed(prior)
                      if kind=="npc_context" and isinstance(data,dict)),None)
            outcome=resolve_case(case,body.text,already,npc)
            record(cur,body.session_id,"player_action",{"text":body.text})
            db.commit()

    recent=[(kind,data.get("text","")) for kind,data in prior
            if kind in ("player_action","npc_reply") and isinstance(data,dict) and data.get("text")][-6:]
    context="\n".join(("Player" if kind=="player_action" else "NPC")+": "+txt[:250] for kind,txt in recent)
    prompt=("Continue as the same "+outcome["npc"]+". " if outcome.get("npc") else "") + (
        "Conversation so far (context only; not a source of historical facts):\n"+context+"\n"
        if context else "")+"Player: "+body.text
    reply=narrate(outcome["facts"],prompt,outcome["reply"]) if outcome["ok"] else {"text":outcome["reply"],"source":"engine"}
    # The LLM may paraphrase, but only verified scene facts can be attributed to it.
    # Restrict awards to the facts the engine explicitly authorized for this turn.
    permitted={key for key,fact in case["evidence"].items() if fact in outcome["facts"]}
    if outcome.get("discovered"):
        permitted.add(outcome["discovered"])
    candidates=[k for k in detect_discoveries(case,reply["text"]) if k in permitted]
    with connect() as db:
        with db.cursor() as cur:
            # Re-read events to prevent duplicate points on parallel player requests.
            current=session_events(cur,body.session_id)
            known=set(evidence(current,case))
            new=[key for key in candidates if key not in known]
            if outcome.get("npc"):
                record(cur,body.session_id,"npc_context",{"npc":outcome["npc"]})
            for key in new:
                record(cur,body.session_id,"evidence_discovered",
                       {"key":key,"fact":case["evidence"][key],
                        "points":round(60/len(case["evidence"])),"source":"npc_reply"})
            record(cur,body.session_id,"npc_reply",
                   {"text":reply["text"],"source":reply["source"],"npc":outcome.get("npc"),"evidence_ids":new})
            db.commit()
    return {"saved":True,"accepted":outcome["ok"],"session_id":body.session_id,
            "discovered":new[0] if new else None,"discoveries":new,
            "score_awarded":round(60*(len(known)+len(new))/len(case["evidence"]))-round(60*len(known)/len(case["evidence"])),
            "total_score":round(60*(len(known)+len(new))/len(case["evidence"])),
            "reply":reply["text"],"source":reply["source"]}


@app.post("/archive/extract")
def extract(body: ExtractRequest):
    """Early extraction or the first request after expiry; always persisted."""
    with connect() as db:
        with db.cursor() as cur:
            phase = active_session(cur, body.session_id)
            if phase == "CRISIS":
                record(cur, body.session_id, "temporal_extraction", {"reason": "player", "at": datetime.now(timezone.utc).isoformat()})
                cur.execute(
                    f"UPDATE {DB_OWNER}.NN_SESSIONS SET CURRENT_PHASE='COURT' WHERE SESSION_ID=:sid",
                    sid=body.session_id
                )
                db.commit()
    return {"phase": "COURT", "session_id": body.session_id}


@app.get("/archive/state/{session_id}")
def state(session_id: str):
    with connect() as db:
        with db.cursor() as cur:
            phase = active_session(cur, session_id)
            case = session_case(cur, session_id)
            history = session_events(cur, session_id)
            phase = expire_if_needed(cur, session_id, phase, history)
            db.commit()
    if phase == "COURT":
        with connect() as db:
            with db.cursor() as cur:
                phase = court_expire(cur, session_id, phase, history)
                db.commit()
    limit = deadline(history) if phase == "CRISIS" else court_deadline(history)
    remaining = max(0, int((limit - datetime.now(timezone.utc)).total_seconds())) if limit else None
    return {"session_id": session_id, "phase": phase, "remaining_seconds": remaining,
            "evidence": list(evidence(history,case)), "score": archive_score(history,case), "score_max":100, "scenario_id":case["id"], "title":case["title"], "deadline": limit.isoformat() if limit else None,
            "duration_seconds": 60 if phase == "CRISIS" else 90}


@app.post("/archive/court")
def court(body: CourtRequest):
    # The player's actual discovered clues, NOT every clue in the scenario.
    with connect() as db:
        with db.cursor() as cur:
            phase = active_session(cur, body.session_id)
            history = session_events(cur, body.session_id)
            phase = expire_if_needed(cur, body.session_id, phase, history)
            if phase == "CRISIS":
                record(cur, body.session_id, "temporal_extraction", {"reason": "court_requested", "at": datetime.now(timezone.utc).isoformat()})
                cur.execute(
                    f"UPDATE {DB_OWNER}.NN_SESSIONS SET CURRENT_PHASE='COURT' WHERE SESSION_ID=:sid",
                    sid=body.session_id
                )
            else:
                phase = court_expire(cur, body.session_id, phase, history)
            if phase != "COURT":
                db.commit()
                raise HTTPException(409, "Court time expired")
            case=session_case(cur,body.session_id)
            found = evidence(history,case)
            record(cur, body.session_id, "court_testimony",
                   {"text": body.testimony, "available_evidence": list(found)})
            db.commit()

    # Deterministic, open-ended follow-up: no AI-generated trivia or name/date recall.
    probe = court_question(case, body.testimony, found)
    probe["source"] = "curated"
    with connect() as db:
        with db.cursor() as cur:
            record(cur, body.session_id, "archivist_question",
                   {"text": probe["text"], "source": probe["source"], "question_type": probe["type"], "evidence_ids": list(found)})
            db.commit()
    return {"saved": True, "phase": "COURT", "archivist_question": probe["text"],
            "source": probe["source"], "question_type": probe["type"], "evidence_ids": list(found), "evaluated": False}


@app.post("/archive/verdict")
def verdict(body: VerdictRequest):
    """Transparent evidence review, not an AI-issued historical accuracy grade."""
    with connect() as db:
        with db.cursor() as cur:
            phase = active_session(cur, body.session_id)
            history = session_events(cur, body.session_id)
            case=session_case(cur,body.session_id)
            existing = next((data for kind, data in reversed(history)
                             if kind == "archive_verdict"), None)
            if existing:
                return {"phase": "REVIEW", **existing}
            if not any(kind == "court_testimony" for kind, _ in history):
                raise HTTPException(409, "Submit a testimony before requesting a verdict")
            if phase not in ("COURT", "REVIEW"):
                raise HTTPException(409, "Court is not active")
            if phase == "COURT":
                phase = court_expire(cur, body.session_id, phase, history)
            testimony = next((data.get("text", "") for kind, data in reversed(history)
                              if kind == "court_testimony" and isinstance(data, dict)), "")
            if body.response.strip() and phase == "COURT":
                record(cur, body.session_id, "court_answer", {"text": body.response.strip()})
            answer = body.response.strip() if phase == "COURT" else next(
                (data.get("text","") for kind,data in reversed(history)
                 if kind=="court_answer" and isinstance(data,dict)),"")
            found=evidence(history,case)
            review=evaluate(case,testimony,answer,found)
            breakdown=score_case(case,found,testimony,answer)
            report = {
                **review, **breakdown,
                "evidence_ids":list(found),"evidence_count":len(found),
                "evidence_total":len(case["evidence"]),
                "scenario_id":case["id"],"title":case["title"],
                "testimony":testimony,"court_answer":answer,
                "historical_review":[
                    {"topic":name,"fact":case["evidence"][key],"discovered":key in found}
                    for name,key in case["topics"]
                ]
            }
            record(cur, body.session_id, "archive_verdict", report)
            cur.execute(f"UPDATE {DB_OWNER}.NN_SESSIONS SET CURRENT_PHASE='REVIEW' WHERE SESSION_ID=:sid", sid=body.session_id)
            db.commit()
            return {"phase": "REVIEW", **report}


@app.post("/archive/save")
def save_visit(body: ExtractRequest):
    """Bookmark a run as an archival visit, not a pause of the server clock."""
    with connect() as db:
        with db.cursor() as cur:
            phase=active_session(cur,body.session_id)
            history=session_events(cur,body.session_id)
            if not any(kind=="visit_saved" for kind,_ in history):
                record(cur,body.session_id,"visit_saved",
                       {"at":datetime.now(timezone.utc).isoformat(),"phase":phase})
                db.commit()
    return {"saved":True,"session_id":body.session_id,"phase":phase,
            "note":"Visit archived; active server countdown is not paused."}


@app.get("/archive/saves")
def saves(limit: int = 30):
    """Recent runs from Oracle, including verdict summaries when available."""
    limit=max(1,min(limit,100))
    with connect() as db:
        with db.cursor() as cur:
            cur.execute(
                f"SELECT SESSION_ID, SCENARIO_ID, PLAYER_NAME, CURRENT_PHASE, STARTED_AT "
                f"FROM {DB_OWNER}.NN_SESSIONS ORDER BY STARTED_AT DESC FETCH FIRST {limit} ROWS ONLY"
            )
            rows=cur.fetchall()
            items=[]
            for sid,scenario_id,name,phase,started_at in rows:
                case=get_scenario(scenario_id)
                if not case:
                    continue
                history=session_events(cur,sid)
                result=next((data for kind,data in reversed(history) if kind=="archive_verdict"),None)
                items.append({
                    "session_id":sid,"scenario_id":scenario_id,"title":case["title"],
                    "player_name":name,"phase":phase,
                    "started_at":started_at.isoformat() if started_at else None,
                    "evidence_count":len(evidence(history,case)),
                    "score":result.get("score") if result else archive_score(history,case),
                    "decision":result.get("decision") if result else None,
                    "improvements":result.get("improvements",[]) if result else [],
                    "strengths":result.get("strengths",[]) if result else []
                })
    return {"saves":items}


@app.get("/archive/saves/{session_id}")
def saved_case(session_id: str):
    with connect() as db:
        with db.cursor() as cur:
            phase=active_session(cur,session_id)
            case=session_case(cur,session_id)
            history=session_events(cur,session_id)
    verdict=next((data for kind,data in reversed(history) if kind=="archive_verdict"),None)
    return {
        "session_id":session_id,"scenario_id":case["id"],"title":case["title"],
        "phase":phase,"score":verdict.get("score") if verdict else archive_score(history,case),
        "evidence":[{"id":key,"fact":fact} for key,fact in evidence(history,case).items()],
        "transcript":[{"type":kind,"data":data} for kind,data in history
                      if kind in ("player_action","npc_reply","court_testimony","archivist_question","court_answer")],
        "verdict":verdict,
    }


def decode_event_data(value):
    """Oracle JSON may return a Python dict/list directly, or a CLOB/string."""
    if hasattr(value, "read"):
        value = value.read()
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, (str, bytes, bytearray)):
        return json.loads(value)
    if value is None:
        return None
    raise TypeError(f"Unsupported event data type: {type(value).__name__}")

@app.get("/archive/events/{session_id}")
def events(session_id: str):
    try:
        with connect() as db:
            with db.cursor() as cur:
                active_session(cur, session_id)
                cur.execute(
                    f"SELECT EVENT_ID, EVENT_TYPE, EVENT_DATA FROM {DB_OWNER}.NN_EVENTS "
                    "WHERE SESSION_ID=:sid ORDER BY EVENT_ID",
                    sid=session_id
                )
                rows = [{"event_id": row[0], "type": row[1], "data": decode_event_data(row[2])} for row in cur]
        return {"session_id": session_id, "events": rows}
    except oracledb.DatabaseError as exc:
        raise HTTPException(503, "Oracle events read failed") from exc
