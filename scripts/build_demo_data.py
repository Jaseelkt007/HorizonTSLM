"""Export a curated subset of held-out windows + the headline model's explanations for the demo page (webapp/).

    uv run python scripts/build_demo_data.py docs/results/t1_flamingo_llama1b_evidence_rich/predictions.jsonl.gz \\
        --out webapp/demo_data.json --n 160

Picks Kelmarsh (unseen farm) and 2020-21 Penmanshiel (unseen years) windows: correct positives with well-verified
claims, correct negatives, and a few honest misses; attaches per-claim verdicts (verified / wrong spans), facts,
the gold outcome (message, lead time) and the raw 24 h channels (rounded).
"""

from __future__ import annotations

import argparse
import gzip
import json
import random
from pathlib import Path

import numpy as np
import pandas as pd

from turbine_tslm.data.channels import CHANNEL_NAMES, CHANNELS
from turbine_tslm.data.evidence import extract_facts
from turbine_tslm.eval.faithfulness import _RULES
from turbine_tslm.eval.score import DEFAULT_WINDOWS

META = [
    "window_id",
    "farm",
    "turbine",
    "anchor",
    "horizon_h",
    "label",
    "split",
    "state_at_anchor",
    "lead_time_min",
    "next_event_message",
    "next_event_duration_h",
]


def claim_spans(text: str, facts: dict) -> list[dict]:
    body = text.split("Answer")[0] if "Answer" in text else text
    out = []
    for pat, ok in _RULES:
        for m in pat.finditer(body):
            try:
                good = bool(ok(m, facts))
            except Exception:  # noqa: BLE001
                good = False
            out.append({"start": m.start(), "end": m.end(), "ok": good})
    out.sort(key=lambda d: d["start"])
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("predictions")
    ap.add_argument("--out", default="webapp/demo_data.json")
    ap.add_argument("--n", type=int, default=160)
    ap.add_argument("--windows", nargs="+", default=list(DEFAULT_WINDOWS))
    a = ap.parse_args()
    opener = gzip.open if a.predictions.endswith(".gz") else open
    with opener(a.predictions, "rt", encoding="utf-8") as fh:
        preds = [json.loads(line) for line in fh if line.strip()]
    t1 = {
        p["window_id"]: p
        for p in preds
        if p.get("task", "t1") == "t1" and p["split"] in ("test_a", "test_b")
    }
    t3 = {p["window_id"].split("#")[0]: p for p in preds if p.get("task") == "t3"}
    frames = [pd.read_parquet(p) for p in a.windows]
    df = pd.concat(frames, ignore_index=True)
    df = df[df.window_id.isin(t1)].set_index("window_id")

    # facts + verdicts for every candidate, then curate
    rows = []
    for wid, p in t1.items():
        r = df.loc[wid]
        series = {c: np.asarray(r[c], dtype=np.float32) for c in CHANNEL_NAMES}
        facts = extract_facts(series)
        spans = claim_spans(p["text"], facts)
        n_ok = sum(s["ok"] for s in spans)
        rows.append((wid, p, r, series, facts, spans, n_ok, len(spans)))
    rng = random.Random(0)

    def pick(cond, k, key=None):
        cands = [x for x in rows if cond(x)]
        if key:
            cands.sort(key=key, reverse=True)
            return cands[:k]
        rng.shuffle(cands)
        return cands[:k]

    def correct(x):
        return x[1]["label"] == x[1]["gold"]

    chosen = []
    chosen += pick(
        lambda x: x[2]["split"] == "test_b" and x[1]["gold"] != "none" and correct(x),
        a.n * 3 // 10,
        key=lambda x: (x[6] - (x[7] - x[6]), x[6]),
    )
    chosen += pick(
        lambda x: x[2]["split"] == "test_a" and x[1]["gold"] != "none" and correct(x),
        a.n * 2 // 10,
        key=lambda x: (x[6] - (x[7] - x[6]), x[6]),
    )
    chosen += pick(lambda x: x[1]["gold"] == "none" and correct(x), a.n * 3 // 10)
    chosen += pick(lambda x: not correct(x), a.n * 2 // 10)
    seen, out = set(), []
    for wid, p, r, series, facts, spans, n_ok, n in chosen:
        if wid in seen:
            continue
        seen.add(wid)
        out.append(
            {
                "id": wid,
                "farm": r["farm"],
                "turbine": int(r["turbine"]),
                "anchor": pd.Timestamp(r["anchor"]).strftime("%Y-%m-%d %H:%M"),
                "horizon_h": int(r["horizon_h"]),
                "split": r["split"],
                "state": r["state_at_anchor"],
                "gold": p["gold"],
                "pred": p["label"],
                "score": round(float(p["score"]), 3),
                "class_scores": {
                    k: round(v, 3) for k, v in (p.get("class_scores") or {}).items()
                },
                "text": p["text"].strip(),
                "claims": spans,
                "t3_text": (t3[wid]["text"].strip() if wid in t3 else None),
                "outcome": {
                    "message": None
                    if pd.isna(r["next_event_message"])
                    else r["next_event_message"],
                    "lead_time_min": None
                    if pd.isna(r["lead_time_min"])
                    else round(float(r["lead_time_min"])),
                    "duration_h": None
                    if pd.isna(r["next_event_duration_h"])
                    else round(float(r["next_event_duration_h"]), 1),
                },
                "facts": {
                    k: (
                        round(float(v), 2)
                        if isinstance(v, (int, float, np.floating)) and np.isfinite(v)
                        else v
                    )
                    for k, v in facts.items()
                    if k != "excursions"
                },
                "channels": {
                    c: [round(float(v), 2) for v in series[c]] for c in CHANNEL_NAMES
                },
            }
        )
    meta = {
        "channels": [
            {"name": c.name, "label": c.description, "unit": c.unit_text}
            for c in CHANNELS
        ],
        "model": "t1_flamingo_llama1b_evidence_rich",
        "n": len(out),
    }
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(
        json.dumps({"meta": meta, "windows": out}, separators=(",", ":")),
        encoding="utf-8",
    )
    print(
        f"wrote {a.out}: {len(out)} windows, {Path(a.out).stat().st_size / 1e6:.1f} MB"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
