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


def _detect_task_and_build_xy(df: pd.DataFrame, *, cfu_threshold: float) -> tuple[pd.DataFrame, pd.Series, list[str]]:
    """
    Builds (X, y, labels) for two supported dataset styles:

    A) Your own collected dataset:
       columns: Sensor_Resistance_Ohms, Label

    B) Public mox dataset:
       columns: Sensor_Resistance_Ohms, Bacteria_Load_CFU_per_mL
       -> we derive Label = LOW_LOAD/HIGH_LOAD using cfu_threshold
    """
    if "Sensor_Resistance_Ohms" not in df.columns:
        raise ValueError("CSV missing required column: Sensor_Resistance_Ohms")

    if "Label" in df.columns:
        y = df["Label"].astype(str)
        labels = sorted(y.dropna().unique().tolist())
        X = df[["Sensor_Resistance_Ohms"]]
        return X, y, labels

    if "Bacteria_Load_CFU_per_mL" in df.columns:
        cfu = pd.to_numeric(df["Bacteria_Load_CFU_per_mL"], errors="coerce").astype(float)
        y = pd.Series(np.where(cfu >= cfu_threshold, "HIGH_LOAD", "LOW_LOAD"))
        labels = ["LOW_LOAD", "HIGH_LOAD"]
        X = df[["Sensor_Resistance_Ohms"]]
        return X, y, labels

    raise ValueError("Dataset must contain either 'Label' or 'Bacteria_Load_CFU_per_mL'.")


def _clean_xy(X: pd.DataFrame, y: pd.Series) -> tuple[pd.DataFrame, pd.Series]:
    Xc = X.copy()
    Xc["Sensor_Resistance_Ohms"] = pd.to_numeric(Xc["Sensor_Resistance_Ohms"], errors="coerce")

    Xc = Xc.replace([np.inf, -np.inf], np.nan).dropna()
    yc = y.loc[Xc.index].reset_index(drop=True)
    Xc = Xc.reset_index(drop=True)
    return Xc, yc


def _maybe_stratify(y: pd.Series) -> pd.Series | None:
    counts = y.value_counts(dropna=False)
    if len(counts) < 2:
        print("⚠️  Only one class present in y; stratify disabled.")
        return None
    if (counts < 2).any():
        print("⚠️  Not enough samples per class for stratify; stratify disabled.")
        print(counts.to_string())
        return None
    return y


def main() -> int:
    ap = argparse.ArgumentParser(description="Train RandomForest classifier from CSV and save artifacts.")
    ap.add_argument("--data", required=True, help="Path to CSV dataset")
    ap.add_argument("--out", default="artifacts", help="Output folder for artifacts (default: artifacts)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--test-size", "--test_size", type=float, default=0.25, help="Test split fraction (default: 0.25)")
    ap.add_argument(
        "--cfu-threshold",
        "--cfu_threshold",
        type=float,
        default=1e7,
        help="If CFU column exists, classify LOW/HIGH around this threshold (default: 1e7)",
    )
    ap.add_argument("--trees", type=int, default=300, help="Number of trees (default: 300)")

    args = ap.parse_args()

    data_path = Path(args.data)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(data_path)

    # Build X/y
    X, y, labels = _detect_task_and_build_xy(df, cfu_threshold=float(args.cfu_threshold))
    X, y = _clean_xy(X, y)

    print("Class counts:")
    print(y.value_counts().to_string())

    strat = _maybe_stratify(y)

    # Split
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=float(args.test_size),
        random_state=int(args.seed),
        stratify=strat,
    )

    # Train
    model = RandomForestClassifier(
        n_estimators=int(args.trees),
        random_state=int(args.seed),
        n_jobs=-1,
    )
    model.fit(X_train, y_train)

    # Eval
    y_pred = model.predict(X_test)
    acc = float(accuracy_score(y_test, y_pred))

    cm = confusion_matrix(y_test, y_pred, labels=labels).tolist()
    report = classification_report(y_test, y_pred, labels=labels, output_dict=True, zero_division=0)

    metrics = {
        "accuracy": acc,
        "labels": labels,
        "feature_names": ["Sensor_Resistance_Ohms"],
        "confusion_matrix": cm,
        "classification_report": report,
        "n_rows_total": int(len(y)),
        "n_train": int(len(y_train)),
        "n_test": int(len(y_test)),
        "cfu_threshold": float(args.cfu_threshold) if "Bacteria_Load_CFU_per_mL" in df.columns else None,
    }

    # Save artifacts
    model_path = out_dir / "model.joblib"
    metrics_path = out_dir / "metrics.json"
    joblib.dump(model, model_path)
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    print(f"\nSaved model:   {model_path}")
    print(f"Saved metrics: {metrics_path}")
    print(f"Accuracy:      {acc:.4f}")
    print(f"Features:      ['Sensor_Resistance_Ohms']")

    # Extra sanity warning for tiny eval sets
    if len(y_test) < 20:
        print("⚠️  Tiny test set. If you see 1.0000 accuracy, it might be luck, not science.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
