"""Training script for OpenTSLM on TimeNet SCADA data with class-balanced weighting."""

import argparse
import shutil
import sys
from pathlib import Path

# Ensure repo root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np
import torch
import torch.nn.functional as F
from sklearn.metrics import accuracy_score, f1_score
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR

from src.data.schemas import FAULT_CLASSES, PENMANSHIEL_DATASET_ID
from src.models.architecture import OpenTSLMForTurbineDiagnosis
from src.models.opentslm_dataset import get_dataloaders


def compute_class_weights(loader_or_dataset, num_classes: int, device: torch.device) -> torch.Tensor:
    """Compute smoothed inverse-frequency class weights for balanced focal loss."""
    if hasattr(loader_or_dataset, "dataset"):
        ds = loader_or_dataset.dataset
    else:
        ds = loader_or_dataset

    if hasattr(ds, "get_labels"):
        labels = ds.get_labels()
    elif hasattr(ds, "labels"):
        labels = list(ds.labels)
    else:
        labels = []
        for batch in loader_or_dataset:
            labels.extend(batch["label_indices"].numpy().tolist())

    counts = np.bincount(labels, minlength=num_classes)
    total = len(labels)
    
    # Smoothed inverse square-root weights: sqrt(total / (num_classes * max(counts, 1)))
    raw_w = np.sqrt(total / (num_classes * np.maximum(counts, 1).astype(float)))
    active_mask = counts > 0
    if np.any(active_mask):
        raw_w[active_mask] = raw_w[active_mask] / np.mean(raw_w[active_mask])
    # Clip to moderate range [0.6, 2.5] so normal operation is never starved
    weights = np.clip(raw_w, 0.6, 2.5)
    print(f"[*] Computed smoothed class weights: {np.round(weights, 2)}")
    return torch.tensor(weights, dtype=torch.float32, device=device)


def train_epoch(model, loader, optimizer, scheduler, device, class_weights=None):
    model.train()
    total_loss = 0.0
    all_preds, all_targets = [], []

    for batch in loader:
        time_series = batch["time_series"].to(device)
        targets = batch["label_indices"].to(device)

        optimizer.zero_grad()
        outputs = model(time_series, label_indices=targets, class_weights=class_weights)
        loss = outputs["loss"]
        loss.backward()

        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()
        if scheduler is not None:
            scheduler.step()

        total_loss += loss.item() * len(targets)
        preds = torch.argmax(outputs["logits"], dim=-1).cpu().numpy()
        all_preds.extend(preds)
        all_targets.extend(targets.cpu().numpy())

    epoch_loss = total_loss / len(loader.dataset)
    acc = accuracy_score(all_targets, all_preds)
    f1 = f1_score(all_targets, all_preds, average="macro", zero_division=0)
    return epoch_loss, acc, f1


@torch.no_grad()
def evaluate_model(model, loader, device, class_weights=None):
    model.eval()
    total_loss = 0.0
    all_preds, all_targets = [], []

    for batch in loader:
        time_series = batch["time_series"].to(device)
        targets = batch["label_indices"].to(device)

        outputs = model(time_series, label_indices=targets, class_weights=class_weights)
        loss = outputs["loss"]

        total_loss += loss.item() * len(targets)
        preds = torch.argmax(outputs["logits"], dim=-1).cpu().numpy()
        all_preds.extend(preds)
        all_targets.extend(targets.cpu().numpy())

    val_loss = total_loss / len(loader.dataset)
    acc = accuracy_score(all_targets, all_preds)
    f1 = f1_score(all_targets, all_preds, average="macro", zero_division=0)
    return val_loss, acc, f1


def train_epoch_softprompt(model, loader, optimizer, scheduler, device, class_weights=None):
    model.train()
    total_loss, total_cls_loss, total_lm_loss = 0.0, 0.0, 0.0
    all_preds, all_targets = [], []

    for batch in loader:
        time_series = batch["time_series"].to(device)
        targets = batch["label_indices"].to(device)
        input_ids = batch["input_ids"].to(device)
        attention_mask = batch["attention_mask"].to(device)
        labels = batch["labels"].to(device)

        optimizer.zero_grad()
        outputs = model(
            time_series=time_series,
            input_ids=input_ids,
            attention_mask=attention_mask,
            labels=labels,
            label_indices=targets,
            class_weights=class_weights,
        )
        loss = outputs["loss"]
        loss.backward()

        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()
        if scheduler is not None:
            scheduler.step()

        b_size = len(targets)
        total_loss += loss.item() * b_size
        total_cls_loss += outputs.get("cls_loss", torch.tensor(0.0)).item() * b_size
        total_lm_loss += outputs.get("lm_loss", torch.tensor(0.0)).item() * b_size

        preds = torch.argmax(outputs["cls_logits"], dim=-1).cpu().numpy()
        all_preds.extend(preds)
        all_targets.extend(targets.cpu().numpy())

    n = len(loader.dataset)
    return (
        total_loss / n,
        total_cls_loss / n,
        total_lm_loss / n,
        accuracy_score(all_targets, all_preds),
        f1_score(all_targets, all_preds, average="macro", zero_division=0),
    )


@torch.no_grad()
def evaluate_model_softprompt(model, loader, device, class_weights=None):
    model.eval()
    total_loss, total_cls_loss, total_lm_loss = 0.0, 0.0, 0.0
    all_preds, all_targets = [], []
    all_anomaly_probs = []

    for batch in loader:
        time_series = batch["time_series"].to(device)
        targets = batch["label_indices"].to(device)
        input_ids = batch["input_ids"].to(device)
        attention_mask = batch["attention_mask"].to(device)
        labels = batch["labels"].to(device)

        outputs = model(
            time_series=time_series,
            input_ids=input_ids,
            attention_mask=attention_mask,
            labels=labels,
            label_indices=targets,
            class_weights=class_weights,
        )
        loss = outputs["loss"]

        b_size = len(targets)
        total_loss += loss.item() * b_size
        total_cls_loss += outputs.get("cls_loss", torch.tensor(0.0)).item() * b_size
        total_lm_loss += outputs.get("lm_loss", torch.tensor(0.0)).item() * b_size

        if "triage_logits" in outputs:
            triage_probs = F.softmax(outputs["triage_logits"], dim=-1)
            anom_p = triage_probs[:, 1].cpu().numpy()
        else:
            cls_probs = F.softmax(outputs["cls_logits"], dim=-1)
            anom_p = 1.0 - cls_probs[:, 0].cpu().numpy()
        all_anomaly_probs.extend(anom_p)

        preds = torch.argmax(outputs["cls_logits"], dim=-1).cpu().numpy()
        all_preds.extend(preds)
        all_targets.extend(targets.cpu().numpy())

    n = len(loader.dataset)
    normal_mask = np.array(all_targets) == 0
    anom_arr = np.array(all_anomaly_probs)
    if np.any(normal_mask):
        normal_scores = anom_arr[normal_mask]
        tau_star = float(np.percentile(normal_scores, 90.0))  # 90th percentile -> <=10% FAR
        mean_norm = float(np.mean(normal_scores))
    else:
        tau_star = 0.35
        mean_norm = 0.0
    fault_mask = ~normal_mask
    mean_fault = float(np.mean(anom_arr[fault_mask])) if np.any(fault_mask) else 0.0

    return (
        total_loss / n,
        total_cls_loss / n,
        total_lm_loss / n,
        accuracy_score(all_targets, all_preds),
        f1_score(all_targets, all_preds, average="macro", zero_division=0),
        tau_star,
        mean_norm,
        mean_fault,
    )


def main():
    parser = argparse.ArgumentParser(description="Train OpenTSLM on TimeNet Penmanshiel data")
    parser.add_argument("--model-type", type=str, default="encoder", choices=["encoder", "softprompt"], help="Architecture type")
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--dataset-id", type=str, default=PENMANSHIEL_DATASET_ID)
    parser.add_argument("--save-dir", type=Path, default=Path("mk/checkpoints"))
    parser.add_argument("--device", type=str, default=None)
    args = parser.parse_args()

    args.save_dir.mkdir(parents=True, exist_ok=True)

    if args.device:
        device = torch.device(args.device)
    elif torch.cuda.is_available():
        device = torch.device("cuda")
    elif torch.backends.mps.is_available():
        device = torch.device("mps")
    else:
        device = torch.device("cpu")

    print(f"[*] Training on device: {device}")
    print(f"[*] Architecture: {args.model_type.upper()}")
    print(f"[*] Target dataset: {args.dataset_id}")

    if args.model_type == "softprompt":
        from transformers import GPT2Tokenizer
        from src.models.architecture import OpenTSLMSoftPromptForTurbineDiagnosis
        from src.models.opentslm_dataset import get_softprompt_dataloaders
        from src.data.schemas import SUBSYSTEM_CLASSES

        tokenizer = GPT2Tokenizer.from_pretrained("openai-community/gpt2")
        tokenizer.pad_token = tokenizer.eos_token

        train_loader, val_loader, test_loader = get_softprompt_dataloaders(
            tokenizer=tokenizer, batch_size=args.batch_size, dataset_id=args.dataset_id, target_mode="subsystem"
        )
        print(f"[*] Datasets: Train={len(train_loader.dataset)}, Val={len(val_loader.dataset)}, Test={len(test_loader.dataset)}")

        class_weights = compute_class_weights(train_loader, len(SUBSYSTEM_CLASSES), device)
        model = OpenTSLMSoftPromptForTurbineDiagnosis(
            in_channels=11,
            patch_size=4,
            d_encoder=256,
            d_llm=768,
            num_classes=len(SUBSYSTEM_CLASSES),
            llm_model_name="openai-community/gpt2",
        )
        model.to(device)

        trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
        total_params = sum(p.numel() for p in model.parameters())
        print(f"[*] Trainable parameters: {trainable_params:,} / {total_params:,} ({trainable_params/total_params:.2%})")

        optimizer = AdamW([p for p in model.parameters() if p.requires_grad], lr=args.lr, weight_decay=1e-2)
        scheduler = CosineAnnealingLR(optimizer, T_max=args.epochs * len(train_loader))

        best_val_loss = float("inf")
        best_val_cls = float("inf")
        best_val_f1 = -1.0
        best_epoch = 1
        best_checkpoint_path = args.save_dir / "opentslm_softprompt_best.pt"
        last_checkpoint_path = args.save_dir / "opentslm_softprompt_last.pt"

        for epoch in range(1, args.epochs + 1):
            model.current_epoch = epoch  # update gradient gate warm-up tracker
            tr_loss, tr_cls, tr_lm, tr_acc, tr_f1 = train_epoch_softprompt(
                model, train_loader, optimizer, scheduler, device, class_weights
            )
            val_loss, val_cls, val_lm, val_acc, val_f1, val_tau, val_norm, val_fault = evaluate_model_softprompt(
                model, val_loader, device, class_weights
            )
            model.anomaly_threshold = val_tau

            is_best = (val_f1 > best_val_f1 + 1e-4) or (abs(val_f1 - best_val_f1) <= 1e-4 and val_cls < best_val_cls)
            star = " ★" if is_best else ""
            print(
                f"Epoch {epoch:02d}/{args.epochs:02d} | "
                f"Train Loss: {tr_loss:.4f} (Cls: {tr_cls:.3f}, LM: {tr_lm:.3f}) F1: {tr_f1:.4f} | "
                f"Val Loss: {val_loss:.4f} (Cls: {val_cls:.3f}, LM: {val_lm:.3f}) F1: {val_f1:.4f} "
                f"[tau*={val_tau:.4f}, NormAnom={val_norm:.3f}, FaultAnom={val_fault:.3f}]{star}",
                flush=True,
            )

            if is_best:
                best_val_loss = val_loss
                best_val_cls = val_cls
                best_val_f1 = val_f1
                best_epoch = epoch
                state_dict_cpu = {k: v.cpu().clone() for k, v in model.state_dict().items()}
                ckpt_payload = {
                    "epoch": epoch,
                    "model_state_dict": state_dict_cpu,
                    "val_loss": val_loss,
                    "val_f1": val_f1,
                    "val_acc": val_acc,
                    "val_cls": val_cls,
                    "val_lm": val_lm,
                    "calibrated_threshold": val_tau,
                    "classes": SUBSYSTEM_CLASSES,
                    "dataset_id": args.dataset_id,
                }
                torch.save(ckpt_payload, best_checkpoint_path)
                root_ckpt_dir = Path("checkpoints")
                root_ckpt_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(best_checkpoint_path, root_ckpt_dir / "opentslm_softprompt_best.pt")
                del state_dict_cpu, ckpt_payload

            # Clean memory at end of each epoch to prevent MPS unified memory leak
            if hasattr(torch, "mps") and torch.backends.mps.is_available():
                torch.mps.empty_cache()
            import gc
            gc.collect()

        # Save final epoch checkpoint
        final_state_cpu = {k: v.cpu().clone() for k, v in model.state_dict().items()}
        torch.save(
            {
                "epoch": args.epochs,
                "model_state_dict": final_state_cpu,
                "val_loss": val_loss,
                "val_f1": val_f1,
                "val_acc": val_acc,
                "val_cls": val_cls,
                "val_lm": val_lm,
                "calibrated_threshold": val_tau,
                "classes": SUBSYSTEM_CLASSES,
                "dataset_id": args.dataset_id,
            },
            last_checkpoint_path,
        )
        del final_state_cpu

        print(f"\n[+] SoftPrompt Training complete! Best validation loss: {best_val_loss:.4f} (Epoch {best_epoch}, F1: {best_val_f1:.4f}). Saved to {best_checkpoint_path}", flush=True)

        # Evaluate best checkpoint on held-out test split
        checkpoint = torch.load(best_checkpoint_path, map_location=device, weights_only=False)
        model.load_state_dict(checkpoint["model_state_dict"])
        if "calibrated_threshold" in checkpoint:
            model.anomaly_threshold = checkpoint["calibrated_threshold"]
            print(f"[*] Set model anomaly threshold to calibrated tau*={model.anomaly_threshold:.4f}")
        test_loss, test_cls, test_lm, test_acc, test_f1, test_tau, test_norm, test_fault = evaluate_model_softprompt(
            model, test_loader, device
        )
        print("\n================ HELD-OUT IN-DOMAIN TEST EVALUATION (Penmanshiel WT13-WT15) ================")
        print(f"Test Accuracy: {test_acc:.2%} | Test Macro F1: {test_f1:.4f} | Cls Loss: {test_cls:.4f} | LM Loss: {test_lm:.4f}")
        print("============================================================================================")

        # Sample generative diagnosis on test set
        sample_batch = next(iter(test_loader))
        diag = model.generate_diagnosis(
            sample_batch["time_series"][0].to(device),
            tokenizer=tokenizer,
            max_new_tokens=120,
            temperature=0.2,
        )
        print("\n[*] Sample OpenTSLM Generated Chain-of-Thought Diagnosis (Test Turbine):")
        print("-------------------------------------------------------------------------")
        print(diag["generated_text"])
        print("-------------------------------------------------------------------------")
        print(f"Parsed Subsystem: {diag['parsed_subsystem']} | Triage: {diag['parsed_triage']}")

    else:
        from src.models.architecture import OpenTSLMForTurbineDiagnosis
        from src.models.opentslm_dataset import get_dataloaders
        from src.data.schemas import FAULT_CLASSES

        train_loader, val_loader, test_loader = get_dataloaders(batch_size=args.batch_size, dataset_id=args.dataset_id)
        print(f"[*] Datasets: Train={len(train_loader.dataset)} samples, Val={len(val_loader.dataset)} samples, Test={len(test_loader.dataset)} samples")

        class_weights = compute_class_weights(train_loader, len(FAULT_CLASSES), device)
        model = OpenTSLMForTurbineDiagnosis(in_channels=11, patch_size=4, d_encoder=256, d_llm=512)
        model.to(device)

        optimizer = AdamW(model.parameters(), lr=args.lr, weight_decay=1e-2)
        scheduler = CosineAnnealingLR(optimizer, T_max=args.epochs * len(train_loader))

        best_val_f1 = -1.0
        best_val_loss = float("inf")
        best_checkpoint_path = args.save_dir / "opentslm_best.pt"

        for epoch in range(1, args.epochs + 1):
            tr_loss, tr_acc, tr_f1 = train_epoch(model, train_loader, optimizer, scheduler, device, class_weights)
            val_loss, val_acc, val_f1 = evaluate_model(model, val_loader, device, class_weights)

            is_best = (val_f1 > best_val_f1 + 1e-4) or (np.isclose(val_f1, best_val_f1, atol=1e-4) and val_loss < best_val_loss)
            star = " ★" if is_best else ""
            print(
                f"Epoch {epoch:02d}/{args.epochs:02d} | "
                f"Train Loss: {tr_loss:.4f} Acc: {tr_acc:.2%} F1: {tr_f1:.4f} | "
                f"Val Loss: {val_loss:.4f} Acc: {val_acc:.2%} F1: {val_f1:.4f}{star}"
            )

            if is_best:
                best_val_f1 = val_f1
                best_val_loss = val_loss
                state_dict = {
                    "epoch": epoch,
                    "model_state_dict": model.state_dict(),
                    "val_f1": val_f1,
                    "val_acc": val_acc,
                    "classes": FAULT_CLASSES,
                    "dataset_id": args.dataset_id,
                }
                torch.save(state_dict, best_checkpoint_path)

                root_ckpt_dir = Path("checkpoints")
                root_ckpt_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(best_checkpoint_path, root_ckpt_dir / "opentslm_best.pt")

        print(f"\n[+] Training complete! Best validation F1: {best_val_f1:.4f}. Saved to {best_checkpoint_path}")

        checkpoint = torch.load(best_checkpoint_path, map_location=device, weights_only=False)
        model.load_state_dict(checkpoint["model_state_dict"])
        test_loss, test_acc, test_f1 = evaluate_model(model, test_loader, device)
        print("\n================ HELD-OUT IN-DOMAIN TEST EVALUATION (Penmanshiel WT13-WT15) ================")
        print(f"Test Accuracy: {test_acc:.2%} | Test Macro F1: {test_f1:.4f}")
        print("============================================================================================")


if __name__ == "__main__":
    main()

