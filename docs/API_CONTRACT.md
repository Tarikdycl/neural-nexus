# Neural Nexus — Shared Contract v1

This document is the agreement between API/frontend (Tarik), AI (Siddiq), and SQL/world persistence (Taseen). Do not change an existing response field without discussing it.

## Existing HTTP API

- `GET /health` → `{"status":"ok"}`
- `POST /game/start` → `GameResponse`. Optional JSON body `{"realm_id":"odyssey_island","player_name":"Explorer"}`. Omit body for legacy frontend. Other realms currently return 422 until implemented.
- `POST /game/action` → `GameResponse`. Body `{"session_id":"uuid","action":"search","target":null}`. Existing game only understands literal look/search/take/move.
- `GET /game/{session_id}` → `{"session_id":"uuid","world":PublicWorld}`.

`GameResponse`: `session_id: str`, `narration: str`, `world: PublicWorld`.
`PublicWorld`: `location_id`, `location`, `description`, `exits`, `turn`, `visible_objects`, `inventory`, `events`. Preserve these during SQL/AI work.

## Siddiq — AI module boundary

Implement these functions in an AI module; do not modify the database or game state directly:

```python
def interpret_action(player_action: str, visible_context: dict) -> ActionProposal: ...
def narrate_result(player_action: str, validated_results: list[str], visible_context: dict) -> str: ...
```

`ActionProposal` is defined in `app/models/schemas.py`. It uses `action_type`, `target`, `dialogue`, `duration_seconds`. No free-form executable Python or SQL. The current engine validates only look/search/take/move. Additional action types need explicit engine handlers before activation.

Pass ONLY `public_world(world)` plus validated outcome to the AI. Hidden, undiscovered objects must not enter the prompt. Story text cannot mutate game state. If the model fails, return a safe engine-written narration.

## Taseen — persistence/world boundary

Provide functions behind a storage adapter (exact DB tables are implementation details):

```python
def list_realms() -> list[dict]: ...
def load_realm(realm_id: str) -> dict: ...
def load_session(session_id: str) -> WorldState: ...
def save_session(session_id: str, world: WorldState) -> None: ...
def available_exits(realm_id: str, location_id: str) -> dict[str, str]: ...
def due_events(realm_id: str, game_time: str) -> list[dict]: ...
```

Persist sessions, discovered/carried object state PER SESSION, not globally. The engine owns action validation and state transitions. Future time-based events should be deterministic, validated, and processed before saving. Oracle secrets remain in local .env; never commit credentials.

## Tarik — integration responsibilities

Keep HTTP request/response shape stable, wire React to endpoints, validate player actions through the Python engine, and orchestrate AI → validation → event processing → persistence → narration. Do not assume the proposed AI/storage interfaces are implemented until teammates merge them.

## Minimal smoke tests

1. Start with no body still works.
2. Start with `odyssey_island` succeeds.
3. Unknown realm returns 422.
4. Hidden compass absent before search; visible afterward.
5. Taking a non-visible object fails.
6. Session load returns the same state.
7. AI failure cannot undo or invent state changes.

## Suggested branches

- `feature/three-page-ui`: Tarik
- `feature/ai-integration`: Siddiq
- `feature/oracle-world`: Taseen

Pull requests target `main`, coordinated by Tarik. Keep changes small.
