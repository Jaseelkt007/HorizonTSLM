# Turbine Alarm Explainer

A Time-Series Language Model over wind-turbine SCADA data — Temporal AI Challenge (Aionic Labs × ETH ASL),
European Hackathon League Zurich, 12–13 Sep 2026.

Given 24 h of a turbine's sensor channels, the model explains an alarm in plain language, names the subsystem,
states the lost production, and flags forced outages before they start.

**Start here:** [`docs/problem-statement.md`](docs/problem-statement.md) (what we build, exact inputs/outputs) ·
[`docs/team-brief.html`](docs/team-brief.html) (challenge, OpenTSLM, TimeNet) · [`CLAUDE.md`](CLAUDE.md) (conventions).

## Data

Cubico wind farms, CC-BY-4.0: **Penmanshiel** (14 turbines, train) and **Kelmarsh** (6 turbines, held-out site),
2017–2021, from Zenodo. Never committed.

```bash
DATA_DIR=./data scripts/download_data.sh   # ~4.6 GB
```

## Setup

```bash
uv sync --group dev          # Python >= 3.12; installs timenet[cli,torch], pytest, ruff, jupyter
uv run timenet-build build timenet/hello-world && uv run python scripts/smoke_timenet.py
```

## Layout

```
src/turbine_tslm/
  data/         raw loaders, windows, taxonomy.yaml, target-text generation   (preprocessing)
  connectors/   TimeNet connectors cubico/penmanshiel, cubico/kelmarsh        (preprocessing)
  training/     TimeNet -> TSLM glue, LoRA fine-tune, checkpoint export       (training)
  eval/         baselines and metrics                                          (evaluation)
  demo/         live demo                                                      (demo)
configs/        one YAML per experiment; configs/submission.yaml is the submitted run
scripts/        entry points (download_data.sh, smoke_timenet.py, ...)
docs/           briefs, problem statement, figures
data/           git-ignored; see data/README.md
```

## Working agreement

Feature branches, small commits, rebase on `main`. The shared Nebius GPU VM is used by one person at a time;
anything worth keeping is committed and pushed before you leave it. Details in `CLAUDE.md`.
