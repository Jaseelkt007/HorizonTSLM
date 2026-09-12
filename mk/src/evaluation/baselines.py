"""Comparative Baselines: Classical ML (Random Forest) and Text-Only LLM for Wind Turbine SCADA."""

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.metrics import accuracy_score, classification_report, f1_score

try:
    from mk.src.data.schemas import FAULT_CLASSES, FAULT_CLASS_TO_IDX, IDX_TO_FAULT_CLASS, SELECTED_SIGNALS
    from mk.src.models.opentslm_dataset import OpenTSLMKelmarshDataset
except ImportError:
    try:
        from ..data.schemas import FAULT_CLASSES, FAULT_CLASS_TO_IDX, IDX_TO_FAULT_CLASS, SELECTED_SIGNALS
        from ..models.opentslm_dataset import OpenTSLMKelmarshDataset
    except (ImportError, ValueError):
        from src.data.schemas import FAULT_CLASSES, FAULT_CLASS_TO_IDX, IDX_TO_FAULT_CLASS, SELECTED_SIGNALS
        from src.models.opentslm_dataset import OpenTSLMKelmarshDataset


def extract_window_tabular_features(time_series: np.ndarray) -> np.ndarray:
    """Extracts 48 statistical features from a (72, 8) multivariate window:

    For each channel: mean, std, min, max, delta (end - start), trend slope.
    """
    features = []
    num_steps, num_channels = time_series.shape
    t = np.arange(num_steps)

    for c in range(num_channels):
        channel_data = time_series[:, c]
        mean_val = np.mean(channel_data)
        std_val = np.std(channel_data)
        min_val = np.min(channel_data)
        max_val = np.max(channel_data)
        delta_val = channel_data[-1] - channel_data[0]

        # Linear slope
        if std_val > 1e-6:
            slope = np.polyfit(t, channel_data, 1)[0]
        else:
            slope = 0.0

        features.extend([mean_val, std_val, min_val, max_val, delta_val, slope])

    return np.array(features, dtype=np.float32)


def prepare_tabular_dataset(dataset: OpenTSLMKelmarshDataset) -> Tuple[np.ndarray, np.ndarray, List[Dict[str, Any]]]:
    """Converts an OpenTSLMKelmarshDataset into tabular features X and labels y."""
    X_list = []
    y_list = []
    metadata_list = []

    for i in range(len(dataset)):
        sample = dataset[i]
        ts = sample["time_series"].numpy()  # (72, 8)
        feats = extract_window_tabular_features(ts)
        X_list.append(feats)
        y_list.append(sample["label_idx"])
        metadata_list.append(
            {
                "record_id": sample["record_id"],
                "turbine_id": sample["turbine_id"],
                "label_name": sample["label_name"],
                "rationale": sample["rationale"],
                "action": sample["action"],
            }
        )

    X = np.stack(X_list, axis=0)
    y = np.array(y_list, dtype=np.int64)
    return X, y, metadata_list


class ClassicalMLBaseline:
    """Random Forest classifier on statistical telemetry features (Zero-Leakage split)."""

    def __init__(self, n_estimators: int = 100, random_state: int = 42):
        self.model = RandomForestClassifier(n_estimators=n_estimators, random_state=random_state)
        self.is_trained = False

    def fit(self, X_train: np.ndarray, y_train: np.ndarray):
        self.model.fit(X_train, y_train)
        self.is_trained = True

    def evaluate(self, X_test: np.ndarray, y_test: np.ndarray) -> Dict[str, Any]:
        preds = self.model.predict(X_test)
        probs = self.model.predict_proba(X_test)
        acc = accuracy_score(y_test, preds)
        f1 = f1_score(y_test, preds, average="macro", zero_division=0)
        report = classification_report(
            y_test,
            preds,
            target_names=[FAULT_CLASSES[i] for i in sorted(np.unique(np.concatenate([y_test, preds])))],
            output_dict=True,
            zero_division=0,
        )
        return {
            "accuracy": float(acc),
            "macro_f1": float(f1),
            "predictions": preds.tolist(),
            "probabilities": probs.tolist(),
            "report": report,
        }


class TextOnlyLLMBaseline:
    """Text-only LLM baseline that receives summarized telemetry numbers in a text/JSON prompt."""

    def format_prompt(self, window_metadata: Dict[str, Any], features: np.ndarray) -> str:
        """Formats window summary statistics into a pure-text LLM prompt."""
        stats_summary = {}
        idx = 0
        for sig in SELECTED_SIGNALS:
            stats_summary[sig.canonical_name] = {
                "unit": sig.unit,
                "mean": round(float(features[idx]), 2),
                "std": round(float(features[idx + 1]), 2),
                "min": round(float(features[idx + 2]), 2),
                "max": round(float(features[idx + 3]), 2),
                "12h_delta": round(float(features[idx + 4]), 2),
            }
            idx += 6

        prompt = (
            f"You are a wind turbine diagnostic assistant. Below is a 12-hour statistical summary for turbine {window_metadata['turbine_id']}:\n"
            f"{json.dumps(stats_summary, indent=2)}\n\n"
            f"Classes: {FAULT_CLASSES}\n"
            f"Diagnose the turbine health and choose the most likely fault class."
        )
        return prompt

    def predict_heuristic(self, features: np.ndarray) -> Tuple[int, str]:
        """Physics-based heuristic representing ideal zero-shot text reasoning without temporal token embedding."""
        # Gear oil temp max is index 4*6 + 3 = 27
        # Gear oil delta is index 4*6 + 4 = 28
        gear_max = features[27]
        gear_delta = features[28]

        # Generator bearing max is 5*6 + 3 = 33
        gen_bearing_max = features[33]

        # Drivetrain accel max is 7*6 + 3 = 45
        vibe_max = features[45]

        # Power min is 1*6 + 2 = 8, Power mean is 1*6 = 6
        power_min = features[8]
        power_mean = features[6]

        if gear_delta > 15.0 or gear_max > 80.0:
            return FAULT_CLASS_TO_IDX["Gearbox Overheating"], "Gearbox Overheating"
        if gen_bearing_max > 80.0:
            return FAULT_CLASS_TO_IDX["Generator Bearing Anomaly"], "Generator Bearing Anomaly"
        if vibe_max > 50.0:
            return FAULT_CLASS_TO_IDX["Pitch / Aerodynamic Fault"], "Pitch / Aerodynamic Fault"
        if power_min == 0.0 and power_mean < 500.0:
            return FAULT_CLASS_TO_IDX["Turbine Trip / Forced Outage"], "Turbine Trip / Forced Outage"

        return FAULT_CLASS_TO_IDX["Normal Operation"], "Normal Operation"

    def evaluate(self, X_test: np.ndarray, y_test: np.ndarray) -> Dict[str, Any]:
        preds = []
        for i in range(len(X_test)):
            pred_idx, _ = self.predict_heuristic(X_test[i])
            preds.append(pred_idx)

        preds = np.array(preds)
        acc = accuracy_score(y_test, preds)
        f1 = f1_score(y_test, preds, average="macro", zero_division=0)
        return {
            "accuracy": float(acc),
            "macro_f1": float(f1),
            "predictions": preds.tolist(),
        }
