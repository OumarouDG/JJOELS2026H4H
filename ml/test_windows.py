from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix


def make_windows(df: pd.DataFrame, window_seconds: float, sample_rate_hz: float) -> list[pd.DataFrame]:
    n = int(round(window_seconds * sample_rate_hz))
    if n < 2:
        raise ValueError("window_seconds * sample_rate_hz must be >= 2.")
    out = []
    for start in range(0, len(df) - n + 1, n):
        out.append(df.iloc[start : start + n])
    return out


def window_feature_mean_resistance(w: pd.DataFrame) -> pd.DataFrame:
    v = pd.to_numeric(w["Sensor_Resistance_Ohms"], errors="coerce").dropna().to_numpy(dtype=float)
    mean_val = float(np.mean(v)) if len(v) else 0.0
    return pd.DataFrame([{"Sensor_Resistance_Ohms": mean_val}])


def ensure_label(df: pd.DataFrame, *, cfu_threshold: float) -> pd.DataFrame:
    if "Label" in df.columns:
        return df
    if "Bacteria_Load_CFU_per_mL" in df.columns:
        cfu = pd.to_numeric(df["Bacteria_Load_CFU_per_mL"], errors="coerce").astype(float)
        out = df.copy()
        out["Label"] = np.where(cfu >= cfu_threshold, "HIGH_LOAD", "LOW_LOAD")
        return out
    raise ValueError("CSV must contain either Label or Bacteria_Load_CFU_per_mL.")


def main() -> int:
    ap = argparse.ArgumentParser(description="Evaluate a trained model on fixed 5s windows from a CSV.")
    ap.add_argument("--model", required=True, help="Path to model.joblib")
    ap.add_argument("--data", required=True, help="Path to CSV dataset")
    ap.add_argument("--window-seconds", "--window_seconds", type=float, default=5.0)
    ap.add_argument("--sample-rate-hz", "--sample_rate_hz", type=float, default=5.0)
    ap.add_argument("--cfu-threshold", "--cfu_threshold", type=float, default=1e7)
    ap.add_argument("--print-n", type=int, default=0, help="Print first N window predictions")
    args = ap.parse_args()

    model = joblib.load(Path(args.model))

    df = pd.read_csv(Path(args.data))
    if "Sensor_Resistance_Ohms" not in df.columns:
        raise ValueError("CSV missing Sensor_Resistance_Ohms column.")

    df = ensure_label(df, cfu_threshold=float(args.cfu_threshold))

    windows = make_windows(df, float(args.window_seconds), float(args.sample_rate_hz))
    if not windows:
        raise ValueError("Not enough rows to form one full window.")

    y_true = []
    y_pred = []

    for i, w in enumerate(windows):
        y = w["Label"].astype(str).mode().iloc[0]
        Xw = window_feature_mean_resistance(w)
        pred = model.predict(Xw)[0]

        y_true.append(y)
        y_pred.append(pred)

        if args.print_n and i < args.print_n:
            print(f"Window {i:03d}: true={y} pred={pred} mean_res={float(Xw.iloc[0,0]):.2f}")

    labels = sorted(pd.Series(y_true).unique().tolist())
    acc = float(accuracy_score(y_true, y_pred))
    cm = confusion_matrix(y_true, y_pred, labels=labels)

    print(f"\nWindows evaluated: {len(y_true)}")
    print(f"Window seconds: {args.window_seconds}, sample_rate_hz: {args.sample_rate_hz}")
    print(f"Accuracy: {acc:.4f}\n")
    print("Confusion matrix (rows=true, cols=pred):")
    print("labels:", labels)
    print(cm)
    print("\nClassification report:")
    print(classification_report(y_true, y_pred, labels=labels, zero_division=0))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
