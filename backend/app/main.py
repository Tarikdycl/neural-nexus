from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.game import router

app = FastAPI(title="Neural Nexus — MYTHOS API")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(router)

@app.get("/health")
def health():
    return {"status": "ok"}
