# ======================================================================#
#                          model.py                                     #
# ======================================================================#
# Reusable model utilities:
# - Load dataset from CSV
# - Train a RandomForest
# - Evaluate + metrics
# - Save/Load artifacts
#
# NOTE: No serial, no Arduino. That belongs in /collector.
# ======================================================================#

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import sys
import pandas as pd
import joblib
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, confusion_matrix, classification_report


DEFAULT_FEATURE_COLS = ["Temperature", "Humidity", "Pressure", "GasResistance"]
DEFAULT_LABEL_COL = "Label"

model = joblib.load("artifacts/model.joblib")

file = sys.argv[1]
df = pd.read_csv(file)

gas_mean = df["gas"].mean()

prediction = model.predict([[gas_mean]])

print(prediction[0])

@dataclass
class TrainConfig:
    feature_cols: List[str] = None
    label_col: str = DEFAULT_LABEL_COL
    test_size: float = 0.2
    random_state: int = 42
    n_estimators: int = 200
    max_depth: Optional[int] = None

    def __post_init__(self):
        if self.feature_cols is None:
            self.feature_cols = DEFAULT_FEATURE_COLS


def load_csv_dataset(
    csv_path: str | Path,
    feature_cols: List[str],
    label_col: str,
) -> Tuple[pd.DataFrame, pd.Series]:
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Dataset not found: {csv_path}")

    df = pd.read_csv(csv_path)

    missing = [c for c in feature_cols + [label_col] if c not in df.columns]
    if missing:
        raise ValueError(f"CSV missing columns: {missing}. Found: {list(df.columns)}")

    X = df[feature_cols].copy()
    y = df[label_col].astype(str).copy()

    # Defensive cleanup
    X = X.replace([np.inf, -np.inf], np.nan).dropna()
    y = y.loc[X.index]

    if len(X) < 10:
        raise ValueError("Not enough clean rows after filtering NaNs/inf. Need at least ~10.")

    return X, y


def train_model(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    cfg: TrainConfig,
) -> RandomForestClassifier:
    model = RandomForestClassifier(
        n_estimators=cfg.n_estimators,
        random_state=cfg.random_state,
        max_depth=cfg.max_depth,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)
    return model


def evaluate_model(
    model: RandomForestClassifier,
    X_test: pd.DataFrame,
    y_test: pd.Series,
) -> Dict:
    preds = model.predict(X_test)
    acc = float(accuracy_score(y_test, preds))
    labels = sorted(list(set(y_test.astype(str).tolist())))
    cm = confusion_matrix(y_test, preds, labels=labels).tolist()
    report = classification_report(y_test, preds, labels=labels, output_dict=True)

    return {
        "accuracy": acc,
        "labels": labels,
        "confusion_matrix": cm,
        "classification_report": report,
        "feature_names": list(X_test.columns),
        "n_test": int(len(y_test)),
    }


def save_artifacts(
    model: RandomForestClassifier,
    metrics: Dict,
    out_dir: str | Path,
    model_name: str = "model.joblib",
    metrics_name: str = "metrics.json",
) -> Tuple[Path, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    model_path = out_dir / model_name
    metrics_path = out_dir / metrics_name

    joblib.dump(model, model_path)
    metrics_path.write_text(json.dumps(metrics, indent=2))

    return model_path, metrics_path


def load_model(model_path: str | Path) -> RandomForestClassifier:
    return joblib.load(str(model_path))