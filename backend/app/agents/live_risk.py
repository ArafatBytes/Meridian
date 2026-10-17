"""
Live Risk Agent — today's news, on the map. DEMO_PLAN.md D04, source sprint S14.

    news sitemaps ─ list_recent ─▶ relevance filter ─▶ read ─▶ raw_documents
         ─▶ extraction (Gemini, NewsExtraction) ─▶ gazetteer ─▶ risk_flags (unconfirmed)
                                                     └─▶ extracted_incidents (every
                                                          incident, published or not)

Three rules carry the design, and each is checked by a test that does not need a
database or a model (`tests/invariants/test_live_flags_are_unconfirmed.py`):

1. **Every flag this agent writes is `unconfirmed` with one source.** Verification
   is D05's Rumour Guard and nothing else; the database refuses a single-source
   `confirmed` row anyway.
2. **No place is guessed.** Locations resolve through the gazetteer only
   (`allow_llm=False`): free, deterministic, and 93.3% on D03's eval with zero
   fabrications. A location the gazetteer does not know is recorded as
   `unresolved_location` and produces no pin.
3. **The pin's text comes from `framing.py`.** The model's own words go to the audit
   trail (`extracted_incidents.summary_en`) and never to a user.

Spending the free tier carefully
--------------------------------
Gemini's free tier is a few hundred requests a day for this feature's own project.
Two filters keep the agent inside it: headlines are matched against incident
vocabulary *before* an article is fetched, and at most `MAX_EXTRACTIONS_PER_RUN`
documents are read per run. Anything left over is in the retry queue
(`raw_documents.extracted_at is null`) for the next run.
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from datetime import UTC, datetime, timedelta
from itertools import zip_longest
from pathlib import Path
from typing import Any, Final
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.crime_guard import find_duplicate as find_crime_duplicate
from app.agents.crime_guard import merge_into as merge_crime_into
from app.agents.rumour_guard import find_duplicate, merge_into
from app.contracts.agents import AgentContext, AgentResult, AgentStatus, BaseAgent
from app.contracts.risk import GeoResolution, IncidentKind, MobilityImpact, RawDocument
from app.geo.agent import resolve_place
from app.ingestion import store
from app.ingestion.fetcher import Fetcher
from app.ingestion.sources import SOURCES, ArticleRef, Source, publisher_name
from app.llm.client import FEATURE_EXTRACT, LLMUnavailable, complete
from app.llm.models import NewsCrime, NewsExtraction, NewsIncident
from app.policy.attribution import (
    NEWS_CRIME_HALF_LIFE_HOURS,
    radius_for,
    to_attributed_statement,
)
from app.policy.attribution import severity_for as severity_for_crime
from app.policy.framing import to_mobility_statement
from app.policy.independence import is_vetted
from app.scoring.fixture import REPLAY_PATH, SEED_KEY_PREFIX
from app.scoring.kinds import defaults_for, severity_for

logger = logging.getLogger(__name__)

LIVE_KEY_PREFIX: Final = "live-"
"""Every flag this agent writes. The seeder's `seed-` rows are never touched by it."""

CRIME_KEY_PREFIX: Final = "crime-"
"""Every `news_crime_incidents` row this agent writes. A separate namespace from
`LIVE_KEY_PREFIX` so the two surfaces can never collide on an event key, even
though they live in different tables and could not collide anyway — the prefix is
there so a key read out of a log says which surface it belongs to."""

LOOKBACK: Final = timedelta(hours=12)
"""Older articles are skipped: a road accident's flag would be born already expired."""

MAX_READS_PER_SOURCE: Final = 8
MAX_EXTRACTIONS_PER_RUN: Final = 12
MAX_BODY_CHARS: Final = 4000
MIN_CONFIDENCE: Final = 0.5
PROMPT_VERSION: Final = "live_risk_v1"

# Sections that are never about movement inside Dhaka. Checked against the first
# URL path segment, which every publisher in `SOURCES` uses for the desk.
EXCLUDED_SECTIONS: Final = frozenset(
    {
        "international",
        "world",
        # Bangla Tribune's foreign desk. Same class of miss as `sport` below, found
        # the same way: a Houthi drone strike on Saudi Aramco passed the relevance
        # filter on আগুন and would have been fetched and extracted.
        "foreign",
        "sports",
        # Singular, because Dhaka Tribune's desk is /sport/ and the plural did not
        # match it. Found on the first live run with the paper wired in, 2026-10-14:
        # "US women rally to draw 2-2 with Spain" passed the relevance filter on
        # `rally` and would have cost a fetch and an extraction out of the free tier.
        "sport",
        "entertainment",
        "lifestyle",
        "tech",
        "technology",
        "religion",
        "opinion",
        "health",
        "education",
        "economy",
        "business",
        "video",
        "photo",
        # `country` and `countries` were here until 2026-10-15 and should not come
        # back. They read like "foreign" in English and are the opposite: in
        # Bangladeshi news the দেশ desk is the *domestic national* desk. Excluding
        # them cost real Dhaka-area incidents, measured on a labelled sample of
        # 2,622 headlines (`scripts/measure_relevance_filter.py`): of 6 missed
        # incidents, 3 were blocked here, and all 3 were the Tongi medicine factory
        # fire and the Chawkbazar fire -- both inside the pilot box.
        #
        # **The worse cost was corroboration, which nothing was measuring.** A flag
        # needs two or more *independent* publishers to reach `confirmed`. The Tongi
        # fire was filed under `capital` by some publishers and `country` by others,
        # so the pipeline saw one side of it and the event could never be confirmed
        # however many papers carried it. A section filter that correlates with the
        # publisher silently caps the corroboration ceiling.
    }
)
"""
A desk name, not a topic, so this list only works for publishers whose URLs carry
one. Three caveats worth knowing before adding to it:

* **Ittefaq has no desk segment at all.** Its article URLs are `/815086/<slug>`, so
  `ArticleRef.section` is the numeric id and nothing here can ever match it. Its
  articles are filtered by headline vocabulary and then by the gazetteer, which is
  the backstop for every publisher anyway. The cost is a few wasted extractions per
  run on foreign stories that happen to contain an incident word.
* **`country-news` and `whole-country` are deliberately absent.** They are where
  Jugantor and Samakal file domestic news, including events in Tongi, Gazipur and
  Narayanganj — adjacent to Dhaka and sometimes genuinely on a route out of it.
  Excluding them would be cheap and would throw away real events; the pilot-box
  check in `geo/gazetteer.py` is the honest filter for "is this near enough".
* Desk names vary by publisher and are not guessable. Every entry below was read
  off a live listing, never assumed.
"""

# Headline vocabulary for events that change how a road can be used. Substring
# matches on the Bangla headline, so inflected forms (আগুনে, সংঘর্ষে) are caught.
# This decides which articles are worth a fetch and a model request; the model
# decides what, if anything, they actually report.
INCIDENT_WORDS_BN: Final = (
    "আগুন",
    "অগ্নি",
    # Added 2026-10-15 from a measured miss. `নিয়ন্ত্রণে ফায়ার সার্ভিসের ১৯ ইউনিট
    # যোগ দিয়েছে সেনাবাহিনী` -- 19 fire service units, with the army joining --
    # names no fire. Follow-up copy on a large blaze often reports the *response*
    # rather than repeating the word আগুন, and a nineteen-unit deployment is a
    # road closure whatever the headline calls it.
    "ফায়ার সার্ভিস",
    "দমকল",
    "দুর্ঘটনা",
    "সংঘর্ষ",
    "চাপায়",
    "উল্টে",
    "নিহত",
    "আহত",
    "অবরোধ",
    "অবরুদ্ধ",
    "বিক্ষোভ",
    "মিছিল",
    "সমাবেশ",
    "মানববন্ধন",
    "শোভাযাত্রা",
    "ধর্মঘট",
    "হরতাল",
    "ধাওয়া",
    "জলাবদ্ধতা",
    "জলজট",
    "পানিবন্দি",
    "বৃষ্টি",
    "যানজট",
    "সড়ক",
    "রাস্তা",
    "যান চলাচল",
    "খোঁড়াখুঁড়ি",
    "নির্মাণকাজ",
    "বিদ্যুৎ",
    "গ্যাস",
    "বিস্ফোরণ",
    "ভবন ধস",
)

INCIDENT_WORDS_EN: Final = (
    # Inflections are written out rather than produced by a suffix wildcard. See
    # the note below: the wildcard is what breaks this list, not what completes it.
    "fire",
    "fires",
    "blaze",
    "accident",
    "accidents",
    "crash",
    "crashes",
    "crashed",
    "collision",
    "collisions",
    "killed",
    "injured",
    "run over",
    "overturn",
    "overturns",
    "overturned",
    "blockade",
    "blockades",
    "block",
    "blocks",
    "blocked",
    "blocking",
    "protest",
    "protests",
    "protesters",
    "demonstration",
    "demonstrations",
    "rally",
    "rallies",
    "procession",
    "processions",
    "march",
    "marches",
    "strike",
    "strikes",
    "hartal",
    "clash",
    "clashes",
    "waterlogging",
    "waterlogged",
    "flood",
    "floods",
    "flooded",
    "flooding",
    "rain",
    "rains",
    "traffic",
    "gridlock",
    "jam",
    "jams",
    "congestion",
    "road",
    "roads",
    "street",
    "streets",
    "highway",
    "closure",
    "closures",
    "closed",
    "digging",
    "construction",
    "repair",
    "repairs",
    "electricity",
    "power cut",
    "gas line",
    "explosion",
    "explosions",
    "blast",
    "blasts",
    "collapse",
    "collapsed",
)
"""
The English half, for Dhaka Tribune (added 2026-10-14).

**Matched between word boundaries**, which is the one place the two languages need
different machinery rather than a different list. Bangla inflects by suffix — আগুন
is a prefix of আগুনে — so a substring test is what catches the inflected form, and
it is safe because a Bangla compound rarely contains an unrelated word by accident.
English is the opposite: a substring test for `fire` matches *fired*, *firearm* and
*misfired*, and `jam` matches *Jamuna* and *Jamalpur*, two Bangladeshi proper nouns
that appear in the news constantly.

**The first version of this used `\\b(?:...)\\w*`** — a leading boundary plus a
suffix wildcard, to get *blocked* and *blockade* from one stem. That is wrong in a
way worth recording, because it looks careful: `\\bjam\\w*` matches *Jamuna*
perfectly well, so the wildcard hands back exactly the false positives the boundary
was there to prevent. It was caught by the test that had been written for that
case. Every form is therefore spelled out, and the pattern closes with `\\b` too.

The list is as broad as the Bangla one and for the same reason: `road`, `street`
and `traffic` admit a lot, but the headline filter's job is to be cheap and
generous, and the model decides whether an article actually reports anything. A
tight filter here fails silently, and a missed road closure is not recoverable from
the logs.
"""


def boundary_pattern(words: tuple[str, ...]) -> re.Pattern[str]:
    """
    A case-insensitive alternation anchored by a word boundary at **both** ends.

    Longest-first so that `power cut` is tried before `power`, which matters because
    Python's alternation is first-match, not longest-match.
    """
    ordered = sorted(words, key=len, reverse=True)
    return re.compile(
        r"\b(?:" + "|".join(re.escape(word) for word in ordered) + r")\b",
        re.IGNORECASE,
    )


_EN_PATTERN: Final = boundary_pattern(INCIDENT_WORDS_EN)

# Words that wrap a place name in news copy without being part of it. D03's
# gazetteer resolves "মিরপুর ১০ গোলচত্বর" and "কড়াইল" but not
# "রাজধানীর মিরপুর ১০ নম্বর গোলচত্বর এলাকায়" or "কড়াইল বস্তি" (measured
# 2026-10-08). Removing these is deterministic and adds no information: the result
# is still a place the article named, never a different one.
PLACE_FILLER: Final = frozenset(
    {
        "রাজধানীর",
        "রাজধানী",
        "ঢাকার",
        "মহানগরীর",
        "এলাকায়",
        "এলাকার",
        "এলাকা",
        "নম্বর",
        "নং",
        "সংলগ্ন",
        "সামনে",
        "কাছে",
        "পাশে",
        "বস্তি",
        "বস্তিতে",
        "থানা",
        "থানার",
        "থানায়",
        "মহল্লা",
        "মহল্লায়",
    }
)

PLACE_FILLER_EN: Final = frozenset(
    {
        # The English counterpart, compared casefolded. Same rule as above: these
        # wrap a place name in news copy without being part of it, and removing
        # them can only ever make a match possible, never make one up.
        "the",
        "in",
        "at",
        "of",
        "near",
        "beside",
        "front",
        "capital",
        "capital's",
        "city",
        "city's",
        "dhaka's",
        "area",
        "areas",
        "no",
        "no.",
        "number",
        "police",
        "station",
        "thana",
    }
)
"""
Deliberately **no digits and no bare numerals.** D03's number-identity rule is what
stops `গুলশান ৯৭ গোলচত্বর` being rounded up to Gulshan, and the same protection has
to hold for `Gulshan 97 circle`. Adding "one", "two" or a digit pattern here would
quietly delete the part of a name that distinguishes Mirpur 10 from Mirpur 1.
"""

# Generic place-*type* nouns that trail a specific name in Bangla news copy, with
# the case suffixes the copy actually uses. Stripped from the END only, because
# Bangla puts the specific name first: মহাখালী বাস টার্মিনালে is Mohakhali + "bus
# terminal", so the head is the identity and the tail is the category.
#
# Why this exists: the Live Risk Agent asks the model for "the most specific place
# name", and on 2026-10-08 it correctly answered মহাখালী বাস টার্মিনালে for a real
# bus fire. The gazetteer resolves মহাখালী at confidence 1.00 and that phrase at
# nothing, so the most specific answer was the least resolvable one and a genuine
# Dhaka road event was discarded as unresolved_location. Filler removal did not
# help: বাস and টার্মিনালে are part of the place's name, not wrapping around it.
#
# This stays on the right side of "discarded, never guessed" for the same reason
# PLACE_FILLER does — the result is a prefix of what the article said, never a
# different name. The protection against it becoming a *vaguer* name than the
# article supports is D03's number-identity rule: গুলশান ৯৭ গোলচত্বর reduces to
# গুলশান ৯৭, which no entry matches, so a fabricated sub-location is still
# refused rather than being rounded up to Gulshan. Do not add bare numbers here.
PLACE_GENERIC_TAIL: Final = (
    # multi-word first; matching is longest-first so these strip as a unit
    "বাস টার্মিনালে",
    "বাস টার্মিনাল",
    "বাস স্ট্যান্ডে",
    "বাস স্ট্যান্ড",
    "বাসস্ট্যান্ডে",
    "বাসস্ট্যান্ড",
    "রেল স্টেশনে",
    "রেল স্টেশন",
    # single tokens
    "টার্মিনালে",
    "টার্মিনাল",
    "স্ট্যান্ডে",
    "স্ট্যান্ড",
    "স্টেশনে",
    "স্টেশন",
    "গোলচত্বরে",
    "গোলচত্বর",
    "চত্বরে",
    "চত্বর",
    "চৌরাস্তায়",
    "চৌরাস্তা",
    "মোড়ে",
    "মোড়",
    "ক্রসিংয়ে",
    "ক্রসিং",
    "রেলগেটে",
    "রেলগেট",
    "ফ্লাইওভারে",
    "ফ্লাইওভার",
    "ওভারব্রিজে",
    "ওভারব্রিজ",
    "ব্রিজে",
    "ব্রিজ",
    "সেতুতে",
    "সেতু",
    "বাজারে",
    "বাজার",
    "সড়কে",
    "সড়ক",
    "রোডে",
    "রোড",
    "রাস্তায়",
    "রাস্তা",
)

PLACE_GENERIC_TAIL_EN: Final = (
    # The English counterpart, matched casefolded and stripped from the END only —
    # English puts the specific name first too ("Mohakhali bus terminal"), so the
    # head is the identity and the tail is the category.
    #
    # Multi-word entries first; `_without_generic_tail` sorts by length anyway, so
    # "bus terminal" strips as a unit before "terminal" can take half of it.
    "bus terminal",
    "bus stand",
    "bus stop",
    "railway station",
    "rail station",
    "train station",
    "launch terminal",
    "truck stand",
    "fish market",
    "kacha bazar",
    "flyover",
    "overpass",
    "overbridge",
    "footbridge",
    "underpass",
    "intersection",
    "crossing",
    "roundabout",
    "circle",
    "junction",
    "terminal",
    "station",
    "square",
    "market",
    "bazar",
    "bazaar",
    "mor",
    "more",
    "chowrasta",
    "bridge",
    "road",
    "street",
    "avenue",
    "lane",
    "highway",
)

SYSTEM_PROMPT: Final = (
    "You read Bangla and English news articles for a navigation app in Dhaka, "
    "Bangladesh. "
    "List only events that affect movement on roads inside Dhaka city today: road "
    "accidents, fires, clashes, road blockades, processions or rallies, waterlogging, "
    "road construction, utility works. "
    "For each, give location_text: the most specific place name, copied from the "
    "article in its own script, without words like রাজধানীর, এলাকায় or নম্বর "
    "(write মিরপুর ১০ গোলচত্বর, not রাজধানীর মিরপুর ১০ নম্বর গোলচত্বর এলাকায়). "
    "In an English article, copy the romanised name the same way: write "
    "Mirpur 10 circle, not the capital's Mirpur 10 circle area. Keep any number "
    "that is part of the name — Mirpur 10 and Mirpur 1 are different places. "
    # Permission, not preference. "Most specific place name" above already does
    # the ordering; this only says a road qualifies. It was added with S31's road
    # layer, because until the gazetteer held roads a model that correctly copied
    # "সাতমসজিদ রোড" produced a guaranteed discard, and the cheapest-looking fix
    # would have been to teach it to answer "ধানমন্ডি" instead — generalising the
    # article's own words, which is the opposite of what this prompt is for.
    "A road name is a place name: write সাতমসজিদ রোড or Satmasjid Road when that "
    "is the most specific place the article names. "
    "mobility_impact is road_blocked, heavy_crowd, delay_likely, lane_closed, "
    "impassable, or none if traffic is not affected. "
    "For `incidents`, ignore events outside Dhaka city, events more than a day old, "
    "court cases, arrests, statements and announcements. "
    "\n\n"
    "Separately, in `crimes`, list crimes the article reports as having happened at "
    "a named place in or near Dhaka: theft, assault, harassment, vandalism, "
    "burglary, robbery, fraud, or other. "
    "An arrest report or a charge-sheet report counts if it says where the crime "
    "itself happened; the place you give must be where the CRIME happened, never "
    "the police station, the court or the hospital. "
    # B11a, 2026-10-15. Added with the DMP News source, and specific to how police
    # copy is written rather than to how newspapers write.
    #
    # "never the police station" above is already the rule, and it is not enough
    # here, because **a Dhaka thana is also a neighbourhood.** যাত্রাবাড়ী is a
    # police station AND a place the gazetteer resolves at 1.2 km. So
    # `যাত্রাবাড়ী থানার বিশেষ অভিযানে গ্রেফতার ১৭` -- seventeen arrests across a
    # thana's whole area in one sweep -- would not self-discard the way
    # `ডিএমপির অভিযানে গ্রেফতার ৫৩০` does. "DMP" resolves to nothing and falls out
    # on its own; "Jatrabari" resolves, and a city-wide round-up would be pinned
    # as though a crime had happened at a spot.
    #
    # The owner's decision on 15 Oct: only items naming a located incident. An
    # Uttara mugging with the auto-rickshaw recovered qualifies; a thana-wide
    # sweep does not.
    "A police unit is not a place, even when it is named after one: a drive by "
    "যাত্রাবাড়ী থানা or Uttara Police Station tells you which officers acted, not "
    "where anything happened. If an article reports a round-up, a drive or a "
    "24-hour total across an area rather than one crime at one place, return "
    "nothing for it. "
    "Give the same kind of specific place name as above. "
    "summary_en is one short factual English sentence for an internal audit log. "
    "Do not name any person — not a suspect, a victim, a witness or an officer — "
    "and do not name any political party, religious group or ethnic group. "
    "Do not say an area is dangerous or unsafe; report only what happened and where. "
    "One event is one entry: an article about a robbery and the arrest that "
    "followed it is a single crime, not two. "
    "\n\n"
    "Most articles report nothing for either list: then return empty lists. Never "
    "invent a place the article does not name."
)


# ---------------------------------------------------------------------------
# Pure decisions — tested without a database or a model
# ---------------------------------------------------------------------------


CRIME_WORDS_BN: Final = (
    "ছিনতাই",  # snatching / mugging
    "ডাকাতি",  # dacoity, armed robbery
    "ডাকাত",
    "চুরি",  # theft
    "চোর",
    "ছুরিকাঘাত",  # stabbing
    "কুপিয়ে",  # hacked
    "খুন",  # murder
    "হত্যা",  # killing
    "লাশ",  # body
    "ধর্ষণ",  # rape
    "শ্লীলতাহানি",  # molestation
    "যৌন হয়রানি",  # sexual harassment
    "উত্ত্যক্ত",  # eve-teasing / harassment
    "মারধর",  # beating
    "হামলা",  # attack
    "অপহরণ",  # abduction
    "মুক্তিপণ",  # ransom
    "চাঁদাবাজি",  # extortion
    "ভাঙচুর",  # vandalism
    "লুট",  # looting
    "প্রতারণা",  # fraud
    "জালিয়াতি",  # forgery
    "গ্রেপ্তার",  # arrested
    "গ্রেফতার",
    "আটক",  # detained
    "ছিনিয়ে",  # snatched away
)

CRIME_WORDS_EN: Final = (
    "robbery",
    "robbed",
    "robbers",
    "mugging",
    "mugged",
    "snatching",
    "snatched",
    "theft",
    "stolen",
    "burglary",
    "burgled",
    "stabbing",
    "stabbed",
    "murder",
    "murdered",
    "killed",
    "body recovered",
    "rape",
    "raped",
    "molested",
    "molestation",
    "harassment",
    "harassed",
    "assault",
    "assaulted",
    "beaten",
    "attacked",
    "abduction",
    "abducted",
    "kidnapped",
    "ransom",
    "extortion",
    "vandalism",
    "vandalised",
    "looted",
    "fraud",
    "forgery",
    "arrested",
    "detained",
    "mugger",
)
"""
What makes a headline worth fetching for the **crime** half of the extraction.

This is new cost, and it should be understood as such: before this, a crime story
with no mobility word in its headline was never fetched at all, so publishing
news-sourced crime necessarily means reading more articles. The cap that protects
the free tier is still `MAX_EXTRACTIONS_PER_RUN`, and one model call now returns
both vocabularies — see `NewsExtraction` — so the extra cost is in fetching, not in
extraction.

`arrested` and `detained` are deliberately included even though D04's mobility
prompt explicitly discards "court cases, arrests, statements". That instruction is
right for the mobility surface and wrong here: an arrest report is usually the
first *confirmed* account of the underlying crime, and it is the one that names the
place. The extraction prompt is what decides whether an article describes a crime
at a locatable place in Dhaka; this list only decides whether it is worth reading.
"""

_CRIME_PATTERN_EN: Final = boundary_pattern(CRIME_WORDS_EN)


# ---------------------------------------------------------------------------
# Bangla has two spellings of the same letter, and one of them never matched
# ---------------------------------------------------------------------------
# Found 2026-10-15 while measuring the filter, and it had been losing real Dhaka
# road deaths silently the whole time.
#
# ড়, ঢ় and য় each exist twice in Unicode: as one precomposed codepoint (U+09DC,
# U+09DD, U+09DF) and as a base letter plus nukta (U+09A1/U+09A2/U+09AF followed
# by U+09BC). They render identically. They are not equal strings.
#
# **Both forms are live in this data.** 1,568 of 2,622 collected headlines used a
# precomposed form, while 17 keywords in the lists below were written decomposed
# -- including `চাপায়` (run over), `কুপিয়ে` (hacked), `ছিনিয়ে` (snatched),
# `ধাওয়া` (chase). A `word in title` test between the two forms is always False,
# so those keywords matched only the publishers that happened to agree with them.
#
# Measured cost on one sample: 17 headlines, among them
# **`বারিধারায় গাড়িচাপায় নির্মাণশ্রমিকের মৃত্যু`** -- a construction worker
# killed by a car in Baridhara, which is in Dhaka -- plus two truck fatalities
# and a Dhaka-Sylhet highway death. Invisible. Not discarded with a reason, not
# logged: never fetched, because the headline "did not name an incident".
#
# **NFC is the right target even though it looks like the wrong one.** Normally
# NFC composes, but all three of these letters are on Unicode's composition
# exclusion list, so NFC *decomposes* U+09DF to U+09AF U+09BC. Either canonical
# form would work as long as it is applied to both sides; NFC is chosen because
# it is the default everywhere else and needs no explanation at the call site.
def _nfc(text: str) -> str:
    """Canonical form, so two spellings of ড়/ঢ়/য় compare equal."""
    return unicodedata.normalize("NFC", text)


_INCIDENT_WORDS_BN_NFC: Final = frozenset(_nfc(word) for word in INCIDENT_WORDS_BN)
_CRIME_WORDS_BN_NFC: Final = frozenset(_nfc(word) for word in CRIME_WORDS_BN)


def names_a_crime(title: str) -> bool:
    """Does this headline name a crime at a place? Both scripts, as above."""
    normalised = _nfc(title)
    return any(word in normalised for word in _CRIME_WORDS_BN_NFC) or bool(
        _CRIME_PATTERN_EN.search(title)
    )


# ---------------------------------------------------------------------------
# The geographic gate — D04, 2026-10-15
# ---------------------------------------------------------------------------
# Measured cause of nearly every false positive. On a labelled sample of 2,622
# headlines the filter's precision was **0.31**: of 167 articles it passed, 115
# were not Dhaka incidents. They were not borderline either -- a drone strike in
# Ukraine, a Houthi attack on Saudi Aramco, a roof collapse in Rangpur, a road
# blockade in Sajek, Rahul Gandhi in Delhi. The filter asked "does this headline
# name an incident?" and never "is it here?", so every violent event on earth
# matched.
#
# **Why a negative list and not a positive one.** Requiring a Dhaka place name
# would be the obvious design and would be wrong: Dhaka copy routinely names the
# locality and not the city -- `ফুটপাতে মারধর`, `বাড্ডায় গৃহবধূর মৃত্যু`,
# `পল্লবীতে ইজিবাইক চালক হত্যা`. A positive requirement would reject those, and
# a miss is the expensive error here because the article is never fetched and so
# never leaves a trace. Naming the places it is *not* costs recall only when a
# headline mentions somewhere else -- and then `DHAKA_MARKERS` overrides.
#
# **This list is deliberately conservative.** Gazipur, Tongi, Savar and
# Keraniganj are NOT here: Tongi sits inside the pilot box at ~23.89 N, and the
# others are close enough that the gazetteer should make the call rather than a
# headline keyword. The entries are places far enough away that no incident there
# can affect a journey across Dhaka.
NOT_DHAKA: Final = frozenset(
    {
        # Bangladesh, outside the pilot box.
        "চট্টগ্রাম", "সিলেট", "রাজশাহী", "খুলনা", "বরিশাল", "রংপুর", "ময়মনসিংহ",
        "কুমিল্লা", "নোয়াখালী", "কক্সবাজার", "যশোর", "কুষ্টিয়া", "দিনাজপুর",
        "বগুড়া", "পাবনা", "টাঙ্গাইল", "ফরিদপুর", "মাদারীপুর", "গোপালগঞ্জ",
        "সাতক্ষীরা", "নেত্রকোনা", "কুড়িগ্রাম", "নীলফামারী", "চাঁদপুর",
        "ব্রাহ্মণবাড়িয়া", "সাজেক", "খাগড়াছড়ি", "বান্দরবান", "রাঙামাটি",
        "সুন্দরবন", "মুন্সিগঞ্জ", "নারায়ণগঞ্জ", "ঠাকুরগাঁও", "সিরাজগঞ্জ",
        "মীরসরাই", "আড়াইহাজার", "চুয়েট", "পায়রা",
        "Chattogram", "Chittagong", "Sylhet", "Rajshahi", "Khulna", "Barisal",
        "Rangpur", "Mymensingh", "Cumilla", "Comilla", "Noakhali", "Jashore",
        "Kushtia", "Bogura", "Tangail", "Faridpur", "Satkhira", "Chandpur",
        "Brahmanbaria", "Sajek", "Khagrachhari", "Bandarban", "Narayanganj",
        "Munshiganj", "Cuet", "Sirajganj",
        # Abroad.
        "রাশিয়া", "ইউক্রেন", "সৌদি", "ভারত", "পাকিস্তান", "ইরান", "ইরাক",
        "ইসরায়েল", "যুক্তরাষ্ট্র", "আমেরিকা", "যুক্তরাজ্য", "ফ্রান্স", "জাপান",
        "চীন", "ইয়েমেন", "হুথি", "হুতি", "আবুধাবি", "জর্ডান", "দিল্লি",
        "করাচি", "পানামা", "আজারবাইজান", "তাইওয়ান", "গাজা", "ইউরোপ", "ওমান",
        "নেদারল্যান্ডস", "কানাডা", "তুর্কি", "স্পেন", "মস্কো", "নিউ‌ দিল্লি",
        "Russia", "Ukraine", "Saudi", "India", "Pakistan", "Iran", "Iraq",
        "Israel", "Yemen", "Houthi", "Jordan", "Delhi", "Karachi", "Panama",
        "Taiwan", "Gaza", "Oman", "Netherlands", "Canada", "Spain", "Moscow",
        "France", "Japan", "China", "Europe",
    }
)
"""Places far enough from Dhaka that an incident there cannot affect a journey in it."""

# Overrides `NOT_DHAKA`. A headline naming both is about here: `ঢাকা ময়মনসিংহ
# মহাসড়কে দীর্ঘ যানজট` is a jam on the Dhaka corridor, not news from Mymensingh.
DHAKA_MARKERS: Final = frozenset(
    {
        "ঢাকা", "ঢাকার", "ঢাকায়", "রাজধানী", "রাজধানীর", "রাজধানীতে",
        "ধানমন্ডি", "ধানমণ্ডি", "গুলশান", "মিরপুর", "উত্তরা", "মতিঝিল",
        "যাত্রাবাড়ী", "বাড্ডা", "পল্লবী", "তেজগাঁও", "রামপুরা", "মোহাম্মদপুর",
        "চকবাজার", "কারওয়ান", "ফার্মগেট", "শাহবাগ", "টঙ্গী", "মহাখালী",
        "বিমানবন্দর", "গাবতলী", "সায়েদাবাদ", "কমলাপুর", "রূপনগর", "তুরাগ",
        "কেরানীগঞ্জ", "ডেমরা", "খিলগাঁও", "বনানী", "কল্যাণপুর", "শ্যামলী",
        "পুরান ঢাকা", "লালবাগ", "সূত্রাপুর", "ওয়ারী", "গেন্ডারিয়া",
        "Dhaka", "capital", "Dhanmondi", "Gulshan", "Mirpur", "Uttara",
        "Motijheel", "Jatrabari", "Badda", "Pallabi", "Tejgaon", "Rampura",
        "Mohammadpur", "Chawkbazar", "Karwan", "Farmgate", "Shahbagh", "Tongi",
        "Mohakhali", "Banani", "Keraniganj", "Demra",
    }
)


_NOT_DHAKA_NFC: Final = frozenset(_nfc(place).casefold() for place in NOT_DHAKA) | frozenset(
    _nfc(place) for place in NOT_DHAKA
)
_DHAKA_MARKERS_NFC: Final = frozenset(
    _nfc(marker).casefold() for marker in DHAKA_MARKERS
) | frozenset(_nfc(marker) for marker in DHAKA_MARKERS)


def names_elsewhere(title: str) -> bool:
    """
    Is this headline about somewhere an incident cannot affect a Dhaka journey?

    A Dhaka marker wins: a headline carrying both is read as being about here.
    Bangla is matched as written (no case) and English casefolded, the same split
    `names_an_incident` uses and for the same reason -- Dhaka copy mixes scripts.
    """
    # NFC on both sides, for the reason in `_nfc`'s comment. This gate is how the
    # bug was found: `নোয়াখালীতে` stores য় precomposed, the list below spells it
    # decomposed, and a Noakhali arrest sailed through a filter that names
    # Noakhali explicitly.
    normalised = _nfc(title)
    folded = normalised.casefold()
    if any(marker in normalised or marker in folded for marker in _DHAKA_MARKERS_NFC):
        return False
    return any(place in normalised or place in folded for place in _NOT_DHAKA_NFC)


def names_an_incident(title: str) -> bool:
    """
    Does this headline name something that could change how a road can be used?

    Both vocabularies are tried against every headline regardless of the
    publisher's declared language, and that is deliberate rather than lazy: Dhaka
    English copy routinely keeps Bangla terms (*hartal*, *gherao*), Bangla copy
    carries English ones, and a headline is too short to language-detect reliably.
    Trying both costs one regex and removes a whole class of silent miss.
    """
    return any(word in _nfc(title) for word in _INCIDENT_WORDS_BN_NFC) or bool(
        _EN_PATTERN.search(title)
    )


def interleave(batches: list[list[RawDocument]]) -> list[RawDocument]:
    """
    One document from each publisher in turn, then the next from each, and so on.

    **This is a corroboration requirement, not a fairness nicety**, and the
    distinction matters enough to spell out. The extraction queue is cut to
    `MAX_EXTRACTIONS_PER_RUN` because that is the free tier. Concatenating the
    publishers in order and then truncating means the first publisher in `SOURCES`
    fills the whole budget on any busy day: with nine sources and up to
    `MAX_READS_PER_SOURCE` documents each, the cut falls inside the first or
    second publisher's batch every single run.

    What that costs is not a few late articles. It is **every confirmation**. A
    flag reaches `confirmed` only when two or more independent publishers are seen
    to describe one event, which can only happen if both accounts are extracted —
    and under concatenation the second publisher's account of this morning's fire
    is never in the same budget as the first's. The surface would stay entirely
    `unconfirmed` no matter how many outlets were added, and the obvious diagnosis
    would be "Rumour Guard is too strict", which would be wrong.

    Round-robin spreads one run's budget across the publishers, so the articles
    that corroborate each other arrive in the same pass.

    Order within each batch is preserved, and a publisher that returned nothing
    simply drops out. Nothing is lost when the cut falls mid-cycle either: what is
    not extracted this run stays in `raw_documents` with `extracted_at` null, which
    is the retry queue the next run drains.
    """
    queued: list[RawDocument] = []
    for row in zip_longest(*batches):
        queued.extend(doc for doc in row if doc is not None)
    return queued


def is_relevant(ref: ArticleRef, now: datetime) -> bool:
    """
    Worth fetching? Recent, not from an excluded desk, and the headline names
    either a mobility incident or a crime.

    One filter for both halves of the extraction, because one fetch feeds both. An
    article that mentions a road blockade and a stabbing is read once.
    """
    if ref.section in EXCLUDED_SECTIONS:
        return False
    if ref.published_at is not None and ref.published_at < now - LOOKBACK:
        return False
    if names_elsewhere(ref.title):
        return False
    return names_an_incident(ref.title) or names_a_crime(ref.title)


def _without_generic_tail(text: str) -> str:
    """
    Drop trailing generic place-type nouns, longest match first, repeatedly.

    `মহাখালী বাস টার্মিনালে` -> `মহাখালী`. Returns `text` unchanged when nothing
    matches, and never returns an empty string — a bare category word like
    `বাজারে` with no name in front of it is left alone to be refused, because on
    its own it identifies nowhere.
    """
    current = text
    tails = sorted(
        [(tail, False) for tail in PLACE_GENERIC_TAIL]
        + [(tail, True) for tail in PLACE_GENERIC_TAIL_EN],
        key=lambda pair: len(pair[0]),
        reverse=True,
    )
    while True:
        for tail, fold in tails:
            # Bangla has no case, so it is compared as written; English is compared
            # casefolded because copy writes "Mirpur Road" and "Mirpur road" alike.
            subject = current.casefold() if fold else current
            candidate = tail.casefold() if fold else tail
            if subject == candidate:
                return current  # nothing but a category; let it fail to resolve
            if subject.endswith(" " + candidate):
                current = current[: len(current) - len(candidate)].strip()
                break
        else:
            return current


def place_candidates(location_text: str) -> list[str]:
    """
    As written, then without filler, then without a trailing place-type noun.
    Never a shorter *different* name.

    Every candidate is built by **removing** words — those in `PLACE_FILLER`, then
    those in `PLACE_GENERIC_TAIL` from the end — so each one is a sub-phrase of
    what the article said. That is what keeps this on the right side of
    "discarded, never guessed": it can make a match possible, it cannot make one
    up. Order matters: the most specific form is tried first, so a place the
    gazetteer knows in full (`যাত্রাবাড়ী চৌরাস্তা`, `কারওয়ান বাজারে`) resolves to
    itself and never to its own prefix.
    """
    original = " ".join(location_text.split())

    def reduce(text: str) -> tuple[str, str]:
        cleaned = " ".join(
            w
            for w in text.replace("-", " ").split()
            if w not in PLACE_FILLER and w.casefold() not in PLACE_FILLER_EN
        )
        return cleaned, _without_generic_tail(cleaned)

    cleaned, trimmed = reduce(original)
    candidates = [original, cleaned, trimmed]

    # Comma-separated qualifiers, most specific first.
    #
    # News copy names a place by narrowing: "Road No 1 in Lake Circus, Kalabagan",
    # "সাতমসজিদ রোড, ধানমন্ডি". The reductions above only strip wrapping words and
    # trailing category nouns, so neither form resolves even when one of the parts
    # is an entry the gazetteer knows perfectly well — which is exactly what
    # happened on the first live crime extraction, 2026-10-14: `Kalabagan` resolves
    # on its own and `Road No 1 in Lake Circus, Kalabagan` did not, so a located
    # report was discarded for want of a comma.
    #
    # Each segment is a contiguous sub-phrase of what the article wrote, so this
    # stays on the right side of "discarded, never guessed" for the same reason
    # the other two reductions do: it can make a match possible, it cannot invent
    # one. The ordering is what keeps it honest — the whole phrase and its
    # reductions are tried first, so a place the gazetteer knows in full always
    # wins over its own less specific qualifier.
    if "," in original:
        for segment in (part.strip() for part in original.split(",")):
            if not segment:
                continue
            segment_cleaned, segment_trimmed = reduce(segment)
            candidates += [segment, segment_cleaned, segment_trimmed]

    return [c for c in dict.fromkeys(candidates) if c]


async def resolve_news_place(location_text: str) -> GeoResolution:
    """The first candidate the gazetteer knows, or the unresolved answer. No LLM tier."""
    resolution: GeoResolution | None = None
    for candidate in place_candidates(location_text):
        resolution = await resolve_place(candidate, allow_llm=False)
        if resolution.method != "unresolved":
            return resolution
    return resolution or await resolve_place(location_text, allow_llm=False)


def discard_reason(incident: NewsIncident, place: GeoResolution) -> str | None:
    """Why an extracted incident must not become a flag, or None if it may."""
    if incident.confidence < MIN_CONFIDENCE:
        return "low_confidence"
    if place.method == "unresolved":
        return "unresolved_location"
    if incident.mobility_impact == MobilityImpact.NONE:
        return "rejected"  # real, located, and irrelevant to getting through it
    return None


def flag_row(
    *, doc: RawDocument, index: int, incident: NewsIncident, place: GeoResolution
) -> dict[str, Any]:
    """
    One incident as an insert-shaped `risk_flags` row.

    Same shape as `app/scoring/fixture.py`'s rows. `expires_at` is absent because the
    `source_count` is 1 whatever the input, because this agent has exactly one
    source per flag. `expires_at` is absent because the database trigger derives it.

    **`status` is decided by the publisher**, which changed on 2026-10-16. It was
    unconditionally `unconfirmed` -- one article is one source, and `confirmed`
    then meant two independent publishers. It now means "a vetted newsroom or
    institution published this, or two independent publishers agreed", and every
    publisher this agent reads is vetted by construction: `SOURCES` is a
    hand-picked list. The check is still made against
    `policy.independence.VETTED_PUBLISHERS` rather than assumed, because the
    assumption is exactly what would be wrong the day something un-vetted is read.
    """
    kind = IncidentKind(incident.kind)
    defaults = defaults_for(kind)
    observed_at = doc.published_at or doc.fetched_at
    return {
        "event_key": f"{LIVE_KEY_PREFIX}{doc.doc_id[:16]}-{index}",
        "kind": kind.value,
        "status": "confirmed" if is_vetted([doc.source_id]) else "unconfirmed",
        "lat": place.lat,
        "lon": place.lon,
        # The wider of the event's reach and our uncertainty about where it is: a
        # fire resolved only to "Mirpur" is claimed over Mirpur, not over 400 m of it.
        "radius_m": min(20_000, max(defaults.radius_m, place.radius_m)),
        "severity_0": severity_for(kind, incident.severity_hint),
        "half_life_hours": defaults.half_life_hours,
        "observed_at": observed_at,
        "valid_from": None,
        "valid_to": None,
        "source_count": 1,
        "sources": [
            {
                "source_id": doc.source_id,
                "url": doc.url,
                "published_at": observed_at.isoformat(),
                "title": doc.title,
                "snippet": None,
            }
        ],
        "mobility_statement": to_mobility_statement(
            kind=kind, impact=incident.mobility_impact, place=place.resolved_name
        ),
    }


def crime_discard_reason(crime: NewsCrime, place: GeoResolution) -> str | None:
    """
    Why an extracted crime must not be published, or None if it may.

    The mobility version has a third test — `mobility_impact == NONE` — which has
    no analogue here. A crime with no effect on traffic is still a crime that was
    reported, and this surface is not making a traffic claim about it.
    """
    if crime.confidence < MIN_CONFIDENCE:
        return "low_confidence"
    if place.method == "unresolved":
        return "unresolved_location"
    return None


def crime_row(
    *, doc: RawDocument, index: int, crime: NewsCrime, place: GeoResolution, now: datetime
) -> dict[str, Any]:
    """
    One crime as an insert-shaped `news_crime_incidents` row.

    `expires_at` is absent because the database trigger derives it, and
    `source_count` is 1 whatever the input, because this agent publishes exactly
    one publisher's account at a time — corroboration happens in `crime_guard`,
    not here.
    """
    observed_at = doc.published_at or doc.fetched_at
    return {
        "event_key": f"{CRIME_KEY_PREFIX}{doc.doc_id[:16]}-{index}",
        "category": crime.category,
        "status": "published",
        "lat": place.lat,
        "lon": place.lon,
        # The wider of the category's own reach and our uncertainty about where it
        # is, capped at the column's 1 km. Same rule as `flag_row`, a tighter cap:
        # a street crime resolved only to a whole thana is a claim about a corner we
        # cannot locate, and widening it to cover the thana is how one incident
        # becomes an area label.
        "radius_m": min(1_000, max(radius_for(crime.category), place.radius_m)),
        "severity_0": severity_for_crime(crime.category),
        "half_life_hours": NEWS_CRIME_HALF_LIFE_HOURS,
        "observed_at": observed_at,
        "source_count": 1,
        "sources": [
            {
                "source_id": doc.source_id,
                "url": doc.url,
                "published_at": observed_at.isoformat(),
                "title": doc.title,
                "snippet": None,
            }
        ],
        "statement": to_attributed_statement(
            category=crime.category,
            publishers=[publisher_name(doc.source_id)],
            observed_at=observed_at,
            now=now,
        ),
    }


def user_prompt(doc: RawDocument) -> str:
    published = doc.published_at.isoformat() if doc.published_at else "unknown"
    return f"Headline: {doc.title}\nPublished: {published}\n\n{doc.body[:MAX_BODY_CHARS]}"


# ---------------------------------------------------------------------------
# Writes
# ---------------------------------------------------------------------------

_INSERT_FLAG: Final = text(
    """
    insert into public.risk_flags
        (event_key, kind, status, location, radius_m, severity_0, half_life_hours,
         observed_at, valid_from, valid_to, source_count, sources, mobility_statement)
    values
        (:event_key, :kind, :status,
         extensions.ST_SetSRID(extensions.ST_MakePoint(:lon, :lat), 4326)::extensions.geography,
         :radius_m, :severity_0, :half_life_hours, :observed_at, :valid_from, :valid_to,
         :source_count, cast(:sources as jsonb), :mobility_statement)
    returning flag_id
    """
)

_INSERT_CRIME: Final = text(
    """
    insert into public.news_crime_incidents
        (event_key, category, status, location, radius_m, severity_0, half_life_hours,
         observed_at, source_count, sources, statement)
    values
        (:event_key, :category, :status,
         extensions.ST_SetSRID(extensions.ST_MakePoint(:lon, :lat), 4326)::extensions.geography,
         :radius_m, :severity_0, :half_life_hours, :observed_at,
         :source_count, cast(:sources as jsonb), :statement)
    returning incident_id
    """
)

_INSERT_EXTRACTED_CRIME: Final = text(
    """
    insert into public.extracted_crimes
        (doc_id, category, summary_en, location_text, extraction_confidence,
         source, news_crime_id, discarded_reason)
    values
        (:doc_id, :category, :summary_en, :location_text, :confidence,
         cast(:source as jsonb), :news_crime_id, :discarded_reason)
    """
)

_SOURCES_OF: Final = text(
    "select sources from public.news_crime_incidents where incident_id = :incident_id"
)


async def _publish_crime(
    db: AsyncSession, doc: RawDocument, index: int, crime: NewsCrime, dry_run: bool
) -> tuple[bool, str | None]:
    """
    Write one extracted crime and, if it qualifies, its published incident.

    The mobility path's twin, and it runs the same three steps in the same order —
    resolve the place without an LLM, decide whether it may be published, then ask
    the corroboration guard whether this is a new event or another account of one
    already on the map.

    The one structural difference is where the statement comes from. A flag's
    statement depends only on the flag, so `flag_row` can build it once. An
    attributed statement names **every** publisher that has carried the story, so
    it has to be rebuilt at merge time from the combined source list — which is why
    `crime_guard.merge_into` takes a statement rather than writing one.
    """
    place = await resolve_news_place(crime.location_text)
    reason = crime_discard_reason(crime, place)
    now = datetime.now(UTC)
    logger.info(
        "%s crime #%d %s at %r -> %s",
        doc.source_id,
        index,
        crime.category,
        crime.location_text,
        reason or f"incident near {place.resolved_name}",
    )
    if dry_run:
        return reason is None, reason

    source = {
        "source_id": doc.source_id,
        "url": doc.url,
        "title": doc.title,
        "published_at": doc.published_at.isoformat() if doc.published_at else None,
    }

    incident_id: UUID | None = None
    if reason is None:
        row = crime_row(doc=doc, index=index, crime=crime, place=place, now=now)
        match = await find_crime_duplicate(
            db,
            category=crime.category,
            lat=row["lat"],
            lon=row["lon"],
            radius_m=row["radius_m"],
            observed_at=row["observed_at"],
            summary_en=crime.summary_en,
            now=now,
        )
        if match is None:
            result = await db.execute(
                _INSERT_CRIME, {**row, "sources": json.dumps(row["sources"], ensure_ascii=False)}
            )
            incident_id = result.scalar_one()
        else:
            # Another outlet's account of something already published. Append this
            # publisher if it is not already cited -- `source_count` counts
            # publishers, not articles -- and rebuild the sentence so it names them
            # all.
            existing = (
                await db.execute(_SOURCES_OF, {"incident_id": match.incident_id})
            ).scalar_one() or []
            combined = list(existing)
            if doc.source_id not in {s.get("source_id") for s in combined}:
                combined.append(row["sources"][0])
            publishers = [
                publisher_name(s["source_id"])
                for s in combined
                if s.get("source_id")
            ]
            incident_id = await merge_crime_into(
                db,
                match,
                source=source,
                sources=combined,
                statement=to_attributed_statement(
                    category=crime.category,
                    publishers=publishers,
                    observed_at=row["observed_at"],
                    now=now,
                ),
                observed_at=row["observed_at"],
                now=now,
            )

    await db.execute(
        _INSERT_EXTRACTED_CRIME,
        {
            "doc_id": doc.doc_id,
            "category": crime.category,
            "summary_en": crime.summary_en,
            "location_text": crime.location_text,
            "confidence": crime.confidence,
            "source": json.dumps(source, ensure_ascii=False),
            "news_crime_id": incident_id,
            "discarded_reason": reason,
        },
    )
    return reason is None, reason


_INSERT_INCIDENT: Final = text(
    """
    insert into public.extracted_incidents
        (doc_id, kind, summary_en, location_text, severity_hint, mobility_impact,
         extraction_confidence, source, flag_id, discarded_reason)
    values
        (:doc_id, :kind, :summary_en, :location_text, :severity_hint, :mobility_impact,
         :confidence, cast(:source as jsonb), :flag_id, :discarded_reason)
    """
)


async def _publish(
    db: AsyncSession, doc: RawDocument, index: int, incident: NewsIncident, dry_run: bool
) -> tuple[bool, str | None]:
    """Write one incident and, if it qualifies, its flag. Returns (published, reason)."""
    place = await resolve_news_place(incident.location_text)
    reason = discard_reason(incident, place)
    logger.info(
        "%s #%d %s at %r -> %s",
        doc.source_id,
        index,
        incident.kind,
        incident.location_text,
        reason or f"flag near {place.resolved_name}",
    )
    if dry_run:
        return reason is None, reason

    source = {
        "source_id": doc.source_id,
        "url": doc.url,
        "title": doc.title,
        "published_at": doc.published_at.isoformat() if doc.published_at else None,
    }

    flag_id: UUID | None = None
    if reason is None:
        row = flag_row(doc=doc, index=index, incident=incident, place=place)

        # D05. Before this existed every incident became its own flag, so four
        # outlets reporting one fire produced four unconfirmed flags -- reading more
        # news made the surface *less* certain, which is backwards. Rumour Guard
        # decides whether this is another account of something already on the map.
        #
        # It declines whenever it cannot judge confidently (no usable summary, no
        # embedding model, nothing similar enough), and declining falls through to the
        # insert below, which is exactly the pre-D05 behaviour. That asymmetry is
        # deliberate: a duplicate pin is a cosmetic cost, a wrongly merged flag is a
        # false `confirmed` claim.
        match = await find_duplicate(
            db,
            kind=IncidentKind(incident.kind),
            lat=row["lat"],
            lon=row["lon"],
            radius_m=row["radius_m"],
            observed_at=row["observed_at"],
            summary_en=incident.summary_en,
            now=datetime.now(UTC),
        )
        if match is None:
            result = await db.execute(
                _INSERT_FLAG, {**row, "sources": json.dumps(row["sources"], ensure_ascii=False)}
            )
            flag_id = result.scalar_one()
        else:
            # Corroboration, not a new event. The incident row below still points at
            # the flag, so `extracted_incidents` keeps every article while the flag
            # keeps every *publisher* -- which is what lets the audit trail answer
            # "why is this confirmed?" rather than just asserting it.
            outcome = await merge_into(db, match, source=source, now=datetime.now(UTC))
            flag_id = outcome.flag_id
    await db.execute(
        _INSERT_INCIDENT,
        {
            "doc_id": doc.doc_id,
            "kind": incident.kind,
            "summary_en": incident.summary_en,
            "location_text": incident.location_text,
            "severity_hint": incident.severity_hint,
            "mobility_impact": incident.mobility_impact.value,
            "confidence": incident.confidence,
            "source": json.dumps(source, ensure_ascii=False),
            "flag_id": flag_id,
            "discarded_reason": reason,
        },
    )
    return reason is None, reason


# ---------------------------------------------------------------------------
# The agent
# ---------------------------------------------------------------------------


class LiveRiskAgent(BaseAgent):
    name = "live_risk"
    cron = "*/15 * * * *"

    async def run(self, ctx: AgentContext) -> AgentResult:
        if ctx.db is None:
            raise RuntimeError("live_risk needs ctx.db; the runner provides it")
        db = ctx.db
        errors: list[str] = []
        metrics: dict[str, float] = dict.fromkeys(
            (
                "listed",
                "relevant",
                "fetched",
                "documents_read",
                "incidents",
                "published",
                "low_confidence",
                "unresolved_location",
                "rejected",
                # The crime half, counted separately so a run's log says which
                # surface the work went to. `dict.fromkeys` pre-seeds them because
                # the publish loop increments by key and a missing key would raise.
                "crimes",
                "crimes_published",
                "crime_low_confidence",
                "crime_unresolved_location",
            ),
            0.0,
        )

        by_source: list[list[RawDocument]] = []
        async with Fetcher() as fetcher:
            for source in SOURCES:
                try:
                    by_source.append(await self._ingest(source, fetcher, db, ctx, metrics, errors))
                    if not ctx.dry_run:
                        await db.commit()
                except Exception as problem:  # noqa: BLE001 - one publisher must not stop the rest
                    await db.rollback()
                    errors.append(f"{source.source_id}: {type(problem).__name__}: {problem}")

        fresh = interleave(by_source)
        fresh_ids = {doc.doc_id for doc in fresh}
        retry = await store.unextracted(db, since=ctx.now - LOOKBACK, limit=MAX_EXTRACTIONS_PER_RUN)
        queue = (fresh + [doc for doc in retry if doc.doc_id not in fresh_ids])[
            :MAX_EXTRACTIONS_PER_RUN
        ]

        consecutive_misses = 0
        for doc in queue:
            try:
                extraction = await complete(
                    SYSTEM_PROMPT,
                    user_prompt(doc),
                    NewsExtraction,
                    feature=FEATURE_EXTRACT,
                    max_tokens=1024,
                )
            except LLMUnavailable as problem:
                errors.append(f"extract {doc.doc_id[:12]}: {problem}")
                consecutive_misses += 1
                if consecutive_misses >= 2:
                    break  # rate limited or out of quota; the queue waits for the next run
                continue
            consecutive_misses = 0
            metrics["documents_read"] += 1
            try:
                for index, incident in enumerate(extraction.incidents):
                    metrics["incidents"] += 1
                    published, reason = await _publish(db, doc, index, incident, ctx.dry_run)
                    metrics["published" if published else str(reason)] += 1
                # The second half of the same extraction, down a path that shares
                # nothing with the first but the article it came from: a different
                # table, a different guard, a different decay. See `NewsExtraction`.
                for index, crime in enumerate(extraction.crimes):
                    metrics["crimes"] += 1
                    published, reason = await _publish_crime(db, doc, index, crime, ctx.dry_run)
                    metrics["crimes_published" if published else f"crime_{reason}"] += 1
                if not ctx.dry_run:
                    await store.mark_extracted(db, doc.doc_id, ctx.now)
                    await db.commit()
            except Exception as problem:  # noqa: BLE001 - the document stays in the retry queue
                await db.rollback()
                errors.append(f"publish {doc.doc_id[:12]}: {type(problem).__name__}: {problem}")

        status: AgentStatus = "ok"
        if errors:
            # `by_source` holds one list per publisher that *completed*: a
            # publisher that raised never appended. Its length is therefore "how
            # many publishers answered", and its contents are "what they had" —
            # two different questions, and only the first is about our health.
            #
            # This used to ask the second one (`not fresh`: did anybody hand us a
            # document). On a Dhaka laptop those answers coincide often enough to
            # look right. From the deployed host they do not. Five of the eight
            # publishers sit behind a Cloudflare bot check that answers 403 to
            # anything without a browser fingerprint — robots.txt included — and
            # `Fetcher._robots_for` reads a 403 on robots.txt as disallow-all,
            # which is the correct conservative reading and is not worked around.
            # So those five refuse on every single run, `errors` is never empty,
            # and the moment the other three had a quiet half-hour with nothing
            # new, a fleet that was working as designed reported itself dead.
            #
            # Failure is now the two things that really are failures: nobody
            # answered at all, or everybody answered and not one of the documents
            # they gave us could be read (an LLM outage, via the
            # `consecutive_misses` break above). "Some publishers are blocked and
            # the rest had no news" is `partial`, which is what `partial` is for.
            nothing_worked = not by_source or (bool(queue) and metrics["documents_read"] == 0)
            status = "failed" if nothing_worked else "partial"
        return AgentResult(
            agent=self.name,
            run_id=ctx.run_id,
            started_at=ctx.now,
            finished_at=datetime.now(UTC),
            status=status,
            items_in=len(queue),
            items_out=int(metrics["published"]),
            errors=errors,
            metrics=metrics,
        )

    async def _ingest(
        self,
        source: Source,
        fetcher: Fetcher,
        db: AsyncSession,
        ctx: AgentContext,
        metrics: dict[str, float],
        errors: list[str],
    ) -> list[RawDocument]:
        """List, filter, read and store one publisher's new articles."""
        refs = await source.list_recent(fetcher, ctx.now)
        relevant = [ref for ref in refs if is_relevant(ref, ctx.now)]
        known = await store.known_urls(db, [ref.url for ref in relevant])
        to_read = [ref for ref in relevant if ref.url not in known][:MAX_READS_PER_SOURCE]
        metrics["listed"] += len(refs)
        metrics["relevant"] += len(relevant)

        stored: list[RawDocument] = []
        for ref in to_read:
            try:
                doc = await source.read(fetcher, ref, ctx.now)
            except Exception as problem:  # noqa: BLE001 - one article must not stop its source
                errors.append(f"{source.source_id} read {ref.url[-40:]}: {type(problem).__name__}")
                continue
            if doc is None:
                continue
            metrics["fetched"] += 1
            if ctx.dry_run or await store.save(db, doc):
                stored.append(doc)
        return stored


AGENT = LiveRiskAgent()


# ---------------------------------------------------------------------------
# The offline replay — DEMO_PLAN.md D04's "passes again with the network off"
# ---------------------------------------------------------------------------


async def export_replay(db: AsyncSession, now: datetime) -> int:
    """
    Write the live flags served right now to `data/fixtures/live_replay.json`.

    The offline demo has no database, no model and no publisher, so replaying
    `raw_documents` (which lives in Supabase) cannot work. What can: the fixture
    mechanism D02 already built. Each live flag becomes a fixture entry — structured
    fields only, times relative to the export — and `SeededRiskSurface` serves those
    entries beside the hand-built ones, re-anchored to whenever the process starts.
    So a run captured on the 14th still shows fresh, decaying news flags with their
    real headlines on the 24th.

    `place` is re-resolved from the stored `location_text` through the same
    deterministic gazetteer path the agent used, and the statement is re-derived by
    `framing.py` at load — the replay file holds no flag prose, like every fixture.
    """
    result = await db.execute(
        text(
            """
            select f.event_key, f.kind, f.radius_m, f.severity_0, f.half_life_hours,
                   f.observed_at, f.sources::text as sources_json,
                   extensions.ST_Y(f.location::extensions.geometry) as lat,
                   extensions.ST_X(f.location::extensions.geometry) as lon,
                   e.mobility_impact, e.location_text
            from public.risk_flags f
            join public.extracted_incidents e on e.flag_id = f.flag_id
            where f.event_key like :prefix
              and f.status in ('unconfirmed', 'confirmed')
              and f.expires_at > :now
            order by f.observed_at desc
            """
        ),
        {"prefix": LIVE_KEY_PREFIX + "%", "now": now},
    )

    def hours_from_now(at: datetime) -> float:
        return round((at - now).total_seconds() / 3600, 3)

    entries: list[dict[str, Any]] = []
    for row in result:
        place = await resolve_news_place(row.location_text)
        entries.append(
            {
                "event_key": SEED_KEY_PREFIX + row.event_key,
                "kind": row.kind,
                "lat": float(row.lat),
                "lon": float(row.lon),
                "radius_m": int(row.radius_m),
                "severity_0": float(row.severity_0),
                "half_life_hours": float(row.half_life_hours),
                "mobility_impact": row.mobility_impact,
                "place": place.resolved_name if place.method != "unresolved" else None,
                "observed_offset_hours": hours_from_now(row.observed_at),
                "source_count": 1,
                "sources": [
                    {
                        "source_id": s["source_id"],
                        "url": s["url"],
                        "title": s.get("title"),
                        "published_offset_hours": hours_from_now(
                            datetime.fromisoformat(s["published_at"])
                            if s.get("published_at")
                            else row.observed_at
                        ),
                    }
                    for s in json.loads(row.sources_json)
                ],
            }
        )

    write_replay(entries, now, REPLAY_PATH)
    return len(entries)


def write_replay(entries: list[dict[str, Any]], now: datetime, path: Path) -> None:
    document = {
        "_README": (
            "Captured live news flags, replayed by SeededRiskSurface when "
            "RISK_SURFACE_IMPL=seeded. Written by `python -m app.agents export-replay`; "
            "do not edit by hand. Times are hours relative to `exported_at` and are "
            "re-anchored to the moment the backend starts. No mobility_statement: "
            "framing.py derives it at load, as for every fixture."
        ),
        "exported_at": now.isoformat(),
        "flags": entries,
    }
    path.write_text(json.dumps(document, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
