# Demo — Turbine Alarm Explainer

Next.js (App Router, TypeScript, static export). Everything is prerendered from two JSON files at build time: no
server, no GPU, no API calls at runtime.

    npm install
    npm run dev        # http://localhost:3000
    npm run build      # static site in out/
    npm run preview    # serve out/ on http://localhost:8000
    npm run lint && npm run typecheck

Node ≥ 20. `out/` can be dropped on any static host (Vercel, GitHub Pages, S3, `python -m http.server`).

## Pages

An app shell (sidebar navigation, light theme by default, dark follows the OS or the toggle):

- `/` — **Overview**: what the data is and how the model is used, told with real numbers from the JSON: a showcase
  window's signals, the four steps (input → question → answer → checked), the two farms with their sampled turbines,
  the 19 channels grouped by subsystem, and how the alarm log becomes the labels.
- `/farms/kelmarsh/`, `/farms/penmanshiel/` — **Farm board**: one card per turbine — the model's P(fault stop) on its
  latest sampled window, the subsystem it named, what the alarm log says followed, and every sampled window in time
  order (bar = score, dot = a fault stop really followed).
- `/windows/` — **Windows**: the 160 held-out windows as a filterable table (farm, turbine, outcome, subsystem,
  right/wrong; sort by date, verification or risk). `?turbine=<farm>|<n>` pre-filters.
- `/window/<id>/` — **Signals & answer** (160 static pages; `/window/` opens the showcase): a stacked, synchronized
  chart of up to three channels on one real-clock time axis — the last hour shaded, the asked horizon to the right of
  "now", and the stop that followed drawn where it began — with a channel list (click any of the 19 to chart it; the
  ones the explanation cites are flagged); then the model's answer with every number marked verified / wrong, the
  `Answer:` line, P(fault), subsystem probabilities and what actually happened. `?q=t3` shows the same window asked
  the post-hoc question (1 h positives only); earlier / later step through the turbine's sampled windows.
- `/results/` — **Results**: every run under `docs/results/` and the XGBoost baselines on the same splits (pooled or
  per horizon), recall per subsystem with class counts, faithfulness per split, and the Kelmarsh confusion matrix.

## Layout

    data/            demo_data.json, results_summary.json  (generated — see below)
    src/app/         layout.tsx (shell) · page.tsx (overview) · farms/[farm] · windows · window/[id] · results
    src/components/  Sidebar, SignalPanels (the chart engine), ChannelList, WindowView, WindowsTable, FarmView,
                     HistoryStrip, Explanation, ResultsView, ThemeToggle  (+ CSS Modules)
    src/lib/         types.ts (JSON shapes) · data.ts (build-time loading, server only) · labels.ts (naming,
                     channel groups, cite heuristics) · format.ts · time.ts (clock ticks, nice axes) · pins.ts
    src/app/globals.css   design tokens (light/dark) and the shared primitives (.card, .chip, .seg, .kpi, table.data)

Server components read the JSON with `fs` (`src/lib/data.ts`); client components get typed props only. Fonts (Inter,
JetBrains Mono) are self-hosted through `next/font`. `SignalPanels` is plain SVG rendered at the measured container
width — no chart library, so every chart is in the static HTML.

## Data

    uv run python scripts/build_demo_data.py docs/results/t1_flamingo_llama1b_evidence_rich/predictions.jsonl.gz

writes both files the site reads (run from the repository root):

- `data/demo_data.json` — 160 curated held-out windows: raw 24 h × 19 channels, the headline model's explanation with
  per-claim verified/wrong spans, score, class probabilities, the post-hoc (T3) text with its own spans, and the gold
  outcome (message, lead time, duration).
- `data/results_summary.json` — every `docs/results/<run>/results.json` (+ `faithfulness.json`) and the XGBoost table
  parsed from `docs/benchmark.md`. Nothing on the Results page is hand-typed; rerun the script and rebuild when new
  runs land.

The previous single-file version of this demo is published as a private artifact at
https://claude.ai/code/artifact/c460f528-0736-4b79-a9b8-aa0a02d43fab (frozen at that version).
