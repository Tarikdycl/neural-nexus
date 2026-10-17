from typing import Literal
from pydantic import BaseModel, Field

# Shared models: Siddiq (AI), Taseen (storage), and the API must use these.
ActionType = Literal["look", "search", "take", "move", "talk", "use", "wait"]

class ActionProposal(BaseModel):
    """AI suggestion only. The engine decides if it can happen."""
    action_type: ActionType
    target: str | None = None
    dialogue: str | None = None
    duration_seconds: int = Field(default=60, ge=0, le=3600)

class GameObject(BaseModel):
    id: str
    name: str
    description: str
    location_id: str
    hidden: bool = False
    discovered: bool = False
    carried: bool = False

class WorldState(BaseModel):
    # Existing starter fields kept compatible.
    scenario_id: str = "odyssey_island"
    location_id: str = "clearing"
    turn: int = 0
    objects: dict[str, GameObject] = Field(default_factory=dict)
    inventory: list[str] = Field(default_factory=list)
    events: list[str] = Field(default_factory=list)
    character_class: str | None = None
    chosen_artifact: str | None = None
    challenge_solved: bool = False
    journal: dict = Field(default_factory=lambda: {"storyEntries": [], "learningEntries": [], "decisionEntries": []})

class ActionRequest(BaseModel):
    session_id: str
    action: str
    target: str | None = None

class StartRequest(BaseModel):
    realm_id: str = "odyssey_island"
    player_name: str | None = None

class PublicItem(BaseModel):
    id: str
    name: str
    description: str | None = None

class PublicWorld(BaseModel):
    location_id: str
    location: str
    description: str
    exits: dict[str, str]
    turn: int
    visible_objects: list[PublicItem] = Field(default_factory=list)
    inventory: list[PublicItem] = Field(default_factory=list)
    events: list[str] = Field(default_factory=list)

class GameResponse(BaseModel):
    session_id: str
    narration: str
    world: PublicWorld
