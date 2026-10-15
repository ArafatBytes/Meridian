"""
D08 — the General Diary: draft it, read it, approve it, and stop. ADR 0007.

    POST   /casework/reports/{report_id}/draft   generate (or regenerate)
    GET    /casework/reports/{report_id}/draft   fetch
    PATCH  /casework/drafts/{draft_id}           edit the narrative or the thana
    POST   /casework/drafts/{draft_id}/approve   draft -> ready_to_file
    POST   /casework/drafts/{draft_id}/gd-number record what the thana gave back
    GET    /casework/profile · PUT /casework/profile
    GET    /casework/thanas

**There is no submit endpoint, and there is not going to be one.** Bangladesh
Police has no API, a cognizable offence cannot be closed online in any case, and
filing requires a signature that only the complainant can give. The chain ends
here, with a document the user prints or pastes.

The state machine lives in this module and in the table's check constraints, not
in the app. A disabled button is a courtesy to the user; these are the rule.
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.casework.draft import draft_narrative
from app.casework.thana import all_thana_names, nearest_thana
from app.core.database import get_db
from app.core.security import get_current_user
from app.llm.client import FEATURE_GD, LLMUnavailable, chain
from app.models.crime import CrimeReport
from app.models.gd_draft import STATE_DRAFT, STATE_READY, GdDraft
from app.models.gd_profile import GdProfile as GdProfileRow
from app.schemas.casework import (
    GdApproval,
    GdDraftEdit,
    GdDraftResponse,
    GdNumber,
    GdProfile,
    GdProfileResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()

PROFILE_FIELDS = GdProfileRow.REQUIRED


def _digest(narrative: str) -> str:
    return hashlib.sha256(narrative.encode("utf-8")).hexdigest()


def _as_response(draft: GdDraft) -> GdDraftResponse:
    return GdDraftResponse(
        id=str(draft.id),
        report_id=str(draft.report_id),
        state=draft.state,
        narrative_bn=draft.narrative_bn,
        narrative_sha256=_digest(draft.narrative_bn),
        summary_en=draft.summary_en,
        missing_details=list(draft.missing_details or []),
        thana_name=draft.thana_name,
        thana_district=draft.thana_district,
        engine=draft.engine,
        approved_at=draft.approved_at,
        gd_number=draft.gd_number,
        gd_filed_at=draft.gd_filed_at,
        created_at=draft.created_at,
    )


async def _owned_draft(draft_id: str, user_id: str, db: AsyncSession) -> GdDraft:
    draft = (
        await db.execute(select(GdDraft).where(GdDraft.id == draft_id))
    ).scalar_one_or_none()
    if draft is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such draft")
    # 404 rather than 403 on someone else's draft: whether a given draft id
    # exists is not this caller's business either.
    if str(draft.user_id) != str(user_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such draft")
    return draft


# ---------------------------------------------------------------------------
# The profile
# ---------------------------------------------------------------------------

@router.get("/profile", response_model=GdProfileResponse)
async def get_gd_profile(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    What we hold for the identity block of the form. Nothing is inferred.

    A user who has never opened this screen has no row, and that is not an
    error — it is an empty profile with everything listed as missing. The
    earlier version returned 404 here, which took the whole General Diary
    screen down for anyone whose account predated the profile.
    """
    row = (
        await db.execute(
            select(GdProfileRow).where(GdProfileRow.user_id == current_user["user_id"])
        )
    ).scalar_one_or_none()

    values = {field: getattr(row, field, None) if row else None for field in PROFILE_FIELDS}
    missing = [field for field, value in values.items() if not (value or "").strip()]
    return GdProfileResponse(
        **values,
        email=current_user.get("email"),
        is_complete=not missing,
        missing_fields=missing,
    )


@router.put("/profile", response_model=GdProfileResponse)
async def put_gd_profile(
    profile: GdProfile,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Save the identity fields, creating the profile on first use.

    Nothing is validated against anything. An NID is not checked against the
    Election Commission — we have no access and no business checking — and a
    wrong one is the user's to correct, on a document they sign themselves.
    """
    user_id = current_user["user_id"]
    row = (
        await db.execute(select(GdProfileRow).where(GdProfileRow.user_id == user_id))
    ).scalar_one_or_none()
    if row is None:
        row = GdProfileRow(user_id=user_id)
        db.add(row)

    for field in PROFILE_FIELDS:
        value = getattr(profile, field, None)
        if value is not None:
            setattr(row, field, value.strip() or None)
    await db.commit()
    return await get_gd_profile(db=db, current_user=current_user)


# ---------------------------------------------------------------------------
# Drafting
# ---------------------------------------------------------------------------

@router.post("/reports/{report_id}/draft", response_model=GdDraftResponse)
async def generate_draft(
    report_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Write the General Diary narrative for one report.

    Regenerating replaces an existing draft **only while it is still a draft**.
    Once approved it is frozen: the user has read that exact text and said yes
    to it, and quietly swapping it would make the approval a lie.
    """
    user_id = current_user["user_id"]
    report = (
        await db.execute(select(CrimeReport).where(CrimeReport.id == report_id))
    ).scalar_one_or_none()
    if report is None or str(report.user_id) != str(user_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such report")

    existing = (
        await db.execute(select(GdDraft).where(GdDraft.report_id == report_id))
    ).scalar_one_or_none()
    if existing is not None and existing.state == STATE_READY:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This General Diary has been approved. Regenerating it would replace "
            "text that was already read and approved.",
        )

    try:
        latitude = float(report.latitude)
        longitude = float(report.longitude)
    except (TypeError, ValueError):
        latitude = longitude = None  # type: ignore[assignment]

    station = (
        nearest_thana(latitude, longitude)
        if latitude is not None and longitude is not None
        else None
    )

    try:
        result = await draft_narrative(
            category=getattr(report.category, "value", str(report.category)),
            title=report.title or "",
            description=report.description or "",
            incident_at=report.incident_date_time,
            location_name=report.location_name,
        )
    except LLMUnavailable as problem:
        # No template fallback on purpose. A form with the raw description
        # pasted into it would look like a drafted application while being
        # nothing of the kind, and the person signing it could not tell.
        logger.warning("GD drafting unavailable for report %s: %s", report_id, problem)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Could not draft the General Diary right now. Nothing was saved — "
            "try again when you have a connection.",
        ) from problem

    if existing is None:
        existing = GdDraft(report_id=report_id, user_id=user_id)
        db.add(existing)

    existing.narrative_bn = result.draft.narrative_bn
    existing.summary_en = result.draft.summary_en
    existing.missing_details = list(result.draft.missing_details)[:6]
    # An unknown thana is left blank rather than guessed. An application
    # addressed to the wrong officer-in-charge is worse than one addressed to
    # nobody yet, and the review screen makes the user pick.
    existing.thana_name = station.name if station else ""
    existing.thana_district = station.district if station else ""
    existing.engine = result.engine
    existing.state = STATE_DRAFT
    existing.approved_at = None

    await db.commit()
    await db.refresh(existing)
    return _as_response(existing)


@router.get("/reports/{report_id}/draft", response_model=GdDraftResponse)
async def get_draft_for_report(
    report_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    draft = (
        await db.execute(select(GdDraft).where(GdDraft.report_id == report_id))
    ).scalar_one_or_none()
    if draft is None or str(draft.user_id) != str(current_user["user_id"]):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No draft for this report")
    return _as_response(draft)


@router.patch("/drafts/{draft_id}", response_model=GdDraftResponse)
async def edit_draft(
    draft_id: str,
    edit: GdDraftEdit,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Change the narrative or the thana, while it is still a draft.

    The user's edit is final — we do not re-run the model over it, re-check it
    or improve it. They are the one signing it.
    """
    draft = await _owned_draft(draft_id, current_user["user_id"], db)
    if draft.state != STATE_DRAFT:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This General Diary has been approved and can no longer be edited.",
        )

    if edit.narrative_bn is not None:
        draft.narrative_bn = edit.narrative_bn
    if edit.thana_name is not None:
        draft.thana_name = edit.thana_name.strip()
    if edit.thana_district is not None:
        draft.thana_district = edit.thana_district.strip()

    await db.commit()
    await db.refresh(draft)
    return _as_response(draft)


@router.post("/drafts/{draft_id}/approve", response_model=GdDraftResponse)
async def approve_draft(
    draft_id: str,
    approval: GdApproval,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    `draft` -> `ready_to_file`. The only transition there is.

    The caller must name the exact text it is approving, by its sha256. That is
    the gate, and it is a gate rather than a checkbox because the hash can only
    be produced from a narrative the client was actually given, and is only
    accepted while that is still what is stored. Approving without reading and
    approving a stale draft both fail here, with no help from the UI.
    """
    draft = await _owned_draft(draft_id, current_user["user_id"], db)
    if draft.state == STATE_READY:
        return _as_response(draft)

    if approval.narrative_sha256.lower() != _digest(draft.narrative_bn):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This draft has changed since it was loaded. Read the current text "
            "and approve that.",
        )
    if not draft.thana_name.strip():
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Choose the police station before approving — the application is "
            "addressed to its officer-in-charge.",
        )

    draft.state = STATE_READY
    draft.approved_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(draft)
    logger.info("GD draft %s approved by %s", draft_id, current_user["user_id"])
    return _as_response(draft)


@router.post("/drafts/{draft_id}/gd-number", response_model=GdDraftResponse)
async def record_gd_number(
    draft_id: str,
    body: GdNumber,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Record the number the thana gave back.

    We did not file it and we have no way to check this — it is what the user
    tells us the duty officer wrote on their copy. Stored because it is the one
    thread that ties their report to a real police record, and because they
    will want it later.
    """
    draft = await _owned_draft(draft_id, current_user["user_id"], db)
    if draft.state != STATE_READY:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Approve the General Diary before recording a GD number — an "
            "unapproved draft was never taken anywhere.",
        )
    draft.gd_number = body.gd_number.strip()
    draft.gd_filed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(draft)
    return _as_response(draft)


# ---------------------------------------------------------------------------
# Supporting lookups
# ---------------------------------------------------------------------------

@router.get("/thanas", response_model=list[str])
async def list_thanas():
    """
    Every station name, for the review screen's picker.

    **Dhaka city only, 49 names** — defect 17. The CSV covers all 607 stations
    in Bangladesh; `thana.py` loads the 51 `district == "Dhaka"` rows (exactly
    the DMP thanas) and drops two exact duplicates. Five of them can be named
    here but are never ranked by `nearest_thana`, because the file marks their
    coordinates `legacy — unverified` and they land kilometres inside another
    thana's area.

    Both spellings of `Gandaria`/`Gendaria` and `Bhatara`/`Vatara` are present
    on purpose: this list is searched by the name the user knows.

    Names only. The CSV's email and phone columns hold one value repeated across
    every row and nothing in this feature reads them (DEMO_PLAN 7.2).
    """
    return list(all_thana_names())


@router.get("/status", response_model=dict)
async def casework_status():
    """What is configured, for a walkthrough to check before the demo."""
    return {
        "feature": "D08 — General Diary drafting",
        "chain": [f"{provider}:{model}" for provider, model in chain(FEATURE_GD)],
        "states": [STATE_DRAFT, STATE_READY],
        "submits_to_police": False,
        "why": (
            "Bangladesh Police has no public API, and a cognizable offence cannot "
            "be closed online in any case — the applicant must appear at the thana. "
            "Meridian drafts; a person files."
        ),
        "thanas_loaded": len(all_thana_names()),
    }
