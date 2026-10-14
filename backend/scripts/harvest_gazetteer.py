#!/usr/bin/env python3
"""
Build the Dhaka gazetteer from OpenStreetMap.

    python backend/scripts/harvest_gazetteer.py                 write data/gazetteer/dhaka_central.json
    python backend/scripts/harvest_gazetteer.py --out other.json
    python backend/scripts/harvest_gazetteer.py --dry-run       print a summary, write nothing
    python backend/scripts/harvest_gazetteer.py --refresh       ignore the cache, refetch

Why harvest instead of typing 150 rows by hand
----------------------------------------------
OpenStreetMap's Dhaka coverage is Bangla-primary: `name` holds the Bangla form
and `name:en` the romanisation, already paired, on 98% of the features in the
box. That is both halves of every entry plus coordinates, for free, and it is
the tedious error-prone part.

What OSM does **not** give, and so what still has to be entered by hand:

  aliases   The words people actually type. OSM calls the Mirpur 10 roundabout
            `গোলচক্কর`; half of Dhaka says `গোলচত্বর`. Same place, different
            word, and `alt_name` appears on a few dozen features. This is the
            whole remaining job and it is the part that makes the search better
            than Google's.
  radius_m  OSM gives a point. A neighbourhood is not a point. Defaults below
            are by kind, and are a judgment call, not a measurement. Roads are
            the exception — their radius is measured, see `cluster_roads`.

Both are seeded here with defaults and `reviewed: false`, so the file never
claims a human checked something a script guessed.

Why the box and the layer list grew (S31)
-----------------------------------------
The gazetteer is the ceiling on the whole news pipeline. An article naming a
place this file does not know is discarded — correctly, because a wrong pin is
worse than no pin — so the pipeline can read thousands of articles, extract
perfectly, and publish nothing. Two measured gaps:

  1. **No roads at all.** The first live crime extraction geocoded neither of
     its two results; one was `Satmasjid Road`, a major Dhanmondi road. The
     previous harvest asked OSM for places, junctions, markets and terminals
     and never for `highway`, so the single most common way a Bangla crime
     report names a location was absent by construction.
  2. **The box stopped inside the city.** `23.70–23.90 / 90.33–90.50` cuts off
     Uttarkhan, Dakshinkhan and Turag in the north and Demra, Matuail and
     Kadamtali in the south, all of which are Dhaka city. A Tongi factory fire
     carried by four publishers in one pass was discarded for want of a
     `place=town` node, which this harvest never asked for either.

The box now covers both city corporations with a margin. Savar, Narayanganj
city and Gazipur city are still outside it on purpose: they are different
cities, the pilot claim is Dhaka, and `in_pilot_box` is also the sanity gate
the LLM tier is checked against — widening it weakens that gate everywhere.
Moving the four constants below is the whole change if that decision changes.

Ambiguity is recorded, not resolved
-----------------------------------
Dhaka has more than one "Sector 11" — Uttara's and Bashundhara's, 10 km apart.
Those entries get `ambiguous: true`, and the loader refuses to resolve a query
that only matches ambiguous entries. That is D03's "unresolvable locations are
discarded, never guessed" applied to our own data rather than only to the LLM's
output. Dropping them would lose a real place; guessing between them would put
a pin 10 km wrong.

Licence
-------
The harvested fields are OpenStreetMap data, ODbL 1.0. Attribution is required
and travels with the file in its `_README`. Do not strip it.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import socket
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

# The pilot zone: Dhaka North and Dhaka South city corporations, with a margin.
# `app/geo/gazetteer.py` carries the same four numbers and they must not drift —
# `tests/invariants/test_unresolvable_places_are_discarded.py` asserts every
# harvested entry sits inside the loader's box.
BBOX_S: Final = 23.66
BBOX_W: Final = 90.30
BBOX_N: Final = 23.94
BBOX_E: Final = 90.54

# Tried in order. The main instance rejects a busy request outright rather than
# queueing, so a mirror list is the difference between a script that works and
# one that works on a good day.
#
# Ordered by measured behaviour, not by reputation. Asking all of them for the
# same 181-node query on 2026-10-14: overpass-api.de refused in 32 s, mail.ru
# answered correctly in 20 s, kumi hung until the socket timeout and
# private.coffee refused after 100 s. A mirror that fails *fast* is better
# placed first than one that hangs, because the hang is charged to every query.
ENDPOINTS: Final = (
    "https://overpass-api.de/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
)

# Overpass is told `[timeout:180]`, so an answer that has not arrived in 200 s is
# not coming. The previous 300 s only lengthened every hang: with four mirrors
# and four passes, one bad layer could hold the run for over an hour.
SOCKET_TIMEOUT_S: Final = 200

# How many times a mirror may hang before this run stops asking it.
#
# This is the single biggest thing that made the S31 harvest slow, and it is
# worth spelling out because the symptom looks like "Overpass is down" when it is
# not. A mirror that *refuses* costs about 30 seconds and may well answer the
# next query; a mirror that *hangs* costs SOCKET_TIMEOUT_S every time it is
# tried and, measured over several hours on 2026-10-14, never once answered. Two
# of the four mirrors behaved that way all afternoon, and with ten passes the
# arithmetic is brutal: 2 x 200 s x 10 is over an hour per tile spent on
# endpoints that were never going to reply.
#
# One strike, therefore. A hang is strong evidence on its own, the mirror is
# still tried once per run in case it has recovered, and a fresh process clears
# the list — which is why the supervising loop restarts the script rather than
# retrying inside it.
MIRROR_STRIKES: Final = 1
_DOWN: set[str] = set()

# How many times to go round the mirror list before giving up on a query.
#
# Four was not enough, and the reason is worth recording because it is not
# obvious: a loaded Overpass instance **refuses rather than queues**, and it does
# so quickly. Measured on 2026-10-14, asking overpass-api.de for four road tiles
# in a row: three answered 504 in about 29 seconds each and the fourth returned
# 587 ways in 25 seconds — and the one that succeeded was the *densest* of the
# four. So a 504 here says almost nothing about the query and almost everything
# about the minute it was sent in, which means the right response is to ask
# again rather than to make the query smaller. Tiling a layer further costs more
# requests for no better odds.
PASSES: Final = 10

# Backoff grows with the pass number, but not without limit: these failures come
# back in 30 seconds, so waiting five minutes between late attempts would cost
# more than the retries.
MAX_PAUSE_S: Final = 30.0

# Mirrors deliberately NOT in that list, because two of them answer wrongly
# rather than failing. Measured 2026-10-14, asking all seven for the 181
# `place=suburb` nodes in the box:
#
#   overpass.osm.ch              200 OK, **0 elements**, in 1.2 s
#   overpass.osm.jp              connection refused
#   overpass.openstreetmap.ru    connection refused
#
# The first is the dangerous one. It serves a regional extract, so a Dhaka query
# is perfectly valid there and simply matches nothing — and a harvest that
# accepted it would cache an empty layer and write a gazetteer with no suburbs in
# it, with no error anywhere. `overpass` below refuses to cache an empty answer
# for that reason. Do not add a mirror without checking it returns Bangladesh.

USER_AGENT: Final = "Meridian/0.1 gazetteer harvest (+https://github.com/ArafatBytes/Meridian)"

# Overpass answers 429 to a client that asks again immediately. Measured while
# sizing this harvest: six queries in a row, the first three answered and the
# next three were refused. A pause between queries is cheaper than a retry.
POLITE_PAUSE_S: Final = 4.0

# What a 429 costs. Overpass hands out a small number of concurrent slots per
# client and refuses outright once they are used, so the only useful response is
# to stop asking for a while. Measured: a burst of six sizing queries put this
# host over the quota and the next three were refused instantly.
SLOT_BACKOFF_S: Final = 45.0


@dataclass(frozen=True, slots=True)
class Harvest:
    """
    One Overpass request, cached under `key`, producing entries of `kind`.

    `selectors` are Overpass statements with the bounding box left off; the box
    is appended per tile. `tiles` splits the box into a `tiles` x `tiles` grid
    and asks for each cell separately: the road layers are an order of magnitude
    larger than anything the previous harvest fetched and a single whole-box
    request for them times out against every mirror.
    """

    key: str
    kind: str
    selectors: tuple[str, ...]
    tiles: int = 1


# One request per layer keeps each answer small enough to finish. A single
# combined query timed out repeatedly against every mirror.
#
# Layers deliberately **not** harvested, with reasons, because the obvious
# instinct is to add every named node in the box and that costs more than it pays:
#
#   amenity=school          ~1,100 in the box and the names are generic —
#                           "Government Primary School" resolves nothing and
#                           gives the fuzzy matcher a thousand near-identical
#                           strings to score against on every lookup.
#   amenity=place_of_worship ~1,200, same problem. Bangla reports say "মসজিদের
#                           সামনে" (in front of the mosque), which is a generic
#                           reference, not a named landmark we could pin.
#   boundary=administrative Thana and ward polygons. Their names duplicate the
#                           `place` nodes we already have, but their centroids
#                           sit up to 2 km away, so every one of them would
#                           collide with a known neighbourhood at a distance
#                           that makes both ambiguous. That turns "Dhanmondi"
#                           from resolving into refused — the invariant failing
#                           in the direction that costs a real place.
HARVESTS: Final[tuple[Harvest, ...]] = (
    Harvest(
        "neighbourhood",
        "neighbourhood",
        ('node["place"~"^(neighbourhood|quarter|city_block|locality|borough)$"]["name"]',),
    ),
    Harvest("area", "area", ('node["place"="suburb"]["name"]',)),
    # Tongi, Keraniganj, Demra and the rest of the urban fringe are `place=town`
    # or `village`, which the previous harvest never asked for. This is why a
    # fire four publishers covered could not be placed.
    Harvest("town", "town", ('node["place"~"^(city|town|village|hamlet)$"]["name"]',)),
    Harvest(
        "junction",
        "junction",
        (
            'node["junction"]["name"]',
            'way["junction"="roundabout"]["name"]',
        ),
    ),
    Harvest(
        "market",
        "market",
        (
            'node["amenity"="marketplace"]["name"]',
            'way["amenity"="marketplace"]["name"]',
        ),
    ),
    Harvest(
        "mall",
        "mall",
        ('node["shop"="mall"]["name"]', 'way["shop"="mall"]["name"]'),
    ),
    Harvest(
        "terminal",
        "terminal",
        (
            'node["amenity"="bus_station"]["name"]',
            'way["amenity"="bus_station"]["name"]',
            'node["railway"="station"]["name"]',
            'node["railway"="halt"]["name"]',
            'way["aeroway"="terminal"]["name"]',
        ),
    ),
    # Crime reporting is organised by thana. "Hazaribagh thana area" is a
    # location in a way that no `place` node spells.
    Harvest(
        "police",
        "police",
        ('node["amenity"="police"]["name"]', 'way["amenity"="police"]["name"]'),
    ),
    Harvest(
        "hospital",
        "hospital",
        ('node["amenity"="hospital"]["name"]', 'way["amenity"="hospital"]["name"]'),
    ),
    # The layer the whole sprint is about, so it goes before the nice-to-have
    # ones. Split major from minor so a failure in the large one does not throw
    # away the small one, and tile both.
    #
    # Order here is a reliability decision, not a cosmetic one. Each layer is
    # cached separately and the public mirrors fail often, so whatever sits last
    # is what a bad afternoon costs you. On 2026-10-14 `campus` drew a 504 from
    # every live mirror for half an hour while the roads waited behind it — and
    # the roads are the reason this harvest was rewritten.
    Harvest(
        "road_major",
        "road",
        ('way["highway"~"^(trunk|primary|secondary|tertiary)$"]["name"]',),
        tiles=2,
    ),
    Harvest(
        "road_minor",
        "road",
        ('way["highway"~"^(residential|unclassified|living_street)$"]["name"]',),
        tiles=3,
    ),
    # Tiled because it is not cheap: asking for `way` centres makes Overpass
    # resolve the geometry of every campus polygon, and untiled this query drew a
    # 504 from both live mirrors every time.
    Harvest(
        "campus",
        "campus",
        (
            'node["amenity"~"^(university|college)$"]["name"]',
            'way["amenity"~"^(university|college)$"]["name"]',
        ),
        tiles=2,
    ),
    Harvest(
        "park",
        "park",
        (
            'way["leisure"~"^(park|stadium)$"]["name"]',
            'node["leisure"~"^(park|stadium)$"]["name"]',
        ),
        tiles=2,
    ),
    # Named still water. Added after the eval caught what its absence cost:
    # Dhaka's lakes are places, and reports locate things by them, but the only
    # Hatirjheel this harvest knew was "Hatirjheel Park" — a 300 m feature
    # inside a 3 km lake complex. So "Hatirjheel" resolved 2.5 km from
    # Hatirjheel while claiming 300 m of precision, which is worse than
    # declining. Rivers are excluded: the Buriganga and the Turag run the length
    # of the city, so naming one locates nothing.
    Harvest(
        "water",
        "water",
        (
            'way["natural"="water"]["name"]["water"!~"^(river|stream|canal|ditch|drain)$"]',
            'relation["natural"="water"]["name"]["water"!~"^(river|stream|canal|ditch|drain)$"]',
        ),
        tiles=2,
    ),
    # `way["bridge"]["name"]` on its own matches every named road way that
    # happens to cross water, and the name it returns is the road's — a short
    # duplicate segment of something `road_major` already has. Ask for structures
    # mapped as bridges, plus ways whose own name says what they are.
    Harvest(
        "bridge",
        "bridge",
        (
            'way["man_made"="bridge"]["name"]',
            'way["bridge"]["name"~"(flyover|overpass|over.?bridge|setu|ফ্লাইওভার|সেতু|ব্রিজ)",i]',
        ),
    ),
    # The vernacular layer, and **last on purpose**. OSM names Dhaka's bus stops
    # the way people say them — "শেওড়াপাড়া", "আগারগাঁও" — and some of those names
    # are not on any `place` node, so it is worth having. But it is also the
    # weakest kind (a stop is named *after* the place it serves, so the
    # borrowed-name rule strips most of them again) and by far the slowest to
    # fetch: on 2026-10-14 three of its four tiles took longer than every other
    # layer put together and the fourth drew 504s from all four mirrors.
    #
    # Ordering is the cheap fix. Layers are cached individually, so with this one
    # last a run that dies here has already banked the roads, which are the
    # layer this sprint is actually for.
    Harvest("stop", "stop", ('node["highway"="bus_stop"]["name"]',), tiles=2),
)

# A point plus a radius is the whole spatial model. These are judgment calls:
# a junction is a place you stand, a suburb is a place you are somewhere inside.
# They exist so every entry has a usable number before anyone reviews it.
# `road` is absent on purpose — a road's radius is measured, not defaulted.
DEFAULT_RADIUS_M: Final[dict[str, int]] = {
    "junction": 150,
    "stop": 120,
    "market": 200,
    "mall": 250,
    "bridge": 250,
    "hospital": 250,
    "terminal": 300,
    "park": 300,
    "campus": 400,
    "police": 400,
    "neighbourhood": 600,
    "area": 1200,
    # A lake is a place you are beside, and Dhaka's are long and narrow.
    "water": 900,
    "town": 1500,
}

BENGALI: Final = re.compile(r"[ঀ-৿]")

# Names too generic to resolve anything. "Market" is not a place, and with the
# bus-stop, hospital and police layers added there are now hundreds of features
# whose entire name is the word for what they are.
JUNK_EN: Final = frozenset(
    {
        "market", "mosque", "masjid", "jame mosque", "jame masjid", "school",
        "high school", "primary school", "government primary school", "college",
        "madrasa", "madrasah", "bazar", "bazaar", "kacha bazar", "mor", "more",
        "moor", "mora", "stand", "bus stand", "bus stop", "bus station",
        "bus counter", "counter", "dhaka", "dhaka city", "block", "sector",
        "road", "main road", "new road", "link road", "access road",
        "service road", "lane", "alley", "gali", "chourasta", "chowrasta",
        "circle", "roundabout", "crossing", "intersection", "bridge",
        "foot bridge", "footbridge", "over bridge", "overbridge", "culvert",
        "flyover", "police station", "thana", "police box", "police outpost",
        "hospital", "clinic", "medical", "health complex", "park",
        "playground", "field", "khela mat", "graveyard", "kabarsthan",
        "community centre", "community center", "filling station", "gate",
        "railway station", "station", "terminal", "ghat", "launch ghat",
        "mazar", "eidgah", "university", "shop", "store", "unnamed road",
    }
)

# The same words as OSM actually writes them. The previous JUNK check only fired
# on an entry with no Bangla name at all, which let every Bangla-named "মসজিদ"
# through.
JUNK_BN: Final = frozenset(
    {
        "মসজিদ", "জামে মসজিদ", "বাজার", "কাঁচা বাজার", "মোড়", "স্কুল",
        "প্রাথমিক বিদ্যালয়", "সরকারি প্রাথমিক বিদ্যালয়", "বিদ্যালয়", "কলেজ",
        "মাদ্রাসা", "রাস্তা", "সড়ক", "প্রধান সড়ক", "গলি", "লেন", "সেক্টর",
        "ব্লক", "ঢাকা", "থানা", "পুলিশ ফাঁড়ি", "হাসপাতাল", "ক্লিনিক", "পার্ক",
        "মাঠ", "খেলার মাঠ", "কবরস্থান", "ঈদগাহ", "ব্রিজ", "সেতু", "ফ্লাইওভার",
        "বাসস্ট্যান্ড", "বাস স্ট্যান্ড", "বাস স্টপ", "স্টেশন", "রেলস্টেশন",
        "ঘাট", "গেট", "কাউন্টার", "বিশ্ববিদ্যালয়", "মাজার",
    }
)


def _usable_cache(cache: Path, body: str) -> bool:
    """
    Is this cached answer an answer to the question we are asking now?

    The cache is keyed by layer name and tile index, and neither of those says
    anything about *where* the tile was or what it selected. So raising a layer's
    `tiles` from 2 to 3, or moving the bounding box, leaves files named
    `stop.0.json` and `stop.1.json` on disk that answer completely different
    questions — and the harvest would read them back as if nothing had changed
    and write a gazetteer covering the wrong area, with no error anywhere.

    S31 moved the box and changed every selector, so this is not hypothetical.
    The query body is written beside each answer and compared on the way back in.
    """
    if not cache.is_file():
        return False
    sidecar = cache.with_suffix(".query.txt")
    if not sidecar.is_file():
        # Written before this check existed. Trust it, loudly, and name the file,
        # because the alternative is silently discarding a slow harvest.
        print(
            f"  (cached) {cache.name} — no recorded query; assuming it still "
            f"matches. Delete it, or use --refresh, if the box or selectors moved.",
            file=sys.stderr,
            flush=True,
        )
        _write_sidecar(cache, body)
        return True
    if sidecar.read_text(encoding="utf-8") == body:
        print(f"  (cached) {cache.name}", file=sys.stderr, flush=True)
        return True
    print(
        f"  {cache.name} answers a different query than the one being asked "
        f"(the box, the selectors or `tiles` changed) — refetching",
        file=sys.stderr,
        flush=True,
    )
    return False


def _write_sidecar(cache: Path, body: str) -> None:
    cache.with_suffix(".query.txt").write_text(body, encoding="utf-8")


def _write_cache(cache: Path, raw: str, body: str) -> None:
    """
    Write a cached answer so a reader can never see half of one.

    A 20 MB road tile takes a moment to write, and this harvest is resumable, so
    two runs sharing a cache directory is a normal situation rather than an
    exotic one — it happened on 2026-10-14, when two interrupted runs were still
    alive inside the container alongside a third. A reader that caught a
    partial write would get a `JSONDecodeError` on a file that looks cached, and
    the obvious fix would be to delete the cache and start over.
    """
    cache.parent.mkdir(parents=True, exist_ok=True)
    temporary = cache.with_name(f"{cache.name}.{os.getpid()}.part")
    temporary.write_text(raw, encoding="utf-8")
    temporary.replace(cache)  # atomic on POSIX and on Windows for a same-dir move
    # The question this file answers, so a later run can tell whether it still
    # applies. Written after the answer, never before: a sidecar without its
    # answer would claim a cache hit for a file that is not there.
    _write_sidecar(cache, body)


def overpass(body: str, *, cache: Path | None = None) -> list[dict[str, Any]]:
    """
    Run one Overpass query, trying each mirror until one answers.

    Answers are cached on disk because the public instances are genuinely
    unreliable — during this script's own development one query succeeded against
    a mirror and the same query timed out against all three twenty minutes later.
    Without a cache, one slow mirror throws away every query that already
    succeeded, so re-running resumes instead of starting from nothing.
    """
    if cache is not None and _usable_cache(cache, body):
        return list(json.loads(cache.read_text(encoding="utf-8")).get("elements", []))

    query = f"[out:json][timeout:180];({body});out tags center;"
    payload = urllib.parse.urlencode({"data": query}).encode()
    last: str = "no endpoint tried"
    # Which mirrors answered cleanly with nothing in them. One such answer is
    # indistinguishable from a regional mirror that does not hold Bangladesh; two
    # from different mirrors is evidence the tile really is empty, which happens
    # for a road tile over the river. Agreement is the only way to tell apart a
    # true negative from a wrong answer, so it is what the rule asks for.
    agreed_empty: set[str] = set()
    # `PASSES` times round the list: a mirror that is busy right now is often
    # fine a minute later, and the alternative is losing the whole run to one bad
    # moment. `strikes` is per query; `_DOWN` is per run.
    strikes: dict[str, int] = {}
    for attempt in range(1, PASSES + 1):
        for url in ENDPOINTS:
            if url in _DOWN:
                continue
            request = urllib.request.Request(
                url, data=payload, headers={"User-Agent": USER_AGENT}
            )
            try:
                with urllib.request.urlopen(request, timeout=SOCKET_TIMEOUT_S) as response:
                    raw = response.read().decode("utf-8")
                parsed = json.loads(raw)
            except (
                urllib.error.URLError,
                TimeoutError,
                json.JSONDecodeError,
                OSError,
            ) as problem:
                # The status code is most of the diagnosis and the generic
                # handler was throwing it away — every failure, from a slot quota
                # to a hung socket, printed the single word "HTTPError". The
                # three cases below want three different responses, and telling
                # them apart is the only way to pick the right one.
                detail = type(problem).__name__
                pause = min(POLITE_PAUSE_S * attempt, MAX_PAUSE_S)
                if isinstance(problem, urllib.error.HTTPError):
                    detail = f"HTTP {problem.code}"
                    if problem.code == 429:
                        detail += " (over the slot quota — waiting)"
                        pause = SLOT_BACKOFF_S * attempt
                    elif problem.code in (504, 503):
                        # A loaded Overpass refuses rather than queueing, and it
                        # does so in about 30 seconds. It reads almost entirely
                        # as "not this minute" rather than "not this query" —
                        # see `PASSES` for the measurement — so the response is
                        # to ask again, not to make the query smaller.
                        detail += " (mirror loaded — will ask again)"
                # A hang is what gets a mirror struck off, not a refusal: a 504
                # costs a second and might be the next query's success, while a
                # timeout costs SOCKET_TIMEOUT_S every single time it is tried.
                if isinstance(problem, (TimeoutError, socket.timeout)) or isinstance(
                    getattr(problem, "reason", None), (TimeoutError, socket.timeout)
                ):
                    strikes[url] = strikes.get(url, 0) + 1
                    # Never strike off the last one standing. An empty mirror
                    # list turns every remaining layer into an instant failure,
                    # and a slow mirror is worth more than no mirror.
                    if strikes[url] >= MIRROR_STRIKES and len(_DOWN) < len(ENDPOINTS) - 1:
                        _DOWN.add(url)
                        detail += f" — {MIRROR_STRIKES} hangs, dropping it for this run"
                last = f"{url}: {detail}"
                print(f"  pass {attempt} {last} — next mirror", file=sys.stderr, flush=True)
                time.sleep(pause)
                continue
            elements = list(parsed.get("elements", []))
            if not elements:
                # An empty answer is not cached, ever. A regional mirror answers
                # a Dhaka query with 200 and nothing in it (see the note above),
                # and caching that writes a gazetteer silently missing a whole
                # layer — the failure this script's own comments call "a demo
                # that fails on stage, not a smaller gazetteer". A genuinely
                # empty tile costs one refetch on the next run, which is cheap.
                agreed_empty.add(url)
                print(
                    f"  {url} returned 0 elements — not cached, trying the next mirror",
                    file=sys.stderr,
                    flush=True,
                )
                last = f"{url}: empty answer"
                continue
            if cache is not None:
                _write_cache(cache, raw, body)
            return elements
    if len(agreed_empty) >= 2:
        print(
            f"  {len(agreed_empty)} mirrors agree this query matches nothing — "
            "accepting the empty answer",
            file=sys.stderr,
            flush=True,
        )
        if cache is not None:
            _write_cache(cache, '{"elements": []}', body)
        return []
    raise RuntimeError(f"every Overpass mirror failed, last was {last}")


def tile_boxes(tiles: int) -> list[tuple[float, float, float, float]]:
    """The box, or a `tiles` x `tiles` grid of sub-boxes, as (s, w, n, e)."""
    if tiles <= 1:
        return [(BBOX_S, BBOX_W, BBOX_N, BBOX_E)]
    lat_step = (BBOX_N - BBOX_S) / tiles
    lon_step = (BBOX_E - BBOX_W) / tiles
    out: list[tuple[float, float, float, float]] = []
    for row in range(tiles):
        for col in range(tiles):
            out.append(
                (
                    round(BBOX_S + row * lat_step, 6),
                    round(BBOX_W + col * lon_step, 6),
                    round(BBOX_S + (row + 1) * lat_step, 6),
                    round(BBOX_W + (col + 1) * lon_step, 6),
                )
            )
    return out


def fetch(harvest: Harvest, cache_dir: Path) -> list[dict[str, Any]]:
    """Every element for one layer, across its tiles, de-duplicated by OSM id."""
    seen: set[tuple[str, int]] = set()
    out: list[dict[str, Any]] = []
    boxes = tile_boxes(harvest.tiles)
    for index, (south, west, north, east) in enumerate(boxes):
        body = "".join(
            f"{selector}({south},{west},{north},{east});" for selector in harvest.selectors
        )
        suffix = "" if len(boxes) == 1 else f".{index}"
        name = f"{harvest.key}{suffix}.json"
        cached = (cache_dir / name).is_file()
        elements = overpass(body, cache=cache_dir / name)
        # A tiled way can appear in more than one cell when it crosses the
        # boundary; Overpass returns it for each cell whose box it touches.
        for element in elements:
            marker = (str(element.get("type")), int(element.get("id", 0)))
            if marker in seen:
                continue
            seen.add(marker)
            out.append(element)
        if not cached:
            time.sleep(POLITE_PAUSE_S)
    return out


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


def in_box(lat: float, lon: float) -> bool:
    """
    Is this point inside the zone we claim to cover?

    The same test `app/geo/gazetteer.in_pilot_box` applies, and it has to be
    applied here because Overpass does not apply it for us. A bbox filter on a
    `node` returns only nodes inside the box, which is why the pre-S31 harvest
    never needed this — but a bbox filter on a `way` or `relation` returns every
    one that *intersects* the box, and `out center` then reports a centre that
    can be well outside it.

    Measured on the S31 harvest: 13 entries, among them `Narshinghapur Kashimpur
    Road` at 23.9432 (north of the box), `Madanganj - Madanpur Road` at 90.5330
    (east of it) and `Padma Bridge Rail Link`, which is not in Dhaka at all.
    """
    return BBOX_S <= lat <= BBOX_N and BBOX_W <= lon <= BBOX_E


def fold(text: str) -> str:
    """Compare-form of a name: case, punctuation and spacing removed."""
    folded = unicodedata.normalize("NFKC", text).casefold()
    return re.sub(r"[^a-z0-9ঀ-৿]+", "", folded)


_JUNK_FOLDED: Final = frozenset(fold(word) for word in (*JUNK_EN, *JUNK_BN))


def is_junk(bangla: str, latin: str) -> bool:
    """
    True when every name form this feature has is a bare generic word.

    The previous version only tested the romanised name, and only when there was
    no Bangla name at all, so a node whose entire name was "মসজিদ" was kept. With
    the bus-stop, hospital, police and road layers added there are hundreds of
    those and each one is a string the fuzzy matcher has to score on every
    lookup, for a name that could never identify a place.
    """
    forms = [fold(form) for form in (bangla, latin) if form.strip()]
    return bool(forms) and all(form in _JUNK_FOLDED for form in forms)


def metres(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6_371_000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi, dlam = phi2 - phi1, math.radians(lon2 - lon1)
    h = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(h))


# ---------------------------------------------------------------------------
# Roads
# ---------------------------------------------------------------------------
#
# A road is a line and this gazetteer stores a point with a radius. That gap is
# the whole difficulty, and it is not solved by pretending otherwise.
#
# OSM splits one named road into many `way`s, broken at junctions and wherever a
# tag changes. `out tags center` gives the centre of each. So "Satmasjid Road"
# arrives as a few dozen points strung along the real road, which is enough to
# measure the road's extent without fetching any geometry.
#
# Single-link clustering is the right shape for this: consecutive segment centres
# on one road are a few hundred metres apart and chain together however long the
# road is, while two unrelated roads that happen to share a name — and Dhaka has
# "Road No 5" in a dozen neighbourhoods — have nothing between them to chain
# through, so they stay separate clusters and the existing ambiguity machinery
# refuses them. That is the correct answer for "Road No 5": we know the name, we
# cannot say which one, so we decline.

# How close two segment centres of the same name must be to count as one road.
#
# Chain generously, and let the *extent* be the judge. That split of
# responsibilities was arrived at by measuring, not by taste. 1,570 named major-
# road segments in three tiles of the box, clustered at four thresholds:
#
#     chain      entries   pinnable   refused   names split across clusters
#       900 m      550        399       141        47  of 472
#     1,500 m      507        411        86        27
#     2,500 m      491        418        62        15
#     4,000 m      478        419        48         6
#
# A tight threshold does not protect anything; it just shreds long roads. At
# 900 m, Begum Rokeya Sharani came out as six pieces, Mirpur Road as five, and
# Dhaka–Cumilla Highway as four — one arterial each, broken up because a long
# OSM way puts its own centre far from its neighbour's. Those pieces then share a
# name while sitting kilometres apart, so `resolve_collisions` refuses all of
# them: the right answer for Mirpur Road, reached by accident, at the cost of
# five junk entries and of also losing shorter roads like DIT Road.
#
# The obvious worry about chaining this far is the opposite error — merging two
# genuinely different roads that share a name. `ROAD_MAX_RADIUS_M` closes it:
# any merge spanning more than 3 km is refused outright, so the worst a
# surviving merge can do is put the pin within 1.5 km of either road, which is
# exactly what its radius then claims.
ROAD_CHAIN_M: Final = 4_000

# A road entry's radius is half its measured extent. The floor exists because a
# 40 m lane is still not a point.
ROAD_MIN_RADIUS_M: Final = 250

# And the ceiling is where a road stops being a location at all.
#
# One constant doing both jobs is deliberate. Above this, a point and a radius
# cannot describe the road honestly — Mirpur Road is about 8 km end to end, so a
# pin at its midpoint would be 4 km from the event — and the alternative to
# refusing is to publish a claim we know is wrong by kilometres. So the rule is:
# **the radius is always the measured half-extent, and a road whose half-extent
# will not fit under the ceiling is refused rather than clamped into looking
# precise.** 1,500 m is set just above `area`'s 1,200 m, because the system
# already publishes 1,200 m claims for suburbs and a road-shaped claim of the
# same order is consistent with what it already says.
#
# Refused entries are still kept, with `ambiguous` set. Dropping them would send
# the query down to the LLM tier, which will cheerfully invent a point for a road
# it has heard of; keeping them means the loader declines by the same rule that
# declines "Sector 11". The road is known. It is simply not pinnable.
ROAD_MAX_RADIUS_M: Final = 1500
ROAD_REFUSE_HALF_SPAN_M: Final = ROAD_MAX_RADIUS_M


# The same three numbers for water, which OSM fragments the same way. A lake is
# allowed a wider claim than a road because it genuinely is wide in both
# directions — Hatirjheel is about 3 km end to end and a point in the middle of
# it is a fair answer to "Hatirjheel", in a way that the midpoint of an 8 km road
# is not a fair answer to the road's name.
WATER_CHAIN_M: Final = 3_000
WATER_MIN_RADIUS_M: Final = 300
WATER_MAX_RADIUS_M: Final = 2_000


def cluster_roads(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """`cluster_fragments` with the road constants. Kept as its own name because
    the road case is the one the thresholds were measured against."""
    return cluster_fragments(
        segments,
        chain_m=ROAD_CHAIN_M,
        min_radius_m=ROAD_MIN_RADIUS_M,
        max_radius_m=ROAD_MAX_RADIUS_M,
    )


def cluster_water(segments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """`cluster_fragments` with the water constants."""
    return cluster_fragments(
        segments,
        chain_m=WATER_CHAIN_M,
        min_radius_m=WATER_MIN_RADIUS_M,
        max_radius_m=WATER_MAX_RADIUS_M,
    )


def _chain(points: list[tuple[float, float]], limit_m: float) -> list[list[int]]:
    """Single-link clusters of `points`: indices grouped by chained proximity."""
    remaining = set(range(len(points)))
    clusters: list[list[int]] = []
    while remaining:
        seed = remaining.pop()
        group = [seed]
        frontier = [seed]
        while frontier:
            current = frontier.pop()
            near = [
                other
                for other in remaining
                if metres(*points[current], *points[other]) <= limit_m
            ]
            for other in near:
                remaining.discard(other)
                group.append(other)
                frontier.append(other)
        clusters.append(group)
    return clusters


def cluster_fragments(
    segments: list[dict[str, Any]],
    *,
    chain_m: float,
    min_radius_m: int,
    max_radius_m: int,
) -> list[dict[str, Any]]:
    """
    Collapse same-named OSM pieces of one feature into one entry per locality.

    Input rows are the raw per-piece dicts `build` makes for every other kind.
    Output is the same shape, with `lat`/`lon` at the cluster centroid, a measured
    `radius_m`, and `ambiguous` already set on anything too large to pin.

    Written for roads and then needed verbatim for water, which is the useful
    generalisation: **OSM fragments large features, and fragmentation looks
    exactly like ambiguity to `resolve_collisions`.** One road is fifty ways
    broken at junctions; one lake is several polygons plus a relation. In both
    cases the pieces share a name while sitting more than `MERGE_RADIUS_M` apart,
    so the generic duplicate rule marks them all ambiguous and the loader then
    refuses a place that is not ambiguous at all — it is simply big.

    Measured: Hatirjheel arrived as three objects all named হাতিরঝিল হ্রদ, 0.6,
    1.0 and 1.2 km from the lake's reference point. All three were refused, so
    "Hatirjheel" fell through to the subset tier and resolved to *Hatirjheel
    Park*, a 300 m feature 2.5 km away — a wrong pin produced by having more
    data about things near the lake than about the lake.
    """
    by_name: dict[str, list[dict[str, Any]]] = {}
    for segment in segments:
        key = fold(segment["name_en"]) or fold(segment["name_bn"])
        if key:
            by_name.setdefault(key, []).append(segment)

    out: list[dict[str, Any]] = []
    for rows in by_name.values():
        points = [(row["lat"], row["lon"]) for row in rows]
        for group in _chain(points, chain_m):
            members = [rows[index] for index in group]
            lat = sum(row["lat"] for row in members) / len(members)
            lon = sum(row["lon"] for row in members) / len(members)
            half_span = max(metres(lat, lon, row["lat"], row["lon"]) for row in members)
            # The lowest OSM id, chosen for one reason: it does not depend on the
            # order Overpass returned the ways in, so a re-harvest produces the
            # same entry id for the same road. `aliases.json` is keyed by entry
            # id, and `main` refuses to write a file that has orphaned one.
            seed = min(members, key=lambda row: row["id"])
            # OSM tags road segments unevenly — the lowest-id way may carry only
            # `name` in Bangla while a later one carries `name:en` too. Taking the
            # seed's record wholesale would file that romanisation as an alias and
            # leave `display_name` Bangla-only, so each side is filled from the
            # first member that has it.
            name_bn = seed["name_bn"] or next(
                (row["name_bn"] for row in members if row["name_bn"]), ""
            )
            name_en = seed["name_en"] or next(
                (row["name_en"] for row in members if row["name_en"]), ""
            )
            names = [
                name
                for row in members
                for name in (row["name_bn"], row["name_en"])
                if name
            ]
            aliases = [alias for row in members for alias in row["aliases"]]
            own = {fold(name_bn), fold(name_en)}
            out.append(
                {
                    **seed,
                    "name_bn": name_bn,
                    "name_en": name_en,
                    "aliases": [
                        name
                        for name in dict.fromkeys([*aliases, *names])
                        if fold(name) not in own
                    ],
                    "lat": round(lat, 6),
                    "lon": round(lon, 6),
                    # For a road that survives, this is exactly the measured
                    # half-extent. The upper clamp only ever applies to one that
                    # has already been refused on the next line, so no entry
                    # carries an absurd radius even though no entry needs it.
                    "radius_m": int(min(max(round(half_span), min_radius_m), max_radius_m)),
                    "segments": len(members),
                    "span_m": int(round(half_span * 2)),
                    "ambiguous": half_span > max_radius_m,
                }
            )
    return out


# ---------------------------------------------------------------------------
# Collisions
# ---------------------------------------------------------------------------

# Two entries sharing a name this close together are one place that OSM lists in
# more than one layer, not two places. Measured on the harvest: "Farmgate" appears
# as a neighbourhood and a terminal 276 m apart, "TSC Mor" twice 15 m apart, while
# Uttara's and Bashundhara's "Sector 11" are 10 km apart. Anything inside this
# radius is merged; anything outside it is a genuine ambiguity.
MERGE_RADIUS_M: Final = 1_000

# Most specific first. When merging duplicates, the narrower kind wins: if OSM
# named a junction exactly what the user typed, the junction is the landmark meant.
#
# The order below is not just "smaller radius first". `road` sits behind
# `neighbourhood` and `area` because a road's centroid is the least precise point
# in the file, and `stop` sits last because a bus stop's name is almost always
# borrowed from the place it serves — keeping the stop and dropping the
# neighbourhood would shrink a 600 m area claim to a 120 m pin at a kerb.
KIND_SPECIFICITY: Final[dict[str, int]] = {
    "junction": 0,
    "bridge": 1,
    "terminal": 2,
    "mall": 3,
    "market": 4,
    "campus": 5,
    "hospital": 6,
    "police": 7,
    "park": 8,
    "neighbourhood": 9,
    "area": 10,
    "water": 11,
    "town": 12,
    "road": 13,
    "stop": 14,
}

# A kind that gives a place its name, against a kind that borrows one. A bus stop
# called "Mohakhali" does not make "Mohakhali" ambiguous; it is named after
# Mohakhali. See `_drop_borrowed_names`.
NAMING_KINDS: Final = frozenset(
    {"junction", "bridge", "terminal", "mall", "market", "neighbourhood", "area", "water", "town", "road"}
)
BORROWING_KINDS: Final = frozenset({"stop", "campus", "hospital", "police", "park"})


def _name_groups(entries: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        for name in (entry["name_bn"], entry["name_en"]):
            if name:
                groups.setdefault(fold(name), []).append(entry)
    return groups


def _drop_borrowed_names(entries: list[dict[str, Any]], annotated: frozenset[str]) -> list[dict[str, Any]]:
    """
    Stop a borrowed name from making the place it was borrowed from ambiguous.

    This is new in S31 and it exists because of the layers S31 added. OSM names
    Dhaka's bus stops, hospital gates and police stations after their
    neighbourhoods, and those features sit well over `MERGE_RADIUS_M` from the
    neighbourhood's label node. Left alone, `resolve_collisions` would read that
    as "two different places share a name", mark both ambiguous, and the loader
    would then refuse the neighbourhood — so adding the vernacular layer would
    have *removed* Mohakhali, Farmgate and Shewrapara from the gazetteer.

    When exactly one entry in a name group is a kind that names a place and every
    other is a kind that borrows one, the borrowers lose that name: it is struck
    from their own name fields, and an entry left with no name at all is dropped.
    Nothing is lost that was not a duplicate — a stop whose only name is
    "Mohakhali" tells us nothing the Mohakhali entry does not.

    An entry a person has written aliases for is never stripped. The hand file is
    the most reliable thing in the gazetteer and it is keyed by entry id.
    """
    drop: set[int] = set()
    for folded, members in _name_groups(entries).items():
        rows = list({id(row): row for row in members}.values())
        if len(rows) < 2:
            continue
        spread = max(
            metres(a["lat"], a["lon"], b["lat"], b["lon"])
            for i, a in enumerate(rows)
            for b in rows[i + 1:]
        )
        if spread <= MERGE_RADIUS_M:
            continue  # one place in several layers; resolve_collisions merges it
        owners = [row for row in rows if row["kind"] in NAMING_KINDS]
        borrowers = [
            row
            for row in rows
            if row["kind"] in BORROWING_KINDS and row["id"] not in annotated
        ]
        if len(owners) != 1 or len(borrowers) != len(rows) - 1:
            continue  # a real ambiguity, or not one this rule can judge
        for row in borrowers:
            for field_name in ("name_bn", "name_en"):
                if fold(row[field_name]) == folded:
                    row[field_name] = ""
            row["aliases"] = [a for a in row["aliases"] if fold(a) != folded]
            if not (row["name_bn"] or row["name_en"]):
                drop.add(id(row))
    return [entry for entry in entries if id(entry) not in drop]


def resolve_collisions(
    entries: list[dict[str, Any]], annotated: frozenset[str] = frozenset()
) -> list[dict[str, Any]]:
    """
    Decide what a repeated name means, and act on it.

    Same name, close together -> one place listed twice. Keep the most specific
    one and drop the rest, so the matcher is not forced to choose between two
    records of the same thing and refuse.

    Same name, far apart -> genuinely different places. Flag every one of them
    `ambiguous`; the loader then refuses such a query rather than picking. That is
    the discard invariant, and getting it wrong in the other direction is worse:
    before this function looked at distance, the gazetteer refused "Farmgate".

    `annotated` is the set of entry ids `aliases.json` has hand-written names
    for. Those entries win every merge. The hand file is keyed by id, so a merge
    that picked a different record would silently orphan a person's work — and
    the demo types one of those aliases on stage.
    """
    groups = _name_groups(entries)

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
                key=lambda r: (
                    r["id"] not in annotated,
                    KIND_SPECIFICITY.get(r["kind"], 99),
                    not (r["name_bn"] and r["name_en"]),
                    r["id"],
                ),
            )
            for row in rows:
                if row is not keeper:
                    drop.add(id(row))
                else:
                    # Merging loses the other records' spellings otherwise.
                    extra = [
                        n
                        for r in rows
                        if r is not keeper
                        for n in (r["name_bn"], r["name_en"])
                        if n
                    ]
                    keeper["aliases"] = list(dict.fromkeys([*keeper["aliases"], *extra]))
                    # One name in several layers is one place, and the widest
                    # layer is the honest extent of what we know. Keeping the
                    # most specific *point* while shrinking to its radius would
                    # turn the Farmgate area into the Farmgate bus bay.
                    keeper["radius_m"] = max(int(r["radius_m"]) for r in rows)
        else:
            for row in rows:
                row["ambiguous"] = True

    kept = [e for e in entries if id(e) not in drop]
    # An alias identical to the entry's own name adds nothing; drop the noise.
    for entry in kept:
        own = {fold(entry["name_bn"]), fold(entry["name_en"])}
        entry["aliases"] = [a for a in entry["aliases"] if fold(a) not in own]
    return kept


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------


def build(cache_dir: Path, annotated: frozenset[str]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    # Kinds OSM delivers in pieces, held back so same-named pieces can be joined
    # before `resolve_collisions` mistakes the fragmentation for ambiguity.
    fragmented: dict[str, list[dict[str, Any]]] = {"road": [], "water": []}
    seen_osm: set[str] = set()

    for harvest in HARVESTS:
        print(f"querying {harvest.key} ...", file=sys.stderr, flush=True)
        # A failure here aborts the run on purpose. A gazetteer silently missing
        # every junction is a demo that fails on stage, not a smaller gazetteer.
        # The cache means re-running only fetches what is still missing.
        kept = 0
        strays = 0
        for element in fetch(harvest, cache_dir):
            tags = element.get("tags", {})
            point = coordinates(element)
            if point is None:
                continue
            # A way or relation that merely touches the box comes back with a
            # centre outside it. Dropping the piece rather than the finished
            # entry keeps every cluster centroid inside the box too, since a
            # centroid of in-box points cannot fall outside their hull.
            if not in_box(*point):
                strays += 1
                continue
            bangla, latin = split_names(tags)
            if not bangla and not latin:
                continue
            # A bare generic word resolves nothing and would match everything.
            if is_junk(bangla, latin):
                continue

            osm_id = f"{element['type']}/{element['id']}"
            if osm_id in seen_osm:
                continue
            seen_osm.add(osm_id)

            row = {
                "id": f"osm-{element['type']}-{element['id']}",
                "name_bn": bangla,
                "name_en": latin,
                "aliases": harvested_aliases(tags),
                "kind": harvest.kind,
                "lat": round(point[0], 6),
                "lon": round(point[1], 6),
                "radius_m": DEFAULT_RADIUS_M.get(harvest.kind, 300),
                "source": f"osm:{osm_id}",
                "reviewed": False,
                "ambiguous": False,
            }
            fragmented.get(harvest.kind, entries).append(row)
            kept += 1
        outside = f", {strays} outside the box" if strays else ""
        print(f"  kept {kept}{outside}", file=sys.stderr, flush=True)

    for kind, cluster in (("road", cluster_roads), ("water", cluster_water)):
        pieces = fragmented[kind]
        if not pieces:
            continue
        joined = cluster(pieces)
        print(
            f"{kind}: {len(pieces)} pieces -> {len(joined)} entries "
            f"({sum(1 for r in joined if r['ambiguous'])} too large to pin)",
            file=sys.stderr,
            flush=True,
        )
        entries.extend(joined)

    entries = _drop_borrowed_names(entries, annotated)
    entries = resolve_collisions(entries, annotated)
    entries.sort(key=lambda e: (e["kind"], e["name_en"] or e["name_bn"]))
    return entries


README: Final = {
    "zone": "Dhaka city — Dhaka North and Dhaka South city corporations, with a margin",
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
        "kind": (
            "junction | bridge | terminal | mall | market | campus | hospital | "
            "police | park | neighbourhood | area | town | road | stop."
        ),
        "radius_m": (
            "Default by kind, and a judgment call rather than a measurement — "
            "except on a road, where it is half the measured extent of the "
            "road's own segments, clamped to [250, 1500]."
        ),
        "source": "osm:<type>/<id>, or 'manual' for a hand-added entry.",
        "reviewed": "True only once a person has checked this row. The harvest sets false.",
        "ambiguous": (
            "True when this entry's name cannot identify one place: either the "
            "name is shared with another entry far enough away that choosing "
            "would put the pin kilometres wrong, or the entry is a road longer "
            "than 3 km, which a point and a radius cannot describe honestly. "
            "The loader refuses to resolve a query that matches only ambiguous "
            "entries, rather than picking one."
        ),
        "segments": "Roads only. How many OSM ways were merged into this entry.",
        "span_m": "Roads only. The measured end-to-end extent of those ways.",
    },
    "roads_are_lines_and_this_file_stores_points": (
        "A road arrives from OSM as many short ways. Their centres are chained "
        "into one entry per road per locality, the point is the centroid and the "
        "radius is half the measured extent. A road over 3 km long is marked "
        "ambiguous instead, because a pin at the midpoint of Mirpur Road would "
        "be up to 4 km from the incident and a wrong pin is worse than no pin."
    ),
    "hand_work_still_outstanding": (
        "aliases and radius_m. OSM spells the Mirpur 10 roundabout "
        "'গোলচক্কর'; much of Dhaka says 'গোলচত্বর'. The gazetteer is only "
        "better than a general map once those synonyms are in."
    ),
}


def load_annotated(path: Path) -> frozenset[str]:
    """Entry ids `aliases.json` has hand-written names for. Never overridden."""
    if not path.is_file():
        print(f"  no aliases file at {path}", file=sys.stderr, flush=True)
        return frozenset()
    payload = json.loads(path.read_text(encoding="utf-8"))
    return frozenset(key for key in payload if not key.startswith("_"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    data = Path(__file__).resolve().parent.parent / "data" / "gazetteer"
    parser.add_argument("--out", default=str(data / "dhaka_central.json"))
    parser.add_argument(
        "--aliases",
        default=str(data / "aliases.json"),
        help="Hand-written aliases. Read only, to protect annotated ids from being merged away.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--cache-dir",
        default=str(data / ".osm-cache"),
        help="Raw Overpass answers, so a re-run resumes. Delete it to refetch.",
    )
    parser.add_argument(
        "--refresh", action="store_true", help="Ignore the cache and refetch everything."
    )
    args = parser.parse_args()

    cache_dir = Path(args.cache_dir)
    if args.refresh and cache_dir.is_dir():
        for stale in (*cache_dir.glob("*.json"), *cache_dir.glob("*.query.txt")):
            stale.unlink()
        print(f"cleared {cache_dir}", file=sys.stderr, flush=True)

    annotated = load_annotated(Path(args.aliases))
    print(f"{len(annotated)} hand-annotated entry ids will win every merge", file=sys.stderr, flush=True)

    try:
        entries = build(cache_dir, annotated)
    except RuntimeError as problem:
        print(f"harvest failed: {problem}", file=sys.stderr, flush=True)
        return 1

    by_kind: dict[str, int] = {}
    for entry in entries:
        by_kind[entry["kind"]] = by_kind.get(entry["kind"], 0) + 1
    ambiguous = sum(1 for e in entries if e["ambiguous"])
    both = sum(1 for e in entries if e["name_bn"] and e["name_en"])
    missing = sorted(annotated - {e["id"] for e in entries})

    print(f"\n{len(entries)} entries", file=sys.stderr, flush=True)
    for kind, count in sorted(by_kind.items(), key=lambda row: -row[1]):
        print(f"  {kind:16s} {count:5d}", file=sys.stderr, flush=True)
    print(f"  both name forms  {both:5d}", file=sys.stderr, flush=True)
    print(f"  ambiguous        {ambiguous:5d}", file=sys.stderr, flush=True)

    if missing:
        # Loud and fatal. An orphaned id means a person's hand-written aliases
        # silently stop working, and the demo types one of them on stage.
        print(
            f"\nREFUSING TO WRITE: {len(missing)} id(s) in {args.aliases} are not in "
            f"this harvest: {', '.join(missing[:8])}",
            file=sys.stderr,
        )
        return 2

    if args.dry_run:
        print("\n--dry-run: nothing written", file=sys.stderr, flush=True)
        return 0

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps({"_README": README, "entries": entries}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"\nwrote {out}", file=sys.stderr, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
