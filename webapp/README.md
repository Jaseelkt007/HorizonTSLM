# Demo — Turbine Alarm Explainer

Next.js (App Router, TypeScript, static export). Everything is prerendered from two JSON files at build time: no
server, no GPU, no API calls at runtime.

    npm install
    npm run dev        # http://localhost:3000
    npm run build      # static site in out/
    npm run preview    # serve out/ on http://localhost:8000
    npm run lint && npm run typecheck

Node ≥ 20. `out/` can be dropped on any static host (Vercel, GitHub Pages, S3, `python -m http.server`).

## Routes

- `/` — **Farm board**: one row per turbine of the chosen farm (Kelmarsh = unseen farm, Penmanshiel 2020–21 = unseen
  years): the model's P(fault stop) on its latest sampled window, the subsystem it named, what the alarm log says
  followed, and a strip of every sampled window in time order (bar = score, dot = a fault stop really followed).
- `/window/<id>/` — one held-out window (160 static pages; `/window/` opens the showcase): the question, the
  explanation with every number marked verified / wrong against the window, the parseable `Answer:` line, P(fault) and
  subsystem probabilities, "what actually happened" as a timeline (window → horizon → stop at its lead time), and the 19
  channels as small multiples grouped by subsystem (last hour shaded, cited channels outlined). `?q=t3` opens the same
  window asked the post-hoc question (available for the 1 h positives); `?turbine=<farm>|<n>` pre-filters the list.
- `/results/` — every run under `docs/results/` and the XGBoost baselines on the same splits (pooled or per horizon),
  recall per subsystem with class counts, faithfulness per split, and the headline model's Kelmarsh confusion matrix.

Theme follows the OS; the header toggle overrides it (saved in `localStorage`).

## Layout

    data/            demo_data.json, results_summary.json  (generated — see below)
    src/app/         layout + routes: page.tsx (farm), window/[id]/page.tsx, results/page.tsx
    src/components/  FarmBoard, HistoryStrip, WindowRail, WindowDetail, Explanation, Timeline, ChannelWall,
                     ChannelChart, ResultsView, TopBar/NavTabs/ThemeToggle, Footer  (+ CSS Modules)
    src/lib/         types.ts (JSON shapes), data.ts (build-time loading, server only), labels.ts (naming,
                     channel groups, cite heuristics), format.ts (formatting, answer parsing)
    src/app/globals.css   design tokens (light/dark) and the few shared primitives (.chip, .seg, .panel, .meter)

Server components read the JSON with `fs` (`src/lib/data.ts`); client components get typed props only. Fonts
(Barlow, Barlow Semi Condensed, Source Serif 4, JetBrains Mono) are self-hosted through `next/font`.

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
