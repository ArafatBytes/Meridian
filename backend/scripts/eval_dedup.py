"""
Pick `DEDUP_SIMILARITY_THRESHOLD` from evidence instead of from taste.

    docker compose exec api python scripts/eval_dedup.py
    docker compose exec api python scripts/eval_dedup.py --json

Sweeps the threshold over `data/eval/dedup/clusters.json` and reports, at each step,
how many true duplicate pairs are merged (recall) and how many distinct events are
wrongly merged (precision). Prints the widest safe band and the midpoint of it.

---

## Why this script exists

`DEMO_PLAN.md` §9 declares `DEDUP_SIMILARITY_THRESHOLD=0.82`. Measured against
`all-MiniLM-L6-v2` on the text this system actually embeds -- the extraction model's
one-line English summaries -- **true duplicates score 0.70 to 0.75**. At 0.82 the
Rumour Guard merges nothing, so D05 would be a no-op that looked implemented: flags
would stay unconfirmed forever and reading four outlets would still produce four
pins. That is precisely the under-merging failure `agents/rumour_guard.py` warns
about, and nothing short of measurement would have caught it.

A threshold is a property of **the model and the text**, not of the problem. Changing
either -- a multilingual model, or embedding Bangla headlines instead of English
summaries -- invalidates the number and means re-running this.

## What is and is not being measured

Only the pairs that **reach** the embedding test. `find_duplicate()` applies three
cheap gates first: same `kind`, centroids within the larger radius (capped at 3 km),
and `observed_at` within `DEDUP_WINDOW_HOURS`. A fire in Gazipur and a fire in
Bangshal never get compared, so scoring that pair here would flatter the threshold
with a decision the SQL already made. The `hard_negatives` in the fixture are
therefore all same-kind, same-area, same-window -- the genuinely hard cases.
"""

from __future__ import annotations

import argparse
import itertools
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agents.rumour_guard import cosine_similarity, embed  # noqa: E402
from app.core.config import settings  # noqa: E402

CLUSTERS = Path(__file__).resolve().parent.parent / "data" / "eval" / "dedup" / "clusters.json"


def load() -> dict[str, Any]:
    return json.loads(CLUSTERS.read_text(encoding="utf-8"))


def pairs(data: dict[str, Any]) -> tuple[list[tuple[str, str, str]], list[tuple[str, str, str]]]:
    """(positives, negatives), each entry (label, text_a, text_b)."""
    positives: list[tuple[str, str, str]] = []
    for cluster in data["clusters"]:
        for a, b in itertools.combinations(cluster["members"], 2):
            positives.append((cluster["event"], a, b))

    negatives: list[tuple[str, str, str]] = [
        (n["why"], n["a"], n["b"]) for n in data["hard_negatives"]
    ]
    return positives, negatives


def score(positives: list[tuple[str, str, str]], negatives: list[tuple[str, str, str]]):
    texts = sorted({t for _, a, b in positives + negatives for t in (a, b)})
    vectors = embed(texts)
    if vectors is None:
        raise SystemExit(
            "no embedding model available -- cannot evaluate. "
            "See app/agents/rumour_guard.py :: embeddings_available()."
        )
    index = {text: vec for text, vec in zip(texts, vectors, strict=True)}

    pos = [(label, cosine_similarity(index[a], index[b])) for label, a, b in positives]
    neg = [(label, cosine_similarity(index[a], index[b])) for label, a, b in negatives]
    return pos, neg


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args()

    data = load()
    positives, negatives = pairs(data)
    pos, neg = score(positives, negatives)

    pos_scores = sorted(s for _, s in pos)
    neg_scores = sorted((s for _, s in neg), reverse=True)

    # The safe band: above every hard negative, at or below every true duplicate.
    floor = neg_scores[0] if neg_scores else 0.0        # highest false pair
    ceiling = pos_scores[0] if pos_scores else 1.0      # lowest true pair
    separated = ceiling > floor
    recommended = round((floor + ceiling) / 2, 2) if separated else None

    rows = []
    step = 0.02
    t = 0.50
    while t <= 0.92 + 1e-9:
        merged = sum(1 for _, s in pos if s >= t)
        wrong = sum(1 for _, s in neg if s >= t)
        rows.append(
            {
                "threshold": round(t, 2),
                "duplicates_merged": merged,
                "duplicates_total": len(pos),
                "recall": round(merged / len(pos), 3) if pos else 0.0,
                "false_merges": wrong,
                "negatives_total": len(neg),
            }
        )
        t += step

    report = {
        "model": settings.DEDUP_MODEL,
        "configured_threshold": settings.DEDUP_SIMILARITY_THRESHOLD,
        "true_pairs": len(pos),
        "hard_negative_pairs": len(neg),
        "lowest_true_duplicate": round(ceiling, 3),
        "highest_false_pair": round(floor, 3),
        "separated": separated,
        "recommended_threshold": recommended,
        "sweep": rows,
    }

    if args.json:
        print(json.dumps(report, indent=2))
        return 0

    print(f"model                  : {report['model']}")
    print(f"configured threshold   : {report['configured_threshold']}")
    print(f"true duplicate pairs   : {report['true_pairs']}")
    print(f"hard negative pairs    : {report['hard_negative_pairs']}")
    print()
    print("threshold  merged/true  recall  false merges")
    for row in rows:
        mark = "  <-- configured" if abs(row["threshold"] - settings.DEDUP_SIMILARITY_THRESHOLD) < 1e-9 else ""
        if recommended is not None and abs(row["threshold"] - recommended) < 1e-9:
            mark += "  <-- recommended"
        print(
            f"   {row['threshold']:.2f}      {row['duplicates_merged']:2d}/{row['duplicates_total']:<2d}"
            f"      {row['recall']:.2f}         {row['false_merges']}{mark}"
        )

    print()
    print(f"lowest TRUE duplicate  : {report['lowest_true_duplicate']}")
    print(f"highest FALSE pair     : {report['highest_false_pair']}")
    if separated:
        print(f"safe band              : {floor:.3f} < t <= {ceiling:.3f}")
        print(f"RECOMMENDED            : {recommended}")
    else:
        print(
            "NOT SEPARABLE: a hard negative scores at least as high as a true duplicate. "
            "No threshold divides them -- the model or the embedded text has to change, "
            "not the number."
        )

    print()
    print("worst true duplicates (closest to being missed):")
    for label, s in sorted(pos, key=lambda p: p[1])[:3]:
        print(f"  {s:.3f}  {label}")
    print("worst false pairs (closest to being merged):")
    for label, s in sorted(neg, key=lambda p: p[1], reverse=True)[:3]:
        print(f"  {s:.3f}  {label}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
