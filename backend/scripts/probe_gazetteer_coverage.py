#!/usr/bin/env python3
"""
How much of Dhaka can the gazetteer actually place?

    python backend/scripts/probe_gazetteer_coverage.py
    python backend/scripts/probe_gazetteer_coverage.py --verbose      list every miss
    python backend/scripts/probe_gazetteer_coverage.py --json out.json

What this is, and what it is not
--------------------------------
This is a **coverage** measure, not an accuracy measure. It asks one question of
each reference — does the gazetteer return a point, refuse, or know nothing —
and it deliberately does not check *where* that point is.

`data/eval/geocoding/references.json` is the accuracy measure, and it is the one
to care about: 53 cases with hand-checked coordinates and a recorded baseline,
so a change that starts resolving more places while moving existing pins is
caught there. The two are complementary and neither replaces the other. Adding
coordinates to the list below would mean inventing ground truth for 150 places,
and invented ground truth is worse than an honest coverage count.

Why a separate file was needed
------------------------------
The accuracy set is 53 references chosen around the demo. It cannot answer the
question S31 exists to answer, which is whether the pipeline can place the kinds
of reference Dhaka crime and traffic copy actually uses:

    * a named road, which the harvest did not fetch at all before S31;
    * a thana, which is how crime reporting is organised;
    * the outer city — Uttarkhan, Demra, Kadamtali — which sat outside the box.

The references below are written the way a news desk writes them. A `REFUSED`
is not a failure: "Mirpur Road" is 8 km long and "Sector 11" belongs to two
places, and declining both is the discard invariant working. `UNKNOWN` is the
number this sprint is trying to move.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Final

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.geo.gazetteer import gazetteer, reset_cache  # noqa: E402  (after sys.path)

# Named roads, as a report names them. None of these could resolve before S31:
# the harvest never asked OpenStreetMap for a `highway`.
ROADS: Final = (
    "Satmasjid Road",
    "সাতমসজিদ রোড",
    "Mirpur Road",
    "মিরপুর রোড",
    "Airport Road",
    "Begum Rokeya Sarani",
    "বেগম রোকেয়া সরণি",
    "Pragati Sarani",
    "প্রগতি সরণি",
    "Bijoy Sarani",
    "বিজয় সরণি",
    "Manik Mia Avenue",
    "Kazi Nazrul Islam Avenue",
    "Elephant Road",
    "New Elephant Road",
    "Green Road",
    "Panthapath",
    "পান্থপথ",
    "Bailey Road",
    "বেইলি রোড",
    "Gulshan Avenue",
    "Kemal Ataturk Avenue",
    "Tejgaon Link Road",
    "Hatirjheel",
    "হাতিরঝিল",
    "Toyenbee Circular Road",
    "Shahid Tajuddin Ahmed Sarani",
    "Rokeya Sarani",
    "DIT Road",
    "Progoti Sarani",
    "Shaheed Buddhijibi Road",
    "Kakrail",
    "কাকরাইল",
    "Nawabpur Road",
    "Johnson Road",
    "Hare Road",
    "Minto Road",
    "Sonargaon Road",
    "Mymensingh Road",
    "Outer Circular Road",
    "Inner Circular Road",
)

# Thanas. Crime reporting is organised by them and the previous harvest had no
# layer that reliably carried their names.
THANAS: Final = (
    "Hazaribagh",
    "হাজারীবাগ",
    "Kamrangirchar",
    "কামরাঙ্গীরচর",
    "Shyampur",
    "শ্যামপুর",
    "Kadamtali",
    "কদমতলী",
    "Jatrabari",
    "যাত্রাবাড়ী",
    "Demra",
    "ডেমরা",
    "Khilgaon",
    "খিলগাঁও",
    "Sabujbagh",
    "সবুজবাগ",
    "Mugda",
    "মুগদা",
    "Badda",
    "বাড্ডা",
    "Vatara",
    "ভাটারা",
    "Khilkhet",
    "খিলক্ষেত",
    "Uttarkhan",
    "উত্তরখান",
    "Dakshinkhan",
    "দক্ষিণখান",
    "Turag",
    "তুরাগ",
    "Pallabi",
    "পল্লবী",
    "Rupnagar",
    "Darus Salam",
    "Shah Ali",
    "Kafrul",
    "কাফরুল",
    "Bhashantek",
    "Cantonment",
    "Tejgaon",
    "তেজগাঁও",
    "Ramna",
    "রমনা",
    "Paltan",
    "পল্টন",
    "Sutrapur",
    "সূত্রাপুর",
    "Kotwali",
    "কোতোয়ালী",
    "Bangshal",
    "বংশাল",
    "Chawkbazar",
    "চকবাজার",
    "Lalbagh",
    "লালবাগ",
    "Gendaria",
    "গেন্ডারিয়া",
    "Wari",
    "ওয়ারী",
    "Adabor",
    "আদাবর",
    "Sher-e-Bangla Nagar",
    "Mohammadpur",
    "মোহাম্মদপুর",
)

# The outer city. All of this was outside the old 23.70-23.90 / 90.33-90.50 box,
# so an article about it was discarded for being out of area.
OUTER: Final = (
    "Matuail",
    "মাতুয়াইল",
    "Konapara",
    "কোনাপাড়া",
    "Dania",
    "ডেমরা স্টাফ কোয়ার্টার",
    "Sarulia",
    "Amulia",
    "Nandipara",
    "নন্দীপাড়া",
    "Trimohoni",
    "Beraid",
    "বেরাইদ",
    "Satarkul",
    "সাতারকুল",
    "Dumni",
    "Uttara Sector 18",
    "Abdullahpur",
    "আব্দুল্লাহপুর",
    "Kamarpara",
    "Diabari",
    "দিয়াবাড়ী",
    "Baunia",
    "Keraniganj",
    "কেরানীগঞ্জ",
    "Zinzira",
    "Postogola",
    "পোস্তগোলা",
    "Fatullah",
    "Tongi",
    "টঙ্গী",
)

# Landmarks the pipeline already handled, carried here as a regression check:
# S31 must not make any of these worse.
LANDMARKS: Final = (
    "Karwan Bazar",
    "কারওয়ান বাজার",
    "New Market",
    "নিউ মার্কেট",
    "Gulistan",
    "গুলিস্তান",
    "Nilkhet",
    "নীলক্ষেত",
    "Shewrapara",
    "শেওড়াপাড়া",
    "Kazipara",
    "কাজীপাড়া",
    "Agargaon",
    "আগারগাঁও",
    "Nakhalpara",
    "নাখালপাড়া",
    "Monipuripara",
    "Mohakhali",
    "মহাখালী",
    "Farmgate",
    "ফার্মগেট",
    "Shahbagh",
    "শাহবাগ",
    "Motijheel",
    "মতিঝিল",
    "Dhanmondi",
    "ধানমন্ডি",
    "Gulshan 1",
    "Gulshan 2",
    "Banani",
    "বনানী",
    "Notun Bazar",
    "নতুন বাজার",
    "Kuril",
    "কুড়িল",
    "Bashundhara",
    "Rampura",
    "রামপুরা",
    "Malibagh",
    "মালিবাগ",
    "Mouchak",
    "Sayedabad",
    "সায়েদাবাদ",
    "Gabtoli",
    "গাবতলী",
    "Mirpur 1",
    "Mirpur 2",
    "Mirpur 10",
    "Uttara",
    "উত্তরা",
    "Azampur",
    "আজমপুর",
    "Jasimuddin",
    "House Building",
    "Mohakhali bus terminal",
    "Jatrabari chourasta",
    "Mirpur 10 golchattar",
)

GROUPS: Final = {
    "roads": ROADS,
    "thanas": THANAS,
    "outer city": OUTER,
    "landmarks (regression)": LANDMARKS,
}


def classify(query: str) -> tuple[str, str]:
    """(outcome, detail). RESOLVED, REFUSED or UNKNOWN."""
    g = gazetteer()
    hit = g.resolve(query)
    if hit is not None:
        return "RESOLVED", f"{hit.entry.display_name} [{hit.entry.kind}] r={hit.entry.radius_m}m"
    if g.matches_ambiguous_only(query):
        return "REFUSED", "known, but the name cannot identify one place"
    return "UNKNOWN", "no entry of any kind"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verbose", action="store_true", help="List every reference.")
    parser.add_argument("--json", dest="as_json", default=None, help="Write the full result.")
    parser.add_argument("--gazetteer", default=None, help="A different gazetteer file to measure.")
    args = parser.parse_args()

    if args.gazetteer:
        from app.geo import gazetteer as module

        module.GAZETTEER_PATH = Path(args.gazetteer)  # type: ignore[misc]
    reset_cache()

    report: dict[str, object] = {"entries": len(gazetteer()), "groups": {}}
    totals = {"RESOLVED": 0, "REFUSED": 0, "UNKNOWN": 0}

    print(f"{len(gazetteer())} entries loaded\n")
    for group, references in GROUPS.items():
        counts = {"RESOLVED": 0, "REFUSED": 0, "UNKNOWN": 0}
        rows: list[dict[str, str]] = []
        for query in references:
            outcome, detail = classify(query)
            counts[outcome] += 1
            totals[outcome] += 1
            rows.append({"query": query, "outcome": outcome, "detail": detail})
        placed = counts["RESOLVED"] / len(references)
        print(
            f"{group:24s} {counts['RESOLVED']:3d} resolved  "
            f"{counts['REFUSED']:3d} refused  {counts['UNKNOWN']:3d} unknown"
            f"   ({placed:.0%} placed of {len(references)})"
        )
        if args.verbose:
            for entry in rows:
                if args.verbose:
                    mark = {"RESOLVED": "  +", "REFUSED": "  ~", "UNKNOWN": "  -"}[entry["outcome"]]
                    print(f"{mark} {entry['query']:34s} {entry['detail']}")
        report["groups"][group] = {"counts": counts, "rows": rows}  # type: ignore[index]

    total = sum(totals.values())
    print(
        f"\n{'TOTAL':24s} {totals['RESOLVED']:3d} resolved  {totals['REFUSED']:3d} refused  "
        f"{totals['UNKNOWN']:3d} unknown   ({totals['RESOLVED'] / total:.0%} placed of {total})"
    )
    report["totals"] = totals

    if args.as_json:
        Path(args.as_json).write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"wrote {args.as_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
