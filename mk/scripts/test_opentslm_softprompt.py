"""Full evaluation and analysis script for OpenTSLM-SoftPrompt.

Evaluates both:
1. In-Domain Held-Out Test Set: Penmanshiel WT13-WT15 (90 samples)
2. Cross-Farm Zero-Shot Transfer: Kelmarsh 1-6 (180 samples)

Assesses:
- Discrete Subsystem Classification Head (Accuracy, Macro F1, Per-Class F1, Confusion Matrix)
- Generative Language Model Head (Triage, Subsystem Extraction, CoT Diagnostic Quality)
- Error Analysis: What is predicted correctly vs. incorrectly, and why.
"""

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score, precision_score, recall_score
from torch.utils.data import DataLoader
from transformers import GPT2Tokenizer

# Add repo root and mk to sys.path
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "mk"))

from mk.src.data.schemas import (
    KELMARSH_DATASET_ID,
    PENMANSHIEL_DATASET_ID,
    SUBSYSTEM_CLASSES,
)
from mk.src.models.architecture import OpenTSLMSoftPromptForTurbineDiagnosis
from mk.src.models.opentslm_dataset import OpenTSLMSoftPromptDataCollator, OpenTSLMWindDataset


def evaluate_dataset(
    model: OpenTSLMSoftPromptForTurbineDiagnosis,
    dataset: OpenTSLMWindDataset,
    tokenizer: GPT2Tokenizer,
    device: torch.device,
    dataset_name: str,
    max_generations: int = 90,
    batch_size: int = 16,
) -> dict:
    print(f"\n{'='*80}")
    print(f"[*] EVALUATING: {dataset_name} (Total samples: {len(dataset)})")
    print(f"{'='*80}")

    collator = OpenTSLMSoftPromptDataCollator(tokenizer=tokenizer)
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=False, collate_fn=collator)

    # -------------------------------------------------------------
    # 1. Batched Classification Head Evaluation
    # -------------------------------------------------------------
    model.eval()
    all_targets = []
    all_preds_cls = []
    all_probs = []
    all_records = []

    with torch.no_grad():
        for batch in loader:
            time_series = batch["time_series"].to(device)
            targets = batch["label_indices"].to(device)

            outputs = model(time_series)
            logits = outputs["cls_logits"]
            probs = torch.softmax(logits, dim=-1)

            preds = torch.argmax(logits, dim=-1).cpu().numpy()
            all_preds_cls.extend(preds)
            all_targets.extend(targets.cpu().numpy())
            all_probs.extend(probs.cpu().numpy())

    all_targets = np.array(all_targets)
    all_preds_cls = np.array(all_preds_cls)

    acc_cls = accuracy_score(all_targets, all_preds_cls)
    f1_macro_cls = f1_score(all_targets, all_preds_cls, average="macro", zero_division=0)
    f1_weighted_cls = f1_score(all_targets, all_preds_cls, average="weighted", zero_division=0)

    print(f"\n--- [1] Classification Head Performance ---")
    print(f"Accuracy:        {acc_cls:.2%}")
    print(f"Macro F1:        {f1_macro_cls:.4f}")
    print(f"Weighted F1:     {f1_weighted_cls:.4f}")

    # Unique classes present in target
    unique_present_targets = sorted(list(set(all_targets)))
    target_names = [SUBSYSTEM_CLASSES[i] for i in unique_present_targets]

    cls_report = classification_report(
        all_targets,
        all_preds_cls,
        labels=unique_present_targets,
        target_names=target_names,
        digits=4,
        output_dict=True,
        zero_division=0,
    )
    print("\nClassification Report (Head):")
    print(classification_report(
        all_targets,
        all_preds_cls,
        labels=unique_present_targets,
        target_names=target_names,
        digits=4,
        zero_division=0,
    ))

    # Confusion matrix
    cm = confusion_matrix(all_targets, all_preds_cls, labels=range(len(SUBSYSTEM_CLASSES)))

    # -------------------------------------------------------------
    # 2. Generative CoT Diagnosis Evaluation
    # -------------------------------------------------------------
    print(f"\n--- [2] Generative Language Model Evaluation (Generating CoT Diagnoses) ---")
    gen_limit = min(len(dataset), max_generations)
    print(f"Generating Chain-of-Thought diagnosis for {gen_limit} samples...")

    gen_preds_subsystem = []
    gen_preds_triage = []
    ground_truth_triages = []
    generated_texts = []
    sample_details = []

    t0 = time.time()
    for i in range(gen_limit):
        item = dataset[i]
        ts = item["time_series"].unsqueeze(0).to(device)
        gt_idx = item["label_idx"]
        gt_class = item["label_name"]
        gt_triage = "normal" if gt_class == "normal_operation" else "fault"
        ground_truth_triages.append(gt_triage)

        diag = model.generate_diagnosis(
            time_series=ts,
            tokenizer=tokenizer,
            max_new_tokens=90,
            temperature=0.0,  # Greedy for reproducible evaluation
        )

        parsed_sub = diag["parsed_subsystem"]
        parsed_tri = diag["parsed_triage"]
        gen_text = diag["generated_text"]

        # Map parsed subsystem to index if possible
        if parsed_sub in SUBSYSTEM_CLASSES:
            parsed_idx = SUBSYSTEM_CLASSES.index(parsed_sub)
        else:
            parsed_idx = diag["cls_pred_idx"]  # fallback

        gen_preds_subsystem.append(parsed_idx)
        gen_preds_triage.append(parsed_tri)
        generated_texts.append(gen_text)

        correct_cls = (all_preds_cls[i] == gt_idx)
        correct_gen = (parsed_idx == gt_idx)
        correct_triage = (parsed_tri.lower() == gt_triage.lower())

        sample_details.append({
            "sample_index": i,
            "turbine_id": item["turbine_id"],
            "ground_truth_idx": int(gt_idx),
            "ground_truth_class": gt_class,
            "ground_truth_triage": gt_triage,
            "cls_head_pred_idx": int(all_preds_cls[i]),
            "cls_head_pred_class": SUBSYSTEM_CLASSES[all_preds_cls[i]],
            "gen_pred_idx": int(parsed_idx),
            "gen_pred_class": SUBSYSTEM_CLASSES[parsed_idx],
            "gen_pred_triage": parsed_tri,
            "cls_correct": bool(correct_cls),
            "gen_correct": bool(correct_gen),
            "triage_correct": bool(correct_triage),
            "generated_text": gen_text,
            "actual_rationale": item.get("rationale", ""),
            "actual_action": item.get("action", ""),
        })

        if (i + 1) % 25 == 0 or (i + 1) == gen_limit:
            elapsed = time.time() - t0
            print(f"  Processed {i+1}/{gen_limit} samples ({elapsed:.1f}s, {elapsed/(i+1):.2f}s/sample)...")

    gen_targets = all_targets[:gen_limit]
    gen_preds_subsystem = np.array(gen_preds_subsystem)

    acc_gen = accuracy_score(gen_targets, gen_preds_subsystem)
    f1_macro_gen = f1_score(gen_targets, gen_preds_subsystem, average="macro", zero_division=0)
    acc_triage = np.mean([1 if p.lower() == g.lower() else 0 for p, g in zip(gen_preds_triage, ground_truth_triages)])

    print(f"\n--- Generative Output Performance ---")
    print(f"Generative Subsystem Accuracy: {acc_gen:.2%}")
    print(f"Generative Macro F1:          {f1_macro_gen:.4f}")
    print(f"Operational Triage Accuracy:   {acc_triage:.2%}")

    # Agreement between classification head and generative head
    agreement = np.mean(all_preds_cls[:gen_limit] == gen_preds_subsystem)
    print(f"Dual-Head Decision Agreement:  {agreement:.2%}")

    # -------------------------------------------------------------
    # 3. Detailed Breakdown: What is predicted correctly vs incorrectly
    # -------------------------------------------------------------
    correct_samples = [s for s in sample_details if s["cls_correct"]]
    incorrect_samples = [s for s in sample_details if not s["cls_correct"]]

    print(f"\n{'*'*60}")
    print(f"SUMMARY OF WHAT IS PREDICTED CORRECTLY ({len(correct_samples)} / {gen_limit} = {len(correct_samples)/gen_limit:.1%}):")
    print(f"{'*'*60}")
    correct_by_class = Counter([s["ground_truth_class"] for s in correct_samples])
    total_by_class = Counter([s["ground_truth_class"] for s in sample_details])

    for cls_name, total_cnt in total_by_class.most_common():
        corr_cnt = correct_by_class.get(cls_name, 0)
        rec = corr_cnt / total_cnt if total_cnt > 0 else 0.0
        print(f"  - {cls_name:24s}: {corr_cnt:2d}/{total_cnt:2d} correctly predicted ({rec:.1%})")

    print(f"\n{'*'*60}")
    print(f"SUMMARY OF WHAT IS NOT PREDICTED CORRECTLY ({len(incorrect_samples)} / {gen_limit} = {len(incorrect_samples)/gen_limit:.1%}):")
    print(f"{'*'*60}")
    confusion_pairs = Counter([(s["ground_truth_class"], s["cls_head_pred_class"]) for s in incorrect_samples])
    for (gt, pred), cnt in confusion_pairs.most_common():
        print(f"  - Ground Truth '{gt}' MISPREDICTED as '{pred}': {cnt} times")

    return {
        "dataset_name": dataset_name,
        "total_samples": len(dataset),
        "evaluated_samples": gen_limit,
        "classification_head": {
            "accuracy": float(acc_cls),
            "macro_f1": float(f1_macro_cls),
            "weighted_f1": float(f1_weighted_cls),
            "per_class": cls_report,
        },
        "generative_head": {
            "accuracy": float(acc_gen),
            "macro_f1": float(f1_macro_gen),
            "triage_accuracy": float(acc_triage),
            "dual_head_agreement": float(agreement),
        },
        "confusion_matrix": cm.tolist(),
        "class_breakdown": {
            cls_name: {
                "total": int(total_by_class.get(cls_name, 0)),
                "correct": int(correct_by_class.get(cls_name, 0)),
                "recall": float(correct_by_class.get(cls_name, 0) / total_by_class[cls_name]) if total_by_class.get(cls_name, 0) > 0 else 0.0,
            }
            for cls_name in total_by_class
        },
        "confusion_pairs": {f"{gt} -> {pred}": count for (gt, pred), count in confusion_pairs.items()},
        "sample_details": sample_details,
    }


def main():
    parser = argparse.ArgumentParser(description="Full test of OpenTSLM-SoftPrompt")
    parser.add_argument("--checkpoint", type=str, default="checkpoints/opentslm_softprompt_best.pt")
    parser.add_argument("--device", type=str, default=None)
    parser.add_argument("--max-eval-samples", type=int, default=90)
    args = parser.parse_args()

    if args.device:
        device = torch.device(args.device)
    elif torch.backends.mps.is_available():
        device = torch.device("mps")
    elif torch.cuda.is_available():
        device = torch.device("cuda")
    else:
        device = torch.device("cpu")

    print(f"[*] Running OpenTSLM-SoftPrompt Full Test on Device: {device}")
    print(f"[*] Checkpoint: {args.checkpoint}")

    tokenizer = GPT2Tokenizer.from_pretrained("openai-community/gpt2")
    tokenizer.pad_token = tokenizer.eos_token

    model = OpenTSLMSoftPromptForTurbineDiagnosis(
        in_channels=11,
        patch_size=4,
        d_encoder=256,
        d_llm=768,
        num_classes=len(SUBSYSTEM_CLASSES),
        llm_model_name="openai-community/gpt2",
    )

    ckpt_path = Path(args.checkpoint)
    if not ckpt_path.exists():
        ckpt_path = Path("mk") / args.checkpoint
    checkpoint = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    model.load_state_dict(checkpoint["model_state_dict"])
    if "calibrated_threshold" in checkpoint:
        model.anomaly_threshold = checkpoint["calibrated_threshold"]
        print(f"[*] Loaded calibrated anomaly threshold tau* = {model.anomaly_threshold:.4f}")
    model.to(device)
    model.eval()

    print(f"[+] Loaded model checkpoint from {ckpt_path} (Trained Epoch {checkpoint.get('epoch')})")

    # 1. In-Domain Held-Out Test Set (Penmanshiel WT13-WT15)
    penmanshiel_test = OpenTSLMWindDataset(
        split="test",
        dataset_id=PENMANSHIEL_DATASET_ID,
        target_mode="subsystem",
    )
    penmanshiel_results = evaluate_dataset(
        model=model,
        dataset=penmanshiel_test,
        tokenizer=tokenizer,
        device=device,
        dataset_name="Penmanshiel Held-Out Test Set (Turbines WT13-WT15)",
        max_generations=90,  # All 90 samples
    )

    # 2. Cross-Farm Held-Out Test Set (Kelmarsh 1-6)
    kelmarsh_test = OpenTSLMWindDataset(
        split="all",
        dataset_id=KELMARSH_DATASET_ID,
        target_mode="subsystem",
    )
    kelmarsh_results = evaluate_dataset(
        model=model,
        dataset=kelmarsh_test,
        tokenizer=tokenizer,
        device=device,
        dataset_name="Kelmarsh Cross-Farm Zero-Shot Transfer (Turbines 1-6)",
        max_generations=args.max_eval_samples,  # Evaluate up to 90 or user-specified samples
    )

    # Save full JSON output
    out_dir = Path("mk/results")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "opentslm_softprompt_full_evaluation.json"

    with open(out_file, "w") as f:
        json.dump(
            {
                "checkpoint": str(ckpt_path),
                "trained_epoch": checkpoint.get("epoch"),
                "penmanshiel_held_out": penmanshiel_results,
                "kelmarsh_transfer": kelmarsh_results,
            },
            f,
            indent=2,
        )

    print(f"\n[+] Full test report saved to {out_file}")


if __name__ == "__main__":
    main()
