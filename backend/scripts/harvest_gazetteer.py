#!/usr/bin/env python3
"""
Build the Dhaka-central gazetteer candidate file from OpenStreetMap.

    python backend/scripts/harvest_gazetteer.py                 write data/gazetteer/dhaka_central.json
    python backend/scripts/harvest_gazetteer.py --out other.json
    python backend/scripts/harvest_gazetteer.py --dry-run       print a summary, write nothing

Why harvest instead of typing 150 rows by hand
----------------------------------------------
OpenStreetMap's Dhaka coverage is Bangla-primary: `name` holds the Bangla form
and `name:en` the romanisation, already paired, on 98% of the features in the
pilot box. That is both halves of every entry plus coordinates, for free, and it
is the tedious error-prone part. Measured before this script was written: 782
place/junction features in the box, 770 with Bangla script, 768 with both forms.

What OSM does **not** give, and so what still has to be entered by hand:

  aliases   The words people actually type. OSM calls the Mirpur 10 roundabout
            `গোলচক্কর`; half of Dhaka says `গোলচত্বর`. Same place, different
            word, and `alt_name` appears on about 40 of 782 features. This is
            the whole remaining job and it is the part that makes the search
            better than Google's.
  radius_m  OSM gives a point. A neighbourhood is not a point. Defaults below
            are by kind, and are a judgment call, not a measurement.

Both are seeded here with defaults and `reviewed: false`, so the file never
claims a human checked something a script guessed.

Ambiguity is recorded, not resolved
-----------------------------------
Dhaka has more than one "Sector 11" — Uttara's and Bashundhara's, 10 km apart.
42 names in the box are duplicated this way. Those entries get
`ambiguous: true`, and the loader refuses to resolve a query that only matches
ambiguous entries. That is D03's "unresolvable locations are discarded, never
guessed" applied to our own data rather than only to the LLM's output. Dropping
them would lose a real place; guessing between them would put a pin 10 km wrong.

Licence
-------
The harvested fields are OpenStreetMap data, ODbL 1.0. Attribution is required
and travels with the file in its `_README`. Do not strip it.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Final

# The pilot zone. Same box D02's fixture and walkthrough use, so the gazetteer
# and the risk surface cannot drift apart on geography.
BBOX_S: Final = 23.70
BBOX_W: Final = 90.33
BBOX_N: Final = 23.90
BBOX_E: Final = 90.50

# Tried in order. The main instance rejects a busy request outright rather than
# queueing, so a mirror list is the difference between a script that works and
# one that works on a good day.
ENDPOINTS: Final = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
)

USER_AGENT: Final = "Meridian/0.1 gazetteer harvest (+https://github.com/ArafatBytes/Meridian)"

# One query per kind keeps each request small enough to finish. A single
# combined query timed out repeatedly against every mirror.
QUERIES: Final[dict[str, str]] = {
    "neighbourhood": (
        f'node["place"~"^(neighbourhood|quarter|city_block|locality)$"]["name"]'
        f"({BBOX_S},{BBOX_W},{BBOX_N},{BBOX_E});"
    ),
    "area": (
        f'node["place"="suburb"]["name"]({BBOX_S},{BBOX_W},{BBOX_N},{BBOX_E});'
    ),
    "junction": (
        f'node["junction"]["name"]({BBOX_S},{BBOX_W},{BBOX_N},{BBOX_E});'
        f'way["junction"="roundabout"]["name"]({BBOX_S},{BBOX_W},{BBOX_N},{BBOX_E});'
    ),
    "market": (
        f'node["amenity"="marketplace"]["name"]({BBOX_S},{BBOX_W},{BBOX_N},{BBOX_E});'
    ),
    "terminal": (
        f'node["amenity"="bus_station"]["name"]({BBOX_S},{BBOX_W},{BBOX_N},{BBOX_E});'
        f'node["railway"="station"]["name"]({BBOX_S},{BBOX_W},{BBOX_N},{BBOX_E});'
    ),
}

# A point plus a radius is the whole spatial model. These are judgment calls:
# a junction is a place you stand, a suburb is a place you are somewhere inside.
# They exist so every entry has a usable number before anyone reviews it.
DEFAULT_RADIUS_M: Final[dict[str, int]] = {
    "junction": 150,
    "market": 200,
    "terminal": 300,
    "neighbourhood": 600,
    "area": 1200,
}

BENGALI: Final = re.compile(r"[ঀ-৿]")

# Names too generic to resolve anything. "Market" is not a place.
JUNK: Final = frozenset(
    {"market", "mosque", "school", "bazar", "bazaar", "mor", "more", "moor",
     "stand", "dhaka", "block", "sector", "road", "chourasta", "circle"}
)


def overpass(body: str, *, cache: Path | None = None) -> list[dict[str, Any]]:
    """
    Run one Overpass query, trying each mirror until one answers.

    Answers are cached on disk because the public instances are genuinely
    unreliable — during this script's own development one query succeeded against
    a mirror and the same query timed out against all three twenty minutes later.
    Without a cache, one slow mirror throws away every query that already
    succeeded, so re-running resumes instead of starting from nothing.
    """
    if cache is not None and cache.is_file():
        print(f"  (cached) {cache.name}", file=sys.stderr)
        return list(json.loads(cache.read_text(encoding="utf-8")).get("elements", []))

    query = f"[out:json][timeout:90];({body});out tags center;"
    payload = urllib.parse.urlencode({"data": query}).encode()
    last: str = "no endpoint tried"
    # Two passes: a mirror that is busy right now is often fine a minute later,
    # and the alternative is losing the whole run to one bad moment.
    for attempt in (1, 2):
        for url in ENDPOINTS:
            request = urllib.request.Request(
                url, data=payload, headers={"User-Agent": USER_AGENT}
            )
            try:
                with urllib.request.urlopen(request, timeout=180) as response:
                    raw = response.read().decode("utf-8")
                parsed = json.loads(raw)
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as problem:
                last = f"{url}: {type(problem).__name__}"
                print(f"  pass {attempt} {last} — next mirror", file=sys.stderr)
                continue
            if cache is not None:
                cache.parent.mkdir(parents=True, exist_ok=True)
                cache.write_text(raw, encoding="utf-8")
            return list(parsed.get("elements", []))
    raise RuntimeError(f"every Overpass mirror failed, last was {last}")


# A name longer than this, after the address tail is cut off, is a business
# description rather than a place anyone asks for by name.
MAX_NAME_TOKENS: Final = 6


def clean_name(name: str) -> str:
    """
    Cut the address off a name.

    Mappers in the market layer routinely type the whole address into `name`:
    "Dhaka New Market, Mirpur Rd, Dhaka". Keeping the part before the first comma
    recovers a real landmark; keeping the whole string gives the matcher a name
    nobody will ever type, which then wins subset matches against the short,
    correct entry for the same place. 43 of 1,059 harvested names were like this,
    every one of them a market.
    """
    head = name.split(",", 1)[0].strip(" -–—·|")
    return "" if len(head.split()) > MAX_NAME_TOKENS else head


def split_names(tags: dict[str, str]) -> tuple[str, str]:
    """Return (bangla, romanised). Either may be empty."""
    name = clean_name(tags.get("name", "").strip())
    bangla = clean_name(tags.get("name:bn", "").strip())
    latin = clean_name(tags.get("name:en", "").strip())
    # `name` is whichever script the mapper typed. Assign it to the side that is
    # still empty rather than trusting it to be one or the other.
    if name:
        if BENGALI.search(name):
            bangla = bangla or name
        else:
            latin = latin or name
    return bangla, latin


def harvested_aliases(tags: dict[str, str]) -> list[str]:
    """The few variant spellings OSM does carry. Rare, but free and real."""
    out: list[str] = []
    for key, value in tags.items():
        if key.startswith(("alt_name", "old_name", "loc_name", "int_name")):
            value = value.strip()
            if value:
                out.extend(part.strip() for part in value.split(";") if part.strip())
    return out


def coordinates(element: dict[str, Any]) -> tuple[float, float] | None:
    if "lat" in element and "lon" in element:
        return float(element["lat"]), float(element["lon"])
    centre = element.get("center")
    if isinstance(centre, dict) and "lat" in centre and "lon" in centre:
        return float(centre["lat"]), float(centre["lon"])
    return None


def fold(text: str) -> str:
    """Compare-form of a name: case, punctuation and spacing removed."""
    folded = unicodedata.normalize("NFKC", text).casefold()
    return re.sub(r"[^a-z0-9ঀ-৿]+", "", folded)


def build(cache_dir: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    seen_osm: set[str] = set()

    for kind, body in QUERIES.items():
        print(f"querying {kind} ...", file=sys.stderr)
        # A failure here aborts the run on purpose. A gazetteer silently missing
        # every junction is a demo that fails on stage, not a smaller gazetteer.
        # The cache means re-running only fetches what is still missing.
        for element in overpass(body, cache=cache_dir / f"{kind}.json"):
            tags = element.get("tags", {})
            point = coordinates(element)
            if point is None:
                continue
            bangla, latin = split_names(tags)
            if not bangla and not latin:
                continue
            # A bare generic word resolves nothing and would match everything.
            if fold(latin) in {fold(j) for j in JUNK} and not bangla:
                continue

            osm_id = f"{element['type']}/{element['id']}"
            if osm_id in seen_osm:
                continue
            seen_osm.add(osm_id)

            entries.append(
                {
                    "id": f"osm-{element['type']}-{element['id']}",
                    "name_bn": bangla,
                    "name_en": latin,
                    "aliases": harvested_aliases(tags),
                    "kind": kind,
                    "lat": round(point[0], 6),
                    "lon": round(point[1], 6),
                    "radius_m": DEFAULT_RADIUS_M[kind],
                    "source": f"osm:{osm_id}",
                    "reviewed": False,
                    "ambiguous": False,
                }
            )

    entries = resolve_collisions(entries)
    entries.sort(key=lambda e: (e["kind"], e["name_en"] or e["name_bn"]))
    return entries


# Two entries sharing a name this close together are one place that OSM lists in
# more than one layer, not two places. Measured on the harvest: "Farmgate" appears
# as a neighbourhood and a terminal 276 m apart, "TSC Mor" twice 15 m apart, while
# Uttara's and Bashundhara's "Sector 11" are 10 km apart. Anything inside this
# radius is merged; anything outside it is a genuine ambiguity.
MERGE_RADIUS_M: Final = 1_000

# Most specific first. When merging duplicates, the narrower kind wins: if OSM
# named a junction exactly what the user typed, the junction is the landmark meant.
KIND_SPECIFICITY: Final = {"junction": 0, "terminal": 1, "market": 2, "neighbourhood": 3, "area": 4}


def metres(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6_371_000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi, dlam = phi2 - phi1, math.radians(lon2 - lon1)
    h = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(h))


def resolve_collisions(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Decide what a repeated name means, and act on it.

    Same name, close together -> one place listed twice. Keep the most specific
    one and drop the rest, so the matcher is not forced to choose between two
    records of the same thing and refuse.

    Same name, far apart -> genuinely different places. Flag every one of them
    `ambiguous`; the loader then refuses such a query rather than picking. That is
    the discard invariant, and getting it wrong in the other direction is worse:
    before this function looked at distance, the gazetteer refused "Farmgate".
    """
    groups: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        for name in (entry["name_bn"], entry["name_en"]):
            if name:
                groups.setdefault(fold(name), []).append(entry)

    drop: set[int] = set()
    for members in groups.values():
        unique = {id(m): m for m in members}.values()
        if len(unique) < 2:
            continue
        rows = list(unique)
        spread = max(
            metres(a["lat"], a["lon"], b["lat"], b["lon"])
            for i, a in enumerate(rows)
            for b in rows[i + 1:]
        )
        if spread <= MERGE_RADIUS_M:
            keeper = min(
                rows,
                key=lambda r: (KIND_SPECIFICITY.get(r["kind"], 9), not (r["name_bn"] and r["name_en"]), r["id"]),
            )
            for row in rows:
                if row is not keeper:
                    drop.add(id(row))
                else:
                    # Merging loses the other records' spellings otherwise.
                    extra = [n for r in rows if r is not keeper for n in (r["name_bn"], r["name_en"]) if n]
                    keeper["aliases"] = list(dict.fromkeys([*keeper["aliases"], *extra]))
        else:
            for row in rows:
                row["ambiguous"] = True

    kept = [e for e in entries if id(e) not in drop]
    # An alias identical to the entry's own name adds nothing; drop the noise.
    for entry in kept:
        own = {fold(entry["name_bn"]), fold(entry["name_en"])}
        entry["aliases"] = [a for a in entry["aliases"] if fold(a) not in own]
    return kept


README: Final = {
    "zone": "Dhaka central (the D02 fixture bbox)",
    "bbox": f"{BBOX_W},{BBOX_S},{BBOX_E},{BBOX_N}",
    "built_by": "backend/scripts/harvest_gazetteer.py",
    "source": "OpenStreetMap contributors, ODbL 1.0 — https://www.openstreetmap.org/copyright",
    "licence_note": (
        "Harvested fields are OpenStreetMap data under ODbL 1.0. Attribution is "
        "required. Do not remove this block."
    ),
    "fields": {
        "name_bn": "Bangla form, from OSM name / name:bn.",
        "name_en": "Romanised form, from OSM name:en.",
        "aliases": "Variant spellings and local synonyms. Hand-entered; OSM has almost none.",
        "kind": "junction | market | terminal | neighbourhood | area.",
        "radius_m": "Default by kind. A judgment call, not a measurement.",
        "source": "osm:<type>/<id>, or 'manual' for a hand-added entry.",
        "reviewed": "True only once a person has checked this row. The harvest sets false.",
        "ambiguous": (
            "True when every name form this entry has is shared with another "
            "entry. The loader refuses to resolve a query that matches only "
            "ambiguous entries, rather than picking one."
        ),
    },
    "hand_work_still_outstanding": (
        "aliases and radius_m. OSM spells the Mirpur 10 roundabout "
        "'গোলচক্কর'; much of Dhaka says 'গোলচত্বর'. The gazetteer is only "
        "better than a general map once those synonyms are in."
    ),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        default=str(Path(__file__).resolve().parent.parent / "data" / "gazetteer" / "dhaka_central.json"),
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--cache-dir",
        default=str(Path(__file__).resolve().parent.parent / "data" / "gazetteer" / ".osm-cache"),
        help="Raw Overpass answers, so a re-run resumes. Delete it to refetch.",
    )
    parser.add_argument(
        "--refresh", action="store_true", help="Ignore the cache and refetch everything."
    )
    args = parser.parse_args()

    cache_dir = Path(args.cache_dir)
    if args.refresh and cache_dir.is_dir():
        for stale in cache_dir.glob("*.json"):
            stale.unlink()
        print(f"cleared {cache_dir}", file=sys.stderr)

    try:
        entries = build(cache_dir)
    except RuntimeError as problem:
        print(f"harvest failed: {problem}", file=sys.stderr)
        return 1

    by_kind: dict[str, int] = {}
    for entry in entries:
        by_kind[entry["kind"]] = by_kind.get(entry["kind"], 0) + 1
    ambiguous = sum(1 for e in entries if e["ambiguous"])
    both = sum(1 for e in entries if e["name_bn"] and e["name_en"])

    print(f"\n{len(entries)} entries", file=sys.stderr)
    for kind, count in sorted(by_kind.items()):
        print(f"  {kind:16s} {count:5d}", file=sys.stderr)
    print(f"  both name forms  {both:5d}", file=sys.stderr)
    print(f"  ambiguous        {ambiguous:5d}", file=sys.stderr)

    if args.dry_run:
        print("\n--dry-run: nothing written", file=sys.stderr)
        return 0

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps({"_README": README, "entries": entries}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"\nwrote {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
