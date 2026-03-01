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



# ML folder

You have two modes:

## 1) Train per-row (recommended for public mox CSV)
This trains using only `Sensor_Resistance_Ohms` as the feature.

It supports either:
- `Label` column (your collected data), or
- `Bacteria_Load_CFU_per_mL` (public dataset, label derived by threshold)

### Train
PowerShell (Windows):
```powershell
cd ml
python .\train.py --data "$env:USERPROFILE\Downloads\mox_streptococcus_pneumoniae_dataset (1).csv" --out .\artifacts --cfu-threshold 1e7
```

### Evaluate on 5-second windows (optional)
This evaluates by taking mean resistance over each window and predicting once per window.

```powershell
python .\test_windows.py --model .\artifacts\model.joblib --data "$env:USERPROFILE\Downloads\mox_streptococcus_pneumoniae_dataset (1).csv" --window-seconds 5 --sample-rate-hz 5 --cfu-threshold 1e7
```

Note: If your CSV is not a real time-series stream, window accuracy can look unrealistically perfect. Treat it as a demo metric, not truth.

## 2) Train on windows (only for real streamed sensor logs)
If you have a CSV that is literally a stream sampled at a known rate, train with:

```powershell
python .\train_windows.py --data .\your_stream.csv --out .\artifacts --window-seconds 5 --sample-rate-hz 5
```

## Common gotcha
Your terminal errors were because you typed underscores:

- use `--window-seconds` not `--window_seconds`
- use `--sample-rate-hz` not `--sample_rate_hz`
- use `--cfu-threshold` not `--cfu_threshold`

The scripts now accept both forms.
