"""Paired bootstrap confidence intervals for the headline metrics on one split (docs/benchmark.md asks for these
before any positive claim about incremental value).

    uv run python scripts/bootstrap_ci.py --split test_b \\
        headline=docs/results/t1_flamingo_llama1b_evidence_rich/predictions.jsonl.gz \\
        xgb=docs/results/xgboost_sensors_only/../../..//outputs/xgb_sensors_only.jsonl ...

Resamples windows with replacement (B times, same draws for every model = paired), recomputes AUROC and recall at
10 % FAR, and reports each model's 95 % interval plus the paired difference vs the first model.
"""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

import numpy as np

from turbine_tslm.eval.score import auroc, load_labels, recall_at_far


def read_preds(path: str) -> dict[str, tuple[float, str]]:
    op = gzip.open if path.endswith(".gz") else open
    out = {}
    with op(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("task", "t1") != "t1":
                continue
            out[r["window_id"]] = (float(r["score"]), r.get("label", "none"))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "models", nargs="+", help="name=path (first = reference for paired differences)"
    )
    ap.add_argument("--split", default="test_b")
    ap.add_argument("--B", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out")
    a = ap.parse_args()
    labels = load_labels()
    labels = labels[(labels["split"] == a.split) & (labels["task"] == "t1")]
    names, preds = [], []
    for spec in a.models:
        n, p = spec.split("=", 1)
        names.append(n)
        preds.append(read_preds(p))
    ids = [w for w in labels["window_id"] if all(w in p for p in preds)]
    y = labels.set_index("window_id").loc[ids, "label"].ne("none").to_numpy()
    S = np.array([[p[w][0] for w in ids] for p in preds])  # (models, n)
    rng = np.random.default_rng(a.seed)
    n = len(ids)
    stats = {m: {"auroc": [], "r10": []} for m in names}
    for _ in range(a.B):
        idx = rng.integers(0, n, n)
        yb = y[idx]
        if yb.sum() == 0 or (~yb).sum() == 0:
            continue
        for m, s in zip(names, S, strict=True):
            sb = s[idx]
            stats[m]["auroc"].append(auroc(yb, sb))
            stats[m]["r10"].append(recall_at_far(yb, sb, 0.10)[0])
    res = {
        "split": a.split,
        "n_windows": n,
        "n_pos": int(y.sum()),
        "B": a.B,
        "models": {},
    }
    ref = names[0]
    for m in names:
        d = {}
        for k in ("auroc", "r10"):
            v = np.array(stats[m][k])
            point = (
                auroc(y, S[names.index(m)])
                if k == "auroc"
                else recall_at_far(y, S[names.index(m)], 0.10)[0]
            )
            d[k] = {
                "point": float(point),
                "ci95": [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))],
            }
            if m != ref:
                diff = v - np.array(stats[ref][k])
                d[k]["diff_vs_" + ref] = {
                    "mean": float(diff.mean()),
                    "ci95": [
                        float(np.percentile(diff, 2.5)),
                        float(np.percentile(diff, 97.5)),
                    ],
                    "p_better": float((diff > 0).mean()),
                }
        res["models"][m] = d
    for m, d in res["models"].items():
        line = f"{m:>12s}  AUROC {d['auroc']['point']:.3f} [{d['auroc']['ci95'][0]:.3f}, {d['auroc']['ci95'][1]:.3f}]  R@10%FAR {d['r10']['point']:.3f} [{d['r10']['ci95'][0]:.3f}, {d['r10']['ci95'][1]:.3f}]"
        if m != ref:
            dd = d["r10"]["diff_vs_" + ref]
            line += f"  ΔR@10 vs {ref} {dd['mean']:+.3f} [{dd['ci95'][0]:+.3f}, {dd['ci95'][1]:+.3f}] P(better)={dd['p_better']:.2f}"
        print(line)
    if a.out:
        Path(a.out).write_text(json.dumps(res, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
