# ml/test_model_windows.py
# Runs an already-trained model (joblib) on a CSV and reports accuracy.
# Also computes 5-second-window accuracy using majority vote.

import argparse                              # Parses command-line arguments
import os                                    # File/path checks
import sys                                   # Exits cleanly on error
from collections import Counter              # Majority vote
from typing import List, Optional            # Type hints

import joblib                                # Loads the saved model
import pandas as pd                          # CSV loading + data handling


def majority_vote(values: List[str]) -> Optional[str]:
    """Return the most common value in a list (or None if empty)."""
    if not values:                           # If list is empty
        return None                          # No vote possible
    counts = Counter(values)                 # Count each label
    return counts.most_common(1)[0][0]        # Return the top label


def main() -> None:
    parser = argparse.ArgumentParser(description="Test a joblib ML model on sensor CSV data.")
    parser.add_argument("--data", required=True, help="Path to CSV file with sensor rows + labels.")
    parser.add_argument("--model", default="ml/artifacts/model.joblib",
                        help="Path to saved model.joblib (default: ml/artifacts/model.joblib).")
    parser.add_argument("--window_s", type=float, default=5.0, help="Window size in seconds (default: 5).")

    # Column names (you can override if your CSV uses different names)
    parser.add_argument("--label_col", default="Label", help="Label column name (default: Label).")
    parser.add_argument("--ts_col", default=None,
                        help="Timestamp column name (optional). If provided, used for 5s windowing.")
    parser.add_argument("--feature_cols", default="Temperature,Humidity,Pressure,GasResistance",
                        help="Comma-separated feature columns (default: Temperature,Humidity,Pressure,GasResistance).")

    # If you do NOT have timestamps, you can fake time using a sampling rate
    parser.add_argument("--hz", type=float, default=None,
                        help="Sampling rate (rows per second). Used only if --ts_col is not provided.")

    args = parser.parse_args()               # Parse all args

    data_path = args.data                    # CSV path from CLI
    model_path = args.model                  # Model path from CLI

    if not os.path.exists(data_path):        # Ensure CSV exists
        print(f"ERROR: CSV not found: {data_path}")  # Print clear error
        sys.exit(1)                          # Exit with failure code

    if not os.path.exists(model_path):       # Ensure model exists
        print(f"ERROR: model not found: {model_path}")  # Print clear error
        sys.exit(1)                          # Exit with failure code

    # Turn "a,b,c" into ["a","b","c"]
    feature_cols = [c.strip() for c in args.feature_cols.split(",") if c.strip()]

    # Load CSV
    df = pd.read_csv(data_path)              # Read CSV into a DataFrame

    # Basic column checks
    missing = [c for c in feature_cols if c not in df.columns]  # Find missing feature columns
    if missing:                               # If any are missing
        print(f"ERROR: Missing feature columns in CSV: {missing}")  # Show which ones
        print(f"CSV columns are: {list(df.columns)}")               # Show what exists
        sys.exit(1)                           # Exit

    if args.label_col not in df.columns:     # Ensure label column exists
        print(f"ERROR: Missing label column '{args.label_col}' in CSV.")  # Print error
        print(f"CSV columns are: {list(df.columns)}")                      # Show columns
        sys.exit(1)                           # Exit

    # Load model
    model = joblib.load(model_path)          # Load joblib model

    # Build X and y
    X = df[feature_cols].copy()              # Feature matrix
    y_true = df[args.label_col].astype(str)  # Ground truth labels as strings

    # Predict per row
    y_pred = model.predict(X)                # Model predictions
    y_pred = pd.Series(y_pred).astype(str)   # Convert to string series

    # Row-level accuracy
    row_acc = (y_pred == y_true).mean()      # Fraction correct
    print(f"Row accuracy: {row_acc * 100:.2f}% ({int((y_pred == y_true).sum())}/{len(df)})")

    # Build a time column for windowing
    if args.ts_col is not None:              # If timestamp column is provided
        if args.ts_col not in df.columns:    # Ensure it exists
            print(f"ERROR: Timestamp column '{args.ts_col}' not found in CSV.")  # Error
            sys.exit(1)                      # Exit

        # Convert to pandas datetime
        ts = pd.to_datetime(df[args.ts_col], errors="coerce")  # Parse timestamps
        if ts.isna().any():                  # If parsing failed anywhere
            print("ERROR: Some timestamps could not be parsed. Fix the ts format or choose another column.")
            sys.exit(1)

        # Convert to seconds since start
        t0 = ts.min()                        # Start time
        t_sec = (ts - t0).dt.total_seconds() # Seconds from start

    else:
        # No timestamps: require a sampling rate to fake time
        if args.hz is None or args.hz <= 0:  # Validate sampling rate
            print("ERROR: Provide either --ts_col <timestamp_column> OR --hz <rows_per_second> for 5s windows.")
            sys.exit(1)

        # Fake time: 0, 1/hz, 2/hz, ...
        t_sec = pd.Series(range(len(df)), dtype=float) / float(args.hz)

    # Assign a window id: floor(time / window_s)
    window_id = (t_sec / float(args.window_s)).astype(int)      # Window bucket per row

    # Compute window-level majority labels
    window_true = []                         # True label per window
    window_pred = []                         # Pred label per window

    for wid, group_idx in df.groupby(window_id).groups.items(): # Iterate window groups
        idx = list(group_idx)               # Row indices in this window

        # Majority label in that window (true)
        true_vote = majority_vote(list(y_true.iloc[idx]))       # Majority of y_true
        pred_vote = majority_vote(list(y_pred.iloc[idx]))       # Majority of y_pred

        if true_vote is None or pred_vote is None:              # Safety check
            continue                                            # Skip weird empty window

        window_true.append(true_vote)                           # Store window true label
        window_pred.append(pred_vote)                           # Store window predicted label

    if len(window_true) == 0:               # If no windows built
        print("Window accuracy: N/A (no windows computed)")
        return

    # Window accuracy
    w_true = pd.Series(window_true)          # True window labels
    w_pred = pd.Series(window_pred)          # Pred window labels
    win_acc = (w_true == w_pred).mean()      # Fraction correct at window level
    print(f"Window accuracy ({args.window_s:.1f}s): {win_acc * 100:.2f}% ({int((w_true == w_pred).sum())}/{len(w_true)})")


if __name__ == "__main__":
    main()                                   # Run main