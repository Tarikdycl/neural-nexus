# Neural Nexus — The Last Archive

A chat-driven historical investigation game: investigate a historical crisis for 60 seconds, defend your testimony before the AI Archivist for 90 seconds, and review the verdict.

## Current historical cases

- **The Tea in the Harbor — Boston, 1773** (playable)
- **Storming the Bastille — Paris, 1789** (playable after one-time Oracle seed)
- **The Wall Opens — Berlin, 1989** (artwork / coming soon)

Original mythology prototypes remain in the repository, but are not linked from the current landing page.

## Run locally

**Backend** (Windows / Oracle Autonomous Database):

1. Configure backend-tests/.env and the ignored backend-tests/.secrets Oracle Wallet / OCI config.
2. Install backend-tests/requirements.txt in your environment.
3. Set the Oracle Instant Client location in ORACLE_CLIENT_DIR.
4. Run `cd backend-tests` then `python -m uvicorn app.archive_server:app --port 8002`.

**Frontend**: `cd frontend`, `npm install`, `npm run dev`.

The Vite proxy forwards `/archive` to port 8002. Confirm `/archive/health` reports `{"ok":true,"store":"oracle"}`.

### Paris scenario setup (run once)

The Oracle schema already has NN_WORLDS, NN_SCENARIOS, NN_SESSIONS and NN_EVENTS. Run **backend-tests/sql/archive_paris_seed.sql** in the ADMIN SQL Worksheet once so the Paris scenario can satisfy the NN_SESSIONS scenario foreign key. It copies the world_id of the existing Boston scenario, without changing other tables. The file is idempotent and safe to run again.

## Saved Visits / previous cases

**Saved Visits** opens from the historical mission selection screen. The existing Oracle NN_SESSIONS + NN_EVENTS tables provide case history and retained decisions; no new history table is needed.

API:

- `POST /archive/start` with `{"nickname":"Chrono Agent","scenario_id":"storming_bastille_1789"}`
- `POST /archive/action`, `POST /archive/extract`, `POST /archive/court`, `POST /archive/verdict`, `POST /archive/save`
- `GET /archive/state/{session_id}`, `GET /archive/saves`, `GET /archive/saves/{session_id}`

Each session saves discovered evidence, player actions, NPC replies, testimony, Court questions, answers and provisional verdicts. Older sessions may lack NPC reply events. **Saved Visits is a history viewer, not a pause/resume feature.** Scores are provisional and out of 100: 60 evidence points (20 for each unique clue) and 40 Court points (historical concept coverage plus a substantive answer). The 60/90-second server timers continue to run independently.

**Privacy / publishing warning:** these local prototype history APIs do not yet authenticate users or isolate one player's saved cases from another. Add login/authorization and ownership checks before publicly exposing saved sessions.

## Architecture notes

- `backend-tests/app/archive_scenarios.py`: authored facts, actions and deterministic historical concept rubrics for each scenario.
- `backend-tests/app/archive_server.py`: Oracle-persisted event API, sessions and Saved Visits.
- `backend-tests/app/archive_logic.py`: OCI narration (no game-state authority).
- `frontend/src/pages/LastArchive.jsx`: mission selection, chat, Court, review and history screens.

AI narration may vary; actions, evidence and points are validated by Python. Verdicts are **provisional concept-coverage checks, not authenticated historical-accuracy certification**. Historical facts should be independently source-checked before an educational production release.

## Tests

`cd backend-tests` and run `python -m pytest tests/test_archive_scenarios.py -q`.

Existing Monkey King and Odyssey subsystems remain available for the team's separate work.
