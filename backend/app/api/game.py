from uuid import uuid4
from fastapi import APIRouter, HTTPException
from app.models.schemas import ActionRequest, StartRequest, WorldState
from app.engine.world import new_world, public_world
from app.engine.actions import apply_action
from app.ai.narrator import narrate

router = APIRouter(prefix="/game", tags=["game"])
SESSIONS: dict[str, WorldState] = {}

@router.post("/start")
def start_game(request: StartRequest | None = None):
    request = request or StartRequest()
    if request.realm_id != "odyssey_island":
        raise HTTPException(status_code=422, detail="Realm not implemented yet")
    session_id = str(uuid4())
    world = new_world()
    SESSIONS[session_id] = world
    return {"session_id": session_id, "narration": "Welcome, young explorer! A curious island awaits.", "world": public_world(world)}

@router.post("/action")
def game_action(request: ActionRequest):
    world = SESSIONS.get(request.session_id)
    if world is None:
        raise HTTPException(status_code=404, detail="Session not found")
    result = apply_action(world, request.action, request.target)
    return {"session_id": request.session_id, "narration": narrate(world, result), "world": public_world(world)}

@router.get("/{session_id}")
def get_game(session_id: str):
    world = SESSIONS.get(session_id)
    if world is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session_id": session_id, "world": public_world(world)}
