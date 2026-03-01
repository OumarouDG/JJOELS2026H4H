from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import joblib
from sklearn.metrics import accuracy_score, confusion_matrix, classification_report


def make_windows(df: pd.DataFrame, window_seconds: int, sample_rate_hz: int) -> list[pd.DataFrame]:
    """Split a dataframe into fixed-size consecutive windows."""
    n_per_window = int(window_seconds * sample_rate_hz)
    if n_per_window <= 0:
        raise ValueError("window_seconds * sample_rate_hz must be > 0")

    windows = []
    for start in range(0, len(df), n_per_window):
        chunk = df.iloc[start : start + n_per_window]
        if len(chunk) == n_per_window:
            windows.append(chunk)
    return windows


def window_features(chunk: pd.DataFrame) -> pd.DataFrame:
    """
    Turn a window into the exact feature set the model expects.
    Right now: only Sensor_Resistance_Ohms, aggregated to mean.
    """
    vals = chunk["Sensor_Resistance_Ohms"].astype(float).to_numpy()
    feat = {
        "Sensor_Resistance_Ohms": float(np.mean(vals)),
    }
    return pd.DataFrame([feat])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="Path to model.joblib")
    ap.add_argument("--data", required=True, help="Path to CSV")
    ap.add_argument("--window_seconds", type=int, default=5)
    ap.add_argument("--sample_rate_hz", type=int, default=5)
    ap.add_argument("--cfu_threshold", type=float, default=1e7)
    args = ap.parse_args()

    model = joblib.load(args.model)

    df = pd.read_csv(args.data)

    # --- Validate columns ---
    if "Sensor_Resistance_Ohms" not in df.columns:
        raise ValueError("CSV missing Sensor_Resistance_Ohms column.")
    if "Bacteria_Load_CFU_per_mL" not in df.columns:
        raise ValueError("CSV missing Bacteria_Load_CFU_per_mL column.")

    # --- Derive labels (LOW vs HIGH load) ---
    cfu = df["Bacteria_Load_CFU_per_mL"].astype(float)
    df = df.copy()
    df["Label"] = np.where(cfu >= args.cfu_threshold, "HIGH_LOAD", "LOW_LOAD")

    # --- Windowing ---
    windows = make_windows(df, args.window_seconds, args.sample_rate_hz)
    if not windows:
        raise ValueError("Not enough rows to form even one full window.")

    y_true = []
    y_pred = []

    for w in windows:
        # Label the window by majority label inside the window
        label = w["Label"].mode().iloc[0]
        Xw = window_features(w)

        pred = model.predict(Xw)[0]

        y_true.append(label)
        y_pred.append(pred)

    acc = accuracy_score(y_true, y_pred)
    labels = ["LOW_LOAD", "HIGH_LOAD"]
    cm = confusion_matrix(y_true, y_pred, labels=labels)

    print(f"Windows evaluated: {len(y_true)}")
    print(f"Accuracy: {acc:.4f}")
    print("\nConfusion matrix (rows=true, cols=pred) [LOW_LOAD, HIGH_LOAD]:")
    print(cm)
    print("\nClassification report:")
    print(classification_report(y_true, y_pred, labels=labels))


if __name__ == "__main__":
    main()