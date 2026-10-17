from pydantic import BaseModel, Field

class GameObject(BaseModel):
    id: str
    name: str
    description: str
    location_id: str
    hidden: bool = False
    discovered: bool = False
    carried: bool = False

class WorldState(BaseModel):
    scenario_id: str = "odyssey_island"
    location_id: str = "clearing"
    turn: int = 0
    objects: dict[str, GameObject] = Field(default_factory=dict)
    inventory: list[str] = Field(default_factory=list)
    events: list[str] = Field(default_factory=list)

class ActionRequest(BaseModel):
    session_id: str
    action: str
    target: str | None = None
