"""Trivial reference predictors (docs/problem-statement.md §9: "always no") in the shared predictions.jsonl format.

    uv run python -m turbine_tslm.eval.baselines always_no --out outputs/always_no.jsonl
    uv run python -m turbine_tslm.eval.baselines random   --out outputs/random.jsonl --seed 0

They exist to check the harness (always-no must give AUROC 0.5 / recall 0; random must give AUROC ≈ 0.5) and as the
floor every real model is compared against. GBM / LLM baselines live with their owner and write the same format.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from turbine_tslm.data.taxonomy import fault_classes
from turbine_tslm.eval.score import DEFAULT_WINDOWS, NONE, load_labels


def always_no(labels: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({"window_id": labels["window_id"], "score": 0.0, "label": NONE})


def random_prior(labels: pd.DataFrame, seed: int = 0) -> pd.DataFrame:
    """Uniform random score; label = a random fault class when score > 0.5, else none."""
    rng = np.random.default_rng(seed)
    classes = list(fault_classes())
    s = rng.random(len(labels))
    lab = np.where(s > 0.5, rng.choice(classes, size=len(labels)), NONE)
    return pd.DataFrame({"window_id": labels["window_id"], "score": s, "label": lab})


def write_predictions(df: pd.DataFrame, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.writelines(
            json.dumps(
                {
                    k: (float(v) if isinstance(v, (np.floating, float)) else v)
                    for k, v in rec.items()
                }
            )
            + "\n"
            for rec in df.to_dict(orient="records")
        )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=["always_no", "random"])
    ap.add_argument("--windows", nargs="+", default=list(DEFAULT_WINDOWS))
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args(argv)
    labels = load_labels(args.windows)
    df = (
        always_no(labels)
        if args.kind == "always_no"
        else random_prior(labels, args.seed)
    )
    write_predictions(df, args.out)
    print(f"wrote {len(df)} predictions to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
