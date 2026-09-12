"""Anchors, labels and 24 h windows for the early-warning task (docs/problem-statement.md §5–§6).

A record is a window of ``WINDOW_STEPS`` rows ending at an anchor ``t``. Labels come only from status-log events
that start *after* ``t``. Nothing after ``t`` is read when building the window.

Positives: for each fault-class Forced-outage event (deduped per class within 2 h) one record per horizon
``t = event_start - H``; dropped when the turbine is already stopped despite wind at ``t`` (the controller has
acted) or a manual / maintenance stop overlaps the window. Idle in low wind is allowed and recorded. Negatives: anchors on an hourly grid with no fault-class event starting in ``(t, t + H_max]``, none
ongoing at ``t``, no Stop in the previous 2 h, producing at ``t``; sampled ``NEG_RATIO`` per positive.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from turbine_tslm.data.channels import CHANNEL_NAMES, STEP_MINUTES, extract_channels
from turbine_tslm.data.taxonomy import classify

WINDOW_HOURS = 24
WINDOW_STEPS = WINDOW_HOURS * 60 // STEP_MINUTES  # 144
HORIZONS_H: tuple[int, ...] = (1, 3, 6)
NEG_RATIO = 2.0
DEDUPE_HOURS = 2
PRODUCING_KW = 50.0  # mean power over the last 3 steps above this -> "producing"
CUT_IN_MS = 4.0  # below this wind the turbine is legitimately idle
MAX_MISSING = 0.20  # per channel, per window
POSITIVE_STATUSES = ("Stop", "Warning")
POSITIVE_IEC = "Forced outage"

FILL_LIMIT = 3


@dataclass
class Events:
    """Status log split into the event sets the sampler needs (all UTC)."""

    faults: pd.DataFrame  # positive candidates, deduped
    forced: pd.DataFrame  # positive candidates before dedupe (for the fault_within_* labels)
    any_fault: pd.DataFrame  # every fault-class event (for negative exclusion)
    stops: pd.DataFrame  # every Stop-status row
    manual: pd.DataFrame  # manual_safety class (maintenance/test), used to exclude overlapping windows


def split_events(status: pd.DataFrame, strict_forced: bool = False) -> Events:
    """Positives are fault-class events that stopped the turbine: status ``Stop`` (IEC Forced outage or Technical
    Standby) or any ``Warning`` the operator filed as a Forced outage. ``strict_forced=True`` keeps Forced outages only."""
    cls = status["message"].map(lambda m: classify(m)[0])
    kind = status["message"].map(lambda m: classify(m)[1])
    df = status.assign(cls=cls, kind=kind)
    any_fault = df[df["kind"] == "fault"]
    faults = any_fault[any_fault["status"].isin(POSITIVE_STATUSES)]
    if strict_forced:
        faults = faults[faults["iec_category"] == POSITIVE_IEC]
    else:
        faults = faults[(faults["status"] == "Stop") | (faults["iec_category"] == POSITIVE_IEC)]
    # dedupe: same class within DEDUPE_HOURS -> keep the first
    keep, last_by_cls = [], {}
    for idx, row in faults.iterrows():
        prev = last_by_cls.get(row["cls"])
        if prev is None or (row["start"] - prev) > pd.Timedelta(hours=DEDUPE_HOURS):
            keep.append(idx)
        last_by_cls[row["cls"]] = row["start"]
    return Events(
        faults=faults.loc[keep],
        forced=faults,
        any_fault=any_fault,
        stops=df[df["status"] == "Stop"],
        # only real manual/maintenance stops disqualify a window; battery tests and brake test programs do not
        manual=df[(df["cls"] == "manual_safety") & (df["status"] == "Stop") & ~df["message"].str.contains("test", case=False)],
    )


@dataclass
class WindowRecord:
    turbine_id: str
    farm: str
    turbine: int
    anchor: pd.Timestamp
    horizon_h: int
    label: str  # subsystem class or "none"
    is_positive: bool
    state_at_anchor: str
    fault_within: dict[str, str]  # {"1h": cls|none, "3h": ..., "6h": ...}
    lead_time_min: float | None
    next_event_message: str | None
    next_event_duration_h: float | None
    next_event_iec: str | None
    signals: np.ndarray = field(repr=False)  # (WINDOW_STEPS, n_channels) raw values


def _first_fault_within(events: pd.DataFrame, t: pd.Timestamp, hours: int) -> pd.Series | None:
    """First event starting in ``(t, t + hours + one step]``; the step of slack covers anchors floored to the grid."""
    end = t + pd.Timedelta(hours=hours) + pd.Timedelta(minutes=STEP_MINUTES)
    sel = events[(events["start"] > t) & (events["start"] <= end)]
    return None if sel.empty else sel.iloc[0]


def _window(channels: pd.DataFrame, t: pd.Timestamp) -> np.ndarray | None:
    """Rows in ``(t - 24 h, t]`` as a (144, C) array, or None if incomplete / too many gaps."""
    w = channels.loc[t - pd.Timedelta(hours=WINDOW_HOURS) + pd.Timedelta(minutes=STEP_MINUTES) : t]
    if len(w) != WINDOW_STEPS:
        return None
    if (w.isna().mean() > MAX_MISSING).any():
        return None
    w = w.ffill(limit=FILL_LIMIT)
    w = w.fillna(w.mean())
    if w.isna().any().any():
        return None
    return w.to_numpy(dtype=np.float32)


def _state(channels: pd.DataFrame, t: pd.Timestamp) -> str | None:
    """``producing`` | ``idle_low_wind`` | ``stopped`` (stopped despite wind, i.e. the controller already acted)."""
    recent = channels.loc[t - pd.Timedelta(minutes=2 * STEP_MINUTES) : t, ["power", "wind_speed"]]
    if len(recent) == 0 or recent.isna().all().any():
        return None
    power, wind = float(recent["power"].mean()), float(recent["wind_speed"].mean())
    if power > PRODUCING_KW:
        return "producing"
    return "idle_low_wind" if wind < CUT_IN_MS else "stopped"


def _overlaps(df: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> bool:
    if df.empty:
        return False
    ev_end = df["end"].fillna(df["start"])
    return bool(((df["start"] <= end) & (ev_end >= start)).any())


def build_windows(
    scada: pd.DataFrame,
    status: pd.DataFrame,
    farm: str,
    turbine: int,
    horizons: tuple[int, ...] = HORIZONS_H,
    neg_ratio: float = NEG_RATIO,
    strict_forced: bool = False,
    seed: int = 0,
) -> list[WindowRecord]:
    channels = extract_channels(scada)
    ev = split_events(status, strict_forced=strict_forced)
    turbine_id = f"{farm}-{turbine:02d}"
    h_max = max(horizons)
    records: list[WindowRecord] = []

    def labels_at(t: pd.Timestamp) -> dict[str, str]:
        fw = {}
        for h in horizons:
            f = _first_fault_within(ev.forced, t, h)
            fw[f"{h}h"] = "none" if f is None else f["cls"]
        return fw

    # --- positives
    for _, fault in ev.faults.iterrows():
        for h in horizons:
            t = (fault["start"] - pd.Timedelta(hours=h)).floor(f"{STEP_MINUTES}min")
            state = _state(channels, t)
            if state in (None, "stopped"):
                continue
            w_start = t - pd.Timedelta(hours=WINDOW_HOURS)
            if _overlaps(ev.manual, w_start, t):
                continue
            sig = _window(channels, t)
            if sig is None:
                continue
            fw = labels_at(t)
            lead = (fault["start"] - t).total_seconds() / 60
            records.append(
                WindowRecord(
                    turbine_id, farm, turbine, t, h, fault["cls"], True, state, fw, lead,
                    fault["message"], (fault["duration_s"] / 3600) if pd.notna(fault["duration_s"]) else None,
                    fault["iec_category"], sig,
                )
            )

    # --- negatives
    n_neg_target = int(round(len(records) * neg_ratio))
    if n_neg_target:
        rng = np.random.default_rng(seed)
        grid = channels.index[channels.index.minute == 0]
        grid = grid[(grid - channels.index[0]) >= pd.Timedelta(hours=WINDOW_HOURS)]
        order = rng.permutation(len(grid))
        n_neg = 0
        for i in order:
            if n_neg >= n_neg_target:
                break
            t = grid[i]
            state = _state(channels, t)
            if state in (None, "stopped"):
                continue
            if _first_fault_within(ev.any_fault, t, h_max) is not None:
                continue
            if _overlaps(ev.any_fault, t, t) or _overlaps(ev.manual, t - pd.Timedelta(hours=WINDOW_HOURS), t):
                continue
            if _overlaps(ev.stops, t - pd.Timedelta(hours=2), t):
                continue
            sig = _window(channels, t)
            if sig is None:
                continue
            h = horizons[n_neg % len(horizons)]
            fw = {f"{hh}h": "none" for hh in horizons}
            records.append(WindowRecord(turbine_id, farm, turbine, t, h, "none", False, state, fw, None, None, None, None, sig))
            n_neg += 1
    return records


def assign_split(farm: str, turbine: int, year: int) -> str:
    """docs/problem-statement.md §6: Penmanshiel 1–12 / 2017–19 train, 13–15 val, 2020–21 test_a; Kelmarsh test_b."""
    if farm == "kelmarsh":
        return "test_b"
    if year >= 2020:
        return "test_a"
    return "val" if turbine >= 13 else "train"


def records_to_frame(records: list[WindowRecord], year: int) -> pd.DataFrame:
    rows = []
    for r in records:
        row = {
            "window_id": f"{r.turbine_id}-{r.anchor.strftime('%Y%m%dT%H%M')}-h{r.horizon_h}",
            "farm": r.farm,
            "turbine": r.turbine,
            "turbine_id": r.turbine_id,
            "year": year,
            "anchor": r.anchor,
            "horizon_h": r.horizon_h,
            "label": r.label,
            "is_positive": r.is_positive,
            "state_at_anchor": r.state_at_anchor,
            "lead_time_min": r.lead_time_min,
            "next_event_message": r.next_event_message,
            "next_event_duration_h": r.next_event_duration_h,
            "next_event_iec": r.next_event_iec,
            "split": assign_split(r.farm, r.turbine, year),
        }
        row.update({f"fault_within_{k}": v for k, v in r.fault_within.items()})
        for j, name in enumerate(CHANNEL_NAMES):
            row[name] = r.signals[:, j].tolist()
        rows.append(row)
    return pd.DataFrame(rows)
