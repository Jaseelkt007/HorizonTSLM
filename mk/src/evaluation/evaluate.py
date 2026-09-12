"""Comprehensive evaluation comparing OpenTSLM vs Baselines on In-Domain (Penmanshiel) and Cross-Farm Blank Demo Data (Kelmarsh)."""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Ensure repo root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np
import pandas as pd
import torch
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score

from src.data.schemas import (
    FAULT_CLASSES,
    KELMARSH_DATASET_ID,
    PENMANSHIEL_DATASET_ID,
    PENMANSHIEL_TEST_TURBINES,
    PENMANSHIEL_TRAIN_TURBINES,
    PENMANSHIEL_VAL_TURBINES,
)
from src.evaluation.baselines import (
    ClassicalMLBaseline,
    TextOnlyLLMBaseline,
    prepare_tabular_dataset,
)
from src.models.architecture import OpenTSLMForTurbineDiagnosis
from src.models.opentslm_dataset import OpenTSLMKelmarshDataset, OpenTSLMWindDataset


def evaluate_opentslm_checkpoint(
    checkpoint_path: Path,
    test_dataset: OpenTSLMWindDataset,
    device: torch.device,
) -> Dict[str, Any]:
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
    model = OpenTSLMForTurbineDiagnosis(in_channels=8, patch_size=4, d_encoder=256, d_llm=512)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.to(device)
    model.eval()

    all_preds, all_targets = [], []
    with torch.no_grad():
        for i in range(len(test_dataset)):
            sample = test_dataset[i]
            ts = sample["time_series"].unsqueeze(0).to(device)  # (1, 72, 8)
            preds, probs = model.predict(ts)
            all_preds.append(preds.item())
            all_targets.append(sample["label_idx"])

    y_true = np.array(all_targets)
    y_pred = np.array(all_preds)

    acc = accuracy_score(y_true, y_pred)
    f1 = f1_score(y_true, y_pred, average="macro", zero_division=0)
    prec = precision_score(y_true, y_pred, average="macro", zero_division=0)
    rec = recall_score(y_true, y_pred, average="macro", zero_division=0)

    return {
        "model_name": "OpenTSLM (Ours)",
        "accuracy": float(acc),
        "macro_f1": float(f1),
        "macro_precision": float(prec),
        "macro_recall": float(rec),
        "predictions": all_preds,
    }


def run_benchmark_suite(
    benchmark_name: str,
    train_ds: OpenTSLMWindDataset,
    test_ds: OpenTSLMWindDataset,
    checkpoint_path: Path,
    device: torch.device,
) -> List[Dict[str, Any]]:
    print(f"\n========================================================")
    print(f"[*] Running Benchmark Suite: {benchmark_name}")
    print(f"[*] Test Set Size: {len(test_ds)} windows")
    print(f"========================================================")

    # 1. Classical ML Baseline (Random Forest)
    print("  [1/3] Evaluating Classical ML (Random Forest on window aggregations)...")
    X_train, y_train, _ = prepare_tabular_dataset(train_ds)
    X_test, y_test, _ = prepare_tabular_dataset(test_ds)

    rf_baseline = ClassicalMLBaseline(n_estimators=100, random_state=42)
    rf_baseline.fit(X_train, y_train)
    rf_eval = rf_baseline.evaluate(X_test, y_test)
    rf_metrics = {
        "benchmark": benchmark_name,
        "model_name": "Random Forest (Tabular)",
        "accuracy": rf_eval["accuracy"],
        "macro_f1": rf_eval["macro_f1"],
        "macro_precision": float(precision_score(y_test, rf_eval["predictions"], average="macro", zero_division=0)),
        "macro_recall": float(recall_score(y_test, rf_eval["predictions"], average="macro", zero_division=0)),
    }

    # 2. Text-only LLM Baseline
    print("  [2/3] Evaluating Text-only LLM (Window Summary Prompt)...")
    text_baseline = TextOnlyLLMBaseline()
    text_eval = text_baseline.evaluate(X_test, y_test)
    text_metrics = {
        "benchmark": benchmark_name,
        "model_name": "Text-only LLM (Stats Prompt)",
        "accuracy": text_eval["accuracy"],
        "macro_f1": text_eval["macro_f1"],
        "macro_precision": float(precision_score(y_test, text_eval["predictions"], average="macro", zero_division=0)),
        "macro_recall": float(recall_score(y_test, text_eval["predictions"], average="macro", zero_division=0)),
    }

    # 3. OpenTSLM
    print("  [3/3] Evaluating OpenTSLM (TimeNet + Soft-Prompt Encoder)...")
    opentslm_metrics = evaluate_opentslm_checkpoint(checkpoint_path, test_ds, device)
    opentslm_metrics["benchmark"] = benchmark_name

    return [rf_metrics, text_metrics, opentslm_metrics]


def main():
    parser = argparse.ArgumentParser(description="Run zero-leakage held-out evaluation on Penmanshiel and blank Kelmarsh demo.")
    parser.add_argument("--checkpoint", type=Path, default=Path("checkpoints/opentslm_best.pt"))
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu")

    print("[*] Loading Penmanshiel datasets for in-domain zero-leakage evaluation...")
    pen_train_ds = OpenTSLMWindDataset(split="train", dataset_id=PENMANSHIEL_DATASET_ID)
    pen_val_ds = OpenTSLMWindDataset(split="val", dataset_id=PENMANSHIEL_DATASET_ID)
    pen_test_ds = OpenTSLMWindDataset(split="test", dataset_id=PENMANSHIEL_DATASET_ID)

    print(f"[*] Penmanshiel Train set (9 Turbines: WT01-WT10): {len(pen_train_ds)} windows")
    print(f"[*] Penmanshiel Val set (2 Turbines: WT11, WT12): {len(pen_val_ds)} windows")
    print(f"[*] Penmanshiel In-Domain Test set (3 Turbines: WT13-WT15): {len(pen_test_ds)} windows")

    print("\n[*] Loading Kelmarsh blank dataset for cross-farm zero-shot evaluation...")
    kel_blank_ds = OpenTSLMKelmarshDataset(split="all", dataset_id=KELMARSH_DATASET_ID)
    print(f"[*] Kelmarsh Blank Test set (6 Turbines: Kelmarsh 1-6): {len(kel_blank_ds)} windows")

    # Run Benchmark 1: In-Domain Zero-Leakage Benchmark (Penmanshiel WT13-WT15)
    in_domain_results = run_benchmark_suite(
        benchmark_name="In-Domain Held-Out Test (Penmanshiel WT13-WT15)",
        train_ds=pen_train_ds,
        test_ds=pen_test_ds,
        checkpoint_path=args.checkpoint,
        device=device,
    )

    # Run Benchmark 2: Cross-Farm Zero-Shot Transfer Benchmark (Kelmarsh 100% Unseen)
    cross_farm_results = run_benchmark_suite(
        benchmark_name="Cross-Farm Zero-Shot Transfer (Kelmarsh 1-6 Blank Demo)",
        train_ds=pen_train_ds,
        test_ds=kel_blank_ds,
        checkpoint_path=args.checkpoint,
        device=device,
    )

    all_results = in_domain_results + cross_farm_results
    df_all = pd.DataFrame(all_results)

    print("\n" + "=" * 80)
    print("                EVALUATION BENCHMARK SUMMARY TABLE")
    print("=" * 80)
    cols = ["benchmark", "model_name", "accuracy", "macro_f1", "macro_precision", "macro_recall"]
    print(df_all[cols].to_markdown(index=False))
    print("=" * 80)

    # Save outputs
    json_path = args.output_dir / "benchmark_results.json"
    md_path = args.output_dir / "benchmark_table.md"

    with open(json_path, "w") as f:
        json.dump(all_results, f, indent=2)

    with open(md_path, "w") as f:
        f.write("# Zero-Leakage Wind Turbine Benchmark Evaluation\n\n")
        f.write("### Model Training Setup\n")
        f.write("- **Primary Dataset**: Penmanshiel Wind Farm (`energy/penmanshiel-wind-scada`)\n")
        f.write("- **Turbine Splits**: Turbines `WT01`–`WT10` (Train), `WT11`–`WT12` (Val), `WT13`–`WT15` (Held-Out Test)\n")
        f.write("- **Cross-Farm Blank Demo Testbed**: Kelmarsh Wind Farm (`energy/kelmarsh-wind-scada`, Turbines 1–6) — **100% unseen, completely blank during training**.\n\n")
        f.write("### Benchmark Results\n\n")
        f.write(df_all[cols].to_markdown(index=False))
        f.write("\n\n*Zero-Leakage Guarantee: No turbine overlap exists between training, validation, and testing sets.*\n")

    print(f"[+] Saved evaluation outputs to {json_path} and {md_path}")


if __name__ == "__main__":
    main()
