# Baseline comparison

Run the three XGBoost ablations with the fixed train/validation/test splits:

```bash
uv sync --group dev
uv run python scripts/train_xgboost_baseline.py --model context_only
uv run python scripts/train_xgboost_baseline.py --model sensors_only
uv run python scripts/train_xgboost_baseline.py --model combined
```

Each run tunes its XGBoost settings on `val` only, refits on `train + val`, and writes test-A and test-B JSONL files to `outputs/predictions/`.  Its matching metrics JSON includes overall and 1/3/6-hour AUROC, recall at 10% false-alarm rate, positive-class macro-F1, and a confusion matrix.

`brake_hydraulics` is retained in the confusion matrix but excluded from macro-F1 because it has only four examples in the project label set.

Score any model's JSONL using the shared harness:

```bash
uv run python -m turbine_tslm.eval.score --windows data/interim/penmanshiel_windows.parquet --split test_a --predictions outputs/predictions/MODEL_test_a.jsonl --output outputs/MODEL_test_a_metrics.json
uv run python -m turbine_tslm.eval.score --windows data/interim/kelmarsh_windows.parquet --split test_b --predictions outputs/predictions/MODEL_test_b.jsonl --output outputs/MODEL_test_b_metrics.json
```

| Comparison | Inputs | What it establishes |
| --- | --- | --- |
| `context_only` | anchor state, calendar month, requested horizon | Available operational-context proxy only |
| `sensors_only` | 24-hour SCADA summary statistics | Value of sensors for a conventional model |
| `combined` | SCADA statistics plus context | Incremental value after context |
| text-only LLM | The same statistics expressed in text | Whether a general LLM can use summaries without native sequence input |
| OpenTSLM | Raw 144 x 19 sequence plus the permitted prompt context | Whether native sensor-sequence processing improves the honest unseen-farm test |

Run the text-only baseline with the API key in `.env`; it uses no raw sequence values, alarm text, or future fields:

```bash
uv run python scripts/run_gemini_text_baseline.py --split test_a --limit 3  # smoke test
uv run python scripts/run_gemini_text_baseline.py --split test_a
uv run python scripts/run_gemini_text_baseline.py --split test_b
```

The runner uses the account-supported `gemini-3.6-flash`, is resumable, and begins with two concurrent calls to respect account rate limits. It writes the same JSONL schema, so score each completed split with the command above.

The parquet tables do **not** include alarm/status events before the anchor. Therefore `context_only` must not be presented as a true logs-only result. To make the requested logs-only/combined claim, add a leakage-safe pre-anchor status-log feature builder (event counts, recency, duration by subsystem) and rerun it as `logs_only` and `sensors_plus_logs`. Never use `next_event_*`, `lead_time_min`, `fault_within_*`, `label`, or `is_positive` as inputs.

Report test-A and test-B separately; compare models primarily on test-B and include confidence intervals or paired bootstrap intervals before making a positive claim about incremental value.

## First reproducible XGBoost run

These are the overall metrics from the fixed-seed `v1` run above.  They are deliberately kept here rather than committed as generated prediction artefacts; rerunning the command reproduces the JSONL and detailed metric files locally.

| Model | Test-A AUROC | Test-A recall @ 10% FAR | Test-A macro-F1+ | Test-B AUROC | Test-B recall @ 10% FAR | Test-B macro-F1+ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| context-only proxy | 0.547 | 0.156 | 0.066 | 0.563 | 0.138 | 0.087 |
| XGBoost sensors-only | 0.774 | 0.504 | 0.162 | 0.609 | 0.231 | 0.095 |
| XGBoost combined | 0.767 | 0.516 | 0.167 | 0.615 | 0.226 | 0.084 |

The sensor summaries substantially improve binary early-warning discrimination over available context on both sites.  The tiny and mixed effect of adding current context means it should not be described as an improvement.  Macro-F1 is low because several rare subsystem classes have too few training examples; inspect the saved confusion matrices rather than over-interpret a single aggregate.

## Final comparison status

Use this table in the project tracker; only rows with completed predictions may appear as numerical results on a slide.

| Input / model | Test-B AUROC | Test-B recall @ 10% FAR | Status |
| --- | ---: | ---: | --- |
| Operational-context proxy (XGBoost) | 0.563 | 0.138 | Complete; **not** a logs-only baseline |
| Sensors-only summary statistics (XGBoost) | 0.609 | 0.231 | Complete |
| Sensors + current context (XGBoost) | 0.615 | 0.226 | Complete; **not** sensors + logs |
| Historical logs-only (XGBoost) | — | — | Waiting for `hist_*` parquet columns |
| Sensors + historical logs (XGBoost) | — | — | Waiting for `hist_*` parquet columns |
| Gemini text-only summary baseline | — | — | Resumable test jobs running; score after both JSONLs are complete |
| OpenTSLM Flamingo, label only (`t1_flamingo_llama1b`) | 0.613 | 0.241 | Complete — `docs/results/t1_flamingo_llama1b/` |
| OpenTSLM SP + LoRA, label only (`t1_sp_llama1b`) | 0.623 | 0.244 | Complete — `docs/results/t1_sp_llama1b/` |
| OpenTSLM Flamingo, reason-first, basic channel text (`t1_flamingo_llama1b_evidence_fixed`) | 0.565* | 0.230 | Complete — `docs/results/t1_flamingo_llama1b_evidence_fixed/` (re-predicted with the left-padding fix) |
| OpenTSLM Flamingo, reason-first + rich text (`t1_flamingo_llama1b_evidence_rich`, headline) | 0.589* | 0.268 | Complete — `docs/results/t1_flamingo_llama1b_evidence_rich/`; *generate-mode score is near-binary, loglik re-score pending |
| OpenTSLM Flamingo, headline + 1 epoch RFT (`t1_flamingo_llama1b_evidence_rich_rft`) | 0.601* | 0.275 | Complete — `docs/results/t1_flamingo_llama1b_evidence_rich_rft/`; rejection-sampling fine-tune, reward = label correct + all numbers verified |

Notes for the comparison (OpenTSLM rows): all scored with `turbine_tslm.eval.score` on the committed window tables,
same records as the XGBoost rows (the XGBoost `v1` predictions re-scored with the same harness are in
`docs/results/xgboost_{sensors_only,combined}/`: test-B AUROC 0.596 / 0.614, R@10 0.206 / 0.223). Paired bootstrap
intervals on test-B (2,000 resamples, `scripts/bootstrap_ci.py`, `docs/results/bootstrap/test_b.json`): headline
R@10 0.268 [0.238, 0.297] vs XGBoost sensors-only 0.206 [0.173, 0.238], paired difference −0.062 [−0.097, −0.027];
RFT vs headline +0.007 [−0.019, +0.035] (not significant). Hard-label metrics (written "yes"/"no" + subsystem),
per-horizon and per-class rows, and the text faithfulness numbers are in each run's `report.md` / `results.json` /
`faithfulness.json`; see `docs/results/README.md` for the columns.
