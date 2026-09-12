# Zero-Leakage Wind Turbine Benchmark Evaluation

### Model Training Setup
- **Primary Dataset**: Penmanshiel Wind Farm (`energy/penmanshiel-wind-scada`)
- **Turbine Splits**: Turbines `WT01`–`WT10` (Train), `WT11`–`WT12` (Val), `WT13`–`WT15` (Held-Out Test)
- **Cross-Farm Blank Demo Testbed**: Kelmarsh Wind Farm (`energy/kelmarsh-wind-scada`, Turbines 1–6) — **100% unseen, completely blank during training**.

### Benchmark Results

| benchmark                                               | model_name                   |   accuracy |   macro_f1 |   macro_precision |   macro_recall |
|:--------------------------------------------------------|:-----------------------------|-----------:|-----------:|------------------:|---------------:|
| In-Domain Held-Out Test (Penmanshiel WT13-WT15)         | Random Forest (Tabular)      |   1        |   1        |          1        |       1        |
| In-Domain Held-Out Test (Penmanshiel WT13-WT15)         | Text-only LLM (Stats Prompt) |   0.922222 |   0.862357 |          0.980282 |       0.844444 |
| In-Domain Held-Out Test (Penmanshiel WT13-WT15)         | OpenTSLM (Ours)              |   0.811111 |   0.376552 |          0.358025 |       0.4      |
| Cross-Farm Zero-Shot Transfer (Kelmarsh 1-6 Blank Demo) | Random Forest (Tabular)      |   1        |   1        |          1        |       1        |
| Cross-Farm Zero-Shot Transfer (Kelmarsh 1-6 Blank Demo) | Text-only LLM (Stats Prompt) |   0.95     |   0.854535 |          0.986466 |       0.836364 |
| Cross-Farm Zero-Shot Transfer (Kelmarsh 1-6 Blank Demo) | OpenTSLM (Ours)              |   0.75     |   0.369283 |          0.346746 |       0.4      |

*Zero-Leakage Guarantee: No turbine overlap exists between training, validation, and testing sets.*
