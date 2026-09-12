"""Upload a finished (or running) training run's outputs/<run>/ to Weights & Biases after the fact.

    WANDB_API_KEY=... uv run python scripts/wandb_backfill.py outputs/t1_flamingo_llama1b --project turbine-tslm

Reads config.yaml, train_log.jsonl (per-step train loss, epoch-end val loss) and, if present, results.json (the
eval.score metrics) and predictions.jsonl (uploaded as an artifact). Same keys as train.py's live logging.
"""

import argparse
import json
from pathlib import Path

import wandb
import yaml

p = argparse.ArgumentParser()
p.add_argument("run_dir")
p.add_argument("--project", default="turbine-tslm")
p.add_argument("--name", help="wandb run name (default: the directory name)")
a = p.parse_args()
run_dir = Path(a.run_dir)
cfg = yaml.safe_load((run_dir / "config.yaml").read_text(encoding="utf-8"))
wb = wandb.init(
    project=a.project, name=a.name or run_dir.name, config=cfg, resume="allow"
)
n = 0
for line in (run_dir / "train_log.jsonl").read_text(encoding="utf-8").splitlines():
    if line.strip():
        rec = json.loads(line)
        wb.log({k: v for k, v in rec.items() if k != "step"}, step=rec.get("step"))
        n += 1
print(f"logged {n} records")
results = run_dir / "results.json"
if results.exists():
    res = json.loads(results.read_text(encoding="utf-8"))
    summary = {}
    for split, per_h in res["results"].items():
        for h, m in per_h.items():
            for k in ("auroc", "ap", "recall_at_10far", "recall_at_5far"):
                summary[f"{split}/h{h}/{k}"] = m[k]
            summary[f"{split}/h{h}/subsystem_macro_f1"] = m["subsystem"][
                "macro_f1_over_positives"
            ]
    wb.log(summary)
    print(f"logged {len(summary)} metrics")
preds = run_dir / "predictions.jsonl"
if preds.exists():
    art = wandb.Artifact(f"{run_dir.name}-predictions", type="predictions")
    art.add_file(str(preds))
    for f in ("report.md", "results.json", "config.yaml"):
        if (run_dir / f).exists():
            art.add_file(str(run_dir / f))
    wb.log_artifact(art)
    print("uploaded predictions artifact")
wb.finish()
