# Demo — Turbine Alarm Explainer

Static product demo: one HTML page and two JSON files, no GPU, no API calls.

    cd webapp && python -m http.server 8000      # open http://localhost:8000

Published (private): https://claude.ai/code/artifact/c460f528-0736-4b79-a9b8-aa0a02d43fab

## Views

- **Farm** — one row per turbine of the chosen farm (Kelmarsh = unseen farm, Penmanshiel 2020–21 = unseen years):
  the model's P(fault stop) on its latest sampled window, the subsystem it named, what the alarm log says followed,
  and a strip of every sampled window in time order (bar = score, dot = a fault stop really followed).
- **Window** — the 24 h the model saw as small multiples grouped by subsystem (last hour shaded, channels the
  explanation cites outlined and drawn in the accent), the explanation with every number marked verified / wrong
  against the window, the parseable `Answer:` line, P(fault) and subsystem probabilities, and "what actually
  happened" as a timeline (window → horizon → stop at its lead time). The question switch shows the same window
  asked the post-hoc question (T3), available for the 1 h positives.
- **Results** — every run under `docs/results/` and the XGBoost baselines on the same splits (pooled or per horizon),
  recall per subsystem with class counts, faithfulness per split, and the headline model's Kelmarsh confusion matrix.

Deep links: `#farm`, `#results`, `#w=<window id>`, `#w=<window id>&q=t3`. `?theme=dark` forces the dark theme
(otherwise the OS setting or the toggle in the header).

## Data

    uv run python scripts/build_demo_data.py docs/results/t1_flamingo_llama1b_evidence_rich/predictions.jsonl.gz --out webapp/demo_data.json

writes both files the page reads:

- `demo_data.json` — 160 curated held-out windows: raw 24 h × 19 channels, the headline model's explanation with
  per-claim verified/wrong spans, score, class probabilities, the post-hoc (T3) text with its own spans, and the gold
  outcome (message, lead time, duration).
- `results_summary.json` — every `docs/results/<run>/results.json` (+ `faithfulness.json`) and the XGBoost table
  parsed from `docs/benchmark.md`. Nothing on the Results tab is hand-typed; rerun the script when new runs land.
