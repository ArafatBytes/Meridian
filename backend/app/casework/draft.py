"""
One report in, a formal-Bangla General Diary narrative out. D08, ADR 0007.

    draft = await draft_narrative(
        category="assault",
        description="ami Kakrail mor theke hete bari firchilam...",
        incident_at=datetime(2026, 10, 9, 21, 40),
        location_name="Kakrail mor",
    )
    draft.narrative_bn   # the paragraph that goes on the form AND in the app

The whole flow:

    report
      -> one model call, formal Bangla          gemini -> groq
      -> the narrative, an English gloss, and what the officer will still ask

**The complainant's identity is never sent to the model.** The NID, the parents'
names and the addresses live in the GD profile and are stamped onto the printed
form by `render.py`. The model sees the incident and nothing else -- partly
because it does not need them to write the narrative, and partly because an NID
is not something to hand to a free-tier API for no reason.

Nothing here decides anything. It proposes words; a person reads them, edits
them, approves them and signs them. The signature is the point: an invented
detail in a police document is a false statement by whoever signed it, which is
why the prompt would rather leave a visible gap than fill one in.
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Final

from app.llm.client import FEATURE_GD, complete_with_engine
from app.llm.models import GdDraft

logger = logging.getLogger(__name__)

# Both lines below were measured defects on 2026-10-10, not guesses. Round one
# of the bake-off had flash-lite writing 2025 for an incident in 2026, and both
# models repeating a line the form already prints above the blank. Each went to
# 0 occurrences in 9 runs once the prompt said so.
SYSTEM: Final = (
    "You draft the body of a General Diary (সাধারণ ডাইরী) application for a "
    "Bangladesh police station, in the formal written Bangla used in official "
    "applications.\n"
    "You write in the first person, as the complainant.\n"
    "You use ONLY the facts the complainant gave you. You never add a detail, "
    "never guess a name, an address, a time or an amount, and never state or "
    "imply which offence or section of law was committed — that is the "
    "officer's decision, not yours.\n"
    "Copy every date, time, number and name exactly as given. Never shift a "
    "year, round a time or correct a spelling of a place.\n"
    "A number that identifies a thing — an IMEI, a phone number, an NID, a "
    "vehicle registration, an account or a serial number — must be written in "
    "the SAME digits it was given to you, character for character. Do NOT "
    "convert it to Bangla numerals: measured on 2026-10-10, converting a "
    "15-digit IMEI dropped a digit on both attempts, and a wrong IMEI means a "
    "stolen phone can never be traced. Dates and times may use Bangla "
    "numerals; identifiers may not.\n"
    "Where a fact a police officer would expect is missing, write […] in its "
    "place and list it in missing_details. An invented detail in a police "
    "document is a false statement by the person who signs it.\n"
    "Begin with বিনীত নিবেদন এই যে, and state the date, time and place of the "
    "incident inside the narrative.\n"
    "The form already prints 'আমি এই মর্মে জানাচ্ছি যে,' above your text and "
    "the closing line and signature block below it. Write neither. The exact "
    "words আমি এই মর্মে জানাচ্ছি যে must never appear anywhere in your text.\n"
    "End with the last fact of the incident. Do NOT write a closing request — "
    "no অতএব, no মর্জি, no কামনা, no 'সদয় মর্জি কামনা করি', no "
    "'ডায়েরীভুক্ত করার জন্য অনুরোধ'. The form prints "
    "'অতএব, মহোদয় উপরোক্ত বিষয়টি আপনার থানায় সাধারণ ডাইরীভূক্ত করতে মর্জি হয়।' "
    "underneath, and a second closing makes the application end twice."
)

# What the user confirmed in the report. It selects nothing in the prompt beyond
# giving the model the word the complainant themselves chose -- D07's cue
# outputs and its proposed category never reach this call. ADR 0007.
CATEGORY_BN: Final = {
    "theft": "চুরি",
    "assault": "মারধর",
    "harassment": "উত্ত্যক্তকরণ",
    "vandalism": "ভাঙচুর",
    "burglary": "সিঁধেল চুরি",
    "robbery": "ছিনতাই",
    "fraud": "প্রতারণা",
    "other": "অন্যান্য",
}


@dataclass(frozen=True, slots=True)
class DraftResult:
    draft: GdDraft
    engine: str
    elapsed_seconds: float


# A run of seven or more digits is an identifier, not a quantity: an IMEI, a
# phone number, an NID, a vehicle registration, an account number.
IDENTIFIER: Final = re.compile(r"\d[\d\s\-]{5,}\d")
ANY_DIGITS: Final = re.compile(r"[\d০-৯][\d০-৯\s\-]{4,}[\d০-৯]")
TO_LATIN: Final = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")


def _bare(value: str) -> str:
    return re.sub(r"\D", "", value.translate(TO_LATIN))


def _repair_identifiers(source: str, narrative: str) -> tuple[str, list[str]]:
    """
    Put the identifiers back, digit for digit.

    Measured on 2026-10-10: asked to carry the IMEI 352099001761481 into the
    narrative, Gemini produced 35209900171481, 35099001761481 and
    3352099001761481 across five attempts — a digit dropped, dropped again, and
    one added. Telling it not to convert the number to Bangla numerals did not
    help, because the problem is copying a long digit string at all, not the
    script it is copied into.

    So the model does not get to be responsible for this. We already hold the
    exact string the complainant typed; this substitutes it back in. Where that
    cannot be done unambiguously — several identifiers of similar length — it
    is not guessed at. It becomes a line in `missing_details`, which the review
    screen shows the user before they sign anything.

    A wrong IMEI on a police report is not a typo. It is a stolen phone that
    can never be traced.
    """
    notes: list[str] = []
    placed: set[str] = set()
    for match in IDENTIFIER.finditer(source):
        exact = match.group().strip()
        digits = _bare(exact)
        if len(digits) < 7 or digits in placed:
            continue
        placed.add(digits)

        # Compare whole digit runs, never substrings. An extra leading digit
        # makes 3352099001761481 contain 352099001761481, and a substring test
        # reads that corrupted number as correct.
        runs = list(ANY_DIGITS.finditer(narrative))
        if any(_bare(run.group()) == digits for run in runs):
            continue

        candidates = [
            run for run in runs
            if abs(len(_bare(run.group())) - len(digits)) <= 3
            and _bare(run.group()) not in placed
        ]
        if len(candidates) == 1:
            found = candidates[0]
            narrative = narrative[: found.start()] + exact + narrative[found.end():]
            logger.warning(
                "GD draft: model wrote %r for identifier %r — substituted the "
                "complainant's own value", found.group().strip(), exact,
            )
        elif candidates:
            notes.append(
                f"Check the number in the text reads exactly {exact} — "
                f"the draft may have altered it"
            )
            logger.warning(
                "GD draft: identifier %r has %d possible matches in the "
                "narrative — flagged for the user rather than guessed at",
                exact, len(candidates),
            )
        # No candidate at all means the model left the number out rather than
        # mangling it. That is an omission the user can see for themselves, and
        # warning about a number that is not on the page is just noise.
    return narrative, notes


def _prompt(
    *,
    category: str,
    title: str,
    description: str,
    incident_at: datetime,
    location_name: str | None,
) -> str:
    """
    What the model is told. Deliberately flat: labelled lines, no instructions
    mixed in, and the complainant's own words quoted last and unedited so the
    model is clearly copying from them rather than paraphrasing a summary.
    """
    lines = [
        f"Incident date and time: {incident_at.strftime('%d %B %Y, %I:%M %p')}",
        f"Category the complainant confirmed: {category} ({CATEGORY_BN.get(category, category)})",
    ]
    if location_name:
        lines.append(f"Place, as the complainant named it: {location_name}")
    if title and title.strip().casefold() != description.strip().casefold()[: len(title)]:
        lines.append(f"The complainant's own title for the report: {title}")
    lines.append("What the complainant wrote:")
    lines.append(description)
    return "\n".join(lines)


async def draft_narrative(
    *,
    category: str,
    title: str,
    description: str,
    incident_at: datetime,
    location_name: str | None = None,
    request_timeout: float = 20.0,
) -> DraftResult:
    """
    Raises `LLMUnavailable` when every tier in `LLM_CHAIN_GD` is exhausted.

    There is no fallback narrative and there deliberately is not one: a
    template with the user's description dropped into it would look like a
    drafted application while being nothing of the kind, and the person
    signing it would have no way to tell. An error the user can see is the
    honest failure.
    """
    started = time.perf_counter()
    result_draft, engine = await complete_with_engine(
        SYSTEM,
        _prompt(
            category=category,
            title=title,
            description=description,
            incident_at=incident_at,
            location_name=location_name,
        ),
        GdDraft,
        feature=FEATURE_GD,
        request_timeout=request_timeout,
        max_tokens=1200,
    )
    narrative, repairs = _repair_identifiers(description, result_draft.narrative_bn)
    if narrative != result_draft.narrative_bn or repairs:
        result_draft = result_draft.model_copy(
            update={
                "narrative_bn": narrative,
                "missing_details": [*repairs, *result_draft.missing_details][:6],
            }
        )

    elapsed = time.perf_counter() - started
    logger.info(
        "GD narrative drafted by %s in %.2fs — %d chars, %d missing detail(s)",
        engine, elapsed, len(result_draft.narrative_bn),
        len(result_draft.missing_details),
    )
    return DraftResult(draft=result_draft, engine=engine, elapsed_seconds=elapsed)
