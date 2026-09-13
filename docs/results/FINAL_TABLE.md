# Final benchmark — every model on the same held-out windows

Cells: AUROC · recall at 10 % false-alarm rate · hard F1 of the written decision · subsystem accuracy on true fault
windows. Splits: val = unseen turbines on the training farm (model selection only); test_a = training farm, 2020–21
(unseen years); test_b = Kelmarsh (unseen farm and turbine model). All rows scored by `turbine_tslm.eval.score` on the
committed window tables; text columns by `eval.faithfulness` (numbers recomputed from the window) and
`scripts/llm_judge.py` (gpt-5, the same 40 windows for each text model; grounded / coherent on 1–5, supports = share
of texts whose reasoning justifies the answer line). Generated from `docs/results/*/` by the snippet in
`docs/results/README.md`; intervals in `docs/results/bootstrap/`.

| model | val: AUROC · R@10 % · F1 · subsys | test_a (unseen years) | test_b (Kelmarsh, unseen farm) | T3 subsys acc (a / b) | claim precision | texts w/ wrong number | judge grounded / coherent / supports |
|---|---|---|---|---|---|---|---|
| always no | 0.500 · 0.00 · – · – | 0.500 · 0.00 · – · – | 0.500 · 0.00 · – · – | – | – | – | – |
| XGBoost, sensor statistics (teammate) | – | 0.780 · 0.51 · 0.64 · 0.51 | 0.596 · 0.21 · 0.20 · 0.09 | – | no text | no text | – |
| XGBoost, sensors + context (teammate) | – | 0.779 · 0.52 · 0.64 · 0.50 | 0.614 · 0.22 · 0.19 · 0.09 | – | no text | no text | – |
| OpenTSLM Flamingo, label only | 0.747 · 0.53 · 0.49 · 0.30 | 0.698 · 0.25 · 0.35 · 0.19 | 0.613 · 0.24 · 0.24 · 0.08 | – | no text | no text | – |
| OpenTSLM SP + LoRA, label only | 0.787 · 0.55 · 0.65 · 0.43 | 0.707 · 0.40 · 0.55 · 0.48 | 0.623 · 0.24 · 0.34 · 0.16 | – | no text | no text | – |
| OpenTSLM Flamingo, reason-first, basic channel text | 0.634 · 0.34 · 0.49 · 0.34 | 0.650 · 0.21 · 0.53 · 0.42 | 0.565 · 0.23 · 0.37 · 0.17 | 0.55 / 0.44 | 0.52 | 76 % | 1.7 / 3.3 / 45 % |
| OpenTSLM Flamingo, reason-first + rich channel text (headline), graded score | 0.770 · 0.49 · 0.56 · 0.44 | 0.721 · 0.38 · 0.54 · 0.48 | 0.595 · 0.26 · 0.42 · 0.25 | 0.65 / 0.31 | 0.86 | 28 % | 2.4 / 3.4 / 48 % |
| OpenTSLM Flamingo, headline + RFT (generate-mode score) | 0.706 · 0.51 · 0.59 · 0.41 | 0.708 · 0.39 · 0.62 · 0.47 | 0.601 · 0.27 · 0.37 · 0.17 | 0.61 / 0.48 | 0.87 | 26 % | 2.9 / 3.9 / 57 % |

Notes.
- XGBoost rows are the teammate's `v1` predictions (`scripts/train_xgboost_baseline.py`) re-scored with the shared
  harness; the original numbers are in `docs/benchmark.md`. XGBoost has no val row (it tunes on val).
- "Graded score" = conclusion candidates scored conditioned on the model's own evidence sentences
  (`predict_mode: rescore`); the generate-mode score of a reason-first model is near-binary, and the plain
  teacher-forced loglik after the prompt is off-distribution (AUROC ≈ 0.5). RFT graded rescore: pending at the time
  of writing (`docs/results/t1_flamingo_llama1b_evidence_rich_rft_rescore/` when done).
- Paired bootstrap on Kelmarsh (2,000 resamples): headline recall 0.258 [0.226, 0.288] vs XGBoost sensors-only
  0.206 [0.173, 0.238], difference −0.052 [−0.087, −0.015]; vs XGBoost + context −0.030 [−0.069, +0.007]; label-only
  TSLMs within noise. Unseen years: XGBoost better by +0.113 [+0.060, +0.165]; headline better than label-only
  Flamingo by 0.141 [0.074, 0.208].
- Per-class recall (Kelmarsh, headline / XGBoost sensors-only): overspeed 0.59 / 0.40, yaw 0.35 / 0.14, cooling
  0.13 / 0.17, pitch 0.09 / 0.09, grid 0.09 / 0.11, brake 0.00 / 0.07. Full per-class and per-horizon rows in each
  run's `report.md`.
- Warning escalation (T2) is not learnable from this data (7 escalating warnings in the training set); text-only
  Gemini baseline and the M4-init ablation were not completed.
