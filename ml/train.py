import os
import json
import argparse
import joblib
import numpy as np
import pandas as pd

from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, confusion_matrix, classification_report
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error
from sklearn.tree import DecisionTreeRegressor


RES_COL = "Sensor_Resistance_Ohms"
TARGET_CFU = "Bacteria_Load_CFU_per_mL"
PPM_COLS = [
    "Ethanol_ppm",
    "Acetaldehyde_ppm",
    "Acetic_Acid_ppm",
    "Isoprene_ppm",
    "Hydrogen_Sulfide_ppm",
]


def parse_args():
    p = argparse.ArgumentParser(description="Train resistance->CFU regressor (optional marker classifier).")
    p.add_argument("--data", required=True, help="Path to CSV dataset")
    p.add_argument("--artifacts", required=True, help="Output artifacts directory")

    p.add_argument("--test-size", type=float, default=0.2)
    p.add_argument("--seed", type=int, default=42)

    # Decision tree knobs (accuracy vs overfit control)
    p.add_argument("--max-depth", type=int, default=6)
    p.add_argument("--min-samples-leaf", type=int, default=3)

    # Marker model stays as-is (best-effort, but your dataset likely has 1 class)
    p.add_argument("--n-estimators", type=int, default=300)
    p.add_argument("--with-marker", action="store_true", help="Also train dominant biomarker classifier (best effort)")
    p.add_argument("--no-plot", action="store_true", help="Disable confusion matrix plot export")
    return p.parse_args()


def load_dataset(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)

    for col in [RES_COL, TARGET_CFU]:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    df[RES_COL] = pd.to_numeric(df[RES_COL], errors="coerce")
    df[TARGET_CFU] = pd.to_numeric(df[TARGET_CFU], errors="coerce")

    for c in PPM_COLS:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    df = df.dropna(subset=[RES_COL, TARGET_CFU]).copy()
    return df


def train_cfu_regressor(df, test_size, seed, max_depth, min_samples_leaf):
    X = df[[RES_COL]].astype(float).values
    y = df[TARGET_CFU].astype(float).values

    # Predict log10(CFU) for stability across 1e3..1e8
    y_log = np.log10(np.clip(y, 1.0, None))

    X_train, X_test, y_train, y_test = train_test_split(
        X, y_log, test_size=test_size, random_state=seed
    )

    model = DecisionTreeRegressor(
        random_state=seed,
        max_depth=max_depth,
        min_samples_leaf=min_samples_leaf,
    )
    model.fit(X_train, y_train)

    pred_log = model.predict(X_test)

    r2 = float(r2_score(y_test, pred_log))
    mae_log = float(mean_absolute_error(y_test, pred_log))
    rmse_log = float(np.sqrt(mean_squared_error(y_test, pred_log)))

    metrics = {
        "task": "regression",
        "input_feature": RES_COL,
        "target": TARGET_CFU,
        "target_transform": "log10",
        "r2_score_log10": r2,
        "mae_log10": mae_log,
        "rmse_log10": rmse_log,
        "n_samples": int(len(df)),
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
        "model": {
            "type": "DecisionTreeRegressor",
            "max_depth": None if max_depth is None else int(max_depth),
            "min_samples_leaf": int(min_samples_leaf),
            "seed": int(seed),
        },
    }

    return model, metrics


def dominant_marker_label(df: pd.DataFrame) -> pd.Series:
    missing = [c for c in PPM_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing ppm columns for marker model: {missing}")
    ppm = df[PPM_COLS].astype(float)
    return ppm.idxmax(axis=1)


def train_marker_classifier(df: pd.DataFrame, test_size: float, seed: int, n_estimators: int):
    y = dominant_marker_label(df)

    if y.nunique() < 2:
        raise ValueError("Marker labels have only one class; cannot train classifier.")

    X = df[[RES_COL]].astype(float)

    counts = y.value_counts()
    use_stratify = counts.min() >= 2

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=seed, stratify=y if use_stratify else None
    )

    clf = RandomForestClassifier(
        n_estimators=n_estimators,
        random_state=seed,
        class_weight="balanced",
        n_jobs=-1,
    )
    clf.fit(X_train, y_train)

    preds = clf.predict(X_test)
    acc = float(accuracy_score(y_test, preds))
    cm = confusion_matrix(y_test, preds, labels=clf.classes_)
    report = classification_report(y_test, preds, output_dict=True)

    metrics = {
        "task": "classification",
        "input_feature": RES_COL,
        "target": "dominant_biomarker_ppm",
        "classes": list(clf.classes_),
        "accuracy": acc,
        "stratified_split": bool(use_stratify),
        "class_counts": {k: int(v) for k, v in counts.to_dict().items()},
        "confusion_matrix": {"labels": list(clf.classes_), "matrix": cm.tolist()},
        "report": report,
        "n_samples": int(len(df)),
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
        "model": {
            "type": "RandomForestClassifier",
            "n_estimators": int(n_estimators),
            "seed": int(seed),
        },
    }

    return clf, metrics, cm


def save_json(path: str, obj: dict):
    with open(path, "w") as f:
        json.dump(obj, f, indent=2)


def save_confusion_png(cm, labels, out_path):
    try:
        import matplotlib.pyplot as plt

        fig = plt.figure()
        plt.imshow(cm, interpolation="nearest")
        plt.title("Dominant Biomarker Confusion Matrix")
        plt.xlabel("Predicted")
        plt.ylabel("True")
        plt.xticks(range(len(labels)), labels, rotation=45, ha="right")
        plt.yticks(range(len(labels)), labels)
        for (i, j), v in np.ndenumerate(cm):
            plt.text(j, i, str(v), ha="center", va="center")
        plt.tight_layout()
        fig.savefig(out_path, dpi=200)
        plt.close(fig)
    except Exception:
        pass


def main():
    args = parse_args()
    os.makedirs(args.artifacts, exist_ok=True)

    df = load_dataset(args.data)

    reg_model, reg_metrics = train_cfu_regressor(
        df=df,
        test_size=args.test_size,
        seed=args.seed,
        max_depth=args.max_depth,
        min_samples_leaf=args.min_samples_leaf,
    )

    reg_model_path = os.path.join(args.artifacts, "model.joblib")
    reg_metrics_path = os.path.join(args.artifacts, "metrics.json")
    joblib.dump(reg_model, reg_model_path)
    save_json(reg_metrics_path, reg_metrics)

    print("✅ CFU regressor trained")
    print(f"  model:   {reg_model_path}")
    print(f"  metrics: {reg_metrics_path}")

    if args.with_marker:
        try:
            marker_model, marker_metrics, cm = train_marker_classifier(
                df=df,
                test_size=args.test_size,
                seed=args.seed,
                n_estimators=args.n_estimators,
            )

            marker_model_path = os.path.join(args.artifacts, "marker_model.joblib")
            marker_metrics_path = os.path.join(args.artifacts, "marker_metrics.json")
            joblib.dump(marker_model, marker_model_path)
            save_json(marker_metrics_path, marker_metrics)

            if not args.no_plot:
                png_path = os.path.join(args.artifacts, "confusion_matrix.png")
                save_confusion_png(cm, marker_metrics["classes"], png_path)

            print("✅ Marker classifier trained (best-effort)")
            print(f"  model:   {marker_model_path}")
            print(f"  metrics: {marker_metrics_path}")

        except Exception as e:
            print("⚠️ Marker classifier skipped:", str(e))

    print("\nRuntime note:")
    print("  Model predicts log10(CFU). For a 5-second blow window (Option A):")
    print("    log10_avg = mean(model.predict([[R_i]]) for i in window)")
    print("    CFU_final = 10 ** log10_avg")


if __name__ == "__main__":
    main()