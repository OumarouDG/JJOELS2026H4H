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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", required=True, help="Path to CSV dataset")
    parser.add_argument("--out", default="artifacts", help="Output folder for artifacts")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--test-size", type=float, default=0.25)

    # For CFU dataset mode:
    parser.add_argument("--cfu-threshold", type=float, default=1e7,
                        help="If CFU column exists, classify LOW/HIGH around this threshold")

    args = parser.parse_args()

    data_path = Path(args.data)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(data_path)

    # ---- Detect dataset type ----
    if "Label" in df.columns:
        # Generic labeled dataset
        label_col = "Label"
        feature_cols = [c for c in df.columns if c != label_col]

        y = df[label_col].astype(str)
        X = df[feature_cols]

        labels = sorted(y.unique().tolist())

    elif "Bacteria_Load_CFU_per_mL" in df.columns:
        # Your provided CFU dataset: make a binary label
        cfu = df["Bacteria_Load_CFU_per_mL"].astype(float)
        y = np.where(cfu >= args.cfu_threshold, "HIGH_LOAD", "LOW_LOAD")
        y = pd.Series(y)

        feature_cols = [
            "Ethanol_ppm",
            "Acetaldehyde_ppm",
            "Acetic_Acid_ppm",
            "Isoprene_ppm",
            "Hydrogen_Sulfide_ppm",
            "Sensor_Resistance_Ohms",
        ]
        missing = [c for c in feature_cols if c not in df.columns]
        if missing:
            raise ValueError(f"CSV missing expected feature columns: {missing}")

        X = df[feature_cols]
        labels = ["LOW_LOAD", "HIGH_LOAD"]

    else:
        raise ValueError("No Label column and no Bacteria_Load_CFU_per_mL column found.")

    # ---- Clean ----
    X = X.replace([np.inf, -np.inf], np.nan).dropna()
    y = y.loc[X.index]

    # ---- Split ----
    strat = y if len(set(y)) > 1 else None
    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=args.test_size,
        random_state=args.seed,
        stratify=strat,
    )

    # ---- Train ----
    model = RandomForestClassifier(
        n_estimators=300,
        random_state=args.seed,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)

    # ---- Eval ----
    pred = model.predict(X_test)
    acc = float(accuracy_score(y_test, pred))
    cm = confusion_matrix(y_test, pred, labels=labels).tolist()
    report = classification_report(y_test, pred, labels=labels, output_dict=True)

    metrics = {
        "accuracy": acc,
        "labels": labels,
        "feature_names": list(X.columns),
        "confusion_matrix": cm,
        "classification_report": report,
        "n_train": int(len(y_train)),
        "n_test": int(len(y_test)),
    }

    # ---- Save artifacts ----
    model_path = out_dir / "model.joblib"
    metrics_path = out_dir / "metrics.json"

    joblib.dump(model, model_path)
    metrics_path.write_text(json.dumps(metrics, indent=2))

    print(f"Saved model:   {model_path}")
    print(f"Saved metrics: {metrics_path}")
    print(f"Accuracy:      {acc:.4f}")
    print(f"Labels:        {labels}")
    print(f"Features:      {list(X.columns)}")


if __name__ == "__main__":
    main()