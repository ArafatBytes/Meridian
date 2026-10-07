"""
The risk-flag fixture, resolved into insert-shaped rows.

`data/fixtures/risk_flags.json` is the most valuable artifact in D02: it is what
makes demo beats 1, 2, 4 and 5 work whether or not live ingestion is up on the day.
This module is the single reader of it.

It has two consumers and they must agree exactly:

* `scripts/seed_risk_flags.py` — writes the rows into `risk_flags`.
* `app/scoring/surface_seeded.py` — serves the same rows with no database at all,
  which is the offline demo path (`RISK_SURFACE_IMPL=seeded`).

Before D02 this logic lived in the seeder script. Two consumers of one fixture with
two readers would mean the seeded surface and the seeded database could disagree
about what the fixture says, and the symptom would be a demo that behaves one way in
rehearsal and another on stage.

The compact entry form
----------------------
A 200-entry fixture is only maintainable if an entry is one line, so most fields are
optional:

* `half_life_hours` and `radius_m` default to the reviewed per-kind values in
  `app/scoring/kinds.py`. An entry that wants something else states it.
* `sources` defaults to generated sample references, one per `source_count`.
* `status` defaults to `unconfirmed`.

Two fields are never accepted:

* `mobility_statement` — produced here by `app.policy.framing`, from `kind`,
  `mobility_impact` and `place`. A fixture carrying hand-written flag prose would be
  text that never passed the framing guard, sitting in the demo database, looking
  exactly like text that did. The loader raises rather than letting it through.
* `expires_at` — derived. The database's trigger owns it for stored rows and
  `decay.expires_at_for()` mirrors it for the seeded surface.

Times are relative
------------------
`observed_offset_hours: -1.5` means "an hour and a half before `now`". Absolute
timestamps would make the fixture correct on the day it was written and entirely
expired the next morning — which, for a fixture whose job is to work on 24 October,
is the one failure that matters.
"""

import json
import zlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Final

from app.contracts.risk import IncidentKind, MobilityImpact
from app.policy.framing import to_mobility_statement
from app.scoring.chronic import chronic_rows
from app.scoring.kinds import defaults_for

FIXTURE_PATH: Final[Path] = (
    Path(__file__).resolve().parent.parent.parent / "data" / "fixtures" / "risk_flags.json"
)

REPLAY_PATH: Final[Path] = FIXTURE_PATH.with_name("live_replay.json")
"""
Captured live news flags (D04), in this same compact entry form, written by
`python -m app.agents export-replay`. Served only by `SeededRiskSurface` — the
offline demo path — and never seeded into the database, where the live agent's own
rows already are. Absent until a capture has been made, which is not an error.
"""

SEED_KEY_PREFIX: Final[str] = "seed-"
"""
Every row this module produces carries it.

It is what lets the seeder clear its own rows without touching a flag produced by an
agent, and it is why `event_key` is validated rather than trusted.
"""

_SAMPLE_PUBLISHERS: Final[tuple[str, ...]] = (
    "sample_prothom_alo",
    "sample_the_daily_star",
    "sample_bdnews24",
    "sample_jugantor",
    "sample_kaler_kantho",
    "sample_dhaka_tribune",
)
"""
Stand-in publisher ids for generated source references.

Every one is prefixed `sample_` and every generated URL uses a `sample:` scheme, so
nothing here can be mistaken for real reporting and no link resolves. Real
provenance arrives in D04 with genuine article URLs. **If the flags on screen still
say `sample_`, you are showing the fixture**, and the honest thing to say on stage is
that this is the seeded surface and live ingestion is the next beat.
"""


class FixtureError(ValueError):
    """A fixture entry the loader will not produce a row from."""


def _publishers_for(event_key: str, count: int) -> list[str]:
    """
    `count` distinct publishers, chosen stably from the event key.

    `zlib.crc32` rather than `hash()`: Python's string hash is salted per process, so
    `hash()` here would give a flag different sources on every run and make the
    generated seed SQL churn for no reason.
    """
    start = zlib.crc32(event_key.encode()) % len(_SAMPLE_PUBLISHERS)
    return [_SAMPLE_PUBLISHERS[(start + i) % len(_SAMPLE_PUBLISHERS)] for i in range(count)]


def _generated_sources(
    *, event_key: str, place: str | None, observed_offset: float, count: int, now: datetime
) -> list[dict[str, Any]]:
    """
    Sample source references for an entry that did not spell its own out.

    Titles are deliberately not plausible headlines. Inventing "Fire service responds
    in Bangshal, traffic diverted" for 180 flags would produce a fixture that reads
    like a real news archive, and the point of the `sample_` marking is that nobody —
    including us, at midnight on the 23rd — can mistake it for one.

    Publication is placed shortly *after* observation, which is the real ordering: an
    event happens and is then reported. Clamped so a generated timestamp never lands
    in the future relative to `now`.
    """
    sources = []
    for index, publisher in enumerate(_publishers_for(event_key, count)):
        published_offset = min(observed_offset + 0.15 * (index + 1), -0.05)
        sources.append(
            {
                "source_id": publisher,
                "url": f"sample:{publisher}/{event_key}",
                "published_at": (now + timedelta(hours=published_offset)).isoformat(),
                "title": f"Sample report — {place or 'unnamed location'}",
                "snippet": None,
            }
        )
    return sources


def _explicit_sources(entry: dict[str, Any], now: datetime) -> list[dict[str, Any]]:
    """Source references the fixture spelled out, with offsets resolved."""
    return [
        {
            "source_id": source["source_id"],
            "url": source["url"],
            "published_at": (
                now + timedelta(hours=float(source["published_offset_hours"]))
            ).isoformat(),
            "title": source.get("title"),
            "snippet": source.get("snippet"),
        }
        for source in entry["sources"]
    ]


def _offset_or_none(now: datetime, offset: Any) -> datetime | None:
    return None if offset is None else now + timedelta(hours=float(offset))


def _row_from_entry(entry: dict[str, Any], now: datetime) -> dict[str, Any]:
    """One fixture entry to one insert-shaped row."""
    event_key = entry.get("event_key", "<missing event_key>")

    if "mobility_statement" in entry:
        raise FixtureError(
            f"fixture entry {event_key!r} contains a 'mobility_statement'. Flag text is "
            "produced by app/policy/framing.py, never written by hand. Remove the field; "
            "set 'mobility_impact' and 'place' instead."
        )
    if "expires_at" in entry:
        raise FixtureError(
            f"fixture entry {event_key!r} contains an 'expires_at'. It is derived from "
            "observed_at, severity_0, half_life_hours and valid_to — by the database for "
            "stored rows, by decay.expires_at_for() for the seeded surface."
        )

    kind = IncidentKind(entry["kind"])
    impact = MobilityImpact(entry["mobility_impact"])
    defaults = defaults_for(kind)
    observed_offset = float(entry["observed_offset_hours"])

    source_count = int(entry.get("source_count", max(1, len(entry.get("sources", [])))))
    sources = (
        _explicit_sources(entry, now)
        if entry.get("sources")
        else _generated_sources(
            event_key=event_key,
            place=entry.get("place"),
            observed_offset=observed_offset,
            count=source_count,
            now=now,
        )
    )

    return {
        "event_key": event_key,
        "kind": kind.value,
        "status": entry.get("status", "unconfirmed"),
        "lat": float(entry["lat"]),
        "lon": float(entry["lon"]),
        "radius_m": int(entry.get("radius_m", defaults.radius_m)),
        "severity_0": float(entry.get("severity_0", defaults.severity_0)),
        "half_life_hours": float(entry.get("half_life_hours", defaults.half_life_hours)),
        "observed_at": now + timedelta(hours=observed_offset),
        "valid_from": _offset_or_none(now, entry.get("valid_from_offset_hours")),
        "valid_to": _offset_or_none(now, entry.get("valid_to_offset_hours")),
        "source_count": source_count,
        "sources": sources,
        # The one and only writer of this string.
        "mobility_statement": to_mobility_statement(
            kind=kind, impact=impact, place=entry.get("place")
        ),
    }


def check_rows(rows: list[dict[str, Any]]) -> None:
    """
    Catch in the fixture what the database would otherwise reject mid-load.

    Each check mirrors a CHECK constraint on `risk_flags`. Validating here as well
    means a bad entry is reported by name, with every offender listed at once, instead
    of the load dying on the first one with a constraint name and no row identity.

    It also runs for the seeded surface, which has no constraints at all — so this is
    the only thing standing between a typo in the fixture and an offline demo serving
    a flag the real database would have refused.
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
                f"{key}: event_key must start with {SEED_KEY_PREFIX!r} so the seeder can "
                "clear its own rows without touching agent output"
            )
        if row["half_life_hours"] <= 0:
            problems.append(f"{key}: half_life_hours must be positive")
        if not 0 <= row["severity_0"] <= 100:
            problems.append(f"{key}: severity_0 must be 0-100")
        if not 0 < row["radius_m"] <= 20_000:
            problems.append(f"{key}: radius_m must be 1-20000")
        if not -90 <= row["lat"] <= 90 or not -180 <= row["lon"] <= 180:
            problems.append(f"{key}: coordinates out of range")
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
        if (
            row["valid_from"] is not None
            and row["valid_to"] is not None
            and row["valid_to"] <= row["valid_from"]
        ):
            problems.append(f"{key}: valid_to must be after valid_from")

    if problems:
        raise FixtureError(
            "fixture is invalid:\n" + "\n".join(f"    - {p}" for p in problems)
        )


def fixture_rows(
    now: datetime,
    *,
    include_chronic: bool = True,
    include_replay: bool = False,
    fixture_path: Path | None = None,
) -> list[dict[str, Any]]:
    """
    The whole seeded surface: hand-built event flags, then the chronic baseline, then
    (for the offline surface only) the captured live news flags.

    `include_chronic` exists for one case — a test that wants only the hand-built
    entries, because the chronic layer is derived from a data file rather than from
    this fixture and has its own tests. Nothing in the demo path turns it off.

    `include_replay` is off by default so the seeder never writes captured news into
    a database that already holds the live originals. Replay entries go through the
    same `_row_from_entry` and `check_rows` as everything else: no prose, `seed-`
    keys, the same constraints.
    """
    path = fixture_path or FIXTURE_PATH
    raw = json.loads(path.read_text(encoding="utf-8"))

    rows = [_row_from_entry(entry, now) for entry in raw["flags"]]
    if include_chronic:
        rows += chronic_rows(now)
    if include_replay and REPLAY_PATH.is_file():
        replay = json.loads(REPLAY_PATH.read_text(encoding="utf-8"))
        rows += [_row_from_entry(entry, now) for entry in replay["flags"]]

    check_rows(rows)
    return rows
