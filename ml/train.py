import os
import json
import argparse
import joblib
import numpy as np
import pandas as pd

from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, confusion_matrix, classification_report
from sklearn.ensemble import RandomForestClassifier

def parse_args():
    p = argparse.ArgumentParser(description="Train VOC breath infection model")
    p.add_argument("--data", default="ml/data/voc_dataset.csv", help="Path to CSV dataset")
    p.add_argument("--artifacts", default="ml/artifacts", help="Output artifacts directory")
    p.add_argument("--threshold", type=float, default=1e5, help="CFU/mL threshold to label infection=1")
    p.add_argument("--test-size", type=float, default=0.2, help="Test split fraction")
    p.add_argument("--seed", type=int, default=42, help="Random seed")
    p.add_argument("--n-estimators", type=int, default=300, help="RandomForest trees")
    p.add_argument("--max-depth", type=int, default=None, help="RandomForest max depth")
    p.add_argument("--no-plot", action="store_true", help="Disable confusion matrix plot export")
    return p.parse_args()

FEATURE_COLS = [
    "Ethanol_ppm",
    "Acetaldehyde_ppm",
    "Acetic_Acid_ppm",
    "Isoprene_ppm",
    "Hydrogen_Sulfide_ppm",
    "Sensor_Resistance_Ohms",
]

TARGET_COL = "Bacteria_Load_CFU_per_mL"

def make_label(bacteria_load: pd.Series, threshold: float) -> pd.Series:
    return (bacteria_load.astype(float) >= threshold).astype(int)

def load_dataset(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    needed = set(FEATURE_COLS + [TARGET_COL])
    missing = [c for c in needed if c not in df.columns]
    if missing:
        raise ValueError(f"Dataset missing columns: {missing}")
    df = df.dropna(subset=FEATURE_COLS + [TARGET_COL]).copy()
    for c in FEATURE_COLS + [TARGET_COL]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=FEATURE_COLS + [TARGET_COL]).copy()
    return df

def train_and_eval(df: pd.DataFrame, threshold: float, test_size: float, seed: int,
                   n_estimators: int, max_depth):
    X = df[FEATURE_COLS].astype(float)
    y = make_label(df[TARGET_COL], threshold)

    # If y has only one class, training is meaningless, so fail loudly.
    if y.nunique() < 2:
        raise ValueError(
            f"Only one class present after labeling (threshold={threshold}). "
            f"Try a different threshold or check dataset."
        )

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=seed, stratify=y
    )

    model = RandomForestClassifier(
        n_estimators=n_estimators,
        max_depth=max_depth,
        random_state=seed,
        class_weight="balanced",
        n_jobs=-1,
    )
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    acc = float(accuracy_score(y_test, preds))
    cm = confusion_matrix(y_test, preds)

    report = classification_report(y_test, preds, output_dict=True)

    metrics = {
        "accuracy": acc,
        "confusion_matrix": cm.tolist(),
        "feature_cols": FEATURE_COLS,
        "label_threshold_cfu_per_ml": threshold,
        "n_samples": int(len(df)),
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
        "class_balance": {
            "label_0": int((y == 0).sum()),
            "label_1": int((y == 1).sum()),
        },
        "report": report,
    }

    return model, metrics, cm

def save_artifacts(model, metrics: dict, cm: np.ndarray, out_dir: str, no_plot: bool):
    os.makedirs(out_dir, exist_ok=True)

    model_path = os.path.join(out_dir, "model.joblib")
    metrics_path = os.path.join(out_dir, "metrics.json")
    png_path = os.path.join(out_dir, "confusion_matrix.png")

    joblib.dump(model, model_path)

    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)

    if not no_plot:
        try:
            import matplotlib.pyplot as plt

            fig = plt.figure()
            plt.imshow(cm, interpolation="nearest")
            plt.title("Confusion Matrix")
            plt.xlabel("Predicted")
            plt.ylabel("True")
            plt.xticks([0, 1], ["no_infection", "infection"])
            plt.yticks([0, 1], ["no_infection", "infection"])
            for (i, j), v in np.ndenumerate(cm):
                plt.text(j, i, str(v), ha="center", va="center")
            plt.tight_layout()
            fig.savefig(png_path, dpi=200)
            plt.close(fig)
        except Exception:
            # If matplotlib isn't available, don't crash training.
            pass

    return model_path, metrics_path, png_path

def main():
    args = parse_args()
    df = load_dataset(args.data)
    model, metrics, cm = train_and_eval(
        df=df,
        threshold=args.threshold,
        test_size=args.test_size,
        seed=args.seed,
        n_estimators=args.n_estimators,
        max_depth=args.max_depth,
    )
    model_path, metrics_path, png_path = save_artifacts(
        model=model,
        metrics=metrics,
        cm=cm,
        out_dir=args.artifacts,
        no_plot=args.no_plot,
    )

    print("✅ Training complete")
    print(f"  model:   {model_path}")
    print(f"  metrics: {metrics_path}")
    if not args.no_plot:
        print(f"  cm png:  {png_path}")

if __name__ == "__main__":
    main()
