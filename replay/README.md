# Replay — one Kelmarsh turbine-day, hour by hour through the whole pipeline

Standalone showcase: `index.html` plus copies of `docs/results/replay/*.json` (one case per file). No build, no
server logic, no GPU or API calls.

    cd replay && python -m http.server 8010      # open http://localhost:8010

Cases (tabs at the top): `tower_oscillation_2019` (caught hours ahead, every number verified), `quiet_day_2019`
(should stay "no"), `generator_cooling_miss_2019` (an honest miss). Deep links: `#<case>&step=<0–12>&h=<1|3|6>`.

What you see per hourly step (scrub, ◀ ▶, or Play; ← → and space work too):

- **left** — the 24 h window sliding forward: 19 small multiples on real clock time, last hour shaded, the channels
  the current explanation cites outlined;
- **right** — the three risk gauges (6 h / 3 h / 1 h ahead; red at P ≥ 0.80, amber from 0.50), the explanation
  typed out with verified numbers green and wrong ones red, the answer line and subsystem, the class probabilities;
  at the last step the outcome card opens with the real log line, the lead time from the first alarm, and the
  post-hoc explanation;
- **below** — the pipeline for that hour (raw SCADA → window → prompt with the real channel descriptions →
  OpenTSLM-Flamingo, drawn after the paper's architecture: patch encoder → Perceiver Resampler → gated
  cross-attention into a frozen Llama-3.2-1B → text → checker with every claim ticked), and the status log as the
  controller wrote it, rows appearing as the replay passes them (context only, never an input).

Every figure comes from the case JSON (`scripts/replay_case.py`, headline checkpoint
`t1_flamingo_llama1b_evidence_rich`); the channel-description statistics in the prompt stage are recomputed from
the window exactly as the training code does (mean, std, first 6 h, 6 h before the end, last hour). Schema:
`docs/results/replay/README.md`. Light and dark themes; phone-width safe.
