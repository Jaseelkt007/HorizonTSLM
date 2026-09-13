# docs/results — every scored run, same records, same harness

One folder per run. Everything in a folder is produced by the code in this repository from the committed window
tables (`data/interim/*_windows.parquet`); nothing is hand-typed.

| file | what it is |
|---|---|
| `report.md` | the markdown table printed by `python -m turbine_tslm.eval.score` (per split × horizon + pooled, per class) |
| `results.json` | the same metrics as JSON (`results[split][horizon]`), incl. confusion matrices and per-class blocks |
| `faithfulness.json` | text models only: `eval.faithfulness` summary + per-text claim verdicts |
| `predictions.jsonl.gz` | one record per evaluated window: `window_id, task, split, gold, label, score, class_scores[, text]` |
| `config.yaml`, `train_log.jsonl` | the run's config and per-step / per-epoch losses (val_loss = selection; test_*_loss = diagnostic only) |

## Columns in `report.md`

- **n / pos**: windows scored / of which a fault stop followed within the horizon.
- **AUROC, AP**: ranking quality of `score` = P(fault stop within H). For the generate-mode text models the score is
  conditioned on the model's own written conclusion and is near-binary — read their recall / F1 columns and the
  `*_loglik` re-scores rather than their AUROC.
- **R@10%FAR / R@5%FAR**: recall of true fault windows when the threshold lets 10 % (5 %) of quiet windows through.
  The headline metric.
- **hard P / R / F1**: precision / recall / F1 of the *written* decision (`label != none`), no threshold.
- **subsystem macro-F1 / acc**: among true fault windows, is the named subsystem right (macro-F1 over classes present;
  plain accuracy).
- **Per class block**: `recall@10%FAR · subsystem accuracy · n` per true class, horizons pooled.
- `t3/<split>` rows: the post-hoc question (every record is a real stop; only the subsystem is scored).

## Runs

| folder | model | one-line description |
|---|---|---|
| `t1_flamingo_llama1b` | OpenTSLM Flamingo, Llama-3.2-1B | label-only MVP |
| `t1_sp_llama1b` | OpenTSLM SP + LoRA, Llama-3.2-1B | label-only; best on the training farm, forgets Kelmarsh fastest |
| `t1_flamingo_llama1b_evidence` | Flamingo, reason-first targets, basic channel text | first evidence run (generation partly garbled by the right-padding bug; kept for the record) |
| `t1_flamingo_llama1b_evidence_fixed` | same checkpoint, re-predicted with left-padded generation | clean "before rich text" row |
| `t1_flamingo_llama1b_evidence_rich` | + first-6h / 6h-ago / last-hour statistics in every channel text | **headline / demo model** |
| `t1_flamingo_llama1b_evidence_rich_rft` | headline + 1 epoch on label-correct, fully verified self-samples | the "RL on top" step; same faithfulness, better ranking, more conservative alarms |
| `xgboost_sensors_only`, `xgboost_combined` | teammate's XGBoost `v1` predictions | re-scored here with the shared harness (see `docs/benchmark.md` for the original numbers and the script) |
| `bootstrap/` | paired bootstrap CIs on test_b for all of the above | `scripts/bootstrap_ci.py` |

Floors for every split: always-no → AUROC 0.500, recall 0 (`python -m turbine_tslm.eval.baselines always_no`).
