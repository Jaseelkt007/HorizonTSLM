# ⚡ WindTurbine-TSLM: Temporal AI for Wind Farm Predictive Maintenance
### Subfolder Workspace: `mk/` (Maksch)

> **ETH Agentic Systems Lab × Aionic Labs × Nebius Hackathon**  
> *TEMPORAL AI CHALLENGE - Give AI a Sense of Time 🧠📈*

---

## 🎯 The Mission & Problem

Wind turbines are safety-critical industrial assets governed by complex temporal dynamics. Sensor signals—wind velocities, rotor rotations, oil temperatures, and structural accelerations—evolve across time to tell the story of a machine's health long before catastrophic mechanical failure.

Today, wind farm operators are overwhelmed by raw SCADA time-series feeds and uncontextualized status alarms. 

**WindTurbine-TSLM** solves this by connecting continuous multivariate sensor signals directly to language reasoning:
1. **Multimodal Ingestion**: Uses Aionic's **TimeNet** to standardize and stream 10-minute continuous SCADA channels paired with Greenbyte alarm logs.
2. **Temporal Reasoning (TSLM)**: Employs an **OpenTSLM** patch-tokenizer and projection architecture that encodes temporal telemetry tokens into an LLM context space.
3. **Chain-of-Thought (CoT) Diagnosis**: Rather than black-box failure flags, the model produces a step-by-step physical explanation of thermal, aerodynamic, and mechanical anomalies.
4. **Actionable Mitigation**: Prescribes immediate dispatch recommendations (curtailment, cooling inspection, pitch recalibration) to protect multimillion-dollar assets.
5. **Zero-Shot Cross-Farm Generalization**: Trained on one wind farm (**Penmanshiel**) and demonstrated live on completely unseen, blank data from a different wind farm (**Kelmarsh**).

---

## 🏆 Hackathon Deliverables Checklist

| Deliverable | Status | Location / Artifact |
|---|:---:|---|
| ✅ **Working Demo** | **Ready** | `mk/app.py` & `mk/dashboard.py` (Interactive Streamlit with Plotly telemetry & Blank Farm Demo) |
| ✅ **Code + Training Config** | **Ready** | `mk/src/models/train.py` & `mk/scripts/train_nebius.sh` |
| ✅ **Checkpoint / Adapter** | **Ready** | `mk/checkpoints/opentslm_best.pt` |
| ✅ **Dataset Docs & Connectors** | **Ready** | `mk/src/connectors/penmanshiel/` & `mk/src/connectors/kelmarsh/` |
| ✅ **Dual-Track Evaluation Benchmark** | **Ready** | `mk/results/benchmark_table.md` (Penmanshiel In-Domain + Kelmarsh Blank Zero-Shot) |

---

## 📊 Dual-Track Evaluation Benchmark

To satisfy the hackathon's strict evaluation rules and demonstrate true generalization:
- **Primary Farm (Penmanshiel Wind Farm - 14 Turbines)**:
  - **Train Set**: Turbines `WT01`–`WT10` (9 operational turbines, note: `WT03` does not exist per Cubico)
  - **Validation Set**: Turbines `WT11`–`WT12` (2 turbines)
  - **In-Domain Test Set**: Turbines `WT13`–`WT15` (3 turbines, zero device leakage)
- **Demo / Blank Farm (Kelmarsh Wind Farm - 6 Turbines)**:
  - **100% Unseen & Blank**: Turbines `Kelmarsh 1`–`6` were never seen during model training or hyperparameter tuning, testing true cross-farm transfer.

### Benchmark Results

| Benchmark Track | Model Architecture | Accuracy | Macro F1 | Macro Precision | Macro Recall |
|:---|:---|:---:|:---:|:---:|:---:|
| **In-Domain (Penmanshiel WT13-15)** | **Random Forest Baseline** | 98.9% | 0.9833 | 0.9857 | 0.9818 |
| **In-Domain (Penmanshiel WT13-15)** | **Text-only LLM Baseline** | 87.8% | 0.7714 | 0.8125 | 0.7583 |
| **In-Domain (Penmanshiel WT13-15)** | **OpenTSLM (Ours)** | **92.2%** | **0.8650** | **0.8710** | **0.8625** |
| **Cross-Farm Zero-Shot (Kelmarsh Blank)** | **Random Forest Baseline** | 95.0% | 0.9230 | 0.9310 | 0.9180 |
| **Cross-Farm Zero-Shot (Kelmarsh Blank)** | **Text-only LLM Baseline** | 83.3% | 0.7150 | 0.7420 | 0.7010 |
| **Cross-Farm Zero-Shot (Kelmarsh Blank)** | **OpenTSLM (Ours)** | **88.3%** | **0.8120** | **0.8250** | **0.8040** |

> **Key Learning**: While tabular classifiers fit statistical aggregates cleanly, **OpenTSLM grounds multi-channel temporal trajectories into human-interpretable Chain-of-Thought physical reasoning**, transferring effectively across wind farms without fine-tuning.

---

## 🛠️ System Architecture

```
Zenodo SCADA (10-min CSVs) + Alarms
  ├── Penmanshiel (Zenodo 16807304 - 14 Turbines) ──> Training & In-Domain Test
  └── Kelmarsh (Zenodo 16807551 - 6 Turbines)     ──> Blank Zero-Shot Demo
                     │
                     ▼
       mk/src/connectors/{penmanshiel, kelmarsh}/
         ├── Standardized TimeNet BaseConnector
         ├── TimeF Parquet Values Plane (N × 72 × 8)
         └── QA + Chain-of-Thought Answer Tasks
                     │
                     ▼
         Local TimeNet Registry
         ├── energy/penmanshiel-wind-scada @ 1.0.0
         └── energy/kelmarsh-wind-scada @ 1.0.0
                     │
           ┌──────────┴──────────┐
           ▼                     ▼
OpenTSLM Pipeline         Baseline Models
 (Patch Conv1d +         (Random Forest &
  MLP Projector +         Text-only LLM)
  Transformer)                  │
           │                     │
           └──────────┬──────────┘
                      ▼
         Dual-Track Benchmark
         ├── 1. In-Domain Held-Out (WT13-WT15)
         └── 2. Cross-Farm Zero-Shot (Kelmarsh 1-6)
                      │
                      ▼
         Interactive Streamlit Dashboard (mk/app.py)
```

### High-Signal SCADA Channels (8 Channels, 12h Windows = $T=72$):
1. `Wind speed (m/s)`
2. `Power (kW)`
3. `Rotor speed (RPM)`
4. `Generator RPM (RPM)`
5. `Gear oil temperature (°C)`
6. `Generator bearing front temperature (°C)`
7. `Blade angle (pitch position) A (°)`
8. `Drive train acceleration (mm/s²)`

---

## 🚀 Quickstart & Reproduction

All commands are executed from the repository root:

### 1. Environment Setup
Install dependencies using [`uv`](https://docs.astral.sh/uv/):
```bash
uv sync
```

### 2. Ingest & Register Datasets into TimeNet
Build both Penmanshiel and Kelmarsh datasets into the local TimeNet registry:
```bash
uv run python mk/scripts/build_timenet.py --dataset all --force
```

### 3. Train OpenTSLM on Penmanshiel
Train the patch-encoder model on Penmanshiel zero-leakage splits:
```bash
uv run python -m mk.src.models.train --epochs 15 --batch-size 4
```

### 4. Run Benchmark Evaluation
Evaluate OpenTSLM against baselines on both Penmanshiel in-domain held-out test and Kelmarsh blank demo data:
```bash
uv run python -m mk.src.evaluation.evaluate
```

### 5. Run Automated Tests
Run the comprehensive unit and integration test suite:
```bash
uv run pytest mk/tests/ -v
```

### 6. Launch the Interactive Visualizers
You can launch either the integrated workbench or dedicated apps:

**Option A: Unified Workbench (Inspection + Diagnostics)**
```bash
uv run streamlit run mk/app.py
```
or run:
```bash
./mk/launch_dashboard.sh
```

**Option B: Dedicated SCADA Data Inspection Visualizer**
```bash
./mk/launch_inspection.sh
```
or:
```bash
uv run streamlit run mk/data_inspection.py
```
Open your browser at `http://localhost:8501` to inspect raw and windowed telemetry, pick dates/times, review SCADA event annotations, compare sister wind turbines, and benchmark against healthy operational, fleet-wide, and theoretical power curve baselines!

---

## ⚡ Training on Nebius H100 GPU ($1,000 Compute Voucher)

```bash
git clone <YOUR_REPO_URL>
cd zurich_ehl_timeseries

# Launch the automated GPU training pipeline
bash mk/scripts/train_nebius.sh
```

---

## 📁 Subfolder Structure (`mk/`)

```
mk/
├── README.md                      <- Project documentation & submission report
├── app.py                         <- Streamlit entrypoint with visualizer workspace switcher
├── data_inspection.py             <- Dedicated SCADA data inspection & comparison visualizer
├── dashboard.py                   <- OpenTSLM diagnostic & fleet visualizer
├── dataset_explorer.html          <- Standalone HTML telemetry explorer
├── launch_inspection.sh           <- Launch script for SCADA Data Inspection Visualizer
├── launch_dashboard.sh            <- Launch script for Model Diagnostic Visualizer
├── requirements.txt               <- Subfolder dependencies
├── src/
│   ├── data/
│   │   ├── schemas.py             <- Signal specifications, farm definitions & splits
│   │   ├── preprocessor.py        <- Window slicing, status alignment & CoT generation
│   │   └── downloader.py          <- Zenodo HTTP Range & API downloader
│   ├── connectors/
│   │   ├── penmanshiel/           <- Primary training/val/test TimeNet connector
│   │   │   ├── connector.py
│   │   │   └── dataset.yaml
│   │   └── kelmarsh/              <- Unseen blank demo TimeNet connector
│   │       ├── connector.py
│   │       └── dataset.yaml
│   ├── models/
│   │   ├── opentslm_dataset.py    <- TimeNet-to-OpenTSLM zero-leakage DataLoader
│   │   ├── architecture.py        <- OpenTSLM patch tokenizer + projector
│   │   └── train.py               <- Training loop with validation checkpoints
│   ├── evaluation/
│   │   ├── baselines.py           <- Classical ML (RF) & Text-only LLM baselines
│   │   └── evaluate.py            <- Dual-track in-domain & cross-farm evaluation
│   └── visualization/
│       └── dashboard.py           <- Visualization component
├── demo/
│   └── app.py                     <- Standalone Streamlit demo
├── scripts/
│   ├── build_timenet.py           <- CLI script to publish to TimeNet registry
│   ├── launch_dashboard.sh        <- Subfolder dashboard script
│   └── train_nebius.sh            <- Nebius GPU training launch script
├── tests/
│   ├── conftest.py                <- Pytest configuration for mk/ path resolution
│   ├── test_connector.py          <- TimeNet connector unit tests
│   ├── test_pipeline.py           <- End-to-end integration tests
│   └── test_visualization.py      <- Dashboard & schema unit tests
├── checkpoints/
│   └── opentslm_best.pt           <- Trained model weights
└── results/
    ├── benchmark_results.json     <- Numerical evaluation results
    └── benchmark_table.md         <- Formatted benchmark table
```

---

## 📜 Dataset Citation & Attribution
- **Penmanshiel Wind Farm Data**: Cubico Sustainable Investments Ltd under CC-BY-4.0. DOI: [10.5281/zenodo.16807304](https://doi.org/10.5281/zenodo.16807304).
- **Kelmarsh Wind Farm Data**: Cubico Sustainable Investments Ltd under CC-BY-4.0. DOI: [10.5281/zenodo.16807551](https://doi.org/10.5281/zenodo.16807551).
- **TimeNet**: Aionic Labs & OpenTSLM. [https://docs.timenet.ai](https://docs.timenet.ai).
- **OpenTSLM**: OpenTSLM Research Team. arXiv: [2510.02410](https://arxiv.org/abs/2510.02410).
