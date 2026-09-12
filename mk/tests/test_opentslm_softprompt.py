"""Unit and integration tests for OpenTSLM-SoftPrompt with 24-hour context and generative diagnosis."""

import pytest
import torch
from transformers import GPT2Tokenizer

from mk.src.data.schemas import (
    SUBSYSTEM_CLASSES,
    WINDOW_STEPS,
    WINDOW_STEPS_12H,
    WINDOW_STEPS_24H,
)
from mk.src.models.architecture import (
    MultiScalePatchTokenizer,
    OpenTSLMSoftPromptForTurbineDiagnosis,
)
from mk.src.models.opentslm_dataset import OpenTSLMSoftPromptDataCollator


@pytest.fixture(scope="module")
def gpt2_tokenizer():
    tok = GPT2Tokenizer.from_pretrained("openai-community/gpt2")
    tok.pad_token = tok.eos_token
    return tok


def test_multiscale_patch_tokenizer_24h_and_12h():
    """Verify MultiScalePatchTokenizer produces correct patch sequences for 24h and 12h windows."""
    tokenizer = MultiScalePatchTokenizer(in_channels=8, patch_size=4, d_model=128)

    # 24h window: 144 steps -> 144 / 4 = 36 patches
    x_24h = torch.randn(2, WINDOW_STEPS_24H, 8)
    tokens_24h = tokenizer(x_24h)
    assert tokens_24h.shape == (2, 36, 128)

    # 12h window: 72 steps -> 72 / 4 = 18 patches
    x_12h = torch.randn(2, WINDOW_STEPS_12H, 8)
    tokens_12h = tokenizer(x_12h)
    assert tokens_12h.shape == (2, 18, 128)


def test_opentslm_softprompt_forward_and_loss(gpt2_tokenizer):
    """Verify dual-head forward pass with 24h telemetry and language modeling loss."""
    model = OpenTSLMSoftPromptForTurbineDiagnosis(
        in_channels=8,
        patch_size=4,
        d_encoder=64,
        d_llm=768,
        num_classes=len(SUBSYSTEM_CLASSES),
        num_encoder_layers=2,
        lora_r=4,
    )

    B = 2
    time_series_24h = torch.randn(B, WINDOW_STEPS_24H, 8)
    label_indices = torch.tensor([1, 4])

    text_samples = [
        "Triage: fault\nSubsystem: gearbox_lubrication\nACTION: Curtail power.\nAnswer: gearbox_lubrication",
        "Triage: normal\nSubsystem: normal_operation\nACTION: None.\nAnswer: normal_operation",
    ]
    tok_res = gpt2_tokenizer(text_samples, padding=True, return_tensors="pt")
    input_ids = tok_res.input_ids
    attention_mask = tok_res.attention_mask
    labels = input_ids.clone()
    labels[attention_mask == 0] = -100

    outputs = model(
        time_series=time_series_24h,
        input_ids=input_ids,
        attention_mask=attention_mask,
        labels=labels,
        label_indices=label_indices,
    )

    assert "cls_logits" in outputs
    assert "lm_logits" in outputs
    assert "cls_loss" in outputs
    assert "lm_loss" in outputs
    assert outputs["cls_logits"].shape == (B, len(SUBSYSTEM_CLASSES))
    assert outputs["ts_embeds"].shape == (B, 36, 768)
    assert outputs["loss"] > 0.0

    # Backward pass verification
    outputs["loss"].backward()
    # Check that trainable parameters received gradients
    trainable_grads = [p.grad for p in model.parameters() if p.requires_grad]
    assert len(trainable_grads) > 0
    assert any(g is not None and g.abs().sum() > 0 for g in trainable_grads)


def test_opentslm_softprompt_generation(gpt2_tokenizer):
    """Verify autoregressive text generation conditioned on 24h continuous telemetry."""
    model = OpenTSLMSoftPromptForTurbineDiagnosis(
        in_channels=8,
        patch_size=4,
        d_encoder=64,
        d_llm=768,
        num_classes=len(SUBSYSTEM_CLASSES),
        num_encoder_layers=2,
        lora_r=4,
    )

    x_24h = torch.randn(1, WINDOW_STEPS_24H, 8)
    diag = model.generate_diagnosis(
        time_series=x_24h,
        tokenizer=gpt2_tokenizer,
        max_new_tokens=20,
        temperature=0.0,
    )

    assert "generated_text" in diag
    assert "cls_pred_idx" in diag
    assert "parsed_subsystem" in diag
    assert "parsed_triage" in diag
    assert isinstance(diag["cls_pred_idx"], int)
    assert 0 <= diag["cls_pred_idx"] < len(SUBSYSTEM_CLASSES)
    assert len(diag["generated_text"]) > 0


def test_softprompt_data_collator(gpt2_tokenizer):
    """Verify that OpenTSLMSoftPromptDataCollator properly masks prompt tokens with -100."""
    collator = OpenTSLMSoftPromptDataCollator(tokenizer=gpt2_tokenizer, max_length=64)

    dummy_batch = [
        {
            "time_series": torch.randn(WINDOW_STEPS_24H, 8),
            "label_idx": 1,
            "structured_target": "Triage: fault\nSubsystem: gearbox_lubrication\nAnswer: gearbox_lubrication",
        },
        {
            "time_series": torch.randn(WINDOW_STEPS_24H, 8),
            "label_idx": 0,
            "structured_target": "Triage: normal\nSubsystem: normal_operation\nAnswer: normal_operation",
        },
    ]

    batch = collator(dummy_batch)
    assert batch["time_series"].shape == (2, WINDOW_STEPS_24H, 8)
    assert batch["label_indices"].shape == (2,)
    assert batch["input_ids"].shape[0] == 2
    assert batch["labels"].shape == batch["input_ids"].shape
    # Check that initial prompt tokens are masked to -100
    assert (batch["labels"][:, 0] == -100).all()
