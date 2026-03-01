from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.model_selection import train_test_split


def make_windows(df: pd.DataFrame, window_seconds: float, sample_rate_hz: float) -> list[pd.DataFrame]:
    n = int(round(window_seconds * sample_rate_hz))
    if n < 2:
        raise ValueError("window_seconds * sample_rate_hz must be >= 2.")
    windows = []
    for start in range(0, len(df) - n + 1, n):
        w = df.iloc[start : start + n]
        windows.append(w)
    return windows


def window_to_feature(w: pd.DataFrame) -> dict:
    v = pd.to_numeric(w["Sensor_Resistance_Ohms"], errors="coerce").dropna().to_numpy(dtype=float)
    if len(v) == 0:
        return {"Sensor_Resistance_Ohms": 0.0}
    return {"Sensor_Resistance_Ohms": float(np.mean(v))}


def majority_label(w: pd.DataFrame, label_col: str) -> str:
    return w[label_col].astype(str).mode().iloc[0]


def maybe_derive_label_from_cfu(df: pd.DataFrame, cfu_threshold: float) -> pd.DataFrame:
    if "Label" in df.columns:
        return df
    if "Bacteria_Load_CFU_per_mL" not in df.columns:
        raise ValueError("Need either Label or Bacteria_Load_CFU_per_mL to derive labels.")
    cfu = pd.to_numeric(df["Bacteria_Load_CFU_per_mL"], errors="coerce").astype(float)
    out = df.copy()
    out["Label"] = np.where(cfu >= cfu_threshold, "HIGH_LOAD", "LOW_LOAD")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Train on fixed time windows (mean Sensor_Resistance_Ohms per window).")
    ap.add_argument("--data", required=True, help="Path to CSV dataset")
    ap.add_argument("--out", default="artifacts", help="Output folder for artifacts")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--test-size", "--test_size", type=float, default=0.25)
    ap.add_argument("--window-seconds", "--window_seconds", type=float, default=5.0)
    ap.add_argument("--sample-rate-hz", "--sample_rate_hz", type=float, default=5.0)
    ap.add_argument("--cfu-threshold", "--cfu_threshold", type=float, default=1e7)
    ap.add_argument("--trees", type=int, default=300)
    args = ap.parse_args()

    df = pd.read_csv(Path(args.data))
    if "Sensor_Resistance_Ohms" not in df.columns:
        raise ValueError("CSV missing Sensor_Resistance_Ohms column.")

    df = maybe_derive_label_from_cfu(df, float(args.cfu_threshold))

    windows = make_windows(df, float(args.window_seconds), float(args.sample_rate_hz))
    if not windows:
        raise ValueError("Not enough rows to form one full window. Lower window_seconds/sample_rate_hz or collect more data.")

    X_rows = []
    y_rows = []

    for w in windows:
        X_rows.append(window_to_feature(w))
        y_rows.append(majority_label(w, "Label"))

    X = pd.DataFrame(X_rows)
    y = pd.Series(y_rows)

    print("Window class counts:")
    print(y.value_counts().to_string())

    counts = y.value_counts()
    if len(counts) >= 2 and (counts < 2).any():
        print("⚠️  Not enough windows per class for stratify; stratify disabled.")
        strat = None
    elif len(counts) < 2:
        print("⚠️  Only one class present; stratify disabled.")
        strat = None
    else:
        strat = y

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=float(args.test_size),
        random_state=int(args.seed),
        stratify=strat,
    )

    model = RandomForestClassifier(
        n_estimators=int(args.trees),
        random_state=int(args.seed),
        n_jobs=-1,
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    labels = ["LOW_LOAD", "HIGH_LOAD"] if set(y.unique()) <= {"LOW_LOAD", "HIGH_LOAD"} else sorted(y.unique().tolist())
    acc = float(accuracy_score(y_test, y_pred))
    cm = confusion_matrix(y_test, y_pred, labels=labels).tolist()
    report = classification_report(y_test, y_pred, labels=labels, output_dict=True, zero_division=0)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    model_path = out_dir / "model.joblib"
    metrics_path = out_dir / "metrics.json"

    joblib.dump(model, model_path)
    metrics_path.write_text(
        json.dumps(
            {
                "accuracy": acc,
                "labels": labels,
                "feature_names": ["Sensor_Resistance_Ohms"],
                "window_seconds": float(args.window_seconds),
                "sample_rate_hz": float(args.sample_rate_hz),
                "samples_per_window": int(round(float(args.window_seconds) * float(args.sample_rate_hz))),
                "confusion_matrix": cm,
                "classification_report": report,
                "n_windows_total": int(len(y)),
                "n_train": int(len(y_train)),
                "n_test": int(len(y_test)),
                "cfu_threshold": float(args.cfu_threshold),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"\nSaved model:   {model_path}")
    print(f"Saved metrics: {metrics_path}")
    print(f"Accuracy:      {acc:.4f}")
    print(f"Windows used:  {len(y)}")
    if len(y_test) < 20:
        print("⚠️  Tiny test set. Window accuracy can look perfect even when the model is not.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
