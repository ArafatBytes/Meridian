"""
Generate General Diary drafts for a native speaker to read. D08, ADR 0007.

    docker exec meridian-api python scripts/eval_gd_drafts.py
    python scripts/eval_gd_drafts.py --runs 3 --out data/eval/gd_drafts.md

**This script exists because of a gate, not a metric.** D08's gate is that a
native Bangla speaker reads at least three drafts and signs off. Formal legal
Bangla is not validatable by anyone here, and the narrative is the entire
product in both routes -- the printed form and the online app's বিবরণ box both
carry this paragraph and nothing else. So the useful output is readable drafts,
not a score.

What *is* checked automatically is only what a machine can honestly check:

* **a date or number the model invented** -- a changed year on a police
  application is a false statement by the person who signs it. Round one of the
  bake-off moved 2026 to 2025, which is why this check exists at all;
* **the line the form already prints** -- both models used to repeat
  `আমি এই মর্মে জানাচ্ছি যে,`, which the DMP form prints above the blank;
* **Bangla script ratio** -- gpt-oss-120b leaves dates and IMEIs in Latin
  script, and a half-English application looks unserious at a thana counter;
* **run-to-run variation** -- the same input through the same chain, so the
  reviewer knows whether they are signing off on a stable prompt or on one
  lucky sample.

None of those say the Bangla is *right*. Only the reviewer does.
"""
from __future__ import annotations

import argparse
import asyncio
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.casework.draft import draft_narrative  # noqa: E402
from app.llm.client import LLMUnavailable  # noqa: E402

BANGLA = re.compile(r"[ঀ-৿]")
LATIN = re.compile(r"[A-Za-z]")
BN_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
FORM_LINE = "আমি এই মর্মে জানাচ্ছি যে"
# The form prints its own closing underneath the blank. A narrative that ends
# with one of these makes the application close twice.
CLOSINGS = ("মর্জি", "কামনা", "অতএব", "ডায়েরীভুক্ত করার জন্য", "ডাইরিভুক্ত করার জন্য")


@dataclass(frozen=True, slots=True)
class Scenario:
    id: str
    why: str
    category: str
    title: str
    description: str
    incident_at: datetime
    location_name: str


# Three, because three is the gate. Each one is here to make a different kind of
# mistake visible to the reviewer.
SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        id="assault",
        why="Banglais input, attacker unidentified. Does it invent a description?",
        category="assault",
        title="Attacked while walking home",
        description=(
            "ami Kakrail mor theke hete bari firchilam, duijon lok amake pichon "
            "theke dhore mare. amar mathay aghat lagse. tara ke chinina. ekjon er "
            "hate lathi chilo. amar phone o nia gese."
        ),
        incident_at=datetime(2026, 10, 9, 21, 40),
        location_name="Kakrail mor",
    ),
    Scenario(
        id="snatching",
        why="Specific facts present. Do the IMEI, the model and the time survive intact?",
        category="theft",
        title="Phone snatched at Shapla Chattar",
        description=(
            "I was standing near Motijheel Shapla Chattar waiting for a bus. A man "
            "on a red motorcycle snatched my mobile phone from my hand and drove "
            "towards Arambagh. The phone is a Samsung A54, black, IMEI "
            "352099001761481. I could not see his face, he wore a helmet."
        ),
        incident_at=datetime(2026, 10, 8, 19, 15),
        location_name="Motijheel Shapla Chattar",
    ),
    Scenario(
        id="harassment",
        why="Sensitive, no physical act. Does it reach for a legal conclusion?",
        category="harassment",
        title="Someone waiting outside my house",
        description=(
            "Ekta lok gotho ek soptaho dhore amar basar samne daray thake, ami ber "
            "hole pichone pichone ase. ajke se amar name chitkar kore kotha bolse. "
            "ami voy pacchi. amar protibeshi o dekhse."
        ),
        incident_at=datetime(2026, 10, 9, 18, 0),
        location_name="Elephant Road",
    ),
)


def bangla_percent(text: str) -> int:
    bangla, latin = len(BANGLA.findall(text)), len(LATIN.findall(text))
    total = bangla + latin
    return round(100 * bangla / total) if total else 0


def invented_numbers(narrative: str, scenario: Scenario) -> list[str]:
    """Numbers in the draft that appear nowhere in what the model was given."""
    source = " ".join([
        scenario.description,
        scenario.location_name,
        scenario.incident_at.strftime("%d %B %Y %I:%M %p %Y %m %d %H %M"),
    ]).translate(BN_DIGITS)
    given = set(re.findall(r"\d+", source))
    produced = set(re.findall(r"\d+", narrative.translate(BN_DIGITS)))
    return sorted(number for number in produced - given if len(number) > 2)


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", type=int, default=2,
                        help="drafts per scenario, so variation is visible")
    parser.add_argument("--out", default="data/eval/gd_drafts.md",
                        help="markdown file for the reviewer")
    args = parser.parse_args()

    lines: list[str] = [
        "# General Diary drafts — for native-speaker review",
        "",
        f"Generated {datetime.now():%d %B %Y, %H:%M}. D08 gate, ADR 0007.",
        "",
        "**What to check.** Is this formal enough to hand to a duty officer? Does it",
        "read as something a complainant wrote, in the first person? Does it state",
        "anything the complainant did not say? Does it name an offence or a section of",
        "law — it must not; that is the officer's decision. Would a thana accept it?",
        "",
        "Each draft is the paragraph that goes between the DMP form's two fixed lines,",
        "and into the Online GD app's `বিবরণ` box unchanged. Nothing else carries it.",
        "",
        "---",
        "",
    ]

    failures = 0
    for scenario in SCENARIOS:
        lines += [f"## {scenario.id}", "", f"*{scenario.why}*", "",
                  "**What the complainant wrote:**", "", "> " +
                  scenario.description.replace("\n", " "), ""]
        for run in range(1, args.runs + 1):
            try:
                result = await draft_narrative(
                    category=scenario.category,
                    title=scenario.title,
                    description=scenario.description,
                    incident_at=scenario.incident_at,
                    location_name=scenario.location_name,
                )
            except LLMUnavailable as problem:
                failures += 1
                lines += [f"**Run {run} — every tier unavailable:** {problem}", ""]
                print(f"{scenario.id} run {run}: FAILED — {problem}")
                continue

            narrative = result.draft.narrative_bn
            invented = invented_numbers(narrative, scenario)
            repeats = FORM_LINE in narrative
            closes = [word for word in CLOSINGS if word in narrative]
            percent = bangla_percent(narrative)

            flags = []
            if invented:
                flags.append(f"**INVENTED NUMBER {invented}**")
            if repeats:
                flags.append("**REPEATS THE FORM'S OWN LINE**")
            if closes:
                flags.append(f"**WRITES ITS OWN CLOSING {closes}**")
            if percent < 95:
                flags.append(f"**{100 - percent}% Latin script**")

            lines += [
                f"**Run {run}** — {result.engine}, {result.elapsed_seconds:.1f}s, "
                f"{percent}% Bangla"
                + (" · " + " · ".join(flags) if flags else ""),
                "",
                "```",
                narrative,
                "```",
                "",
                f"*English gloss:* {result.draft.summary_en}",
                "",
            ]
            if result.draft.missing_details:
                lines += ["*The officer will still ask for:* "
                          + "; ".join(result.draft.missing_details), ""]
            if flags:
                failures += 1
            print(f"{scenario.id} run {run}: {result.engine} "
                  f"{result.elapsed_seconds:.1f}s {percent}% bangla "
                  f"{'FLAGGED ' + ', '.join(flags) if flags else 'ok'}")
        lines += ["---", ""]

    lines += [
        "## Reviewer sign-off",
        "",
        "- [ ] Read all drafts above",
        "- [ ] The Bangla is formal enough for a thana",
        "- [ ] Nothing is stated that the complainant did not say",
        "- [ ] No offence or section of law is named",
        "",
        "Name: ______________________  Date: ____________",
        "",
    ]

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nwritten to {out}")
    if failures:
        print(f"{failures} draft(s) flagged automatically — read them before the reviewer does")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
