# Replay cases — one Kelmarsh turbine-day each, hour by hour through the whole pipeline

Produced by `scripts/replay_case.py` with the headline checkpoint (`t1_flamingo_llama1b_evidence_rich`). Kelmarsh is
fully held out and hourly anchors are never training records. Cases:

| file | what it shows |
|---|---|
| `tower_oscillation_2019.json` | Kelmarsh T1, stop "Tower oscillation X level 2" at 2019-03-15 12:13 — P(fault) climbs from 0.27 (−12 h) to 0.87 (−8 h) to 0.95+ (−3 h); caught early, numbers verified |
| `quiet_day_2019.json` | Kelmarsh T1, 2019-01-05 07:00 → 19:00, no fault — scores stay 0.1–0.6, text stays "no sign…" |
| `generator_cooling_miss_2019.json` | Kelmarsh T1, stop "Overload generator fan 1" at 2019-11-13 11:44 — an honest miss: 0.2–0.6 throughout |

## Schema (one JSON per case)

```
name, farm, turbine, end (ISO), model
stop:     null | {start, message, class, duration_h, iec}          the real log line at the end
log:      [{start, end, status, message, iec, class}, ...]          status-log rows around the day (context only)
channels: [{name, label, unit}, ...]                                 19 channels, order used everywhere
steps:    [ {anchor (ISO), hours_to_end, state ("producing"|"idle_low_wind"|"stopped"),
             channels: {name: [144 floats]},                         the raw 24 h window ending at anchor
             facts: {…},                                             numbers the rules computed from the window
             answers: {
               t1_h1 | t1_h3 | t1_h6: {text, label, p_fault, class_scores{class: p}, claims:[{start,end,ok}]},
               t3 (last steps only):  {text, label, claims}
             }} , ... ]                                              −12 h … 0 h, hourly
```

- `text` is the model's full generation ("…explanation… \nAnswer: yes, structural_overspeed"); `claims` are
  character spans inside `text` for every numeric claim, `ok` = matches the window (green) or not (red).
- `p_fault` is the graded probability that a fault stop begins within the horizon (conclusion candidates scored
  conditioned on the model's own evidence sentences); `label` is the parsed answer line.
- `hours_to_end` counts down to the stop (or the quiet end). Lead time at a step = `hours_to_end` + (stop − end).
