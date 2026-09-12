"""Score prediction JSONL files against the committed benchmark window tables."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix, f1_score, roc_auc_score, roc_curve

IGNORED_EVALUATION_LABELS = {"brake_hydraulics"}


def recall_at_false_alarm_rate(
    y_true: np.ndarray, scores: np.ndarray, far: float = 0.10
) -> float:
    """Highest achievable recall at or below ``far`` false-positive rate."""
    if len(np.unique(y_true)) < 2:
        return float("nan")
    fpr, tpr, _ = roc_curve(y_true, scores)
    eligible = tpr[fpr <= far]
    return float(eligible.max()) if len(eligible) else 0.0


def score_predictions(
    labels: pd.DataFrame, predictions: pd.DataFrame
) -> dict[str, object]:
    required = {"window_id", "pred_label", "score_positive"}
    missing = required - set(predictions.columns)
    if missing:
        raise ValueError(f"Prediction file misses columns: {sorted(missing)}")
    if predictions.window_id.duplicated().any():
        raise ValueError("Prediction file has duplicate window_id values")

    merged = labels[["window_id", "horizon_h", "label", "is_positive"]].merge(
        predictions[list(required)], on="window_id", how="left", validate="one_to_one"
    )
    if merged.pred_label.isna().any():
        raise ValueError(
            f"Missing predictions for {merged.pred_label.isna().sum()} windows"
        )
    if len(merged) != len(predictions):
        raise ValueError(
            "Prediction file contains window_ids outside the requested split"
        )

    def one(group: pd.DataFrame) -> dict[str, object]:
        y_binary = group.is_positive.astype(int).to_numpy()
        scores = group.score_positive.astype(float).to_numpy()
        confusion_labels = [
            "none",
            *sorted(label for label in group.label.unique() if label != "none"),
        ]
        positive_labels = sorted(
            label
            for label in group.label.unique()
            if label != "none" and label not in IGNORED_EVALUATION_LABELS
        )
        return {
            "n": len(group),
            "positives": int(y_binary.sum()),
            "auroc": float(roc_auc_score(y_binary, scores))
            if len(np.unique(y_binary)) == 2
            else float("nan"),
            "recall_at_10pct_far": recall_at_false_alarm_rate(y_binary, scores),
            "macro_f1_positive": float(
                f1_score(
                    group.label,
                    group.pred_label,
                    labels=positive_labels,
                    average="macro",
                    zero_division=0,
                )
            )
            if positive_labels
            else float("nan"),
            "labels": confusion_labels,
            "confusion_matrix": confusion_matrix(
                group.label, group.pred_label, labels=confusion_labels
            ).tolist(),
        }

    return {
        "overall": one(merged),
        "by_horizon_h": {str(h): one(g) for h, g in merged.groupby("horizon_h")},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--windows", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--split",
        help="Optional split to score from a multi-split parquet table (for example test_a).",
    )
    args = parser.parse_args()
    labels = pd.read_parquet(args.windows)
    if args.split:
        labels = labels[labels["split"] == args.split]
        if labels.empty:
            raise ValueError(f"No rows with split={args.split!r} in {args.windows}")
    predictions = pd.read_json(args.predictions, lines=True)
    metrics = score_predictions(labels, predictions)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(metrics, indent=2, allow_nan=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
