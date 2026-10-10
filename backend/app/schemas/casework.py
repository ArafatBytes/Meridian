"""
Request and response shapes for D08's General Diary endpoints. ADR 0007.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class GdProfile(BaseModel):
    """
    What the official DMP form asks for above the narrative.

    All optional on the way in so a half-finished profile can be saved, and
    `is_complete` says whether the printed form can actually be produced. The
    draft itself needs none of this — it can be generated, read, edited and
    approved without a profile; only printing needs the identity block.

    `full_name` and `phone` are here, and editable, rather than read off the
    login. A General Diary is signed by hand and the printed name has to match
    the signature, which is not something to derive from an email address.
    """

    full_name: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=40)
    gd_nid: str | None = Field(default=None, max_length=40)
    gd_father_name: str | None = Field(default=None, max_length=120)
    gd_mother_name: str | None = Field(default=None, max_length=120)
    gd_permanent_address: str | None = Field(default=None, max_length=400)
    gd_present_address: str | None = Field(default=None, max_length=400)


class GdProfileResponse(GdProfile):
    email: str | None = None
    is_complete: bool
    missing_fields: list[str]


class GdDraftResponse(BaseModel):
    id: str
    report_id: str
    state: str
    narrative_bn: str
    # sha256 of `narrative_bn`. The client sends it back to approve, which is
    # what makes approving a draft you have not loaded impossible.
    narrative_sha256: str
    summary_en: str
    missing_details: list[str]
    thana_name: str
    thana_district: str
    engine: str
    approved_at: datetime | None
    gd_number: str | None
    gd_filed_at: datetime | None
    created_at: datetime


class GdDraftEdit(BaseModel):
    """Editing is only possible while the draft is still a draft."""

    narrative_bn: str | None = Field(default=None, min_length=20, max_length=3000)
    thana_name: str | None = Field(default=None, max_length=200)
    thana_district: str | None = Field(default=None, max_length=120)


class GdApproval(BaseModel):
    """
    Approving names the exact text being approved.

    Not a formality: it is the whole gate. The client can only produce this
    hash from a narrative it has actually been given, and the server only
    accepts it if that is still what is stored — so a blind approve and an
    approve of a stale draft both fail, and neither needs the UI's cooperation.
    """

    narrative_sha256: str = Field(min_length=64, max_length=64)


class GdNumber(BaseModel):
    """What the duty officer wrote on the copy he handed back."""

    gd_number: str = Field(min_length=1, max_length=80)
