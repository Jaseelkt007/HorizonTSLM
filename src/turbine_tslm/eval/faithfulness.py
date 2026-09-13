"""Check generated evidence text against the numbers in the window (the "judge" from the mentor session, rule-based).

Every sentence template in ``data/evidence.py`` carries numbers that can be recomputed from the raw window. This
module parses those claims out of a generated paragraph, recomputes the facts, and reports how many claims are
verified, wrong, or unparseable, plus whether the conclusion sentence agrees with the ``Answer:`` line.

    uv run python -m turbine_tslm.eval.faithfulness outputs/<run>/predictions.jsonl [--windows ...] [--out f.json]

Tolerances are deliberately loose (a generated number within the rounding + a few units counts): the question is
"did the model make things up", not "did it copy the template to the decimal".
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from turbine_tslm.data.channels import CHANNEL_NAMES
from turbine_tslm.data.evidence import CONCLUSION, THERMAL, extract_facts
from turbine_tslm.eval.score import DEFAULT_WINDOWS, NONE, parse_answer

THERMAL_BY_LABEL = {label: name for name, label in THERMAL.items()}
CONCLUSION_CLASS = {sent: cls for cls, sent in CONCLUSION.items()}

# (regex, checker(match, facts) -> bool). Each checker returns True if the claim matches the window.
_RULES: list[tuple[re.Pattern[str], Any]] = [
    (
        re.compile(
            r"(generator front bearing|generator rear bearing|stator|gear oil|main bearing) temperature rose (\d+) °C in the last 6 h to (\d+) °C",
            re.IGNORECASE,
        ),
        lambda m, f: (
            abs(
                f[f"{THERMAL_BY_LABEL[m.group(1).lower()]}_delta6h"] - float(m.group(2))
            )
            <= 2.5
            and abs(
                f[f"{THERMAL_BY_LABEL[m.group(1).lower()]}_now"] - float(m.group(3))
            )
            <= 2.5
        ),
    ),
    (
        re.compile(r"producing about (\d+) kW", re.IGNORECASE),
        lambda m, f: (
            abs(f["power_last1h"] - float(m.group(1)))
            <= max(60, 0.15 * f["power_last1h"])
        ),
    ),
    (
        re.compile(r"Wind (rose|fell) from (\d+) to (\d+) m/s", re.IGNORECASE),
        lambda m, f: (
            abs(f["wind_first6h"] - float(m.group(2))) <= 1.5
            and abs(f["wind_last6h"] - float(m.group(3))) <= 1.5
        ),
    ),
    (
        re.compile(r"Wind is steady around (\d+) m/s", re.IGNORECASE),
        lambda m, f: abs(f["wind_mean"] - float(m.group(1))) <= 1.5,
    ),
    (
        re.compile(r"Wind is (\d+) m/s in the last hour", re.IGNORECASE),
        lambda m, f: abs(f["wind_last1h"] - float(m.group(1))) <= 1.5,
    ),
    (
        re.compile(r"(\d+) °C hotter than the other side", re.IGNORECASE),
        lambda m, f: abs(abs(f["bearing_asym_now"]) - float(m.group(1))) <= 2.5,
    ),
    (
        re.compile(r"Tower acceleration X is (\d+) mm/s²", re.IGNORECASE),
        lambda m, f: (
            abs(f["tower_acc_last1h"] - float(m.group(1)))
            <= max(3, 0.2 * f["tower_acc_last1h"])
        ),
    ),
    (
        re.compile(r"([\d.]+)× its 24 h median", re.IGNORECASE),
        lambda m, f: (
            np.isfinite(f["tower_acc_ratio"])
            and abs(f["tower_acc_ratio"] - float(m.group(1))) <= 0.6
        ),
    ),
    (
        re.compile(r"Gear oil inlet pressure fell (\d+) % over 6 h", re.IGNORECASE),
        lambda m, f: (
            f["oil_pressure_6h_ago"] > 0
            and abs(
                (f["oil_pressure_6h_ago"] - f["oil_pressure_now"])
                / f["oil_pressure_6h_ago"]
                * 100
                - float(m.group(1))
            )
            <= 10
        ),
    ),
    (
        re.compile(r"Grid voltage stepped by (\d+) V", re.IGNORECASE),
        lambda m, f: abs(f["grid_voltage_max_step"] - float(m.group(1))) <= 3,
    ),
    (
        re.compile(r"Grid frequency deviated up to ([\d.]+) Hz", re.IGNORECASE),
        lambda m, f: abs(f["grid_freq_max_dev"] - float(m.group(1))) <= 0.05,
    ),
    (
        re.compile(r"Nacelle is (\d+)° off the wind direction", re.IGNORECASE),
        lambda m, f: abs(abs(f["yaw_misalignment_last1h"]) - float(m.group(1))) <= 6,
    ),
    (
        re.compile(r"rotor at ([\d.]+) rpm", re.IGNORECASE),
        lambda m, f: abs(f["rotor_rpm_last1h"] - float(m.group(1))) <= 1.0,
    ),
    (
        re.compile(r"power at (\d+) kW", re.IGNORECASE),
        lambda m, f: (
            abs(f["power_last1h"] - float(m.group(1)))
            <= max(60, 0.15 * f["power_last1h"])
        ),
    ),
    (
        re.compile(r"Blades are feathered at (\d+)°", re.IGNORECASE),
        lambda m, f: abs(f["pitch_last1h"] - float(m.group(1))) <= 8,
    ),
    (
        re.compile(r"Power is (\d+) kW below the farm power curve", re.IGNORECASE),
        lambda m, f: (
            abs(-f["residual_last3h"] - float(m.group(1)))
            <= max(50, 0.2 * abs(f["residual_last3h"]))
        ),
    ),
]
_NUMBER = re.compile(r"\d")


def check_text(text: str, series: dict[str, np.ndarray]) -> dict[str, Any]:
    """Verify one generated paragraph against its window."""
    facts = extract_facts(series)
    body = text.split("Answer")[0] if "Answer" in text else text
    verified, wrong, matched_spans = 0, 0, []
    for pat, ok in _RULES:
        for m in pat.finditer(body):
            matched_spans.append(m.span())
            try:
                good = bool(ok(m, facts))
            except (KeyError, ValueError, TypeError):
                good = False
            verified += good
            wrong += not good
    # numeric sentences that no rule recognises = unverifiable claims
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", body) if s.strip()]
    unverifiable = 0
    for s in sentences:
        if _NUMBER.search(s) and not any(pat.search(s) for pat, _ in _RULES):
            unverifiable += 1
    answer = parse_answer(text)
    concl = next((cls for sent, cls in CONCLUSION_CLASS.items() if sent in body), None)
    if concl is None and (
        "No sign of a developing fault" in body or "Nothing here points" in body
    ):
        concl = NONE
    consistent = None if concl is None else (concl == answer)
    return {
        "n_claims": verified + wrong,
        "verified": verified,
        "wrong": wrong,
        "unverifiable": unverifiable,
        "answer": answer,
        "conclusion": concl,
        "conclusion_consistent": consistent,
    }


def load_series(
    paths: list[str], window_ids: set[str]
) -> dict[str, dict[str, np.ndarray]]:
    out: dict[str, dict[str, np.ndarray]] = {}
    for p in paths:
        df = pd.read_parquet(p, columns=["window_id", *CHANNEL_NAMES])
        df = df[df.window_id.isin(window_ids)]
        for row in df.itertuples(index=False):
            out[row.window_id] = {
                c: np.asarray(getattr(row, c), dtype=np.float32) for c in CHANNEL_NAMES
            }
    return out


def evaluate(pred_path: str | Path, windows: list[str] | None = None) -> dict[str, Any]:
    windows = windows or list(DEFAULT_WINDOWS)
    rows = [
        json.loads(line)
        for line in Path(pred_path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    rows = [r for r in rows if r.get("text")]
    base = {
        r["window_id"]: r["window_id"].split("#")[0] for r in rows
    }  # t3 ids = window id + "#t3"
    series = load_series(windows, set(base.values()))
    per: list[dict[str, Any]] = []
    for r in rows:
        if base[r["window_id"]] not in series:
            continue
        c = check_text(r["text"], series[base[r["window_id"]]])
        c["window_id"], c["split"], c["gold"] = (
            r["window_id"],
            r.get("split"),
            r.get("gold"),
        )
        per.append(c)
    df = pd.DataFrame(per)
    summary: dict[str, Any] = {"n_texts": len(df)}
    if len(df):
        claims = int(df.n_claims.sum())
        summary.update(
            {
                "claims": claims,
                "claim_precision": float(df.verified.sum() / claims)
                if claims
                else float("nan"),
                "texts_with_wrong_claim": float((df.wrong > 0).mean()),
                "texts_with_unverifiable_numbers": float((df.unverifiable > 0).mean()),
                "claims_per_text": float(df.n_claims.mean()),
                "conclusion_present": float(df.conclusion.notna().mean()),
                "conclusion_consistent": float(df.conclusion_consistent.dropna().mean())
                if df.conclusion_consistent.notna().any()
                else float("nan"),
                "per_split": {
                    str(k): {
                        "claim_precision": float(g.verified.sum() / g.n_claims.sum())
                        if g.n_claims.sum()
                        else float("nan"),
                        "texts_with_wrong_claim": float((g.wrong > 0).mean()),
                        "conclusion_consistent": float(
                            g.conclusion_consistent.dropna().mean()
                        )
                        if g.conclusion_consistent.notna().any()
                        else float("nan"),
                        "n": len(g),
                    }
                    for k, g in df.groupby("split")
                },
            }
        )
    return {"summary": summary, "per_text": per}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("predictions")
    ap.add_argument("--windows", nargs="+", default=list(DEFAULT_WINDOWS))
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    res = evaluate(a.predictions, a.windows)
    print(json.dumps(res["summary"], indent=1))
    if a.out:
        Path(a.out).write_text(json.dumps(res, indent=1), encoding="utf-8")
        print(f"wrote {a.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
