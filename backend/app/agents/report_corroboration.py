"""
Report Corroboration — several strangers reporting one corner become one published
cluster; one person reporting it becomes nothing.

Defect 54 / B13 / S29. The gap this closes, in `IMPLEMENTATION_PLAN.md`'s words:

    `crime_reports` and `risk_flags` have no pipeline between them, so a user's own
    report never becomes a risk flag, never bends a route and never raises a zone
    alert — while the Map draws both as pins, which makes them look interchangeable.
    Deliberate (a single unverified report must not steer other people's routes) but
    a real gap. The bridge is Rumour Guard's existing logic applied to user reports:
    N independent reports, same area, same window.

That is what this is, with one correction the plan does not mention: the bridge
does **not** end in `risk_flags`. A risk flag is a mobility claim and a cluster of
reports is not one — see the header of
`migrations/versions/20261013120100__community_clusters.sql`. It ends in
`community_clusters`, which publishes a count and a recency and nothing else.

---

## Recomputed from scratch, every run

The obvious design is incremental: on each new report, find the cluster it belongs
to and increment it. This does the opposite — it rebuilds every live cluster in the
window from the reports that currently qualify, then reconciles that against the
table.

Three things fall out of that for free, and all three are correctness rather than
tidiness:

1. **Withdrawal works.** A report its author retracts stops counting on the next
   run, and a cluster that drops below the threshold retires itself. An incremental
   design would need a decrement path, and a decrement path that is ever skipped
   leaves a published claim standing on evidence that no longer exists.
2. **Removal works**, by the same mechanism and with no extra code. The human
   demote lever is a `status` write on one report.
3. **It is idempotent.** Running it twice changes nothing, so it is safe to trigger
   by hand mid-demo, and a run that dies halfway leaves no partial cluster.

It is affordable because the input is small: a fortnight of reports for one city,
read once. If this ever needs to be incremental, the thing to change first is the
candidate query's window, not the shape.

## How reports are grouped

Agglomerative, greedy, and conservative in the same direction Rumour Guard is: it
would rather leave two clusters than invent one.

For each family (`app/policy/community.py::ReportFamily`), reports are taken oldest
first and each either joins the first existing group whose **centroid** is within
`CLUSTER_RADIUS_M` or starts its own. Comparing against the centroid rather than
against any member is what stops a chain of reports 199 m apart from growing into a
cluster a kilometre across — the failure mode of single-link clustering, and the
thing that would turn "this corner" into "this neighbourhood".

Oldest-first makes the grouping deterministic: the same reports always produce the
same clusters, which is what lets the reconcile step below compare runs.

There is **no embedding step**. Rumour Guard needs one because two outlets write
about one fire in different words and the question is whether they mean the same
event. Here the question is different: three muggings on one corner in one week are
not one event and must not be merged into one — they are the pattern, and the
pattern is the thing being published. Comparing their prose would be answering a
question nobody asked, and it would quietly drop the second report of a genuinely
repeated incident.

## What it refuses to do

* **It never writes `risk_flags`.** Pinned by
  `tests/invariants/test_reports_never_write_risk_flags.py`.
* **It never publishes a single reporter.** Pinned in three places, as the
  single-source rule is: `policy/community.status_for`, the
  `community_clusters_needs_two_reporters` CHECK, and an invariant test.
* **It never reads a report's narrative.** The candidate query selects no title,
  description or photo path. A cluster that cannot see the text cannot leak it, and
  `reports` stores a per-cluster pseudonym rather than a user id.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Final

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts.agents import AgentContext, AgentResult, BaseAgent
from app.policy.community import (
    CLUSTER_HALF_LIFE_HOURS,
    CLUSTER_RADIUS_M,
    CLUSTER_WINDOW,
    ClusterStatus,
    ReportFamily,
    eligible_reporters,
    family_for_category,
    independent_reporters,
    severity_for,
    status_for,
    to_cluster_statement,
)
from app.scoring.geometry import haversine_m

logger = logging.getLogger(__name__)

__all__ = ["AGENT", "Candidate", "ReportCorroborationAgent", "group_by_proximity"]


_PSEUDONYM_DOMAIN: Final[bytes] = b"meridian/community-cluster/reporter-ref/v1"
"""
Domain separation for the reporter pseudonym.

The HMAC key is this string plus the cluster key, over `JWT_SECRET_KEY`. Reusing
the signing secret for a second purpose is only safe when the two uses cannot be
confused for each other, which is what a domain-separation constant buys: no input
to this function can produce a value that is also a valid token signature.

A dedicated secret would be marginally cleaner and would mean another variable to
keep in step across machines, which this project has already paid for once.
"""


@dataclass(frozen=True)
class Candidate:
    """
    One report, reduced to the fields corroboration is allowed to see.

    Note what is absent: title, description, category (only its family survives),
    evidence photo, location name. The candidate query does not select them.
    """

    report_id: uuid.UUID
    user_id: str
    family: ReportFamily
    lat: float
    lon: float
    incident_at: datetime


@dataclass
class Group:
    """A provisional cluster, mid-computation. Not the stored shape."""

    family: ReportFamily
    members: list[Candidate] = field(default_factory=list)

    @property
    def lat(self) -> float:
        return sum(m.lat for m in self.members) / len(self.members)

    @property
    def lon(self) -> float:
        return sum(m.lon for m in self.members) / len(self.members)

    @property
    def reporter_count(self) -> int:
        return len(independent_reporters(m.user_id for m in self.members))

    @property
    def observed_at(self) -> datetime:
        return max(m.incident_at for m in self.members)

    @property
    def first_report_at(self) -> datetime:
        return min(m.incident_at for m in self.members)


# ---------------------------------------------------------------------------
# Candidates
# ---------------------------------------------------------------------------
# Account age comes from `auth.users.created_at` rather than `public.profiles`:
# the profile row is written by the client on registration and may be missing,
# while the auth row is the account. `eligible_reporters` refuses a report whose
# account age cannot be established, so reading the nullable one would silently
# discard reports instead of gating them.
#
# `status` is selected rather than filtered in SQL so that the gate lives in one
# readable place in `policy/community.py` instead of being half here and half
# there. The window is filtered in SQL, because that is the part that would
# otherwise read the whole table.
_CANDIDATES: Final = text(
    """
    select r.id                 as report_id,
           r.user_id::text      as user_id,
           r.category::text     as category,
           r.status             as status,
           r.latitude           as latitude,
           r.longitude          as longitude,
           r.incident_date_time as incident_date_time,
           u.created_at         as account_created_at
      from public.crime_reports r
      join auth.users u on u.id = r.user_id
     where r.incident_date_time >= :since
     order by r.incident_date_time asc
    """
)

_EXISTING_CLUSTERS: Final = text(
    """
    select cluster_id,
           cluster_key,
           family,
           status,
           corroborated_at,
           observed_at,
           extensions.ST_Y(location::extensions.geometry) as lat,
           extensions.ST_X(location::extensions.geometry) as lon
      from public.community_clusters
    """
)
# Every cluster, not just the live ones, and the two terminal states are the
# reason:
#
# * `removed` is the only human lever in this design. A run that could not see a
#   removed cluster would create a fresh one at the same corner within the hour and
#   quietly undo the takedown. Matching it and declining to publish is what makes
#   the lever hold.
# * `expired` must not be resurrected at full strength. A cluster's decay can run
#   out (~10 days past its newest report) while reports are still inside the
#   14-day candidate window, so an agent that only looked at live rows would
#   re-insert the same pattern with a new identity, a new `corroborated_at` and a
#   severity of 50 — a faded claim popping back to full brightness on a timer.
#   It is refreshed only when a report arrived *after* it expired, which is the one
#   case where something genuinely new has happened on that corner.

_INSERT: Final = text(
    """
    insert into public.community_clusters (
        cluster_key, family, status, location, radius_m,
        report_count, reporter_count, reports,
        severity_0, half_life_hours,
        observed_at, first_report_at,
        statement, corroborated_at
    ) values (
        :cluster_key, :family, :status,
        extensions.ST_SetSRID(extensions.ST_MakePoint(:lon, :lat), 4326)::extensions.geography,
        :radius_m,
        :report_count, :reporter_count, cast(:reports as jsonb),
        :severity_0, :half_life_hours,
        :observed_at, :first_report_at,
        :statement, :corroborated_at
    )
    """
)
# `expires_at` is NOT in the column list, although it is `not null`. The BEFORE
# trigger fills it, and a BEFORE trigger runs ahead of the constraint check -- so
# omitting it is both legal and the honest way to write a derived column: there is
# no value here for a reader to wonder about. Same as `_INSERT_FLAG` in live_risk.py,
# and the reason there is no Python copy of the formula.

_UPDATE: Final = text(
    """
    update public.community_clusters
       set family          = :family,
           status          = :status,
           location        = extensions.ST_SetSRID(
                                 extensions.ST_MakePoint(:lon, :lat), 4326
                             )::extensions.geography,
           radius_m        = :radius_m,
           report_count    = :report_count,
           reporter_count  = :reporter_count,
           reports         = cast(:reports as jsonb),
           severity_0      = :severity_0,
           half_life_hours = :half_life_hours,
           observed_at     = :observed_at,
           first_report_at = :first_report_at,
           statement       = :statement,
           corroborated_at = :corroborated_at
     where cluster_id = :cluster_id
    """
)

_RETIRE: Final = text(
    """
    update public.community_clusters
       set status = 'expired'
     where cluster_id = any(:cluster_ids)
       and status in ('provisional', 'corroborated')
    """
)
# The status guard is belt and braces: `stale` is built only from live rows, and
# this makes a bug there unable to rewrite a `removed` cluster into `expired`,
# which would launder a takedown into an ordinary expiry.


def group_by_proximity(candidates: list[Candidate]) -> list[Group]:
    """
    Reports into groups: same family, centroid within `CLUSTER_RADIUS_M`.

    Greedy and centroid-linked. See the module docstring for why centroid rather
    than nearest-member: single-link growth would let a chain of reports each 199 m
    from the last become one cluster spanning a kilometre, and a cluster that wide
    is the area label the concept document forbids.

    Pure, and takes its input as a list, so the clustering can be tested with no
    database at all — which is most of what
    `tests/invariants/test_report_corroboration.py` does.
    """
    groups: list[Group] = []
    for candidate in candidates:
        for group in groups:
            if group.family is not candidate.family:
                continue
            if haversine_m(group.lat, group.lon, candidate.lat, candidate.lon) <= CLUSTER_RADIUS_M:
                group.members.append(candidate)
                break
        else:
            groups.append(Group(family=candidate.family, members=[candidate]))
    return groups


def _reporter_ref(cluster_key: str, user_id: str) -> str:
    """
    A per-cluster pseudonym for a report's author.

    Keyed HMAC rather than a plain hash, and keyed *per cluster* rather than
    globally: the agent needs to answer "was this the same person as that one,
    inside this cluster", and nothing more. A global pseudonym would let anyone with
    the table join a person's reports across the city, which is a worse privacy
    surface than the reports it was derived from.

    Truncated to 32 hex characters. This is a membership tag, not a signature —
    128 bits is far past what a collision would need to matter here, and the column
    caps at 64.

    `settings` is imported here rather than at module scope, which is the lesson
    `app/scoring/factory.py` records: `Settings` has required fields with no
    defaults, so importing it needs a discoverable `.env`, and the registry imports
    every agent module to discover it. At module scope this one function's need for
    a secret would make the clustering logic unimportable without credentials it
    does not use — and that logic is most of what the tests exercise.
    """
    from app.core.config import settings

    key = _PSEUDONYM_DOMAIN + cluster_key.encode() + settings.JWT_SECRET_KEY.encode()
    return hmac.new(key, user_id.encode(), hashlib.sha256).hexdigest()[:32]


def _rows_to_candidates(rows: list[Any]) -> list[Candidate]:
    """
    Database rows to candidates, after the eligibility gates.

    The gates are `policy.community.eligible_reporters`: filed only, account older
    than the incident by `MIN_ACCOUNT_AGE_HOURS`, one report per account. They are
    applied here, over the whole window, rather than per group — an account that
    reported twice on one corner should count once, and which of the two reports
    survives must not depend on how the groups happened to form.

    `latitude` and `longitude` are `varchar` in this schema (a latent bug logged for
    S07, not this sprint's to fix), so a row whose coordinates do not parse is
    dropped rather than crashing the run.
    """
    prepared: list[dict[str, object]] = []
    for row in rows:
        try:
            lat = float(row.latitude)
            lon = float(row.longitude)
        except (TypeError, ValueError):
            logger.warning("report %s has unparseable coordinates; skipped", row.report_id)
            continue
        if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
            logger.warning("report %s has out-of-range coordinates; skipped", row.report_id)
            continue

        incident = row.incident_date_time
        created = row.account_created_at
        # `crime_reports.incident_date_time` is `timestamp` without a zone (S07
        # again), so it arrives naive. Read as UTC, matching how every other edge
        # of this system reads a naive instant -- and it has to be made aware
        # before being compared with `auth.users.created_at`, which is not.
        if incident is not None and incident.tzinfo is None:
            incident = incident.replace(tzinfo=UTC)
        if created is not None and created.tzinfo is None:
            created = created.replace(tzinfo=UTC)

        prepared.append(
            {
                "report_id": row.report_id,
                "user_id": row.user_id,
                "category": row.category,
                "status": row.status,
                "lat": lat,
                "lon": lon,
                "incident_date_time": incident,
                "account_created_at": created,
            }
        )

    eligible = eligible_reporters(prepared)
    return [
        Candidate(
            report_id=(
                r["report_id"]
                if isinstance(r["report_id"], uuid.UUID)
                else uuid.UUID(str(r["report_id"]))
            ),
            user_id=str(r["user_id"]),
            family=family_for_category(str(r["category"])),
            lat=float(r["lat"]),  # type: ignore[arg-type]
            lon=float(r["lon"]),  # type: ignore[arg-type]
            incident_at=r["incident_date_time"],  # type: ignore[arg-type]
        )
        for r in eligible
    ]


def _publishable(groups: list[Group]) -> list[Group]:
    """The groups that earn a status at all. Everything else is simply not written."""
    return [group for group in groups if status_for(group.reporter_count) is not None]


class ReportCorroborationAgent(BaseAgent):
    """
    Rebuilds `community_clusters` from the reports currently eligible.

    Hourly. Reports arrive at human speed and a cluster is a statement about a
    fortnight, so there is nothing to gain from running it more often — and the run
    reads every report in the window, which is work worth doing sixty times less
    frequently than the ingestion agents.
    """

    name = "report_corroboration"
    cron = "17 * * * *"

    async def run(self, ctx: AgentContext) -> AgentResult:
        if ctx.db is None:
            raise RuntimeError("report_corroboration needs ctx.db; the runner provides it")

        db: AsyncSession = ctx.db
        errors: list[str] = []
        since = ctx.now - CLUSTER_WINDOW

        rows = list((await db.execute(_CANDIDATES, {"since": since})).all())
        candidates = _rows_to_candidates(rows)
        groups = _publishable(group_by_proximity(candidates))

        existing = list((await db.execute(_EXISTING_CLUSTERS)).all())

        matched: set[Any] = set()
        written = 0
        suppressed = 0

        for group in groups:
            status = status_for(group.reporter_count)
            if status is None:  # pragma: no cover - _publishable already filtered
                continue

            row = _match_existing(group, existing, matched)

            if row is not None and row.status == ClusterStatus.REMOVED:
                # A human took this down. Nothing the reports do brings it back;
                # only clearing the row does, which is a deliberate act by whoever
                # removed it. See `_EXISTING_CLUSTERS`.
                suppressed += 1
                continue

            if row is not None and row.status == ClusterStatus.EXPIRED:
                previous = row.observed_at
                if previous is not None and previous.tzinfo is None:
                    previous = previous.replace(tzinfo=UTC)
                if previous is not None and group.observed_at <= previous:
                    # Faded, and nothing new has been reported since. Leave it
                    # faded rather than re-publishing the same evidence.
                    suppressed += 1
                    continue

            cluster_key = row.cluster_key if row is not None else f"reports-{uuid.uuid4()}"

            # Corroboration time is set once and then preserved. A cluster that
            # reached three reporters at 14:31 and picks up a fourth at 16:02 was
            # still corroborated at 14:31 -- the same rule Rumour Guard applies to
            # `confirmed_at`, and for the same reason: it is a claim about when we
            # decided to believe something.
            corroborated_at: datetime | None = None
            if status is ClusterStatus.CORROBORATED:
                prior = row.corroborated_at if row is not None else None
                corroborated_at = prior or ctx.now

            params = {
                "cluster_key": cluster_key,
                "family": str(group.family),
                "status": str(status),
                "lat": group.lat,
                "lon": group.lon,
                "radius_m": CLUSTER_RADIUS_M,
                "report_count": len(group.members),
                "reporter_count": group.reporter_count,
                "reports": json.dumps(
                    [
                        {
                            "report_id": str(member.report_id),
                            "reporter_ref": _reporter_ref(cluster_key, member.user_id),
                            "incident_at": member.incident_at.isoformat(),
                        }
                        for member in group.members
                    ]
                ),
                "severity_0": severity_for(group.reporter_count),
                "half_life_hours": CLUSTER_HALF_LIFE_HOURS,
                "observed_at": group.observed_at,
                "first_report_at": group.first_report_at,
                "statement": to_cluster_statement(
                    reporter_count=group.reporter_count,
                    radius_m=CLUSTER_RADIUS_M,
                    span=group.observed_at - group.first_report_at,
                ),
                "corroborated_at": corroborated_at,
            }

            if ctx.dry_run:
                written += 1
                continue

            try:
                if row is None:
                    await db.execute(_INSERT, params)
                else:
                    await db.execute(_UPDATE, {**params, "cluster_id": row.cluster_id})
                written += 1
            except Exception as exc:  # noqa: BLE001 - one bad cluster must not lose the run
                errors.append(f"{cluster_key}: {exc}")
                logger.exception("failed to write cluster %s", cluster_key)

        # Anything live that no longer has evidence behind it. This is where a
        # withdrawal, a removal of a contributing report and an aged-out pattern
        # all land, and the reason none of them needs code of its own.
        #
        # Live rows only: an already-expired row is not retired twice, and a
        # `removed` row is never touched by this agent at all.
        stale = [
            row.cluster_id
            for row in existing
            if row.cluster_id not in matched
            and row.status in (ClusterStatus.PROVISIONAL, ClusterStatus.CORROBORATED)
        ]
        if stale and not ctx.dry_run:
            await db.execute(_RETIRE, {"cluster_ids": stale})

        if ctx.dry_run:
            await db.rollback()
        else:
            await db.commit()

        logger.info(
            "report_corroboration: %d candidate(s) -> %d cluster(s), "
            "%d retired, %d suppressed%s",
            len(candidates),
            written,
            len(stale),
            suppressed,
            " (dry run)" if ctx.dry_run else "",
        )

        return AgentResult(
            agent=self.name,
            run_id=ctx.run_id,
            started_at=ctx.now,
            finished_at=datetime.now(UTC),
            status="partial" if errors else "ok",
            items_in=len(candidates),
            items_out=written,
            errors=errors,
            metrics={
                "reports_in_window": float(len(rows)),
                "eligible_reports": float(len(candidates)),
                "clusters_published": float(written),
                "clusters_retired": float(len(stale)),
                # Groups that met the threshold and were deliberately not
                # published: a takedown holding, or a faded cluster with no new
                # evidence. Worth a metric because a rising number here is how a
                # removal that should have been a report-level fix shows up.
                "clusters_suppressed": float(suppressed),
            },
        )


_MATCH_PRECEDENCE: Final[dict[str, int]] = {
    # A takedown outranks everything: if a removed cluster covers this group, that
    # is the row the caller must see, whatever else is nearby.
    ClusterStatus.REMOVED: 0,
    ClusterStatus.PROVISIONAL: 1,
    ClusterStatus.CORROBORATED: 1,
    ClusterStatus.EXPIRED: 2,
}


def _match_existing(group: Group, existing: list[Any], matched: set[Any]) -> Any | None:
    """
    The stored cluster this group is a recomputation of, or None.

    Same family, centroid within `CLUSTER_RADIUS_M`, not already claimed by another
    group this run. Matching is what keeps a cluster's identity -- and therefore its
    `corroborated_at` and any takedown applied to it -- stable across runs as
    reports come and go.

    Candidates are considered in `_MATCH_PRECEDENCE` order rather than table order,
    so a `removed` row always wins over a live one covering the same ground. Within
    a precedence band the nearest centroid wins, which keeps the choice independent
    of how the database happened to return the rows -- a run has to be reproducible
    to be worth reconciling against.

    `matched` is mutated on a hit. Two groups must never both update one row: the
    second would silently overwrite the first and one of the two patterns would
    vanish, which is the over-merging failure in a different costume.
    """
    candidates: list[tuple[int, float, Any]] = []
    for row in existing:
        if row.cluster_id in matched:
            continue
        if row.family != str(group.family):
            continue
        distance = haversine_m(float(row.lat), float(row.lon), group.lat, group.lon)
        if distance > CLUSTER_RADIUS_M:
            continue
        candidates.append((_MATCH_PRECEDENCE.get(row.status, 3), distance, row))

    if not candidates:
        return None

    candidates.sort(key=lambda entry: (entry[0], entry[1]))
    row = candidates[0][2]
    matched.add(row.cluster_id)
    return row


AGENT = ReportCorroborationAgent()
