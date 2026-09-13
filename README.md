# Turbine Alarm Explainer

**Early warning for wind-turbine fault stops, with an explanation you can check.**
A Time-Series Language Model reads the last 24 hours of a turbine's SCADA channels and answers, hours before the
controller trips: *will a fault-related stop begin within the next 1, 3 or 6 hours, in which subsystem, and why?* The
answer is plain text ending in a scored label, and every number in it is recomputed from the data and marked verified
or not.

Built in 24 hours for the Temporal AI Challenge (Aionic Labs × ETH ASL × Nebius, 12–13 September 2026) on
[OpenTSLM](https://github.com/OpenTSLM/OpenTSLM) and TimeNet, with a new dataset from two Cubico wind farms
(Zenodo, CC-BY-4.0) and reusable TimeNet connectors for both.

---

## Results at a glance

Test B is **Kelmarsh**, a wind farm and turbine model (Senvion MM92) the model never saw; training used Penmanshiel
(MM82). Every model is scored on identical held-out records with one harness. "Recall @ 10 % FAR" is the operator's
number: the share of upcoming fault stops flagged when one quiet window in ten may raise a false alarm.

| model | AUROC | recall @ 10 % FAR | hard F1 (written decision) | subsystem accuracy |
|---|---|---|---|---|
| always "no" | 0.500 | 0.000 | – | – |
| XGBoost on 24 h statistics + context | 0.614 | 0.223 | 0.19 | 0.09 |
| OpenTSLM, label only (best of Flamingo / SP+LoRA) | 0.623 | 0.244 | 0.34 | 0.16 |
| **OpenTSLM, reason-first + rich prompt (headline)** | 0.595 | **0.258** | **0.42** | **0.25** |
| OpenTSLM, headline + rejection-sampling fine-tune | see note | 0.275 | 0.37 | 0.17 |

- The headline model catches **25 % more upcoming failures than XGBoost on sensor statistics** at the same
  false-alarm budget (0.258 vs 0.206; paired bootstrap 95 % interval excludes zero; vs XGBoost with context 0.223,
  borderline), names the subsystem three times as often, and is the only model that explains itself.
- AUROC is level with XGBoost on the unseen farm (intervals overlap). On unseen *years* of the training farm
  XGBoost is clearly stronger (recall 0.51 vs 0.39). We say so.
- Explanation quality, rule check of every number against the window / LLM-judge grounding on the same 40 windows:
  basic prompt 52 % / 1.7, rich prompt 86 % / 2.4, + RFT 87 % / 2.9 out of 5.
- Where the signal is: structural/overspeed stops are learnable from 10-minute data (Kelmarsh recall 0.59 at 10 %
  FAR, subsystem named correctly in 55 %); thermal classes only partly; grid, yaw and brake stops have no precursor
  at this resolution.

Full tables with intervals, per-horizon and per-class rows: [`docs/results/FINAL_TABLE.md`](docs/results/FINAL_TABLE.md).
The RFT row's graded AUROC is added there when its rescoring finishes; its generate-mode value (0.601) is not
comparable with the graded headline score.

## What is in this repository

| path | contents |
|---|---|
| [`docs/method.md`](docs/method.md) | the complete write-up: problem, data, splits, tasks, models, evidence targets and thresholds, training recipe, evaluation, results, lessons, limitations |
| [`docs/results/`](docs/results/) | every scored run (report, metrics, faithfulness, predictions), the final table, bootstrap intervals, LLM-judge output, replay cases; its [README](docs/results/README.md) explains every column |
| [`docs/benchmark.md`](docs/benchmark.md) | the baseline comparison (XGBoost ablations, text-only LLM) |
| [`docs/problem-statement.md`](docs/problem-statement.md), [`docs/team-brief.html`](docs/team-brief.html) | the specification and the challenge brief |
| [`docs/pitch.md`](docs/pitch.md), [`docs/session-handoff.md`](docs/session-handoff.md) | slide outline with sourced numbers; chronological engineering log |
| [`src/turbine_tslm/`](src/turbine_tslm/) | the package (below) |
| [`configs/`](configs/) | one YAML per experiment |
| [`scripts/`](scripts/) | data download and build, baselines, judge, bootstrap, replay, demo data |
| [`webapp/`](webapp/), `replay/` | the interactive demo and the hour-by-hour replay showcase |
| [`third_party/`](third_party/) | OpenTSLM and TimeNet as pinned, unmodified submodules |
| [`CLAUDE.md`](CLAUDE.md) | conventions for contributors |

### The package

```
src/turbine_tslm/
  data/         Greenbyte readers → 19 channels → 24 h windows, labels and splits; alarm taxonomy;
                prompt templates; rule-based evidence text (the training targets for the explanation)
  connectors/   TimeNet connectors cubico/penmanshiel and cubico/kelmarsh (records, annotations, tasks)
  training/     OpenTSLM QADataset over the TimeNet registry; trainer (Flamingo / SP, warm start, early
                stopping, left-padded generation, graded rescoring); rejection-sampling fine-tune
  eval/         the shared scorer (predictions.jsonl → AUROC, recall @ FAR, per class, confusion),
                trivial floors, faithfulness checker (numbers in generated text vs the window)
```

## How it works

1. **Windows.** For every fault-class stop in the alarm log, 24 h windows of 19 channels ending 1, 3 and 6 h before
   it; negatives sampled 2 : 1 from quiet periods. Nothing after the window end is ever an input; the alarm text is
   the label only.
2. **Model.** OpenTSLM-Flamingo on a frozen Llama-3.2-1B: each channel is patched, pooled by a perceiver and injected
   through gated cross-attention. Warm-started from OpenTSLM's published checkpoint; 838 M trainable parameters.
3. **Targets.** Not just the label. A rule engine turns each window into a short, faithful-by-construction
   explanation (thermal ramps at steady load, bearing asymmetry, oil-pressure drop, tower vibration, grid steps, …;
   thresholds at the 99th percentile of the data) ending in the scored `Answer:` line. The channel descriptions in
   the prompt carry the statistics those sentences quote, so the model can read them rather than guess.
4. **Checking.** Every number in a generated explanation is recomputed from the window; an LLM judge scores
   grounding and coherence on a fixed sample. A rejection-sampling fine-tune uses the checker as its reward.
5. **Evaluation.** Train on Penmanshiel 2017–19 (turbines 13–15 held out for model selection), test on Penmanshiel
   2020–21 (unseen years) and on Kelmarsh (unseen farm and turbine model). Paired bootstrap intervals on every claim.

## Setup

```bash
git clone --recurse-submodules https://github.com/Jaseelkt007/zurich_ehl_timeseries.git
cd zurich_ehl_timeseries
uv sync --group dev --extra wandb        # Python >= 3.12; opentslm from the submodule, timenet[cli,torch]
uv run pytest tests/
```

The preprocessed window tables are committed (`data/interim/*_windows.parquet`, 47 MB), so evaluation, baselines and
the demo run on a laptop. The raw exports (4.6 GB) are only needed to rebuild them:

```bash
DATA_DIR=./data scripts/download_data.sh
DATA_DIR=./data uv run python scripts/build_windows.py penmanshiel --out data/interim/penmanshiel_windows.parquet
DATA_DIR=./data uv run python scripts/build_timenet.py            # both farms into the TimeNet registry
```

## Reproduce

```bash
# headline model (one 96 GB GPU, ~45 min training + ~45 min evaluation)
uv run python -m turbine_tslm.training.train configs/t1_flamingo_llama1b_evidence_rich.yaml
# graded score for a reason-first model
uv run python -m turbine_tslm.training.train configs/t1_flamingo_llama1b_evidence_rich.yaml --predict-only \
    --set predict_mode=rescore --set rescore_from=outputs/t1_flamingo_llama1b_evidence_rich/predictions.jsonl
# rejection-sampling fine-tune (sample, then train one epoch on the kept samples)
uv run python -m turbine_tslm.training.rft sample configs/t1_flamingo_llama1b_evidence_rich.yaml \
    --checkpoint $DATA_DIR/checkpoints/t1_flamingo_llama1b_evidence_rich/best.pt --out outputs/rft/kept.jsonl
uv run python -m turbine_tslm.training.train configs/t1_flamingo_llama1b_evidence_rich_rft.yaml
# scoring, text check, judge, intervals (laptop)
uv run python -m turbine_tslm.eval.score outputs/<run>/predictions.jsonl
uv run python -m turbine_tslm.eval.faithfulness outputs/<run>/predictions.jsonl
OPENAI_API_KEY=... uv run python scripts/llm_judge.py outputs/<run>/predictions.jsonl --n 40
uv run python scripts/bootstrap_ci.py --split test_b headline=outputs/<run>/predictions.jsonl xgb=outputs/xgb_combined.jsonl
# baselines and demo
uv run python scripts/train_xgboost_baseline.py --model combined
uv run python scripts/build_demo_data.py docs/results/t1_flamingo_llama1b_evidence_rich/predictions.jsonl.gz
DATA_DIR=~/data uv run python scripts/replay_case.py configs/t1_flamingo_llama1b_evidence_rich.yaml \
    --checkpoint ~/data/checkpoints/t1_flamingo_llama1b_evidence_rich/best.pt --farm kelmarsh --turbine 1 \
    --end "2019-03-15 12:13" --name tower_oscillation_2019 --out docs/results/replay/tower_oscillation_2019.json
```

Every run logs to Weights & Biases when `wandb_project` is set in its config, and its results are copied to
`docs/results/<run>/`.

## Inference with a trained checkpoint

Checkpoints hold only the trainable parameters (`$DATA_DIR/checkpoints/<run>/best.pt`, ~1 GB); the base LLM is
re-downloaded from the Hugging Face Hub by `llm_id` (Llama-3.2-1B is gated: set `HF_TOKEN`). One GPU with ≥ 16 GB
is enough for inference.

**1. Score the held-out splits with an existing checkpoint** (no training):

```bash
uv run python -m turbine_tslm.training.train configs/t1_flamingo_llama1b_evidence_rich.yaml --predict-only \
    --set "eval_splits=[val, test_a, test_b]"        # generate mode: explanation + label + score per window
```

Output: `outputs/<run>/predictions.jsonl` (one record per window: `window_id, task, split, gold, text, label,
score, class_scores`), `report.md` and `results.json` from the shared scorer. Add `--set max_samples=64` for a smoke
test, `--set predict_mode=rescore --set rescore_from=<predictions.jsonl>` for the graded probability.

**2. Ask about any turbine and time (needs the raw exports):** `scripts/replay_case.py` rebuilds the 24 h window
ending at each hourly anchor from the raw SCADA files, runs the model for the 1 / 3 / 6 h questions and the
post-hoc question, checks every number in the text, and writes one JSON per case:

```bash
DATA_DIR=~/data uv run python scripts/replay_case.py configs/t1_flamingo_llama1b_evidence_rich.yaml \
    --checkpoint ~/data/checkpoints/t1_flamingo_llama1b_evidence_rich/best.pt \
    --farm kelmarsh --turbine 1 --end "2019-03-15 12:13" --hours-before 12 --name my_case --out outputs/replay/my_case.json
```

For a single window, use `--hours-before 0`. The schema is documented in `docs/results/replay/README.md`.

**3. From Python** (any 144 × 19 window as a `{channel: np.ndarray}` dict, channel names in
`turbine_tslm.data.channels.CHANNEL_NAMES`):

```python
from turbine_tslm.training import train as T
from turbine_tslm.training.turbine_dataset import channel_prompts
from turbine_tslm.data.prompts import POST_PROMPT, pre_prompt
from turbine_tslm.eval.faithfulness import check_text
from opentslm.time_series_datasets.util import extend_time_series_to_match_patch_size_and_aggregate as collate_fn

cfg = T.load_config("configs/t1_flamingo_llama1b_evidence_rich.yaml", ["wandb_project=null"])
model = T.build_model(cfg); T.load_checkpoint(model, "best.pt"); model.eval()
prompts = channel_prompts(series, series_stats="rich")
sample = {"pre_prompt": pre_prompt("kelmarsh", "kelmarsh-01", "March", "producing", 6),
          "time_series": [p.get_time_series() for p in prompts], "time_series_text": [p.get_text() for p in prompts],
          "post_prompt": POST_PROMPT, "answer": ""}
text = T.generate_texts(model, collate_fn([sample], patch_size=4), 160)[0]   # "...\nAnswer: yes, structural_overspeed"
print(text, check_text(text, series))                                       # numbers verified / wrong, conclusion consistent
```

The prompt wording, channel order and statistics must match training exactly; `channel_prompts` and `pre_prompt`
guarantee that. No alarm-log information ever enters the prompt.

## Limitations

- Ground truth is the controller's alarm log, not a technician's diagnosis; "subsystem" is the message class.
- Explanations are rule-derived and model-written: checkable, not expert-written. 28 % still contain at least one
  wrong number, and none contains a recommended action yet.
- One manufacturer, two farms, mid-2018 → 2019 training data, 572 fault events. Grid, communication, brake and
  warning-escalation events carry no usable precursor at 10-minute resolution.
- The generate-mode probability of a reason-first model is near-binary; ranking metrics for those models use the
  graded rescoring described in `docs/method.md` § 7.

## Working agreement

Feature branches, small commits, rebase on `main`. The shared GPU VM is used by one person at a time; anything worth
keeping is committed and pushed before leaving it. Details in `CLAUDE.md`.

## Acknowledgements

OpenTSLM (Stanford / ETH Zurich) and TimeNet, used unmodified as submodules. SCADA data: Cubico Sustainable
Investments, Penmanshiel and Kelmarsh wind farms, published on Zenodo under CC-BY-4.0. Compute: Nebius.
