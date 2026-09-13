"""Run one real OpenTSLM diagnostic query for a saved SCADA window.

The module deliberately loads no ML dependency until it is executed. The
Next.js demo invokes it only after an operator presses Send.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def _checkpoint(config: dict) -> str | None:
    """Prefer an explicitly deployed fine-tune, then the configured best run."""
    explicit = os.environ.get("DEMO_MODEL_CHECKPOINT")
    if explicit:
        return explicit
    candidate = Path(config["checkpoint_dir"]) / "best.pt"
    return str(candidate) if candidate.exists() else None


def infer(window_id: str, question: str, config_path: str) -> str:
    # Imports stay here so merely starting the web app cannot load a model.
    from turbine_tslm.training import train
    from turbine_tslm.training.turbine_dataset import load_rows, make_dataset_class

    cfg = train.load_config(config_path, [])
    checkpoint = _checkpoint(cfg)
    if checkpoint:
        cfg["init_checkpoint"] = checkpoint
    model = train.build_model(cfg)
    model.eval()
    row = next((item for item in load_rows() if item["window_id"] == window_id), None)
    if row is None:
        raise ValueError(f"SCADA window {window_id!r} is not present in the local TimeNet registry.")
    row = dict(row)
    # Keep the trained instruction's final-answer constraint at the end of the
    # preamble; the operator question is additional model input, not a UI-only
    # label or a lookup key.
    final_instruction = ' Do not state a decision until the final line. End with "Answer: ".'
    row["pre_prompt"] = row["pre_prompt"].replace(
        final_instruction,
        f" Operator question: {question.strip()}.{final_instruction}",
    )
    # Formatting one record must not instantiate QADataset: its constructor eagerly
    # formats every split, which is needless for an interactive request.
    dataset_type = make_dataset_class("demo_inference", series_stats=cfg["series_stats"])
    formatter = dataset_type.__new__(dataset_type)
    formatter.EOS_TOKEN = model.get_eos_token()
    sample = formatter._format_sample(row)
    with train.autocast(cfg):
        answer = train.generate_texts(model, [sample], cfg["max_new_tokens"])[0]
    return answer.strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--window-id", required=True)
    parser.add_argument("--question", required=True)
    parser.add_argument("--config", default=os.environ.get("DEMO_MODEL_CONFIG", "configs/t1_flamingo_llama1b_evidence_rich.yaml"))
    args = parser.parse_args()
    print(json.dumps({"answer": infer(args.window_id, args.question, args.config)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
