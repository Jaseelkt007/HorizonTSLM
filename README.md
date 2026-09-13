# Turbine Alarm Explainer

A Time-Series Language Model that reads the last 24 hours of a wind turbine's SCADA channels and says, hours before
the controller trips, whether a fault stop is coming, in which subsystem, and why — in text whose every number can be
checked against the data. Built in 24 h for the Temporal AI Challenge (Aionic Labs × ETH ASL × Nebius, 12–13 Sep
2026) on OpenTSLM + TimeNet, with a new dataset from two Cubico wind farms (CC-BY-4.0).

- **Method and results**: [`docs/method.md`](docs/method.md) — the complete write-up.
- **Spec**: [`docs/problem-statement.md`](docs/problem-statement.md) · [`docs/team-brief.html`](docs/team-brief.html) (challenge, OpenTSLM, TimeNet). **Chronological log**: [`docs/session-handoff.md`](docs/session-handoff.md). **Pitch outline**: [`docs/pitch.md`](docs/pitch.md).
- **Every scored run**: [`docs/results/<run>/`](docs/results/) (report, metrics, faithfulness, predictions). **Baselines**: [`docs/benchmark.md`](docs/benchmark.md).
- **Demo**: [`webapp/`](webapp/). **Conventions for contributors**: [`CLAUDE.md`](CLAUDE.md).

## Headline (Kelmarsh, a farm and turbine model the model never saw)

| model | recall @ 10 % false alarms | hard F1 | subsystem accuracy | numbers in the explanation verified |
|---|---|---|---|---|
| always no | 0.00 | – | – | – |
| XGBoost on 24 h statistics | 0.21 | 0.20 | 0.09 | no explanation |
| TSLM, label only | 0.24 | 0.24 | 0.08 | no explanation |
| **TSLM, reason-first + rich channel text** | **0.27** [0.24, 0.30] | **0.42** | **0.25** | **86 %** |

## Setup

```bash
git clone --recurse-submodules https://github.com/Jaseelkt007/zurich_ehl_timeseries.git
# already cloned? -> git submodule update --init
uv sync --group dev --extra wandb   # Python >= 3.12; opentslm from the submodule, timenet[cli,torch], pytest, ruff
uv run timenet-build build timenet/hello-world && uv run python scripts/smoke_timenet.py
uv run pytest tests/
```

Data (never committed): Cubico Penmanshiel (train) and Kelmarsh (held-out site), 2017–2021, CC-BY-4.0, from Zenodo —
`DATA_DIR=./data scripts/download_data.sh` (~4.6 GB). The preprocessed window tables *are* committed
(`data/interim/*_windows.parquet`), so baselines and evaluation run without the raw data.

## Reproduce

```bash
DATA_DIR=./data scripts/download_data.sh
DATA_DIR=./data uv run python scripts/build_windows.py penmanshiel --out data/interim/penmanshiel_windows.parquet
DATA_DIR=./data uv run python scripts/build_timenet.py
uv run python -m turbine_tslm.training.train configs/t1_flamingo_llama1b_evidence_rich.yaml
uv run python -m turbine_tslm.eval.score outputs/t1_flamingo_llama1b_evidence_rich/predictions.jsonl
uv run python -m turbine_tslm.eval.faithfulness outputs/t1_flamingo_llama1b_evidence_rich/predictions.jsonl
```

Python ≥ 3.12, `uv`, one 96 GB GPU for training (about 45 min per run). The preprocessed window tables are committed,
so the baselines and the evaluation run on a laptop.

## Layout

`src/turbine_tslm/{data,connectors,training,eval}` · `configs/` · `scripts/` · `docs/` · `webapp/` ·
`third_party/{OpenTSLM,TimeNet}` (pinned submodules, unmodified).

## Working agreement

Feature branches, small commits, rebase on `main`. The shared Nebius GPU VM is used by one person at a time; anything
worth keeping is committed and pushed before you leave it. Details in `CLAUDE.md`.
