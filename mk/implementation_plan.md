# Implementation Plan: OpenTSLM-SoftPrompt Architecture with 24-Hour Context & Subsystem Triage

Implement the canonical **OpenTSLM-SoftPrompt** (`OpenTSLM-SP`) architecture as defined in the OpenTSLM paper (`docs/opentslm-paper/03_methods.tex`) and problem statement (`docs/problem-statement.md` Section 6), expanding the context window to **24 hours (144 steps at 10-minute resolution)** for immediate alarm explanation, operational triage (`fault` / `benign_stop` / `normal`), and subsystem classification.

---

## User Review Required

> [!IMPORTANT]
> **24-Hour Context Window & Triage Targets**:
> - **Telemetry Context**: Expanded from 12h (72 steps) to **24h (144 steps)**, capturing full diurnal cycles, steady-state baselines, and thermal dissipation trends preceding alarms.
> - **Patch Tokens**: With patch size $p=4$, 144 timesteps produce $N = 36$ continuous time-series soft tokens ($N = 18$ for $p=8$), fitting comfortably inside the LLM prompt.
> - **Structured Multi-Stage Output**: The target text incorporates immediate triage and explanation:
>   ```text
>   Triage:         fault | benign_stop | normal
>   Subsystem:      <subsystem_class>
>   Alarm Event:    <message> (Code: <code_id>, Severity: <severity>)
>   Rationale:      Step-by-step 24h telemetry evidence (power-wind curve, thermal rise, vibration shocks).
>   Recommendation: Actionable dispatch intervention.
>   Answer:         <subsystem_class>
>   ```
> - **MacBook Training Feasibility**:
>   36 soft tokens per 24h sample is extremely lightweight for GPT-2 / LoRA ($r=8$). VRAM remains **< 1.8 GB**, training in **~1–2 minutes per epoch** on Apple Silicon (`mps`).


---

## Proposed Changes

### Model Architecture

#### [MODIFY] [`mk/src/models/architecture.py`](file:///Users/maximiliankalk/Coding/Private/Zurich%20EHL%20Hackathon/zurich_ehl_timeseries/mk/src/models/architecture.py)
- **Multi-Scale Patch Tokenizer (`MultiScalePatchTokenizer`)**:
  - Encodes continuous SCADA channels with parallel kernel strides ($p=2$ for rapid shocks, $p=4$ for baseline trends) and learnable temporal positional encodings.
- **MLP Projector (`MLPProjector`)**:
  - Projects time-series patch representations into the language model's embedding dimension ($d_{\text{llm}} = 768$).
- **`OpenTSLMSoftPromptForTurbineDiagnosis`**:
  - Integrates `openai-community/gpt2` with LoRA adapters (`peft.LoraConfig(r=8, target_modules=['c_attn'])`).
  - Prepend time-series patch embeddings as continuous soft tokens: $\mathbf{X}_{\text{inputs\_embeds}} = [\mathbf{Z}_{\text{time\_series}}, \mathbf{T}_{\text{prompt}}]$.
  - Auxiliary linear classification head on pooled patch tokens.
  - Joint loss during training:
    $$\mathcal{L}_{\text{total}} = \mathcal{L}_{\text{cls}} + \lambda_{\text{text}} \mathcal{L}_{\text{lm}}$$
  - `generate_diagnosis(time_series, tokenizer, max_new_tokens=120)` method that runs autoregressive decoding to output the clinical-style explanation and parses the final `Answer: <class>`.

---

### Data Collator & Training Loop

#### [MODIFY] [`mk/src/models/opentslm_dataset.py`](file:///Users/maximiliankalk/Coding/Private/Zurich%20EHL%20Hackathon/zurich_ehl_timeseries/mk/src/models/opentslm_dataset.py)
- Add `OpenTSLMDataCollator`:
  - Tokenizes `pre_prompt` and target `answer` (`Rationale: ... Recommendation: ... Answer: <label>`).
  - Masks input prompt tokens with `-100` so loss is only computed over generated answer tokens (standard causal LM training).
  - Batches `time_series`, `input_ids`, `attention_mask`, `labels`, and `label_indices`.

#### [MODIFY] [`mk/src/models/train.py`](file:///Users/maximiliankalk/Coding/Private/Zurich%20EHL%20Hackathon/zurich_ehl_timeseries/mk/src/models/train.py)
- Support training both the classification objective and the language modeling generation objective.
- Track both **Macro-F1** (classification) and **Perplexity / LM Loss** (text generation).
- Log sample generated diagnoses at the end of each epoch to monitor text quality directly in the console.

---

## Verification Plan

### Automated Tests
- Run `pytest mk/tests/test_opentslm_softprompt.py`:
  - Test forward pass with soft prompt concatenation.
  - Test dual loss calculation ($\mathcal{L}_{\text{cls}} + \mathcal{L}_{\text{lm}}$).
  - Test `generate_diagnosis()` producing text starting with `Rationale:` and containing `Answer:`.
  - Verify gradient flow into LoRA adapters and time-series encoder while base LLM remains frozen.
- Run existing test suite (`pytest mk/tests`) to ensure 100% backward compatibility across connectors, data inspection, and preprocessor.

### MacBook Training Run
- Run a 3-epoch test run on Apple Silicon MPS / CPU:
  ```bash
  .venv/bin/python mk/src/models/train.py --epochs 3 --batch-size 4
  ```
- Verify throughput, VRAM usage (< 2 GB), and sample generated explanation text.
