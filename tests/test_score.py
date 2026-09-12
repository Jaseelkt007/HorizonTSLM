"""Eval harness on a synthetic label table: perfect / always-no / inverted predictors give known numbers."""

import json

import numpy as np
import pandas as pd
import pytest

from turbine_tslm.eval import score as S
from turbine_tslm.eval.baselines import always_no, write_predictions

CLASSES = ("generator_cooling", "gearbox_lubrication", "pitch_system")


@pytest.fixture
def labels():
    rng = np.random.default_rng(1)
    rows = []
    for split in ("train", "test_b"):
        for h in (1, 3, 6):
            for i in range(60):
                pos = i % 3 == 0  # 20 positives, 40 negatives per group
                cls = CLASSES[(i // 3) % len(CLASSES)] if pos else S.NONE
                rows.append(
                    {
                        "window_id": f"{split}-{h}-{i}",
                        "farm": "x",
                        "split": split,
                        "horizon_h": h,
                        "label": cls,
                        "is_positive": pos,
                        "state_at_anchor": "producing",
                    }
                )
    df = pd.DataFrame(rows)
    df["noise"] = rng.random(len(df))
    return df


def perfect(labels: pd.DataFrame) -> pd.DataFrame:
    pos = labels["label"].ne(S.NONE)
    return pd.DataFrame(
        {
            "window_id": labels["window_id"],
            "score": np.where(pos, 0.9, 0.1) + labels["noise"] * 0.05,
            "pred_label": labels["label"],
        }
    )


def test_parse_answer_variants():
    assert S.parse_answer("Answer: no", CLASSES) == "none"
    assert (
        S.parse_answer("Answer: yes, generator_cooling", CLASSES) == "generator_cooling"
    )
    assert (
        S.parse_answer("blah\nAnswer: yes, gearbox_lubrication.", CLASSES)
        == "gearbox_lubrication"
    )
    assert S.parse_answer("Answer: Pitch_System", CLASSES) == "pitch_system"
    assert S.parse_answer("Answer: yes, unknown_thing", CLASSES) == "none"
    assert S.parse_answer("no answer line at all", CLASSES) == "none"
    assert (
        S.parse_answer("Answer: yes, pitch_system\nAnswer: no", CLASSES) == "none"
    )  # last one wins


def test_metric_primitives():
    y = np.array([1, 1, 0, 0], bool)
    assert S.auroc(y, np.array([0.9, 0.8, 0.2, 0.1])) == 1.0
    assert S.auroc(y, np.array([0.1, 0.2, 0.8, 0.9])) == 0.0
    assert S.auroc(y, np.array([0.5, 0.5, 0.5, 0.5])) == 0.5
    assert np.isnan(S.auroc(np.zeros(4, bool), np.arange(4)))
    r, _ = S.recall_at_far(y, np.array([0.9, 0.8, 0.2, 0.1]), 0.10)
    assert r == 1.0
    r, _ = S.recall_at_far(y, np.array([0.5, 0.5, 0.5, 0.5]), 0.10)
    assert r == 0.0  # ties never clear the strict threshold -> realised FAR stays 0


def test_perfect_predictor_scores_one(labels):
    res = S.score(perfect(labels), labels, CLASSES)
    assert res["coverage"]["n_scored"] == len(labels)
    for split in ("train", "test_b"):
        for h in ("1", "3", "6", "all"):
            m = res["results"][split][h]
            assert m["n_pos"] == (20 if h != "all" else 60)
            assert m["auroc"] == 1.0
            assert m["recall_at_10far"] == 1.0
            assert m["hard"]["f1"] == 1.0
            assert m["subsystem"]["macro_f1_over_positives"] == 1.0
            for c in CLASSES:
                assert m["per_class"][c]["recall_at_10far"] == 1.0


def test_always_no_is_the_floor(labels):
    preds = always_no(labels).rename(columns={"label": "pred_label"})
    res = S.score(preds, labels, CLASSES)
    m = res["results"]["test_b"]["all"]
    assert (
        m["auroc"] == 0.5 and m["recall_at_10far"] == 0.0 and m["hard"]["recall"] == 0.0
    )
    assert m["subsystem"]["macro_f1_over_positives"] == 0.0
    cm = pd.DataFrame(
        **{k: v for k, v in m["confusion"].items() if k != "index"},
        index=m["confusion"]["index"],
    )
    assert cm.loc["generator_cooling", "none"] == 21 and cm.loc["none", "none"] == 120


def test_far_is_respected_on_negatives(labels):
    preds = pd.DataFrame(
        {
            "window_id": labels["window_id"],
            "score": labels["noise"],
            "pred_label": S.NONE,
        }
    )
    res = S.score(preds, labels, CLASSES)
    g = labels[labels.split == "train"].merge(preds, on="window_id")
    thr = res["results"]["train"]["all"]["recall_at_10far_threshold"]
    neg = g[g.label == S.NONE]
    assert (neg.score > thr).mean() <= 0.10


def test_missing_and_unknown_windows_are_counted(labels):
    preds = perfect(labels).iloc[:100].copy()
    preds.loc[len(preds)] = {
        "window_id": "not-a-window",
        "score": 0.5,
        "pred_label": "none",
    }
    res = S.score(preds, labels, CLASSES)
    assert res["coverage"]["n_scored"] == 100
    assert res["coverage"]["n_unknown_window_ids"] == 1
    assert sum(res["coverage"]["missing_per_split"].values()) == len(labels) - 100


def test_jsonl_roundtrip_with_text_answers(labels, tmp_path):
    path = tmp_path / "p.jsonl"
    with open(path, "w") as fh:
        for _, r in labels.iterrows():
            ans = (
                "Answer: no"
                if r.label == S.NONE
                else f"some evidence.\nAnswer: yes, {r.label}"
            )
            fh.write(
                json.dumps(
                    {
                        "window_id": r.window_id,
                        "text": ans,
                        "score": 0.9 if r.label != S.NONE else 0.1,
                    }
                )
                + "\n"
            )
    preds = S.load_predictions(path, CLASSES)
    assert set(preds.columns) >= {"window_id", "pred_label", "score"}
    res = S.score(preds, labels, CLASSES)
    assert res["results"]["train"]["all"]["subsystem"]["macro_f1_over_positives"] == 1.0
    write_predictions(always_no(labels), tmp_path / "no.jsonl")
    assert len(S.load_predictions(tmp_path / "no.jsonl", CLASSES)) == len(labels)
    report = S.format_report(res, "t")
    assert "test_b" in report and "R@10%FAR" in report


def test_duplicate_window_id_rejected(tmp_path):
    path = tmp_path / "d.jsonl"
    path.write_text(
        '{"window_id": "a", "label": "none"}\n{"window_id": "a", "label": "none"}\n'
    )
    with pytest.raises(ValueError, match="duplicate"):
        S.load_predictions(path, CLASSES)
