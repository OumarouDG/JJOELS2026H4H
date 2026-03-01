# ML — Model Training & Research Pipeline

## 🔥 PURPOSE
Contains all machine learning experimentation and training workflows.

Training occurs using public VOC datasets and AMD Developer Cloud.

Artifacts generated here are consumed by the backend.

---

## 👨‍💻 WHO WORKS HERE
Branch example:
feature/model-training

Only ML developers modify this folder.

---

## RESPONSIBILITIES
- Dataset preprocessing
- Feature engineering
- Model training
- Evaluation
- Exporting artifacts

---

## OUTPUT ARTIFACTS
Stored in:
ml/artifacts/

Files:
- model.joblib
- metrics.json
- confusion_matrix.png (optional)

---

## TRAINING WORKFLOW
1. Train model on AMD Dev Cloud
2. Export artifacts
3. Commit artifacts for backend inference

---

## FILES TO IMPLEMENT
train.py
- dataset loading
- model training
- evaluation
- artifact export

---

## SUCCESS CONDITION
Backend loads model and performs inference locally.
