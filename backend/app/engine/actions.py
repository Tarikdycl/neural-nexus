from app.models.schemas import WorldState
from app.engine.world import LOCATIONS, visible_objects


def apply_action(world: WorldState, action: str, target: str | None = None) -> str:
    command = action.strip().lower()
    if command not in {"look", "search", "take", "move"}:
        return "Try look, search, take, or move."
    if command == "look":
        outcome = LOCATIONS[world.location_id]["description"]
        class_observations = {
            "Warrior": "You notice the safest footing and possible hazards along the path.",
            "Ship Captain": "You assess the wind and shoreline for a safe route.",
            "General": "You survey the terrain, judging where a group could move safely.",
            "Archer": "You notice distant movement and places with clear sightlines.",
            "Mage": "You study the shifting wind and how the environment responds to it.",
            "Scholar": "You inspect the old stonework for signs of its history.",
            "Explorer": "You scan the terrain, searching for tracks and overlooked landmarks.",
        }
        outcome += " " + class_observations.get(world.character_class, "")
        # An Explorer can spot the hidden compass without repeating a search action.
        if world.character_class == "Ship Captain" and world.location_id == "clearing":
            compass = world.objects.get("compass")
            if compass and compass.hidden and not compass.discovered and not compass.carried:
                compass.discovered = True
                outcome += " A Bronze Compass glints beneath an olive root."
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
