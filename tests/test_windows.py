"""Window/label logic on a synthetic turbine-year: one fault stop, one manual stop, steady production elsewhere."""

import numpy as np
import pandas as pd
import pytest

from turbine_tslm.data.channels import CHANNEL_NAMES, RAW_CHANNELS
from turbine_tslm.data.windows import HORIZONS_H, WINDOW_STEPS, build_windows, records_to_frame


@pytest.fixture
def synthetic():
    idx = pd.date_range("2019-03-01", periods=6 * 24 * 10, freq="10min", tz="UTC")  # 10 days
    rng = np.random.default_rng(0)
    scada = pd.DataFrame(index=idx)
    for ch in RAW_CHANNELS:
        scada[ch.column] = rng.normal(50, 5, len(idx))
    scada["Wind speed (m/s)"] = 8.0 + rng.normal(0, 1, len(idx))
    scada["Power (kW)"] = 900.0 + rng.normal(0, 50, len(idx))
    fault_start = pd.Timestamp("2019-03-06 12:00", tz="UTC")
    # controller trips the turbine at the alarm: power 0 despite wind, from the alarm onwards for 3 h
    scada.loc[fault_start : fault_start + pd.Timedelta(hours=3), "Power (kW)"] = 0.0
    status = pd.DataFrame(
        {
            "start": [fault_start, pd.Timestamp("2019-03-03 09:00", tz="UTC")],
            "end": [fault_start + pd.Timedelta(hours=3), pd.Timestamp("2019-03-03 15:00", tz="UTC")],
            "duration_s": [3 * 3600.0, 6 * 3600.0],
            "status": ["Stop", "Stop"],
            "code": ["2550", "1"],
            "message": ["Overload generator fan 1", "Manual stop - on site"],
            "service_category": ["", ""],
            "iec_category": ["Forced outage", "Scheduled Maintenance"],
        }
    )
    return scada, status, fault_start


def test_positives_one_per_horizon_with_correct_labels(synthetic):
    scada, status, fault_start = synthetic
    recs = build_windows(scada, status, "penmanshiel", 7, neg_ratio=0)
    pos = [r for r in recs if r.is_positive]
    assert sorted(r.horizon_h for r in pos) == sorted(HORIZONS_H)
    for r in pos:
        assert r.label == "generator_cooling"
        assert r.anchor < fault_start and r.anchor >= fault_start - pd.Timedelta(hours=r.horizon_h)
        assert r.fault_within[f"{r.horizon_h}h"] == "generator_cooling"
        assert r.signals.shape == (WINDOW_STEPS, len(CHANNEL_NAMES))
        assert not np.isnan(r.signals).any()


def test_nothing_after_anchor_leaks_into_signals(synthetic):
    scada, status, fault_start = synthetic
    recs = build_windows(scada, status, "penmanshiel", 7, neg_ratio=0)
    power_col = list(CHANNEL_NAMES).index("power")
    for r in recs:
        assert r.signals[:, power_col].min() > 500  # the post-alarm zeros never appear in any window


def test_negatives_avoid_faults_and_manual_stops(synthetic):
    scada, status, fault_start = synthetic
    recs = build_windows(scada, status, "penmanshiel", 7, neg_ratio=2.0, seed=1)
    neg = [r for r in recs if not r.is_positive]
    assert len(neg) == 2 * len([r for r in recs if r.is_positive])
    for r in neg:
        assert r.label == "none" and all(v == "none" for v in r.fault_within.values())
        assert not (fault_start - pd.Timedelta(hours=6) <= r.anchor <= fault_start + pd.Timedelta(hours=3))
        m_start, m_end = pd.Timestamp("2019-03-03 09:00", tz="UTC"), pd.Timestamp("2019-03-03 15:00", tz="UTC")
        window_start = r.anchor - pd.Timedelta(hours=24)
        assert not (m_start <= r.anchor and m_end >= window_start)  # window never overlaps the manual stop


def test_frame_has_split_and_one_column_per_channel(synthetic):
    scada, status, _ = synthetic
    df = records_to_frame(build_windows(scada, status, "penmanshiel", 7, neg_ratio=1.0), year=2019)
    assert set(df["split"]) == {"train"}
    assert all(c in df.columns for c in CHANNEL_NAMES)
    assert df["window_id"].is_unique
