# data/

Only `interim/*_windows.parquet` is committed (the preprocessed window tables, 28 + 19 MB, so baselines can
train locally without the 4.6 GB raw zips). Everything else is git-ignored. Layout, identical on laptops and on the Nebius VM (`~/data`):

    data/raw/kelmarsh/      Kelmarsh_SCADA_<year>_*.zip          (scripts/download_data.sh)
    data/raw/penmanshiel/   Penmanshiel_SCADA_<year>_WT*.zip
    data/timenet/           local TimeNet registry (timenet-build output)
    data/checkpoints/       adapters / checkpoints
    data/interim/           anything preprocessing wants to cache

Set `DATA_DIR` to point elsewhere. On the VM: `export DATA_DIR=~/data`.

## interim/<farm>_windows.parquet — what's in it

One row per 24 h window (built by `scripts/build_windows.py`, spec in `docs/problem-statement.md` §6):

| column | meaning |
|---|---|
| `window_id` | `<farm>-<turbine>-<anchor YYYYmmddTHHMM>-h<horizon>`; identical to the TimeNet record id |
| `farm`, `turbine`, `turbine_id`, `year` | where / when |
| `anchor` | window end `t` (UTC); the window is the 144 × 10-min steps up to and including `t` |
| `horizon_h` | 1, 3 or 6 — the question asked: "fault stop within the next H hours?" |
| `label` | subsystem class of the fault stop starting in `(t, t+H]`, or `none` |
| `is_positive` | `label != none` |
| `fault_within_1h/3h/6h` | same lookup for every horizon, regardless of `horizon_h` |
| `lead_time_min`, `next_event_message`, `next_event_iec`, `next_event_duration_h` | the event behind a positive (NaN for negatives) — **never model inputs** |
| `state_at_anchor` | `producing` or `idle_low_wind` (already-stopped windows are excluded) |
| `split` | `train` / `val` / `test_a` (Penmanshiel) or `test_b` (Kelmarsh) — use it, don't re-split |
| 19 channel columns | raw values, list of 144 floats each; order and units in `src/turbine_tslm/data/channels.py` |

```python
import pandas as pd, numpy as np
df = pd.read_parquet("data/interim/penmanshiel_windows.parquet")
X = np.stack([np.stack(df[c].to_list()) for c in CHANNEL_NAMES], axis=-1)   # (n_windows, 144, 19)
```
