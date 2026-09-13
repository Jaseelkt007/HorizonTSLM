"""Prompt and answer templates for the early-warning task (docs/problem-statement.md §7). Single source for
the connector (which stores them in AnswerTask) and the training dataset class."""

from __future__ import annotations

from turbine_tslm.data.channels import CHANNELS
from turbine_tslm.data.taxonomy import fault_classes

TURBINE_TYPE = {"penmanshiel": "Senvion MM82", "kelmarsh": "Senvion MM92"}
RATED_KW = 2050
POST_PROMPT = "Assessment:"

PRE_PROMPT = (
    "You are monitoring wind turbine {turbine_id} ({turbine_type}, {rated_kw} kW) in {month}. "
    "Below are the last 24 hours of 10-minute SCADA signals, ending now. The turbine is currently {state}. "
    "Analyse the signals and decide whether a fault-related stop (forced outage) is likely to begin within the "
    "next {horizon_h} hours. If yes, name the subsystem from: {classes}. "
    'Do not state a decision until the final line. End with "Answer: ".'
)


def pre_prompt(
    farm: str, turbine_id: str, month: str, state: str, horizon_h: int
) -> str:
    return PRE_PROMPT.format(
        turbine_id=turbine_id,
        turbine_type=TURBINE_TYPE[farm],
        rated_kw=RATED_KW,
        month=month,
        state=state,
        horizon_h=horizon_h,
        classes=", ".join(fault_classes()),
    )


def series_text(channel_name: str, mean: float, std: float) -> str:
    ch = next(c for c in CHANNELS if c.name == channel_name)
    return f"{ch.description} in {ch.unit_text}, 10-minute means over 24 h, mean {mean:.1f} std {std:.1f}:"


def answer_label(label: str) -> str:
    """MVP answer: the scored line only."""
    return "Answer: no" if label == "none" else f"Answer: yes, {label}"


# ---- T3 post-hoc explanation (docs/problem-statement.md §5), derived from the 1 h early-warning windows:
# the window ends about one hour before the event, so the prompt says so (the spec's 30 min anchor would need a rebuild).
T3_PRE_PROMPT = (
    "You are reviewing wind turbine {turbine_id} ({turbine_type}, {rated_kw} kW) in {month}. "
    "Below are 24 hours of 10-minute SCADA signals. A status event began about one hour after the end of this window "
    "and stopped the turbine. Describe what the signals show and name the subsystem from: {classes}. "
    'Do not state a decision until the final line. End with "Answer: ".'
)


def t3_pre_prompt(farm: str, turbine_id: str, month: str) -> str:
    return T3_PRE_PROMPT.format(
        turbine_id=turbine_id,
        turbine_type=TURBINE_TYPE[farm],
        rated_kw=RATED_KW,
        month=month,
        classes=", ".join(fault_classes()),
    )


def t3_answer_label(label: str) -> str:
    return f"Answer: {label}"


# ---- T2 warning escalation: the warning text is known at the anchor, so it is part of the question.
T2_PRE_PROMPT = (
    "You are monitoring wind turbine {turbine_id} ({turbine_type}, {rated_kw} kW) in {month}. "
    "Below are the last 24 hours of 10-minute SCADA signals, ending now. The turbine is currently {state}. "
    'The controller has just raised the warning "{warning}". Decide whether it will escalate to a fault stop '
    "(forced outage) within the next 24 hours. If yes, name the subsystem from: {classes}. "
    'Do not state a decision until the final line. End with "Answer: ".'
)


def t2_pre_prompt(
    farm: str, turbine_id: str, month: str, state: str, warning: str
) -> str:
    return T2_PRE_PROMPT.format(
        turbine_id=turbine_id,
        turbine_type=TURBINE_TYPE[farm],
        rated_kw=RATED_KW,
        month=month,
        state=state,
        warning=warning,
        classes=", ".join(fault_classes()),
    )
