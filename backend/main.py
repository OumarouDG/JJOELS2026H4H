
from pydantic import BaseModel
from typing import Optional, List
from uuid import uuid4
from datetime import datetime, timezone

# In-memory store for hackathon speed (replace with SQLite later if you want)
CAPTURES: List[dict] = []

class ExternalCaptureIn(BaseModel):
    prediction: str
    confidence: Optional[float] = None
    createdAt: Optional[str] = None

@app.post("/capture_external")
def capture_external(payload: ExternalCaptureIn):
    created_at = payload.createdAt
    if not created_at:
        created_at = datetime.now(timezone.utc).isoformat()

    capture = {
        "id": str(uuid4()),
        "createdAt": created_at,
        "features": {},  # empty because inference is on-device
        "prediction": payload.prediction,
        "confidence": payload.confidence,
    }

    CAPTURES.append(capture)
    return capture

@app.get("/captures")
def get_captures():
    return CAPTURES