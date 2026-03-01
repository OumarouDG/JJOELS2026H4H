from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from uuid import uuid4
from datetime import datetime, timezone
from pathlib import Path
import asyncio
import json
import os
import time
import subprocess
from collections import deque

import serial  # pyserial


# ----------------------------
# Config
# ----------------------------
SERIAL_PORT = os.getenv("SERIAL_PORT", "COM8")
SERIAL_BAUD = int(os.getenv("SERIAL_BAUD", "115200"))
RECORDINGS_DIR = Path(os.getenv("RECORDINGS_DIR", "./recordings"))
RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)

# infer.py should print JSON to stdout, like: {"label":"...", "confidence":0.87, "features":{...}}
from pathlib import Path

ML_DIR = Path(__file__).parent.parent / "ml"
MODEL_PATH = ML_DIR / "artifacts/model.joblib"   # change if your model file has a different name
INFER_SCRIPT = ML_DIR / "live_file_test.py"

INFER_CMD = [
    "python",
    str(INFER_SCRIPT),
    "--model",
    str(MODEL_PATH),
    "--data",
]

# Arduino sketch uses 's' to stream, 'p' to stop (per UnoQSketch.ino)
ARDUINO_STREAM_ON = os.getenv("ARDUINO_STREAM_ON", "s")
ARDUINO_STREAM_OFF = os.getenv("ARDUINO_STREAM_OFF", "p")


# ----------------------------
# App + CORS
# ----------------------------
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ----------------------------
# In-memory state
# ----------------------------
CAPTURES: List[dict] = []

# ring buffer of live samples
SAMPLES_MAX = int(os.getenv("SAMPLES_MAX", "4000"))  # plenty for a few minutes @ 5Hz
SAMPLES = deque(maxlen=SAMPLES_MAX)
SAMPLES_LOCK = asyncio.Lock()

# protect /record from overlapping sessions
recording_lock = asyncio.Lock()


# ----------------------------
# Models
# ----------------------------
class ExternalCaptureIn(BaseModel):
    prediction: str
    confidence: Optional[float] = None
    createdAt: Optional[str] = None


# ----------------------------
# Helpers
# ----------------------------
class SerialManager:
    def __init__(self, port: str, baud: int):
        self.port_name = port
        self.baud = baud
        self.ser: Optional[serial.Serial] = None
        self.write_lock = asyncio.Lock()

    def is_open(self) -> bool:
        return self.ser is not None and self.ser.is_open

    def open(self):
        self.ser = serial.Serial(self.port_name, self.baud, timeout=0.2)
        # Arduino boards often reset on open
        time.sleep(2.0)

    def close(self):
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
        except Exception:
            pass

    async def write_line(self, line: str):
        async with self.write_lock:
            if not self.is_open():
                raise RuntimeError("Serial is not open")
            await asyncio.to_thread(self.ser.write, line.encode("utf-8"))

    async def read_line(self) -> Optional[str]:
        if not self.is_open():
            return None

        def _read():
            raw = self.ser.readline()
            if not raw:
                return None
            return raw.decode("utf-8", errors="ignore").strip()

        return await asyncio.to_thread(_read)


serial_mgr = SerialManager(SERIAL_PORT, SERIAL_BAUD)


def _parse_sensor_line(line: str) -> Optional[Dict[str, Any]]:
    """
    Arduino (UnoQSketch.ino) prints:
      "tempC,humidity,pressure_hPa,gas_ohms"
    plus some text lines like:
      "BME688 ready..."
      "OK: streaming ON"
      header line: "tempC,humidity,pressure_hPa,gas_ohms"

    We return frontend-friendly keys:
      { t, tempC, humidity, pressure_hPa, gas_ohms }
    """
    if not line:
        return None

    # ignore obvious non-data lines
    if line.startswith("BME") or line.startswith("OK:") or line.startswith("Commands:"):
        return None
    if line.strip() == "tempC,humidity,pressure_hPa,gas_ohms":
        return None

    parts = line.split(",")
    if len(parts) != 4:
        return None

    try:
        tempC = float(parts[0])
        humidity = float(parts[1])
        pressure_hPa = float(parts[2])
        gas_ohms = float(parts[3])
    except ValueError:
        return None

    return {
        "t": int(time.time() * 1000),
        "tempC": tempC,
        "humidity": humidity,
        "pressure_hPa": pressure_hPa,
        "gas_ohms": gas_ohms,
    }


def _write_csv(csv_path: Path, rows: List[Dict[str, Any]]):
    header = "Sensor_Resistance_Ohms\n"
    lines = [str(r["gas_ohms"]) for r in rows]
    csv_path.write_text(header + "\n".join(lines) + "\n", encoding="utf-8")


async def _run_inference(csv_path: Path) -> Dict[str, Any]:
    cmd = INFER_CMD + [str(csv_path)]

    def _run():
        p = subprocess.run(cmd, capture_output=True, text=True)
        if p.returncode != 0:
            raise RuntimeError(p.stderr.strip() or f"Inference exited {p.returncode}")
        try:
            return json.loads(p.stdout)
        except json.JSONDecodeError:
            raise RuntimeError(f"infer.py did not output valid JSON:\n{p.stdout}")

    return await asyncio.to_thread(_run)


async def serial_reader_loop():
    """
    Always-on serial reader that keeps SAMPLES filled.
    This is what makes the whole thing stable: frontend polls HTTP,
    backend just buffers data.
    """
    while True:
        try:
            line = await serial_mgr.read_line()
            if not line:
                await asyncio.sleep(0.002)
                continue

            sample = _parse_sensor_line(line)
            if not sample:
                continue

            async with SAMPLES_LOCK:
                SAMPLES.append(sample)

        except Exception:
            # If serial dies, don't take down the web server.
            await asyncio.sleep(0.25)


# ----------------------------
# REST endpoints
# ----------------------------
@app.get("/health")
def health():
    return {
        "ok": True,
        "serial_port": SERIAL_PORT,
        "serial_open": serial_mgr.is_open(),
        "samples_buffered": len(SAMPLES),
    }


@app.get("/metrics")
def metrics():
    return {"ok": True, "captures": len(CAPTURES)}


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


# keep the alias, because humans love inconsistency
@app.post("/capture")
def post_capture_alias(payload: ExternalCaptureIn):
    return post_capture(payload)


@app.get("/live")
async def live(tail: int = 120):
    """
    Polling endpoint for the live chart.
    tail=120 gives you last ~24 seconds at 5Hz.
    """
    tail = max(1, min(int(tail), 2000))
    async with SAMPLES_LOCK:
        data = list(SAMPLES)[-tail:]
    return {"samples": data}


@app.post("/record")
async def record(duration_ms: int = 5000):
    """
    No WebSocket. No background task.
    This blocks for duration_ms, then returns the capture result.
    """
    duration_ms = max(500, min(int(duration_ms), 60000))

    if not serial_mgr.is_open():
        return {"ok": False, "error": f"Serial not connected on {SERIAL_PORT}"}

    async with recording_lock:
        start_t = int(time.time() * 1000)
        await asyncio.sleep(duration_ms / 1000.0)
        end_t = int(time.time() * 1000)

        async with SAMPLES_LOCK:
            window = [s for s in SAMPLES if start_t <= s["t"] <= end_t]

        ts = int(time.time() * 1000)
        csv_path = RECORDINGS_DIR / f"session_{ts}.csv"
        _write_csv(csv_path, window)

        try:
            result = await _run_inference(csv_path)
            capture = {
                "id": str(uuid4()),
                "createdAt": datetime.now(timezone.utc).isoformat(),
                "window": window,  # optional, UI can ignore
                "features": result.get("features") or {"csv_rows": len(window)},
                "prediction": result.get("label") or result.get("prediction") or "unknown",
                "confidence": result.get("confidence"),
            }
            CAPTURES.append(capture)
            return {"ok": True, "capture": capture, "csv": str(csv_path)}
        except Exception as e:
            return {"ok": False, "error": str(e), "csv": str(csv_path)}


# ----------------------------
# Startup / Shutdown
# ----------------------------
@app.on_event("startup")
async def _startup():
    print("[startup] routes:", [getattr(r, "path", None) for r in app.routes])
    try:
        serial_mgr.open()
        print(f"[serial] opened {SERIAL_PORT} @ {SERIAL_BAUD}")

        # start Arduino streaming (matches UnoQSketch.ino)
        await serial_mgr.write_line(f"{ARDUINO_STREAM_ON}\n")
        print("[serial] sent stream ON")

        asyncio.create_task(serial_reader_loop())
        print("[serial] reader loop started")

    except Exception as e:
        print(f"[serial] FAILED to open {SERIAL_PORT}: {e}")


@app.on_event("shutdown")
def _shutdown():
    try:
        serial_mgr.close()
    except Exception:
        pass