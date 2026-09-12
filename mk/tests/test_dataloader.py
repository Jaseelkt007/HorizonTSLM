"""Tests for balanced DataLoader, class equalization, and OpenTSLM in-memory dataset."""

from collections import Counter

import numpy as np
import pytest
import torch

from mk.src.data.preprocessor import TelemetryWindow
from mk.src.data.schemas import (
    FAULT_CLASSES,
    SIGNAL_NAMES,
    WINDOW_STEPS,
)
from mk.src.models.opentslm_dataset import (
    BalancedBatchSampler,
    OpenTSLMInMemoryDataset,
    compute_sample_weights,
    get_dataloaders,
)


def _make_mock_windows(class_distribution: dict) -> list:
    """Create mock TelemetryWindow instances matching a given class distribution dict {class_idx: count}."""
    windows = []
    w_id = 0
    for cls_idx, count in class_distribution.items():
        cls_name = FAULT_CLASSES[cls_idx]
        for _ in range(count):
            signals = np.random.randn(WINDOW_STEPS, 8).astype(np.float32)
            windows.append(
                TelemetryWindow(
                    turbine_id=f"Penmanshiel WT{(w_id % 14) + 1:02d}",
                    start_time="2020-01-01 00:00",
                    end_time="2020-01-01 12:00",
                    signals=signals,
                    channel_names=SIGNAL_NAMES,
                    label_idx=cls_idx,
                    label_name=cls_name,
                    prompt="Analyze telemetry",
                    rationale=f"Rationale for {cls_name}",
                    action=f"Action for {cls_name}",
                    status_events=[],
                )
            )
            w_id += 1
    return windows


def test_compute_sample_weights_equalization():
    """Verify compute_sample_weights computes inverse frequencies that equalize draw probabilities."""
    # Heavily imbalanced: 900 normal (0), 90 warning (1), 10 critical fault (2)
    labels = [0] * 900 + [1] * 90 + [2] * 10
    weights = compute_sample_weights(labels, num_classes=3)

    assert len(weights) == 1000
    assert weights.dtype == torch.float32

    # Weight of class 2 should be ~90x class 0
    w_0 = weights[0].item()
    w_1 = weights[900].item()
    w_2 = weights[990].item()

    assert w_2 > w_1 > w_0
    assert pytest.approx(w_2 / w_0, rel=0.05) == 90.0
    assert pytest.approx(w_1 / w_0, rel=0.05) == 10.0


def test_balanced_batch_sampler_distribution():
    """Verify BalancedBatchSampler produces batches containing diverse balanced classes."""
    # 80 normal, 15 warning, 5 fault
    labels = [0] * 80 + [1] * 15 + [2] * 5
    batch_size = 6
    sampler = BalancedBatchSampler(labels, batch_size=batch_size, seed=42)

    batches = list(sampler)
    assert len(batches) > 0

    all_drawn = [labels[idx] for b in batches for idx in b]
    counts = Counter(all_drawn)

    # In raw data, class 2 is only 5% of dataset.
    # With balanced batch sampling, class 2 should be drawn ~30-40% of the time!
    prop_2 = counts[2] / len(all_drawn)
    assert prop_2 > 0.20, f"Class 2 proportion {prop_2:.2f} is too low for balanced sampling"


def test_opentslm_in_memory_dataset():
    """Verify OpenTSLMInMemoryDataset wraps TelemetryWindows and yields OpenTSLM sample dicts."""
    windows = _make_mock_windows({0: 5, 1: 3, 2: 2})
    ds = OpenTSLMInMemoryDataset(windows)

    assert len(ds) == 10
    assert ds.get_labels() == [0] * 5 + [1] * 3 + [2] * 2

    sample = ds[0]
    assert "time_series" in sample
    assert sample["time_series"].shape == (WINDOW_STEPS, 8)
    assert sample["label_idx"] == 0
    assert sample["label_name"] == FAULT_CLASSES[0]
    assert "pre_prompt" in sample
    assert "answer" in sample


def test_get_dataloaders_balanced_weighted():
    """Verify get_dataloaders with balanced=True draws classes with balanced distribution during training."""
    # 100 normal, 10 warning, 5 fault
    mock_windows = _make_mock_windows({0: 100, 1: 10, 2: 5})
    train_ds = OpenTSLMInMemoryDataset(mock_windows)
    val_ds = OpenTSLMInMemoryDataset(mock_windows[:10])
    test_ds = OpenTSLMInMemoryDataset(mock_windows[:10])

    train_loader, _val_loader, _test_loader = get_dataloaders(
        batch_size=8,
        balanced=True,
        sampler_type="weighted",
        train_dataset=train_ds,
        val_dataset=val_ds,
        test_dataset=test_ds,
    )

    # Collect training epoch draws
    drawn_labels = []
    for batch in train_loader:
        assert batch["time_series"].shape[1:] == (WINDOW_STEPS, 8)
        drawn_labels.extend(batch["label_indices"].tolist())

    counts = Counter(drawn_labels)
    # The minority class 2 (5 samples in dataset of 115) should be drawn at a comparable rate to class 0
    ratio_2_to_0 = counts[2] / max(1, counts[0])
    assert ratio_2_to_0 > 0.35, f"Expected balanced draw ratio > 0.35, got {ratio_2_to_0:.2f}"


def test_subsystem_mode_balanced_dataloader():
    """Verify that DataLoader balances minority subsystem classes (e.g. curtailment, sensor comms) equally."""
    from mk.src.data.schemas import SUBSYSTEM_CLASS_TO_IDX, StructuredLMTarget

    # Create dataset with heavy class imbalance across subsystems:
    # normal_operation (100), curtailment_external (3), sensor_comms (2), gearbox_lubrication (5)
    windows = []
    dist = {
        "normal_operation": 100,
        "curtailment_external": 3,
        "sensor_comms": 2,
        "gearbox_lubrication": 5,
    }
    for subsys, count in dist.items():
        subsys_idx = SUBSYSTEM_CLASS_TO_IDX[subsys]
        for i in range(count):
            target = StructuredLMTarget(
                finding=f"Finding for {subsys}",
                evidence="Telemetry evidence",
                cause=f"Subsystem root cause for {subsys}",
                impact="0 kWh lost",
                action="Continue monitoring",
                subsystem=subsys,
            )
            windows.append(
                TelemetryWindow(
                    turbine_id="Penmanshiel WT01",
                    start_time="2020-01-01 00:00",
                    end_time="2020-01-01 12:00",
                    signals=np.zeros((WINDOW_STEPS, 8), dtype=np.float32),
                    channel_names=SIGNAL_NAMES,
                    label_idx=subsys_idx,
                    label_name=subsys,
                    prompt="Analyze telemetry",
                    rationale="Rationale text",
                    action="Action text",
                    status_events=[],
                    structured_target=target,
                )
            )

    train_ds = OpenTSLMInMemoryDataset(windows, target_mode="subsystem")
    assert len(train_ds) == 110

    train_loader, _, _ = get_dataloaders(
        batch_size=8,
        balanced=True,
        sampler_type="batch",
        target_mode="subsystem",
        train_dataset=train_ds,
        val_dataset=train_ds,
        test_dataset=train_ds,
    )

    all_drawn_subsystems = []
    for batch in train_loader:
        assert len(batch["answers"]) == 8
        for ans in batch["answers"]:
            assert "FINDING   " in ans
            assert "Answer: " in ans
        all_drawn_subsystems.extend(batch["label_names"])

    subsys_counts = Counter(all_drawn_subsystems)
    # Rare classes like curtailment_external and sensor_comms (only 2-3 instances in dataset)
    # should be drawn in significant proportions (~20-30% each) thanks to BalancedBatchSampler
    assert subsys_counts["curtailment_external"] > 0
    assert subsys_counts["sensor_comms"] > 0
    prop_curtail = subsys_counts["curtailment_external"] / len(all_drawn_subsystems)
    assert prop_curtail > 0.15, f"Expected curtailment draw > 15%, got {prop_curtail:.2f}"


def test_collate_opentslm_batch_structure():
    """Verify collate_opentslm_batch correctly packages multimodal tensors and structured target strings."""
    from mk.src.models.opentslm_dataset import collate_opentslm_batch

    batch_samples = [
        {
            "record_id": f"w-{i}",
            "turbine_id": f"Penmanshiel WT0{i+1}",
            "time_series": torch.randn(WINDOW_STEPS, 8),
            "pre_prompt": f"Analyze window {i}",
            "rationale": f"Rationale {i}",
            "action": f"Action {i}",
            "answer": f"FINDING Finding {i}\nEVIDENCE Ev\nCAUSE Cause\nIMPACT Imp\nACTION Act\nAnswer: normal_operation",
            "label_idx": i % 5,
            "label_name": FAULT_CLASSES[i % 5],
        }
        for i in range(4)
    ]

    collated = collate_opentslm_batch(batch_samples)
    assert "time_series" in collated
    assert collated["time_series"].shape == (4, WINDOW_STEPS, 8)
    assert len(collated["answers"]) == 4
    assert len(collated["pre_prompts"]) == 4
    assert len(collated["rationales"]) == 4
    assert len(collated["actions"]) == 4
    assert len(collated["label_indices"]) == 4
    assert len(collated["label_names"]) == 4
    assert len(collated["turbine_ids"]) == 4
    assert len(collated["record_ids"]) == 4


