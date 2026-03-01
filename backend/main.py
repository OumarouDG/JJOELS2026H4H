from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from uuid import uuid4
from datetime import datetime, timezone
from pathlib import Path
import asyncio
import os
import time
import subprocess
import re
from collections import deque

import serial  # pyserial


# ----------------------------
# Config
# ----------------------------
SERIAL_PORT = os.getenv("SERIAL_PORT", "COM8")
SERIAL_BAUD = int(os.getenv("SERIAL_BAUD", "115200"))

RECORDINGS_DIR = Path(os.getenv("RECORDINGS_DIR", "./recordings"))
RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)

ML_DIR = Path(__file__).parent.parent / "ml"
INFER_SCRIPT = ML_DIR / "live_file_test.py"
MODEL_PATH = ML_DIR / "artifacts" / "model.joblib"

# Arduino sketch uses 's' to stream, 'p' to stop (per UnoQSketch.ino)
ARDUINO_STREAM_ON = os.getenv("ARDUINO_STREAM_ON", "s")
ARDUINO_STREAM_OFF = os.getenv("ARDUINO_STREAM_OFF", "p")

# Live buffer (for chart) during a capture only
LIVE_MAX = int(os.getenv("LIVE_MAX", "4000"))  # plenty
LIVE_STREAM = deque(maxlen=LIVE_MAX)
LIVE_LOCK = asyncio.Lock()

# Background raw buffer (sensor always streaming to keep heater warm)
RAW_MAX = int(os.getenv("RAW_MAX", "8000"))
RAW_BUFFER = deque(maxlen=RAW_MAX)
RAW_LOCK = asyncio.Lock()

CAPTURES: List[dict] = []

# only one capture at a time
recording_lock = asyncio.Lock()
is_capturing = False


# ----------------------------
# App + CORS
# ----------------------------
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ----------------------------
# Models
# ----------------------------
class ExternalCaptureIn(BaseModel):
    prediction: str
    confidence: Optional[float] = None
    createdAt: Optional[str] = None


# ----------------------------
# Serial Manager
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
        time.sleep(2.0)  # Arduino often resets on open

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

    async def flush_input(self, max_lines: int = 200):
        # Drain any buffered lines so a new capture starts "clean"
        for _ in range(max_lines):
            line = await self.read_line()
            if not line:
                break


serial_mgr = SerialManager(SERIAL_PORT, SERIAL_BAUD)


def _parse_sensor_line(line: str) -> Optional[Dict[str, Any]]:
    """
    UnoQSketch prints: tempC,humidity,pressure_hPa,gas_ohms
    plus header and text lines. We keep gas_ohms primarily.
    """
    if not line:
        return None

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
    """
    live_file_test.py expects a single column:
      Sensor_Resistance_Ohms
    """
    header = "Sensor_Resistance_Ohms\n"
    lines = [str(r["gas_ohms"]) for r in rows]
    csv_path.write_text(header + "\n".join(lines) + "\n", encoding="utf-8")


async def _run_inference(csv_path: Path) -> Dict[str, Any]:
    """
    live_file_test.py prints human text like:
      Prediction: LOW_LOAD | probs: LOW_LOAD=0.997, HIGH_LOAD=0.003
      Window mean Sensor_Resistance_Ohms: 130691.91

    We parse it into structured fields.
    """
    cmd = [
        "python",
        str(INFER_SCRIPT),
        "--model",
        str(MODEL_PATH),
        "--data",
        str(csv_path),
    ]

    def _run():
        p = subprocess.run(cmd, capture_output=True, text=True)
        out = (p.stdout or "").strip()
        err = (p.stderr or "").strip()

        if p.returncode != 0:
            raise RuntimeError(err or out or f"Inference exited {p.returncode}")

        pred = None
        probs: Dict[str, float] = {}
        mean_val = None

        for line in out.splitlines():
            if line.startswith("Prediction:"):
                m = re.search(r"Prediction:\s*([A-Z0-9_]+)", line)
                if m:
                    pred = m.group(1)

                m2 = re.search(r"probs:\s*(.+)$", line)
                if m2:
                    for chunk in m2.group(1).split(","):
                        chunk = chunk.strip()
                        if "=" in chunk:
                            k, v = chunk.split("=", 1)
                            k = k.strip()
                            try:
                                probs[k] = float(v.strip())
                            except ValueError:
                                pass

            if "Window mean Sensor_Resistance_Ohms" in line:
                m3 = re.search(r":\s*([0-9]+(?:\.[0-9]+)?)", line)
                if m3:
                    mean_val = float(m3.group(1))

        confidence = None
        if pred and pred in probs:
            confidence = probs[pred]
        elif probs:
            best = max(probs.items(), key=lambda kv: kv[1])
            pred, confidence = best[0], best[1]

        if not pred:
            raise RuntimeError(f"Could not parse prediction from output:\n{out}")

        return {
            "label": pred,
            "confidence": confidence,
            "features": {
                "window_mean_ohms": mean_val,
                **{f"prob_{k}": v for k, v in probs.items()},
            },
            "raw": out,
        }

    return await asyncio.to_thread(_run)


async def serial_reader_loop():
    """
    Background reader: keeps the sensor streaming and buffers the most recent
    samples in RAW_BUFFER. This keeps the MOX heater "warmed up" continuously.
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

            async with RAW_LOCK:
                RAW_BUFFER.append(sample)

        except Exception:
            # Don't kill the server if serial hiccups.
            await asyncio.sleep(0.25)


# ----------------------------
# Endpoints
# ----------------------------
@app.get("/health")
def health():
    return {
        "ok": True,
        "serial_port": SERIAL_PORT,
        "serial_open": serial_mgr.is_open(),
        "capturing": is_capturing,
        "live_buffered": len(LIVE_STREAM),
        "raw_buffered": len(RAW_BUFFER),
        "captures": len(CAPTURES),
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


@app.post("/capture")
def post_capture_alias(payload: ExternalCaptureIn):
    return post_capture(payload)


@app.get("/live")
async def live(tail: int = 120):
    """
    Live data for the chart: only the current capture window.
    (Sensor itself may still be streaming in background; we don't expose that.)
    """
    tail = max(1, min(int(tail), 2000))
    async with LIVE_LOCK:
        data = list(LIVE_STREAM)[-tail:]
    return {"samples": data, "capturing": is_capturing}


@app.post("/record")
async def record(duration_ms: int = 5000, expected_samples: int = 25):
    """
    Sensor streams continuously in the background (heater warm).
    This endpoint captures a clean window starting at button-press time:
      - take samples appended to RAW_BUFFER after start_idx
      - mirror them into LIVE_STREAM so the graph animates
      - write only that window to CSV
      - run inference
    """
    global is_capturing

    duration_ms = max(500, min(int(duration_ms), 60000))
    expected_samples = max(1, min(int(expected_samples), 5000))

    if not serial_mgr.is_open():
        return {"ok": False, "error": f"Serial not connected on {SERIAL_PORT}"}

    async with recording_lock:
        is_capturing = True

        # Clear session live buffer so the chart shows only this session
        async with LIVE_LOCK:
            LIVE_STREAM.clear()

        # Mark where "new" samples begin
        async with RAW_LOCK:
            start_idx = len(RAW_BUFFER)

        t_end = time.time() + (duration_ms / 1000.0)
        window: List[Dict[str, Any]] = []

        # Collect until time is up OR we have enough samples
        while time.time() < t_end:
            await asyncio.sleep(0.01)

            async with RAW_LOCK:
                new_samples = list(RAW_BUFFER)[start_idx:]

            window = new_samples

            # Update LIVE_STREAM so the chart animates in near-real-time
            async with LIVE_LOCK:
                LIVE_STREAM.clear()
                LIVE_STREAM.extend(window[-120:])

            if len(window) >= expected_samples:
                break

        is_capturing = False

        # Write a fresh session CSV every time
        ts = int(time.time() * 1000)
        csv_path = RECORDINGS_DIR / f"session_{ts}.csv"
        _write_csv(csv_path, window)

        # Run inference; even if it fails, return something useful
        try:
            result = await _run_inference(csv_path)
            capture = {
                "id": str(uuid4()),
                "createdAt": datetime.now(timezone.utc).isoformat(),
                "features": result.get("features") or {},
                "prediction": result.get("label") or "unknown",
                "confidence": result.get("confidence"),
            }
            CAPTURES.append(capture)
            return {
                "ok": True,
                "capture": capture,
                "csv": str(csv_path),
                "rows": len(window),
            }
        except Exception as e:
            capture = {
                "id": str(uuid4()),
                "createdAt": datetime.now(timezone.utc).isoformat(),
                "features": {"csv_rows": len(window), "error": str(e)},
                "prediction": "ERROR",
                "confidence": 0.0,
            }
            CAPTURES.append(capture)
            return {
                "ok": True,
                "capture": capture,
                "csv": str(csv_path),
                "rows": len(window),
            }


@app.on_event("startup")
async def _startup():
    print("[startup] routes:", [getattr(r, "path", None) for r in app.routes])
    try:
        serial_mgr.open()
        print(f"[serial] opened {SERIAL_PORT} @ {SERIAL_BAUD}")

        # Keep heater warm: stream continuously in background
        await serial_mgr.write_line(f"{ARDUINO_STREAM_ON}\n")
        print("[serial] stream ON (background warmup)")

        asyncio.create_task(serial_reader_loop())
        print("[serial] reader loop started")

    except Exception as e:
        print(f"[serial] FAILED to open {SERIAL_PORT}: {e}")


@app.on_event("shutdown")
def _shutdown():
    try:
        # Optional: stop streaming on shutdown
        try:
            if serial_mgr.is_open():
                # best-effort
                asyncio.run(serial_mgr.write_line(f"{ARDUINO_STREAM_OFF}\n"))
        except Exception:
            pass
        serial_mgr.close()
    except Exception:
        pass