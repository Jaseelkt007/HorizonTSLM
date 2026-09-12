# Problem statement — Turbine Alarm Explainer

*Temporal AI Challenge · v2 (early-warning framing) · 12 Sep 2026*

A Time-Series Language Model (TSLM) that reads the last 24 hours of a wind turbine's sensor data and
tells the operations engineer, **hours before the controller trips: is a fault stop coming, in which
subsystem, and why** — in plain language they can act on.

---

## 0. The idea in plain words

A wind farm records ~300 sensor channels per turbine every 10 minutes (wind, power, temperatures,
pressures, pitch, vibration …). Separately, the turbine controller writes a **log of events** with
a text message, e.g. `Overload generator fan 2`, `Low gearbox oil pressure`, `Grid loss`.

The log arrives **when the turbine has already stopped**. Many fault stops, however, are preceded
by hours of visible drift in the signals — a bearing heating faster than load explains, gear-oil
pressure sagging, tower vibration creeping up. Today nobody watches 300 channels × 14 turbines for
that.

**We train a model that does:** give it the last 24 h of sensor data, and it says whether a
fault-related stop will begin in the next hours, which subsystem, and what evidence it sees.
The training labels come from the log — but from events **after** the window, so the model learns
to anticipate, not to describe.

```
INPUT (ending at 08:00)                              OUTPUT
24 h × 17 channels, 10-min data       ──►   "Wind rising 4→8 m/s, power ramping to 1.1 MW.
+ "Turbine Penmanshiel 7, MM82,               Generator rear bearing +7 °C in 4 h, front bearing
   producing. Will a fault stop                flat — rear-side cooling not keeping up.
   begin within 6 h?"                          Recommend: limit power, check generator fan 1.
                                               Answer: yes, generator_cooling"

                        (the log says "Overload generator fan 1" at 11:50 — 3 h 50 min later)
```

Why this is not just a paraphrase of the log: the log is written at second precision when the
fault has already happened. The value is **lead time** — de-rate the turbine instead of a forced
stop, send the technician in the morning instead of an emergency call-out. A plain classifier
(gradient boosting on window statistics) can give the yes/no; the TSLM's contribution is giving
the yes/no **and** the evidence from the same raw signal, with no per-site feature engineering.

---

## 1. Target user

**The wind-farm operations engineer** (asset owner or service provider) monitoring 10–100
turbines from a control room. A 14-turbine farm produces roughly **4,000 status events a
year**; most are benign (low wind, battery tests, comms blips), some are the first sign of a
forced outage that costs days of production and a site visit.

Their three daily questions:

1. **What happened here, and which subsystem is it?** (triage)
2. **Does it matter — what did it cost, does it need a visit?** (prioritise)
3. **Is this turbine drifting toward a stop?** (anticipate)

Secondary users: the site technician who gets the work order; the asset manager who reviews
lost-production reports.

---

## 2. The data we have

Two wind farms owned by Cubico, exported from Greenbyte SCADA, CC-BY-4.0:

| Farm | Turbines | Years | Zenodo |
|---|---|---|---|
| Kelmarsh (UK) | 6 × Senvion MM92, 2.05 MW | 2016 – 2021 | https://zenodo.org/records/5841834 |
| Penmanshiel (UK) | 14 × Senvion MM82, 2.05 MW | 2016 – mid-2021 | https://zenodo.org/records/5946808 |

Per turbine-year there are two files.

### Stream A — SCADA telemetry (`Turbine_Data_*.csv`) — the time series

52,416 rows (one per 10 min), 299 columns. Only ~70 columns are actually populated; the rest
are empty channels for this turbine type. We use a curated set of **~16 base signals**:

| Group | Signals | Why |
|---|---|---|
| Environment | Wind speed, Wind direction, Nacelle ambient temperature | Should the turbine be producing? ambient baseline |
| Operation | Power, Rotor speed, Generator RPM, Blade pitch A/B/C, Nacelle position | Producing / idle / stopped / feathered |
| Drivetrain thermal | Generator bearing front & rear, Stator, Gear oil, Front/rear main bearing, Transformer temps | Cooling, lubrication, bearing faults — the precursor channels |
| Hydraulics | Gear oil inlet pressure, Gear oil pump pressure | Lubrication faults |
| Electrical | Grid voltage, Grid current, Grid frequency, Reactive power | Grid / converter events |
| Structural | Tower acceleration X/Y, Drive-train acceleration | Oscillation, overspeed |
| Bookkeeping (labels only) | Lost Production Total (kWh), Potential power (kW) | Ground truth for *impact* |

### Stream B — Status / alarm log (`Status_*.csv`) — the language

One row per event:
`Timestamp start, Timestamp end, Duration, Status, Code, Message, Comment, Service contract category, IEC category`

- `Status`: Stop / Warning / Informational / Communication
- `Message`: ~120 distinct texts per farm-year — *Overload generator fan 2, Brake accumulator
  defect, Low gearbox oil pressure, Frequency converter error, Grid loss, Tower oscillation X
  level 2, Pitch measuring system 1><2, Brake pads worn, Cable autounwind, Comm. failure FPM,
  Wind < start wind, Manual stop – on site …*
- `IEC category`: Full Performance / Forced outage / Scheduled Maintenance / Technical Standby /
  Out of Environmental Specification … → tells us whether it was a real failure.

### Static metadata

Turbine type (MM92 vs MM82), rated power, rotor diameter, hub height. Goes into the text context.

### Data facts that shape the design (checked in the raw files)

- 2016 is incomplete (Kelmarsh temperatures / RPM / pitch only exist from May 2016) → we use **2017 → 2021** for both farms.
- 649 of 2,122 status rows in one turbine-year have an open end (`-`) → treat as point events.
- `Battery test` and `Manual stop` dominate the log → excluded from fault classes, kept as context.
- After filtering (2017–21): **10,410 fault-type Stop/Warning events at Penmanshiel (2,503 IEC
  "Forced outage") and 3,387 at Kelmarsh (694 forced outages)**; 122 and 87 distinct messages.

---

## 3. Problems we solve, with the farm's own numbers

Penmanshiel, 14 turbines, 2017–2021, from the status log + lost-production columns:

| Subsystem class | Events | Forced outages | Median dur. | Lost energy (5 yr) | Precursor in 10-min SCADA? |
|---|---|---|---|---|---|
| pitch_system | 1,255 | 169 | 0.5 h | 2,848 MWh | partly (battery / charging degrade over days) |
| converter_grid | 575 | 505 | 0.0 h | 1,195 MWh | mostly no (grid-side) |
| generator_cooling | 530 | 444 | 1.0 h | 541 MWh | **yes** — thermal ramp over hours |
| structural_overspeed | 457 | 399 | 0.2 h | 284 MWh | partly (tower acceleration trend) |
| gearbox_lubrication | 166 | 145 | 0.1 h | 183 MWh | **yes** — oil temp / pressure drift |
| brake_hydraulics | 1,519 | 7 | 0.2 h | 616 MWh | partly |
| sensor_comms, yaw_cable | 2,655 | 0 | ~0 | 647 MWh | no (not real faults) |
| environmental / curtailment / manual | 8,245 | — | — | ~10,000 MWh | not a fault — excluded |

≈ **1,260 MWh per year lost to fault-class stops on this one farm** (≈ £60–100k/yr at UK wind
prices, before call-out costs); ~39 forced outages per turbine per year. Losses are a long tail:
the median fault stop is 12 min, the top 5 % last over 6 h — those are the ones where lead time
turns a forced stop into a planned intervention.

What the system does for the operations engineer:

- **Early warning.** "Fault stop likely on turbine 7 within 6 h" while the turbine is still
  producing — the log cannot give this.
- **Say which subsystem and why**, from the signals, so the warning is actionable
  (de-rate, inspect fan, schedule oil check) rather than a bare probability.
- **Know when to stay quiet.** Most windows are normal; a warning system that cries wolf is
  switched off. False-alarm rate is a first-class metric.
- **Work on the next site.** Trained on Penmanshiel (MM82), tested on Kelmarsh (MM92) with no
  re-engineering.

Honest scope: the model will give lead time on the thermal / lubrication / structural / pitch
classes and essentially none on grid loss, comms or manual stops. We report per class.

---

## 4. Workflow (Aionic's four stages)

1. **Sense & encode** — 24 h window of ~16 channels for one turbine (144 steps), static
   description, question. Each channel encoded separately and described in text with its
   mean / std / unit (OpenTSLM multi-series "stacking").
2. **Reason & explain** — the TSLM writes a structured finding: which signals changed, turbine
   state, most plausible subsystem — before committing to a label.
3. **Act & execute** — one recommended action with the reason. The engineer approves or
   dismisses; nothing is executed automatically.
4. **System implications** — the finding carries the price: kWh lost, wind available or not,
   recurrence of the same message on this turbine.

### Worked example (real event, post-hoc view)

Kelmarsh turbine 1, 9 June 2016. Log row: `Overload generator fan 1` (Warning, code 2550,
IEC "Forced outage", 12:34–14:14, 1 h 40 min). Hourly means of the six hours before:

| Hour | Wind m/s | Power kW | Rotor rpm | Gen. bearing rear °C | Stator °C | Ambient °C | Pitch A ° |
|---|---|---|---|---|---|---|---|
| 06:00 | 2.5 | −1.1 | 0.7 | 39.1 | 55.9 | 11.4 | 45.0 |
| 08:00 | 2.1 | 1.0 | 1.3 | 38.0 | 50.2 | 14.4 | 40.8 |
| 09:00 | 2.9 | 15.6 | 6.2 | 37.6 | 51.8 | 15.8 | 11.9 |
| 11:00 | 2.8 | −1.0 | 0.2 | 40.5 | 52.2 | 19.0 | 79.0 |
| 12:00 | 2.6 | −2.0 | 0.0 | 40.6 | 50.4 | 20.2 | 91.3 |

Target output for the **post-hoc explanation task (T3)**, i.e. when asked after the fact:

```
FINDING   Generator cooling warning while the turbine was idle.
EVIDENCE  Wind 2–3 m/s, below cut-in, for the whole 6 h; power ≈ 0 and rotor stopped except a
          brief 15 kW run-up at 09:00. Generator rear bearing temperature rose 37.6 → 40.6 °C
          over 3 h with no load while stator stayed at 50–56 °C — heat is not being removed.
          Blades feathered to 91° at 12:00: the controller took the turbine to stop shortly
          before the alarm.
CAUSE     Generator fan 1 overload (cooling circuit), consistent with rising bearing
          temperature at zero load.
IMPACT    0 kWh lost so far — no wind available. Risk moves to the next windy period if the
          fan is not cleared.
ACTION    Reset and inspect generator fan 1 / its contactor before wind returns; check whether
          fans 2 and 3 showed the same message recently.
Answer: generator_cooling
```

Every sentence is derivable from the window plus the log row. **That is the standard for all
training targets: no claims the data cannot support.** For the early-warning task the same event
is used with the window ending 1, 3 and 6 h *earlier*, and the answer is
`Answer: yes, generator_cooling`.

---

## 5. Task definitions — inputs and outputs

Every record is a 24 h window **anchored at a time `t`**. Labels describe what the log says
*after* `t`; nothing after `t` enters the input.

| # | Task | Anchor `t` | Prompt (abridged) | Answer | Label source | Priority |
|---|---|---|---|---|---|---|
| **T1** | **Early warning — will a fault stop begin?** (headline) | `t = alarm − H`, H ∈ {1, 3, 6} h; plus negatives | "Turbine producing now. Will a fault-related stop begin within the next H hours? If yes, name the subsystem." | `Answer: no` · `Answer: yes, <subsystem>` — optionally preceded by evidence text | First fault-class Forced outage in `(t, t+H]` from the log; `no` if none | **Must** |
| T2 | Warning escalation | `t` = start of a Warning row | "A warning has just been raised. Will it escalate to a forced outage within 24 h?" | `Answer: yes / no` | Next Stop in `(t, t+24h]` | Should |
| T3 | Post-hoc explanation (morning report) | `t = alarm − 30 min` (excludes the controller's reaction) | "A status event began 30 min after this window. Describe what happened and name the subsystem." | FINDING / EVIDENCE / CAUSE / IMPACT / ACTION + `Answer: <subsystem>` | Message → taxonomy; kWh, duration from log + SCADA | Should (demo narrative + clean accuracy) |
| T4 | Impact estimate | as T3 | "How much production will this stop cost?" | kWh | Lost Production Total over the event | Stretch |
| T5 | Outage localisation | 48 h window containing one stop | "When did the turbine stop although wind was available?" | (start, end) | Event span | Stretch (TimeRLM comparison) |

**T1 is what we sell and what we score first.** Its binary form (`yes`/`no`) is the MVP and the
number on the slide; the subsystem and the evidence text are the language layer added on top of
the same records once the binary works.

**In one sentence:** input = 24 h of 17 SCADA channels ending now + turbine context + the
question; output = whether a fault stop is coming in the next H hours, which subsystem, and the
evidence — ending in a label we can score.

---

## 6. Input specification

```
      |<──────── input: 24 h, 144 steps @ 10 min ────────>|<── H ──>|
  ────┼───────────────────────────────────────────────────┼─────────┼──────
   t-24h                                                  t        alarm
                                                          ^ anchor: nothing after this is seen
```

**Time-series part**
- Window: 24 h = 144 steps at 10 min, ending at the anchor `t`. (12 h is the fallback if the model
  struggles; 48 h a later experiment. The connector takes the length as a parameter.)
- Channels: the 17 base signals of section 2, fixed order, one `TimeSeries` each.
- Normalisation: per-channel z-score inside the window; original mean / std / unit written into
  the channel's text description (OpenTSLM convention).
- Missing values: forward-fill up to 3 steps, else 0 after z-scoring; drop windows with > 20 %
  missing in any core channel.

**Text part**
- Context: turbine id and type, rated power, month, state at `t` (producing / idle), the horizon
  H, and the number of fault-class events on this turbine in the previous 30 days.
- Per-channel description: `"generator bearing rear temperature in °C, 10-minute means over 24 h,
  mean 45.0 std 3.6:"`.
- Question: the T1–T5 prompt (with the subsystem list for T1/T3).
- **Never given:** anything from after `t` — no alarm message, code or category.

**Anchors and sampling (T1)**
- Positives: for every fault-class Forced outage (dedupe repeats of the same message within 2 h to
  the first), three records with `t = alarm − 1 h`, `− 3 h`, `− 6 h`. Drop a record if the turbine
  is not producing at `t` (already stopped → trivial) or if a manual / maintenance stop overlaps
  the window.
- Negatives: random anchors where the turbine is producing at `t` and no fault-class event starts
  in `(t, t + 6 h]` and none is ongoing. Sampled 2:1 against positives.
- Labels stored as annotations: `fault_within_1h`, `fault_within_3h`, `fault_within_6h`
  (class or `none`), `lead_time_min`, `next_event_message`, `next_event_duration_h`,
  `next_event_lost_kwh`, `state_at_anchor`.

**Splits (no leakage)** — train on the larger farm, hold out the smaller one entirely

| Split | Data | What it tests |
|---|---|---|
| Train | Penmanshiel turbines 1–12 (no #3 exists), 2017 → 2019 | — |
| Validation | Penmanshiel turbines 13–15, 2017 → 2019 | unseen turbines, same site |
| Test A | Penmanshiel, all 14 turbines, 2020 → 2021 | unseen **time** |
| Test B | Kelmarsh, all 6 turbines, 2017 → 2021 | unseen **site and turbine model** (MM82 → MM92) |

Penmanshiel has ~2× the data (14 turbines × 5 years) — 10,410 fault-type events vs 3,387 at
Kelmarsh — so it is the training farm. 73 alarm messages occur on both farms; the 14
Kelmarsh-only messages are rare (≤ 4 each), so the taxonomy is built from the union.

---

## 7. Output specification

The prompt is fixed text (input tokens, no loss); the **answer** is what the model learns (loss
only there). Template for T1:

```
pre_prompt:
  You are monitoring wind turbine {turbine_id} ({turbine_type}, {rated_kw} kW) in {month}.
  Below are the last 24 hours of 10-minute SCADA signals, ending now. The turbine is
  currently {state}. Analyse the signals and decide whether a fault-related stop
  (forced outage) is likely to begin within the next {H} hours. If yes, name the
  subsystem from: generator_cooling, gearbox_lubrication, pitch_system, brake_hydraulics,
  converter_grid, structural_overspeed, sensor_comms.
  Do not state a decision until the final line. End with "Answer: ".

time_series_text[i]:  "{channel} in {unit}, 10-minute means over 24 h, mean {m} std {s}:"  + 144 values
post_prompt:          Assessment:
```

Answer, MVP (label only — day 1):

```
Answer: no
Answer: yes, generator_cooling
```

Answer, full (evidence first, then label — day 2):

```
Wind rose from 4 to 8 m/s over the last 6 hours and power ramped from 200 kW to 1.1 MW.
Generator rear bearing temperature climbed 7 °C in 4 hours and is at its 24 h maximum,
while the front bearing stayed flat at 41 °C — the rear side is not being cooled as load
increases. Gear oil and pitch behave normally. This pattern precedes a generator cooling
stop. Recommended: limit power to 1 MW and check generator fan 1.
Answer: yes, generator_cooling
```
```
Production is steady at 6–7 m/s, all temperatures track load, pressures and grid values
are stable. No sign of a developing fault.
Answer: no
```

The text after `Answer:` must be exactly parseable — that is what gets scored. The evidence comes
**before** `Answer:` so the model reasons first (OpenTSLM shows this improves label accuracy).

T3 (post-hoc) keeps the five-line FINDING / EVIDENCE / CAUSE / IMPACT / ACTION template of the
worked example, followed by `Answer: <subsystem>`.

**How training targets are produced** (there are no technician reports in the data):

1. `Answer:` line, kWh, duration, lead time come directly from the log and Lost Production columns.
2. Evidence sentences are generated by **rules** over the window: largest z-score excursions,
   temperature deltas over the last 3–6 h and vs ambient, front-vs-rear bearing asymmetry,
   power-vs-wind residual (farm's own power curve), pitch / RPM state, pressure drift, grid steps.
   Only rule-verified facts go in; nothing from after `t`.
3. A frontier LLM paraphrases the rule output into fluent text (OpenTSLM's HAR-CoT recipe),
   instructed not to add facts. We human-check a 5 % sample.
4. Negatives get short fixed answers.

---

## 8. Subsystem taxonomy (label space)

~130 raw messages (union of both farms) → 11 classes. The mapping lives as a versioned table in the connector.

| Class | Raw messages (examples) | Type |
|---|---|---|
| `generator_cooling` | Overload generator fan 1/2/3, Overload transformer fan inlet/outlet air | fault |
| `brake_hydraulics` | Brake accumulator defect, Timeout brake closed, Feedback brake 1, Brake pads worn, Error brake resistor CHP, Hydraulic oil flushing operation | fault |
| `pitch_system` | Battery charge cycle axis 1/2/3 error, Pitch measuring system 1><2, Limit switch error 95° axis N, Error lubrication pump pitch, Pitch batteries charging cycle | fault |
| `converter_grid` | Frequency converter error / not ready, Grid loss, Overvoltage, Maximum grid frequency, Reduced power converter, Repeating error BP52 | fault |
| `gearbox_lubrication` | Low gearbox oil pressure, Overload gear oil pump, Overload gear bypass filter, Implausible gear speed, Particle sensor defect | fault |
| `yaw_cable` | Cable autounwind, Manual yaw, Deviation winddirection > 60° | fault / operational |
| `structural_overspeed` | Tower oscillation X/Y level 1/2, Oscillation encoder tower, High rotor speed nacelle | fault |
| `sensor_comms` | Comm. failure FPM, Data communication unavailable, 4-20 mA anemometer / vane, Vane 2 defect, No assignment to a PMU | fault (data) |
| `environmental_stop` | Wind < start wind, Max. wind speed, Absence of wind during run-up, Gearbox warm-up stage, ice | benign stop |
| `curtailment_external` | Externally stopped, P output externally reduced, Reduced power converter (grid request) | benign stop |
| `manual_safety` | Manual stop (on site / remote), Park master stop, Remote stop, Safety chain open, Emergency stop, Battery test, Test brake program | benign (context only, not a T2 target) |

---

## 9. Evaluation and baselines

| Task | Metric | Baselines | Reported on |
|---|---|---|---|
| **T1 binary** (fault stop within H) | AUROC; **recall at 10 % false-alarm rate**, per H ∈ {1, 3, 6} h; per subsystem class | "always no" · gradient boosting on window statistics (slopes, deltas, power-curve residual) · text-only LLM given the same statistics · OpenTSLM zero-shot (no fine-tune) | Val · Test A (unseen years) · **Test B (unseen farm)** |
| T1 subsystem | Macro-F1 over positives, confusion matrix | GBM on statistics | Val · A · B |
| T1 evidence text | Factual consistency of evidence sentences vs rule facts; human rating of 30 samples | GBM + LLM-afterwards (fluent but ungrounded) | Test A, B (qualitative in demo) |
| T2 escalation | AUROC, recall at 10 % FAR | GBM | Val · A · B |
| T3 post-hoc | Subsystem accuracy / macro-F1 | GBM · text-only LLM | Val · A · B |
| T5 localisation | IoU of predicted vs true stop interval | rule (power ≈ 0 while wind > cut-in) · TimeRLM zero-shot | Test A |

The pitch structure:

| | Binary "fault stop in 6 h" | Explanation |
|---|---|---|
| GBM on features | strong — the number to beat | none |
| GBM + LLM afterwards | same number | fluent but never saw the signal |
| **TSLM (ours)** | must be ≥ GBM, or we say why not | grounded in the raw signal, one model, no per-site features |

Headline numbers: **recall at 10 % false alarms at 3 h and 6 h lead, on the unseen farm**, per
class. Cooling and lubrication are expected to score; grid and comms are not, and we say so.

---

## 10. Not in scope · limitations we will state

- **No remaining-useful-life or long-horizon forecasting** — not enough run-to-failure history
  per component. (TimesFM-3 may appear as an optional power-forecast baseline only.)
- **Ground truth is the alarm log, not a technician's diagnosis.** The true root cause may differ.
- **Many alarms have no precursor at 10-min resolution** (grid loss, comms). T4 will work for
  thermal / hydraulic classes and not others; we report per class.
- **Explanations are rule-derived text paraphrased by an LLM** — faithful by construction, not
  expert-written.
- **Not every fault has a precursor.** Grid loss, comms and manual stops are unpredictable from
  turbine signals by construction; the headline metric is reported per class, not averaged over
  them.
- **One manufacturer (Senvion).** Generalisation to Vestas / Siemens is untested.

---

## 11. Decisions for the team

- **Split direction — decided:** train on Penmanshiel (larger), hold out Kelmarsh. Verified: both
  farms populate the same core channels and share 73 alarm messages; Kelmarsh-only ones are rare.
- **Window length** — 24 h proposed (144 steps). 12 h halves compute; 48 h helps thermal drifts.
- **Channel set** — 16 (section 2) or a minimal 8 (wind, power, rotor rpm, pitch A, gen bearing
  rear, stator, gear oil temp, gear oil pressure)?
- **Lead times** — 1 / 3 / 6 h proposed (three records per alarm). 12 h is the ambitious add-on.
- **Negative sampling ratio** — 2:1 proposed.
- **T2 / T4 / T5** — only if T1 is training by hour 12.
- **Explanation generation** — which LLM paraphrases, who owns the 5 % human check.

---

*Companion to `docs/team-brief.html`. Signal names, message texts and the worked example are
taken from the Kelmarsh 2016 export.*
