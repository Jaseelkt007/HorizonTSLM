"""Evidence text is derived from the window only and says the right things about planted anomalies."""

import numpy as np

from turbine_tslm.data.channels import CHANNEL_NAMES
from turbine_tslm.data.evidence import evidence_sentences, evidence_text, extract_facts


def steady_window(seed=0):
    rng = np.random.default_rng(seed)
    s = {c: rng.normal(0, 0.1, 144) for c in CHANNEL_NAMES}
    s["wind_speed"] += 7.0
    s["power"] += 900.0
    s["rotor_speed"] += 14.0
    s["pitch_angle"] += 1.0
    for c in ("gen_bearing_front_temperature", "gen_bearing_rear_temperature"):
        s[c] += 45.0
    s["stator_temperature"] += 60.0
    s["gear_oil_temperature"] += 55.0
    s["main_bearing_temperature"] += 35.0
    s["ambient_temperature"] += 12.0
    s["gear_oil_inlet_pressure"] = 200.0 + rng.normal(0, 2.0, 144)
    s["grid_frequency"] = 50.0 + rng.normal(0, 0.01, 144)
    s["grid_voltage"] = 690.0 + rng.normal(0, 1.0, 144)
    s["tower_acceleration_x"] += 10.0
    return s


def test_steady_window_has_no_evidence_and_says_so():
    s = steady_window()
    assert evidence_sentences(extract_facts(s)) == []
    text = evidence_text(s, "none")
    assert text.endswith("Answer: no") and "No sign of a developing fault" in text
    assert "producing about 900 kW" in text


def test_rear_bearing_ramp_is_named_and_quantified():
    s = steady_window()
    s["gen_bearing_rear_temperature"][108:] += np.linspace(
        0, 8, 36
    )  # +8 °C over the last 6 h
    text = evidence_text(s, "generator_cooling")
    assert (
        "Generator rear bearing temperature rose 8 °C" in text
        and "at steady load" in text
    )
    assert "24 h maximum" in text
    assert "rear bearing is now" in text and "hotter than the other side" in text
    assert text.endswith("Answer: yes, generator_cooling")
    assert "generator cooling stop" in text


def test_oil_pressure_drop_and_tower_vibration():
    s = steady_window()
    s["gear_oil_inlet_pressure"][108:] -= np.linspace(0, 80, 36)  # -40 % at steady load
    s["tower_acceleration_x"][138:] += 15.0
    sents = [x for _, x in evidence_sentences(extract_facts(s))]
    assert any("Gear oil inlet pressure fell" in x and "% over 6 h" in x for x in sents)
    assert any("Tower acceleration X" in x and "× its 24 h median" in x for x in sents)


def test_positive_without_precursor_is_honest():
    text = evidence_text(steady_window(), "converter_grid")
    assert "No specific precursor" in text and text.endswith(
        "Answer: yes, converter_grid"
    )


def test_load_following_rise_is_not_an_anomaly_and_conclusion_is_gated():
    s = steady_window()
    s["power"][108:] += np.linspace(0, 900, 36)  # load ramps up over the last 6 h
    s["stator_temperature"][108:] += np.linspace(0, 8, 36)  # +8 °C following the load
    tagged = evidence_sentences(extract_facts(s))
    assert not any(tag == "stator_temperature" for tag, _ in tagged)
    s["gen_bearing_rear_temperature"][108:] += np.linspace(
        0, 20, 36
    )  # +20 °C: reported even under load
    text = evidence_text(s, "yaw_cable")
    assert (
        "Generator rear bearing temperature rose 20 °C" in text
        and "while power rose" in text
    )
    assert (
        "No specific precursor" in text
    )  # thermal evidence does not justify a yaw conclusion


def test_facts_use_only_the_window():
    f = extract_facts(steady_window())
    assert set(f) >= {
        "wind_last1h",
        "power_last1h",
        "residual_last3h",
        "bearing_asym_now",
        "excursions",
    }
    assert "next_event" not in " ".join(f)
