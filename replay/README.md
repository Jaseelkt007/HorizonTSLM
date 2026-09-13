# Pipeline console — one window, end to end, on one screen

Standalone page: `index.html` plus copies of `docs/results/replay/*.json` (one Kelmarsh turbine-day each, hourly
windows through the headline checkpoint). No build, no server logic, no GPU or API calls.

    cd replay && python -m http.server 8010      # open http://localhost:8010

Layout (everything on one screen at ≥ 1280 px; columns stack on phones):

- **header** — turbine-day, the 24 h window, the horizon (1 / 3 / 6 h), the pace, and **Run / Next → / Reset**;
  a stage rail underneath (Input → Question → Model → Answer → Check) fills in as the run proceeds.
- **left — Input**: the 19 SCADA channels as a vertical list (name, unit, sparkline, last value of the window);
  the ones the answer cites are marked once the model has answered.
- **middle — Model**: the five-step strip (SCADA inputs → patch encoder → Perceiver resampler → Llama-3.2-1B →
  generated text) and the flow diagram beneath it: channel sparklines fan into the patch grid (36 per channel), then
  the latent tokens (64 per channel), the transformer (frozen, gated cross-attention), the generated tokens and the
  text streaming word by word — the real generated assessment, then its `Answer:` line; a progress bar below.
- **right — chat column**: the **Question** on top (with the exact prompt behind a disclosure), then the **Model
  answer**: a verdict box ("Yes — structural / overspeed stop likely within 3 h" or "No fault stop expected"),
  P(fault stop) with the 0.80 alarm line, **Key evidence** — the model's own sentences, each marked ✓ (every number
  verified against the window) / ✗ (a number does not match) / – (no numeric claim), the answer line, and buttons for
  the full text + prompt and for the **Check** card: numbers verified, what the alarm log recorded (real log line,
  lead time from this window, whether the answer matches), and an action line that is a fixed playbook entry per
  subsystem, labelled as such (not model output).

Keys: Enter = Run, → = Next, Esc = Reset. Deep links: `#<case>&step=<0–12>&h=<1|3|6>`; `?autorun` opens the page
already running; `?pace=1.5|1|0.6`; `?theme=dark|light` forces a theme; `?embed` hides the brand and footer (used
when the page is embedded in `demo-app/` as the "TSLM Explainer" view — a copy lives in `demo-app/public/pipeline/`;
re-copy after editing here). Every figure comes from the case JSON (`scripts/replay_case.py`, checkpoint
`t1_flamingo_llama1b_evidence_rich`); schema in `docs/results/replay/README.md`. Light and dark themes.
