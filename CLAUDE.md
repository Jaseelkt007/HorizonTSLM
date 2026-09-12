# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

"Turbine Alarm Explainer" — a 24 h hackathon project (Temporal AI Challenge, Aionic Labs × ETH ASL, 12–13 Sep 2026).
We fine-tune a Time-Series Language Model on wind-turbine SCADA data so it can read a 24 h window of sensor
channels and explain an alarm in plain language, name the subsystem, and anticipate forced outages.

Read these before touching anything — they are the spec, not background:

- `docs/problem-statement.md` — target user, signals, the six tasks (T1–T6) with exact inputs/outputs, splits,
  output template, subsystem taxonomy, evaluation plan, limitations. **Section 11 lists decisions still open.**
- `docs/team-brief.html` — challenge rules, what the judges reward, how OpenTSLM works, TimeNet basics.
- `brief.pdf`, `ts-corpus-list.md` — the organisers' brief and their dataset shortlist (we chose an off-list dataset).
- `docs/opentslm-paper/03_methods.tex` — the OpenTSLM architecture/training section, verbatim.
- `third_party/OpenTSLM`, `third_party/TimeNet` — upstream repos as pinned submodules (`git submodule update --init`).
  Read them, do not edit them in place; anything we change goes in `src/turbine_tslm/` (or a fork, bumped here).

## Data (never in git)

Cubico wind farms from Zenodo, CC-BY-4.0. **Penmanshiel** (14 × Senvion MM82, turbines 1,2,4–15) is the training
farm; **Kelmarsh** (6 × Senvion MM92) is held out entirely as the unseen-site test. Years 2017–2021 only (2016 is
incomplete). Per turbine-year: `Turbine_Data_*.csv` (10-min SCADA, 299 columns, ~70 populated, 9 comment lines
before the header, `# Date and time` is the time column) and `Status_*.csv` (alarm log; `Timestamp end` can be `-`).

```bash
DATA_DIR=./data scripts/download_data.sh      # ~4.6 GB, idempotent
```

Layout under `$DATA_DIR` (default `./data`, on the VM `~/data`): `raw/{kelmarsh,penmanshiel}/`,
`interim/<farm>_windows.parquet` (one row per window: labels + 19 list-columns of 144 floats), `checkpoints/`.
The TimeNet registry lives where TimeNet puts it (`~/.cache/timenet/registry/cubico/{penmanshiel,kelmarsh}/0.1.0`
on the VM; `TIMENET_REGISTRY` overrides). Regenerate:

```bash
DATA_DIR=~/data uv run python scripts/build_windows.py penmanshiel --out ~/data/interim/penmanshiel_windows.parquet
DATA_DIR=~/data uv run python scripts/build_timenet.py            # both farms -> registry, then verifies load()
```

Data facts that shape everything: pitch, gear-oil temperature, main-bearing temperature and tower acceleration do
not exist before ~May 2018 (windows with an empty channel are dropped, so training data is mid-2018 → 2019);
`Cable autounwind`, `Hydraulic oil flushing` and `Battery test` are routine operations (context class), never labels;
positives are fault-class events that stopped the turbine (Stop status, or a Warning filed as IEC Forced outage).

## Commands

```bash
uv sync                                        # env incl. timenet[cli,torch]; add --group dev for pytest/ruff/jupyter
uv run python scripts/smoke_timenet.py        # sanity: loads timenet/hello-world (build it first, below)
uv run timenet-build build timenet/hello-world # build the TimeNet demo dataset into the local registry
uv run pytest tests/ -x                        # all tests
uv run pytest tests/test_taxonomy.py -k name   # one test
uv run ruff check src tests && uv run ruff format src tests
uv run python -m turbine_tslm.training.turbine_dataset            # dataset sizes + one formatted sample
uv run python -m turbine_tslm.training.train configs/smoke_flamingo.yaml       # 64-sample GPU smoke run (VM)
uv run python -m turbine_tslm.training.train configs/t1_flamingo_llama1b.yaml  # MVP; --predict-only reuses best.pt
uv run python -m turbine_tslm.eval.score outputs/<run>/predictions.jsonl       # re-score any predictions file
```

`opentslm` is installed from the submodule as an editable path dependency (`[tool.uv.sources]`), with
open-flamingo pinned to 2.x via `override-dependencies` (the 0.0.2 wheel breaks `OpenTSLMFlamingo`). After
`git submodule update --init`, `uv sync` is all that is needed.

Python ≥ 3.12; `uv` is the only supported way to run things (`uv run …`), `uv.lock` is committed.
On WSL with the repo under `/mnt/<drive>`, put the venv on the Linux side first (copying torch onto the Windows mount
fails with I/O errors): `export UV_PROJECT_ENVIRONMENT=~/.venvs/turbine` before any `uv` command.

## Architecture

`src/turbine_tslm/` is one installable package; each subpackage maps to a team role and a section of the problem
statement. `data/` and `connectors/` are done and tested; `training/`, `eval/`, `demo/` are created by their owners.

| Package | Role | Spec |
|---|---|---|
| `data/` | `greenbyte.py` (zip → SCADA/status frames) → `channels.py` (19 channels, 2 derived) → `windows.py` (events → anchors → labels → 144×19 windows, split) ; `taxonomy.yaml`/`.py` message → class ; `prompts.py` pre/post-prompt + answer templates | §2, §6, §7, §8 |
| `connectors/cubico/` | `base.py` shared TimeNet connector (download = window table, convert = records + annotations + tasks); `penmanshiel/`, `kelmarsh/` cards | §2, §6 |
| `training/` | `turbine_dataset.py` OpenTSLM `QADataset` over the TimeNet registry (split annotation → train/validation/test, z-score + `series_text`) ; `train.py` YAML config → Flamingo/SP warm-started from an OpenTSLM Hub checkpoint → trainable-only checkpoints in `$DATA_DIR/checkpoints/<run>` → generate + yes/no log-likelihood score → `outputs/<run>/predictions.jsonl` + report | §5, §7 |
| `eval/` | baselines + metrics; the two headline numbers are T2 macro-F1 on Kelmarsh and T4 recall@10 % FAR | §9 |
| `demo/` | pick turbine + window → answer in the FINDING/EVIDENCE/CAUSE/IMPACT/ACTION template | §7 |

Data flow: raw zips → (data) windows/labels → (connectors) `TimeFDataset` → `timenet-build` → local registry →
(training) `load_torch()` → model → (eval, demo). Nothing in `training/` or `eval/` should parse CSVs; if it needs a
field, add it to the connector as an annotation.

Key conventions everyone depends on:

- **Taxonomy** (`data/taxonomy.yaml`): case-insensitive substring match on `Message`, first pattern wins, top to
  bottom. Classes with `kind: context` (e.g. `manual_safety`) are never a classification target. Append patterns;
  never rename a class — it is the label space of every task.
- **Window** = 24 h = 144 steps at 10 min, ending at the event start (T1–T3) or 6 h before it (T4); per-channel
  z-score inside the window with the raw mean/std/unit written into that channel's text description.
- **The alarm message, code and category are never model inputs** — they are the answer.
- **Split** is stored as a record annotation (`split ∈ {train, val, test_a, test_b}`) by the connector, so every
  downstream stage reads the same split; do not re-split in training code. Baselines read the same windows from
  `interim/<farm>_windows.parquet` (same ids, labels and split), so every model is scored on identical records.
- **Windows are raw values.** z-scoring and the per-series text (`prompts.series_text(name, mean, std)`) happen in the
  training dataset class, not in the data.
- **Output template** is fixed: five labelled lines then `Answer: <class>`; the label after `Answer:` is what gets
  scored.
- **Predictions** (`src/turbine_tslm/eval/score.py`): every model writes `predictions.jsonl`, one object per window:
  `{"window_id", "score" (P(fault within H), higher = more likely), "label" (class or "none") | "text" (generated
  answer, label parsed from its last `Answer:` line)}`. Score it with
  `uv run python -m turbine_tslm.eval.score preds.jsonl --out results.json` → AUROC, recall at 10 % / 5 % false
  alarms, hard P/R/F1, per-class recall, subsystem macro-F1 and confusion, per split × horizon. Floors:
  `uv run python -m turbine_tslm.eval.baselines always_no --out outputs/always_no.jsonl`. Nothing in `eval/` reads
  signals, only the label columns of the parquet.
- `configs/`: one YAML per experiment, `<task>_<model>_<variant>.yaml`; the submitted run is `configs/submission.yaml`.

## Working on the shared Nebius VM

`ssh <user>@<vm-host>` (RTX PRO 6000, 96 GB VRAM; no network disk — everything lives on its root disk).
Repo is at `~/zurich_ehl_timeseries`, data at `~/data`. Team rule: **one person runs on the VM at a time, and
everything worth keeping is committed and pushed** — the VM may be preempted. Edit locally, push, `git pull` on the
VM, run there. Checkpoint to `~/data/checkpoints` every N steps.

`hackathon-25-bypass.pdf` and `Serverless-hackathon-guide.pdf` are Nebius-internal and git-ignored; this repo is
public — keep them out.

## Open questions (resolve with organisers / team, then update this file)

- ~~Whether glue between TimeNet and the OpenTSLM training loop exists~~ — written: `training/turbine_dataset.py`.
- Decisions in `docs/problem-statement.md` §11: channel set (16 vs 8), window length, T4 horizon, which LLM
  paraphrases the rule-generated explanations.
