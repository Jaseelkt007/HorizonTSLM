"""Thin OpenTSLM fine-tune for T1 (label-only MVP): YAML config -> model -> train -> predictions.jsonl -> scores.

    uv run python -m turbine_tslm.training.train configs/smoke_flamingo.yaml
    uv run python -m turbine_tslm.training.train configs/t1_flamingo_llama1b.yaml --set epochs=3 --set max_samples=400
    uv run python -m turbine_tslm.training.train configs/t1_flamingo_llama1b.yaml --predict-only   # reuse best.pt

Deliberately not the upstream curriculum script (stage names, results/ layout, DDP). Same model classes, same
collate, same loss; a plain loop with periodic checkpoints (the VM may be preempted) and, at the end, generation +
a yes/no log-likelihood score on the requested splits, written in the shared predictions.jsonl format and scored
with ``turbine_tslm.eval.score``.

Checkpoints hold only the trainable parameters (perceiver, gated cross-attention, input embeddings, encoder / LoRA),
so they are a few hundred MB instead of the whole LLM; the base LLM is re-downloaded from the Hub by ``llm_id``.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch
import yaml
from torch.utils.data import DataLoader

from turbine_tslm.eval import score as scoring

DEFAULTS: dict[str, Any] = {
    "run_name": "run",
    "model_type": "OpenTSLMFlamingo",  # or OpenTSLMSP
    "llm_id": "meta-llama/Llama-3.2-1B",
    "init_checkpoint": None,  # HF repo (OpenTSLM/<base>-<stage>-flamingo|sp, file model_checkpoint.pt) or a local .pt
    "lora": False,  # OpenTSLMSP only
    "gradient_checkpointing": False,
    "model_dtype": "float32",  # Flamingo: transformers>=5 loads the LLM in its config dtype (bf16) while the OpenTSLM
    # encoder/perceiver/cross-attention are fp32 -> cast the whole model to one dtype (checkpoints were trained fp32)
    "autocast_bf16": True,  # bf16 autocast around forward passes (speed); parameters stay in model_dtype
    "epochs": 3,
    "batch_size": 4,
    "eval_batch_size": 8,
    "lr": 1e-4,
    "warmup_frac": 0.03,
    "grad_clip": 1.0,
    "early_stop_patience": 3,
    "tasks": [
        "t1"
    ],  # t1 early warning (+ t3 post-hoc explanation rows derived from the 1 h positives)
    "answer_mode": "label",  # label (MVP) | evidence (rule-based reasoning before the Answer line)
    "evidence_sentences": 3,
    "series_stats": "basic",  # rich: first-6h / 6h-before-end / last-hour values in every channel text
    "answers_from": None,  # jsonl of {window_id, answer}: per-record answer override (RFT stage 2)
    "max_samples": None,  # per split, stratified (smoke runs)
    "horizons": None,  # e.g. [6]
    "dataset_ids": ["cubico/penmanshiel", "cubico/kelmarsh"],
    "eval_splits": ["val", "test_a", "test_b"],
    "max_new_tokens": 24,
    "predict_mode": "loglik",  # loglik: batched teacher-forced scoring of every answer candidate (fast, no
    # generation); generate: free generation + parse + yes/no log-likelihood (needed for evidence text); both
    "score_batch_size": 32,  # candidate sequences per forward pass in loglik mode
    "rescore_from": None,  # predict_mode=rescore: existing predictions.jsonl with generated text; the yes/no score is
    # recomputed by comparing conclusion candidates conditioned on the model's own evidence sentences (without its
    # conclusion), which gives a graded score where the generate-mode score is near-binary
    "predict_dtype": "bfloat16",  # cast the whole model before prediction (inference only; training keeps model_dtype)
    "checkpoint_every_steps": 200,
    "log_every_steps": 10,
    "resume": True,  # continue from last.pt in checkpoint_dir if present
    "seed": 0,
    "device": None,
    "out_dir": None,  # default outputs/<run_name>
    "checkpoint_dir": None,  # default $DATA_DIR/checkpoints/<run_name>
    "windows": None,  # parquet label tables; default $DATA_DIR/interim/*_windows.parquet
    "epoch_loss_splits": [
        "test_a",
        "test_b",
    ],  # diagnostic only: mean answer loss on these splits each epoch
    # (logged as <split>_loss; never used for checkpoint selection, which is val_loss only)
    "wandb_project": None,  # e.g. "turbine-tslm": mirror train_log.jsonl + final metrics to Weights & Biases
    # (needs `uv sync --extra wandb` and WANDB_API_KEY in the environment; run name = run_name)
}


# --------------------------------------------------------------------------------------------- config


def data_dir() -> Path:
    return Path(os.environ.get("DATA_DIR", "data")).expanduser()


def load_config(path: str | None, overrides: list[str]) -> dict[str, Any]:
    cfg = dict(DEFAULTS)
    if path:
        cfg.update(yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {})
    for ov in overrides:
        k, _, v = ov.partition("=")
        if k not in DEFAULTS:
            raise SystemExit(f"unknown config key {k!r}")
        cfg[k] = yaml.safe_load(v)
    cfg["out_dir"] = str(cfg["out_dir"] or Path("outputs") / cfg["run_name"])
    cfg["checkpoint_dir"] = str(
        cfg["checkpoint_dir"] or data_dir() / "checkpoints" / cfg["run_name"]
    )
    cfg["windows"] = cfg["windows"] or [
        str(data_dir() / "interim" / f"{f}_windows.parquet")
        for f in ("penmanshiel", "kelmarsh")
    ]
    cfg["device"] = cfg["device"] or ("cuda" if torch.cuda.is_available() else "cpu")
    return cfg


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


# --------------------------------------------------------------------------------------------- model


def build_model(cfg: dict[str, Any]):
    from opentslm.model.llm.OpenTSLMFlamingo import OpenTSLMFlamingo
    from opentslm.model.llm.OpenTSLMSP import OpenTSLMSP

    device = cfg["device"]
    if cfg["model_type"] == "OpenTSLMFlamingo":
        model = OpenTSLMFlamingo(
            device=device,
            llm_id=cfg["llm_id"],
            cross_attn_every_n_layers=1,
            gradient_checkpointing=cfg["gradient_checkpointing"],
        )
    elif cfg["model_type"] == "OpenTSLMSP":
        model = OpenTSLMSP(llm_id=cfg["llm_id"], device=device)
        if cfg["lora"]:
            model.enable_lora()
    else:
        raise SystemExit(f"unknown model_type {cfg['model_type']}")
    model.to(device)
    if cfg["model_type"] == "OpenTSLMFlamingo":
        model.to(getattr(torch, cfg["model_dtype"]))

    init = cfg["init_checkpoint"]
    if init:
        path = Path(init)
        if not path.exists():
            from huggingface_hub import hf_hub_download

            path = Path(hf_hub_download(repo_id=init, filename="model_checkpoint.pt"))
        print(f"[init] loading {path}")
        ck = torch.load(path, map_location="cpu", weights_only=False)
        if "trainable" in ck:  # one of our own checkpoints (trainable parameters only)
            load_checkpoint(model, path)
        else:
            model.load_from_file(str(path))  # upstream format, strict=False
    return model


def autocast(cfg: dict[str, Any]):
    return torch.autocast(
        "cuda",
        dtype=torch.bfloat16,
        enabled=bool(cfg["autocast_bf16"]) and cfg["device"] == "cuda",
    )


def tokenizer_of(model):
    return getattr(model, "text_tokenizer", None) or model.tokenizer


def trainable_state(model) -> dict[str, torch.Tensor]:
    names = {n for n, p in model.named_parameters() if p.requires_grad}
    return {k: v.detach().cpu() for k, v in model.state_dict().items() if k in names}


def save_checkpoint(model, path: Path, **meta) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    torch.save({"trainable": trainable_state(model), **meta}, tmp)
    tmp.replace(path)


def load_checkpoint(model, path: Path) -> dict[str, Any]:
    ck = torch.load(path, map_location="cpu", weights_only=False)
    _missing, unexpected = model.load_state_dict(ck["trainable"], strict=False)
    if unexpected:
        raise RuntimeError(f"{path}: unexpected keys {unexpected[:5]}")
    return {k: v for k, v in ck.items() if k != "trainable"}


def make_optimizer(model, cfg: dict[str, Any]) -> torch.optim.Optimizer:
    """Upstream grouping: weight decay only on the gated cross-attention (Flamingo); 1e-2 everywhere for SP."""
    params = [(n, p) for n, p in model.named_parameters() if p.requires_grad]
    if not params:
        raise RuntimeError("no trainable parameters")
    if cfg["model_type"] == "OpenTSLMFlamingo":
        wd = [p for n, p in params if "gated_cross_attn" in n]
        no_wd = [p for n, p in params if "gated_cross_attn" not in n]
        groups = [
            {"params": wd, "weight_decay": 0.1},
            {"params": no_wd, "weight_decay": 0.0},
        ]
    else:
        groups = [{"params": [p for _, p in params], "weight_decay": 1e-2}]
    n = sum(p.numel() for _, p in params)
    print(f"[model] trainable parameters: {n / 1e6:.1f} M")
    return torch.optim.AdamW(groups, lr=cfg["lr"])


# --------------------------------------------------------------------------------------------- data


def load_answer_overrides(path: str | None) -> dict[str, str] | None:
    if not path:
        return None
    rows = [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return {r["window_id"]: r["answer"] for r in rows}


def make_loaders(cfg: dict[str, Any], eos: str):
    from opentslm.model_config import PATCH_SIZE
    from opentslm.time_series_datasets.util import (
        extend_time_series_to_match_patch_size_and_aggregate,
    )

    from turbine_tslm.training.turbine_dataset import make_dataset_class

    DS = make_dataset_class(
        cfg["run_name"],
        dataset_ids=tuple(cfg["dataset_ids"]),
        max_samples=cfg["max_samples"],
        horizons=cfg["horizons"],
        seed=cfg["seed"],
        answer_mode=cfg["answer_mode"],
        evidence_sentences=cfg["evidence_sentences"],
        tasks=tuple(cfg["tasks"]),
        series_stats=cfg["series_stats"],
        answer_overrides=load_answer_overrides(cfg["answers_from"]),
    )
    sets = {s: DS(s, EOS_TOKEN=eos) for s in ("train", "validation", "test")}
    for s, d in sets.items():
        n_pos = sum(x["label"] != "none" for x in d)
        print(f"[data] {s}: {len(d)} samples ({n_pos} positive)")

    def collate(batch):
        return extend_time_series_to_match_patch_size_and_aggregate(
            [dict(b) for b in batch], patch_size=PATCH_SIZE
        )

    train_loader = DataLoader(
        sets["train"], batch_size=cfg["batch_size"], shuffle=True, collate_fn=collate
    )
    val_loader = DataLoader(
        sets["validation"],
        batch_size=cfg["batch_size"],
        shuffle=False,
        collate_fn=collate,
    )
    extra = {}
    for split in cfg["epoch_loss_splits"] or []:
        rows = [x for x in sets["test"] if x["split"] == split]
        if rows:
            extra[split] = DataLoader(
                rows, batch_size=cfg["batch_size"], shuffle=False, collate_fn=collate
            )
    return sets, train_loader, val_loader, collate, extra


# --------------------------------------------------------------------------------------------- train


@torch.no_grad()
def mean_loss(cfg: dict[str, Any], model, loader) -> float:
    model.eval()
    tot, n = 0.0, 0
    for batch in loader:
        with autocast(cfg):
            tot += model.compute_loss(batch).item()
        n += 1
    return tot / max(n, 1)


def train(
    cfg: dict[str, Any], model, train_loader, val_loader, log, extra_loaders=None
) -> Path:
    ckdir = Path(cfg["checkpoint_dir"])
    best_path, last_path = ckdir / "best.pt", ckdir / "last.pt"
    opt = make_optimizer(model, cfg)
    total = cfg["epochs"] * len(train_loader)
    warm = int(cfg["warmup_frac"] * total)

    def lr_at(step):  # linear warmup then linear decay, as upstream
        if step < warm:
            return step / max(warm, 1)
        return max(0.0, (total - step) / max(total - warm, 1))

    sched = torch.optim.lr_scheduler.LambdaLR(opt, lr_at)
    step, start_epoch, best_val = 0, 1, math.inf
    if cfg["resume"] and last_path.exists():
        meta = load_checkpoint(model, last_path)
        step, start_epoch, best_val = (
            meta.get("step", 0),
            meta.get("epoch", 1),
            meta.get("best_val", math.inf),
        )
        for _ in range(step):
            sched.step()
        print(
            f"[resume] {last_path}: step {step}, epoch {start_epoch}, best val {best_val:.4f}"
        )

    bad_epochs = 0
    t0 = time.time()
    for epoch in range(start_epoch, cfg["epochs"] + 1):
        model.train()
        running, n_run = 0.0, 0
        for batch in train_loader:
            opt.zero_grad(set_to_none=True)
            with autocast(cfg):
                loss = model.compute_loss(batch)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(
                [p for p in model.parameters() if p.requires_grad], cfg["grad_clip"]
            )
            opt.step()
            sched.step()
            step += 1
            running += loss.item()
            n_run += 1
            if step % cfg["log_every_steps"] == 0:
                log(
                    {
                        "step": step,
                        "epoch": epoch,
                        "train_loss": running / n_run,
                        "lr": sched.get_last_lr()[0],
                        "elapsed_s": time.time() - t0,
                    }
                )
                running, n_run = 0.0, 0
            if (
                cfg["checkpoint_every_steps"]
                and step % cfg["checkpoint_every_steps"] == 0
            ):
                save_checkpoint(
                    model, last_path, step=step, epoch=epoch, best_val=best_val
                )
        val = mean_loss(cfg, model, val_loader)
        rec = {
            "step": step,
            "epoch": epoch,
            "val_loss": val,
            "best_val": min(best_val, val),
        }
        for name, loader in (extra_loaders or {}).items():
            rec[f"{name}_loss"] = mean_loss(
                cfg, model, loader
            )  # diagnostic, not for selection
        rec["elapsed_s"] = time.time() - t0
        log(rec)
        save_checkpoint(
            model, last_path, step=step, epoch=epoch + 1, best_val=min(best_val, val)
        )
        if val + 1e-4 < best_val:
            best_val, bad_epochs = val, 0
            save_checkpoint(model, best_path, step=step, epoch=epoch, val_loss=val)
            print(f"[train] epoch {epoch}: val {val:.4f} — new best")
        else:
            bad_epochs += 1
            print(
                f"[train] epoch {epoch}: val {val:.4f} (best {best_val:.4f}, {bad_epochs}/{cfg['early_stop_patience']} without improvement)"
            )
            if bad_epochs >= cfg["early_stop_patience"]:
                break
    if not best_path.exists():
        save_checkpoint(
            model, best_path, step=step, epoch=cfg["epochs"], val_loss=best_val
        )
    return best_path


# --------------------------------------------------------------------------------------------- predict


def _sum_logprob(logits: torch.Tensor, labels: torch.Tensor) -> torch.Tensor:
    """Per-sample sum of log p(label token) over positions where labels != -100 (next-token shifted).

    Only the labelled positions go through log-softmax (a full-vocabulary log-softmax over every position of 64
    long SP sequences is ~40 GB), so memory scales with the number of answer tokens, not the prompt length.
    """
    tgt = labels[:, 1:]
    mask = tgt != -100
    rows = mask.nonzero(as_tuple=True)
    sel = logits[:, :-1][rows].float()  # (n_label_tokens, vocab)
    lp = torch.log_softmax(sel, dim=-1).gather(-1, tgt[rows].unsqueeze(-1)).squeeze(-1)
    out = torch.zeros(labels.size(0), dtype=lp.dtype, device=lp.device)
    out.index_add_(0, rows[0], lp)
    return out


@torch.no_grad()
def batch_answer_loglik(model, batch: list[dict[str, Any]]) -> torch.Tensor:
    """Sum log-likelihood of each item's ``answer`` given its prompt, for a whole batch in one forward pass."""
    if hasattr(model, "text_tokenizer"):  # OpenTSLMFlamingo
        input_ids, images, attention_mask, labels = model.pad_and_apply_batch(
            batch, include_labels=False
        )
        out = model.model(
            vision_x=images, lang_x=input_ids, attention_mask=attention_mask
        )
        logits = out.logits if hasattr(out, "logits") else out[0]
        return _sum_logprob(logits, labels)
    # OpenTSLMSP: replicate its compute_loss without the batch-mean reduction
    answers = [b["answer"] for b in batch]
    inputs_embeds, attention_mask = model.pad_and_apply_batch(batch)
    B, L, _ = inputs_embeds.size()
    ans = model.tokenizer(answers, return_tensors="pt", padding=True)
    ans_ids = ans.input_ids.to(model.device)
    ans_mask = ans.attention_mask.to(model.device)
    ans_emb = model.llm.get_input_embeddings()(ans_ids).to(inputs_embeds.dtype)
    inputs_embeds = torch.cat([inputs_embeds, ans_emb], dim=1)
    attention_mask = torch.cat([attention_mask, ans_mask], dim=1)
    labels = torch.full(
        (B, attention_mask.size(1)), -100, device=model.device, dtype=torch.long
    )
    labels[:, L:] = ans_ids.masked_fill(ans_mask == 0, -100)
    out = model.llm(
        inputs_embeds=inputs_embeds, attention_mask=attention_mask, return_dict=True
    )
    return _sum_logprob(out.logits, labels)


@torch.no_grad()
def answer_loglik(
    cfg: dict[str, Any], model, sample: dict[str, Any], answer: str, collate
) -> float:
    s = dict(sample)
    s["answer"] = answer
    with autocast(cfg):
        return float(batch_answer_loglik(model, collate([s]))[0])


@torch.no_grad()
def generate_texts(
    model, batch: list[dict[str, Any]], max_new_tokens: int, **gen_kwargs
) -> list[str]:
    """Batched generation with LEFT padding.

    OpenTSLM pads prompts on the right (fine for teacher-forced loss), but then generation for the shorter prompts
    in a batch starts after pad tokens and comes out garbled / mid-sentence. Flamingo: flip the tokenizer's padding
    side for the call. SP: roll each right-padded embedding row so its padding moves to the front, then call the
    LLM's generate directly (mirrors OpenTSLMSP.generate).
    """
    if hasattr(model, "text_tokenizer"):  # OpenTSLMFlamingo
        tok = model.text_tokenizer
        side = tok.padding_side
        tok.padding_side = "left"
        try:
            return model.generate(batch, max_new_tokens=max_new_tokens, **gen_kwargs)
        finally:
            tok.padding_side = side
    inputs_embeds, attention_mask = model.pad_and_apply_batch(batch)
    B, L, _ = inputs_embeds.shape
    lengths = attention_mask.sum(dim=1).long()
    left_embeds = torch.zeros_like(inputs_embeds)
    left_mask = torch.zeros_like(attention_mask)
    for i in range(B):
        n = int(lengths[i])
        left_embeds[i, L - n :] = inputs_embeds[i, :n]
        left_mask[i, L - n :] = 1
    gen_ids = model.llm.generate(
        inputs_embeds=left_embeds,
        attention_mask=left_mask,
        max_new_tokens=max_new_tokens,
        pad_token_id=model.tokenizer.pad_token_id,
        **gen_kwargs,
    )
    return model.tokenizer.batch_decode(gen_ids, skip_special_tokens=True)


def evidence_prefix(text: str) -> str:
    """Generated text up to (not including) its last 'Answer' — the reasoning part, whitespace-trimmed."""
    i = text.lower().rfind("answer")
    return (text if i < 0 else text[:i]).strip()


_CONCLUSION_RE = re.compile(
    r"\s*(This pattern precedes[^.]*\.|This is consistent with[^.]*\.|No sign of a developing fault\.|"
    r"Nothing here points to an imminent fault stop\.|No specific precursor[^.]*\.|The signals show no specific precursor[^.]*\.)\s*$"
)


def evidence_without_conclusion(text: str) -> str:
    """The model's evidence sentences: generated text before 'Answer', minus a trailing conclusion sentence."""
    return _CONCLUSION_RE.sub("", evidence_prefix(text)).strip()


def conclusion_candidates(
    model, classes: tuple[str, ...]
) -> tuple[list[str], list[int]]:
    """Conclusion + Answer candidates (t1); returns (texts, is_yes flags). Index 0/1 = the two 'no' conclusions."""
    from turbine_tslm.data.evidence import CONCLUSION

    eos = model.get_eos_token()
    cands = [
        f"No sign of a developing fault.\nAnswer: no{eos}",
        f"Nothing here points to an imminent fault stop.\nAnswer: no{eos}",
    ]
    flags = [0, 0]
    for c in classes:
        concl = CONCLUSION.get(
            c, f"This pattern precedes a {c.replace('_', ' ')} stop."
        )
        cands.append(f"{concl}\nAnswer: yes, {c}{eos}")
        cands.append(
            f"No specific precursor for it is visible in these signals, but a {c.replace('_', ' ')} stop follows.\nAnswer: yes, {c}{eos}"
        )
        flags += [1, 1]
    return cands, flags


@torch.no_grad()
def rescore(cfg: dict[str, Any], model, sets, collate, out_path: Path) -> None:
    """Graded P(yes) for an evidence model from its own generated texts (see DEFAULTS['rescore_from'])."""
    from turbine_tslm.data.taxonomy import fault_classes

    model.eval()
    classes = fault_classes()
    cands, flags = conclusion_candidates(model, classes)
    flags_t = torch.tensor(flags, dtype=torch.bool)
    prev = {}
    for line in Path(cfg["rescore_from"]).read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            prev[r["window_id"]] = r
    samples = [
        s
        for d in (sets["validation"], sets["test"])
        for s in d
        if s["window_id"] in prev and s.get("task", "t1") == "t1"
    ]
    print(
        f"[rescore] {len(samples)} t1 records from {cfg['rescore_from']}, {len(cands)} candidates each"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    bs = cfg["eval_batch_size"]
    t0 = time.time()
    with open(out_path, "w", encoding="utf-8") as fh:
        for i in range(0, len(samples), bs):
            chunk = samples[i : i + bs]
            prefixes = [
                evidence_without_conclusion(prev[s["window_id"]]["text"]) for s in chunk
            ]
            ll = score_candidates(cfg, model, chunk, cands, collate, prefixes)
            probs = torch.softmax(ll, dim=1)
            for s, p in zip(chunk, probs, strict=True):
                rec = dict(prev[s["window_id"]])
                p_yes = float(p[flags_t].sum())
                per_class = {
                    c: float(p[2 + 2 * k] + p[3 + 2 * k]) for k, c in enumerate(classes)
                }
                tot = max(sum(per_class.values()), 1e-12)
                rec["score"] = p_yes
                rec["score_generate_mode"] = prev[s["window_id"]].get("score")
                rec["class_scores"] = {c: v / tot for c, v in per_class.items()}
                fh.write(json.dumps(rec) + "\n")
            if (i // bs) % 20 == 0:
                print(
                    f"[rescore] {i + len(chunk)}/{len(samples)} ({time.time() - t0:.0f}s)",
                    flush=True,
                )
        # t3 and any records without text pass through unchanged
        for wid, r in prev.items():
            if r.get("task") == "t3":
                fh.write(json.dumps(r) + "\n")


def candidate_answers(model, classes: tuple[str, ...], task: str = "t1") -> list[str]:
    """t1: 'no' + one 'yes, <class>' per class (index 0 = no); t3: one 'Answer: <class>' per class."""
    eos = model.get_eos_token()
    if task == "t3":
        return [f"Answer: {c}{eos}" for c in classes]
    return [f"Answer: no{eos}"] + [f"Answer: yes, {c}{eos}" for c in classes]


def fill_record(
    rec: dict[str, Any], p: torch.Tensor, task: str, classes: tuple[str, ...]
) -> None:
    """score / label / class_scores from the candidate probabilities (t1: index 0 is 'no'; t3: classes only)."""
    if task == "t3":
        cls_p = p
        rec["score"] = 1.0  # every t3 record is a real stop; only the class is scored
    else:
        rec["score"] = float(1 - p[0])
        cls_p = p[1:] / max(float(p[1:].sum()), 1e-12)
    best = int(torch.argmax(cls_p))
    rec["label"] = classes[best] if task == "t3" or rec["score"] >= 0.5 else "none"
    rec["class_scores"] = {c: float(v) for c, v in zip(classes, cls_p, strict=True)}


@torch.no_grad()
def score_candidates(
    cfg: dict[str, Any],
    model,
    chunk: list[dict[str, Any]],
    cands: list[str],
    collate,
    prefixes=None,
) -> torch.Tensor:
    """(len(chunk), len(cands)) sum log-likelihoods, computed in sub-batches of score_batch_size sequences.

    ``prefixes`` (one string per chunk item, e.g. the model's own generated evidence) is prepended to every
    candidate, so the yes/no score is conditioned on the reasoning the model actually wrote.
    """
    seqs = []
    for j, s in enumerate(chunk):
        for c in cands:
            item = dict(s)
            item["answer"] = (prefixes[j] + " " if prefixes and prefixes[j] else "") + c
            seqs.append(item)
    out = []
    step = max(1, cfg["score_batch_size"])
    for i in range(0, len(seqs), step):
        with autocast(cfg):
            out.append(batch_answer_loglik(model, collate(seqs[i : i + step])).cpu())
    return torch.cat(out).view(len(chunk), len(cands))


@torch.no_grad()
def predict(cfg: dict[str, Any], model, sets, collate, out_path: Path) -> None:
    from turbine_tslm.data.taxonomy import fault_classes

    model.eval()
    wanted = set(cfg["eval_splits"])
    samples = [
        s for d in (sets["validation"], sets["test"]) for s in d if s["split"] in wanted
    ]
    samples.sort(
        key=lambda s: s.get("task", "t1")
    )  # chunks never mix tasks (different candidate sets)
    mode = cfg["predict_mode"]
    classes = fault_classes()
    print(f"[predict] {len(samples)} windows over {sorted(wanted)}, mode={mode}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    bs = cfg["eval_batch_size"]
    t0 = time.time()
    n_chunks = 0
    with open(out_path, "w", encoding="utf-8") as fh:
        i = 0
        while i < len(samples):
            chunk = samples[i : i + bs]
            task = chunk[0].get("task", "t1")
            if any(c.get("task", "t1") != task for c in chunk):
                chunk = chunk[
                    : next(
                        k for k, c in enumerate(chunk) if c.get("task", "t1") != task
                    )
                ]
            cands = candidate_answers(model, classes, task)
            recs = [
                {
                    "window_id": s["window_id"],
                    "task": task,
                    "split": s["split"],
                    "horizon_h": s["horizon_h"],
                    "gold": s["label"],
                }
                for s in chunk
            ]
            if mode in ("loglik", "both"):
                ll = score_candidates(cfg, model, chunk, cands, collate)
                probs = torch.softmax(ll, dim=1)
                for rec, p in zip(recs, probs, strict=True):
                    fill_record(rec, p, task, classes)
            if mode in ("generate", "both"):
                with autocast(cfg):
                    texts = generate_texts(model, collate(chunk), cfg["max_new_tokens"])
                for rec, text in zip(recs, texts, strict=True):
                    rec["text"] = text
                if mode == "generate":
                    # score the label candidates conditioned on the evidence the model wrote (text before "Answer")
                    prefixes = [evidence_prefix(t) for t in texts]
                    ll = score_candidates(cfg, model, chunk, cands, collate, prefixes)
                    probs = torch.softmax(ll, dim=1)
                    for rec, text, p in zip(recs, texts, probs, strict=True):
                        fill_record(rec, p, task, classes)
                        rec["label"] = scoring.parse_answer(
                            text
                        )  # what the model actually wrote
            for rec in recs:
                fh.write(json.dumps(rec) + "\n")
            i += len(chunk)
            n_chunks += 1
            if n_chunks % 20 == 1:
                print(
                    f"[predict] {i}/{len(samples)} ({time.time() - t0:.0f}s)",
                    flush=True,
                )


def score_predictions(cfg: dict[str, Any], pred_path: Path) -> dict[str, Any]:
    preds = scoring.load_predictions(pred_path)
    labels = scoring.load_labels(cfg["windows"], tasks=tuple(cfg["tasks"]))
    res = scoring.score(preds, labels)
    report = scoring.format_report(res, cfg["run_name"])
    print(report)
    out = Path(cfg["out_dir"])
    (out / "results.json").write_text(
        json.dumps(scoring._json_safe(res), indent=1), encoding="utf-8"
    )
    (out / "report.md").write_text(report + "\n", encoding="utf-8")
    return res


# --------------------------------------------------------------------------------------------- main


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("config", nargs="?", help="YAML config (keys = DEFAULTS)")
    ap.add_argument(
        "--set",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="override a config key",
    )
    ap.add_argument(
        "--predict-only",
        action="store_true",
        help="skip training; load best.pt and predict + score",
    )
    args = ap.parse_args(argv)
    cfg = load_config(args.config, args.set)
    set_seed(cfg["seed"])
    out = Path(cfg["out_dir"])
    out.mkdir(parents=True, exist_ok=True)
    (out / "config.yaml").write_text(yaml.safe_dump(cfg), encoding="utf-8")
    print(f"[config] {json.dumps({k: v for k, v in cfg.items() if k != 'windows'})}")
    log_fh = open(out / "train_log.jsonl", "a", encoding="utf-8")  # noqa: SIM115 — closed in main
    wb = None
    if cfg["wandb_project"]:
        netrc = Path.home() / ".netrc"
        if os.environ.get("WANDB_API_KEY") or (
            netrc.exists() and "wandb" in netrc.read_text(encoding="utf-8")
        ):
            import wandb

            wb = wandb.init(
                project=cfg["wandb_project"],
                name=cfg["run_name"],
                config=cfg,
                resume="allow",
            )
        else:
            print(
                "[wandb] no WANDB_API_KEY / ~/.netrc login found — logging to train_log.jsonl only",
                flush=True,
            )

    def log(rec: dict[str, Any]) -> None:
        log_fh.write(json.dumps(rec) + "\n")
        log_fh.flush()
        print(
            "[log] "
            + " ".join(
                f"{k}={v:.4g}" if isinstance(v, float) else f"{k}={v}"
                for k, v in rec.items()
            ),
            flush=True,
        )
        if wb is not None:
            wb.log({k: v for k, v in rec.items() if k != "step"}, step=rec.get("step"))

    model = build_model(cfg)
    sets, train_loader, val_loader, collate, extra_loaders = make_loaders(
        cfg, model.get_eos_token()
    )
    best = Path(cfg["checkpoint_dir"]) / "best.pt"
    if args.predict_only:
        if not best.exists():
            raise SystemExit(f"--predict-only needs {best}")
    else:
        best = train(cfg, model, train_loader, val_loader, log, extra_loaders)
    meta = load_checkpoint(model, best)
    print(f"[predict] using {best} ({meta})")
    pred_path = out / "predictions.jsonl"
    if cfg["predict_dtype"] and cfg["model_type"] == "OpenTSLMFlamingo":
        model.to(getattr(torch, cfg["predict_dtype"]))
    if cfg["predict_mode"] == "rescore":
        rescore(cfg, model, sets, collate, pred_path)
    else:
        predict(cfg, model, sets, collate, pred_path)
    res = score_predictions(cfg, pred_path)
    if wb is not None:
        summary = {}
        for split, per_h in res["results"].items():
            for h, m in per_h.items():
                for k in ("auroc", "ap", "recall_at_10far", "recall_at_5far"):
                    summary[f"{split}/h{h}/{k}"] = m[k]
                summary[f"{split}/h{h}/subsystem_macro_f1"] = m["subsystem"][
                    "macro_f1_over_positives"
                ]
        wb.log(summary)
        wb.finish()
    log_fh.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
