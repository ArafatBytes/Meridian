"""
Measure the crime-vision pipeline against a labelled image set. D07, ADR 0006.

    docker exec meridian-api python scripts/eval_crime_vision.py
    docker exec meridian-api python scripts/eval_crime_vision.py --save-baseline
    docker exec meridian-api python scripts/eval_crime_vision.py --compare

**The gate metric changed in D07, and the old one is gone.** This script used to
report a *reachability* table -- which of the decision engine's 21 object signals
YOLOv9c could physically emit -- and the D07 gate was "6 of 6 classes reachable".
With a vision-language model that number is trivially true: a VLM can name any
category, so reachability measures nothing. It was deleted rather than left in,
because a gate that cannot fail is worse than no gate.

What replaced it:

* **false-accusation rate** -- of the photos labelled `none`, how many got a
  category proposed anyway. This is the number to quote in Q&A, because it is
  the answer to "what if your AI is wrong about a crime?"
* **abstention rate** -- how often it correctly proposes nothing.
* **detection recall** -- on photos that *should* flag. Zero of these exist in
  the seed set, which is the whole reason the eval set is the critical path.
* **the descriptions, printed in full** -- faithfulness is human-judged. A
  machine cannot score "is this sentence true about this photo", so the harness
  shows them and a person reads them.

The chain runs **without its replay tier** (`chain_without_replay`). If a
rehearsed photo were also an eval image, the cache would answer its own exam.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

# Run from backend/ so `app` is importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.llm.client import LLMUnavailable  # noqa: E402
from app.vision.analyze import analyze_photo  # noqa: E402
from app.vision.replay import chain_without_replay  # noqa: E402

EVAL_DIR = Path(__file__).resolve().parent.parent / "data" / "eval" / "crime_vision"
MANIFEST = EVAL_DIR / "manifest.csv"
IMAGES = EVAL_DIR / "images"
BASELINE = EVAL_DIR / "baseline.json"

BENIGN = "none"


def load_manifest() -> list[dict[str, str]]:
    if not MANIFEST.is_file():
        sys.exit(f"no manifest at {MANIFEST}")
    with MANIFEST.open(encoding="utf-8", newline="") as handle:
        return [row for row in csv.DictReader(handle) if row.get("image")]


async def run_one(row: dict[str, str]) -> dict[str, Any]:
    path = IMAGES / row["image"]
    if not path.is_file():
        return {"image": row["image"], "error": "missing file"}

    started = time.perf_counter()
    try:
        # `report_text` is deliberately not passed: the cross-check is a UI
        # corroboration hint, and feeding the label in would measure the label.
        result = await analyze_photo(path.read_bytes(), request_timeout=120.0)
    except LLMUnavailable as exhausted:
        return {"image": row["image"], "error": f"no tier answered: {exhausted}"}
    except Exception as problem:  # noqa: BLE001
        return {"image": row["image"], "error": f"{type(problem).__name__}: {problem}"}

    return {
        "image": row["image"],
        "expected": (row.get("expected") or "").strip() or BENIGN,
        "proposed": result.proposed_category,
        "confidence": result.confidence,
        "cues_fired": list(result.cues_fired),
        "people_count": result.cues.people_count,
        "scene": result.cues.scene,
        "description": result.cues.description,
        "engine": result.engine,
        "seconds": round(time.perf_counter() - started, 2),
    }


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ok = [r for r in rows if "error" not in r]
    errors = [r for r in rows if "error" in r]

    benign = [r for r in ok if r["expected"] == BENIGN]
    positive = [r for r in ok if r["expected"] != BENIGN]

    false_accusations = [r for r in benign if r["proposed"]]
    abstained = [r for r in benign if not r["proposed"]]
    detected = [r for r in positive if r["proposed"]]
    correct_category = [r for r in positive if r["proposed"] == r["expected"]]

    def rate(part: list, whole: list) -> float | None:
        return round(len(part) / len(whole), 3) if whole else None

    return {
        "images": len(rows),
        "analysed": len(ok),
        "errors": len(errors),
        "benign_images": len(benign),
        "positive_images": len(positive),
        # The headline number.
        "false_accusation_rate": rate(false_accusations, benign),
        "abstention_rate": rate(abstained, benign),
        # None when there are no positives yet, which is honest rather than 0.0.
        "detection_rate": rate(detected, positive),
        "correct_category_rate": rate(correct_category, positive),
        "engines": dict(Counter(r["engine"] for r in ok)),
        "mean_seconds": (
            round(sum(r["seconds"] for r in ok) / len(ok), 2) if ok else None
        ),
    }


def report(rows: list[dict[str, Any]], totals: dict[str, Any], chain: str) -> None:
    print()
    print("=" * 78)
    print("D07 crime vision — measured against %d image(s)" % totals["images"])
    print("chain (replay excluded): %s" % chain)
    print("=" * 78)

    print()
    print("PER IMAGE")
    for row in rows:
        if "error" in row:
            print("  %-32s ERROR  %s" % (row["image"][:32], row["error"][:40]))
            continue
        verdict = row["proposed"] or "-"
        mark = " "
        if row["expected"] == BENIGN and row["proposed"]:
            mark = "!"            # a false accusation
        elif row["expected"] != BENIGN and not row["proposed"]:
            mark = "x"            # a miss
        elif row["expected"] != BENIGN and row["proposed"] == row["expected"]:
            mark = "+"            # a hit
        print("  %s %-30s want %-10s got %-10s %-6s %5.1fs %s" % (
            mark, row["image"][:30], row["expected"], verdict,
            row["confidence"], row["seconds"], row["engine"]))

    print()
    print("DESCRIPTIONS — read these. Faithfulness is not machine-scorable.")
    for row in rows:
        if "error" not in row:
            print("  %-30s %s" % (row["image"][:30], row["description"]))

    print()
    print("NUMBERS")
    print("  benign images                 : %s" % totals["benign_images"])
    print("  false-accusation rate         : %s   <- the Q&A number" % _pct(totals["false_accusation_rate"]))
    print("  abstention rate               : %s" % _pct(totals["abstention_rate"]))
    print("  positive images               : %s" % totals["positive_images"])
    print("  detection rate                : %s" % _pct(totals["detection_rate"]))
    print("  correct category when detected: %s" % _pct(totals["correct_category_rate"]))
    print("  mean seconds per image        : %s" % totals["mean_seconds"])
    print("  answered by                   : %s" % totals["engines"])
    if totals["errors"]:
        print("  errors                        : %s" % totals["errors"])

    if not totals["positive_images"]:
        print()
        print("  ⚠️  EVERY IMAGE IN THIS SET IS BENIGN.")
        print("      So the numbers above measure abstention and nothing else —")
        print("      no evidence either model RECOGNISES a real confrontation.")
        print("      30-40 images, with positives, is the D07 gate. See DEMO_PLAN §9.3.")


def _pct(value: float | None) -> str:
    return "n/a (no such images)" if value is None else f"{value:.1%}"


def compare(totals: dict[str, Any]) -> int:
    if not BASELINE.is_file():
        print("\nno baseline yet — run with --save-baseline")
        return 0
    old = json.loads(BASELINE.read_text(encoding="utf-8"))
    previous = old.get("totals", old)
    print()
    print("AGAINST THE BASELINE (%s)" % old.get("captured_at", "unknown date"))
    worse = 0
    for key, better_is in (
        ("false_accusation_rate", "lower"),
        ("abstention_rate", "higher"),
        ("detection_rate", "higher"),
        ("correct_category_rate", "higher"),
    ):
        was, now = previous.get(key), totals.get(key)
        if was is None or now is None:
            print("  %-30s %s -> %s" % (key, _pct(was), _pct(now)))
            continue
        moved = now - was
        direction = "same"
        if abs(moved) > 1e-9:
            improved = (moved < 0) if better_is == "lower" else (moved > 0)
            direction = "better" if improved else "WORSE"
            if not improved:
                worse += 1
        print("  %-30s %s -> %s  (%s)" % (key, _pct(was), _pct(now), direction))
    if worse:
        print("\n  %d metric(s) regressed." % worse)
    return 1 if worse else 0


async def main_async(args: argparse.Namespace) -> int:
    chain = chain_without_replay()
    if not chain:
        sys.exit("LLM_CHAIN_CRIME has no model tiers — nothing to measure")

    manifest = load_manifest()
    rows = []
    for row in manifest:
        outcome = await run_one(row)
        rows.append(outcome)
        # Printed as it goes: on a cold local tier this takes ~9s per image, and
        # silence for several minutes looks like a hang.
        sys.stdout.write(".")
        sys.stdout.flush()

    totals = summarise(rows)
    report(rows, totals, chain)

    payload = {
        "captured_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "chain": chain,
        "totals": totals,
        "rows": rows,
    }
    if args.save_baseline:
        BASELINE.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
        print("\nbaseline written to %s" % BASELINE)
        return 0
    if args.compare:
        return compare(totals)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--save-baseline", action="store_true",
                        help="write this run to baseline.json")
    parser.add_argument("--compare", action="store_true",
                        help="compare against baseline.json; non-zero exit if anything regressed")
    return asyncio.run(main_async(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
