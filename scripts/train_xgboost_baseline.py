"""Train leakage-safe XGBoost baselines on the committed SCADA window tables.

Models: context_only (the currently available logs-only proxy), sensors_only,
and combined.  True logs-only needs pre-anchor alarm/status history, which the
window parquet intentionally does not include.
"""

from __future__ import annotations

import argparse
import json
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.preprocessing import OneHotEncoder
from xgboost import XGBClassifier

from turbine_tslm.data.channels import CHANNEL_NAMES
from turbine_tslm.eval.score import recall_at_false_alarm_rate, score_predictions

SEGMENTS = {"1h": 6, "6h": 36, "24h": 144}


def _slope(values: np.ndarray) -> np.ndarray:
    x = np.arange(values.shape[1], dtype=float)
    x -= x.mean()
    return (values * x).sum(axis=1) / (x * x).sum()


def sensor_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Requested window-only statistics; no label or post-anchor field is read."""
    columns: dict[str, np.ndarray] = {}
    arrays = {
        channel: np.stack(frame[channel].to_list()).astype(float)
        for channel in CHANNEL_NAMES
    }
    for channel, values in arrays.items():
        for name, width in SEGMENTS.items():
            window = values[:, -width:]
            columns[f"{channel}_{name}_mean"] = window.mean(axis=1)
            columns[f"{channel}_{name}_std"] = window.std(axis=1)
            columns[f"{channel}_{name}_min"] = window.min(axis=1)
            columns[f"{channel}_{name}_max"] = window.max(axis=1)
            columns[f"{channel}_{name}_slope"] = _slope(window)
        columns[f"{channel}_last_minus_first"] = values[:, -1] - values[:, 0]
    ambient = arrays["ambient_temperature"]
    for channel, values in arrays.items():
        if channel == "ambient_temperature" or "temperature" not in channel:
            continue
        difference = values - ambient
        for name, width in SEGMENTS.items():
            window = difference[:, -width:]
            columns[f"{channel}_minus_ambient_{name}_mean"] = window.mean(axis=1)
            columns[f"{channel}_minus_ambient_{name}_slope"] = _slope(window)
    return (
        pd.DataFrame(columns, index=frame.index)
        .replace([np.inf, -np.inf], np.nan)
        .fillna(0.0)
    )


def context_features(
    frame: pd.DataFrame, encoder: OneHotEncoder | None = None
) -> tuple[np.ndarray, OneHotEncoder]:
    anchor = pd.to_datetime(frame.anchor, utc=True)
    raw = pd.DataFrame(
        {
            "state_at_anchor": frame.state_at_anchor.astype(str),
            "month": anchor.dt.month.astype(str),
            "horizon_h": frame.horizon_h.astype(str),
        }
    )
    if encoder is None:
        encoder = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
        return encoder.fit_transform(raw), encoder
    return encoder.transform(raw), encoder


def make_features(
    frame: pd.DataFrame, kind: str, encoder: OneHotEncoder | None = None
) -> tuple[np.ndarray, OneHotEncoder | None]:
    context, encoder = context_features(frame, encoder)
    if kind == "context_only":
        return context, encoder
    sensors = sensor_features(frame).to_numpy(dtype=float)
    if kind == "sensors_only":
        return sensors, encoder
    return np.hstack([sensors, context]), encoder


def classifier(
    params: dict[str, int], objective: str, num_class: int | None = None
) -> XGBClassifier:
    options: dict[str, object] = dict(
        **params,
        random_state=42,
        n_jobs=1,
        tree_method="hist",
        eval_metric="logloss",
        objective=objective,
    )
    if num_class is not None:
        options["num_class"] = num_class
    return XGBClassifier(**options)


def choose_params(
    X_train: np.ndarray, y_train: np.ndarray, X_val: np.ndarray, y_val: np.ndarray
) -> dict[str, int]:
    candidates = [
        {
            "max_depth": depth,
            "learning_rate": rate,
            "n_estimators": 250,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
        }
        for depth, rate in product((2, 3), (0.03, 0.08))
    ]
    scored = []
    for params in candidates:
        model = classifier(params, "binary:logistic")
        model.fit(X_train, y_train)
        score = model.predict_proba(X_val)[:, 1]
        scored.append((recall_at_false_alarm_rate(y_val, score), params))
    return max(scored, key=lambda item: item[0])[1]


def predictions(
    frame: pd.DataFrame,
    X: np.ndarray,
    binary: XGBClassifier,
    multi: XGBClassifier,
    class_names: np.ndarray,
    model_name: str,
) -> pd.DataFrame:
    probabilities = multi.predict_proba(X)
    return pd.DataFrame(
        {
            "window_id": frame.window_id,
            "pred_label": class_names[probabilities.argmax(axis=1)],
            "score_positive": binary.predict_proba(X)[:, 1],
            "model": model_name,
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model", choices=("context_only", "sensors_only", "combined"), required=True
    )
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/predictions"))
    args = parser.parse_args()
    pen = pd.read_parquet("data/interim/penmanshiel_windows.parquet")
    kel = pd.read_parquet("data/interim/kelmarsh_windows.parquet")
    train, val = pen[pen.split == "train"], pen[pen.split == "val"]
    X_train, encoder = make_features(train, args.model)
    X_val, _ = make_features(val, args.model, encoder)
    params = choose_params(
        X_train,
        train.is_positive.astype(int).to_numpy(),
        X_val,
        val.is_positive.astype(int).to_numpy(),
    )
    # Refit only after the val-selected hyperparameters are frozen.
    fit = pd.concat([train, val], ignore_index=True)
    X_fit, fit_encoder = make_features(fit, args.model)
    binary = classifier(params, "binary:logistic").fit(
        X_fit, fit.is_positive.astype(int)
    )
    class_names, y_multi = np.unique(fit.label.to_numpy(), return_inverse=True)
    multi = classifier(params, "multi:softprob", len(class_names)).fit(X_fit, y_multi)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    summary: dict[str, object] = {
        "model": args.model,
        "selected_on_val": params,
        "splits": {},
    }
    for split, data in {"test_a": pen[pen.split == "test_a"], "test_b": kel}.items():
        X_test, _ = make_features(data, args.model, fit_encoder)
        pred = predictions(
            data, X_test, binary, multi, class_names, f"xgb_{args.model}_v1"
        )
        path = args.output_dir / f"xgb_{args.model}_v1_{split}.jsonl"
        pred.to_json(path, orient="records", lines=True)
        summary["splits"][split] = score_predictions(data, pred)
    metrics_path = args.output_dir.parent / f"xgb_{args.model}_v1_metrics.json"
    metrics_path.write_text(
        json.dumps(summary, indent=2, allow_nan=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, allow_nan=True))


if __name__ == "__main__":
    main()
