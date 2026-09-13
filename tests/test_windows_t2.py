"""T2 warning-escalation records on the synthetic turbine-year (fixture from test_windows)."""

import pandas as pd
from test_windows import synthetic  # noqa: F401  (pytest fixture)

from turbine_tslm.data.windows import build_t2_windows, records_to_frame


def test_warning_records_label_escalation_within_24h(synthetic):  # noqa: F811
    scada, status, fault_start = synthetic
    warn = pd.DataFrame(
        {
            "start": [
                fault_start - pd.Timedelta(hours=4),
                pd.Timestamp("2019-03-08 10:00", tz="UTC"),
            ],
            "end": [pd.NaT, pd.NaT],
            "duration_s": [None, None],
            "status": ["Warning", "Warning"],
            "code": ["2551", "2552"],
            "message": ["Overload generator fan 2", "Overload generator fan 3"],
            "service_category": ["", ""],
            "iec_category": ["Full Performance", "Full Performance"],
        }
    )
    status = pd.concat([status, warn], ignore_index=True).sort_values("start")
    recs = build_t2_windows(scada, status, "penmanshiel", 7)
    assert [r.task for r in recs] == ["t2", "t2"]
    esc, no = sorted(recs, key=lambda r: r.anchor)
    assert (
        esc.is_positive
        and esc.label == "generator_cooling"
        and esc.warning_message == "Overload generator fan 2"
    )
    assert (
        esc.next_event_message == "Overload generator fan 1"
        and 230 < esc.lead_time_min < 250
    )
    assert (
        not no.is_positive
        and no.label == "none"
        and no.warning_message == "Overload generator fan 3"
    )
    df = records_to_frame(recs, year=2019)
    assert set(df["task"]) == {"t2"} and df["window_id"].str.endswith("-w24").all()
    assert df["fault_within_24h"].tolist() == ["generator_cooling", "none"]
