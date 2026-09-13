"""Rejection-sampling fine-tuning (RFT) — the "RL on top of the fine-tune" step with a verifiable reward.

Stage 1, ``sample``: from a trained evidence checkpoint, draw ``k`` explanations per training record (temperature
sampling), score each with a reward computable from the window alone — label correct, every numeric claim verified
by ``eval.faithfulness.check_text``, conclusion consistent with the Answer line — and keep the best passing sample
per record (falls back to the rule-generated target when none passes, so the training set keeps its size).

    uv run python -m turbine_tslm.training.rft sample configs/t1_flamingo_llama1b_evidence_rich.yaml \\
        --checkpoint ~/data/checkpoints/t1_flamingo_llama1b_evidence_rich/best.pt --k 3 --temperature 0.8 \\
        --out outputs/rft/kept.jsonl

Stage 2: train with ``answers_from: outputs/rft/kept.jsonl`` + ``init_checkpoint: <best.pt>`` (see
``configs/t1_flamingo_llama1b_evidence_rich_rft.yaml``); the dataset uses the kept text as the answer.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import torch

from turbine_tslm.eval.faithfulness import check_text
from turbine_tslm.eval.score import parse_answer
from turbine_tslm.training import train as T


def reward(text: str, gold: str, series) -> tuple[bool, int]:
    """(passes, n_verified): passes iff label right, no wrong / unverifiable numbers, conclusion consistent."""
    c = check_text(text, series)
    label_ok = parse_answer(text) == gold
    clean = (
        c["wrong"] == 0
        and c["unverifiable"] == 0
        and c["conclusion_consistent"] is not False
    )
    return (label_ok and clean and text.strip().startswith("Wind")), c["verified"]


def sample(args) -> int:
    cfg = T.load_config(args.config, args.set)
    cfg["wandb_project"] = None
    T.set_seed(cfg["seed"] + 1)
    model = T.build_model(cfg)
    T.load_checkpoint(model, Path(args.checkpoint))
    if cfg["predict_dtype"] and cfg["model_type"] == "OpenTSLMFlamingo":
        model.to(getattr(torch, cfg["predict_dtype"]))
    model.eval()
    sets, _, _, collate, _ = T.make_loaders(cfg, model.get_eos_token())
    from turbine_tslm.training.turbine_dataset import TurbineQADataset

    DS = next(
        c
        for c in TurbineQADataset.__subclasses__()
        if c.__name__.endswith(cfg["run_name"])
    )
    raw = {r["window_id"].split("#")[0]: r["series"] for r in DS.rows()}
    samples = list(sets["train"])
    if args.limit:
        samples = samples[: args.limit]
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    bs = cfg["eval_batch_size"]
    t0 = time.time()
    n_pass = n_sampled_kept = 0
    with open(out, "w", encoding="utf-8") as fh:
        for i in range(0, len(samples), bs):
            chunk = samples[i : i + bs]
            cands: list[list[str]] = [[] for _ in chunk]
            for _ in range(args.k):
                with T.autocast(cfg):
                    texts = T.generate_texts(
                        model,
                        collate(chunk),
                        cfg["max_new_tokens"],
                        do_sample=True,
                        temperature=args.temperature,
                        top_p=0.95,
                    )
                for j, t in enumerate(texts):
                    cands[j].append(t.strip())
            for s, texts in zip(chunk, cands, strict=True):
                series = raw[s["window_id"].split("#")[0]]
                scored = sorted(
                    ((reward(t, s["label"], series), t) for t in texts),
                    key=lambda x: (x[0][0], x[0][1]),
                    reverse=True,
                )
                (passes, _n_ver), best = scored[0]
                rec = {
                    "window_id": s["window_id"],
                    "task": s["task"],
                    "gold": s["label"],
                    "n_pass": sum(r[0] for r, _ in scored),
                }
                if passes:
                    rec["answer"] = best + (
                        model.get_eos_token()
                        if not best.endswith(model.get_eos_token())
                        else ""
                    )
                    rec["source"] = "sampled"
                    n_pass += 1
                    n_sampled_kept += 1
                else:
                    rec["answer"] = s["answer"]
                    rec["source"] = "rule"
                fh.write(json.dumps(rec) + "\n")
            if (i // bs) % 10 == 0:
                print(
                    f"[rft] {i + len(chunk)}/{len(samples)} sampled, {n_pass} with a passing sample ({time.time() - t0:.0f}s)",
                    flush=True,
                )
    print(
        f"[rft] done: {n_sampled_kept}/{len(samples)} records use a sampled answer, rest keep the rule target -> {out}"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sample")
    s.add_argument("config")
    s.add_argument("--checkpoint", required=True)
    s.add_argument("--k", type=int, default=3)
    s.add_argument("--temperature", type=float, default=0.8)
    s.add_argument("--limit", type=int)
    s.add_argument("--out", required=True)
    s.add_argument("--set", action="append", default=[], metavar="KEY=VALUE")
    a = ap.parse_args(argv)
    return sample(a)


if __name__ == "__main__":
    sys.exit(main())
