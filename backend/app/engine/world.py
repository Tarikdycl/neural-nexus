from app.models.schemas import GameObject, WorldState

LOCATIONS = {
    "clearing": {"name": "Moonlit Clearing", "description": "Olive trees rustle in the warm breeze.", "exits": {"east": "beach"}},
    "beach": {"name": "Silver Beach", "description": "Gentle waves roll against the shore.", "exits": {"west": "clearing"}},
}

def new_world() -> WorldState:
    return WorldState(objects={
        "compass": GameObject(id="compass", name="Bronze Compass", description="A tiny compass marked with a star.", location_id="clearing", hidden=True),
        "shell": GameObject(id="shell", name="Pearl Shell", description="A smooth shell glimmering in the sun.", location_id="beach"),
    })

def visible_objects(world: WorldState) -> list[GameObject]:
    return [o for o in world.objects.values() if o.location_id == world.location_id and not o.carried and (not o.hidden or o.discovered)]

def public_world(world: WorldState) -> dict:
    loc = LOCATIONS[world.location_id]
    return {"location_id": world.location_id, "location": loc["name"], "description": loc["description"], "exits": loc["exits"], "turn": world.turn,
            "visible_objects": [{"id": o.id, "name": o.name, "description": o.description} for o in visible_objects(world)],
            "inventory": [{"id": world.objects[i].id, "name": world.objects[i].name} for i in world.inventory], "events": world.events[-5:], "character_class": world.character_class, "chosen_artifact": world.chosen_artifact, "challenge_solved": world.challenge_solved, "journal": world.journal}
