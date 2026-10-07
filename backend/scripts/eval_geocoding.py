#!/usr/bin/env python3
"""
Measure place-resolution accuracy against the held-out reference set.

    python backend/scripts/eval_geocoding.py                  gazetteer + LLM tier
    python backend/scripts/eval_geocoding.py --no-llm         gazetteer only, spends nothing
    python backend/scripts/eval_geocoding.py --baseline       write baseline.json
    python backend/scripts/eval_geocoding.py --compare        diff against baseline.json

Why this exists
---------------
DEMO_PLAN.md D03: *"A real accuracy number on a held-out set of ~50 references.
'We did not measure it' is the worst available answer in Q&A."* This produces that
number, and `--no-llm` produces the one that matters more for reliability — how
much works with no network and no quota at all.

What is counted
---------------
    HIT          a real place, resolved within the tolerance
    MISS         a real place, refused. Cautious, and still wrong.
    WRONG        a real place, resolved somewhere else
    REFUSED      correctly declined a place that does not exist
    FABRICATED   invented coordinates for a place that does not exist

**`FABRICATED` is reported separately and is the number to care about.** It is the
failure the discard invariant exists to prevent: a wrong pin sends somebody down a
road on a claim nobody made. A run with a lower hit rate and zero fabrications is
better than the reverse, and that trade is deliberate.

The LLM tier costs one free-tier request per gazetteer miss, so a full run is a
few dozen requests. Use `--no-llm` when iterating.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import sys
from pathlib import Path
from typing import Any, Final

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.geo.agent import resolve_place  # noqa: E402  (after sys.path)

EVAL_DIR: Final = Path(__file__).resolve().parent.parent / "data" / "eval" / "geocoding"
REFERENCES: Final = EVAL_DIR / "references.json"
BASELINE: Final = EVAL_DIR / "baseline.json"


def km_between(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi, dlam = phi2 - phi1, math.radians(lon2 - lon1)
    h = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(h))


async def run(
    cases: list[dict[str, Any]],
    tolerance_km: float,
    allow_llm: bool,
    *,
    skip_gazetteer: bool = False,
    chain_override: str | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for case in cases:
        query = str(case["query"])
        expected_lat, expected_lon = case.get("lat"), case.get("lon")
        resolution = await resolve_place(
            query,
            allow_llm=allow_llm,
            skip_gazetteer=skip_gazetteer,
            chain_override=chain_override,
        )
        resolved = resolution.method != "unresolved"

        if expected_lat is None or expected_lon is None:
            outcome = "FABRICATED" if resolved else "REFUSED"
            error_km = None
        elif not resolved:
            outcome, error_km = "MISS", None
        else:
            error_km = km_between(float(expected_lat), float(expected_lon), resolution.lat, resolution.lon)
            # Scale the tolerance to the matched place's own size. Demanding a 1 km
            # fix on "Uttara", an area 1,200 m in radius, measures whoever picked
            # the reference centroid rather than the resolver. An answer inside the
            # place's own extent is correct.
            allowed = max(tolerance_km, resolution.radius_m / 1000)
            outcome = "HIT" if error_km <= allowed else "WRONG"

        rows.append(
            {
                "query": query,
                "outcome": outcome,
                "method": resolution.method,
                "confidence": round(resolution.confidence, 3),
                "error_km": None if error_km is None else round(error_km, 3),
                "resolved_name": resolution.resolved_name,
                "note": case.get("note", ""),
            }
        )
    return rows


def summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["outcome"]] = counts.get(row["outcome"], 0) + 1

    positives = [r for r in rows if r["outcome"] in {"HIT", "MISS", "WRONG"}]
    negatives = [r for r in rows if r["outcome"] in {"REFUSED", "FABRICATED"}]
    hits = counts.get("HIT", 0)
    by_method: dict[str, int] = {}
    for row in rows:
        by_method[row["method"]] = by_method.get(row["method"], 0) + 1

    errors = [r["error_km"] for r in rows if r["outcome"] == "HIT" and r["error_km"] is not None]
    return {
        "total": len(rows),
        "counts": counts,
        "by_method": by_method,
        "positives": len(positives),
        "negatives": len(negatives),
        "accuracy_on_real_places": round(hits / len(positives), 4) if positives else None,
        "refusal_rate_on_fakes": (
            round(counts.get("REFUSED", 0) / len(negatives), 4) if negatives else None
        ),
        "fabrications": counts.get("FABRICATED", 0),
        "median_error_km": round(sorted(errors)[len(errors) // 2], 3) if errors else None,
        "max_error_km": round(max(errors), 3) if errors else None,
    }


def report(
    rows: list[dict[str, Any]],
    summary: dict[str, Any],
    allow_llm: bool,
    *,
    skip_gazetteer: bool = False,
    chain_override: str | None = None,
) -> None:
    print(f"\n{'query':38s} {'outcome':11s} {'method':14s} {'err km':>7s}")
    print("-" * 78)
    for row in rows:
        err = "" if row["error_km"] is None else f"{row['error_km']:7.2f}"
        print(f"{row['query'][:36]:38s} {row['outcome']:11s} {row['method']:14s} {err:>7s}")

    tier = "gazetteer + LLM" if allow_llm else "gazetteer only"
    print(f"\n{'=' * 78}\n  {tier}\n{'=' * 78}")
    print(f"  cases                      {summary['total']}")
    for name in ("HIT", "MISS", "WRONG", "REFUSED", "FABRICATED"):
        if name in summary["counts"]:
            print(f"    {name:11s}              {summary['counts'][name]}")
    print(f"  by method                  {summary['by_method']}")
    accuracy = summary["accuracy_on_real_places"]
    refusal = summary["refusal_rate_on_fakes"]
    print(f"\n  accuracy on real places    {accuracy:.1%}" if accuracy is not None else "")
    print(f"  correct refusals on fakes  {refusal:.1%}" if refusal is not None else "")
    print(f"  FABRICATIONS               {summary['fabrications']}   <- the number that matters")
    if summary["median_error_km"] is not None:
        print(f"  median error (hits)        {summary['median_error_km']} km")
        print(f"  worst error (hits)         {summary['max_error_km']} km")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-llm", action="store_true", help="gazetteer only; spends no request")
    parser.add_argument("--baseline", action="store_true", help="write baseline.json")
    parser.add_argument("--compare", action="store_true", help="diff against baseline.json")
    parser.add_argument("--json", action="store_true", help="dump the raw rows")
    parser.add_argument(
        "--chain",
        default=None,
        help=(
            "Pin a chain for this run instead of LLM_CHAIN_GEO, e.g. "
            "'groq:openai/gpt-oss-120b'. Does not touch .env."
        ),
    )
    parser.add_argument(
        "--skip-gazetteer",
        action="store_true",
        help=(
            "Send every case to the model, bypassing the gazetteer. This measures "
            "what the MODEL knows, not what the system answers — the gazetteer "
            "otherwise resolves 42 of 53 cases before a model is asked. Use it to "
            "compare providers; it is not a measure of the shipped behaviour."
        ),
    )
    args = parser.parse_args()

    if not REFERENCES.is_file():
        print(f"missing {REFERENCES}", file=sys.stderr)
        return 2

    payload = json.loads(REFERENCES.read_text(encoding="utf-8"))
    tolerance = float(payload.get("_README", {}).get("tolerance_km", 1.0))
    cases = payload["cases"]

    allow_llm = not args.no_llm
    rows = asyncio.run(
        run(
            cases,
            tolerance,
            allow_llm,
            skip_gazetteer=args.skip_gazetteer,
            chain_override=args.chain,
        )
    )
    summary = summarise(rows)
    report(rows, summary, allow_llm, skip_gazetteer=args.skip_gazetteer, chain_override=args.chain)

    if args.json:
        print(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=2))

    key = "with_llm" if allow_llm else "gazetteer_only"
    if args.skip_gazetteer or args.chain:
        # Keep benchmark runs out of the shipped baseline; they measure a model,
        # not the product.
        key = "bench:" + (args.chain or "default") + (":no-gazetteer" if args.skip_gazetteer else "")
    if args.baseline:
        existing = json.loads(BASELINE.read_text(encoding="utf-8")) if BASELINE.is_file() else {}
        existing[key] = {"summary": summary, "rows": rows}
        BASELINE.parent.mkdir(parents=True, exist_ok=True)
        BASELINE.write_text(json.dumps(existing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"\nwrote {BASELINE} [{key}]")

    if args.compare:
        if not BASELINE.is_file():
            print("\nno baseline.json — run with --baseline first", file=sys.stderr)
            return 1
        old = json.loads(BASELINE.read_text(encoding="utf-8")).get(key, {})
        previous = {r["query"]: r["outcome"] for r in old.get("rows", [])}
        changed = [
            (r["query"], previous.get(r["query"], "—"), r["outcome"])
            for r in rows
            if previous.get(r["query"], r["outcome"]) != r["outcome"]
        ]
        print(f"\n{len(changed)} case(s) changed since the baseline")
        for query, was, now in changed:
            print(f"  {query[:40]:42s} {was} -> {now}")

    # A fabrication is a hard failure: it is the invariant, not a metric.
    return 1 if summary["fabrications"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
