# Pitch outline — Turbine Alarm Explainer

*Every number below is copied from `docs/method.md` / `docs/results/`; do not put a figure on a slide that is not in
those files. Suggested length: 8 slides + demo.*

## 1. The problem (30 s)

- A wind farm logs ~4,000 status events a year per 14 turbines. The log arrives *after* the turbine has stopped.
- Fault-class stops cost Penmanshiel ≈ 1,260 MWh a year (≈ £60–100k) plus call-outs; the top 5 % of stops last
  over 6 h — those are the ones where lead time turns a forced stop into a planned intervention.
- Nobody watches 300 channels × 14 turbines for a bearing heating faster than load explains.

## 2. What we built (30 s)

- One model reads the last 24 h of 19 SCADA channels and answers, hours before the controller trips: **will a fault
  stop begin within 1 / 3 / 6 h, in which subsystem, and why** — in text an operator can act on, with every number
  checkable against the data.
- Same model answers the post-hoc question ("what happened, which subsystem") on the same window.
- Built on OpenTSLM (Flamingo variant on Llama-3.2-1B) with TimeNet as the data format; a new, off-list dataset
  (Cubico Penmanshiel + Kelmarsh) with reusable TimeNet connectors.

## 3. The honest test (30 s)

- Train on Penmanshiel (MM82). **Test on Kelmarsh — a farm and turbine model the model never saw** — and on
  Penmanshiel years it never saw. Nothing after the window end is ever an input; the alarm text is the label only.
- Every model — ours, gradient boosting, always-no — is scored on identical records with one harness.

## 4. The showcase (60 s, live or screenshot from the demo)

- Kelmarsh turbine 1, 18 Jan 2018, one hour before a structural/overspeed stop (4 of 6 numbers verified):
  "Wind rose from 11 to 15 m/s over the day and the turbine is producing about 2052 kW. Stator temperature rose
  18 °C in the last 6 h to 79 °C while power rose from 2028 to 2052 kW. Wind is 14 m/s in the last hour (24 h
  maximum 19 m/s) with the rotor at 15.1 rpm and power at 2052 kW. This pattern precedes a structural or overspeed
  stop. Answer: yes, structural_overspeed"
- Then a quiet window: "…No sign of a developing fault. Answer: no"
- Show the verified / wrong highlighting: the numbers are checked, not trusted.

## 5. Results (60 s) — Kelmarsh, unseen farm

| model | recall @ 10 % false alarms | hard F1 | subsystem acc | explanation |
|---|---|---|---|---|
| always no | 0.00 | – | – | – |
| XGBoost on 24 h statistics | 0.21 (0.22 with context) | 0.20 | 0.09 | none |
| TSLM, label only | 0.24 | 0.24 | 0.08 | none |
| **TSLM, reason-first + rich text** | **0.27** [0.24, 0.30] | **0.42** | **0.25** | **86 % of numbers verified** |

- Paired bootstrap: the recall gain over XGBoost is significant (Δ = −0.06 for XGBoost, 95 % CI [−0.10, −0.03]).
- Reason-first training improved the *decision*, not just the text: hard F1 0.24 → 0.42, subsystem accuracy 3×.
- On unseen years (test_a): recall 0.35, subsystem accuracy 0.48, post-hoc subsystem accuracy 0.65. XGBoost is
  stronger there on AUROC (0.78 vs 0.67) — say it.

## 6. Where the signal is (30 s) — per subsystem, Kelmarsh, recall @ 10 % FAR

- structural / overspeed 0.59 (XGBoost 0.40) — learnable from 10-min data, subsystem named correctly 55 %.
- generator cooling 0.13, pitch 0.09, grid 0.09, brake 0.00 — no or weak precursor at this resolution, or too few
  training examples (83 / 54 for the thermal classes). We report them; we don't average them away.
- Warning escalation (T2): built, not learnable — 7 escalating warnings in the training set.

## 7. How we got here (30 s) — three findings worth repeating

1. Reason-first targets (rule-generated, faithful by construction) beat label-only on every hard metric.
2. A 1B TSLM can't read a 6 h delta off z-scored patches: writing the last-hour / 6 h-ago statistics into the channel
   text took verified claims from 52 % to 86 %.
3. Check the text mechanically: 28 % of explanations still contain a wrong number, and the demo shows which.
   (Plus two OpenTSLM infrastructure fixes: open-flamingo 2.x, left-padded generation.)

## 8. Limitations and next (30 s)

- Ground truth is the alarm log, not a technician; one manufacturer, two farms, 572 training events.
- Next: more sites (the connector is reusable), class-balanced training for the thermal classes, an LLM judge for
  coherence, a second RFT round with the faithfulness checker as reward, T4 (kWh at risk).

## Demo flow

1. Farm view → pick Kelmarsh turbine with a high score.
2. Window: signals, explanation with verified numbers, answer, score → reveal "what actually happened" and lead time.
3. Same window, post-hoc question.
4. Results tab.
