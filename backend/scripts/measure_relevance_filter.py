#!/usr/bin/env python3
"""
What does the news relevance filter actually accept and reject? — D04.

    python scripts/measure_relevance_filter.py collect       list sitemaps, apply the filter
    python scripts/measure_relevance_filter.py collect --out sample.json
    python scripts/measure_relevance_filter.py score         precision/recall against labels

`live_risk.is_relevant` decides, from the headline alone, whether an article is
worth fetching. Recent `live_risk` runs read `in=0 out=0`, and roughly **1%** of
~390 listed articles per run pass. The number on its own says nothing about
whether that is right: 1% could be a correctly tight filter on a quiet news day,
or it could be throwing away most of Dhaka.

The filter's own docstrings record failures in **both** directions, which is why
this script exists rather than a decision to loosen it:

* **Too loose.** A Houthi drone strike on Saudi Aramco passed. So did *"US women
  rally to draw 2-2 with Spain"* — `names_an_incident` matched "rally", which in
  Dhaka copy means a political procession that closes a road, and in sports copy
  means coming back from behind.
* **Too tight.** It is a keyword list against a headline. A Dhaka incident whose
  headline uses a word nobody listed is invisible, and unlike a gazetteer miss it
  leaves no trace: the article is never fetched, so it never reaches
  `raw_documents` and never gets a `discarded_reason`. **Rejections are not
  recorded anywhere**, which is precisely why recall cannot be measured from the
  database and this script has to list the sitemaps itself.

## Why collecting and scoring are separate commands

`collect` fetches sitemaps only — no article bodies, so it is cheap and polite —
and writes every ref with the filter's verdict and which sub-matcher fired. It
labels nothing. A human then sets `"relevant"` on each row, and `score` reports
precision and recall against those labels.

Splitting them keeps the labels honest. If one command both collected and scored,
the temptation would be to label while watching the verdict, and a label agreeing
with the thing it is meant to judge measures nothing. The verdict is in the file
because the point is to find disagreements, but `score` reports how many rows are
still unlabelled so a partially labelled sample cannot masquerade as a full one.

## What a good result looks like

**Not a higher pass rate.** Recall matters more than precision here, but not
without limit: a false negative silently loses a real incident, while a false
positive costs one fetch and one extraction, and the extraction stage already
rejects irrelevant articles (`live_risk` logs them as `rejected`). So the filter
should lean loose — but every article it passes spends part of
`MAX_EXTRACTIONS_PER_RUN`, which is the free tier, so a filter that passes
everything starves the real incidents of budget. Both numbers, reported together.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agents.live_risk import (  # noqa: E402
    EXCLUDED_SECTIONS,
    LOOKBACK,
    is_relevant,
    names_a_crime,
    names_an_incident,
)
from app.ingestion.sources import SOURCES, publisher_name  # noqa: E402
from app.ingestion.sources.base import ArticleRef  # noqa: E402

DEFAULT_OUT = Path(__file__).resolve().parent.parent / "data" / "eval" / "relevance" / "sample.json"


def verdict_for(ref: ArticleRef, now: datetime) -> dict[str, Any]:
    """
    The filter's answer, plus *why* — the reason is what makes a disagreement
    actionable rather than just visible.

    `is_relevant` is called rather than reimplemented, so this cannot drift from
    the thing it measures. The sub-reasons are recomputed alongside it; they are
    cheap and pure.
    """
    stale = ref.published_at is not None and ref.published_at < now - LOOKBACK
    return {
        "passed": is_relevant(ref, now),
        "excluded_section": ref.section in EXCLUDED_SECTIONS,
        "too_old": stale,
        "names_incident": names_an_incident(ref.title),
        "names_crime": names_a_crime(ref.title),
    }


async def collect(args: argparse.Namespace) -> int:
    from app.ingestion.fetcher import Fetcher

    now = datetime.now(UTC)
    rows: list[dict[str, Any]] = []
    failures: list[str] = []

    async with Fetcher() as fetcher:
        for source in SOURCES:
            try:
                refs = await source.list_recent(fetcher, now)
            except Exception as problem:  # noqa: BLE001 - one publisher must not stop the rest
                failures.append(f"{source.source_id}: {type(problem).__name__}: {problem}")
                print(f"  {source.source_id:22} FAILED  {type(problem).__name__}", flush=True)
                continue

            for ref in refs:
                rows.append(
                    {
                        "publisher": source.source_id,
                        "publisher_name": publisher_name(source.source_id),
                        "title": ref.title,
                        "url": ref.url,
                        "section": ref.section,
                        "published_at": ref.published_at.isoformat() if ref.published_at else None,
                        **verdict_for(ref, now),
                        # Set this by hand: true, false, or null for "not yet judged".
                        "relevant": None,
                    }
                )
            passed = sum(1 for row in rows[-len(refs) :] if row["passed"]) if refs else 0
            print(f"  {source.source_id:22} {len(refs):4} listed  {passed:3} passed", flush=True)

    out = Path(args.out) if args.out else DEFAULT_OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    existing = _merge_labels(out, rows)
    out.write_text(
        json.dumps(
            {
                "collected_at": now.isoformat(),
                "lookback_hours": LOOKBACK.total_seconds() / 3600,
                "failures": failures,
                "rows": rows,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    total = len(rows)
    passed = sum(1 for row in rows if row["passed"])
    print(f"\n  {total} article(s) listed, {passed} passed the filter", end="")
    print(f" ({100 * passed / total:.1f}%)" if total else "")
    if existing:
        print(f"  {existing} label(s) carried over from the previous sample")
    print(f"  written to {out}")
    print("\n  Next: set \"relevant\" on each row by hand, then run `score`.\n")
    return 0


def _merge_labels(out: Path, rows: list[dict[str, Any]]) -> int:
    """
    Carry hand labels across a re-collect, keyed by URL.

    Labelling is the expensive half and the sitemaps move under it: a re-run an
    hour later re-lists most of the same articles. Without this, every collect
    would throw away the work. Keyed by URL rather than title because two
    publishers legitimately run the same headline.
    """
    if not out.is_file():
        return 0
    try:
        previous = json.loads(out.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0
    labels = {
        row["url"]: row["relevant"]
        for row in previous.get("rows", [])
        if row.get("relevant") is not None
    }
    carried = 0
    for row in rows:
        if row["url"] in labels:
            row["relevant"] = labels[row["url"]]
            carried += 1
    return carried


def score(args: argparse.Namespace) -> int:
    path = Path(args.out) if args.out else DEFAULT_OUT
    if not path.is_file():
        print(f"\n  error: no sample at {path}. Run `collect` first.\n", file=sys.stderr)
        return 2

    rows = json.loads(path.read_text(encoding="utf-8"))["rows"]

    if args.recompute:
        # Re-run the CURRENT filter over the stored sample instead of trusting the
        # verdict `collect` recorded. This is what makes a change measurable: the
        # labels are fixed and expensive, the sitemaps move hourly, so re-collecting
        # to test a tweak would compare two different populations and tell you
        # nothing. `published_at` is replayed as recorded, so the lookback is
        # evaluated against the collection time rather than now.
        collected = datetime.fromisoformat(
            json.loads(path.read_text(encoding="utf-8"))["collected_at"]
        )
        for row in rows:
            ref = ArticleRef(
                url=row["url"],
                title=row["title"],
                published_at=(
                    datetime.fromisoformat(row["published_at"]) if row["published_at"] else None
                ),
            )
            row.update(verdict_for(ref, collected))
        print("\n  verdicts RECOMPUTED from current code against the stored sample")

    labelled = [row for row in rows if row.get("relevant") is not None]
    print(f"\n  {len(rows)} row(s), {len(labelled)} labelled", end="")
    if not labelled:
        print(" — nothing to score yet.\n")
        return 1
    print(f" ({100 * len(labelled) / len(rows):.0f}%)")

    tp = sum(1 for r in labelled if r["relevant"] and r["passed"])
    fp = sum(1 for r in labelled if not r["relevant"] and r["passed"])
    fn = sum(1 for r in labelled if r["relevant"] and not r["passed"])
    tn = sum(1 for r in labelled if not r["relevant"] and not r["passed"])

    print(f"\n  passed and relevant      {tp:4}")
    print(f"  passed but irrelevant    {fp:4}   (costs one fetch + one extraction slot)")
    print(f"  rejected but relevant    {fn:4}   (a real incident, lost silently)")
    print(f"  rejected and irrelevant  {tn:4}")

    # Recall has to be reweighted, and getting this wrong is the trap this block
    # exists to avoid.
    #
    # Labelling is stratified, not random: every article the filter PASSED gets a
    # label, because that set is small and precision depends on all of it, while
    # the rejected set is sampled because there are thousands. The raw ratio then
    # flatters the filter badly -- on the first real run it read recall 0.90 when
    # the reweighted answer was 0.47, because 167 of 167 passed rows were labelled
    # against 250 of 2455 rejected ones, under-counting misses by a factor of ten.
    #
    # So each stratum's labelled count is scaled back up by its own sampling rate.
    # Precision needs no such correction: it is computed entirely within the
    # passed stratum, which is labelled in full.
    passed_total = sum(1 for r in rows if r["passed"])
    rejected_total = len(rows) - passed_total
    passed_labelled = sum(1 for r in labelled if r["passed"])
    rejected_labelled = len(labelled) - passed_labelled

    precision = tp / (tp + fp) if tp + fp else float("nan")
    print(f"\n  precision {precision:.2f}", end="")
    print(f"   ({tp} of {tp + fp} passed rows are real incidents)")

    if not rejected_labelled or not passed_labelled:
        print("  recall      — needs labels on both sides to estimate\n")
        return 0

    passed_rate = passed_labelled / passed_total
    rejected_rate = rejected_labelled / rejected_total
    est_tp = tp / passed_rate
    est_fn = fn / rejected_rate
    recall = est_tp / (est_tp + est_fn) if est_tp + est_fn else float("nan")

    print(f"  recall    {recall:.2f}", end="")
    print(f"   (reweighted: {passed_labelled}/{passed_total} passed and ", end="")
    print(f"{rejected_labelled}/{rejected_total} rejected rows labelled)")
    print(f"            estimates ~{est_fn:.0f} real incident(s) lost across all ", end="")
    print(f"{rejected_total} rejected articles")
    raw = tp / (tp + fn) if tp + fn else float("nan")
    print(f"            the UNweighted ratio would read {raw:.2f} — do not quote it")

    if fn:
        print("\n  Missed incidents — the expensive kind of error:")
        for row in [r for r in labelled if r["relevant"] and not r["passed"]][:20]:
            why = (
                "excluded section"
                if row["excluded_section"]
                else "too old"
                if row["too_old"]
                else "no keyword matched"
            )
            print(f"    [{why}] {row['title'][:90]}")

    if fp:
        print("\n  False alarms:")
        for row in [r for r in labelled if not r["relevant"] and r["passed"]][:20]:
            fired = "incident" if row["names_incident"] else "crime"
            print(f"    [{fired}] {row['title'][:90]}")

    missed_by_reason = Counter(
        "excluded section"
        if row["excluded_section"]
        else "too old"
        if row["too_old"]
        else "no keyword matched"
        for row in labelled
        if row["relevant"] and not row["passed"]
    )
    if missed_by_reason:
        print("\n  Misses by cause:")
        for reason, count in missed_by_reason.most_common():
            print(f"    {count:4}  {reason}")
    print()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="measure_relevance_filter.py",
        description="Measure live_risk.is_relevant against hand-labelled headlines.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    gather = sub.add_parser("collect", help="list sitemaps and apply the filter")
    gather.add_argument("--out", metavar="PATH", help=f"default: {DEFAULT_OUT}")

    rate = sub.add_parser("score", help="precision/recall against hand labels")
    rate.add_argument("--out", metavar="PATH", help=f"default: {DEFAULT_OUT}")
    rate.add_argument(
        "--recompute",
        action="store_true",
        help="re-run the current filter over the stored sample (A/B a change)",
    )

    args = parser.parse_args()
    if args.command == "score":
        return score(args)
    return asyncio.run(collect(args))


if __name__ == "__main__":
    raise SystemExit(main())
