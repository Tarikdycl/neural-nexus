from app.models.schemas import WorldState
from app.engine.world import public_world

# Safe deterministic narrator for MVP. When adding an LLM, send only public_world()
# and validated outcome, never raw hidden state.
def narrate(world: WorldState, validated_outcome: str) -> str:
    place = public_world(world)["location"]
    return f"{validated_outcome} Your adventure continues in {place}. What will you try next?"
