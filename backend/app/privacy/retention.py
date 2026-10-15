"""
What we keep, for how long, and what deleting it means. B14.

The concept document makes one testable privacy promise, §9:

    **Data minimisation.** Location history is retained only as long as
    operationally necessary, local storage is encrypted, and all API
    communication is over HTTPS with JWT authentication.

Two of those three were already true and provable — HTTPS and JWT are in the
transport and the auth middleware. *"Retained only as long as operationally
necessary"* was a sentence with nothing behind it: no table declared a window,
nothing deleted anything, and no test could fail.

## Expiry is not deletion, and the codebase was clear about that

`agents/expiry_sweep.py` says so in its own docstring: it marks rows `expired`
and **keeps** them, *"because an expired row is the evidence that the surface
retires things on its own."* That is right, and it is a different promise from
minimisation. A flag that stopped being served eight weeks ago is still a row
saying where an incident was. A journey that ended last month is still a record
of where somebody went.

So this registry covers the second half: **after a row stops being useful, when
does it stop existing.**

## Why a registry and not a `WHERE created_at <` in a sweep

Because the failure mode is a table nobody classified. That is not hypothetical:
`PURGES` was written on 2026-10-15 against the live schema, and `journeys` --
which holds a per-user origin and destination, the exact thing §9 names -- was a
table **this repository has no code for**. It was applied by hand, carries no
committed migration, and had accumulated rows that afternoon. A sweep would have
been written against the tables its author remembered.

`tests/invariants/test_retention_is_declared.py` therefore asserts that **every
table in the live database appears here**, classified one way or the other. A new
table fails that test until somebody decides what it holds. That tripwire is the
point of the module; the windows are the easy part.

## `KEEP` is a decision, not an absence

A table listed as `KEEP` has been looked at and judged to need no window. Saying
so in the same structure as a window is deliberate: a reader can tell "indefinite
on purpose" from "nobody got to it", which a registry of only-the-expiring-tables
cannot express.

## Windows marked PROPOSED have not been signed off

Some windows follow from something already in the code and are marked DERIVED.
The rest are a judgement, and a retention period is a policy decision about
somebody else's data, so they are marked PROPOSED and `scripts/purge_expired.py`
refuses to delete under a PROPOSED window without `--force`. **Do not quietly
promote one to DERIVED to make the script run.**
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from enum import Enum
from typing import Final

__all__ = [
    "Basis",
    "Disposal",
    "PURGES",
    "Retention",
    "proposed_windows",
    "retention_for",
    "tables_with_windows",
]


class Disposal(Enum):
    """What happens when a row passes its window."""

    DELETE = "delete"
    """The row goes. Nothing downstream references it."""

    KEEP = "keep"
    """No window, by decision. The `why` field has to say why."""


class Basis(Enum):
    """How much authority a window carries."""

    DERIVED = "derived"
    """Follows from something already in the code, a constraint, or §9 itself."""

    PROPOSED = "proposed"
    """A judgement awaiting the owner's sign-off. The purge script will not act on it alone."""


@dataclass(frozen=True)
class Retention:
    """
    One table's rule.

    `dated_by` is the column the window is measured from, and it is named
    explicitly rather than defaulted to `created_at` because the right column
    differs: a journey should age from when it **ended**, not when it was created,
    or an abandoned `active` row would be purged while still live.
    """

    table: str
    holds: str
    disposal: Disposal
    why: str
    window: timedelta | None = None
    dated_by: str | None = None
    basis: Basis | None = None

    def __post_init__(self) -> None:
        if self.disposal is Disposal.DELETE:
            if self.window is None or self.dated_by is None or self.basis is None:
                raise ValueError(f"{self.table}: a DELETE rule needs window, dated_by and basis")
            if self.window <= timedelta(0):
                raise ValueError(f"{self.table}: window must be positive")
        elif self.window is not None:
            raise ValueError(f"{self.table}: a KEEP rule must not carry a window")


_DAY: Final = timedelta(days=1)


PURGES: Final[tuple[Retention, ...]] = (
    # ---------------------------------------------------------------- location
    #
    # §9's own subject. These are the rows the promise is actually about, so they
    # carry the shortest windows in the registry.
    Retention(
        table="user_locations",
        holds="A user's live position, one row per ping.",
        disposal=Disposal.DELETE,
        window=2 * _DAY,
        dated_by="timestamp",
        basis=Basis.DERIVED,
        why=(
            "Live tracking is the only consumer and it reads the newest row. A ping "
            "older than a couple of days serves no feature, which makes 'operationally "
            "necessary' in §9 a measurable claim rather than a sentiment. DERIVED "
            "because no code path reads a ping this old."
        ),
    ),
    Retention(
        table="journeys",
        holds="Per-user origin, destination and route history, plus Journey Guardian escalation state.",
        disposal=Disposal.DELETE,
        window=30 * _DAY,
        dated_by="ended_at",
        basis=Basis.PROPOSED,
        why=(
            "**The highest-risk table in the registry, and the one this repository "
            "knows least about.** Applied by hand as ledger version 20261014150000, no "
            "committed migration, no code in any branch -- `feature/journey-guardian` "
            "holds a design document only -- and it was accumulating rows on 15 Oct. "
            "Origin plus destination plus user_id plus timestamp is a movement history, "
            "which is precisely what §9 names. "
            "30 days is PROPOSED: B10's anomaly detection needs *some* history to call "
            "something anomalous, and nobody has said how much. Dated by `ended_at` so "
            "an abandoned `active` journey is never purged while it might still be live "
            "-- which also means a row that never ends never ages, and that is a gap "
            "for whoever finishes B10 to close."
        ),
    ),
    # ---------------------------------------------------------------- distress
    Retention(
        table="sos_incidents",
        holds="Location, trigger type and evidence references from a moment of distress.",
        disposal=Disposal.DELETE,
        window=180 * _DAY,
        dated_by="timestamp",
        basis=Basis.PROPOSED,
        why=(
            "Cuts both ways, which is why it is PROPOSED and long. An SOS record is "
            "evidence the user may need months later, possibly for a legal process; it "
            "is also the most sensitive row in the database. 180 days is a guess "
            "standing in for a decision nobody has made. **The stored video is the "
            "sharper question and is not addressed here** -- these rows hold references "
            "to Supabase Storage objects, and deleting the row without the object leaves "
            "the footage behind. Whoever signs this off should decide the object's fate "
            "in the same breath."
        ),
    ),
    # ---------------------------------------------------------------- reporting
    Retention(
        table="gd_drafts",
        holds="A user's own account of a crime, drafted for a General Diary filing, NID-linked.",
        disposal=Disposal.DELETE,
        window=90 * _DAY,
        dated_by="created_at",
        basis=Basis.PROPOSED,
        why=(
            "An unfiled draft is a narrative of a crime attached to a named person with "
            "no official process behind it yet. A filed one (`gd_filed_at` set) is a "
            "record of a real filing and arguably belongs with the user for longer. "
            "90 days is PROPOSED and the distinction between filed and unfiled is a "
            "second decision this rule does not yet make."
        ),
    ),
    # ---------------------------------------------------------------- operations
    Retention(
        table="agent_runs",
        holds="Agent telemetry -- counts, durations, errors. No personal data.",
        disposal=Disposal.DELETE,
        window=90 * _DAY,
        dated_by="created_at",
        basis=Basis.DERIVED,
        why=(
            "Not a privacy rule, a growth one: 3,879 rows on 15 Oct from one agent "
            "firing every minute, and nothing reads a run older than the last few days. "
            "DERIVED because no feature depends on an older row, and B9's observability "
            "should state its own horizon when it lands."
        ),
    ),
    Retention(
        table="raw_documents",
        holds="Fetched news article text. Public reporting, not personal data.",
        disposal=Disposal.DELETE,
        window=90 * _DAY,
        dated_by="fetched_at",
        basis=Basis.PROPOSED,
        why=(
            "Published journalism rather than anything about a user, so this is storage "
            "hygiene, not minimisation. PROPOSED because `content_hash` deduplication "
            "and the B6b provenance page both read history, and deleting a document "
            "whose extracted incident is still served would make that page lie. Check "
            "B6b before enabling this one."
        ),
    ),
    # ---------------------------------------------------------------- kept, on purpose
    #
    # There is no `users` rule, and that is the finished state of defect 9.
    # `public.users` was a mirror of auth.users + profiles that nothing
    # referenced; it was dropped by migration 20261015160000 on 2026-10-15.
    # Account identity lives in `auth.users`, which Supabase owns and this
    # registry does not cover, and display data lives in `profiles` below.
    #
    # Worth recording how this entry left: it was added as an explicitly
    # temporary KEEP, because while the table was live
    # `test_every_table_in_the_database_is_classified` required *some* decision
    # about it, and a retention window is the wrong instrument for a table that
    # should not exist at all -- the answer was a drop, not a sweep. Deleting it
    # was not a chore someone remembered; the moment the drop landed,
    # `test_the_registry_does_not_describe_tables_that_do_not_exist` failed with
    # `retention rules for tables that no longer exist: ['users']`. The two
    # tests handed the task over between them, which is the behaviour to copy
    # the next time a table is on its way out.
    Retention(
        table="profiles",
        holds="Account profile fields.",
        disposal=Disposal.KEEP,
        why="Lives and dies with the account. See `users`.",
    ),
    Retention(
        table="gd_profiles",
        holds="NID, parents' names, permanent and present address.",
        disposal=Disposal.KEEP,
        why=(
            "The most identifying row in the database, and a window would be the wrong "
            "instrument: the user enters this once so they do not have to retype it "
            "under stress, so expiring it silently breaks the feature it exists for. It "
            "belongs to account deletion, like `users`. **If anything here deserves a "
            "'delete my details' button of its own, it is this table.**"
        ),
    ),
    Retention(
        table="emergency_contacts",
        holds="Names and phone numbers of third parties.",
        disposal=Disposal.KEEP,
        why=(
            "**These people never consented to anything** -- the user entered them. That "
            "argues for a window and against one at the same time: the data is not the "
            "user's to keep indefinitely, and an SOS that finds no contact because a "
            "timer expired is the feature failing at the only moment it matters. Kept, "
            "deliberately, and flagged as the registry's least comfortable entry."
        ),
    ),
    Retention(
        table="sos_hot_words",
        holds="Phrases the user intends to shout in an emergency.",
        disposal=Disposal.KEEP,
        why="A setting, not an event. Lives with the account.",
    ),
    Retention(
        table="notification_preferences",
        holds="Alert settings: categories, minimum severity, quiet hours.",
        disposal=Disposal.KEEP,
        why=(
            "A setting the user chose, not an event that happened to them, so there is "
            "no moment at which it stops being current. Expiring it would silently "
            "restore defaults the user had deliberately changed -- and for quiet hours "
            "that means a phone alerting at night because a timer ran out."
        ),
    ),
    Retention(
        table="push_devices",
        holds="Device push tokens and last known coarse location.",
        disposal=Disposal.KEEP,
        why=(
            "`disabled_at` already retires a dead device, and **sign-out hard-deletes "
            "the row** -- `alerts/service.py::delete_device`, because the row holds a "
            "delivery address and the user has asked not to be contacted. That is a "
            "user-initiated erasure rather than a window, which is a different thing "
            "and is allowlisted in `tests/invariants/test_retention_is_declared.py`. "
            "⚠️ It carries `last_location_at`, so if device rows are ever retained "
            "after `disabled_at` this becomes a location table and needs a window."
        ),
    ),
    Retention(
        table="sent_alerts",
        holds="Which alert went to which device, for de-duplication.",
        disposal=Disposal.KEEP,
        why=(
            "The six-hour per-zone debounce reads it, so a window shorter than that "
            "breaks alert fatigue control. Empty on 15 Oct; revisit if it grows."
        ),
    ),
    Retention(
        table="crime_reports",
        holds="User-submitted reports: category, location, description.",
        disposal=Disposal.KEEP,
        why=(
            "The chronic risk layer is built from report history, so a window here "
            "deletes the surface rather than tidying it. The published *claim* already "
            "retires via cluster decay and `expiry_sweep`; the underlying report is the "
            "evidence for it."
        ),
    ),
    Retention(
        table="community_clusters",
        holds="Derived groupings of crime reports.",
        disposal=Disposal.KEEP,
        why=(
            "Derived, and already retired by `expiry_sweep` and `report_corroboration`. "
            "Deleting a cluster whose reports remain would just have it rebuilt."
        ),
    ),
    Retention(
        table="risk_flags",
        holds="Published incidents from news. No personal data.",
        disposal=Disposal.KEEP,
        why=(
            "Public reporting about places, not people, and `expiry_sweep` already stops "
            "serving them. An expired row is the evidence that retirement happens, which "
            "is that module's stated reason for keeping it."
        ),
    ),
    Retention(
        table="news_crime_incidents",
        holds="Attributed crime citations from news. No personal data -- attribution policy forbids naming anyone.",
        disposal=Disposal.KEEP,
        why=(
            "Same as `risk_flags`. Its five-day half-life takes it below the serve "
            "threshold in about eighteen days and `expiry_sweep` marks it then."
        ),
    ),
    Retention(
        table="extracted_incidents",
        holds="Model output per document, including `discarded_reason`.",
        disposal=Disposal.KEEP,
        why=(
            "The audit trail for what was read and what was refused -- the record that "
            "makes 'discarded, never guessed' checkable after the fact. Deleting it "
            "would remove the evidence for the project's central claim."
        ),
    ),
    Retention(
        table="extracted_crimes",
        holds="Model output per document for the crime surface, including what was refused.",
        disposal=Disposal.KEEP,
        why=(
            "The same audit role as `extracted_incidents`, and it matters more here: "
            "the crime surface makes attributed claims about places, so the record of "
            "which extractions were published and which were discarded is the evidence "
            "that the attribution policy was applied rather than merely written down."
        ),
    ),
    Retention(
        table="schema_migrations",
        holds="Applied migration ledger.",
        disposal=Disposal.KEEP,
        why="History. Deleting a row here would re-run a migration.",
    ),
)


def retention_for(table: str) -> Retention | None:
    """This table's rule, or None when it has not been classified."""
    for rule in PURGES:
        if rule.table == table:
            return rule
    return None


def tables_with_windows() -> tuple[Retention, ...]:
    """Only the rules that delete something."""
    return tuple(rule for rule in PURGES if rule.disposal is Disposal.DELETE)


def proposed_windows() -> tuple[Retention, ...]:
    """
    Windows still awaiting sign-off.

    `scripts/purge_expired.py` reports these and refuses to act on them without
    `--force`, so that a retention period nobody agreed to cannot delete somebody's
    data because a cron job existed.
    """
    return tuple(rule for rule in tables_with_windows() if rule.basis is Basis.PROPOSED)
