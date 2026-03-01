# BACKEND — FastAPI API + Inference Layer

##  PURPOSE
This folder contains the FastAPI backend responsible for:
- Receiving captured sensor windows
- Running ML inference
- Serving data to the frontend UI
- Managing capture history

The backend acts as the central communication hub between:
collector → backend → frontend

---

## 👨‍💻 WHO WORKS HERE
Branch example:
feature/api-fastapi

ONLY backend/API developers should modify this folder.

---

##  RESPONSIBILITIES
- FastAPI server setup
- API endpoints
- Model loading (`model.joblib`)
- Feature validation
- Capture storage
- Prediction responses

---

## REQUIRED ENDPOINTS

POST /train  
Loads or trains model from ML artifacts

GET /metrics  
Returns accuracy + evaluation metrics

POST /capture  
Receives captured sensor window

POST /infer  
Returns prediction + confidence score

GET /captures  
Returns capture timeline history

---

## FILES TO IMPLEMENT
main.py
- FastAPI app entrypoint
- route definitions

---

## SUCCESS CONDITION
Frontend can request predictions and receive JSON responses.
