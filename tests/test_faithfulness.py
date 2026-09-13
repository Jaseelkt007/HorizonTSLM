"""The checker verifies the rule-generated targets and catches fabricated numbers / inconsistent conclusions."""

import numpy as np
from test_evidence import steady_window

from turbine_tslm.data.evidence import evidence_text
from turbine_tslm.eval.faithfulness import check_text


def _anomalous():
    s = steady_window()
    s["gen_bearing_rear_temperature"][108:] += np.linspace(0, 8, 36)
    s["tower_acceleration_x"][138:] += 15.0
    return s


def test_generated_targets_verify_completely():
    s = _anomalous()
    text = evidence_text(s, "generator_cooling")
    c = check_text(text, s)
    assert c["n_claims"] >= 4 and c["wrong"] == 0 and c["unverifiable"] == 0
    assert c["conclusion"] == "generator_cooling" and c["conclusion_consistent"] is True
    c = check_text(evidence_text(steady_window(), "none"), steady_window())
    assert (
        c["wrong"] == 0
        and c["conclusion"] == "none"
        and c["conclusion_consistent"] is True
    )


def test_fabricated_number_and_wrong_conclusion_are_caught():
    s = _anomalous()
    text = evidence_text(s, "generator_cooling").replace("rose 8 °C", "rose 30 °C")
    c = check_text(text, s)
    assert c["wrong"] >= 1
    text = evidence_text(s, "generator_cooling").replace(
        "Answer: yes, generator_cooling", "Answer: yes, pitch_system"
    )
    assert check_text(text, s)["conclusion_consistent"] is False
    c = check_text(
        "The stator reached 250 °C and the gearbox exploded at 14:00.\nAnswer: no", s
    )
    assert c["n_claims"] == 0 and c["unverifiable"] == 1
