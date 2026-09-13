"""OpenTSLM model architecture: Time-series CNN/MLP patch tokenizer + projection + Language Model."""

import math
from typing import Any, Dict, List, Optional, Tuple
import torch
import torch.nn as nn
import torch.nn.functional as F

from src.data.schemas import FAULT_CLASSES, SUBSYSTEM_CLASSES


class TimeSeriesPatchTokenizer(nn.Module):
    """Encodes multivariate continuous time-series (B, T, C) into patch tokens (B, N_patches, D_patch)."""

    def __init__(self, in_channels: int = 8, patch_size: int = 4, d_model: int = 256):
        super().__init__()
        self.patch_size = patch_size
        self.in_channels = in_channels
        self.d_model = d_model

        # Conv1d patch encoder over time axis
        self.patch_conv = nn.Conv1d(
            in_channels=in_channels,
            out_channels=d_model,
            kernel_size=patch_size,
            stride=patch_size,
        )
        self.layer_norm = nn.LayerNorm(d_model)
        self.pos_embed = nn.Parameter(torch.randn(1, 100, d_model) * 0.02)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Args:

        x: (B, T, C) Returns: (B, N_patches, D_model)
        """
        # Transpose to (B, C, T) for Conv1d
        x_trans = x.transpose(1, 2)
        tokens = self.patch_conv(x_trans)  # (B, D_model, N_patches)
        tokens = tokens.transpose(1, 2)  # (B, N_patches, D_model)

        seq_len = tokens.size(1)
        tokens = tokens + self.pos_embed[:, :seq_len, :]
        tokens = self.layer_norm(tokens)
        return tokens


class MLPProjector(nn.Module):
    """Projects time-series patch embeddings into LLM embedding space."""

    def __init__(self, in_dim: int = 256, out_dim: int = 512, hidden_dim: int = 512):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(in_dim, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, out_dim),
            nn.LayerNorm(out_dim),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class OpenTSLMForTurbineDiagnosis(nn.Module):
    """End-to-End Time-Series Language Model for Wind Turbine Diagnostics.

    Connects time-series patch tokens with text prompt tokens and outputs:
    1. Direct fault classification logits (for rigorous accuracy/F1 evaluation)
    2. Generated Chain-of-Thought reasoning and maintenance recommendations.
    """

    def __init__(
        self,
        in_channels: int = 8,
        patch_size: int = 4,
        d_encoder: int = 256,
        d_llm: int = 512,
        num_classes: int = len(FAULT_CLASSES),
        num_heads: int = 8,
        num_layers: int = 4,
    ):
        super().__init__()
        self.patch_tokenizer = TimeSeriesPatchTokenizer(
            in_channels=in_channels,
            patch_size=patch_size,
            d_model=d_encoder,
        )
        self.projector = MLPProjector(in_dim=d_encoder, out_dim=d_llm)

        # Transformer encoder/decoder for temporal reasoning & cross-modal interaction
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_llm,
            nhead=num_heads,
            dim_feedforward=d_llm * 4,
            dropout=0.1,
            batch_first=True,
            activation="gelu",
        )
        self.temporal_transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)

        # Classification diagnostic head
        self.classifier = nn.Sequential(
            nn.Linear(d_llm, d_llm // 2),
            nn.GELU(),
            nn.Linear(d_llm // 2, num_classes),
        )

    def forward(
        self,
        time_series: torch.Tensor,  # (B, T, C)
        label_indices: Optional[torch.Tensor] = None,
        class_weights: Optional[torch.Tensor] = None,
    ) -> Dict[str, torch.Tensor]:
        patch_tokens = self.patch_tokenizer(time_series)  # (B, N, D_enc)
        llm_tokens = self.projector(patch_tokens)  # (B, N, D_llm)

        # Process through temporal transformer
        contextual_tokens = self.temporal_transformer(llm_tokens)  # (B, N, D_llm)

        # Global average pool for classification representation
        pooled = contextual_tokens.mean(dim=1)
        logits = self.classifier(pooled)  # (B, num_classes)

        output = {
            "logits": logits,
            "tokens": contextual_tokens,
            "pooled": pooled,
        }

        if label_indices is not None:
            loss = F.cross_entropy(logits, label_indices, weight=class_weights)
            output["loss"] = loss

        return output

    @torch.no_grad()
    def predict(self, time_series: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """Returns (predicted_class_indices, class_probabilities)."""
        self.eval()
        outputs = self.forward(time_series)
        probs = F.softmax(outputs["logits"], dim=-1)
        preds = torch.argmax(probs, dim=-1)
        return preds, probs


class MultiScalePatchTokenizer(nn.Module):
    """Multi-scale continuous time-series patch tokenizer.

    Extracts both fine-grained temporal shocks (e.g. electrical trips/pitch oscillations)
    and coarse thermal drifts (e.g. gearbox lubrication overheating over 24 hours).
    """

    def __init__(
        self,
        in_channels: int = 8,
        patch_size: int = 4,
        d_model: int = 256,
        max_patches: int = 200,
    ):
        super().__init__()
        self.patch_size = patch_size
        self.in_channels = in_channels
        self.d_model = d_model

        # Branch 1: Main scale patch convolution
        self.conv_main = nn.Conv1d(
            in_channels=in_channels,
            out_channels=d_model // 2,
            kernel_size=patch_size,
            stride=patch_size,
        )
        # Branch 2: Fine scale kernel with same stride to match patch sequence length
        self.conv_fine = nn.Conv1d(
            in_channels=in_channels,
            out_channels=d_model // 2,
            kernel_size=2,
            stride=patch_size,
        )
        self.proj = nn.Linear(d_model, d_model)
        self.layer_norm = nn.LayerNorm(d_model)
        self.pos_embed = nn.Parameter(torch.randn(1, max_patches, d_model) * 0.02)

        # Physical channel scaling based on schemas.py [min_val, max_val]
        # Balances channel magnitudes into [0, 1] so high-RPM/kW channels (1250 RPM, 800 kW)
        # do not drown out subtle thermal (+15°C) and pitch (+5°) fault signals.
        from src.data.schemas import SELECTED_SIGNALS
        min_v = [s.min_val for s in SELECTED_SIGNALS]
        max_v = [s.max_val for s in SELECTED_SIGNALS]
        if len(min_v) < in_channels:
            min_v += [0.0] * (in_channels - len(min_v))
            max_v += [1.0] * (in_channels - len(max_v))
        self.register_buffer("channel_min", torch.tensor(min_v[:in_channels], dtype=torch.float32).view(1, 1, in_channels))
        self.register_buffer("channel_scale", (torch.tensor(max_v[:in_channels], dtype=torch.float32) - torch.tensor(min_v[:in_channels], dtype=torch.float32)).clamp(min=1.0).view(1, 1, in_channels))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Args: x: (B, T, C) -> Returns: (B, N_patches, D_model)"""
        # Apply channel normalization to [0, 1]
        if hasattr(self, "channel_min") and self.channel_min.size(-1) == x.size(-1):
            x = (x - self.channel_min) / self.channel_scale

        x_trans = x.transpose(1, 2)  # (B, C, T)
        main_out = self.conv_main(x_trans)  # (B, d_model // 2, N)
        n_patches = main_out.size(2)
        fine_in = x_trans[..., : n_patches * self.patch_size]
        fine_out = self.conv_fine(fine_in)  # (B, d_model // 2, N)

        # Concatenate multi-scale representations along channel dimension
        fused = torch.cat([main_out, fine_out], dim=1).transpose(1, 2)  # (B, N, d_model)
        tokens = self.proj(fused)
        seq_len = tokens.size(1)
        tokens = tokens + self.pos_embed[:, :seq_len, :]
        return self.layer_norm(tokens)


class OpenTSLMSoftPromptForTurbineDiagnosis(nn.Module):
    """Canonical OpenTSLM-SoftPrompt Architecture for Wind Turbine Diagnostics.

    Implements OpenTSLM-SP (docs/opentslm-paper/03_methods.tex Section 3.2):
    1. Multi-Scale Time-Series Patch Tokenizer (T=144 steps -> 36 soft tokens)
    2. Temporal Transformer Encoder for cross-channel temporal feature modeling
    3. MLP Projector aligning continuous patch embeddings to LLM hidden space (d_llm=768)
    4. Frozen Causal LLM backbone (GPT-2, 124M) with LoRA adapters (peft r=8)
    5. Dual output:
       - Autoregressive Chain-of-Thought diagnosis text:
         Finding, Evidence, Cause, Impact, Action, and scored Answer
       - Auxiliary linear classification head for zero-latency metric evaluation
    """

    def __init__(
        self,
        in_channels: int = 11,
        patch_size: int = 4,
        d_encoder: int = 256,
        d_llm: int = 768,
        num_classes: int = len(FAULT_CLASSES),
        num_encoder_layers: int = 3,
        lora_r: int = 8,
        lora_alpha: int = 16,
        llm_model_name: str = "openai-community/gpt2",
        lambda_lm: float = 0.5,
        use_focal_loss: bool = True,
        focal_gamma: float = 1.5,
        anomaly_threshold: float = 0.35,
        lm_warmup_epochs: int = 5,
        lm_leak_coeff: float = 0.1,
    ):
        super().__init__()
        self.d_encoder = d_encoder
        self.d_llm = d_llm
        self.num_classes = num_classes
        self.lambda_lm = lambda_lm
        self.use_focal_loss = use_focal_loss
        self.focal_gamma = focal_gamma
        self.anomaly_threshold = anomaly_threshold
        self.lm_warmup_epochs = lm_warmup_epochs
        self.lm_leak_coeff = lm_leak_coeff
        self.current_epoch = 0  # updated by train loop each epoch

        # 1. Multi-scale Patch Tokenizer
        self.patch_tokenizer = MultiScalePatchTokenizer(
            in_channels=in_channels,
            patch_size=patch_size,
            d_model=d_encoder,
            max_patches=200,
        )

        # 2. Temporal Transformer Encoder
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_encoder,
            nhead=8,
            dim_feedforward=d_encoder * 4,
            dropout=0.1,
            batch_first=True,
            activation="gelu",
        )
        self.temporal_encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_encoder_layers)

        # 3. MLP Projector (d_encoder -> d_llm)
        self.projector = MLPProjector(in_dim=d_encoder, out_dim=d_llm, hidden_dim=d_llm)

        # 4. Hierarchical Classification Heads
        # Stage 1: Binary Triage Gate (0=Normal, 1=Anomaly)
        self.triage_head = nn.Sequential(
            nn.Linear(d_llm, d_llm // 2),
            nn.GELU(),
            nn.Linear(d_llm // 2, 2),
        )
        # Stage 2: Conditional Subsystem Diagnoser (12 fault classes)
        self.subsystem_head = nn.Sequential(
            nn.Linear(d_llm, d_llm // 2),
            nn.GELU(),
            nn.Linear(d_llm // 2, num_classes - 1),
        )
        # Auxiliary full 13-class Head (for backward compatibility)
        self.classifier = nn.Sequential(
            nn.Linear(d_llm, d_llm // 2),
            nn.GELU(),
            nn.Linear(d_llm // 2, num_classes),
        )

        # 5. Language Model Backbone with LoRA
        from transformers import GPT2LMHeadModel
        from peft import LoraConfig, get_peft_model

        base_llm = GPT2LMHeadModel.from_pretrained(llm_model_name)
        # Freeze base parameters
        for param in base_llm.parameters():
            param.requires_grad = False

        lora_config = LoraConfig(
            r=lora_r,
            lora_alpha=lora_alpha,
            target_modules=["c_attn"],
            lora_dropout=0.05,
            bias="none",
            fan_in_fan_out=True,
        )
        self.llm = get_peft_model(base_llm, lora_config)

    def get_time_series_embeddings(self, time_series: torch.Tensor) -> torch.Tensor:
        """Encode time series into projected continuous soft tokens."""
        patch_tokens = self.patch_tokenizer(time_series)  # (B, N, d_enc)
        encoded = self.temporal_encoder(patch_tokens)  # (B, N, d_enc)
        llm_tokens = self.projector(encoded)  # (B, N, d_llm)
        return llm_tokens

    def forward(
        self,
        time_series: torch.Tensor,
        input_ids: Optional[torch.Tensor] = None,
        attention_mask: Optional[torch.Tensor] = None,
        labels: Optional[torch.Tensor] = None,
        label_indices: Optional[torch.Tensor] = None,
        class_weights: Optional[torch.Tensor] = None,
    ) -> Dict[str, Any]:
        """Forward pass supporting dual-head training."""
        B = time_series.size(0)
        device = time_series.device

        # 1. Encode continuous time series into LLM prefix soft tokens
        ts_embeds = self.get_time_series_embeddings(time_series)  # (B, N_ts, d_llm)
        n_ts = ts_embeds.size(1)

        # 2. Hierarchical classification heads on pooled time-series representation
        pooled = ts_embeds.mean(dim=1)
        triage_logits = self.triage_head(pooled)  # (B, 2)
        subsystem_logits = self.subsystem_head(pooled)  # (B, num_classes - 1)
        direct_logits = self.classifier(pooled)  # (B, num_classes)

        # Synthesize joint probability distribution:
        # P(Normal) = Softmax(triage_logits)[:, 0]
        # P(Fault_total) = Softmax(triage_logits)[:, 1]
        # P(Subsystem_i) = P(Fault_total) * Softmax(subsystem_logits)[:, i]
        triage_probs = F.softmax(triage_logits, dim=-1)
        p_normal = triage_probs[:, 0:1]
        p_fault = triage_probs[:, 1:2]
        subsystem_probs = F.softmax(subsystem_logits, dim=-1)

        # Calibrated joint distribution using operating point threshold tau*:
        # When p_fault >= tau*, calibrated fault probability exceeds 0.5 decision boundary
        tau = getattr(self, "anomaly_threshold", 0.35)
        tau = max(1e-4, min(0.99, float(tau)))
        odds = (p_fault.clamp(min=1e-5, max=1.0 - 1e-5) / (1.0 - p_fault).clamp(min=1e-5)) * ((1.0 - tau) / tau)
        p_fault_cal = (odds / (1.0 + odds)).clamp(min=1e-5, max=1.0 - 1e-5)
        p_norm_cal = 1.0 - p_fault_cal

        calibrated_probs = torch.cat([p_norm_cal, p_fault_cal * subsystem_probs], dim=-1).clamp(min=1e-7)
        calibrated_logits = torch.log(calibrated_probs)

        outputs: Dict[str, Any] = {
            "cls_logits": calibrated_logits,
            "logits": calibrated_logits,  # Alias for backward compatibility
            "direct_logits": direct_logits,
            "triage_logits": triage_logits,
            "subsystem_logits": subsystem_logits,
            "ts_embeds": ts_embeds,
            "pooled": pooled,
        }

        total_loss = torch.tensor(0.0, device=device)

        if label_indices is not None:
            # Stage 1 Loss: Binary Triage (Normal=0 vs Fault=1)
            is_fault = (label_indices > 0).long()
            if getattr(self, "use_focal_loss", True):
                ce_triage = F.cross_entropy(triage_logits, is_fault, reduction="none")
                pt_t = torch.exp(-ce_triage)
                triage_loss = (((1.0 - pt_t) ** getattr(self, "focal_gamma", 1.5)) * ce_triage).mean()
            else:
                triage_loss = F.cross_entropy(triage_logits, is_fault)
            outputs["triage_loss"] = triage_loss

            # Stage 2 Loss: Conditional Subsystem Diagnoser on Faults Only
            fault_mask = label_indices > 0
            if fault_mask.any():
                subsystem_targets = label_indices[fault_mask] - 1
                subsystem_loss = F.cross_entropy(subsystem_logits[fault_mask], subsystem_targets)
            else:
                subsystem_loss = torch.tensor(0.0, device=device)
            outputs["subsystem_loss"] = subsystem_loss

            # Direct auxiliary loss for regularization
            direct_loss = F.cross_entropy(direct_logits, label_indices, weight=class_weights)
            outputs["direct_loss"] = direct_loss

            cls_loss = 1.5 * triage_loss + 2.0 * subsystem_loss + 0.5 * direct_loss
            outputs["cls_loss"] = cls_loss
            total_loss = total_loss + 3.0 * cls_loss

        # 3. Autoregressive Language Modeling over text tokens conditioned on soft prompt
        if input_ids is not None:
            # Gradient stop-gate: isolate encoder from LM loss during warm-up epochs.
            # After warm-up, allow a small leak so LM can still nudge the encoder gently.
            in_warmup = self.training and (self.current_epoch < self.lm_warmup_epochs)
            leak = 0.0 if in_warmup else self.lm_leak_coeff
            ts_for_lm = ts_embeds.detach() + leak * (ts_embeds - ts_embeds.detach())

            # Dynamic lambda: ramp from 0 -> lambda_lm over warm-up, then hold constant.
            if in_warmup:
                effective_lambda = 0.0
            elif self.current_epoch < 2 * self.lm_warmup_epochs:
                ramp = (self.current_epoch - self.lm_warmup_epochs) / max(1, self.lm_warmup_epochs)
                effective_lambda = self.lambda_lm * ramp
            else:
                effective_lambda = self.lambda_lm

            text_embeds = self.llm.get_input_embeddings()(input_ids)  # (B, S, d_llm)
            inputs_embeds = torch.cat([ts_for_lm, text_embeds], dim=1)  # (B, N_ts + S, d_llm)

            if attention_mask is not None:
                ts_mask = torch.ones(B, n_ts, dtype=attention_mask.dtype, device=device)
                ext_mask = torch.cat([ts_mask, attention_mask], dim=1)
            else:
                ext_mask = torch.ones(B, inputs_embeds.size(1), dtype=torch.long, device=device)

            if labels is not None:
                # Mask out time-series patch prefix so no loss is computed on soft tokens
                ts_labels = torch.full((B, n_ts), -100, dtype=labels.dtype, device=device)
                ext_labels = torch.cat([ts_labels, labels], dim=1)
            else:
                ext_labels = None

            lm_out = self.llm(
                inputs_embeds=inputs_embeds,
                attention_mask=ext_mask,
                labels=ext_labels,
            )
            outputs["lm_logits"] = lm_out.logits
            if lm_out.loss is not None:
                outputs["lm_loss"] = lm_out.loss
                total_loss = total_loss + effective_lambda * lm_out.loss

        outputs["loss"] = total_loss
        return outputs

    @torch.no_grad()
    def generate_diagnosis(
        self,
        time_series: torch.Tensor,
        tokenizer: Any,
        prompt_text: Optional[str] = None,
        max_new_tokens: int = 150,
        min_new_tokens: int = 5,
        temperature: float = 0.7,
        top_p: float = 0.9,
    ) -> Dict[str, Any]:
        """Autoregressively generate natural language diagnosis and parse structured findings."""
        self.eval()
        if time_series.dim() == 2:
            time_series = time_series.unsqueeze(0)

        device = time_series.device
        B = time_series.size(0)

        # Encode time series into soft prompt tokens
        ts_embeds = self.get_time_series_embeddings(time_series)
        pooled = ts_embeds.mean(dim=1)

        # Direct 13-class head (primary prediction — bypasses razor-thin triage gate)
        direct_logits = self.classifier(pooled)
        direct_probs = F.softmax(direct_logits, dim=-1)
        direct_pred_idx = torch.argmax(direct_probs, dim=-1).item()
        direct_max_prob = direct_probs[0, direct_pred_idx].item()

        # Hierarchical gate (secondary — used as cross-check)
        triage_logits = self.triage_head(pooled)
        triage_probs = F.softmax(triage_logits, dim=-1)
        anomaly_prob = triage_probs[0, 1].item()

        subsystem_logits = self.subsystem_head(pooled)
        subsystem_probs = F.softmax(subsystem_logits, dim=-1)
        sub_pred_idx = torch.argmax(subsystem_probs, dim=-1).item()
        sub_max_prob = subsystem_probs[0, sub_pred_idx].item()

        thresh = getattr(self, "anomaly_threshold", 0.35)
        gate_fires = anomaly_prob >= thresh

        # Determine final prediction:
        # 1. If direct head predicts a fault class (idx > 0), trust it.
        # 2. If calibrated triage gate fires (anomaly_prob >= thresh), trust the subsystem head.
        # 3. Otherwise fall back to normal_operation.
        if direct_pred_idx > 0:
            cls_pred_idx = direct_pred_idx
            hierarchical_subsystem = SUBSYSTEM_CLASSES[cls_pred_idx]
            hierarchical_triage = "fault"
            is_anomaly = True
        elif gate_fires:
            cls_pred_idx = sub_pred_idx + 1
            hierarchical_subsystem = SUBSYSTEM_CLASSES[cls_pred_idx]
            hierarchical_triage = "fault"
            is_anomaly = True
        else:
            cls_pred_idx = 0
            hierarchical_subsystem = "normal_operation"
            hierarchical_triage = "normal"
            is_anomaly = False

        if prompt_text is None:
            # Concrete summary tokens from actual telemetry (Phase 4B)
            mean_wind = time_series[0, :, 0].mean().item()
            mean_pwr = time_series[0, :, 1].mean().item()
            max_gear = time_series[0, :, 4].max().item()
            max_bear = time_series[0, :, 5].max().item()
            if time_series.size(-1) >= 9:
                pitch_spread = (torch.max(time_series[0, :, 6:9], dim=-1).values - torch.min(time_series[0, :, 6:9], dim=-1).values).max().item()
            else:
                pitch_spread = 0.0

            ts_stats = (
                f"[Telemetry Summary: WindAvg={mean_wind:.1f}m/s, PowerAvg={mean_pwr:.0f}kW, "
                f"GearTMax={max_gear:.1f}°C, BearTMax={max_bear:.1f}°C, PitchSpreadMax={pitch_spread:.1f}°]\n"
            )

            # Condition LLM on classification head diagnosis (Phase 4A)
            prompt_prefix = f"{ts_stats}Question: Analyze the 24-hour turbine telemetry. Provide triage, subsystem, evidence, and action.\n\nDiagnosis:\n"
            if not is_anomaly:
                prompt_text = prompt_prefix + "Triage: normal\nSubsystem: normal_operation\nRationale: "
            else:
                prompt_text = prompt_prefix + f"Triage: {hierarchical_triage}\nSubsystem: {hierarchical_subsystem}\nRationale: "

        prompt_ids = tokenizer(prompt_text, return_tensors="pt").input_ids.to(device)
        prompt_embeds = self.llm.get_input_embeddings()(prompt_ids)
        inputs_embeds = torch.cat([ts_embeds, prompt_embeds], dim=1)

        pad_id = tokenizer.pad_token_id or tokenizer.eos_token_id
        effective_min = min(min_new_tokens, max_new_tokens)
        gen_tokens = self.llm.generate(
            inputs_embeds=inputs_embeds,
            max_new_tokens=max_new_tokens,
            min_new_tokens=effective_min,
            pad_token_id=pad_id,
            eos_token_id=tokenizer.eos_token_id,
            repetition_penalty=1.2,
            no_repeat_ngram_size=3,
            do_sample=(temperature > 0.0),
            temperature=max(0.1, temperature) if temperature > 0.0 else 1.0,
            top_p=top_p if temperature > 0.0 else 1.0,
        )

        decoded = tokenizer.decode(gen_tokens[0], skip_special_tokens=True).strip()
        if not decoded and len(gen_tokens[0]) > 0:
            decoded = tokenizer.decode(gen_tokens[0], skip_special_tokens=False).strip()

        parsed_subsystem = hierarchical_subsystem
        parsed_triage = hierarchical_triage
        parsed_answer = hierarchical_subsystem

        full_generated_text = f"Triage: {parsed_triage}\nSubsystem: {parsed_subsystem}\nRationale: {decoded}"

        for line in decoded.split("\n"):
            l = line.strip()
            low_l = l.lower()
            if low_l.startswith("answer:"):
                parsed_answer = l.split(":", 1)[1].strip()
            elif low_l.startswith("recommendation:") and "diagnosis:" in low_l:
                diag_part = low_l.split("diagnosis:", 1)[1].strip()
                parsed_answer = diag_part.split(".", 1)[0].strip()

        return {
            "generated_text": full_generated_text,
            "cls_pred_idx": cls_pred_idx,
            "parsed_subsystem": parsed_subsystem or parsed_answer,
            "parsed_triage": parsed_triage,
            "parsed_answer": parsed_answer,
        }

