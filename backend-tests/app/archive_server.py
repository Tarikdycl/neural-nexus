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
from app.archive_logic import SCENE, CLUES, resolve, narrate

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

class ActionRequest(BaseModel):
    session_id: str
    text: str = Field(min_length=1, max_length=1000)

class ExtractRequest(BaseModel):
    session_id: str

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

def evidence(events):
    keys = {data.get("key") for kind, data in events
            if kind == "evidence_discovered" and isinstance(data, dict)}
    return {key: CLUES[key] for key in CLUES if key in keys}

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
        record(cur, sid, "temporal_extraction", {"reason": "deadline"})
        cur.execute(f"UPDATE {DB_OWNER}.NN_SESSIONS SET CURRENT_PHASE='COURT' WHERE SESSION_ID=:sid", sid=sid)
        return "COURT"
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

@app.post("/archive/start")
def start(body: StartRequest):
    sid = str(uuid.uuid4())
    try:
        with connect() as db:
            with db.cursor() as cur:
                cur.execute(
                    f"INSERT INTO {DB_OWNER}.NN_SESSIONS (SESSION_ID, SCENARIO_ID, PLAYER_NAME, CURRENT_PHASE) "
                    "VALUES (:sid, :scenario, :nick, 'CRISIS')",
                    sid=sid, scenario="boston_tea_party_1773", nick=body.nickname
                )
                record(cur, sid, "scenario_started", {"scenario_id": "boston_tea_party_1773", "started_at": datetime.now(timezone.utc).isoformat()})
                db.commit()
        return {"session_id": sid, "phase": "CRISIS", "scenario_id": "boston_tea_party_1773", "duration_seconds": 60}
    except oracledb.DatabaseError as exc:
        raise HTTPException(503, "Oracle session insert failed; check scenario seed and grants") from exc

@app.post("/archive/action")
def action(body: ActionRequest):
    # Event recording first; interpretation and narrative AI added separately.
    try:
        with connect() as db:
            with db.cursor() as cur:
                phase = active_session(cur, body.session_id)
                prior = session_events(cur, body.session_id)
                phase = expire_if_needed(cur, body.session_id, phase, prior)
                if phase != "CRISIS":
                    db.commit()
                    raise HTTPException(409, "Crisis ended: proceed to the Court of Time")
                already = set(evidence(prior))
                outcome = resolve(body.text, already)
                record(cur, body.session_id, "player_action", {"text": body.text})
                if outcome["discovered"]:
                    record(cur, body.session_id, "evidence_discovered", {"key": outcome["discovered"], "fact": CLUES[outcome["discovered"]]})
                db.commit()
        # Never allow an AI failure to erase a committed player action.
        reply = narrate(outcome["facts"], body.text, outcome["reply"]) if outcome["ok"] else {"text":outcome["reply"],"source":"engine"}
        return {"saved": True, "session_id": body.session_id, "accepted":outcome["ok"],
                "discovered":outcome["discovered"], "reply":reply["text"], "source":reply["source"]}
    except oracledb.DatabaseError as exc:
        raise HTTPException(503, "Oracle action save failed") from exc

@app.post("/archive/extract")
def extract(body: ExtractRequest):
    """Early extraction or the first request after expiry; always persisted."""
    with connect() as db:
        with db.cursor() as cur:
            phase = active_session(cur, body.session_id)
            if phase == "CRISIS":
                record(cur, body.session_id, "temporal_extraction", {"reason": "player"})
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
            history = session_events(cur, session_id)
            phase = expire_if_needed(cur, session_id, phase, history)
            db.commit()
    limit = deadline(history)
    remaining = max(0, int((limit - datetime.now(timezone.utc)).total_seconds())) if limit else None
    return {"session_id": session_id, "phase": phase, "remaining_seconds": remaining,
            "evidence": list(evidence(history)), "deadline": limit.isoformat() if limit else None}


@app.post("/archive/court")
def court(body: CourtRequest):
    # The player's actual discovered clues, NOT every clue in the scenario.
    with connect() as db:
        with db.cursor() as cur:
            phase = active_session(cur, body.session_id)
            history = session_events(cur, body.session_id)
            phase = expire_if_needed(cur, body.session_id, phase, history)
            if phase == "CRISIS":
                record(cur, body.session_id, "temporal_extraction", {"reason": "court_requested"})
                cur.execute(
                    f"UPDATE {DB_OWNER}.NN_SESSIONS SET CURRENT_PHASE='COURT' WHERE SESSION_ID=:sid",
                    sid=body.session_id
                )
            found = evidence(history)
            record(cur, body.session_id, "court_testimony",
                   {"text": body.testimony, "available_evidence": list(found)})
            db.commit()

    facts = [SCENE] + list(found.values())
    fallback = ("What evidence did you uncover, and how does it support your explanation?"
                if found else "What evidence did you gather before arriving at your conclusion?")
    probe = narrate(facts,
                    "The player testified: " + body.testimony
                    + "\nOnly these evidence IDs were discovered: " + ", ".join(found),
                    fallback, court=True)
    with connect() as db:
        with db.cursor() as cur:
            record(cur, body.session_id, "archivist_question",
                   {"text": probe["text"], "source": probe["source"], "evidence_ids": list(found)})
            db.commit()
    return {"saved": True, "phase": "COURT", "archivist_question": probe["text"],
            "source": probe["source"], "evidence_ids": list(found), "evaluated": False}


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
