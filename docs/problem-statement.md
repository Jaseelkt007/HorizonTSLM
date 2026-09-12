# Problem statement — Turbine Alarm Explainer

*Temporal AI Challenge · v1 for team review · 12 Sep 2026*

A Time-Series Language Model (TSLM) that reads a wind turbine's sensor data and tells the
operations engineer, in plain language: **what happened, which part of the turbine is involved,
what it cost, and whether trouble is coming.**

---

## 0. The idea in plain words

A wind farm records ~300 sensor channels per turbine every 10 minutes (wind, power, temperatures,
pressures, pitch, vibration …). Separately, the turbine controller writes a **log of events** with
a text message, e.g. `Overload generator fan 2`, `Low gearbox oil pressure`, `Grid loss`,
`Wind < start wind`.

Today an engineer looks at the event list every morning and, for the events that look serious,
opens the sensor plots to understand what happened. That is slow and needs expertise.

**We train a model that does that step:** give it the sensor data of the hours before an event,
and it writes the explanation an engineer would write — and names the subsystem.

Because the log message is *already* in the data, we have the answer for every event. That is
what makes this trainable: **sensor window in → log message (and an explanation built around
it) out.** We never show the model the message; it must infer it from the signals.

```
INPUT                                             OUTPUT
24 h of ~16 sensor channels (10-min data)  ──►    FINDING   Generator cooling warning while idle.
+ "Turbine K1, MM92, 2.05 MW, June"               EVIDENCE  Wind 2–3 m/s, power ≈ 0, rear bearing
+ "Describe what happened and name                          temp rose 37.6 → 40.6 °C with no load …
   the subsystem."                                CAUSE     Generator fan 1 overload (cooling).
                                                  IMPACT    0 kWh lost — no wind available.
                                                  ACTION    Inspect fan 1 before wind returns.
                                                  Answer: generator_cooling
```

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

- Kelmarsh 2016: temperatures / RPM / pitch only exist from **May 2016** → use June 2016 onward.
- 649 of 2,122 status rows in one turbine-year have an open end (`-`) → treat as point events.
- `Battery test` and `Manual stop` dominate the log → excluded from fault classes, kept as context.
- After filtering: ~900 real Stop/Warning events per 6 turbines per year → roughly **5,000
  Kelmarsh + 8,000 Penmanshiel labelled events** overall.

---

## 3. Problems we solve

- **Separate real faults from operational noise.** Thousands of events; the engineer needs the
  ones that indicate a component problem, with the evidence in the signals.
- **Explain, not just flag.** An alarm code says *what tripped*; it does not say what the
  temperatures, power and pitch were doing in the hours before. The model narrates that.
- **Price the event.** Lost kWh, whether the turbine is still down, whether wind is available.
- **Anticipate.** Given a quiet window, is a forced outage likely in the next hours, in which
  subsystem?
- **Generalise across machines.** Train on one farm, still work on a different turbine model at
  another site — that is what a real fleet looks like.

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

### Worked example (real event)

Kelmarsh turbine 1, 9 June 2016. Log row: `Overload generator fan 1` (Warning, code 2550,
IEC "Forced outage", 12:34–14:14, 1 h 40 min). Hourly means of the six hours before:

| Hour | Wind m/s | Power kW | Rotor rpm | Gen. bearing rear °C | Stator °C | Ambient °C | Pitch A ° |
|---|---|---|---|---|---|---|---|
| 06:00 | 2.5 | −1.1 | 0.7 | 39.1 | 55.9 | 11.4 | 45.0 |
| 08:00 | 2.1 | 1.0 | 1.3 | 38.0 | 50.2 | 14.4 | 40.8 |
| 09:00 | 2.9 | 15.6 | 6.2 | 37.6 | 51.8 | 15.8 | 11.9 |
| 11:00 | 2.8 | −1.0 | 0.2 | 40.5 | 52.2 | 19.0 | 79.0 |
| 12:00 | 2.6 | −2.0 | 0.0 | 40.6 | 50.4 | 20.2 | 91.3 |

Target output:

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
training targets: no claims the data cannot support.**

---

## 5. Task definitions — inputs and outputs

All tasks share the same input (section 6) and are stored as TimeNet tasks on the same records.

| # | Task | Prompt (abridged) | Output | Label source | TimeNet type | Priority |
|---|---|---|---|---|---|---|
| T1 | **Event explanation** (headline) | "Turbine K1 (MM92). The window ends at the start of a status event. Describe what happened, name the subsystem, state impact, recommend an action." | 5-line report ending in `Answer: <subsystem>` | Message + category → subsystem; evidence from rules over the window; kWh from Lost Production | `AnswerTask` (+ rationale) | **Must** |
| T2 | **Subsystem classification** (measurable core of T1) | Same window. "Which subsystem does this event belong to?" (class list given) | 1 of 10 classes (section 8) | Message → taxonomy | `ClassificationTask` | **Must** |
| T3 | **Fault vs benign triage** | "Is this a component fault, an environmental/operational stop, or normal operation?" | `fault` / `benign_stop` / `normal` | IEC category + message; *normal* = windows with no event | `ClassificationTask` | **Must** |
| T4 | **Precursor detection** ("anticipate") | 12 h window with *no* event inside. "Will a forced outage start within the next 6 h? Which subsystem?" | `none` or subsystem | Next event after the window; negatives from quiet periods | `ClassificationTask` | Should |
| T5 | **Outage localisation** | 48 h window with one stop. "When did the turbine stop producing although wind was available?" | (start, end) | Event start/end | `TemporalLocalizationTask` | Stretch (TimeRLM comparison) |
| T6 | **Impact estimate** | "How much production was lost during this event?" | kWh | Sum of Lost Production Total over the span | `ScalarPredictionTask` | Stretch (also in T1's IMPACT) |

**In one sentence:** input = 24 h of ~16 SCADA channels + text context + question; output = a
short finding with evidence, subsystem, impact and action, ending in a label we can score.
T2/T3 give the numbers, T1 gives the demo, T4 gives the "sense of time".

---

## 6. Input specification

**Time-series part**
- Window: 24 h = 144 steps at 10 min, ending at the event start (T1–T3) or 6 h before it (T4).
  48 h for T5.
- Channels: the ~16 base signals, fixed order, one `TimeSeries` each.
- Normalisation: per-channel z-score inside the window; original mean / std / unit written into
  the channel's text description (OpenTSLM convention).
- Missing values: forward-fill up to 3 steps, else 0 after z-scoring; drop windows with > 20 %
  missing in any core channel.

**Text part**
- Context: turbine id and type, rated power, month, ambient at window end, number of events
  with the same message on this turbine in the previous 30 days.
- Per-channel description: `"Generator bearing rear temperature, °C, 10-min, mean 39.4, std 1.1"`.
- Question: one of the T1–T6 prompts (with the class list for T2–T4).
- **Not given:** the alarm message, code or category — those are the answer.

**Sampling**
- Positive windows: one per Stop/Warning event mapped to a fault or benign-stop class (dedupe
  events starting within 10 min on the same turbine → keep the highest-severity message).
- Normal windows: random 24 h windows with no Stop/Warning inside and none in the following
  6 h, sampled 1:1 with positives.

**Splits (no leakage)**

| Split | Data | Tests |
|---|---|---|
| Train | Kelmarsh turbines 1–4, 2016-06 → 2019-12 | — |
| Validation | Kelmarsh turbines 5–6, same years | unseen turbines |
| Test A | Kelmarsh 2020–21, all turbines | unseen **time** |
| Test B | Penmanshiel, all 14 turbines, all years | unseen **site and turbine model** |

---

## 7. Output specification

The model always answers in the same template, then the scored label:

```
FINDING   one sentence: what kind of event, turbine state
EVIDENCE  2–4 sentences: which channels moved, by how much, over what time, relative to wind/load
CAUSE     most plausible subsystem-level cause, hedged when evidence is weak
IMPACT    kWh lost in the event span; wind available or not; still down or not
ACTION    one recommendation, or "no action — <reason>"
Answer: <subsystem class>
```

**How training targets are produced** (there are no technician reports in the data):

1. CAUSE class, IMPACT numbers and `Answer` come directly from the log row and Lost Production
   columns.
2. EVIDENCE sentences are generated by **rules** over the window: largest z-score excursions,
   temperature deltas vs ambient, power-vs-wind residual (farm's own power curve), pitch state,
   RPM state, step changes in grid channels. Only rule-verified facts go in.
3. A frontier LLM paraphrases the rule output into fluent text (same recipe as OpenTSLM's
   HAR-CoT / Sleep-CoT), instructed not to add facts. We human-check a 5 % sample.
4. Benign classes get short targets ("Low-wind standby, no fault. No action.").

---

## 8. Subsystem taxonomy (label space)

~120 raw messages → 10 classes. The mapping lives as a versioned table in the connector.

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
| `environmental_stop` | Wind < start wind, Absence of wind during run-up, Gearbox warm-up stage, ice / curtailment | benign stop |
| `manual_safety` | Manual stop (on site / remote), Park master stop, Remote stop, Safety chain open, Emergency stop, Battery test, Test brake program | benign (context only, not a T2 target) |

---

## 9. Evaluation and baselines

| Task | Metric | Baselines | Reported on |
|---|---|---|---|
| T2 subsystem | Macro-F1, accuracy, confusion matrix | Majority class · logistic regression / GBM on window statistics · text-only LLM given the same statistics as text · OpenTSLM zero-shot | Val · Test A · Test B |
| T3 triage | F1 on `fault`, precision at an operator-acceptable point | same | Val · A · B |
| T4 precursor | AUROC, recall at 10 % false-alarm rate, per subsystem | GBM on statistics · "always none" | Val · A · B |
| T1 explanation | Answer accuracy + factual consistency of EVIDENCE vs rule facts + human rating of 30 samples | text-only LLM with statistics | Test A, B (qualitative in demo) |
| T5 localisation | IoU of predicted vs true stop interval | rule (power ≈ 0 while wind > cut-in) · TimeRLM zero-shot | Test A |

Headline numbers for the pitch: **macro-F1 on the unseen farm (Test B)** for T2, and **recall
at 10 % false alarms** for T4.

---

## 10. Not in scope · limitations we will state

- **No remaining-useful-life or long-horizon forecasting** — not enough run-to-failure history
  per component. (TimesFM-3 may appear as an optional power-forecast baseline only.)
- **Ground truth is the alarm log, not a technician's diagnosis.** The true root cause may differ.
- **Many alarms have no precursor at 10-min resolution** (grid loss, comms). T4 will work for
  thermal / hydraulic classes and not others; we report per class.
- **Explanations are rule-derived text paraphrased by an LLM** — faithful by construction, not
  expert-written.
- **One manufacturer (Senvion).** Generalisation to Vestas / Siemens is untested.

---

## 11. Decisions for the team

- **Window length** — 24 h proposed (144 steps). 12 h halves compute; 48 h helps thermal drifts.
- **Channel set** — 16 (section 2) or a minimal 8 (wind, power, rotor rpm, pitch A, gen bearing
  rear, stator, gear oil temp, gear oil pressure)?
- **T4 horizon** — 6 h proposed.
- **T5 / T6** — only if T1–T3 are training by hour 12.
- **Explanation generation** — which LLM paraphrases, who owns the 5 % human check.

---

*Companion to `docs/team-brief.html`. Signal names, message texts and the worked example are
taken from the Kelmarsh 2016 export.*
