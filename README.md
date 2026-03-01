# JJOELS2026H4H

## Final Tech Stack

---

## Hardware Layer
- **Sensor:** BME688 (I2C)  
- **Controller:** Arduino UNO Q MCU reads sensor  

---

## Data Ingestion
- **Python Serial Collector (local):**
  - Reads Serial stream (CSV)
  - Maintains a rolling buffer
  - On “Capture 10s” request, extracts the last N seconds
  - Computes features + posts to backend

- **Libraries:**
  - pyserial
  - numpy
  - time
  - collections

---

## Backend (API + ML)
- **Framework:** FastAPI (Python)  
- **ML / Data:** scikit-learn, pandas, numpy, joblib  
- **Storage:** SQLite (or JSON files if you’re truly sprinting)  
- **Artifacts:** model.joblib, metrics.json, optional confusion_matrix.png  

### Key endpoints (minimum):
- `POST /train`  
  Runs training on public VOC dataset or loads pre-trained artifact

- `GET /metrics`  
  Returns accuracy, confusion matrix, feature list

- `POST /capture`  
  Accepts captured window raw + features, returns “ready for inference” payload

- `POST /infer`  
  Accepts features, returns prediction + confidence

- `GET /captures`  
  Returns timeline list

---

## Frontend (Demo UI)
- **Platform:** Web (fastest)  
- **Framework:** Next.js (React + TypeScript)  
- **UI:** Tailwind (optionally shadcn/ui)  
- **Charts:** Recharts (live plot + window plot)

### Features:
- “Capture 10s” button
- Plot of last ~30–60s gas resistance
- Table of extracted features
- Model results page (simulation metrics)
- Timeline of captures + predicted label

---

## USE AMD DEV CLOUD
- **Compute:** AMD Developer Cloud  
- **Usage:** training + evaluation job for the online VOC dataset  
- **Workflow:** train on AMD → export model.joblib + metrics.json → use locally for inference
