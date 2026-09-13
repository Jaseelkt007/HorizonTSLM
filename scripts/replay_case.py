"""Replay one turbine-day through the whole pipeline for the demo: hourly anchors up to a stop (or a quiet end),
raw SCADA -> 24 h window -> prompt -> headline model -> explanation + subsystem + P(fault stop within 1/3/6 h) ->
every number checked against the window -> the log line at the end.

Runs where the raw zips are (the VM):
    DATA_DIR=~/data uv run python scripts/replay_case.py configs/t1_flamingo_llama1b_evidence_rich.yaml \\
        --checkpoint ~/data/checkpoints/t1_flamingo_llama1b_evidence_rich/best.pt \\
        --farm kelmarsh --turbine 1 --end "2019-03-15 12:13" --hours-before 12 --name tower_oscillation_2019 \\
        --out webapp/replay_tower_oscillation_2019.json

Kelmarsh is entirely held out and hourly anchors are never training records, so this stays leakage-free.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from turbine_tslm.connectors.cubico.base import data_dir
from turbine_tslm.data.channels import (
    CHANNEL_NAMES,
    CHANNELS,
    STEP_MINUTES,
    extract_channels,
)
from turbine_tslm.data.evidence import extract_facts
from turbine_tslm.data.greenbyte import iter_turbine_years
from turbine_tslm.data.prompts import POST_PROMPT, pre_prompt, t3_pre_prompt
from turbine_tslm.data.taxonomy import classify, fault_classes
from turbine_tslm.data.windows import _state, _window, split_events
from turbine_tslm.eval.faithfulness import claim_spans
from turbine_tslm.eval.score import parse_answer
from turbine_tslm.training import train as T
from turbine_tslm.training.turbine_dataset import channel_prompts


def make_sample(series, farm, turbine_id, anchor, state, task, horizon, series_stats):
    prompts = channel_prompts(series, series_stats)
    month = anchor.strftime("%B")
    pre = (
        t3_pre_prompt(farm, turbine_id, month)
        if task == "t3"
        else pre_prompt(farm, turbine_id, month, state, horizon)
    )
    return {
        "pre_prompt": pre,
        "time_series": [p.get_time_series() for p in prompts],
        "time_series_text": [p.get_text() for p in prompts],
        "post_prompt": POST_PROMPT,
        "answer": "",
        "window_id": f"{turbine_id}-{anchor.strftime('%Y%m%dT%H%M')}-{'t3' if task == 't3' else f'h{horizon}'}",
        "task": task,
        "split": "replay",
        "horizon_h": horizon,
        "label": "?",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("config")
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--farm", required=True)
    ap.add_argument("--turbine", type=int, required=True)
    ap.add_argument(
        "--end",
        required=True,
        help="UTC time of the stop (or the end of a quiet replay)",
    )
    ap.add_argument("--hours-before", type=int, default=12)
    ap.add_argument("--step-hours", type=float, default=1.0)
    ap.add_argument("--name", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--set", action="append", default=[], metavar="KEY=VALUE")
    a = ap.parse_args()

    cfg = T.load_config(a.config, a.set)
    cfg["wandb_project"] = None
    end = pd.Timestamp(a.end, tz="UTC")
    year = end.year
    ty = next(
        t
        for t in iter_turbine_years(data_dir() / "raw", a.farm)
        if t.turbine == a.turbine and t.year == year
    )
    scada, status = ty.load()
    channels = extract_channels(scada)
    ev = split_events(status)
    turbine_id = f"{a.farm}-{a.turbine:02d}"

    # the log around the end: the first fault-class stop at/after `end` within 2 h (None for a quiet replay)
    after = ev.faults[
        (ev.faults["start"] >= end - pd.Timedelta(minutes=STEP_MINUTES))
        & (ev.faults["start"] <= end + pd.Timedelta(hours=2))
    ]
    stop = None if after.empty else after.iloc[0]
    log_rows = status[
        (status["start"] >= end - pd.Timedelta(hours=a.hours_before + 24))
        & (status["start"] <= end + pd.Timedelta(hours=3))
    ]
    log_rows = [
        {
            "start": r["start"].isoformat(),
            "end": None if pd.isna(r["end"]) else r["end"].isoformat(),
            "status": r["status"],
            "message": r["message"],
            "iec": r["iec_category"],
            "class": classify(r["message"])[0],
        }
        for _, r in log_rows.iterrows()
    ]

    model = T.build_model(cfg)
    T.load_checkpoint(model, Path(a.checkpoint))
    if cfg["predict_dtype"] and cfg["model_type"] == "OpenTSLMFlamingo":
        model.to(getattr(torch, cfg["predict_dtype"]))
    model.eval()
    from opentslm.model_config import PATCH_SIZE
    from opentslm.time_series_datasets.util import (
        extend_time_series_to_match_patch_size_and_aggregate,
    )

    def collate(batch):
        return extend_time_series_to_match_patch_size_and_aggregate(
            [dict(b) for b in batch], patch_size=PATCH_SIZE
        )

    classes = fault_classes()
    concl_cands, concl_flags = T.conclusion_candidates(model, classes)
    flags_t = torch.tensor(concl_flags, dtype=torch.bool)

    anchors = [
        end - pd.Timedelta(hours=h)
        for h in np.arange(a.hours_before, -1e-9, -a.step_hours)
    ]
    steps = []
    for t in anchors:
        t = t.floor(f"{STEP_MINUTES}min")
        sig = _window(channels, t)
        state = _state(channels, t)
        if sig is None or state is None:
            steps.append({"anchor": t.isoformat(), "skipped": "incomplete window"})
            continue
        series = {c: sig[:, j].astype(np.float32) for j, c in enumerate(CHANNEL_NAMES)}
        facts = extract_facts(series)
        rec = {
            "anchor": t.isoformat(),
            "hours_to_end": round((end - t).total_seconds() / 3600, 2),
            "state": state,
            "answers": {},
        }
        tasks = [("t1", h) for h in (1, 3, 6)]
        if t == anchors[-1].floor(f"{STEP_MINUTES}min") or (end - t) <= pd.Timedelta(
            hours=1, minutes=10
        ):
            tasks.append(("t3", 1))
        for task, h in tasks:
            s = make_sample(
                series, a.farm, turbine_id, t, state, task, h, cfg["series_stats"]
            )
            with T.autocast(cfg):
                text = T.generate_texts(model, collate([s]), cfg["max_new_tokens"])[
                    0
                ].strip()
            out = {
                "text": text,
                "label": parse_answer(text),
                "claims": claim_spans(text, facts),
            }
            if task == "t1":
                prefix = T.evidence_without_conclusion(text)
                ll = T.score_candidates(cfg, model, [s], concl_cands, collate, [prefix])
                p = torch.softmax(ll, dim=1)[0]
                per_class = {
                    c: float(p[2 + 2 * k] + p[3 + 2 * k]) for k, c in enumerate(classes)
                }
                tot = max(sum(per_class.values()), 1e-12)
                out["p_fault"] = float(p[flags_t].sum())
                out["class_scores"] = {c: v / tot for c, v in per_class.items()}
            rec["answers"][f"{task}_h{h}" if task == "t1" else "t3"] = out
        rec["channels"] = {
            c: [round(float(v), 2) for v in series[c]] for c in CHANNEL_NAMES
        }
        rec["facts"] = {
            k: (
                round(float(v), 2)
                if isinstance(v, (int, float, np.floating)) and np.isfinite(v)
                else v
            )
            for k, v in facts.items()
            if k != "excursions"
        }
        steps.append(rec)
        print(
            f"[replay] {t} ({rec['hours_to_end']:.0f} h before end): "
            + ", ".join(
                f"{k}={v.get('p_fault', float('nan')):.2f}"
                for k, v in rec["answers"].items()
                if k.startswith("t1")
            ),
            flush=True,
        )

    case = {
        "name": a.name,
        "farm": a.farm,
        "turbine": a.turbine,
        "end": end.isoformat(),
        "stop": None
        if stop is None
        else {
            "start": stop["start"].isoformat(),
            "message": stop["message"],
            "class": stop["cls"],
            "duration_h": None
            if pd.isna(stop["duration_s"])
            else round(float(stop["duration_s"]) / 3600, 2),
            "iec": stop["iec_category"],
        },
        "log": log_rows,
        "model": cfg["run_name"],
        "channels": [
            {"name": c.name, "label": c.description, "unit": c.unit_text}
            for c in CHANNELS
        ],
        "steps": steps,
    }
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(case, separators=(",", ":")), encoding="utf-8")
    print(
        f"wrote {a.out} ({len(steps)} steps, stop={'none' if stop is None else stop['message']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
