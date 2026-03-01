
# ======================================================================#
#                    collector.py  -  Sensor Data Ingestion             #
# ======================================================================#
# Reads BME688 CSV lines from Arduino UNO Q serial,
# maintains a rolling buffer, extracts a capture window (default 10s),
# computes simple features, and POSTs them to the backend API.
#
# Pipeline: Arduino -> collector -> backend -> frontend
# ======================================================================#


import os  # for environment variables and file checks
import time  # for timestamps and sleeping
import json  # for pretty printing / debugging
import argparse  # for CLI flags
from collections import deque  # rolling buffer
from typing import Deque, Dict, List, Optional, Tuple  # type hints

import requests  # HTTP client to talk to backend
import serial  # pyserial for Arduino serial connection


# -----------------------------
# CONFIG (env overrides)
# -----------------------------

SERIAL_PORT = os.getenv("SERIAL_PORT", "COM5")  # Windows example; change as needed
BAUD_RATE = int(os.getenv("BAUD_RATE", "115200"))  # must match Arduino Serial.begin(...)
API_BASE = os.getenv("API_BASE", "http://localhost:8000")  # your FastAPI base URL
START_COMMAND = os.getenv("START_COMMAND", "s")  # Arduino expects 's' to begin streaming

EXPECTED_FIELDS = 4  # tempC,humidity,pressure_hPa,gas_ohms

# Rolling buffer size (seconds of history to retain)
BUFFER_SECONDS = float(os.getenv("BUFFER_SECONDS", "60"))

# Where to optionally log raw data (debug)
RAW_CSV_PATH = os.getenv("RAW_CSV_PATH", "")  # set to something like "collector_raw.csv" if you want


# -----------------------------
# Helpers
# -----------------------------

def parse_csv_line(line: str) -> Optional[Tuple[float, float, float, float]]:
    """Parse one CSV line: tempC,humidity,pressure_hPa,gas_ohms -> tuple of floats."""
    try:
        parts = [p.strip() for p in line.split(",")]  # split and clean commas/spaces
        if len(parts) != EXPECTED_FIELDS:  # ensure we got exactly 4 values
            return None  # ignore malformed lines
        tempC = float(parts[0])  # temperature in Celsius
        humidity = float(parts[1])  # relative humidity %
        pressure_hPa = float(parts[2])  # pressure in hPa
        gas_ohms = float(parts[3])  # gas resistance in ohms
        return (tempC, humidity, pressure_hPa, gas_ohms)  # return typed tuple
    except Exception:
        return None  # ignore anything that can’t parse cleanly


def now_ts() -> float:
    """Current time in seconds (float)."""
    return time.time()


def purge_old(buffer: Deque[Tuple[float, Tuple[float, float, float, float]]], keep_seconds: float) -> None:
    """Remove samples older than keep_seconds from the left of the deque."""
    cutoff = now_ts() - keep_seconds  # compute cutoff timestamp
    while buffer and buffer[0][0] < cutoff:  # while oldest sample is too old
        buffer.popleft()  # drop it


def window_last_seconds(
    buffer: Deque[Tuple[float, Tuple[float, float, float, float]]],
    seconds: float
) -> List[Tuple[float, float, float, float]]:
    """Return the samples within the last `seconds` from the buffer."""
    cutoff = now_ts() - seconds  # compute capture start time
    samples: List[Tuple[float, float, float, float]] = []  # list to collect samples
    for ts, vals in buffer:  # iterate through buffer
        if ts >= cutoff:  # keep only samples inside capture window
            samples.append(vals)  # store the 4-tuple
    return samples  # return list of raw sensor tuples


def feature_stats(values: List[float]) -> Dict[str, float]:
    """Compute simple stats for a list."""
    if not values:  # guard empty list
        return {"min": 0.0, "max": 0.0, "mean": 0.0}  # safe defaults
    vmin = min(values)  # minimum
    vmax = max(values)  # maximum
    mean = sum(values) / len(values)  # average
    return {"min": float(vmin), "max": float(vmax), "mean": float(mean)}  # return floats


def extract_features(samples: List[Tuple[float, float, float, float]]) -> Dict[str, float]:
    """
    Turn raw (temp, humid, pressure, gas) samples into features.
    Keep it dead-simple for hackathon reliability.
    """
    temps = [s[0] for s in samples]  # list of tempC
    hums = [s[1] for s in samples]  # list of humidity
    press = [s[2] for s in samples]  # list of pressure
    gas = [s[3] for s in samples]  # list of gas resistance

    tf = feature_stats(temps)  # temp stats
    hf = feature_stats(hums)  # humidity stats
    pf = feature_stats(press)  # pressure stats
    gf = feature_stats(gas)  # gas stats

    features: Dict[str, float] = {}  # flat feature dict (backend-friendly)

    features["temp_mean"] = tf["mean"]  # temp mean
    features["temp_min"] = tf["min"]  # temp min
    features["temp_max"] = tf["max"]  # temp max

    features["humidity_mean"] = hf["mean"]  # humidity mean
    features["humidity_min"] = hf["min"]  # humidity min
    features["humidity_max"] = hf["max"]  # humidity max

    features["pressure_mean"] = pf["mean"]  # pressure mean
    features["pressure_min"] = pf["min"]  # pressure min
    features["pressure_max"] = pf["max"]  # pressure max

    features["gas_mean"] = gf["mean"]  # gas mean

    # Model expects this canonical name (trained feature)
    features["Sensor_Resistance_Ohms"] = gf["mean"]  # alias to gas_mean for backend/model

    features["gas_min"] = gf["min"]  # gas min
    features["gas_max"] = gf["max"]  # gas max

    features["n_samples"] = float(len(samples))  # include how many samples in window

    # Optional: simple “delta” feature for gas trend (last - first)
    if len(gas) >= 2:  # ensure enough points
        features["gas_delta"] = float(gas[-1] - gas[0])  # trend over window
    else:
        features["gas_delta"] = 0.0  # safe default

    return features  # return feature dict


def post_features_to_backend(features: Dict[str, float]) -> Dict:
    """
    POST features to backend inference endpoint.
    Backend should respond with CaptureResult-like JSON.
    """
    url = f"{API_BASE}/infer"  # endpoint for feature inference
    payload = {"features": features}  # backend contract
    r = requests.post(url, json=payload, timeout=10)  # send request
    r.raise_for_status()  # raise if 4xx/5xx
    return r.json()  # return JSON response


def maybe_append_raw_csv(samples: List[Tuple[float, float, float, float]]) -> None:
    """Optional debug logging to CSV if RAW_CSV_PATH is set."""
    if not RAW_CSV_PATH:  # if not configured
        return  # do nothing
    header_needed = not os.path.exists(RAW_CSV_PATH)  # check if file exists
    with open(RAW_CSV_PATH, "a", newline="") as f:  # open append mode
        if header_needed:  # write header once
            f.write("tempC,humidity,pressure_hPa,gas_ohms\n")  # header row
        for s in samples:  # write each sample
            f.write(f"{s[0]},{s[1]},{s[2]},{s[3]}\n")  # CSV row


# -----------------------------
# Main runtime
# -----------------------------

def run(capture_seconds: float, auto_every_seconds: float) -> None:
    """Connect to Arduino, stream data, and trigger captures."""
    print(f"[collector] SERIAL_PORT={SERIAL_PORT}")  # show port for sanity
    print(f"[collector] BAUD_RATE={BAUD_RATE}")  # show baud rate
    print(f"[collector] API_BASE={API_BASE}")  # show backend base url
    print(f"[collector] BUFFER_SECONDS={BUFFER_SECONDS}")  # show history retention
    print(f"[collector] capture_seconds={capture_seconds}")  # show window size

    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)  # open serial port
    time.sleep(2)  # give Arduino time to reset/settle

    # Handshake: tell Arduino to start streaming if needed
    if START_COMMAND:  # only if configured
        ser.write((START_COMMAND + "\n").encode("utf-8"))  # send start command
        ser.flush()  # ensure it goes out
        print(f"[collector] sent start command: {START_COMMAND!r}")  # confirm

    buffer: Deque[Tuple[float, Tuple[float, float, float, float]]] = deque()  # (timestamp, readings)
    last_capture_ts = 0.0  # last auto-capture time

    print("[collector] streaming... Ctrl+C to stop")  # operator instructions

    try:
        while True:  # loop forever
            raw = ser.readline().decode("utf-8", errors="ignore").strip()  # read one line
            parsed = parse_csv_line(raw)  # parse CSV into tuple
            if parsed is not None:  # only keep valid readings
                ts = now_ts()  # timestamp the sample
                buffer.append((ts, parsed))  # add to rolling buffer
                purge_old(buffer, BUFFER_SECONDS)  # keep buffer bounded

            # Auto capture mode (optional)
            if auto_every_seconds > 0:  # if enabled
                if now_ts() - last_capture_ts >= auto_every_seconds:  # time to capture
                    last_capture_ts = now_ts()  # update capture timestamp
                    samples = window_last_seconds(buffer, capture_seconds)  # slice window
                    if len(samples) < 2:  # not enough data yet
                        print("[collector] not enough data for capture yet")  # warn
                        continue  # skip this capture
                    maybe_append_raw_csv(samples)  # optional raw logging
                    features = extract_features(samples)  # compute features
                    try:
                        resp = post_features_to_backend(features)  # send to backend
                        print("[collector] backend response:")  # label
                        print(json.dumps(resp, indent=2))  # pretty print response
                    except Exception as e:
                        print(f"[collector] POST /infer failed: {e}")  # show failure

            time.sleep(0.01)  # tiny sleep to avoid pegging CPU

    except KeyboardInterrupt:
        print("\n[collector] stopped")  # exit message
    finally:
        try:
            ser.close()  # close serial
        except Exception:
            pass  # ignore close errors


def main() -> None:
    """CLI entrypoint."""
    p = argparse.ArgumentParser(description="Arduino BME688 collector -> backend")  # parser
    p.add_argument("--capture-seconds", type=float, default=10.0)  # capture window length
    p.add_argument("--auto-every", type=float, default=0.0)  # 0 = off, else auto capture interval
    args = p.parse_args()  # parse args
    run(capture_seconds=args.capture_seconds, auto_every_seconds=args.auto_every)  # run collector


if __name__ == "__main__":
    main()  # start program