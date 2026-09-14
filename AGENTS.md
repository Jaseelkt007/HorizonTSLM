# AGENTS.md

This file provides guidance to OpenAI Codex when working with code in this repository.

Adapted from `CLAUDE.md`; keep shared project guidance in both files in sync.

## What this is

"Turbine Alarm Explainer" — a 24 h hackathon project (Temporal AI Challenge, Aionic Labs × ETH ASL, 12–13 Sep 2026).
We fine-tune a Time-Series Language Model on wind-turbine SCADA data so it can read a 24 h window of sensor
channels and explain an alarm in plain language, name the subsystem, and anticipate forced outages.

Read these before touching anything — they are the spec, not background:

- `docs/problem-statement.md` — target user, signals, the six tasks (T1–T6) with exact inputs/outputs, splits,
  output template, subsystem taxonomy, evaluation plan, limitations. **Section 11 lists decisions still open.**
- `docs/team-brief.html` — challenge rules, what the judges reward, how OpenTSLM works, TimeNet basics.
- OpenTSLM paper (arXiv 2510.02410, §3 Methods) — the architecture/training reference; not vendored here.
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

Layout under `$DATA_DIR` (default `./data`, on the VM `~/data`): `raw/{kelmarsh,penmanshiel}/`, `timenet/`
(local TimeNet registry), `checkpoints/`, `interim/`. See `data/README.md`.

## Commands

```bash
uv sync                                        # env incl. timenet[cli,torch]; add --group dev for pytest/ruff/jupyter
uv run python scripts/smoke_timenet.py        # sanity: loads timenet/hello-world (build it first, below)
uv run timenet-build build timenet/hello-world # build the TimeNet demo dataset into the local registry
uv run pytest tests/ -x                        # all tests
uv run pytest tests/test_taxonomy.py -k name   # one test
uv run ruff check src tests && uv run ruff format src tests
```

Python ≥ 3.12; `uv` is the only supported way to run things (`uv run …`), `uv.lock` is committed.

## Architecture

`src/turbine_tslm/` is one installable package. The subpackages below are the agreed layout; each owner creates
theirs (only `data/taxonomy.yaml` exists today). Each maps to a team role and a section of the problem statement.

| Package | Role | Spec |
|---|---|---|
| `data/` | raw loaders → windows → labels + generated target text; `taxonomy.yaml` is the alarm-message → class map | §2, §6, §7, §8 |
| `connectors/` | TimeNet connectors `cubico/penmanshiel` and `cubico/kelmarsh` (one code path, two dataset cards) | §2, §6 |
| `training/` | glue from `TimeNet().load_torch()` items to the TSLM, LoRA fine-tune, checkpoint export | §5 |
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
  downstream stage reads the same split; do not re-split in training code.
- **Output template** is fixed: five labelled lines then `Answer: <class>`; the label after `Answer:` is what gets
  scored.
- `configs/`: one YAML per experiment, `<task>_<model>_<variant>.yaml`; the submitted run is `configs/submission.yaml`.

## Working on the shared Nebius VM

`ssh <user>@<vm-host>` (address in the team chat, not in git) (RTX PRO 6000, 96 GB VRAM; no network disk — everything lives on its root disk).
Repo is at `~/zurich_ehl_timeseries`, data at `~/data`. Team rule: **one person runs on the VM at a time, and
everything worth keeping is committed and pushed** — the VM may be preempted. Edit locally, push, `git pull` on the
VM, run there. Checkpoint to `~/data/checkpoints` every N steps.

`hackathon-25-bypass.pdf` and `Serverless-hackathon-guide.pdf` are Nebius-internal and git-ignored; this repo is
public — keep them out.

## Open questions (resolve with organisers / team, then update this file)

- How `timenet-build` discovers a connector that lives outside the `timenet_connectors` package (ours are in
  `src/turbine_tslm/connectors/`). Fallback: run the engine directly from Python.
- Whether glue between TimeNet `load_torch()` and the OpenTSLM training loop exists, or we write it.
- Decisions in `docs/problem-statement.md` §11: channel set (16 vs 8), window length, T4 horizon, which LLM
  paraphrases the rule-generated explanations.
