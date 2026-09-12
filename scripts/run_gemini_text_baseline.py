"""Run the zero-shot Gemini text-only baseline on committed turbine windows.

Only summaries of values at or before the anchor are sent to Gemini.  The
output JSONL is resumable: rerun after a rate limit or interruption and rows
whose ``window_id`` is already present will be skipped.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import numpy as np
import pandas as pd

from turbine_tslm.data.channels import CHANNEL_NAMES

# Gemini's model-list endpoint may retain retired aliases; use the current
# successor returned by the API for this account (September 2026).
MODEL = "gemini-3.6-flash"
CLASSES = [
    "none",
    "generator_cooling",
    "gearbox_lubrication",
    "pitch_system",
    "converter_grid",
    "structural_overspeed",
    "brake_hydraulics",
    "yaw_cable",
]


def load_dotenv_key(path: Path = Path(".env")) -> str:
    """Load GEMINI_API_KEY without printing or placing it in a subprocess."""
    key = os.environ.get("GEMINI_API_KEY")
    if key:
        return key
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            name, separator, value = line.partition("=")
            if separator and name.strip() == "GEMINI_API_KEY":
                return value.strip().strip('"').strip("'")
    raise RuntimeError("GEMINI_API_KEY is not set in the environment or .env")


def slope(values: np.ndarray) -> float:
    x = np.arange(len(values), dtype=float)
    x -= x.mean()
    return float(np.dot(values, x) / np.dot(x, x))


def describe(values: np.ndarray) -> str:
    pieces = []
    for name, width in (("1h", 6), ("6h", 36), ("24h", 144)):
        part = values[-width:]
        pieces.append(
            f"{name}[mean={part.mean():.3g},sd={part.std():.3g},min={part.min():.3g},"
            f"max={part.max():.3g},slope={slope(part):.3g}]"
        )
    return "; ".join(pieces) + f"; delta24={values[-1] - values[0]:.3g}"


def window_prompt(row: pd.Series) -> str:
    readings = {
        channel: np.asarray(row[channel], dtype=float) for channel in CHANNEL_NAMES
    }
    lines = [f"- {channel}: {describe(values)}" for channel, values in readings.items()]
    ambient = readings["ambient_temperature"]
    for channel, values in readings.items():
        if channel != "ambient_temperature" and "temperature" in channel:
            delta = values - ambient
            lines.append(
                f"- {channel}_minus_ambient: 6h_mean={delta[-36:].mean():.3g}, "
                f"24h_mean={delta.mean():.3g}, delta24={delta[-1] - delta[0]:.3g}"
            )
    return "\n".join(
        [
            "You are a benchmark classifier for wind turbine fault-stop early warning.",
            f"Question: will a fault-class stop start in the next {int(row.horizon_h)} hours?",
            f"Anchor operating state: {row.state_at_anchor}. Month: {pd.Timestamp(row.anchor).month}.",
            "Below are summaries of the preceding 24 hours only; no alarm logs or future information are available.",
            *lines,
            (
                "Return only JSON matching the requested schema. score_positive is your calibrated probability that "
                "a fault-class stop starts in the requested horizon. pred_label must be the most likely class, or none."
            ),
        ]
    )


def request_prediction(api_key: str, row: pd.Series) -> dict[str, object]:
    schema = {
        "type": "object",
        "properties": {
            "pred_label": {"type": "string", "enum": CLASSES},
            "score_positive": {"type": "number", "minimum": 0, "maximum": 1},
        },
        "required": ["pred_label", "score_positive"],
        "additionalProperties": False,
    }
    body = {
        "contents": [{"role": "user", "parts": [{"text": window_prompt(row)}]}],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "application/json",
            "responseJsonSchema": schema,
        },
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={api_key}"
    payload = json.dumps(body).encode("utf-8")
    for attempt in range(5):
        try:
            request = Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(request, timeout=90) as response:
                response_body = json.load(response)
            text = response_body["candidates"][0]["content"]["parts"][0]["text"]
            result = json.loads(text)
            label, score = result["pred_label"], float(result["score_positive"])
            if label not in CLASSES or not 0 <= score <= 1:
                raise ValueError(f"Invalid structured response: {result!r}")
            return {"pred_label": label, "score_positive": score}
        except (HTTPError, URLError, KeyError, ValueError, json.JSONDecodeError) as exc:
            if attempt == 4:
                raise RuntimeError(
                    f"Gemini request failed after retries: {exc}"
                ) from exc
            time.sleep(2**attempt)
    raise AssertionError("unreachable")


def existing_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {
        json.loads(line)["window_id"]
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", choices=("test_a", "test_b"), required=True)
    parser.add_argument(
        "--workers",
        type=int,
        default=2,
        help="Concurrent requests; start low for API rate limits.",
    )
    parser.add_argument(
        "--limit", type=int, help="Maximum new rows (useful for a smoke test)."
    )
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/predictions"))
    args = parser.parse_args()
    api_key = load_dotenv_key()
    source = (
        "data/interim/penmanshiel_windows.parquet"
        if args.split == "test_a"
        else "data/interim/kelmarsh_windows.parquet"
    )
    frame = pd.read_parquet(source)
    frame = frame[frame["split"] == args.split] if "split" in frame else frame
    output = args.output_dir / f"gemini_3_6_flash_text_v1_{args.split}.jsonl"
    done = existing_ids(output)
    todo = frame[~frame.window_id.isin(done)]
    if args.limit:
        todo = todo.head(args.limit)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    print(
        f"{args.split}: {len(done)} complete; sending {len(todo)} new windows to {MODEL}"
    )
    with (
        output.open("a", encoding="utf-8") as handle,
        ThreadPoolExecutor(max_workers=args.workers) as pool,
    ):
        futures = {
            pool.submit(request_prediction, api_key, row): row.window_id
            for _, row in todo.iterrows()
        }
        for number, future in enumerate(as_completed(futures), start=1):
            window_id = futures[future]
            prediction = future.result()
            handle.write(
                json.dumps(
                    {
                        "window_id": window_id,
                        "model": "gemini_3_6_flash_text_v1",
                        **prediction,
                    }
                )
                + "\n"
            )
            handle.flush()
            if number % 10 == 0 or number == len(futures):
                print(f"{args.split}: {number}/{len(futures)} newly completed")


if __name__ == "__main__":
    main()
