"""Score a ``predictions.jsonl`` against the window tables (docs/problem-statement.md §9).

Every model — OpenTSLM, GBM, text-only LLM, "always no" — writes the same file and is scored by this module, so all
numbers on the slide come from identical records and identical code.

predictions.jsonl — one JSON object per line
--------------------------------------------
    {"window_id": "penmanshiel-7-20180808T0550-h6", "score": 0.83, "label": "generator_cooling"}
    {"window_id": "penmanshiel-7-20180809T1200-h3", "score": 0.04, "label": "none"}
    {"window_id": "kelmarsh-1-20190101T0000-h1", "text": "...evidence...\\nAnswer: yes, pitch_system"}

- ``window_id``  required; must exist in one of the window tables. Windows without a prediction are reported as
                 missing and skipped (a model is scored on what it predicted, and the count is printed).
- ``score``      P(fault-class stop begins within the window's horizon); higher = more likely. Used for AUROC and
                 recall at fixed false-alarm rate. Optional: if absent it is derived from the label (1.0 / 0.0),
                 which makes the ranking metrics degenerate — fine for "always no", not for a real model.
- ``label``      predicted subsystem class or ``"none"``. Optional if ``text`` is given.
- ``text``       the generated answer; the label is parsed from its last ``Answer:`` line (``parse_answer``).
                 Kept so evidence text can be inspected / scored later.
- ``class_scores`` optional ``{class: prob}``; if given and ``label`` is absent, label = argmax.

Metrics, per split and per horizon (plus horizons pooled)
---------------------------------------------------------
- binary: n, positives, AUROC, average precision, recall at 10 % false-alarm rate (and at 5 %), precision /
  recall / F1 of the hard label (``label != none``).
- per true class: recall at 10 % FAR (threshold is the global one on negatives of that split × horizon), n.
- subsystem: macro-F1 over the fault classes present in the truth, restricted to true positives (the "which
  subsystem" question, independent of the yes/no), plus a confusion matrix over classes ∪ {none}.

CLI
---
    uv run python -m turbine_tslm.eval.score predictions.jsonl [--windows a.parquet b.parquet] [--out results.json]
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

from turbine_tslm.data.taxonomy import fault_classes

NONE = "none"
LABEL_COLUMNS = [
    "window_id",
    "farm",
    "split",
    "horizon_h",
    "label",
    "is_positive",
    "state_at_anchor",
]
DEFAULT_WINDOWS = (
    "data/interim/penmanshiel_windows.parquet",
    "data/interim/kelmarsh_windows.parquet",
)
FAR_LEVELS = (0.10, 0.05)
_ANSWER_RE = re.compile(r"answer\s*:\s*(.*)", re.IGNORECASE)


# --------------------------------------------------------------------------------------------- parsing


def parse_answer(text: str, classes: tuple[str, ...] | None = None) -> str:
    """Label from generated text: the last ``Answer:`` line -> ``none`` or a class name.

    Accepts ``Answer: no``, ``Answer: yes, generator_cooling``, ``Answer: generator_cooling``; case-insensitive,
    tolerant of trailing punctuation. Anything that does not resolve to a known class is ``none`` (a malformed
    answer counts as a miss, never as a lucky hit).
    """
    classes = classes or fault_classes()
    matches = _ANSWER_RE.findall(text or "")
    if not matches:
        # the prompt already ends in 'Answer: ', so a model may emit just ': no' / 'yes, <class>'
        head = re.sub(r"^\s*:?\s*", "", (text or "").strip().split("\n")[0])
        if not re.match(r"(yes|no)\b", head, re.IGNORECASE):
            return NONE
        matches = [head]
    tail = matches[-1].strip().lower()
    tail = re.split(r"[\n]", tail)[0]
    if tail.startswith("no"):
        return NONE
    tail = re.sub(r"^yes\s*[,:\-]?\s*", "", tail)
    tail = re.sub(r"[^a-z_]+$", "", tail).strip()
    for cls in classes:
        if tail == cls or tail.startswith(cls):
            return cls
    return NONE


def load_predictions(
    path: str | Path, classes: tuple[str, ...] | None = None
) -> pd.DataFrame:
    """Read predictions.jsonl -> frame with ``window_id, pred_label, score`` (label resolved from text/class_scores)."""
    classes = classes or fault_classes()
    rows: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as fh:
        for ln, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"{path}:{ln}: not JSON ({e})") from e
            if "window_id" not in obj:
                raise ValueError(f"{path}:{ln}: missing window_id")
            rows.append(_normalise(obj, classes))
    df = pd.DataFrame(rows, columns=["window_id", "pred_label", "score", "text"])
    if df["window_id"].duplicated().any():
        dup = df.loc[df["window_id"].duplicated(), "window_id"].iloc[0]
        raise ValueError(f"{path}: duplicate window_id {dup!r}")
    return df


def _normalise(obj: dict[str, Any], classes: tuple[str, ...]) -> dict[str, Any]:
    label = obj.get("label")
    if label is None and obj.get("class_scores"):
        label = max(obj["class_scores"].items(), key=lambda kv: kv[1])[0]
    if label is None and "text" in obj:
        label = parse_answer(obj["text"], classes)
    if label is None:
        raise ValueError(
            f"window {obj['window_id']}: need one of label / text / class_scores"
        )
    label = str(label).strip().lower()
    if label in ("no", "", "null"):
        label = NONE
    if label != NONE and label not in classes:
        label = NONE  # unknown class name is a miss, not an error
    score = obj.get("score")
    if score is None:
        score = 0.0 if label == NONE else 1.0
    return {
        "window_id": obj["window_id"],
        "pred_label": label,
        "score": float(score),
        "text": obj.get("text"),
    }


def load_labels(
    paths: tuple[str, ...] | list[str] = DEFAULT_WINDOWS,
    tasks: tuple[str, ...] = ("t1",),
) -> pd.DataFrame:
    """Only the label columns of the window tables (the 19 list columns are not read).

    ``tasks``: ``t1`` = the windows as built; ``t3`` = post-hoc records derived from the 1 h positives (ids get a
    ``#t3`` suffix, matching ``training.turbine_dataset.t3_rows``). The returned frame has a ``task`` column.
    """
    frames = [pd.read_parquet(p, columns=LABEL_COLUMNS) for p in paths]
    df = pd.concat(frames, ignore_index=True)
    df["label"] = df["label"].astype(str)
    df["task"] = "t1"
    parts = []
    if "t1" in tasks:
        parts.append(df)
    if "t3" in tasks:
        t3 = df[(df["label"] != NONE) & (df["horizon_h"] == 1)].copy()
        t3["window_id"] = t3["window_id"] + "#t3"
        t3["task"] = "t3"
        parts.append(t3)
    return pd.concat(parts, ignore_index=True)


# --------------------------------------------------------------------------------------------- metrics


def auroc(y: np.ndarray, s: np.ndarray) -> float:
    """Rank-based AUROC (Mann–Whitney), ties count half. NaN if one class is absent."""
    y = np.asarray(y, bool)
    s = np.asarray(s, float)
    n_pos, n_neg = int(y.sum()), int((~y).sum())
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    ranks = pd.Series(s).rank(method="average").to_numpy()
    return float((ranks[y].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def average_precision(y: np.ndarray, s: np.ndarray) -> float:
    y = np.asarray(y, bool)
    s = np.asarray(s, float)
    if y.sum() == 0:
        return float("nan")
    order = np.argsort(-s, kind="stable")
    y = y[order]
    tp = np.cumsum(y)
    precision = tp / np.arange(1, len(y) + 1)
    return float((precision * y).sum() / y.sum())


def far_threshold(neg_scores: np.ndarray, far: float) -> float:
    """Score above which at most ``far`` of negatives fall (false-alarm rate on the negatives)."""
    neg = np.sort(np.asarray(neg_scores, float))
    if len(neg) == 0:
        return float("nan")
    return float(np.quantile(neg, 1 - far, method="higher"))


def recall_at_far(y: np.ndarray, s: np.ndarray, far: float) -> tuple[float, float]:
    """(recall of positives with score > threshold, threshold). Strict '>' keeps the realised FAR ≤ far."""
    y = np.asarray(y, bool)
    s = np.asarray(s, float)
    if y.sum() == 0 or (~y).sum() == 0:
        return float("nan"), float("nan")
    thr = far_threshold(s[~y], far)
    return float((s[y] > thr).mean()), thr


def prf(y_true: np.ndarray, y_pred: np.ndarray) -> tuple[float, float, float]:
    tp = int((y_true & y_pred).sum())
    fp = int((~y_true & y_pred).sum())
    fn = int((y_true & ~y_pred).sum())
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f


def macro_f1(
    true_labels: pd.Series, pred_labels: pd.Series, classes: list[str]
) -> tuple[float, dict[str, float]]:
    per: dict[str, float] = {}
    for c in classes:
        _, _, f = prf((true_labels == c).to_numpy(), (pred_labels == c).to_numpy())
        per[c] = f
    return (float(np.mean(list(per.values()))) if per else float("nan")), per


def confusion(
    true_labels: pd.Series, pred_labels: pd.Series, classes: list[str]
) -> pd.DataFrame:
    return pd.crosstab(
        pd.Categorical(true_labels, categories=classes),
        pd.Categorical(pred_labels, categories=classes),
        rownames=["true"],
        colnames=["pred"],
        dropna=False,
    )


# --------------------------------------------------------------------------------------------- scoring


def score_group(g: pd.DataFrame, classes: tuple[str, ...]) -> dict[str, Any]:
    """All metrics for one (split, horizon) group of merged rows (``label, pred_label, score``)."""
    y = g["label"].ne(NONE).to_numpy()
    y_hat = g["pred_label"].ne(NONE).to_numpy()
    s = g["score"].to_numpy(float)
    out: dict[str, Any] = {"n": len(g), "n_pos": int(y.sum()), "n_neg": int((~y).sum())}
    out["auroc"] = auroc(y, s)
    out["ap"] = average_precision(y, s)
    for far in FAR_LEVELS:
        r, thr = recall_at_far(y, s, far)
        key = f"recall_at_{int(far * 100)}far"
        out[key] = r
        out[key + "_threshold"] = thr
    p, r, f = prf(y, y_hat)
    out["hard"] = {
        "precision": p,
        "recall": r,
        "f1": f,
        "alarm_rate": float(y_hat.mean()) if len(g) else float("nan"),
        "far": float(y_hat[~y].mean()) if (~y).sum() else float("nan"),
    }

    thr10 = out["recall_at_10far_threshold"]
    present = [c for c in classes if (g["label"] == c).any()]
    per_class: dict[str, Any] = {}
    for c in present:
        m = (g["label"] == c).to_numpy()
        per_class[c] = {
            "n": int(m.sum()),
            "recall_at_10far": float((s[m] > thr10).mean())
            if not np.isnan(thr10)
            else float("nan"),
            "hard_recall": float(y_hat[m].mean()),
            "subsystem_acc": float((g.loc[m, "pred_label"] == c).mean()),
        }
    out["per_class"] = per_class

    pos = g[y]
    mf1, per_f1 = macro_f1(pos["label"], pos["pred_label"], present)
    out["subsystem"] = {
        "macro_f1_over_positives": mf1,
        "f1_per_class": per_f1,
        "accuracy_over_positives": float((pos["label"] == pos["pred_label"]).mean())
        if len(pos)
        else float("nan"),
    }
    cm_classes = [
        c for c in classes if (g["label"] == c).any() or (g["pred_label"] == c).any()
    ] + [NONE]
    out["confusion"] = confusion(g["label"], g["pred_label"], cm_classes).to_dict(
        orient="split"
    )
    return out


def score(
    predictions: pd.DataFrame,
    labels: pd.DataFrame,
    classes: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Merge and score. Returns ``{"coverage": ..., "results": {split: {horizon: metrics}}}`` (horizon 'all' pooled)."""
    classes = classes or fault_classes()
    if "task" not in labels.columns:
        labels = labels.assign(task="t1")
    merged = labels.merge(predictions, on="window_id", how="left", indicator=True)
    unknown = set(predictions["window_id"]) - set(labels["window_id"])
    have = merged["_merge"] == "both"
    coverage = {
        "n_predictions": len(predictions),
        "n_unknown_window_ids": len(unknown),
        "n_windows": len(labels),
        "n_scored": int(have.sum()),
        "missing_per_split": merged.loc[~have].groupby("split").size().to_dict(),
    }
    merged = merged[have]
    results: dict[str, dict[str, Any]] = {}
    for split, gs in merged[merged["task"] == "t1"].groupby("split", sort=True):
        results[str(split)] = {}
        for h, gh in gs.groupby("horizon_h", sort=True):
            results[str(split)][str(int(h))] = score_group(gh, classes)
        results[str(split)]["all"] = score_group(gs, classes)
    for (task, split), gs in merged[merged["task"] != "t1"].groupby(
        ["task", "split"], sort=True
    ):
        results[f"{task}/{split}"] = {"all": score_group(gs, classes)}
    return {"coverage": coverage, "results": results}


# --------------------------------------------------------------------------------------------- report


def _fmt(x: float) -> str:
    return (
        "  –  " if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.3f}"
    )


def format_report(res: dict[str, Any], name: str = "") -> str:
    cov = res["coverage"]
    lines = [f"## {name or 'predictions'}", ""]
    lines.append(
        f"scored {cov['n_scored']} / {cov['n_windows']} windows; {cov['n_predictions']} predictions, {cov['n_unknown_window_ids']} unknown ids"
    )
    if cov["missing_per_split"]:
        lines.append(
            "missing predictions per split: "
            + ", ".join(f"{k} {v}" for k, v in cov["missing_per_split"].items())
        )
    lines += [
        "",
        "| split | H | n | pos | AUROC | AP | R@10%FAR | R@5%FAR | hard P / R / F1 | subsystem macro-F1 | subsystem acc |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for split, per_h in res["results"].items():
        for h, m in per_h.items():
            hd = m["hard"]
            lines.append(
                f"| {split} | {h} | {m['n']} | {m['n_pos']} | {_fmt(m['auroc'])} | {_fmt(m['ap'])} | {_fmt(m['recall_at_10far'])} | "
                f"{_fmt(m['recall_at_5far'])} | {_fmt(hd['precision'])} / {_fmt(hd['recall'])} / {_fmt(hd['f1'])} | "
                f"{_fmt(m['subsystem']['macro_f1_over_positives'])} | {_fmt(m['subsystem']['accuracy_over_positives'])} |"
            )
    lines.append("")
    lines.append(
        "Per class, horizons pooled (recall at 10 % FAR · subsystem accuracy · n):"
    )
    lines.append("")
    all_classes = sorted(
        {c for per_h in res["results"].values() for c in per_h["all"]["per_class"]}
    )
    lines.append("| split | " + " | ".join(all_classes) + " |")
    lines.append("|---|" + "---|" * len(all_classes))
    for split, per_h in res["results"].items():
        pc = per_h["all"]["per_class"]
        cells = []
        for c in all_classes:
            if c in pc:
                cells.append(
                    f"{_fmt(pc[c]['recall_at_10far'])} · {_fmt(pc[c]['subsystem_acc'])} · {pc[c]['n']}"
                )
            else:
                cells.append("–")
        lines.append(f"| {split} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _json_safe(o: Any) -> Any:
    if isinstance(o, dict):
        return {str(k): _json_safe(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_json_safe(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return None if np.isnan(o) else float(o)
    if isinstance(o, np.integer):
        return int(o)
    return o


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("predictions", help="predictions.jsonl")
    ap.add_argument(
        "--windows",
        nargs="+",
        default=list(DEFAULT_WINDOWS),
        help="window parquet(s) with the labels",
    )
    ap.add_argument("--out", help="write full metrics as JSON here")
    ap.add_argument("--name", help="name shown in the report (default: the file name)")
    args = ap.parse_args(argv)

    preds = load_predictions(args.predictions)
    labels = load_labels(args.windows)
    res = score(preds, labels)
    print(format_report(res, args.name or Path(args.predictions).stem))
    if args.out:
        Path(args.out).write_text(
            json.dumps(_json_safe(res), indent=1), encoding="utf-8"
        )
        print(f"\nwrote {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
