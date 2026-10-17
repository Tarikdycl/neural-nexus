from app.models.schemas import WorldState
from app.engine.world import LOCATIONS, visible_objects


def apply_action(world: WorldState, action: str, target: str | None = None) -> str:
    command = action.strip().lower()
    if command not in {"look", "search", "take", "move"}:
        return "Try look, search, take, or move."
    if command == "look":
        outcome = LOCATIONS[world.location_id]["description"]
    elif command == "search":
        found = [o for o in world.objects.values() if o.location_id == world.location_id and o.hidden and not o.discovered and not o.carried]
        for obj in found:
            obj.discovered = True
        outcome = "You discover " + ", ".join(o.name for o in found) + "!" if found else "You search carefully but find nothing new."
    elif command == "take":
        selected = next((o for o in visible_objects(world) if o.id == target), None)
        if selected is None:
            return "That item is not available here."
        selected.carried = True
        world.inventory.append(selected.id)
        outcome = f"You pick up {selected.name}."
    else:
        next_id = LOCATIONS[world.location_id]["exits"].get(target or "")
        if not next_id:
            return "There is no path in that direction."
        world.location_id = next_id
        outcome = f"You travel to {LOCATIONS[next_id]['name']}."
    world.turn += 1
    world.events.append(outcome)
    return outcome
