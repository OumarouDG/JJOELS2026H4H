from __future__ import annotations

import argparse
from pathlib import Path
import json

import numpy as np
import pandas as pd
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, confusion_matrix, classification_report


def make_windows(df: pd.DataFrame, n_per_window: int) -> list[pd.DataFrame]:
    windows = []
    for start in range(0, len(df), n_per_window):
        chunk = df.iloc[start : start + n_per_window]
        if len(chunk) == n_per_window:
            windows.append(chunk)
    return windows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", default="artifacts")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--test-size", type=float, default=0.25)
    ap.add_argument("--cfu-threshold", type=float, default=1e7)
    ap.add_argument("--window-seconds", type=float, default=5.0)
    ap.add_argument("--sample-rate-hz", type=float, default=5.0)
    args = ap.parse_args()

    data_path = Path(args.data)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(data_path)

    if "Sensor_Resistance_Ohms" not in df.columns:
        raise ValueError("Missing Sensor_Resistance_Ohms column.")
    if "Bacteria_Load_CFU_per_mL" not in df.columns:
        raise ValueError("Missing Bacteria_Load_CFU_per_mL column.")

    # derive per-row labels
    cfu = pd.to_numeric(df["Bacteria_Load_CFU_per_mL"], errors="coerce")
    df = df.copy()
    df["Label"] = np.where(cfu >= args.cfu_threshold, "HIGH_LOAD", "LOW_LOAD")

    # windowing
    n_per_window = int(round(args.window_seconds * args.sample_rate_hz))
    if n_per_window < 2:
        raise ValueError("window too small; increase window-seconds or sample-rate-hz.")

    windows = make_windows(df, n_per_window)
    if not windows:
        raise ValueError("Not enough rows to form a full window.")

    X_rows = []
    y_rows = []

    for w in windows:
        vals = pd.to_numeric(w["Sensor_Resistance_Ohms"], errors="coerce").dropna().to_numpy(dtype=float)
        if len(vals) == 0:
            continue

        # feature: mean over window (matches your test script)
        X_rows.append({"Sensor_Resistance_Ohms": float(np.mean(vals))})

        # label: majority label in window
        y_rows.append(w["Label"].mode().iloc[0])

    X = pd.DataFrame(X_rows)
    y = pd.Series(y_rows)

    # clean
    X = X.replace([np.inf, -np.inf], np.nan).dropna()
    y = y.loc[X.index]

    # stratify only if safe
    counts = y.value_counts()
    strat = None
    if (counts >= 2).all() and len(counts) > 1:
        strat = y
    else:
        print("⚠️ Not enough samples per class for stratify; splitting without stratify.")
        print(counts.to_string())

    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=args.test_size,
        random_state=args.seed,
        stratify=strat,
    )

    model = RandomForestClassifier(
        n_estimators=300,
        random_state=args.seed,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)

    pred = model.predict(X_test)
    acc = float(accuracy_score(y_test, pred))
    labels = ["LOW_LOAD", "HIGH_LOAD"]
    cm = confusion_matrix(y_test, pred, labels=labels).tolist()
    report = classification_report(y_test, pred, labels=labels, output_dict=True, zero_division=0)

    metrics = {
        "accuracy": acc,
        "labels": labels,
        "feature_names": ["Sensor_Resistance_Ohms"],
        "confusion_matrix": cm,
        "classification_report": report,
        "n_train": int(len(y_train)),
        "n_test": int(len(y_test)),
        "window_seconds": args.window_seconds,
        "sample_rate_hz": args.sample_rate_hz,
        "samples_per_window": n_per_window,
        "cfu_threshold": args.cfu_threshold,
    }

    model_path = out_dir / "model.joblib"
    metrics_path = out_dir / "metrics.json"
    joblib.dump(model, model_path)
    metrics_path.write_text(json.dumps(metrics, indent=2))

    print(f"Saved model:   {model_path}")
    print(f"Saved metrics: {metrics_path}")
    print(f"Accuracy:      {acc:.4f}")
    print(f"Windows used:  {len(y)}")


if __name__ == "__main__":
    main()