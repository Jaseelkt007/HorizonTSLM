# Pipeline showcase — one window, end to end

Standalone page: `index.html` plus copies of `docs/results/replay/*.json` (one Kelmarsh turbine-day each, hourly
windows through the headline checkpoint). No build, no server logic, no GPU or API calls.

    cd replay && python -m http.server 8010      # open http://localhost:8010

Choose the turbine-day, the window (hour) and the horizon, press **Run the pipeline**, and the page walks through the
five stages at a presentation pace (slow / normal / quick; "Next step", → or the floating button skip ahead):

1. **Input** — "The previous 24 hours of SCADA sensor measurements": wind speed, power, gearbox temperature and oil
   pressure, generator temperatures, pitch angle, rotor speed, grid voltage/frequency, tower acceleration, other
   channels — each with its sparkline and last value from the window.
2. **Question** — "Will a fault stop begin within the next H hours? If yes, which subsystem?" with the exact prompt
   (pre-prompt and the 19 channel descriptions, whose statistics are recomputed from the window as the training code
   does) behind a disclosure.
3. **Model** — the data flowing through OpenTSLM-Flamingo (after the paper's architecture figure): the 19 channels
   into the patch encoder (1-D conv, patch 4 → 36 × 128), the Perceiver Resampler (64 latents), gated cross-attention
   before every block of the frozen Llama-3.2-1B, prompt tokens entering below, generated tokens leaving into the
   output box word by word.
4. **Answer** — the model's real output typed out in the FINDING / EVIDENCE / ANSWER frame: FINDING is its
   conclusion sentence, EVIDENCE its evidence sentences with every number marked verified (green) or wrong (red),
   ANSWER its `Answer:` line; P(fault stop) gauge and subsystem probabilities beside it.
5. **Check** — the numbers recomputed from the window, what the log recorded (the real line, lead time from this
   window, whether the answer matches), and an **action** line that is a fixed playbook entry per subsystem — labelled
   as such, it is not model output.

Deep links: `#<case>&step=<0–12>&h=<1|3|6>`; add `?autorun` to open the page already playing, `?pace=1.6|1|0.5`.
Every figure comes from the case JSON (`scripts/replay_case.py`, checkpoint `t1_flamingo_llama1b_evidence_rich`).
Schema: `docs/results/replay/README.md`. Light and dark themes; phone-width safe.
