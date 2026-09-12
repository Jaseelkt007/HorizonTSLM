"""PyTorch Dataset adapting TimeNet records and real SCADA windows for OpenTSLM with balanced loading."""

import random
from collections.abc import Sequence
from typing import Any, Literal

import numpy as np
import torch
from torch.utils.data import DataLoader, Dataset, Sampler, WeightedRandomSampler

try:
    from mk.src.data.preprocessor import TelemetryWindow
    from mk.src.data.schemas import (
        FAULT_CLASS_TO_IDX,
        FAULT_CLASSES,
        IDX_TO_FAULT_CLASS,
        IDX_TO_SUBSYSTEM_CLASS,
        KELMARSH_DATASET_ID,
        KELMARSH_DEMO_TURBINES,
        PENMANSHIEL_DATASET_ID,
        PENMANSHIEL_TEST_TURBINES,
        PENMANSHIEL_TRAIN_TURBINES,
        PENMANSHIEL_VAL_TURBINES,
        SELECTED_SIGNALS,
        SUBSYSTEM_CLASS_TO_IDX,
        SUBSYSTEM_CLASSES,
        StructuredLMTarget,
    )
except ImportError:
    from src.data.preprocessor import TelemetryWindow
    from src.data.schemas import (
        FAULT_CLASS_TO_IDX,
        FAULT_CLASSES,
        IDX_TO_FAULT_CLASS,
        IDX_TO_SUBSYSTEM_CLASS,
        KELMARSH_DATASET_ID,
        PENMANSHIEL_DATASET_ID,
        PENMANSHIEL_TEST_TURBINES,
        PENMANSHIEL_TRAIN_TURBINES,
        PENMANSHIEL_VAL_TURBINES,
        SUBSYSTEM_CLASS_TO_IDX,
        SUBSYSTEM_CLASSES,
    )


from timenet.client import TimeNet
from timenet.registry.factory import default_registry_path


class OpenTSLMWindDataset(Dataset):
    """Bridges TimeNet dataset records to OpenTSLM training samples with zero-leakage turbine splits."""

    def __init__(
        self,
        split: Literal["train", "val", "test", "all"] = "train",
        registry_path: str | None = None,
        dataset_id: str = PENMANSHIEL_DATASET_ID,
        train_turbines: tuple[str, ...] = PENMANSHIEL_TRAIN_TURBINES,
        val_turbines: tuple[str, ...] = PENMANSHIEL_VAL_TURBINES,
        test_turbines: tuple[str, ...] = PENMANSHIEL_TEST_TURBINES,
        target_mode: Literal["coarse", "subsystem"] = "coarse",
    ):
        self.split = split
        self.dataset_id = dataset_id
        self.target_mode = target_mode
        reg = registry_path or default_registry_path()
        client = TimeNet(registry=reg)
        self.raw_torch_dataset = client.load_torch(dataset_id)

        self.indices: list[int] = []
        self.labels: list[int] = []

        for idx in range(len(self.raw_torch_dataset)):
            sample = self.raw_torch_dataset[idx]
            # Find turbine_id annotation
            turb_id = None
            for anno in sample["annotations"]:
                if anno.key == "turbine_id":
                    turb_id = anno.value
                    break

            include = False
            if split == "all" or split == "train" and turb_id in train_turbines or split == "val" and turb_id in val_turbines or split == "test" and turb_id in test_turbines:
                include = True

            if include:
                self.indices.append(idx)
                # Cache label for rapid balanced sampling
                label_name = "Normal Operation" if target_mode == "coarse" else "normal_operation"
                for task in sample.get("tasks", []):
                    if hasattr(task, "target"):
                        if target_mode == "subsystem" and task.target in SUBSYSTEM_CLASS_TO_IDX:
                            label_name = task.target
                        elif target_mode == "coarse" and task.target in FAULT_CLASS_TO_IDX:
                            label_name = task.target
                if target_mode == "subsystem":
                    self.labels.append(SUBSYSTEM_CLASS_TO_IDX.get(label_name, 0))
                else:
                    self.labels.append(FAULT_CLASS_TO_IDX.get(label_name, 0))


    def __len__(self) -> int:
        return len(self.indices)

    def get_labels(self) -> list[int]:
        return list(self.labels)

    def __getitem__(self, i: int) -> dict[str, Any]:
        raw_idx = self.indices[i]
        sample = self.raw_torch_dataset[raw_idx]

        # Stack the 8 channels into (72, 8) tensor
        series_tuple = sample["series"]  # tuple of 8 tensors of shape (72,)
        time_series_tensor = torch.stack(series_tuple, dim=-1).float()  # (72, 8)

        # Extract AnswerTask and ClassificationTask
        prompt = ""
        rationale = ""
        action = ""
        label_name = "Normal Operation"
        turbine_id = "Turbine"

        for anno in sample["annotations"]:
            if anno.key == "turbine_id":
                turbine_id = anno.value

        for task in sample["tasks"]:
            if hasattr(task, "rationale") and task.rationale:
                prompt = task.prompt or ""
                rationale = task.rationale or ""
                action = task.target or ""
            elif hasattr(task, "target") and task.target in FAULT_CLASS_TO_IDX:
                label_name = task.target

        # Composite answer for OpenTSLM training: rationale + diagnosis + action
        full_answer = f"Rationale: {rationale}\nRecommendation: {action}"

        label_idx = FAULT_CLASS_TO_IDX.get(label_name, 0)

        return {
            "record_id": sample["record_id"],
            "turbine_id": turbine_id,
            "time_series": time_series_tensor,  # shape (72, 8)
            "pre_prompt": prompt,
            "rationale": rationale,
            "action": action,
            "answer": full_answer,
            "label_idx": label_idx,
            "label_name": label_name,
        }


# Aliases
OpenTSLMPenmanshielDataset = OpenTSLMWindDataset


class OpenTSLMKelmarshDataset(OpenTSLMWindDataset):
    """Convenience dataset for Kelmarsh wind farm (used as unseen/blank demo testbed)."""

    def __init__(
        self,
        split: Literal["train", "val", "test", "all"] = "all",
        registry_path: str | None = None,
        dataset_id: str = KELMARSH_DATASET_ID,
        train_turbines: tuple[str, ...] = ("Kelmarsh 1", "Kelmarsh 2", "Kelmarsh 3", "Kelmarsh 4"),
        val_turbines: tuple[str, ...] = ("Kelmarsh 5",),
        test_turbines: tuple[str, ...] = ("Kelmarsh 6",),
    ):
        super().__init__(
            split=split,
            registry_path=registry_path,
            dataset_id=dataset_id,
            train_turbines=train_turbines,
            val_turbines=val_turbines,
            test_turbines=test_turbines,
        )


class OpenTSLMInMemoryDataset(Dataset):
    """PyTorch Dataset wrapping preprocessed TelemetryWindow instances directly with dual taxonomy support."""

    def __init__(
        self,
        windows: Sequence[TelemetryWindow],
        target_mode: Literal["coarse", "subsystem"] = "coarse",
    ):
        self.windows = list(windows)
        self.target_mode = target_mode
        self.labels: list[int] = []
        for w in self.windows:
            if target_mode == "subsystem":
                if w.structured_target is not None and w.structured_target.subsystem in SUBSYSTEM_CLASS_TO_IDX:
                    self.labels.append(SUBSYSTEM_CLASS_TO_IDX[w.structured_target.subsystem])
                elif w.label_name in SUBSYSTEM_CLASS_TO_IDX:
                    self.labels.append(SUBSYSTEM_CLASS_TO_IDX[w.label_name])
                else:
                    self.labels.append(w.label_idx if w.label_idx < len(SUBSYSTEM_CLASSES) else 0)
            else:
                if w.structured_target is not None and w.structured_target.coarse_fault in FAULT_CLASS_TO_IDX:
                    self.labels.append(FAULT_CLASS_TO_IDX[w.structured_target.coarse_fault])
                elif w.label_name in FAULT_CLASS_TO_IDX:
                    self.labels.append(FAULT_CLASS_TO_IDX[w.label_name])
                else:
                    self.labels.append(w.label_idx if w.label_idx < len(FAULT_CLASSES) else 0)

    def __len__(self) -> int:
        return len(self.windows)

    def get_labels(self) -> list[int]:
        return list(self.labels)

    def __getitem__(self, i: int) -> dict[str, Any]:
        w = self.windows[i]
        time_series_tensor = torch.tensor(w.signals, dtype=torch.float32)
        target_text = (
            w.structured_target.to_formatted_target()
            if w.structured_target is not None
            else f"Rationale: {w.rationale}\nRecommendation: {w.action}"
        )

        label_idx = self.labels[i]
        if self.target_mode == "subsystem":
            label_name = (
                w.structured_target.subsystem
                if w.structured_target is not None
                else IDX_TO_SUBSYSTEM_CLASS.get(label_idx, w.label_name)
            )
        else:
            label_name = (
                w.structured_target.coarse_fault
                if w.structured_target is not None
                else IDX_TO_FAULT_CLASS.get(label_idx, w.label_name)
            )

        return {
            "record_id": f"w-{i:05d}",
            "turbine_id": w.turbine_id,
            "time_series": time_series_tensor,
            "pre_prompt": w.prompt,
            "rationale": w.rationale,
            "action": w.action,
            "answer": target_text,
            "label_idx": label_idx,
            "label_name": label_name,
            "structured_target": target_text,
        }


def compute_sample_weights(
    labels: Sequence[int],
    num_classes: int | None = None,
    smoothing: float = 1e-6,
) -> torch.Tensor:
    """Compute per-sample weights inversely proportional to class frequencies for equal sampling."""
    labels_arr = np.array(labels, dtype=np.int64)
    if len(labels_arr) == 0:
        return torch.empty(0, dtype=torch.float32)

    if num_classes is None:
        num_classes = int(np.max(labels_arr)) + 1 if len(labels_arr) > 0 else 1

    counts = np.bincount(labels_arr, minlength=num_classes)
    class_weights = np.where(counts > 0, 1.0 / (counts.astype(np.float64) + smoothing), 0.0)
    sample_weights = class_weights[labels_arr]
    sum_w = np.sum(sample_weights)
    if sum_w > 0:
        sample_weights = sample_weights / sum_w * len(labels_arr)

    return torch.tensor(sample_weights, dtype=torch.float32)


class BalancedBatchSampler(Sampler):
    """Yields batches with balanced class representation across all present classes."""

    def __init__(self, labels: Sequence[int], batch_size: int, seed: int = 42):
        self.labels = list(labels)
        self.batch_size = batch_size
        self.rng = random.Random(seed)
        self.classes = sorted(set(labels))
        self.class_indices = {c: [i for i, y in enumerate(labels) if y == c] for c in self.classes}
        for c in self.classes:
            self.rng.shuffle(self.class_indices[c])
        self.class_pointers = {c: 0 for c in self.classes}
        self.num_batches = max(1, len(labels) // max(1, batch_size))

    def __iter__(self):
        for _ in range(self.num_batches):
            batch = []
            for _ in range(self.batch_size):
                cls = self.rng.choice(self.classes)
                ptr = self.class_pointers[cls]
                batch.append(self.class_indices[cls][ptr])
                ptr = (ptr + 1) % len(self.class_indices[cls])
                self.class_pointers[cls] = ptr
            yield batch

    def __len__(self) -> int:
        return self.num_batches


def collate_opentslm_batch(batch: list[dict[str, Any]]) -> dict[str, Any]:
    """Collate function packing batch for OpenTSLM training or evaluation."""
    time_series = torch.stack([b["time_series"] for b in batch], dim=0)  # (B, T, C)
    label_indices = torch.tensor([b["label_idx"] for b in batch], dtype=torch.long)

    return {
        "time_series": time_series,
        "pre_prompts": [b["pre_prompt"] for b in batch],
        "answers": [b["answer"] for b in batch],
        "rationales": [b["rationale"] for b in batch],
        "actions": [b["action"] for b in batch],
        "label_indices": label_indices,
        "label_names": [b["label_name"] for b in batch],
        "turbine_ids": [b["turbine_id"] for b in batch],
        "record_ids": [b["record_id"] for b in batch],
    }


def get_dataloaders(
    batch_size: int = 4,
    registry_path: str | None = None,
    dataset_id: str = PENMANSHIEL_DATASET_ID,
    balanced: bool = True,
    sampler_type: str = "weighted",
    target_mode: Literal["coarse", "subsystem"] = "coarse",
    train_dataset: Dataset | None = None,
    val_dataset: Dataset | None = None,
    test_dataset: Dataset | None = None,
) -> tuple[DataLoader, DataLoader, DataLoader]:
    """Return train, val, and test DataLoaders for Penmanshiel ensuring equal class distribution.

    Parameters:
        batch_size: Batch size per iteration.
        registry_path: Optional TimeNet registry path.
        dataset_id: TimeNet dataset ID.
        balanced: If True, balances class distribution in the train loader.
        sampler_type: 'weighted' (WeightedRandomSampler) or 'batch' (BalancedBatchSampler).
        target_mode: Label space for balancing ('coarse' or 'subsystem').
        train_dataset: Optional custom train Dataset.
        val_dataset: Optional custom val Dataset.
        test_dataset: Optional custom test Dataset.

    Returns:
        (train_loader, val_loader, test_loader)
    """
    train_ds = train_dataset or OpenTSLMWindDataset(
        split="train", registry_path=registry_path, dataset_id=dataset_id, target_mode=target_mode
    )
    val_ds = val_dataset or OpenTSLMWindDataset(
        split="val", registry_path=registry_path, dataset_id=dataset_id, target_mode=target_mode
    )
    test_ds = test_dataset or OpenTSLMWindDataset(
        split="test", registry_path=registry_path, dataset_id=dataset_id, target_mode=target_mode
    )

    if balanced and len(train_ds) > 0:
        if hasattr(train_ds, "get_labels"):
            train_labels = train_ds.get_labels()
        elif hasattr(train_ds, "labels"):
            train_labels = list(train_ds.labels)
        else:
            train_labels = [train_ds[i]["label_idx"] for i in range(len(train_ds))]

        if sampler_type == "batch":
            batch_sampler = BalancedBatchSampler(train_labels, batch_size=batch_size)
            train_loader = DataLoader(
                train_ds,
                batch_sampler=batch_sampler,
                collate_fn=collate_opentslm_batch,
            )
        else:
            num_classes = len(SUBSYSTEM_CLASSES) if target_mode == "subsystem" else len(FAULT_CLASSES)
            sample_weights = compute_sample_weights(train_labels, num_classes=num_classes)
            train_sampler = WeightedRandomSampler(
                weights=sample_weights,
                num_samples=len(train_labels),
                replacement=True,
            )
            train_loader = DataLoader(
                train_ds,
                batch_size=batch_size,
                sampler=train_sampler,
                shuffle=False,
                collate_fn=collate_opentslm_batch,
            )
    else:
        train_loader = DataLoader(
            train_ds,
            batch_size=batch_size,
            shuffle=True,
            collate_fn=collate_opentslm_batch,
        )

    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False, collate_fn=collate_opentslm_batch)
    test_loader = DataLoader(test_ds, batch_size=batch_size, shuffle=False, collate_fn=collate_opentslm_batch)

    return train_loader, val_loader, test_loader


class OpenTSLMSoftPromptDataCollator:
    """Collates and tokenizes time-series samples and text prompts for OpenTSLM-SoftPrompt training."""

    def __init__(
        self,
        tokenizer: Any,
        max_length: int = 256,
        prompt_template: str = "Question: Analyze the 24-hour turbine telemetry. Provide triage, subsystem, evidence, and action.\n\nDiagnosis:\n",
    ):
        self.tokenizer = tokenizer
        self.max_length = max_length
        self.prompt_template = prompt_template
        if self.tokenizer.pad_token_id is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

    def __call__(self, batch: list[dict[str, Any]]) -> dict[str, Any]:
        time_series_list = [item["time_series"] for item in batch]
        label_indices = [item["label_idx"] for item in batch]

        # Stack time series: (B, T, C)
        time_series_tensor = torch.stack(time_series_list, dim=0).float()
        labels_tensor = torch.tensor(label_indices, dtype=torch.long)

        # Build full text: prompt + target answer
        full_texts = []
        prompt_lengths = []
        for item in batch:
            prompt_str = self.prompt_template
            ans = item.get("structured_target", item.get("answer", ""))
            full_text = prompt_str + ans + self.tokenizer.eos_token
            full_texts.append(full_text)

            prompt_ids = self.tokenizer(prompt_str, add_special_tokens=False).input_ids
            prompt_lengths.append(len(prompt_ids))

        tokenized = self.tokenizer(
            full_texts,
            padding=True,
            truncation=True,
            max_length=self.max_length,
            return_tensors="pt",
        )

        input_ids = tokenized.input_ids
        attention_mask = tokenized.attention_mask

        # Create labels where prompt tokens and pad tokens are masked to -100
        labels = input_ids.clone()
        for idx, p_len in enumerate(prompt_lengths):
            labels[idx, :p_len] = -100
        labels[attention_mask == 0] = -100

        return {
            "time_series": time_series_tensor,
            "label_indices": labels_tensor,
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "labels": labels,
            "answers": [item.get("structured_target", item.get("answer", "")) for item in batch],
        }


def get_softprompt_dataloaders(
    tokenizer: Any,
    batch_size: int = 4,
    dataset_id: str = PENMANSHIEL_DATASET_ID,
    target_mode: Literal["coarse", "subsystem"] = "subsystem",
) -> tuple[DataLoader, DataLoader, DataLoader]:
    """Build dataloaders prepared with OpenTSLMSoftPromptDataCollator for generative training."""
    train_ds = OpenTSLMWindDataset(split="train", dataset_id=dataset_id, target_mode=target_mode)
    val_ds = OpenTSLMWindDataset(split="val", dataset_id=dataset_id, target_mode=target_mode)
    test_ds = OpenTSLMWindDataset(split="test", dataset_id=dataset_id, target_mode=target_mode)

    collator = OpenTSLMSoftPromptDataCollator(tokenizer=tokenizer)

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, collate_fn=collator)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False, collate_fn=collator)
    test_loader = DataLoader(test_ds, batch_size=batch_size, shuffle=False, collate_fn=collator)

    return train_loader, val_loader, test_loader


