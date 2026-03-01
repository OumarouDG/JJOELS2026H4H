from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

import asyncio
import csv
import joblib
import os
import serial
import threading
import time
import subprocess

from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# =============================================================================
# FastAPI Backend — Air Event Detector
# Real-time Arduino → Web → ML pipeline
# =============================================================================

app = FastAPI(title="Air-Event Detector Backend", version="FINAL")

# -------------------------------------------------------------------
# SERIAL CONFIG
# -------------------------------------------------------------------
SERIAL_PORT = "COM8"   # CHANGE IF NEEDED
BAUD_RATE = 115200

ser: Optional[serial.Serial] = None
recording = False
buffer: List[list] = []
record_lock = threading.Lock()

# -------------------------------------------------------------------
# WEBSOCKET CLIENTS
# -------------------------------------------------------------------
active_websockets: List[WebSocket] = []


async def broadcast_async(data: dict):
    dead = []
    for ws in active_websockets:
        try:
            await ws.send_json(data)
        except:
            dead.append(ws)

    for d in dead:
        if d in active_websockets:
            active_websockets.remove(d)


def broadcast(data: dict):
    loop = asyncio.get_event_loop()
    loop.create_task(broadcast_async(data))


# -------------------------------------------------------------------
# STARTUP
# -------------------------------------------------------------------
@app.on_event("startup")
def startup_event():
    global ser
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        print(f"✅ Connected to Arduino on {SERIAL_PORT}")
    except Exception as e:
        print("⚠ Serial connection failed:", e)


# -------------------------------------------------------------------
# WEBSOCKET ENDPOINT
# -------------------------------------------------------------------
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_websockets.append(websocket)

    try:
        while True:
            await websocket.receive_text()
    except:
        if websocket in active_websockets:
            active_websockets.remove(websocket)


# -------------------------------------------------------------------
# SERIAL RECORDING THREAD
# -------------------------------------------------------------------
def read_serial_for_seconds(seconds: int):

    global buffer, recording

    with record_lock:

        if ser is None:
            print("❌ Serial not initialized")
            return

        buffer = []
        recording = True
        start_time = time.time()

        try:
            ser.write(b"START\n")

            while time.time() - start_time < seconds:

                line = ser.readline().decode(errors="ignore").strip()

                if not line:
                    continue

                parts = line.split(",")

                if len(parts) != 4:
                    continue

                data = [float(p) for p in parts]
                buffer.append(data)

                broadcast({
                    "temp": data[0],
                    "humidity": data[1],
                    "pressure": data[2],
                    "gas": data[3],
                })

        except Exception as e:
            print("Serial error:", e)

        finally:
            recording = False


# -------------------------------------------------------------------
# CORS
# -------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------------------------
# PATHS / ARTIFACTS
# -------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parent.parent
ARTIFACTS_DIR = ROOT_DIR / "ml" / "artifacts"
MODEL_PATH = ARTIFACTS_DIR / "model.joblib"
METRICS_PATH = ARTIFACTS_DIR / "metrics.json"

CAPTURES: List[dict] = []
LAST_FEATURES: Optional[Dict[str, float]] = None

_model = None
_metrics_cache: Optional[dict] = None


def _utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


# -------------------------------------------------------------------
# MODEL LOADING
# -------------------------------------------------------------------
def _load_model():
    global _model
    if _model is None:
        try:
            _model = joblib.load(MODEL_PATH)
        except Exception as e:
            _model = {"__fallback__": True, "error": repr(e)}
    return _model


def _load_metrics():
    global _metrics_cache
    if _metrics_cache is None:
        if METRICS_PATH.exists():
            import json
            _metrics_cache = json.loads(METRICS_PATH.read_text())
        else:
            _metrics_cache = {"accuracy": 0.0, "labels": []}
    return _metrics_cache


# -------------------------------------------------------------------
# INFERENCE
# -------------------------------------------------------------------
def _predict_from_features(features: Dict[str, float]):

    model = _load_model()

    ohms = float(
        features.get("Sensor_Resistance_Ohms")
        or features.get("gas_mean")
        or features.get("gas")
    )

    if isinstance(model, dict) and model.get("__fallback__"):
        labels = _load_metrics().get("labels", ["LOW", "HIGH"])
        threshold = 50000
        label = labels[-1] if ohms >= threshold else labels[0]
        return label, 0.5

    X = [[ohms]]
    pred = model.predict(X)[0]

    confidence = 0.0
    if hasattr(model, "predict_proba"):
        confidence = float(max(model.predict_proba(X)[0]))

    return str(pred), confidence


# -------------------------------------------------------------------
# MODELS
# -------------------------------------------------------------------
class InferIn(BaseModel):
    features: Dict[str, float] = Field(default_factory=dict)


# -------------------------------------------------------------------
# ROUTES
# -------------------------------------------------------------------
@app.get("/health")
def health():
    return {"ok": True}


@app.post("/record")
def record(seconds: int = 5):

    if recording:
        raise HTTPException(400, "Recording already running")

    thread = threading.Thread(
        target=read_serial_for_seconds,
        args=(seconds,),
    )

    thread.start()
    thread.join()

    filename = f"capture_{int(time.time())}.csv"

    with open(filename, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["temp", "humidity", "pressure", "gas"])
        writer.writerows(buffer)

    result = subprocess.run(
        ["python", "../ml/model.py", filename],
        capture_output=True,
        text=True,
    )

    prediction = result.stdout.strip()

    os.remove(filename)

    broadcast({"prediction": prediction})

    return {
        "samples": len(buffer),
        "prediction": prediction,
    }


@app.post("/infer")
def infer(payload: InferIn):

    if not payload.features:
        raise HTTPException(422, "features required")

    label, confidence = _predict_from_features(payload.features)

    capture = {
        "id": str(uuid4()),
        "createdAt": _utc_now_iso(),
        "features": payload.features,
        "prediction": label,
        "confidence": confidence,
    }

    CAPTURES.append(capture)
    if len(CAPTURES) > 500:
        del CAPTURES[:-500]

    return capture