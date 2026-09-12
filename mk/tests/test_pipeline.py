"""End-to-end integration tests for Penmanshiel data loading, model forward pass, and baselines."""

import numpy as np
import pytest
import torch

from src.data.schemas import (
    KELMARSH_DATASET_ID,
    PENMANSHIEL_DATASET_ID,
)
from src.evaluation.baselines import (
    ClassicalMLBaseline,
    TextOnlyLLMBaseline,
    prepare_tabular_dataset,
)
from src.models.architecture import OpenTSLMForTurbineDiagnosis
from src.models.opentslm_dataset import (
    OpenTSLMKelmarshDataset,
    OpenTSLMWindDataset,
    get_dataloaders,
)


def test_penmanshiel_opentslm_dataset_splits():
    train_ds = OpenTSLMWindDataset(split="train", dataset_id=PENMANSHIEL_DATASET_ID)
    val_ds = OpenTSLMWindDataset(split="val", dataset_id=PENMANSHIEL_DATASET_ID)
    test_ds = OpenTSLMWindDataset(split="test", dataset_id=PENMANSHIEL_DATASET_ID)

    assert len(train_ds) > 0
    assert len(val_ds) > 0
    assert len(test_ds) > 0

    # Ensure strict zero-leakage across turbines
    train_turbines = set(s["turbine_id"] for s in [train_ds[i] for i in range(len(train_ds))])
    val_turbines = set(s["turbine_id"] for s in [val_ds[i] for i in range(len(val_ds))])
    test_turbines = set(s["turbine_id"] for s in [test_ds[i] for i in range(len(test_ds))])

    assert len(train_turbines.intersection(test_turbines)) == 0, "Data leakage detected between Penmanshiel train and test!"
    assert len(val_turbines.intersection(test_turbines)) == 0, "Data leakage detected between Penmanshiel val and test!"
    assert len(train_turbines.intersection(val_turbines)) == 0, "Data leakage detected between Penmanshiel train and val!"


def test_kelmarsh_blank_dataset():
    kel_ds = OpenTSLMKelmarshDataset(split="all", dataset_id=KELMARSH_DATASET_ID)
    assert len(kel_ds) > 0
    kel_turbines = set(s["turbine_id"] for s in [kel_ds[i] for i in range(len(kel_ds))])
    assert all("Kelmarsh" in t for t in kel_turbines)


def test_model_forward_pass():
    model = OpenTSLMForTurbineDiagnosis(in_channels=8, patch_size=4, d_encoder=64, d_llm=128)
    dummy_input = torch.randn(2, 72, 8)
    dummy_labels = torch.tensor([0, 1])

    outputs = model(dummy_input, label_indices=dummy_labels)
    assert "logits" in outputs
    assert "loss" in outputs
    assert outputs["logits"].shape == (2, 5)

    preds, probs = model.predict(dummy_input)
    assert preds.shape == (2,)
    assert probs.shape == (2, 5)


def test_baselines_penmanshiel():
    train_ds = OpenTSLMWindDataset(split="train", dataset_id=PENMANSHIEL_DATASET_ID)
    test_ds = OpenTSLMWindDataset(split="test", dataset_id=PENMANSHIEL_DATASET_ID)

    X_train, y_train, _ = prepare_tabular_dataset(train_ds)
    X_test, y_test, _ = prepare_tabular_dataset(test_ds)

    assert X_train.shape[1] == 48  # 8 channels * 6 statistics

    rf = ClassicalMLBaseline(n_estimators=10)
    rf.fit(X_train, y_train)
    eval_res = rf.evaluate(X_test, y_test)
    assert "accuracy" in eval_res
    assert "macro_f1" in eval_res
    assert 0.0 <= eval_res["accuracy"] <= 1.0

    text_bl = TextOnlyLLMBaseline()
    eval_text = text_bl.evaluate(X_test, y_test)
    assert "accuracy" in eval_text
    assert 0.0 <= eval_text["accuracy"] <= 1.0
