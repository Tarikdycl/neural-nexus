"""HTTP API (design doc section 9) and the web page.

Run on the server:   uvicorn app.main:app --host 0.0.0.0 --port 80
Run on a laptop:     uvicorn app.main:app --reload     (then open http://127.0.0.1:8000)

Every route is a thin wrapper: it checks the request shape, calls one
Engine method, and returns its answer. All game rules live in engine.py.
"""

from __future__ import annotations

import hmac
import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.config import Settings, load_settings
from app.content import load_story
from app.engine import Engine, GameError
from app.migrations import SCHEMA_VERSION
from app.narrator import Narrator, OCIChatModel
from app.store_memory import MemoryStore

log = logging.getLogger("monkey_king")
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


# ------------------------------------------------------------ wiring

def build_store(settings: Settings, story: dict[str, Any]):
    want_mysql = settings.store == "mysql" or (settings.store == "auto" and settings.db_host)
    if not want_mysql:
        log.info("Using the in-memory store (play data is lost on restart).")
        return MemoryStore(story)
    try:
        from app.store_mysql import MySQLStore
        store = MySQLStore(settings.db_host, settings.db_port, settings.db_user,
                           settings.db_password, settings.db_name)
        store.ping()
        version = store.schema_version()
        if version != SCHEMA_VERSION:
            # Review 2: an old database must be upgraded, not used half-matching.
            raise RuntimeError(f"database is version {version}, this code needs version {SCHEMA_VERSION} - "
                               "run: python scripts/setup_db.py")
        if not store.variant_ids():
            raise RuntimeError("story tables are empty - run: python scripts/setup_db.py")
        log.info("Using MySQL at %s/%s.", settings.db_host, settings.db_name)
        return store
    except Exception as e:
        if not settings.fallback_to_memory:
            raise
        # Design doc section 12 fallback: DB fails -> content in a Python dictionary.
        log.error("MySQL unavailable (%s). FALLING BACK to the in-memory store.", e)
        return MemoryStore(story)


def build_narrator(settings: Settings, story: dict[str, Any]) -> Narrator:
    model = None
    if settings.ai_enabled and settings.oci_compartment_id:
        try:
            model = OCIChatModel(settings.oci_config_file, settings.oci_profile, settings.oci_compartment_id,
                                 settings.oci_genai_endpoint, settings.oci_genai_model, settings.ai_timeout_s)
            log.info("AI narrator on: %s", settings.oci_genai_model)
        except Exception as e:
            log.error("AI narrator could not start (%s). Using pre-written lines.", e)
    else:
        log.info("AI narrator off (AI_ENABLED=0 or no OCI_COMPARTMENT_ID). Using pre-written lines.")
    return Narrator(model, story["fallbacks"], timeout_s=settings.ai_timeout_s)


def build_engine(settings: Settings | None = None) -> Engine:
    settings = settings or load_settings()
    story = load_story()
    return Engine(build_store(settings, story), build_narrator(settings, story), story)


# ------------------------------------------------------- request bodies
# Field limits are a first wall; the engine checks everything again.

class StartBody(BaseModel):
    nickname: str = Field(max_length=200)


class ActionBody(BaseModel):
    session_id: str = Field(max_length=36)
    realm: str = Field(max_length=20)
    action: str = Field(max_length=10)


class AskBody(BaseModel):
    session_id: str = Field(max_length=36)
    realm: str = Field(max_length=20)
    question: str = Field(max_length=2000)   # cut to 200 by the engine (section 11)


class OpenBody(BaseModel):
    session_id: str = Field(max_length=36)
    realm: str = Field(max_length=20)


class AssessmentBody(BaseModel):
    session_id: str = Field(max_length=36)
    phase: str = Field(max_length=4)
    answers: dict[str, str] = Field(max_length=10)


class PredictBody(BaseModel):
    session_id: str = Field(max_length=36)
    pearl: str = Field(max_length=20)          # the per-game pearl code, never P1..P6
    choice: str = Field(max_length=120)


class HintBody(BaseModel):
    session_id: str = Field(max_length=36)
    puzzle: str = Field(max_length=10)         # PREDICT, TIMELINE, DUEL or VERDICT
    realm: str | None = Field(default=None, max_length=20)


class TimelineBody(BaseModel):
    session_id: str = Field(max_length=36)
    order: list[str] = Field(max_length=6)


class DuelBody(BaseModel):
    session_id: str = Field(max_length=36)
    round: int = Field(ge=1, le=3)
    said_lie: bool
    proofs: list[str] = Field(max_length=2)
    reason: str = Field(max_length=120)


class VerdictBody(BaseModel):
    session_id: str = Field(max_length=36)
    named: str = Field(max_length=40)
    proof: list[str] = Field(max_length=2)


class LegendBody(BaseModel):
    session_id: str = Field(max_length=36)
    text: str = Field(default="", max_length=10000)
    finish: bool = False


# ------------------------------------------------------------- the app

def create_app(engine: Engine | None = None, teacher_code: str | None = None) -> FastAPI:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("mysql.connector").setLevel(logging.WARNING)
    engine = engine or build_engine()
    app = FastAPI(title="The Stolen Hours of the Monkey King", docs_url="/api/docs", redoc_url=None)
    app.state.engine = engine
    code_needed = load_settings().teacher_code if teacher_code is None else teacher_code

    @app.exception_handler(GameError)
    async def game_error(_: Request, e: GameError) -> JSONResponse:
        return JSONResponse({"error": e.code, "message": e.message}, status_code=e.status)

    @app.exception_handler(Exception)
    async def save_failed(_: Request, e: Exception) -> JSONResponse:
        # Every player action is one transaction (store.atomic), so if anything failed,
        # NOTHING from that click was kept and the same click can simply be sent again.
        logging.getLogger("monkey-king").exception("request failed; transaction rolled back")
        return JSONResponse({"error": "save_failed",
                             "message": "The Scroll could not save that. Nothing was lost - please try again."},
                            status_code=503)

    @app.get("/api/health")
    def health(check_ai: bool = False):
        """ai_configured only means settings exist. ai_last_call says what really happened last time.
        Add ?check_ai=1 to make one real AI call now (review fix: 'configured' is not 'working').
        Answers 503 (ok: false) if the database cannot be reached or is on the wrong version."""
        check = engine.narrator.ping() if check_ai else None   # run first, so ai_last_call includes it
        try:
            db_ok = bool(engine.store.ping())
            version = engine.store.schema_version()
        except Exception as e:  # noqa: BLE001 - health must answer, not crash
            log.error("health: database check failed: %s", e)
            db_ok, version = False, None
        version_ok = version is None or version == SCHEMA_VERSION   # None = in-memory store
        out = {"ok": db_ok and version_ok, "store": engine.store.kind, "db_ok": db_ok,
               "schema_version": version, "schema_version_needed": SCHEMA_VERSION,
               "ai_configured": engine.narrator.ai_enabled, "ai_last_call": engine.narrator.last_call}
        if check is not None:
            out["ai_check"] = check
        return out if out["ok"] else JSONResponse(out, status_code=503)

    @app.post("/api/start")
    def start(body: StartBody) -> dict[str, Any]:
        return engine.start(body.nickname)

    @app.get("/api/state/{session_id}")
    def state(session_id: str) -> dict[str, Any]:
        return engine.state(session_id)

    @app.get("/api/assessment/{phase}")
    def assessment(phase: str, session_id: str) -> dict[str, Any]:
        return engine.assessment(session_id, phase)

    @app.post("/api/assessment")
    def submit_assessment(body: AssessmentBody) -> dict[str, Any]:
        return engine.submit_assessment(body.session_id, body.phase, body.answers)

    @app.post("/api/action")
    def action(body: ActionBody) -> dict[str, Any]:
        return engine.action(body.session_id, body.realm, body.action)

    @app.post("/api/ask")
    def ask(body: AskBody) -> dict[str, Any]:
        return engine.ask(body.session_id, body.realm, body.question)

    @app.post("/api/open")
    def open_pearl(body: OpenBody) -> dict[str, Any]:
        return engine.open_pearl(body.session_id, body.realm)

    @app.post("/api/predict")
    def predict(body: PredictBody) -> dict[str, Any]:
        return engine.predict(body.session_id, body.pearl, body.choice)

    @app.post("/api/hint")
    def hint(body: HintBody) -> dict[str, Any]:
        return engine.hint(body.session_id, body.puzzle, body.realm)

    @app.post("/api/timeline")
    def timeline(body: TimelineBody) -> dict[str, Any]:
        return engine.timeline(body.session_id, body.order)

    @app.get("/api/duel/{round_no}")
    def duel_claim(round_no: int, session_id: str) -> dict[str, Any]:
        return engine.duel_claim(session_id, round_no)

    @app.post("/api/duel")
    def duel(body: DuelBody) -> dict[str, Any]:
        return engine.duel(body.session_id, body.round, body.said_lie, body.proofs, body.reason)

    @app.post("/api/verdict")
    def verdict(body: VerdictBody) -> dict[str, Any]:
        return engine.verdict(body.session_id, body.named, body.proof)

    @app.post("/api/legend")
    def legend(body: LegendBody) -> dict[str, Any]:
        return engine.legend(body.session_id, body.text, body.finish)

    @app.get("/api/teacher")
    def teacher(code: str = "") -> Any:
        # Optional passcode (TEACHER_CODE in .env). Not a student login: students never need it.
        if code_needed and not hmac.compare_digest(code.encode(), code_needed.encode()):
            return JSONResponse({"error": "teacher_code", "message": "Type the teacher code to see class numbers."},
                                status_code=403)
        return engine.teacher()

    # ---- the web page (one page app; /teacher opens the teacher view)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    @app.get("/teacher", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html", headers={"Cache-Control": "no-cache"})

    return app


def __getattr__(name: str):
    # `uvicorn app.main:app` builds the real app on first use, so importing
    # this module in tests does not try to reach MySQL or OCI.
    if name == "app":
        globals()["app"] = create_app()
        return globals()["app"]
    raise AttributeError(name)
