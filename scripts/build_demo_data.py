"""Export a curated subset of held-out windows + the headline model's explanations for the demo page (webapp/).

    uv run python scripts/build_demo_data.py docs/results/t1_flamingo_llama1b_evidence_rich/predictions.jsonl.gz \\
        --n 160

Picks Kelmarsh (unseen farm) and 2020-21 Penmanshiel (unseen years) windows: correct positives with well-verified
claims, correct negatives, and a few honest misses; attaches per-claim verdicts (verified / wrong spans) for the
early-warning text and the post-hoc (T3) text, facts, the gold outcome (message, lead time) and the raw 24 h
channels (rounded).

Also writes webapp/data/results_summary.json (every run under docs/results/ + the XGBoost table in docs/benchmark.md),
so nothing on the Results tab is hand-typed.
"""

from __future__ import annotations

import argparse
import gzip
import json
import random
import re
from pathlib import Path

import numpy as np
import pandas as pd

from turbine_tslm.data.channels import CHANNEL_NAMES, CHANNELS
from turbine_tslm.data.evidence import extract_facts
from turbine_tslm.eval.faithfulness import claim_spans as _claim_spans
from turbine_tslm.eval.score import DEFAULT_WINDOWS

# human labels for the Results tab (naming only; every number comes from the run's results.json)
RUN_LABELS = {
    "t1_flamingo_llama1b": "Flamingo, label only",
    "t1_sp_llama1b": "SP + LoRA, label only",
    "t1_flamingo_llama1b_evidence": "Flamingo, reason-first",
    "t1_flamingo_llama1b_evidence_fixed": "Flamingo, reason-first, left-padded generation",
    "t1_flamingo_llama1b_evidence_rich": "Flamingo, reason-first + rich channel text",
    "t1_flamingo_llama1b_evidence_rich_rft": "Flamingo, reason-first + rich text + RFT",
    "xgboost_sensors_only": "XGBoost, 24 h sensor statistics",
    "xgboost_combined": "XGBoost, sensor statistics + context",
}
HEADLINE_RUN = "t1_flamingo_llama1b_evidence_rich"
# docs/results/bootstrap/test_b.json model keys -> run folder
BOOTSTRAP_KEYS = {
    "headline": "t1_flamingo_llama1b_evidence_rich",
    "xgb_sensors": "xgboost_sensors_only",
    "xgb_combined": "xgboost_combined",
    "flamingo_label": "t1_flamingo_llama1b",
    "sp_label": "t1_sp_llama1b",
    "evidence_basic": "t1_flamingo_llama1b_evidence_fixed",
}
BASELINE_ROWS = {  # row name in docs/benchmark.md -> label
    "context-only proxy": "XGBoost, context only (proxy)",
    "XGBoost sensors-only": "XGBoost, sensor statistics",
    "XGBoost combined": "XGBoost, sensors + context",
}

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


claim_spans = (
    _claim_spans  # kept for compatibility; implementation lives in eval.faithfulness
)


def _split_summary(block: dict) -> dict:
    hard = block.get("hard") or {}
    return {
        "n": block.get("n"),
        "n_pos": block.get("n_pos"),
        "auroc": block.get("auroc"),
        "ap": block.get("ap"),
        "recall_at_10far": block.get("recall_at_10far"),
        "recall_at_5far": block.get("recall_at_5far"),
        "hard_precision": hard.get("precision"),
        "hard_recall": hard.get("recall"),
        "hard_f1": hard.get("f1"),
        "hard_far": hard.get("far"),
        "subsystem_acc": (block.get("subsystem") or {}).get("accuracy_over_positives"),
        "subsystem_macro_f1": (block.get("subsystem") or {}).get(
            "macro_f1_over_positives"
        ),
        "per_class": {
            c: {
                "n": v.get("n"),
                "recall_at_10far": v.get("recall_at_10far"),
                "hard_recall": v.get("hard_recall"),
                "subsystem_acc": v.get("subsystem_acc"),
            }
            for c, v in (block.get("per_class") or {}).items()
        },
        "confusion": block.get("confusion"),
    }


def build_results_summary(results_dir: Path, benchmark_md: Path) -> dict:
    """Results tab data: every run with a results.json under docs/results/, plus the XGBoost rows of
    docs/benchmark.md ('First reproducible XGBoost run' table)."""
    runs = []
    order = list(
        RUN_LABELS
    )  # table order: RUN_LABELS first, unknown runs after, alphabetically
    dirs = sorted(
        results_dir.iterdir(),
        key=lambda d: (order.index(d.name) if d.name in order else len(order), d.name),
    )
    for d in dirs:
        rj = d / "results.json"
        if not rj.is_file():
            continue
        res = json.loads(rj.read_text(encoding="utf-8"))["results"]
        splits = {}
        for split in ("val", "test_a", "test_b"):
            if split not in res:
                continue
            block = res[split]
            summary = _split_summary(block["all"])
            summary["horizons"] = {
                h: {
                    k: block[h].get(k)
                    for k in (
                        "n",
                        "n_pos",
                        "auroc",
                        "recall_at_10far",
                        "recall_at_5far",
                    )
                }
                | {"hard_f1": (block[h].get("hard") or {}).get("f1")}
                for h in ("1", "3", "6")
                if h in block
            }
            t3 = res.get(f"t3/{split}")
            if t3:
                summary["t3"] = {
                    "n": t3["all"].get("n"),
                    "subsystem_acc": (t3["all"].get("subsystem") or {}).get(
                        "accuracy_over_positives"
                    ),
                    "per_class": {
                        c: {"n": v.get("n"), "subsystem_acc": v.get("subsystem_acc")}
                        for c, v in (t3["all"].get("per_class") or {}).items()
                    },
                }
            splits[split] = summary
        run = {
            "run": d.name,
            "label": RUN_LABELS.get(d.name, d.name),
            "kind": "xgboost" if d.name.startswith("xgboost") else "tslm",
            "headline": d.name == HEADLINE_RUN,
            "splits": splits,
        }
        fj = d / "faithfulness.json"
        if fj.is_file():
            fs = json.loads(fj.read_text(encoding="utf-8"))["summary"]
            run["faithfulness"] = {
                k: fs.get(k)
                for k in (
                    "n_texts",
                    "claims",
                    "claim_precision",
                    "texts_with_wrong_claim",
                    "claims_per_text",
                    "conclusion_consistent",
                )
            } | {
                "per_split": {
                    s: {
                        k: v.get(k)
                        for k in ("claim_precision", "texts_with_wrong_claim", "n")
                    }
                    for s, v in (fs.get("per_split") or {}).items()
                }
            }
        runs.append(run)

    baselines = []
    text = benchmark_md.read_text(encoding="utf-8") if benchmark_md.is_file() else ""
    for name, label in BASELINE_ROWS.items():
        m = re.search(
            rf"^\|\s*{re.escape(name)}\s*\|([^\n]*)$", text, flags=re.MULTILINE
        )
        if not m:
            continue
        cells = [c.strip() for c in m.group(1).strip().strip("|").split("|")]
        if len(cells) < 6:
            continue
        a_auroc, a_rec, a_f1, b_auroc, b_rec, b_f1 = (float(c) for c in cells[:6])
        baselines.append(
            {
                "label": label,
                "source": str(benchmark_md),
                "test_a": {
                    "auroc": a_auroc,
                    "recall_at_10far": a_rec,
                    "macro_f1": a_f1,
                },
                "test_b": {
                    "auroc": b_auroc,
                    "recall_at_10far": b_rec,
                    "macro_f1": b_f1,
                },
            }
        )
    bootstrap = None
    bj = results_dir / "bootstrap" / "test_b.json"
    if bj.is_file():
        raw = json.loads(bj.read_text(encoding="utf-8"))
        bootstrap = {
            "split": raw.get("split"),
            "n_windows": raw.get("n_windows"),
            "n_pos": raw.get("n_pos"),
            "B": raw.get("B"),
            "models": {
                BOOTSTRAP_KEYS.get(k, k): v for k, v in raw.get("models", {}).items()
            },
        }
    return {
        "runs": runs,
        "bootstrap": bootstrap,
        "floor": {
            "label": "always \u201cno\u201d",
            "auroc": 0.5,
            "recall_at_10far": 0.0,
        },
        "baselines": baselines,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("predictions")
    ap.add_argument("--out", default="webapp/data/demo_data.json")
    ap.add_argument("--n", type=int, default=160)
    ap.add_argument("--windows", nargs="+", default=list(DEFAULT_WINDOWS))
    ap.add_argument("--results-dir", default="docs/results")
    ap.add_argument("--benchmark", default="docs/benchmark.md")
    ap.add_argument("--results-out", default="webapp/data/results_summary.json")
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
        # offsets index the stripped text, which is what gets written out
        spans = claim_spans(p["text"].strip(), facts)
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
                "t3_claims": (
                    claim_spans(t3[wid]["text"].strip(), facts) if wid in t3 else None
                ),
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
    summary = build_results_summary(Path(a.results_dir), Path(a.benchmark))
    Path(a.results_out).write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(
        f"wrote {a.results_out}: {len(summary['runs'])} runs, {len(summary['baselines'])} baselines"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
