# Neural Nexus — MYTHOS

HackTN26 prototype: an interactive, child-friendly mythology story game.

**Architecture:** The AI proposes narration; the Python engine enforces visibility, movement and inventory rules. Hidden objects are not sent to the AI context before discovery.

## Run the backend

```powershell
cd backend
copy .env.example .env
uv sync
uv run uvicorn app.main:app --reload
```

API: http://127.0.0.1:8000/docs

Without an `OPENAI_API_KEY`, a deterministic demo narrator is used.

## Run the frontend

```powershell
cd frontend
npm install
npm run dev
```

Visit http://localhost:5173

## Test

```powershell
cd backend
uv run pytest -q
```

## Collaboration

Create branches such as `feature/story-engine`, `feature/ui`, `feature/story-content`; open pull requests into `main`. Never commit secrets.

## Hackathon scope

One story: The Odyssey-inspired island adventure. Explore a clearing, search for a hidden compass, collect it, and travel to a beach. Child-friendly original prose, not a verbatim adaptation.

See [architecture](docs/ARCHITECTURE.md), [task breakdown](docs/TASKS.md).
