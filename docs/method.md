# Turbine Alarm Explainer — method and results

*Temporal AI Challenge (Aionic Labs × ETH ASL × Nebius), 12–13 September 2026. This is the complete account of what
we built, why, and what it measures. Every number here is reproducible from the repository; sources are named per
table.*

## 1. The problem and why we framed it this way

A wind farm records about 300 SCADA channels per turbine every 10 minutes and, separately, a controller log of
events with a text message ("Overload generator fan 2", "Low gearbox oil pressure"). The log arrives *after* the
turbine has stopped. Many fault stops are preceded by hours of visible drift: a bearing heating faster than load
explains, gear-oil pressure sagging, tower vibration creeping up. Nobody watches 300 channels × 14 turbines for that.

We chose an **early-warning** framing rather than post-hoc alarm classification: given the last 24 h of sensor data,
*will a fault-related stop begin within the next H hours, in which subsystem, and why?* The value is lead time —
de-rate instead of a forced stop, send the technician in the morning instead of an emergency call-out. A plain
classifier can give the yes/no; a Time-Series Language Model (TSLM) can give the yes/no **and** the evidence from the
same raw signals, with no per-site feature engineering. That difference is the product.

Two constraints shaped everything: **no leakage** (nothing after the window end is ever an input; the alarm text,
code and category are labels only) and **honesty per class** (grid, comms and manual stops have no precursor in
10-minute data; we report them as such rather than averaging them away).

## 2. Data

**Source.** Two Cubico wind farms exported from Greenbyte SCADA, CC-BY-4.0, on Zenodo: Penmanshiel (14 × Senvion
MM82, UK) and Kelmarsh (6 × Senvion MM92, UK). Years 2017–2021. Per turbine-year: a 10-minute telemetry file
(299 columns, ~70 populated) and a status log (start, end, status, code, message, IEC category).

**Channels (19).** Wind speed and direction, nacelle ambient temperature, active power, rotor speed, blade pitch A,
nacelle position, generator bearing front/rear temperature, stator temperature, gear oil temperature, main bearing
temperature, gear-oil inlet pressure, reactive power, grid voltage, grid frequency, tower acceleration X, plus two
derived: power-curve residual (power minus the turbine-year's own median power at that wind speed) and yaw
misalignment (wind direction minus nacelle position). Greenbyte's derived KPI columns (lost production, potential
power, availability) are never inputs — they are back-calculated from the log and would leak the label.

**Taxonomy.** ~130 raw alarm messages → 11 subsystem classes by case-insensitive substring rules
(`src/turbine_tslm/data/taxonomy.yaml`): 8 fault classes (generator_cooling, gearbox_lubrication, pitch_system,
converter_grid, structural_overspeed, brake_hydraulics, yaw_cable, sensor_comms), 2 benign-stop classes, 1 context
class (manual/maintenance/test). Positives are fault-class events that stopped the turbine (Stop status, or a Warning
filed as IEC Forced outage).

**Windows.** 24 h = 144 steps ending at an anchor `t`. Positives: for every fault-class stop (deduped per class
within 2 h), three records at `t = alarm − 1 h, − 3 h, − 6 h`, dropped if the turbine is already stopped despite
wind at `t` (the controller has acted) or a manual stop overlaps the window. Negatives: hourly anchors with the
turbine producing, no fault-class event in the next 6 h, none ongoing, no stop in the previous 2 h; sampled 2 : 1.
Labels stored per record: `fault_within_{1,3,6}h`, lead time, next-event message / duration / IEC (never inputs).
Windows with more than 20 % missing in any channel are dropped; the effective training period is mid-2018 → 2019
because pitch, gear-oil temperature, main-bearing temperature and tower acceleration do not exist earlier.

**Splits (no leakage).**

| split | data | tests |
|---|---|---|
| train | Penmanshiel turbines 1–12, 2017–19 | — |
| val | Penmanshiel turbines 13–15, 2017–19 | unseen turbines, same site (model selection only) |
| test_a | Penmanshiel, all turbines, 2020–21 | unseen time |
| test_b | Kelmarsh, all turbines, 2017–21 | unseen site **and** turbine model (MM82 → MM92) |

Counts: Penmanshiel 3,901 windows (train 572 pos / 1,144 neg · val 148 / 296 · test_a 582 / 1,164); Kelmarsh
2,655 (889 pos / 1,778 neg). The split is stored as a record annotation by the TimeNet connector, so every model —
TSLM, gradient boosting, text-only LLM — is scored on identical records (`data/interim/*_windows.parquet`, committed).

**Pipeline.** Raw zips → `data/greenbyte.py` (readers) → `data/channels.py` → `data/windows.py` (events → anchors →
labels → 144 × 19 windows, split) → `connectors/cubico/` (TimeNet `TimeFDataset`: 19 series per record, annotations
incl. split, a `ClassificationTask` and an `AnswerTask` with the filled prompt) → `timenet-build` → local registry →
`training/turbine_dataset.py` (OpenTSLM `QADataset`). Nothing in training or evaluation parses CSVs.

## 3. Tasks

| id | question put to the model | answer | status |
|---|---|---|---|
| **T1** early warning (headline) | "…decide whether a fault-related stop is likely to begin within the next {H} hours. If yes, name the subsystem…" | `Answer: no` / `Answer: yes, <class>` | trained, scored |
| **T3** post-hoc explanation | "A status event began about one hour after the end of this window and stopped the turbine. Describe what the signals show and name the subsystem." | `Answer: <class>` | trained jointly with T1 (same windows as the 1 h positives) |
| T2 warning escalation | "The controller has just raised the warning '…'. Will it escalate to a fault stop within 24 h?" | yes / no | **built, not trained**: only 7 escalating warnings in train (2 val, 17 test_a, 45 Kelmarsh); warnings are dominated by comms / time-sync / yaw-motor-current messages — a negative result |
| T4 impact (kWh), T5 localisation | — | — | not attempted (need lost-production sums / a different window length) |

Prompt for T1 (fixed text, no loss): turbine id and type, rated power, month, state at `t`, the horizon, the class
list, "Do not state a decision until the final line. End with 'Answer: '." Per-channel text: *"generator bearing rear
temperature in °C, 10-minute means over 24 h, mean 42.2 std 4.0[, first 6 h 44.0, 6 h before the end 38.2, last hour
38.5]:"* followed by the 144 z-scored values. Post-prompt: "Assessment:".

## 4. Models

**OpenTSLM** (Stanford / ETH, `third_party/OpenTSLM`) with two variants, both on a frozen **Llama-3.2-1B**:

- **Flamingo**: each channel is patched (4 steps → 1 token, 36 tokens per channel) by a CNN tokenizer, pooled by a
  perceiver resampler and injected through gated cross-attention layers between the LLM's blocks. Trainable:
  tokenizer, perceiver, cross-attention, input embeddings (838 M parameters, fp32). Prompt length is independent of
  the number of channels — the reason we started here with 19 channels.
- **SP (soft prompt)**: the patches become tokens *inside* the LLM input (19 × 36 = 684 series tokens per record);
  encoder + projector trained, plus LoRA (r 16) on the backbone (13.6 M trainable).

Both warm-start from OpenTSLM's published HAR chain-of-thought checkpoints (`OpenTSLM/llama-3.2-1b-har-flamingo`
/ `-sp`) — the stage whose answers already end in "Answer: <label>". The mentor's advice to start from a *neutral*
checkpoint (M4 captioning stage) is prepared as an ablation config (`configs/t1_flamingo_llama1b_m4init.yaml`).

**Baselines** (same windows, same scorer): always-no; XGBoost on 24 h summary statistics per channel (teammate,
`scripts/train_xgboost_baseline.py`), with and without operational context; a text-only LLM given the same
statistics (Gemini, `scripts/run_gemini_text_baseline.py`, in progress).

## 5. Training targets: from a label to a checkable explanation

**Stage 1 — label only.** Target = `Answer: no` / `Answer: yes, <class>`. Loss only on the answer tokens.

**Stage 2 — reason first.** There are no technician reports in the data, so the reasoning text is generated by
**rules over the window only** (`src/turbine_tslm/data/evidence.py`): a state sentence (wind trend, producing / idle),
up to three evidence sentences, a conclusion, then the same `Answer:` line. Rules and thresholds (99th percentiles of
the Penmanshiel tables, so a sentence means "top 1 % for that quantity"):

| evidence | rule |
|---|---|
| thermal ramp | 6 h rise ≥ 6 °C at steady load (|Δpower| < 200 kW) or ≥ 15 °C under rising load, for generator front/rear bearing, stator, gear oil, main bearing; "its 24 h maximum" when applicable |
| bearing asymmetry | rear − front bearing changed by ≥ 4 °C vs the window's own mean |
| lubrication | gear-oil inlet pressure down ≥ 25 % over 6 h at similar load, producing at both ends |
| structural | tower acceleration last hour ≥ 2 × its 24 h median |
| grid | voltage step ≥ 8 V within 10 min; frequency deviation ≥ 0.18 Hz |
| pitch / rotor | blades feathered > 60° with the rotor stopped in wind > 4.5 m/s; high wind ≥ 12 m/s with rotor and power state |
| power curve | ≥ 150 kW below the farm curve over the last 3 h while producing |
| yaw | nacelle ≥ 25° off the wind |

The class-specific conclusion ("This pattern precedes a generator cooling stop.") is written **only when a sentence
is relevant to that class** (bearing/stator → cooling; oil → gearbox; wind/rotor/tower → overspeed; grid → converter;
yaw → yaw). Otherwise the target says so: "No specific precursor for it is visible in these signals, but a <class>
stop follows." Negatives: "No sign of a developing fault." On 300 training windows, overspeed gets a class-relevant
sentence in 53 / 60 cases, cooling 5 / 19, gearbox 1 / 10 — an honest picture of how subtle 10-minute precursors are.

Why rules and not an LLM: the problem statement's standard is "no claims the data cannot support". Rule-generated
text is faithful by construction and, crucially, **checkable afterwards** (§ 7). An LLM paraphrase is optional polish
we did not spend time on.

**Rich channel text.** The first reason-first model wrote fluent explanations whose numbers were guessed: claims that
need only the window mean (given in the channel text) verified at 77–100 %, claims that need the last hour or a 6 h
delta read off the z-scored series verified at 9–30 %. A 1B model cannot read those values off the patches. Fix:
write the three quantities the rules quote (first 6 h mean, value 6 h before the end, last-hour mean) into every
channel description. Still window-only input; val loss on identical targets fell from 0.345 to 0.146.

**RFT (rejection-sampling fine-tune)** — the mentor's "RL on top of the fine-tune", with a verifiable reward. From
the best checkpoint, sample 3 explanations per training record (temperature 0.8); reward = label correct **and** every
numeric claim verified **and** conclusion consistent with the answer line; keep the best passing sample per record
(69 % of records had one), fall back to the rule target otherwise; fine-tune one epoch at lr 3e-5.

## 6. Training recipe and infrastructure

- `training/train.py`: YAML config → model (Flamingo / SP, optional warm start from a Hub or local checkpoint) →
  AdamW (weight decay 0.1 on gated cross-attention, 0 elsewhere, as upstream), linear warm-up 3 % then linear decay,
  batch 4–8, bf16 autocast with fp32 master weights, grad-clip 1.0, up to 5 epochs, **early stopping on validation
  loss with patience 2**, trainable-parameters-only checkpoints every 100 steps (the VM can be pre-empted; `resume`
  picks up `last.pt`). Diagnostic test losses per epoch are logged but never used for selection.
- Every run logs to Weights & Biases (project `turbine-tslm`) and to `outputs/<run>/train_log.jsonl`; results are
  copied to `docs/results/<run>/` (report, metrics, faithfulness, gzipped predictions).
- Hardware: one Nebius VM, RTX PRO 6000 (96 GB). Label-only run: 23 min training; evidence run: ~45 min training
  + ~45 min generation-based evaluation. Jobs are queued with `scripts/vm_queue.sh` under a GPU lock.
- Two infrastructure bugs found and fixed on the way, both worth knowing for anyone reusing OpenTSLM: the 0.0.2
  open-flamingo wheel breaks `OpenTSLMFlamingo` (2.x needed, with pin overrides); and OpenTSLM pads batched prompts
  on the right, which garbles generation for the shorter prompts in a batch — we generate with left padding.

## 7. Evaluation

**Scorer** (`eval/score.py`, one `predictions.jsonl` contract for every model): per split × horizon, AUROC, average
precision, **recall at 10 % (and 5 %) false-alarm rate** on the score, hard precision / recall / F1 on the written
label, per-class recall at 10 % FAR and subsystem accuracy, macro-F1 over positives, confusion matrix. T3 is scored
as 7-class subsystem accuracy. Floors: always-no (AUROC 0.500, recall 0) and random.

**Faithfulness** (`eval/faithfulness.py`, the mentor's "judge whether the reasoning matches the answer", done with
rules): every numeric claim in a generated explanation is parsed (temperature rises, bearing asymmetry, power, wind,
oil-pressure drop, tower ratio, grid steps, yaw error, rotor speed…) and recomputed from the window with loose
tolerances; we report claim precision, the share of texts with at least one wrong number, the share with numbers no
rule can check, and whether the conclusion sentence agrees with the `Answer:` line. An LLM judge for coherence and
actionability is implemented (`scripts/llm_judge.py`, Claude or OpenAI backend) and complements, not replaces, this.

**Scores for text models.** In generate mode the yes/no likelihood is conditioned on the model's own explanation and
becomes near-binary; ranking metrics for those models are therefore taken from a second, teacher-forced pass
(`predict_mode: loglik`) over the eight answer candidates. Hard-label metrics use the written text.

## 8. Results

**One-table summary of every model, generated from the result files: [`docs/results/FINAL_TABLE.md`](results/FINAL_TABLE.md).**

All numbers from `docs/results/<run>/results.json` and `faithfulness.json`; the XGBoost rows are the teammate's
`v1` predictions re-scored with the same harness (`docs/results/xgboost_*/`), which is why they differ slightly from
`docs/benchmark.md`.

**Early warning (T1), pooled over horizons.**

| model | val AUROC · R@10 % | test_a (unseen years) AUROC · R@10 % · F1 · subsys | test_b (Kelmarsh) AUROC · R@10 % · F1 · subsys |
|---|---|---|---|
| always no | 0.500 · 0.00 | 0.500 · 0.00 · – · – | 0.500 · 0.00 · – · – |
| XGBoost, sensor statistics | – | 0.780 · 0.51 · 0.64 · 0.51 | 0.596 · 0.21 · 0.20 · 0.09 |
| XGBoost, sensors + context | – | 0.779 · 0.52 · 0.64 · 0.50 | 0.614 · 0.22 · 0.19 · 0.09 |
| Flamingo, label only | 0.747 · 0.53 | 0.698 · 0.25 · 0.35 · 0.19 | 0.613 · 0.24 · 0.24 · 0.08 |
| SP + LoRA, label only | 0.787 · 0.55 | 0.707 · 0.40 · 0.55 · 0.48 | 0.623 · 0.24 · 0.34 · 0.16 |
| Flamingo, reason-first (basic text) | 0.634 · 0.35 | 0.650 · 0.22 · 0.53 · 0.42 | 0.565 · 0.23 · 0.37 · 0.17 |
| Flamingo, reason-first + rich text, graded score | 0.770 · 0.49 | 0.721 · 0.39 · 0.54 · 0.48 | 0.595 · 0.26 · **0.42** · **0.25** |
| **Flamingo, reason-first + rich text + 1 epoch RFT, graded score (headline)** | 0.759 · **0.53** | **0.768 · 0.42 · 0.62** · 0.47 | **0.638 · 0.30** · 0.37 · 0.17 |
| (same two checkpoints, generate-mode near-binary score) | 0.720 · 0.49 / 0.706 · 0.51 | 0.672 · 0.35 / 0.708 · 0.39 | 0.589 · 0.27 / 0.601 · 0.28 |

"Graded score" = `predict_mode: rescore` (§ 7): conclusion candidates scored conditioned on the model's own evidence
sentences; the plain teacher-forced loglik after the prompt gives AUROC ≈ 0.5 for reason-first models (off-
distribution) and is not used. The basic-text reason-first row is the generate-mode score. Per horizon, headline model, recall at 10 % FAR: 1 h 0.45 / 0.30,
3 h 0.32 / 0.27, 6 h 0.27 / 0.23 (test_a / test_b).

**Confidence intervals (paired bootstrap, 2,000 resamples, `scripts/bootstrap_ci.py`, `docs/results/bootstrap/`).**
Kelmarsh recall at 10 % FAR: RFT 0.295 [0.260, 0.328] vs XGBoost + context 0.223 (paired difference −0.067
[−0.107, −0.026]), vs XGBoost sensors-only 0.206 (−0.089 [−0.127, −0.049]), vs label-only SP 0.244 (−0.048 [−0.090,
−0.007]), vs the rich model before RFT 0.258 (+0.037 [+0.012, +0.062] for RFT). Kelmarsh AUROC: RFT 0.638 [0.614,
0.662], XGBoost 0.596–0.614, label-only TSLMs 0.613–0.623. Unseen years (test_a): XGBoost 0.523 recall vs RFT 0.425
(+0.099 [+0.044, +0.162], XGBoost better); AUROC 0.779 vs 0.768 (overlapping). Rich channel text vs basic text
(generate-mode scores): 0.268 vs 0.230, −0.035 [−0.066, −0.003].

**Post-hoc explanation (T3), subsystem accuracy over 7 classes:** headline model 0.63 val, 0.65 test_a, 0.31 test_b;
after RFT 0.56 / 0.61 / 0.48.

**RFT outcome.** One round (3 samples per record at temperature 0.8; 1,308 of 1,883 records had a label-correct,
fully verified sample, 1.38 passing samples per record on average) left faithfulness unchanged (0.87 vs 0.86) but,
with the graded score, improved ranking on every split — Kelmarsh AUROC 0.595 → 0.638, recall at 10 % FAR 0.258 →
0.295 (paired +0.037 [+0.012, +0.062]); unseen years 0.721 → 0.768, 0.38 → 0.42 — and made the written alarms more
conservative (Kelmarsh precision 0.39 → 0.58, recall 0.46 → 0.27; subsystem accuracy 0.25 → 0.17): the kept samples
are, by construction, cases the model already got right. The LLM judge also prefers its text (grounded 2.9 vs 2.4,
supports-answer 57 % vs 48 %). It is therefore the headline model for the score and the text; the rich model before
RFT keeps the best written-decision quality on Kelmarsh.

**Per class, Kelmarsh, recall at 10 % FAR (headline model / XGBoost sensors-only):** structural_overspeed 0.59 / 0.40,
yaw_cable 0.35 / 0.14, generator_cooling 0.13 / 0.17, pitch_system 0.09 / 0.09, converter_grid 0.09 / 0.11,
brake_hydraulics 0.00 / 0.07 (gearbox_lubrication has no Kelmarsh positives). Subsystem accuracy when the model
writes a class: overspeed 0.55 vs 0.28 (0.81 on test_a), cooling 0.11 (0.60 on the post-hoc question). Per horizon on
Kelmarsh at 1 h: 0.30 vs 0.28.

**Is the explanation true?**

| model | claim precision (val / test_a / test_b) | texts with a wrong number | conclusion = answer | well-formed |
|---|---|---|---|---|
| reason-first, basic text | 0.52 (0.52 / 0.52 / 0.46) | 76 % | 1.00 | 100 % |
| reason-first + rich text (headline) | **0.86** (0.88 / 0.87 / 0.85) | **28 %** | 1.00 | 100 % |
| + RFT epoch | 0.87 (0.89 / 0.88 / 0.86) | 26 % | 1.00 | 100 % |

**LLM judge** (`scripts/llm_judge.py`, gpt-5, the same 40 held-out windows — 20 fault, 20 quiet — for every model;
`docs/results/llm_judge/judge_n40.json`). Scores 1–5 for grounded (claims match the facts computed from the window),
coherent, actionable, plus whether the reasoning supports the answer line:

| model | grounded | coherent | actionable | supports answer |
|---|---|---|---|---|
| reason-first, basic text | 1.70 | 3.33 | 1.00 | 45 % |
| headline (rich text) | 2.38 | 3.35 | 1.00 | 48 % |
| headline + RFT | 2.88 | 3.92 | 1.00 | 58 % |

The judge's ordering agrees with the rule checker but it is harsher (one wrong figure, or a conclusion that
contradicts the true outcome, costs the whole text); it rates the RFT model as the better *text* (more coherent,
more often supporting its own answer) while the headline stays the better alarm model on Kelmarsh. "Actionable" is
1.0 for every model because the targets never recommend an action — the next cheap improvement is a rule-derived
recommendation sentence per class in the training targets.

**Training dynamics.** Label-only models overfit after epoch 2 (val loss 0.145 → 0.217 for Flamingo); SP + LoRA
fits fastest and its Kelmarsh loss rises from 0.16 to 0.50 by epoch 4 — the adapted backbone memorises the training
farm. Reason-first targets overfit later (epoch 3) and keep the Kelmarsh loss flat: richer supervision per window
regularises. Curves: W&B project `turbine-tslm`, `docs/results/*/train_log.jsonl`.

## 9. What we learned (and would tell the next team)

1. **Reason-first targets improve the decision, not just the text.** Hard F1 on the unseen farm 0.24 → 0.42,
   subsystem accuracy 0.08 → 0.25, with the label line unchanged. This reproduces OpenTSLM's claim on our data.
2. **A 1B TSLM cannot read values off patches; give it the numbers it must quote.** Rich channel text took claim
   precision from 0.52 to 0.86 in one run, with identical targets and generation.
3. **Check the text mechanically.** Rule-generated targets make every generated number verifiable; 28 % of
   explanations still contain a wrong number, and we say so instead of hiding it behind fluency.
4. **Batched generation needs left padding.** 19–77 % of OpenTSLM's generations were mid-sentence garbage before
   the fix. Any evaluation of a TSLM's text should check the share of well-formed outputs first.
5. **Cross-site generalisation is the honest test, and it is hard.** Everything drops from val to Kelmarsh; SP +
   LoRA drops fastest. On Kelmarsh the RFT model beats the gradient-boosting baseline on both ranking numbers
   (recall 0.30 vs 0.22 at 10 % FAR, AUROC 0.64 vs 0.61, paired intervals exclude zero for recall), its written
   decisions are far more useful (subsystem accuracy 0.17–0.25 vs 0.09), and it is the only model with an
   explanation; on unseen years the baseline is stronger on recall (0.52 vs 0.42) with equal AUROC.
6. **Not every fault has a precursor.** Overspeed is learnable from 10-minute data; thermal classes only partly
   (83 and 54 training positives); grid, yaw, brake are at chance; warning escalation is not learnable at all here.

## 10. Limitations and claims we do not make

- Ground truth is the alarm log, not a technician's diagnosis; the "subsystem" is the controller's message class.
- Explanations are rule-derived and model-written; they are checkable, not expert-written, and 28 % contain at
  least one wrong number.
- Positives without a class-relevant precursor are trained with an honest "no specific precursor is visible … but
  a <class> stop follows" text, and the model sometimes produces that sentence on negatives; that costs precision.
- One manufacturer (Senvion), two farms, mid-2018 → 2019 training data, 572 positive events; no remaining-useful-life
  or long-horizon forecasting.
- The generate-mode AUROC of the text models is not comparable with the label-only AUROC (near-binary score).

## 11. Reproduce

```bash
uv sync --group dev --extra wandb                      # opentslm from the submodule, open-flamingo 2.x
DATA_DIR=./data scripts/download_data.sh              # 4.6 GB, idempotent
DATA_DIR=./data uv run python scripts/build_windows.py penmanshiel --out data/interim/penmanshiel_windows.parquet
DATA_DIR=./data uv run python scripts/build_timenet.py # both farms into the TimeNet registry
uv run python -m turbine_tslm.training.train configs/t1_flamingo_llama1b.yaml                # label-only MVP
uv run python -m turbine_tslm.training.train configs/t1_flamingo_llama1b_evidence_rich.yaml  # headline
uv run python -m turbine_tslm.training.rft sample configs/t1_flamingo_llama1b_evidence_rich.yaml \
    --checkpoint $DATA_DIR/checkpoints/t1_flamingo_llama1b_evidence_rich/best.pt --out outputs/rft/kept.jsonl
uv run python -m turbine_tslm.training.train configs/t1_flamingo_llama1b_evidence_rich_rft.yaml
uv run python -m turbine_tslm.eval.score outputs/<run>/predictions.jsonl        # metrics
uv run python -m turbine_tslm.eval.faithfulness outputs/<run>/predictions.jsonl # text vs window
uv run python scripts/train_xgboost_baseline.py --model sensors_only           # baseline
uv run python scripts/build_demo_data.py docs/results/t1_flamingo_llama1b_evidence_rich/predictions.jsonl.gz && (cd webapp && python -m http.server)
```

## 12. Repository map

`src/turbine_tslm/data` (readers, channels, windows, taxonomy, prompts, evidence rules) · `connectors/cubico`
(TimeNet) · `training` (dataset, trainer, RFT) · `eval` (scorer, baselines, faithfulness) · `configs/` (one YAML per
run) · `docs/results/<run>/` (every scored run) · `docs/benchmark.md` (baselines) · `docs/session-handoff.md`
(chronological log) · `docs/notes/mentor-session-2026-09-12.md` · `webapp/` (demo) · `third_party/{OpenTSLM,TimeNet}`
(pinned submodules, unmodified).
