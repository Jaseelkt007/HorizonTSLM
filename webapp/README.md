# Demo — Turbine Alarm Explainer

Static page: browse held-out windows (Kelmarsh = unseen farm, Penmanshiel 2020–21 = unseen years), read the headline
model's explanation with every number checked against the window, see the 24 h of signals and what the alarm log says
happened afterwards; a Results tab shows every model on the same splits.

    uv run python scripts/build_demo_data.py docs/results/t1_flamingo_llama1b_evidence_rich/predictions.jsonl.gz --out webapp/demo_data.json
    cd webapp && python -m http.server 8000      # open http://localhost:8000

`demo_data.json` (160 curated windows, generated) and `results_summary.json` (copied from docs/results/*/results.json)
are the only data the page needs; no GPU, no VM. Regenerate `results_summary.json` with the snippet in
`docs/session-handoff.md` when new runs land.
