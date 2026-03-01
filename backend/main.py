from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any, Tuple
from uuid import uuid4
from datetime import datetime, timezone
from pathlib import Path
import asyncio
import json
import os
import time
import subprocess
from fastapi import BackgroundTasks

import serial  # pyserial


# ----------------------------
# Config
# ----------------------------
SERIAL_PORT = os.getenv("SERIAL_PORT", "COM8")
SERIAL_BAUD = int(os.getenv("SERIAL_BAUD", "115200"))
RECORDINGS_DIR = Path(os.getenv("RECORDINGS_DIR", "./recordings"))
RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)

# Your inference command. Change infer.py path if needed.
# Example default expects: python infer.py --csv <path>
INFER_CMD = os.getenv("INFER_CMD", "python infer.py --csv").split()

# If your Arduino sketch uses simple commands instead of START/STOP:
ARDUINO_START_CMD = os.getenv("ARDUINO_START_CMD", "START")  # "START" or "s"
ARDUINO_STOP_CMD = os.getenv("ARDUINO_STOP_CMD", "STOP")     # "STOP" or "p"


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

CAPTURES: List[dict] = []


class ExternalCaptureIn(BaseModel):
    prediction: str
    confidence: Optional[float] = None
    createdAt: Optional[str] = None


# ----------------------------
# REST endpoints
# ----------------------------
@app.get("/health")
def health():
    return {"ok": True}


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


# Your frontend calls POST /capture (singular), so provide an alias.
@app.post("/capture")
def post_capture_alias(payload: ExternalCaptureIn):
    return post_capture(payload)

@app.post("/record")
async def start_record(background_tasks: BackgroundTasks, duration_ms: int = 5000):
    # kick off recording and streaming; response returns immediately
    background_tasks.add_task(record_session, duration_ms)
    return {"ok": True, "started": True, "duration_ms": duration_ms}


# ----------------------------
# Serial + WebSocket bridge
# ----------------------------
class Hub:
    """Tracks connected WebSocket clients and broadcasts messages."""
    def __init__(self):
        self.clients: List[WebSocket] = []
        self.lock = asyncio.Lock()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        async with self.lock:
            self.clients.append(ws)

    async def disconnect(self, ws: WebSocket):
        async with self.lock:
            if ws in self.clients:
                self.clients.remove(ws)

    async def broadcast(self, message: Dict[str, Any]):
        payload = json.dumps(message)
        async with self.lock:
            clients = list(self.clients)
        for ws in clients:
            try:
                await ws.send_text(payload)
            except Exception:
                pass


hub = Hub()


class SerialManager:
    """Owns the serial port; provides async-friendly read/write."""
    def __init__(self, port: str, baud: int):
        self.port_name = port
        self.baud = baud
        self.ser: Optional[serial.Serial] = None
        self.write_lock = asyncio.Lock()

    def is_open(self) -> bool:
        return self.ser is not None and self.ser.is_open

    def open(self):
        # timeout so readline doesn't block forever
        self.ser = serial.Serial(self.port_name, self.baud, timeout=0.2)
        # Many Arduinos reset on serial open; give it a moment
        time.sleep(2.0)

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

# Guard so you don't start 6 recordings at once
recording_lock = asyncio.Lock()


def _write_csv(csv_path: Path, rows: List[Dict[str, Any]]):
    header = "ms,gas_ohms,temp_c,hum_pct,press_hpa\n"
    lines = [
        f"{r['ms']},{r['gas_ohms']},{r['temp_c']},{r['hum_pct']},{r['press_hpa']}"
        for r in rows
    ]
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


def _parse_sensor_line(line: str) -> Optional[Dict[str, Any]]:
    """
    Accepts TWO formats:
    1) "DATA,ms,gas,temp,hum,press"
    2) "temp,hum,press,gas"   (common Arduino CSV print for BME688)
       (and we synthesize ms as epoch ms)
    Returns dict with keys: ms, gas_ohms, temp_c, hum_pct, press_hpa
    """
    if not line:
        return None

    # Format 1
    if line.startswith("DATA,"):
        parts = line.split(",")
        if len(parts) >= 6:
            try:
                return {
                    "ms": int(parts[1]),
                    "gas_ohms": float(parts[2]),
                    "temp_c": float(parts[3]),
                    "hum_pct": float(parts[4]),
                    "press_hpa": float(parts[5]),
                }
            except ValueError:
                return None

    # Format 2 (temp,hum,press,gas)
    parts = line.split(",")
    if len(parts) == 4:
        try:
            temp_c = float(parts[0])
            hum_pct = float(parts[1])
            press_hpa = float(parts[2])
            gas_ohms = float(parts[3])
            return {
                "ms": int(time.time() * 1000),
                "gas_ohms": gas_ohms,
                "temp_c": temp_c,
                "hum_pct": hum_pct,
                "press_hpa": press_hpa,
            }
        except ValueError:
            return None

    return None


async def _arduino_start(duration_ms: int):
    """
    Supports two Arduino command styles:
    - START,<duration_ms>  (if ARDUINO_START_CMD == "START")
    - s                   (if ARDUINO_START_CMD == "s")
    """
    if ARDUINO_START_CMD.lower() == "s":
        await serial_mgr.write_line("s\n")
    else:
        await serial_mgr.write_line(f"START,{duration_ms}\n")


async def _arduino_stop():
    if ARDUINO_STOP_CMD.lower() == "p":
        await serial_mgr.write_line("p\n")
    else:
        await serial_mgr.write_line("STOP\n")


async def record_session(duration_ms: int = 5000):
    """
    Streams points live, buffers for duration_ms, saves CSV, runs inference.
    Accepts both Arduino output formats via _parse_sensor_line().
    """
    async with recording_lock:
        if not serial_mgr.is_open():
            await hub.broadcast({"type": "error", "error": "Serial not connected"})
            return

        await hub.broadcast({"type": "record_ack", "duration_ms": duration_ms})
        await _arduino_start(duration_ms)

        rows: List[Dict[str, Any]] = []
        deadline = time.time() + (duration_ms / 1000.0)

        while time.time() < deadline:
            line = await serial_mgr.read_line()
            if not line:
                await asyncio.sleep(0.001)
                continue

            # Some sketches print DONE, some don't. If they do, respect it.
            if line.strip().upper() == "DONE":
                break

            point = _parse_sensor_line(line)
            if not point:
                continue

            rows.append(point)
            await hub.broadcast({"type": "data", "sample": point})

        await _arduino_stop()

        ts = int(time.time() * 1000)
        csv_path = RECORDINGS_DIR / f"session_{ts}.csv"
        _write_csv(csv_path, rows)
        await hub.broadcast({"type": "record_done", "csv": str(csv_path), "n": len(rows)})

        try:
            result = await _run_inference(csv_path)
            await hub.broadcast({"type": "inference_result", "result": result})

            capture = {
                "id": str(uuid4()),
                "createdAt": datetime.now(timezone.utc).isoformat(),
                "features": {"csv": str(csv_path), "n": len(rows)},
                "prediction": result.get("label") or result.get("prediction") or "unknown",
                "confidence": result.get("confidence"),
            }
            CAPTURES.append(capture)
            await hub.broadcast({"type": "capture_saved", "capture": capture})
        except Exception as e:
            await hub.broadcast({"type": "inference_error", "error": str(e)})


# ----------------------------
# Startup: don't die if COM8 is busy
# ----------------------------
@app.on_event("startup")
def _startup():
    # print routes so we can confirm /ws exists in the running app
    print("[routes]", [getattr(r, "path", None) for r in app.routes])

    try:
        serial_mgr.open()
        print(f"[serial] opened {SERIAL_PORT} @ {SERIAL_BAUD}")
    except Exception as e:
        # server still runs; UI can show error and you can restart after freeing COM port
        print(f"[serial] FAILED to open {SERIAL_PORT}: {e}")


# ----------------------------
# WebSocket endpoint
# ----------------------------
@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await hub.connect(ws)
    try:
        await ws.send_text(json.dumps({"type": "hello", "serial_port": SERIAL_PORT, "serial_open": serial_mgr.is_open()}))

        while True:
            raw = await ws.receive_text()
            msg = json.loads(raw)

            # Debug echo support (useful to prove WS is working)
            if msg.get("type") == "ping":
                await ws.send_text(json.dumps({"type": "pong"}))
                continue

            if msg.get("type") == "record_start":
                duration_ms = int(msg.get("duration_ms", 5000))
                asyncio.create_task(record_session(duration_ms))

            elif msg.get("type") == "record_stop":
                if serial_mgr.is_open():
                    await _arduino_stop()

    except WebSocketDisconnect:
        pass
    finally:
        await hub.disconnect(ws)