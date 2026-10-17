from app.engine.world import new_world, public_world
from app.engine.actions import apply_action

def test_hidden_object_stays_hidden_until_search():
    w = new_world()
    assert not public_world(w)["visible_objects"]
    assert "Bronze Compass" in apply_action(w, "search")
    assert public_world(w)["visible_objects"][0]["id"] == "compass"

def test_cannot_take_hidden_object():
    w = new_world()
    assert "not available" in apply_action(w, "take", "compass")
    assert not w.inventory

def test_movement_is_validated():
    w = new_world()
    assert "no path" in apply_action(w, "move", "north")
    assert w.location_id == "clearing"
    apply_action(w, "move", "east")
    assert w.location_id == "beach"

def test_sessions_isolated():
    a, b = new_world(), new_world()
    apply_action(a, "search")
    assert not public_world(b)["visible_objects"]
