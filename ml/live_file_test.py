from __future__ import annotations

import argparse
from pathlib import Path

import joblib
import numpy as np
import pandas as pd


def window_feature_mean_resistance(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert a single-window dataframe into the 1-row feature frame
    the model was trained to expect.
    """
    if "Sensor_Resistance_Ohms" not in df.columns:
        raise ValueError("CSV missing Sensor_Resistance_Ohms column.")

    v = pd.to_numeric(df["Sensor_Resistance_Ohms"], errors="coerce").dropna().to_numpy(dtype=float)
    if len(v) < 2:
        raise ValueError("Not enough valid Sensor_Resistance_Ohms samples in this window (need >= 2).")

    mean_val = float(np.mean(v))
    return pd.DataFrame([{"Sensor_Resistance_Ohms": mean_val}])


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Live inference: predict bacterial load class from a single-window CSV (Sensor_Resistance_Ohms only)."
    )
    ap.add_argument("--model", required=True, help="Path to model.joblib")
    ap.add_argument("--data", required=True, help="Path to single-window CSV (one column: Sensor_Resistance_Ohms)")
    ap.add_argument(
        "--expected-samples",
        type=int,
        default=25,
        help="Optional sanity check: expected samples in the window (default 25 for 5s @ 5Hz). Use 0 to disable.",
    )
    args = ap.parse_args()

    model_path = Path(args.model)
    data_path = Path(args.data)

    model = joblib.load(model_path)

    df = pd.read_csv(data_path)

    # Optional: sanity check that you collected the window size you think you did
    if args.expected_samples and len(df) != args.expected_samples:
        print(
            f"[warn] Window has {len(df)} rows, expected {args.expected_samples}. "
            "Prediction will still run, but your timing/sample-rate may be off."
        )

    Xw = window_feature_mean_resistance(df)
    pred = model.predict(Xw)[0]

    # If your model supports probabilities, show them (nice for “how confident are you?”)
    proba_text = ""
    if hasattr(model, "predict_proba"):
        probs = model.predict_proba(Xw)[0]
        classes = getattr(model, "classes_", None)
        if classes is not None and len(classes) == len(probs):
            pairs = sorted(zip(classes, probs), key=lambda x: float(x[1]), reverse=True)
            proba_text = " | probs: " + ", ".join([f"{c}={float(p):.3f}" for c, p in pairs])
        else:
            proba_text = f" | probs: {', '.join([f'{float(p):.3f}' for p in probs])}"

    mean_res = float(Xw.iloc[0]["Sensor_Resistance_Ohms"])
    print(f"Prediction: {pred}{proba_text}")
    print(f"Window mean Sensor_Resistance_Ohms: {mean_res:.2f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())