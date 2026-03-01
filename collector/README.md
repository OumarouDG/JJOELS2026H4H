# COLLECTOR — Sensor Data Ingestion

##  PURPOSE
The collector connects directly to the Arduino UNO Q and streams BME688 data into the system.

This script:
- Reads serial CSV data from the board
- Maintains a rolling buffer
- Extracts 10-second capture windows
- Sends processed features to backend API

Hardware NEVER talks directly to frontend.

collector → backend → frontend

---

## 👨‍💻 WHO WORKS HERE
Branch example:
feature/collector-stream

Only hardware/data ingestion developers modify this folder.

---

## RESPONSIBILITIES
- Serial communication
- Command handshake with UNO Q
- CSV parsing
- Rolling buffer management
- Feature extraction
- POST requests to backend

---

## EXPECTED SERIAL FORMAT
tempC,humidity,pressure_hPa,gas_ohms

Streaming begins after sending command:
s

---

## FILES TO IMPLEMENT
collector.py
- serial reader
- buffer manager
- capture trigger
- backend POST client

---

## SUCCESS CONDITION
Backend receives clean capture data automatically.
