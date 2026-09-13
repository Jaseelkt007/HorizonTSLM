"""LLM-as-judge for generated explanations (the mentor's suggestion), complementing eval/faithfulness.py.

For a stratified sample of predictions the judge sees the *facts recomputed from the window* (so it can check
grounding without the raw series), the gold label, and the model's explanation, and scores 1-5 on:
  grounded   - claims are supported by the facts (no invented signals or numbers)
  coherent   - the reasoning reads as one argument that leads to the final answer
  actionable - an operations engineer could act on it (what to check / de-rate / when)
plus `supports_answer` (does the reasoning justify the Answer line) and a one-line critique.

    ANTHROPIC_API_KEY=... uv run python scripts/llm_judge.py outputs/<run>/predictions.jsonl --n 60 --out judge.json
    OPENAI_API_KEY=...    uv run python scripts/llm_judge.py ...   # same prompt/schema through the OpenAI SDK
    uv run python scripts/llm_judge.py a.jsonl b.jsonl --n 40          # several runs, same sampled window ids

Cost: ~1.5k input tokens per text; 60 texts x 2 runs ~ $1 on Claude Opus 5.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from pathlib import Path

import numpy as np

from turbine_tslm.data.evidence import extract_facts
from turbine_tslm.eval.faithfulness import load_series
from turbine_tslm.eval.score import DEFAULT_WINDOWS

MODEL = "claude-opus-5"
OPENAI_PREFERENCE = (
    "gpt-5",
    "gpt-4.1",
    "gpt-4o",
)  # first one the account can see is used
SYSTEM = (
    "You are a wind-turbine operations expert reviewing an AI assistant's written assessment of 24 hours of SCADA data. "
    "You are given the FACTS computed directly from the data (these are ground truth), the true outcome from the alarm "
    "log, and the assistant's text. Judge the text strictly against the facts. Respond with JSON only."
)
SCHEMA = {
    "type": "object",
    "properties": {
        "grounded": {"type": "integer", "minimum": 1, "maximum": 5},
        "coherent": {"type": "integer", "minimum": 1, "maximum": 5},
        "actionable": {"type": "integer", "minimum": 1, "maximum": 5},
        "supports_answer": {"type": "boolean"},
        "critique": {"type": "string"},
    },
    "required": ["grounded", "coherent", "actionable", "supports_answer", "critique"],
    "additionalProperties": False,
}
FACT_KEYS = [
    "wind_first6h",
    "wind_last6h",
    "wind_last1h",
    "wind_max",
    "power_first6h",
    "power_6h_ago",
    "power_last1h",
    "residual_last3h",
    "gen_bearing_front_temperature_delta6h",
    "gen_bearing_rear_temperature_delta6h",
    "gen_bearing_front_temperature_now",
    "gen_bearing_rear_temperature_now",
    "stator_temperature_delta6h",
    "stator_temperature_now",
    "gear_oil_temperature_delta6h",
    "main_bearing_temperature_delta6h",
    "bearing_asym_now",
    "bearing_asym_mean",
    "oil_pressure_6h_ago",
    "oil_pressure_now",
    "pitch_last1h",
    "rotor_rpm_last1h",
    "tower_acc_last1h",
    "tower_acc_median",
    "grid_voltage_max_step",
    "grid_freq_max_dev",
    "yaw_misalignment_last1h",
]


def facts_text(f: dict) -> str:
    return "\n".join(
        f"{k}: {f[k]:.2f}"
        for k in FACT_KEYS
        if k in f and isinstance(f[k], (int, float)) and np.isfinite(f[k])
    )


def build_prompt(facts: str, gold: str, text: str) -> str:
    return (
        f"FACTS (computed from the window; units: m/s, kW, °C, rpm, mm/s², V, Hz, degrees; *_delta6h = change over "
        f"the last 6 h; *_now / *_last1h = last-hour mean):\n{facts}\n\n"
        f"TRUE OUTCOME from the alarm log: {'no fault stop within the horizon' if gold == 'none' else 'fault stop, subsystem ' + gold}\n\n"
        f"ASSISTANT TEXT:\n{text.strip()}\n\n"
        "Score the text. grounded: every number and every claimed trend must match the FACTS (5 = all correct, "
        "1 = mostly invented). coherent: 5 = the sentences form one argument ending in the answer. actionable: 5 = an "
        "operator knows what to check or do. supports_answer: true if the stated evidence justifies the final Answer "
        "line (a text that says no precursor is visible but answers yes should be false). critique: one sentence."
    )


class ClaudeJudge:
    def __init__(self):
        import anthropic

        self.anthropic = anthropic
        self.client = anthropic.Anthropic()
        self.name = MODEL

    def __call__(self, facts: str, gold: str, text: str) -> dict:
        resp = self.client.messages.parse(
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM,
            messages=[{"role": "user", "content": build_prompt(facts, gold, text)}],
            output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
        )
        return resp.parsed_output

    def is_api_error(self, e: Exception) -> bool:
        return isinstance(e, self.anthropic.APIError)


class OpenAIJudge:
    def __init__(self, model: str | None = None):
        import openai

        self.openai = openai
        self.client = openai.OpenAI()
        if model is None:
            available = {m.id for m in self.client.models.list()}
            model = next(
                (m for m in OPENAI_PREFERENCE if m in available), OPENAI_PREFERENCE[-1]
            )
        self.name = model

    def __call__(self, facts: str, gold: str, text: str) -> dict:
        resp = self.client.chat.completions.create(
            model=self.name,
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": build_prompt(facts, gold, text)},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {"name": "judgement", "schema": SCHEMA, "strict": True},
            },
        )
        return json.loads(resp.choices[0].message.content)

    def is_api_error(self, e: Exception) -> bool:
        return isinstance(e, self.openai.OpenAIError)


def make_judge(model: str | None = None):
    if os.environ.get("ANTHROPIC_API_KEY"):
        return ClaudeJudge()
    if os.environ.get("OPENAI_API_KEY"):
        return OpenAIJudge(model)
    raise SystemExit("set ANTHROPIC_API_KEY or OPENAI_API_KEY")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument(
        "predictions",
        nargs="+",
        help="one or more predictions.jsonl (same sampled window ids across runs)",
    )
    ap.add_argument("--n", type=int, default=60)
    ap.add_argument("--splits", nargs="+", default=["test_a", "test_b"])
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--windows", nargs="+", default=list(DEFAULT_WINDOWS))
    ap.add_argument("--out")
    ap.add_argument("--model", help="override the judge model id (OpenAI backend)")
    a = ap.parse_args(argv)

    runs = {}
    for p in a.predictions:
        rows = [
            json.loads(line)
            for line in Path(p).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        runs[Path(p).parent.name] = {
            r["window_id"]: r
            for r in rows
            if r.get("text") and r.get("task", "t1") == "t1" and r["split"] in a.splits
        }
    common = sorted(set.intersection(*(set(r) for r in runs.values())))
    rng = random.Random(a.seed)
    first = next(iter(runs.values()))
    pos = [w for w in common if first[w]["gold"] != "none"]
    neg = [w for w in common if first[w]["gold"] == "none"]
    sample = rng.sample(pos, min(len(pos), a.n // 2)) + rng.sample(
        neg, min(len(neg), a.n - a.n // 2)
    )
    series = load_series(a.windows, set(sample))
    judge = make_judge(a.model)
    print(
        f"[judge] model {judge.name}, {len(sample)} windows x {len(runs)} runs",
        file=sys.stderr,
    )
    results = {name: [] for name in runs}
    for i, w in enumerate(sample, 1):
        facts = facts_text(extract_facts(series[w]))
        for name, rows in runs.items():
            r = rows[w]
            try:
                j = judge(facts, r["gold"], r["text"])
            except Exception as e:
                if not judge.is_api_error(e):
                    raise
                j = {"error": str(e)}
            results[name].append(
                {
                    "window_id": w,
                    "split": r["split"],
                    "gold": r["gold"],
                    "pred": r.get("label"),
                    **j,
                }
            )
        print(f"[judge] {i}/{len(sample)}", file=sys.stderr, flush=True)
    summary = {"judge_model": judge.name}
    for name, rs in results.items():
        ok = [r for r in rs if "grounded" in r]
        summary[name] = {
            "n": len(ok),
            "grounded": float(np.mean([r["grounded"] for r in ok])) if ok else None,
            "coherent": float(np.mean([r["coherent"] for r in ok])) if ok else None,
            "actionable": float(np.mean([r["actionable"] for r in ok])) if ok else None,
            "supports_answer": float(np.mean([r["supports_answer"] for r in ok]))
            if ok
            else None,
            "errors": len(rs) - len(ok),
        }
    print(json.dumps(summary, indent=1))
    if a.out:
        Path(a.out).write_text(
            json.dumps({"summary": summary, "per_text": results}, indent=1),
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
