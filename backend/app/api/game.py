from uuid import uuid4
from fastapi import APIRouter, HTTPException
from app.models.schemas import ActionRequest, StartRequest, WorldState
from app.engine.world import new_world, public_world
from app.engine.actions import apply_action
from app.ai.narrator import narrate
from pydantic import BaseModel

REALM_ROLES = {
    "odyssey_island": {"helm": "Ship Captain", "sword": "Warrior", "banner": "General", "bow": "Archer"},
    "monkey_king": {"staff": "Staff Adept", "scroll": "Sage", "cloud": "Cloud Wanderer", "seal": "Guardian"},
    "demi_demon": {"blade": "Hunter", "grimoire": "Occultist", "mask": "Infiltrator", "lantern": "Seeker"},
}

class ChoiceRequest(BaseModel):
    session_id: str
    artifact: str


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
    return {"session_id": session_id, "narration": "The island is quiet. For now.", "world": public_world(world)}

@router.post("/choose-artifact")
def choose_artifact(request: ChoiceRequest):
    world = SESSIONS.get(request.session_id)
    if world is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if world.chosen_artifact is not None:
        raise HTTPException(status_code=409, detail="Your path is already chosen.")
    artifact = request.artifact.strip().lower()
    available = REALM_ROLES.get(world.scenario_id, {})
    if artifact not in available:
        raise HTTPException(status_code=422, detail="Invalid role for this realm.")
    world.chosen_artifact = artifact
    world.character_class = available[artifact]
    world.journal["decisionEntries"].append({
        "id": "guardian-choice", "title": "The Path Chosen",
        "body": f"I reached for the {artifact}. The guardian named me {world.character_class}.",
        "tags": [world.character_class]
    })
    return {"session_id": request.session_id, "narration": f"The guardian studies the {artifact}, then steps aside. The path opens before you.", "world": public_world(world)}

@router.post("/action")
def game_action(request: ActionRequest):
    world = SESSIONS.get(request.session_id)
    if world is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if not world.chosen_artifact:
        raise HTTPException(status_code=409, detail="Choose your path before exploring.")
    result = apply_action(world, request.action, request.target)
    return {"session_id": request.session_id, "narration": narrate(world, result), "world": public_world(world)}

@router.get("/{session_id}")
def get_game(session_id: str):
    world = SESSIONS.get(session_id)
    if world is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session_id": session_id, "world": public_world(world)}
