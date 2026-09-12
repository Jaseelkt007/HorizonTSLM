# configs/

One YAML per experiment. Naming: `<task>_<model>_<variant>.yaml`, e.g. `t2_flamingo-gemma1b_w24h.yaml`.
Every config records: dataset id + version, window length, channel set, split, model, LoRA params, seed.
The config used for the submitted checkpoint is copied to `configs/submission.yaml`.
