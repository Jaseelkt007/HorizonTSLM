# Turbine Alarm Explainer demo

The first menu entry, **TSLM Explainer**, is the end-to-end pipeline console from `replay/` (copied to
`public/pipeline/`, embedded with `?embed&theme=dark`): pick a held-out Kelmarsh window, watch the 24 h of SCADA go
through OpenTSLM-Flamingo, read the answer with every number checked against the window and the alarm log.

Run the operator dashboard with `npm run dev` from this directory. Opening the
dashboard and switching turbines never loads an ML model. OpenTSLM is started
only when the Diagnostic Assistant's Send button is pressed.

The inference route starts `uv run python -m turbine_tslm.demo.infer` from the
repository root. It needs the local TimeNet registry containing the source
window and an OpenTSLM-compatible checkpoint. Set these when the defaults are
not suitable:

```bash
export DATA_DIR=/path/to/data
export DEMO_MODEL_CHECKPOINT=/path/to/best.pt
export DEMO_MODEL_CONFIG=configs/t1_flamingo_llama1b_evidence_rich.yaml
npm run dev
```

`DEMO_MODEL_CHECKPOINT` is optional: if omitted, inference uses
`$DATA_DIR/checkpoints/<run-name>/best.pt` when it exists, otherwise the base
checkpoint specified in the model config. This lets the UI be developed and
tested on a laptop without downloading or loading a model until a question is
sent.
