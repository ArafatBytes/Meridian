#!/usr/bin/env python3
"""
Delete what has outlived its retention window. B14.

    python scripts/purge_expired.py                 what WOULD go. Deletes nothing.
    python scripts/purge_expired.py --apply         delete, DERIVED windows only
    python scripts/purge_expired.py --apply --force ... including PROPOSED windows
    python scripts/purge_expired.py --table journeys

`app/privacy/retention.py` holds the rules; this is the only thing that acts on
them. `agents/expiry_sweep.py` is the other half of the pair and does something
different: it marks rows `expired` and **keeps** them, because an expired row is
the evidence that the surface retires things on its own. Stopping serving a row
and deleting it are two promises, and the concept document's §9 minimisation
clause is the second one.

## Three refusals, on purpose

**Dry run is the default.** `--apply` is the only way to delete. A script whose
default action is destructive gets run by accident exactly once.

**A `PROPOSED` window will not delete without `--force`.** Four of the six
windows are a judgement nobody has signed off, and a retention period is a
decision about somebody else's data. `--force` exists so that signing off does
not require editing the registry first, but it has to be typed.

**It is not scheduled.** There is deliberately no `beat_schedule` entry. A cron
job that deletes user data on a window nobody agreed to is the failure this whole
module is meant to prevent, and `agents/registry.py` is where someone would add
it once the windows are settled.

## The naive-timestamp wart

Eight columns here are `timestamp without time zone` -- `crime_reports` (3),
`sos_incidents` (2), `user_locations.timestamp` and `users` (2) -- while the rest
of the schema is `timestamptz`. Those are interpreted as UTC **explicitly** below
rather than by trusting the session's TimeZone to stay UTC, because a window that
changed meaning with a server setting would be the wrong kind of quiet. The real
fix is a migration making the schema consistent.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.privacy.retention import (  # noqa: E402
    Basis,
    Retention,
    proposed_windows,
    tables_with_windows,
)


async def _naive_columns(db: object) -> set[tuple[str, str]]:
    """`(table, column)` pairs stored without a time zone. See the module docstring."""
    from sqlalchemy import text as sql

    rows = (
        await db.execute(  # type: ignore[attr-defined]
            sql(
                "select table_name, column_name from information_schema.columns "
                "where table_schema = 'public' "
                "and data_type = 'timestamp without time zone'"
            )
        )
    ).all()
    return {(row[0], row[1]) for row in rows}


def _predicate(rule: Retention, naive: set[tuple[str, str]]) -> str:
    """The `where` clause, with a naive column read as UTC."""
    assert rule.dated_by
    column = rule.dated_by
    if (rule.table, column) in naive:
        column = f"({column} at time zone 'UTC')"
    return f"{rule.dated_by} is not null and {column} < :cutoff"


async def main() -> int:
    parser = argparse.ArgumentParser(
        prog="purge_expired.py",
        description="Delete rows past their declared retention window.",
    )
    parser.add_argument(
        "--apply", action="store_true", help="actually delete; without it, nothing changes"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="include windows marked PROPOSED, which nobody has signed off",
    )
    parser.add_argument("--table", metavar="NAME", help="just this one table")
    args = parser.parse_args()

    rules = tables_with_windows()
    if args.table:
        rules = tuple(rule for rule in rules if rule.table == args.table)
        if not rules:
            known = ", ".join(sorted(r.table for r in tables_with_windows()))
            print(f"\n  error: no window declared for {args.table!r}. Known: {known}\n")
            return 2

    from sqlalchemy import text as sql

    from app.core.database import AsyncSessionLocal

    now = datetime.now(UTC)
    mode = "DELETING" if args.apply else "dry run — nothing will be deleted"
    print(f"\n  retention purge, {mode}")
    print(f"  {now.isoformat()}\n")

    skipped: list[str] = []
    total = 0

    async with AsyncSessionLocal() as db:
        naive = await _naive_columns(db)

        for rule in rules:
            assert rule.window
            cutoff = now - rule.window
            where = _predicate(rule, naive)
            count = (
                await db.execute(
                    sql(f"select count(*) from public.{rule.table} where {where}"),  # noqa: S608
                    {"cutoff": cutoff},
                )
            ).scalar_one()

            tag = rule.basis.value if rule.basis else "?"
            line = f"  {rule.table:22} {rule.window.days:4}d  {count:6} row(s) past it  [{tag}]"

            if not count:
                print(line)
                continue

            if rule.basis is Basis.PROPOSED and not args.force:
                print(f"{line}  REFUSED — PROPOSED window, needs --force")
                skipped.append(rule.table)
                continue

            if not args.apply:
                print(f"{line}  would delete")
                total += count
                continue

            await db.execute(
                sql(f"delete from public.{rule.table} where {where}"),  # noqa: S608
                {"cutoff": cutoff},
            )
            await db.commit()
            print(f"{line}  DELETED")
            total += count

    print()
    if skipped:
        print(f"  {len(skipped)} table(s) refused for want of sign-off: {', '.join(skipped)}")
        print("  Decide the window, mark it DERIVED in app/privacy/retention.py, or pass --force.")
    if not args.apply:
        print(f"  {total} row(s) would be deleted. Re-run with --apply.")
    else:
        print(f"  {total} row(s) deleted.")

    still_proposed = [rule.table for rule in proposed_windows()]
    if still_proposed:
        print(f"\n  ⚠️  windows still PROPOSED: {', '.join(still_proposed)}")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
