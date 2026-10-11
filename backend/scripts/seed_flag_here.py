#!/usr/bin/env python3
"""
Put one live risk flag at given coordinates, so geofencing can be tested anywhere.

    python backend/scripts/seed_flag_here.py --lat 23.1664 --lon 89.2081
    python backend/scripts/seed_flag_here.py --lat 23.1664 --lon 89.2081 --clear
    python backend/scripts/seed_flag_here.py --sql --lat ... --lon ...

Why this exists
---------------
Every flag in this project's data is in Dhaka, and `refreshZones` only fetches
flags within ~19 km of the user. So from anywhere else the zone count is
correctly zero and **Part 1 of `docs/walkthroughs/GUARDIAN.md` cannot run** —
there is nothing registered to cross and nothing for the test button to read.

The obvious workaround is not one: filing a **crime report** in the app does not
create a risk flag. They are different tables with no pipeline between them
(`grep -c crime_report` over every writer of `risk_flags` returns 0), and that is
deliberate — a single unverified report must not become a published risk claim.
That is the "verification before publication" invariant, and user reports feeding
the surface is backlog B13 / B11a, not a thing to quietly bolt on.

So: a dev tool that writes one flag where you are standing.

What it respects, and why each matters
--------------------------------------
* **`mobility_statement` comes from `app.policy.framing`.** It is the only
  producer of flag text in the system (concept document §9). A hand-written
  string here would be text that never passed the guard, sitting in the same
  table as text that did, indistinguishable.
* **`expires_at` is not supplied.** A database trigger derives it from
  `observed_at`, `severity_0`, `half_life_hours` and `valid_to`. One rule, one
  place — see `contracts/risk.py`.
* **`status` is `unconfirmed` with `source_count = 1`.** A CHECK constraint and
  an invariant test both forbid a single-source flag being `confirmed`, and this
  is a single fabricated source. It is also the honest tier for it.
* **`event_key` is prefixed `devhere-`** so `--clear` can remove exactly these
  rows and nothing else. It is deliberately *not* the fixture's `seed-` prefix:
  `seed_risk_flags.py --clear` would then delete these too, and vice versa.

This is a test fixture, not a feature. It writes one row and tells you how to
remove it.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

# Windows consoles default to cp1252 and the statement may contain an em dash.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.contracts.risk import IncidentKind, MobilityImpact  # noqa: E402
from app.policy.framing import to_mobility_statement  # noqa: E402

DEV_KEY_PREFIX = "devhere-"

INSERT_COLUMNS = (
    "event_key, kind, status, location, radius_m, severity_0, half_life_hours, "
    "observed_at, source_count, sources, mobility_statement"
)


def database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        env = BACKEND / ".env"
        if env.is_file():
            for line in env.read_text(encoding="utf-8").splitlines():
                match = re.match(r"^\s*DATABASE_URL\s*=\s*(.+?)\s*$", line)
                if match:
                    url = match.group(1).strip().strip('"').strip("'")
                    break
    if not url:
        sys.exit("DATABASE_URL not found in the environment or backend/.env")
    # asyncpg wants a bare postgres:// URL, not SQLAlchemy's +asyncpg dialect.
    return url.replace("postgresql+asyncpg://", "postgresql://").replace(
        "postgres+asyncpg://", "postgresql://"
    )


def build(args: argparse.Namespace) -> dict[str, object]:
    """The row. `severity_0` is chosen to clear the geofence threshold."""
    # MIN_SEVERITY_TO_WATCH is 40 on the client and severity decays from
    # `observed_at`, so a flag seeded at exactly 40 would drop below it within
    # minutes and stop being watched. 85 with a 12-hour half-life stays well
    # clear for a testing session.
    statement = to_mobility_statement(
        kind=IncidentKind.BLOCKADE,
        impact=MobilityImpact.ROAD_BLOCKED,
        place=args.place,
    )
    return {
        "event_key": f"{DEV_KEY_PREFIX}{int(datetime.now(UTC).timestamp())}",
        "kind": IncidentKind.BLOCKADE.value,
        "status": "unconfirmed",
        "lat": args.lat,
        "lon": args.lon,
        "radius_m": args.radius,
        "severity_0": args.severity,
        "half_life_hours": 12.0,
        # Slightly in the past: `observed_at` in the future would make the decay
        # arithmetic read oddly in the flag sheet.
        "observed_at": datetime.now(UTC) - timedelta(minutes=5),
        "source_count": 1,
        "sources": "[]",
        "mobility_statement": statement,
    }


def as_sql(row: dict[str, object], clear: bool) -> str:
    def lit(value: object) -> str:
        if isinstance(value, str):
            return "'" + value.replace("'", "''") + "'"
        if isinstance(value, datetime):
            return "'" + value.isoformat() + "'::timestamptz"
        return str(value)

    lines = [
        "-- One live risk flag at the given point, for testing geofencing away",
        "-- from Dhaka. Generated by backend/scripts/seed_flag_here.py.",
        "-- `expires_at` is omitted on purpose: a trigger derives it.",
        "",
    ]
    if clear:
        lines += [
            f"delete from public.risk_flags where event_key like '{DEV_KEY_PREFIX}%';",
            "",
        ]
    lines += [
        f"insert into public.risk_flags ({INSERT_COLUMNS})",
        "values (",
        f"  {lit(row['event_key'])}, {lit(row['kind'])}, {lit(row['status'])},",
        "  extensions.ST_SetSRID(extensions.ST_MakePoint("
        f"{row['lon']}, {row['lat']}), 4326)::extensions.geography,",
        f"  {row['radius_m']}, {row['severity_0']}, {row['half_life_hours']},",
        f"  {lit(row['observed_at'])}, {row['source_count']},"
        f" {lit(row['sources'])}::jsonb, {lit(row['mobility_statement'])}",
        ");",
        "",
        "select event_key, severity_0, expires_at,",
        "       extensions.ST_Y(location::extensions.geometry) as lat,",
        "       extensions.ST_X(location::extensions.geometry) as lon",
        f"from public.risk_flags where event_key like '{DEV_KEY_PREFIX}%';",
    ]
    return "\n".join(lines)


async def insert(row: dict[str, object], clear: bool) -> None:
    import asyncpg  # imported late so --sql needs no driver

    connection = await asyncpg.connect(database_url())
    try:
        if clear:
            removed = await connection.execute(
                "delete from public.risk_flags where event_key like $1",
                f"{DEV_KEY_PREFIX}%",
            )
            print(f"cleared previous dev flags: {removed}")
        await connection.execute(
            f"""
            insert into public.risk_flags ({INSERT_COLUMNS})
            values ($1, $2, $3,
                    extensions.ST_SetSRID(
                        extensions.ST_MakePoint($4, $5), 4326
                    )::extensions.geography,
                    $6, $7, $8, $9, $10, $11::jsonb, $12)
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
            row["source_count"],
            row["sources"],
            row["mobility_statement"],
        )
        found = await connection.fetch(
            """
            select event_key, severity_0, expires_at,
                   extensions.ST_Y(location::extensions.geometry) as lat,
                   extensions.ST_X(location::extensions.geometry) as lon
            from public.risk_flags
            where event_key like $1
            order by observed_at desc
            """,
            f"{DEV_KEY_PREFIX}%",
        )
        print(f"\ndev flags now in the table: {len(found)}")
        for record in found:
            print(
                f"  {record['event_key']}  sev={record['severity_0']}  "
                f"({record['lat']:.4f}, {record['lon']:.4f})  expires {record['expires_at']}"
            )
        print(f"\nstatement: {row['mobility_statement']}")
        print("\nNow: Guardian -> Refresh zones. The count should go above 0.")
        print(
            "Remove afterwards with:\n"
            "  python backend/scripts/seed_flag_here.py --clear-only"
        )
    finally:
        await connection.close()


async def clear_only() -> None:
    import asyncpg

    connection = await asyncpg.connect(database_url())
    try:
        result = await connection.execute(
            "delete from public.risk_flags where event_key like $1", f"{DEV_KEY_PREFIX}%"
        )
        print(f"removed dev flags: {result}")
    finally:
        await connection.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Seed one live risk flag at a point, for testing geofencing."
    )
    parser.add_argument("--lat", type=float, help="latitude, e.g. 23.1664")
    parser.add_argument("--lon", type=float, help="longitude, e.g. 89.2081")
    parser.add_argument(
        "--radius",
        type=int,
        default=300,
        help="flag radius in metres (default 300; the geofence adds 250 on top)",
    )
    parser.add_argument(
        "--severity",
        type=float,
        default=85.0,
        help="severity at observation, 0-100 (default 85, well clear of the 40 floor)",
    )
    parser.add_argument(
        "--place",
        default=None,
        help="optional place name for the statement; omitted gives 'in this area'",
    )
    parser.add_argument(
        "--clear", action="store_true", help="remove previous dev flags first"
    )
    parser.add_argument(
        "--clear-only", action="store_true", help="remove dev flags and exit"
    )
    parser.add_argument("--sql", action="store_true", help="print SQL, change nothing")
    args = parser.parse_args()

    if args.clear_only:
        asyncio.run(clear_only())
        return 0

    if args.lat is None or args.lon is None:
        parser.error("--lat and --lon are required (or use --clear-only)")

    row = build(args)
    if args.sql:
        print(as_sql(row, args.clear))
        return 0

    asyncio.run(insert(row, args.clear))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
