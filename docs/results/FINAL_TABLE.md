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
| XGBoost, sensor statistics (teammate, laptop rerun) | – | 0.780 · 0.51 · 0.64 · 0.51 | 0.596 · 0.21 · 0.20 · 0.09 | – | no text | no text | – |
| XGBoost, sensors + context (teammate, laptop rerun) | – | 0.779 · 0.52 · 0.64 · 0.50 | 0.614 · 0.22 · 0.19 · 0.09 | – | no text | no text | – |
| OpenTSLM Flamingo, label only | 0.747 · 0.53 · 0.49 · 0.30 | 0.698 · 0.25 · 0.35 · 0.19 | 0.613 · 0.24 · 0.24 · 0.08 | – | no text | no text | – |
| OpenTSLM SP + LoRA, label only | 0.787 · 0.55 · 0.65 · 0.43 | 0.707 · 0.40 · 0.55 · 0.48 | 0.623 · 0.24 · 0.34 · 0.16 | – | no text | no text | – |
| OpenTSLM Flamingo, reason-first, basic channel text (generate-mode score) | 0.634 · 0.34 · 0.49 · 0.34 | 0.650 · 0.21 · 0.53 · 0.42 | 0.565 · 0.23 · 0.37 · 0.17 | 0.55 / 0.44 | 0.52 | 76 % | 1.7 / 3.3 / 45 % |
| OpenTSLM Flamingo, reason-first + rich channel text, graded score | 0.770 · 0.49 · 0.56 · 0.44 | 0.721 · 0.38 · 0.54 · 0.48 | 0.595 · 0.26 · 0.42 · 0.25 | 0.65 / 0.31 | 0.86 | 28 % | 2.4 / 3.4 / 48 % |
| **OpenTSLM Flamingo, reason-first + rich text + RFT, graded score (headline)** | 0.759 · 0.53 · 0.59 · 0.41 | 0.768 · 0.42 · 0.62 · 0.47 | 0.638 · 0.30 · 0.37 · 0.17 | 0.61 / 0.48 | 0.87 | 26 % | 2.9 / 3.9 / 57 % |

Notes.
- XGBoost rows: `scripts/train_xgboost_baseline.py` (teammate) re-run on the laptop with its fixed seed
  (`random_state=42`, `n_jobs=1`) and scored with the same harness. The teammate's own run reports Kelmarsh AUROC /
  R@10 of 0.609 / 0.231 (sensors-only) and 0.615 / 0.226 (+ context) in `docs/benchmark.md`; the rerun gives
  0.596 / 0.206 and 0.614 / 0.223 — differences of ≤ 0.025, inside the bootstrap interval (±0.023). The scorer is
  identical (the script calls it); the model differs slightly between machines. The teammate's exact prediction
  files were not committed; if they are, replace `docs/results/xgboost_*/` with them. "Sensors + context" receives
  the same anchor state / month / horizon the TSLM gets in its prompt and is the primary head-to-head comparator;
  "sensor statistics" is the same-signals-only row. XGBoost has no val row (it tunes on val).
- "Graded score" = conclusion candidates scored conditioned on the model's own evidence sentences
  (`predict_mode: rescore`); the generate-mode score of a reason-first model is near-binary, and the plain
  teacher-forced loglik after the prompt is off-distribution (AUROC ≈ 0.5). Both reason-first rich rows use the graded
  score (`…_rescore/` folders); generate-mode values for the same checkpoints: headline 0.589 / 0.268, RFT 0.601 / 0.275.
- Paired bootstrap (2,000 resamples, `bootstrap/`). Kelmarsh recall at 10 % FAR: RFT 0.295 [0.260, 0.328] vs
  XGBoost + context 0.223 (difference −0.067 [−0.107, −0.026]), vs XGBoost sensors-only 0.206 (−0.089 [−0.127,
  −0.049]), vs label-only SP 0.244 (−0.048 [−0.090, −0.007]), vs rich reason-first 0.258 (+0.037 [+0.012, +0.062]
  for RFT). Kelmarsh AUROC: RFT 0.638 [0.614, 0.662] vs XGBoost 0.614 [0.591, 0.637]. Unseen years: XGBoost better
  on recall (+0.099 [+0.044, +0.162]); AUROC 0.779 vs 0.768 (overlapping).
- Per-class recall (Kelmarsh, headline / XGBoost sensors-only): overspeed 0.59 / 0.40, yaw 0.35 / 0.14, cooling
  0.13 / 0.17, pitch 0.09 / 0.09, grid 0.09 / 0.11, brake 0.00 / 0.07. Full per-class and per-horizon rows in each
  run's `report.md`.
- Warning escalation (T2) is not learnable from this data (7 escalating warnings in the training set); text-only
  Gemini baseline and the M4-init ablation were not completed.
