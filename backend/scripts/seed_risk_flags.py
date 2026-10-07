#!/usr/bin/env python3
"""
Load the risk-flag fixture into `risk_flags`.

    python backend/scripts/seed_risk_flags.py              insert over DATABASE_URL
    python backend/scripts/seed_risk_flags.py --sql        print SQL instead
    python backend/scripts/seed_risk_flags.py --sql --out seed.sql
    python backend/scripts/seed_risk_flags.py --keep       do not clear old seed rows

Where the flag text comes from
------------------------------
Not from the fixture. `data/fixtures/risk_flags.json` holds structured fields
only — kind, impact, place, coordinates, severity, half-life — and every
`mobility_statement` is produced here by `app.policy.framing`, at load time.

That is the whole point. A fixture with hand-written prose in it would be flag
text that never passed the framing guard, sitting in the demo database, looking
exactly like text that did. The invariant test would catch it, and the cheapest
way to make the test pass would be to loosen the test. This design removes that
temptation rather than relying on nobody taking it.

`expires_at` is likewise never written: the database derives it from
`observed_at`, `severity_0`, `half_life_hours` and `valid_to`. The INSERT below
simply does not mention the column.

Why the fixture uses relative times
-----------------------------------
`observed_offset_hours: -1.5` means "an hour and a half before this script ran".
Absolute timestamps would mean the seeded surface is correct on the day it was
written and entirely expired the following morning — which, for a fixture whose
job is to make the demo work on 24 October, would be the one failure that matters.

Rows this script writes all have an `event_key` starting `seed-`, and it clears
those before inserting. It never touches a flag produced by an agent.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

# Windows consoles default to cp1252, and both the migrations and the fixture
# contain em dashes, section signs and Bangla place names. Printing them to an
# unreconfigured stdout raises UnicodeEncodeError and the command dies having done
# nothing useful -- which is a particularly bad failure for a tool whose whole job
# is to hand you text to paste. Writing to a file was always fine (those use
# encoding="utf-8" explicitly); this fixes the stdout path.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except (AttributeError, OSError):
        pass  # not a real console, or already UTF-8

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.contracts.risk import IncidentKind, MobilityImpact  # noqa: E402
from app.policy.framing import to_mobility_statement  # noqa: E402

FIXTURE = BACKEND_DIR / "data" / "fixtures" / "risk_flags.json"
SEED_KEY_PREFIX = "seed-"

# Reuse the runner's connection handling rather than duplicating .env parsing and
# the asyncpg DSN translation.
sys.path.insert(0, str(BACKEND_DIR / "scripts"))
from migrate import connect  # noqa: E402


def sql_str(value: str) -> str:
    """A single-quoted SQL literal. Doubles embedded quotes; no other escaping."""
    return "'" + value.replace("'", "''") + "'"


def sql_ts(value: datetime) -> str:
    return sql_str(value.astimezone(UTC).isoformat())


def build_rows(now: datetime) -> list[dict[str, Any]]:
    """
    The fixture, resolved against `now` and framed.

    Returns plain dicts rather than `RiskFlag` models: a flag does not have a
    `flag_id` or an `expires_at` until the database has seen it, and constructing
    a `RiskFlag` here would mean inventing both.
    """
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []

    for entry in raw["flags"]:
        if "mobility_statement" in entry:
            raise SystemExit(
                f"\n  error: fixture entry {entry['event_key']!r} contains a "
                "'mobility_statement'.\n"
                "    Flag text is produced by app/policy/framing.py, never written by "
                "hand.\n    Remove the field; set 'mobility_impact' and 'place' instead.\n"
            )

        kind = IncidentKind(entry["kind"])
        impact = MobilityImpact(entry["mobility_impact"])
        observed_at = now + timedelta(hours=float(entry["observed_offset_hours"]))

        sources = [
            {
                "source_id": s["source_id"],
                "url": s["url"],
                "published_at": (
                    now + timedelta(hours=float(s["published_offset_hours"]))
                ).isoformat(),
                "title": s.get("title"),
                "snippet": s.get("snippet"),
            }
            for s in entry.get("sources", [])
        ]

        rows.append(
            {
                "event_key": entry["event_key"],
                "kind": kind.value,
                "status": entry.get("status", "unconfirmed"),
                "lat": float(entry["lat"]),
                "lon": float(entry["lon"]),
                "radius_m": int(entry["radius_m"]),
                "severity_0": float(entry["severity_0"]),
                "half_life_hours": float(entry["half_life_hours"]),
                "observed_at": observed_at,
                "valid_from": _offset_or_none(now, entry.get("valid_from_offset_hours")),
                "valid_to": _offset_or_none(now, entry.get("valid_to_offset_hours")),
                "source_count": int(entry.get("source_count", max(1, len(sources)))),
                "sources": sources,
                # The one and only writer of this string.
                "mobility_statement": to_mobility_statement(
                    kind=kind, impact=impact, place=entry.get("place")
                ),
            }
        )

    _check_consistency(rows)
    return rows


def _offset_or_none(now: datetime, offset: Any) -> datetime | None:
    return None if offset is None else now + timedelta(hours=float(offset))


def _check_consistency(rows: list[dict[str, Any]]) -> None:
    """
    Catch in the fixture what the database would otherwise reject mid-load.

    Each of these mirrors a CHECK constraint on `risk_flags`. Validating here as
    well means a bad fixture entry is reported by name, with all of them listed at
    once, instead of the load dying on the first offender with a constraint name.
    """
    problems: list[str] = []
    seen: set[str] = set()

    for row in rows:
        key = row["event_key"]
        if key in seen:
            problems.append(f"{key}: duplicate event_key")
        seen.add(key)

        if not key.startswith(SEED_KEY_PREFIX):
            problems.append(
                f"{key}: event_key must start with {SEED_KEY_PREFIX!r} so the "
                "seeder can clear its own rows without touching agent output"
            )
        if row["half_life_hours"] <= 0:
            problems.append(f"{key}: half_life_hours must be positive")
        if not 0 <= row["severity_0"] <= 100:
            problems.append(f"{key}: severity_0 must be 0-100")
        if not 0 < row["radius_m"] <= 20_000:
            problems.append(f"{key}: radius_m must be 1-20000")
        if row["status"] == "confirmed" and row["source_count"] < 2:
            problems.append(
                f"{key}: status 'confirmed' needs source_count >= 2 "
                "(verification before publication)"
            )
        if len(row["sources"]) > row["source_count"]:
            problems.append(
                f"{key}: lists {len(row['sources'])} sources but source_count is "
                f"{row['source_count']}"
            )

    if problems:
        print("\n  fixture is invalid:", file=sys.stderr)
        for problem in problems:
            print(f"    - {problem}", file=sys.stderr)
        print(file=sys.stderr)
        raise SystemExit(2)


INSERT_COLUMNS = (
    "event_key, kind, status, location, radius_m, severity_0, half_life_hours, "
    "observed_at, valid_from, valid_to, source_count, sources, mobility_statement"
)


def row_to_values_sql(row: dict[str, Any]) -> str:
    """One VALUES tuple. Note the absence of `expires_at` — the trigger owns it."""
    point = (
        f"extensions.ST_SetSRID(extensions.ST_MakePoint({row['lon']}, {row['lat']}), 4326)"
        "::extensions.geography"
    )
    return (
        "  ("
        f"{sql_str(row['event_key'])}, "
        f"{sql_str(row['kind'])}, "
        f"{sql_str(row['status'])}, "
        f"{point}, "
        f"{row['radius_m']}, "
        f"{row['severity_0']}, "
        f"{row['half_life_hours']}, "
        f"{sql_ts(row['observed_at'])}, "
        f"{sql_ts(row['valid_from']) if row['valid_from'] else 'NULL'}, "
        f"{sql_ts(row['valid_to']) if row['valid_to'] else 'NULL'}, "
        f"{row['source_count']}, "
        f"{sql_str(json.dumps(row['sources'], ensure_ascii=False))}::jsonb, "
        f"{sql_str(row['mobility_statement'])}"
        ")"
    )


def build_sql(rows: list[dict[str, Any]], *, clear: bool) -> str:
    header = [
        "-- ===========================================================================",
        "-- Meridian — seed risk flags",
        "-- ===========================================================================",
        "-- Generated by backend/scripts/seed_risk_flags.py from",
        "-- backend/data/fixtures/risk_flags.json.",
        "--",
        "-- Every mobility_statement below was produced by",
        "-- app/policy/framing.py::to_mobility_statement(). None of it was typed by",
        "-- hand, and none of it is in the fixture file.",
        "--",
        "-- expires_at is absent on purpose: trg_risk_flags_expires_at derives it.",
        "--",
        f"-- Generated at {datetime.now(UTC).isoformat()}",
        "-- Observation times are relative to that instant, so regenerate rather than",
        "-- re-running an old copy of this file.",
        "-- ===========================================================================",
        "",
    ]
    if clear:
        header += [
            "-- Clear previous seed rows only. Agent-produced flags are untouched.",
            f"delete from public.risk_flags where event_key like {sql_str(SEED_KEY_PREFIX + '%')};",
            "",
        ]

    body = [
        f"insert into public.risk_flags ({INSERT_COLUMNS})",
        "values",
        ",\n".join(row_to_values_sql(r) for r in rows) + ";",
        "",
        "-- What was loaded, and whether the database agrees it is live.",
        "select count(*) as seeded,",
        "       count(*) filter (where expires_at > now()) as live_now,",
        "       count(*) filter (where expires_at <= now()) as already_expired",
        f"from public.risk_flags where event_key like {sql_str(SEED_KEY_PREFIX + '%')};",
        "",
    ]
    return "\n".join(header + body)


async def insert_rows(rows: list[dict[str, Any]], *, clear: bool) -> int:
    conn = await connect()
    try:
        async with conn.transaction():
            if clear:
                deleted = await conn.execute(
                    "delete from public.risk_flags where event_key like $1",
                    SEED_KEY_PREFIX + "%",
                )
                match = re.search(r"(\d+)$", deleted or "")
                print(f"  cleared {match.group(1) if match else '0'} previous seed row(s)")

            for row in rows:
                await conn.execute(
                    f"""
                    insert into public.risk_flags ({INSERT_COLUMNS})
                    values ($1, $2, $3,
                            extensions.ST_SetSRID(
                                extensions.ST_MakePoint($4, $5), 4326
                            )::extensions.geography,
                            $6, $7, $8, $9, $10, $11, $12, $13::jsonb, $14)
                    """,
                    row["event_key"],
                    row["kind"],
                    row["status"],
                    row["lon"],
                    row["lat"],
                    row["radius_m"],
                    row["severity_0"],
                    row["half_life_hours"],
                    row["observed_at"],
                    row["valid_from"],
                    row["valid_to"],
                    row["source_count"],
                    json.dumps(row["sources"], ensure_ascii=False),
                    row["mobility_statement"],
                )

        live = await conn.fetchval(
            "select count(*) from public.risk_flags where event_key like $1 and expires_at > now()",
            SEED_KEY_PREFIX + "%",
        )
        print(f"  inserted {len(rows)} flag(s); {live} live right now")
    finally:
        await conn.close()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="seed_risk_flags.py", description="Load the risk-flag fixture."
    )
    parser.add_argument("--sql", action="store_true", help="print SQL instead of inserting")
    parser.add_argument("--out", metavar="PATH", help="with --sql, write to a file")
    parser.add_argument(
        "--keep",
        action="store_true",
        help="do not delete existing seed- rows first",
    )
    args = parser.parse_args()

    rows = build_rows(datetime.now(UTC))

    if args.sql:
        sql = build_sql(rows, clear=not args.keep)
        if args.out:
            path = Path(args.out)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(sql, encoding="utf-8")
            print(f"\n  wrote {len(rows)} flag(s) of SQL to {path}")
            print("  paste it into the Supabase SQL Editor and run it\n")
        else:
            print(sql)
        return 0

    print(f"\nseeding {len(rows)} risk flag(s)")
    result = asyncio.run(insert_rows(rows, clear=not args.keep))
    print("  done\n")
    return result


if __name__ == "__main__":
    raise SystemExit(main())
