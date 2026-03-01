from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from uuid import uuid4
from datetime import datetime, timezone

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CAPTURES: List[dict] = []

class ExternalCaptureIn(BaseModel):
    prediction: str
    confidence: Optional[float] = None
    createdAt: Optional[str] = None

@app.get("/health")
def health():
    return {"ok": True}

# Your frontend pings this. Make it exist.
@app.get("/metrics")
def metrics():
    return {
        "ok": True,
        "captures": len(CAPTURES),
    }

@app.get("/captures")
def get_captures():
    return CAPTURES

@app.post("/captures")
def post_capture(payload: ExternalCaptureIn):
    created_at = payload.createdAt or datetime.now(timezone.utc).isoformat()
    capture = {
        "id": str(uuid4()),
        "createdAt": created_at,
        "features": {},
        "prediction": payload.prediction,
        "confidence": payload.confidence,
    }
    CAPTURES.append(capture)
    return capture