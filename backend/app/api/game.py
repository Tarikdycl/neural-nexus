from uuid import uuid4
from fastapi import APIRouter, HTTPException
from app.models.schemas import ActionRequest, StartRequest, WorldState
from app.engine.world import new_world, public_world
from app.engine.actions import apply_action
from app.ai.narrator import narrate
from pydantic import BaseModel

ARTIFACTS = {"sword": "Warrior", "staff": "Mage", "book": "Scholar", "compass": "Explorer"}

class ChoiceRequest(BaseModel):
    session_id: str
    artifact: str

class ChallengeRequest(BaseModel):
    session_id: str
    answer: str


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
    if artifact not in ARTIFACTS:
        raise HTTPException(status_code=422, detail="Choose sword, staff, book, or compass.")
    world.chosen_artifact = artifact
    world.character_class = ARTIFACTS[artifact]
    world.journal["decisionEntries"].append({
        "id": "guardian-choice", "title": "The Path Chosen",
        "body": f"I reached for the {artifact}. The guardian named me {world.character_class}.",
        "tags": [world.character_class]
    })
    return {"session_id": request.session_id, "narration": f"The guardian studies the {artifact}, then steps aside. The path opens before you.", "world": public_world(world)}

@router.post("/challenge")
def solve_challenge(request: ChallengeRequest):
    world = SESSIONS.get(request.session_id)
    if world is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if not world.chosen_artifact:
        raise HTTPException(status_code=409, detail="Choose your artifact first.")
    if world.challenge_solved:
        return {"session_id": request.session_id, "narration": "The stone gate is already open.", "world": public_world(world)}
    if request.answer.strip().lower() != "long":
        return {"session_id": request.session_id, "narration": "The stone barely moves. Think about how far from the pivot you apply the force.", "world": public_world(world)}
    world.challenge_solved = True
    world.events.append("Opened the stone gate using a longer lever.")
    world.journal["learningEntries"].append({
        "id": "lever-advantage", "title": "The Stone Gate",
        "body": "I learned that a longer effort arm can reduce the force needed to lift a load.",
        "tags": ["Physics", "Mechanical advantage"]
    })
    return {"session_id": request.session_id, "narration": "The longest lever moves the stone. The gate opens. You've put mechanical advantage to work.", "world": public_world(world)}

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
