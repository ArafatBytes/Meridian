"""
The Dhaka-central gazetteer: load it, and match what someone typed against it.

    from app.geo.gazetteer import gazetteer

    hit = gazetteer().resolve("Mirpur 10 golchattar")

Two files, and the split matters
--------------------------------
    data/gazetteer/dhaka_central.json   harvested from OpenStreetMap. Regenerable
                                        by scripts/harvest_gazetteer.py. **Never
                                        hand-edit it** — a re-harvest overwrites it.
    data/gazetteer/aliases.json         hand-written. Never generated. This is
                                        where the human work lives and survives.

They are separate because the hand work is the valuable part and a re-harvest
would otherwise destroy it. Merged at load time, keyed by gazetteer entry id.

What matching can and cannot do
-------------------------------
Fuzzy matching fixes **spellings**. Aliases fix **synonyms**. They are different
problems and only one of them is automatable:

    "Mirpur 10 Circle"      -> matches, token subset of "Mirpur-10 Circle"
    "Mirpur 10 Cirlce"      -> matches, one transposed letter
    "মিরপুর ১০"              -> matches, Bengali digits folded to Latin
    "Mirpur 10 golchattar"  -> matches ONLY via aliases.json

No edit distance reaches "golchattar" from "Circle"; they share no letters. OSM
spells that roundabout গোলচক্কর and much of Dhaka says গোলচত্বর — a different
word for the same place. That is why `aliases.json` exists and why it is
hand-maintained.

Ambiguity is refused, not guessed
---------------------------------
Dhaka has an Uttara "Sector 11" and a Bashundhara "Sector 11", 10 km apart. When
a query's only candidates are entries the harvest flagged `ambiguous`, or when
two different entries tie on score, `resolve()` returns None. The caller turns
that into `method="unresolved"`. This is the "unresolvable locations are
discarded, never guessed" invariant: a wrong pin is worse than no pin, and the
plan expects a judge to test exactly this.
"""

from __future__ import annotations

import difflib
import json
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

logger = logging.getLogger(__name__)

DATA_DIR: Final = Path(__file__).resolve().parents[1].parent / "data" / "gazetteer"
GAZETTEER_PATH: Final = DATA_DIR / "dhaka_central.json"
ALIASES_PATH: Final = DATA_DIR / "aliases.json"

# The pilot box, matching scripts/harvest_gazetteer.py. Also the sanity gate the
# LLM tier is checked against, which is why it is not simply "all of Bangladesh":
# the wider this box, the less an out-of-box answer tells us.
#
# S31 widened it from 23.70–23.90 / 90.33–90.50 to cover both Dhaka city
# corporations. The old box stopped inside the city — Uttarkhan, Dakshinkhan and
# Turag in the north, Demra, Matuail and Kadamtali in the south were all outside
# it, so an article about any of them was discarded for being out of area rather
# than for anything to do with the article. Savar, Narayanganj city and Gazipur
# city are still outside on purpose: they are different cities.
BBOX_S: Final = 23.66
BBOX_W: Final = 90.30
BBOX_N: Final = 23.94
BBOX_E: Final = 90.54

# Bengali digits are a different Unicode block from Latin ones, so "মিরপুর ১০"
# and "Mirpur 10" share no numeric characters at all. 55 entries in the pilot box
# carry a number; without this fold, half of every sector lookup fails silently.
_BENGALI_DIGITS: Final = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")

_KEEP = re.compile(r"[^a-z0-9ঀ-৿ ]+")
_SPACES = re.compile(r"\s+")
_NUMBER = re.compile(r"\d+")

# A query must be at least this similar to count as a fuzzy match. 0.86 was
# chosen by trying it: it accepts one transposition in a short name
# ("Cirlce"/"Circle" is 0.83 on its own but the full string carries it) and
# rejects "Mohakhali"/"Mohammadpur", which are 0.63 and are different places.
FUZZY_FLOOR: Final = 0.86

# Above this, two candidates are treated as a tie and the query is refused rather
# than resolved to whichever happened to sort first.
TIE_WINDOW: Final = 0.02


def normalise(text: str) -> str:
    """Compare-form of a name: one script for digits, no case, no punctuation."""
    folded = unicodedata.normalize("NFKC", text).casefold().translate(_BENGALI_DIGITS)
    return _SPACES.sub(" ", _KEEP.sub(" ", folded)).strip()


def tokens(text: str) -> frozenset[str]:
    return frozenset(normalise(text).split())


def numbers(text: str) -> tuple[str, ...]:
    """
    Every number in a name, sorted. Compared for equality, never for similarity.

    `normalise` has already folded Bengali digits to Latin, so "মিরপুর ১০" and
    "Mirpur 10" both yield ("10",).
    """
    return tuple(sorted(_NUMBER.findall(normalise(text))))


@dataclass(frozen=True, slots=True)
class GazetteerEntry:
    id: str
    name_bn: str
    name_en: str
    aliases: tuple[str, ...]
    kind: str
    lat: float
    lon: float
    radius_m: int
    source: str
    reviewed: bool
    ambiguous: bool

    @property
    def display_name(self) -> str:
        """What to show a user. Romanised if we have it, Bangla otherwise."""
        return self.name_en or self.name_bn

    def all_names(self) -> tuple[str, ...]:
        return tuple(n for n in (self.name_bn, self.name_en, *self.aliases) if n)


@dataclass(frozen=True, slots=True)
class GazetteerHit:
    entry: GazetteerEntry
    confidence: float
    matched: str
    """Which of the entry's name forms the query actually matched."""


class GazetteerError(RuntimeError):
    """The gazetteer file is missing or malformed. Not a lookup failure."""


@dataclass(frozen=True, slots=True)
class _Name:
    """
    One name form of one entry, with everything matching needs precomputed.

    Every tier used to call `normalise`, `tokens` and `numbers` on every name of
    every entry on every lookup. That was affordable at 1,022 entries and is not
    at six thousand: `resolve_place` is on a request path (`/geo/resolve`), and
    the fuzzy tier alone was running two regex substitutions and a findall per
    name per query before it got as far as comparing anything.
    """

    entry: GazetteerEntry
    raw: str
    text: str
    """`normalise(raw)`."""
    tokens: frozenset[str]
    numbers: tuple[str, ...]
    position: int
    """Index of this name within its entry's `all_names()`, to keep tier 2's
    "first matching name wins" behaviour identical to the unindexed version."""


@dataclass
class Gazetteer:
    entries: tuple[GazetteerEntry, ...]
    _exact: dict[str, list[GazetteerEntry]] = field(default_factory=dict, repr=False)
    _names: tuple[_Name, ...] = field(default=(), repr=False)
    _by_token: dict[str, frozenset[int]] = field(default_factory=dict, repr=False)
    _by_numbers: dict[tuple[str, ...], tuple[int, ...]] = field(
        default_factory=dict, repr=False
    )

    def __post_init__(self) -> None:
        names: list[_Name] = []
        by_token: dict[str, set[int]] = {}
        by_numbers: dict[tuple[str, ...], list[int]] = {}
        for entry in self.entries:
            for position, raw in enumerate(entry.all_names()):
                text = normalise(raw)
                self._exact.setdefault(text, []).append(entry)
                if not text:
                    continue
                index = len(names)
                token_set = frozenset(text.split())
                digits = numbers(raw)
                names.append(
                    _Name(
                        entry=entry,
                        raw=raw,
                        text=text,
                        tokens=token_set,
                        numbers=digits,
                        position=position,
                    )
                )
                for token in token_set:
                    by_token.setdefault(token, set()).add(index)
                by_numbers.setdefault(digits, []).append(index)
        self._names = tuple(names)
        self._by_token.update({token: frozenset(rows) for token, rows in by_token.items()})
        self._by_numbers.update({key: tuple(rows) for key, rows in by_numbers.items()})

    def __len__(self) -> int:
        return len(self.entries)

    def resolve(self, query: str) -> GazetteerHit | None:
        """
        Best match for `query`, or None when there is no safe answer.

        Tiers, in order, stopping at the first that produces a single winner:

            1. exact match on any name form or alias          confidence 1.00
            2. every query token present in one entry's names confidence 0.90
            3. character similarity at or above FUZZY_FLOOR   confidence = ratio

        None means "do not put a pin here" — no match, only ambiguous matches, or
        a tie between two different places.
        """
        wanted = normalise(query)
        if not wanted:
            return None

        hit = self._exact_hit(wanted)
        if hit is not None:
            return hit

        # A refusal for ambiguity is a decision, and the tiers below do not get
        # to overturn it. The module docstring already says this about the LLM
        # tier; it has to hold *inside* the gazetteer too, and it did not.
        #
        # "Sector 11" is the case. Two entries carry that exact name 10 km
        # apart, so `_exact_hit` correctly declines — and then `_subset_hit`
        # resolved it anyway, to a different entry, and reported 0.90. Falling
        # through means "we know this name is ambiguous" is treated as "we have
        # never heard of it", which are opposite facts.
        if self._exact_is_ambiguous_only(wanted):
            logger.info("gazetteer refusing %r — its exact matches are ambiguous", wanted)
            return None

        hit = self._subset_hit(wanted)
        if hit is not None:
            return hit
        return self._fuzzy_hit(wanted)

    def matches_ambiguous_only(self, query: str) -> bool:
        """
        Did this query hit a name we deliberately refuse, or nothing at all?

        The two look identical from `resolve()` — both return None — but they mean
        opposite things, and only the caller can act on the difference:

            nothing at all   we have never heard of this. Ask the LLM.
            ambiguous        we know this name belongs to two different places.
                             **Do not ask the LLM.**

        That second case is a decision, not a gap. "Sector 11" is Uttara's and
        Bashundhara's, 10 km apart; the gazetteer knows that and the model does
        not. Before this existed, the LLM tier answered "Sector 11" with Uttara and
        quietly overturned a refusal that was correct — our own ambiguity guard was
        bypassable by the weaker tier below it.
        """
        wanted = normalise(query)
        if not wanted:
            return False
        exact = self._exact.get(wanted, [])
        if exact and all(entry.ambiguous for entry in exact):
            return True
        want = frozenset(wanted.split())
        if not want:
            return False
        postings = [self._by_token.get(token) for token in want]
        if any(rows is None for rows in postings):
            return False
        ordered = sorted((rows for rows in postings if rows is not None), key=len)
        candidates: frozenset[int] = ordered[0]
        for rows in ordered[1:]:
            candidates &= rows
            if not candidates:
                return False
        # Only reached once `resolve()` has already declined, so any ambiguous
        # entry the query fits is the reason it declined.
        return any(self._names[index].entry.ambiguous for index in candidates)

    # -- tiers ---------------------------------------------------------------

    def _exact_is_ambiguous_only(self, wanted: str) -> bool:
        """Does this exact name belong to entries, and all of them ambiguous?"""
        rows = self._exact.get(wanted, [])
        return bool(rows) and all(entry.ambiguous for entry in rows)

    def _exact_hit(self, wanted: str) -> GazetteerHit | None:
        candidates = self._usable(self._exact.get(wanted, []))
        if len(candidates) != 1:
            # Zero means no exact match; more than one means the same name
            # belongs to two different places and we must not choose.
            return None
        return GazetteerHit(candidates[0], 1.0, wanted)

    def _subset_hit(self, wanted: str) -> GazetteerHit | None:
        """
        "Mirpur 10" should find "Mirpur-10 Circle". Every token must appear.

        Every token must appear, so the candidates are exactly the intersection
        of the token index's posting lists — and a query token no name contains
        settles it with no scan at all.
        """
        want = frozenset(wanted.split())
        if not want:
            return None
        postings = [self._by_token.get(token) for token in want]
        if any(rows is None for rows in postings):
            return None
        # Intersect smallest-first; one rare token usually reduces this to a
        # handful of candidates before the common ones are touched.
        ordered = sorted((rows for rows in postings if rows is not None), key=len)
        candidates: frozenset[int] = ordered[0]
        for rows in ordered[1:]:
            candidates &= rows
            if not candidates:
                return None

        # Numbers are identity here too, and this tier was the one place that did
        # not enforce it. `_fuzzy_hit` has refused a number mismatch since D03,
        # on the grounds that "Sector 11" and "Sector 10" are 0.89 similar and
        # 2 km apart — but a *token subset* can mismatch far more wildly than a
        # misspelling and still pass:
        #
        #     query "Sector 11"          -> {sector, 11}
        #     name  "Road 11 Sector 1"   -> {road, 11, sector, 1}   superset!
        #
        # so the query matched a road in Sector 1 and reported 0.90. It was
        # harmless while the gazetteer held no roads and is a fabrication now
        # that it holds three thousand, which is the shape of hole worth
        # remembering: the new data did not break this tier, it revealed it.
        #
        # Requiring the same multiset of digits keeps every case this tier is
        # for — "Mirpur 10" still finds "Mirpur-10 Circle", ("10",) both sides —
        # and drops the ones where a number is doing the lying.
        wanted_numbers = numbers(wanted)

        # One name per entry, the first in `all_names()` order, exactly as the
        # unindexed version's `break` produced.
        best_by_entry: dict[str, _Name] = {}
        for index in candidates:
            name = self._names[index]
            if name.entry.ambiguous or name.numbers != wanted_numbers:
                continue
            held = best_by_entry.get(name.entry.id)
            if held is None or name.position < held.position:
                best_by_entry[name.entry.id] = name
        if not best_by_entry:
            return None

        # Prefer the shortest matching name: it is the closest thing to what was
        # actually typed. "Sayedabad" should find the Sayedabad area, not
        # "Golden Line Sayedabad Counter", which also contains the word. Refuse
        # only when two *different* places tie at the shortest length, because
        # then there genuinely is no way to choose.
        usable = list(best_by_entry.values())
        fewest = min(len(name.tokens) for name in usable)
        shortest = [name for name in usable if len(name.tokens) == fewest]
        if len({name.entry.id for name in shortest}) != 1:
            return None
        return GazetteerHit(shortest[0].entry, 0.9, shortest[0].raw)

    def _fuzzy_hit(self, wanted: str) -> GazetteerHit | None:
        # Numbers are identity, not spelling. "Sector 11" and "Sector 10" are
        # 0.89 similar as strings and are different places 2 km apart; likewise
        # "Mirpur 10" and "Mirpur 11", or "Road 27" and "Road 2". Before this
        # guard the matcher resolved "Sector 11" to Sector 10 and reported 0.89
        # confidence, which is the wrong-pin failure the discard invariant exists
        # to prevent. Letters may be misspelt. Digits may not. As an index it is
        # also the cheapest filter available, so it goes first.
        bucket = self._by_numbers.get(numbers(wanted))
        if not bucket:
            return None

        wanted_length = len(wanted)
        # `difflib` guarantees ratio <= quick_ratio <= real_quick_ratio, and both
        # bounds are symmetric in their arguments, so they can be computed from a
        # matcher that keeps `wanted` as seq2 and never rebuilds its index. The
        # surviving few are then scored in the original argument order, so the
        # confidence a hit reports is unchanged.
        gate = difflib.SequenceMatcher(None, "", wanted)
        scored: list[tuple[float, GazetteerEntry, str]] = []
        for index in bucket:
            name = self._names[index]
            if name.entry.ambiguous:
                continue
            text = name.text
            # ratio = 2M/(la+lb) and M <= min(la, lb), so a name whose length is
            # too far from the query's cannot reach the floor however it is spelt.
            # Exact, not a heuristic: no match is lost to it.
            if 2 * min(len(text), wanted_length) < FUZZY_FLOOR * (len(text) + wanted_length):
                continue
            gate.set_seq1(text)
            if gate.real_quick_ratio() < FUZZY_FLOOR or gate.quick_ratio() < FUZZY_FLOOR:
                continue
            ratio = difflib.SequenceMatcher(None, wanted, text).ratio()
            if ratio >= FUZZY_FLOOR:
                scored.append((ratio, name.entry, name.raw))
        if not scored:
            return None
        scored.sort(key=lambda row: row[0], reverse=True)
        best = scored[0]
        # Refuse a photo finish between two different places.
        rivals = {row[1].id for row in scored if best[0] - row[0] <= TIE_WINDOW}
        if len(rivals) > 1:
            logger.info("gazetteer refusing %r — %d candidates tied", wanted, len(rivals))
            return None
        return GazetteerHit(best[1], round(best[0], 3), best[2])

    @staticmethod
    def _usable(found: list[GazetteerEntry]) -> list[GazetteerEntry]:
        unique = {entry.id: entry for entry in found if not entry.ambiguous}
        return list(unique.values())


def _entry_from(row: dict[str, Any], extra_aliases: tuple[str, ...]) -> GazetteerEntry:
    try:
        return GazetteerEntry(
            id=str(row["id"]),
            name_bn=str(row.get("name_bn", "")),
            name_en=str(row.get("name_en", "")),
            aliases=tuple(dict.fromkeys((*row.get("aliases", []), *extra_aliases))),
            kind=str(row["kind"]),
            lat=float(row["lat"]),
            lon=float(row["lon"]),
            radius_m=int(row["radius_m"]),
            source=str(row.get("source", "unknown")),
            # An entry with hand-written aliases has by definition been read by a
            # person who supplied its local names, so it counts as reviewed. The
            # harvested file always says false, and is overwritten on every
            # re-harvest, so it cannot be the place the review flag lives.
            reviewed=bool(row.get("reviewed", False)) or bool(extra_aliases),
            ambiguous=bool(row.get("ambiguous", False)),
        )
    except (KeyError, TypeError, ValueError) as problem:
        raise GazetteerError(f"malformed gazetteer entry {row.get('id', '?')!r}: {problem}") from problem


def load(
    gazetteer_path: Path | None = None, aliases_path: Path | None = None
) -> Gazetteer:
    """Read both files and merge them. Raises `GazetteerError` on a bad file."""
    path = gazetteer_path or GAZETTEER_PATH
    if not path.is_file():
        raise GazetteerError(
            f"{path} is missing — run `python backend/scripts/harvest_gazetteer.py`"
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as problem:
        raise GazetteerError(f"{path} is not valid JSON: {problem}") from problem

    aliases = _load_aliases(aliases_path or ALIASES_PATH)
    rows = payload.get("entries", [])
    if not isinstance(rows, list) or not rows:
        raise GazetteerError(f"{path} has no entries")

    entries = tuple(_entry_from(row, aliases.get(str(row.get("id")), ())) for row in rows)
    unmatched = set(aliases) - {e.id for e in entries}
    if unmatched:
        # Loud, because a typo'd id means hand-written aliases silently doing
        # nothing — and the aliases are the whole point of the file.
        logger.warning(
            "aliases.json names %d id(s) not in the gazetteer: %s",
            len(unmatched), ", ".join(sorted(unmatched)[:5]),
        )
    _warn_about_alias_collisions(entries, aliases)
    return Gazetteer(entries)


def _warn_about_alias_collisions(
    entries: tuple[GazetteerEntry, ...], aliases: dict[str, tuple[str, ...]]
) -> None:
    """
    Report a hand-written alias that duplicates another entry's own name.

    The harvest cannot catch this: it merges duplicates by comparing *harvested*
    names, and an alias is added afterwards. The effect is quietly bad — two
    entries then match the query exactly, and `resolve()` refuses rather than
    choosing, so a landmark that looks aliased stops resolving at all.

    This happened: "গাবতলী" was added as an alias of `Gabtoli Bus station` while a
    second OSM record 261 m away already carried গাবতলী as its name, and the query
    went from working to unresolved.
    """
    owners: dict[str, set[str]] = {}
    for entry in entries:
        for own in (entry.name_bn, entry.name_en):
            if own:
                owners.setdefault(normalise(own), set()).add(entry.id)

    for entry_id, hand_written in aliases.items():
        for alias in hand_written:
            holders = owners.get(normalise(alias), set())
            if holders - {entry_id}:
                logger.warning(
                    "aliases.json: %r on %s is already the name of %s — the query "
                    "will be refused as ambiguous instead of resolving",
                    alias, entry_id, ", ".join(sorted(holders - {entry_id})),
                )


def _load_aliases(path: Path) -> dict[str, tuple[str, ...]]:
    if not path.is_file():
        logger.warning("%s not found — no hand-written aliases loaded", path)
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as problem:
        raise GazetteerError(f"{path} is not valid JSON: {problem}") from problem
    out: dict[str, tuple[str, ...]] = {}
    for key, value in payload.items():
        if key.startswith("_"):  # _README and friends
            continue
        if not isinstance(value, list):
            raise GazetteerError(f"{path}: aliases for {key!r} must be a list")
        out[key] = tuple(str(v) for v in value if str(v).strip())
    return out


_CACHE: Gazetteer | None = None


def gazetteer() -> Gazetteer:
    """The process-wide gazetteer. Loaded once; it is a read-only data file."""
    global _CACHE
    if _CACHE is None:
        _CACHE = load()
        logger.info("gazetteer loaded: %d entries", len(_CACHE))
    return _CACHE


def reset_cache() -> None:
    """Drop the cached gazetteer. For tests, and after a re-harvest in a dev run."""
    global _CACHE
    _CACHE = None


def in_pilot_box(lat: float, lon: float) -> bool:
    """
    Is this point inside the zone we claim to cover?

    The LLM tier's sanity gate. `openai/gpt-oss-120b` placed Sayedabad 12.6 km
    from its real location while reporting 0.78 confidence; a model's own
    confidence is not enough on its own.
    """
    return BBOX_S <= lat <= BBOX_N and BBOX_W <= lon <= BBOX_E
