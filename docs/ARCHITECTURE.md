# Engine rules

- A session owns its own authoritative world state (in-memory for MVP; restart clears sessions).
- Objects have `hidden` and `discovered` flags. The narrator only receives the results of `visible_objects()`.
- `look`, `search`, `take`, and `move` are engine-handled actions with allowlists. The API never executes generated code.
- A narrative model may rephrase **validated outcomes** but cannot add objects, modify inventory, or move the player.
- Never send secret objects in the model prompt before discovery. Do not trust model output as state.
- Future: SQLite/PostgreSQL persistence, proper moderated LLM, configurable stories, user accounts, teacher dashboards.
