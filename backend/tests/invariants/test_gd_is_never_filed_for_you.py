"""
D08's invariants. ADR 0007.

The claim this file defends is one sentence: **Meridian drafts a General Diary;
a person reads it, approves it, signs it and files it.** Everything below is a
way that claim could quietly stop being true —

  * a submit path appearing,
  * a third state appearing,
  * approval becoming possible without reading,
  * the drafting prompt learning to invent,
  * the thana lookup becoming confident about a coordinate it should refuse,
  * `police_stations.csv`'s placeholder contacts reaching a user.

A GD application is signed by the person who files it, and a false complaint is
punishable. These tests are the difference between a tool that helps someone
write that document and a tool that writes it for them without their knowing.
"""
from __future__ import annotations

import inspect
import re
from pathlib import Path

import pytest

from app.api.v1.endpoints import casework
from app.casework import draft as draft_module
from app.casework import thana as thana_module
from app.llm.models import GdDraft as GdDraftOutput
from app.models.gd_draft import STATE_DRAFT, STATE_READY, GdDraft

BACKEND = Path(__file__).resolve().parents[2]
MIGRATION = (
    BACKEND / "migrations" / "versions" / "20261010120000__gd_drafts_and_profile.sql"
)
CASEWORK_SOURCE = Path(casework.__file__).read_text(encoding="utf-8")
DRAFT_SOURCE = Path(draft_module.__file__).read_text(encoding="utf-8")
THANA_SOURCE = Path(thana_module.__file__).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# We do not file anything
# ---------------------------------------------------------------------------

def test_there_is_no_state_beyond_ready_to_file():
    """
    Two states. A third would be a claim we cannot support: we are not told
    when a GD is filed, accepted, investigated or rejected.
    """
    assert STATE_DRAFT == "draft"
    assert STATE_READY == "ready_to_file"
    states = set(re.findall(r"state\s*(?:in|=)\s*\(?'([a-z_]+)'", MIGRATION.read_text(encoding="utf-8")))
    assert states <= {STATE_DRAFT, STATE_READY}, f"unexpected state in the schema: {states}"


def test_no_endpoint_submits_to_the_police():
    """
    No route may look like it hands the document to anyone. The nearest thing
    allowed is recording a number the user types in afterwards.
    """
    forbidden = {"submit", "file", "send", "lodge", "transmit", "dispatch"}
    for route in casework.router.routes:
        path = getattr(route, "path", "")
        # Segment by segment, so `/profile` is not read as "file".
        segments = {segment.strip("{}").lower() for segment in path.split("/") if segment}
        offending = segments & forbidden
        assert not offending, f"{path} looks like a submission route ({offending})"


def test_recording_a_gd_number_requires_an_approved_draft():
    source = inspect.getsource(casework.record_gd_number)
    assert "STATE_READY" in source
    assert "409" in source or "HTTP_409_CONFLICT" in source


def test_the_database_enforces_the_state_machine_not_just_the_api():
    """
    The API is one writer. The constraints hold for every other writer too,
    including an endpoint nobody has written yet.
    """
    schema = MIGRATION.read_text(encoding="utf-8")
    assert "gd_drafts_state_known" in schema
    assert "gd_drafts_approved_iff_ready" in schema
    assert "gd_drafts_number_needs_approval" in schema


# ---------------------------------------------------------------------------
# Approving means having read it
# ---------------------------------------------------------------------------

def test_approval_requires_the_hash_of_the_text_being_approved():
    """
    The gate is not the disabled button; it is this. A client can only produce
    this hash from a narrative the server actually sent, and it is only accepted
    while that is still the stored text — so approving unread and approving
    stale both fail server-side.
    """
    source = inspect.getsource(casework.approve_draft)
    assert "narrative_sha256" in source
    assert "_digest(draft.narrative_bn)" in source


def test_approval_refuses_a_draft_with_no_thana():
    source = inspect.getsource(casework.approve_draft)
    assert "thana_name" in source


def test_an_approved_draft_cannot_be_edited_or_regenerated():
    for handler in (casework.edit_draft, casework.generate_draft):
        source = inspect.getsource(handler)
        # Either direction is fine: refuse when it is approved, or require that
        # it is still a draft. Both are the same gate.
        assert "STATE_READY" in source or "STATE_DRAFT" in source, (
            f"{handler.__name__} does not check the state before writing"
        )
        assert "409" in source or "HTTP_409_CONFLICT" in source


def test_digest_is_sha256_of_the_narrative():
    assert casework._digest("x") == (
        "2d711642b726b04401627ca9fbac32f5c8530fb1903cc4db02258717921a4881"
    )


# ---------------------------------------------------------------------------
# The draft states only what the complainant said
# ---------------------------------------------------------------------------

def test_the_prompt_forbids_inventing_a_detail():
    assert "never add a detail" in draft_module.SYSTEM.lower()
    assert "never guess" in draft_module.SYSTEM.lower()


def test_the_prompt_forbids_naming_an_offence():
    """
    Which offence was committed is the officer's decision. A GD that names a
    section of law is a GD arguing its own case.
    """
    assert "section of law" in draft_module.SYSTEM
    assert "officer's decision" in draft_module.SYSTEM


def test_the_prompt_pins_dates_and_numbers():
    """Round one of the bake-off moved a year. This is the line that stopped it."""
    assert "Copy every date, time, number and name exactly as given" in draft_module.SYSTEM
    assert "Never shift a year" in draft_module.SYSTEM


def test_the_prompt_does_not_repeat_the_line_the_form_prints():
    assert "আমি এই মর্মে জানাচ্ছি যে" in draft_module.SYSTEM
    assert "must never appear" in draft_module.SYSTEM


def test_nothing_from_the_vision_pipeline_reaches_the_prompt():
    """
    D07 proposes a category from photo cues; a person confirms it. The confirmed
    category may select wording. The cue answers may not become sentences in a
    document someone signs.
    """
    for forbidden in (
        "CrimeCues",
        "vision_analysis",
        "proposed_category",
        "cues_fired",
        "app.vision",
    ):
        assert forbidden not in DRAFT_SOURCE, f"{forbidden} reaches the GD prompt"
        assert forbidden not in CASEWORK_SOURCE, f"{forbidden} reaches the GD endpoint"


def test_the_identity_fields_are_never_sent_to_a_model():
    """
    The NID and the parents' names are stamped onto the form by the renderer.
    There is no reason for a free-tier API to see them.
    """
    for field in ("gd_nid", "gd_father_name", "gd_mother_name", "gd_permanent_address"):
        assert field not in DRAFT_SOURCE


def test_there_is_no_template_fallback_when_every_tier_fails():
    """
    A form with the raw description pasted in would look like a drafted
    application while being nothing of the kind, and the person signing could
    not tell. An error they can see is the honest failure.
    """
    source = inspect.getsource(casework.generate_draft)
    assert "LLMUnavailable" in source
    assert "503" in source or "HTTP_503_SERVICE_UNAVAILABLE" in source


def test_the_output_model_has_no_field_for_a_conclusion_of_ours():
    """Three fields: the narrative, a gloss to check it by, and what is missing."""
    assert set(GdDraftOutput.model_fields) == {
        "narrative_bn",
        "summary_en",
        "missing_details",
    }


# ---------------------------------------------------------------------------
# The thana is proposed, never asserted
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "latitude, longitude",
    [
        (0.0, 0.0),            # a failed GPS fix
        (90.4125, 23.8103),    # lat and lon swapped
        (51.5074, -0.1278),    # London
        (23.8103, 120.0),      # right latitude, wrong country
    ],
)
def test_a_coordinate_outside_bangladesh_names_no_thana(latitude, longitude):
    """
    None means "we do not know", and the review screen then makes the user
    choose. An application addressed to the wrong officer-in-charge is worse
    than one addressed to nobody yet.
    """
    assert thana_module.nearest_thana(latitude, longitude) is None


def test_a_dhaka_coordinate_names_a_dhaka_thana():
    station = thana_module.nearest_thana(23.7465, 90.3760)  # Dhanmondi 27
    assert station is not None
    assert station.district == "Dhaka"
    assert station.distance_km < 3.0


def test_the_thana_lookup_never_reads_the_placeholder_contacts():
    """
    `police_stations.csv` carries one email and one phone repeated across every
    row. Showing either beside a crime report would be worse than showing
    nothing (DEMO_PLAN 7.2).
    """
    assert "email" not in THANA_SOURCE.split('"""')[-1]
    assert "phone" not in THANA_SOURCE.split('"""')[-1]
    assert not hasattr(thana_module.Thana, "email")
    assert set(thana_module.Thana.__slots__) == {"name", "district", "distance_km"}


def test_nothing_in_the_casework_api_exposes_a_station_contact():
    """
    The user's own email and phone are theirs and appear on their own form.
    A *station's* contact must not reach any response, so the draft response
    carries the thana's name and district and nothing else about it.
    """
    from app.schemas.casework import GdDraftResponse

    thana_fields = {
        name for name in GdDraftResponse.model_fields if name.startswith("thana")
    }
    assert thana_fields == {"thana_name", "thana_district"}
    for leaked in ("thana_email", "thana_phone", "station_email", "station_phone"):
        assert leaked not in CASEWORK_SOURCE


# ---------------------------------------------------------------------------
# The model stays consistent with the schema
# ---------------------------------------------------------------------------

def test_the_orm_model_has_no_filed_column():
    columns = {column.name for column in GdDraft.__table__.columns}
    assert "filed" not in columns
    assert "submitted_at" not in columns
    # What we do keep is what the user told us.
    assert {"gd_number", "gd_filed_at"} <= columns


# ---------------------------------------------------------------------------
# Identifiers are copied by code, because models cannot copy them
# ---------------------------------------------------------------------------
# Measured 2026-10-10: asked to carry IMEI 352099001761481 into the narrative,
# Gemini produced 35209900171481, 35099001761481 and 3352099001761481 across
# five attempts. Prompting did not fix it. A wrong IMEI is a stolen phone that
# can never be traced, so the substitution happens in code.

SOURCE = "Samsung A54, IMEI 352099001761481. My number is 01712345678."
IMEI = "352099001761481"


@pytest.mark.parametrize(
    "written, label",
    [
        ("IMEI ৩৫০৯৯০০১৭৬১৪৮১ নম্বর", "a digit dropped, in Bangla numerals"),
        ("IMEI 35099001761481 নম্বর", "a digit dropped, in Latin digits"),
        ("IMEI 3352099001761481 নম্বর", "a digit added at the front"),
        ("IMEI 35209900171481 নম্বর", "a digit dropped from the middle"),
    ],
)
def test_a_mangled_identifier_is_replaced_with_the_complainants_own(written, label):
    repaired, notes = draft_module._repair_identifiers(SOURCE, written)
    assert IMEI in repaired, label
    assert notes == []


def test_an_extra_leading_digit_is_not_read_as_correct():
    """
    The substring trap: 3352099001761481 contains 352099001761481. Comparing
    whole digit runs is what catches it, and this test is here because the
    first implementation did not.
    """
    repaired, _ = draft_module._repair_identifiers(SOURCE, "IMEI 3352099001761481")
    assert "3352099001761481" not in repaired
    assert IMEI in repaired


def test_a_correct_identifier_is_left_exactly_alone():
    narrative = f"আমার ফোনের IMEI {IMEI} এবং রং কালো।"
    repaired, notes = draft_module._repair_identifiers(SOURCE, narrative)
    assert repaired == narrative
    assert notes == []


def test_an_omitted_identifier_is_not_warned_about():
    """
    A number the model left out is an omission the user can see. Warning about
    a number that is not on the page is noise, and noise in a review screen is
    how a real warning gets ignored.
    """
    narrative = "আমার মোবাইল ফোনটি ছিনতাই হয়েছে।"
    repaired, notes = draft_module._repair_identifiers(SOURCE, narrative)
    assert repaired == narrative
    assert notes == []


def test_several_identifiers_are_each_restored():
    narrative = "IMEI 35099001761481 এবং মোবাইল 01712345679"
    repaired, _ = draft_module._repair_identifiers(SOURCE, narrative)
    assert IMEI in repaired
    assert "01712345678" in repaired


def test_short_numbers_are_left_to_the_model():
    """
    A house number or a road number is not an identifier, and rewriting one
    would be this function inventing a fact rather than preserving one.
    """
    source = "I live at house 12, road 4."
    narrative = "আমি ১২ নম্বর বাড়ি, ৪ নম্বর রোডে থাকি।"
    repaired, notes = draft_module._repair_identifiers(source, narrative)
    assert repaired == narrative
    assert notes == []


def test_a_repair_that_cannot_be_made_becomes_a_warning_not_a_guess():
    """Two candidates of the same length: we do not pick one."""
    source = "IMEI 352099001761481"
    narrative = "নম্বরগুলি 111111111111111 এবং 222222222222222"
    repaired, notes = draft_module._repair_identifiers(source, narrative)
    assert repaired == narrative
    assert len(notes) == 1
    assert IMEI in notes[0]



# ---------------------------------------------------------------------------
# The profile hangs off the table the reports already use
# ---------------------------------------------------------------------------
# The first D08 migration put these columns on `public.users` and pointed
# `gd_drafts.user_id` there too. `public.users` is a mirror of Supabase's
# `auth.users` and is not reliably populated — an account that had filed a
# report had no row, so its profile 404'd and its first draft would have failed
# a foreign key after the model call was already paid for.

FIX_MIGRATION = (
    BACKEND / "migrations" / "versions" / "20261010160000__gd_profiles_on_auth_users.sql"
)


def test_the_profile_table_is_keyed_on_auth_users():
    schema = FIX_MIGRATION.read_text(encoding="utf-8")
    assert "create table if not exists public.gd_profiles" in schema
    assert "references auth.users(id)" in schema


def test_drafts_reference_the_same_user_table_as_reports():
    """
    Whatever `crime_reports.user_id` points at, `gd_drafts.user_id` must point
    at too. Anyone who can file a report can draft a General Diary from it.
    """
    schema = FIX_MIGRATION.read_text(encoding="utf-8")
    assert "gd_drafts_user_id_fkey" in schema
    assert "foreign key (user_id) references auth.users(id)" in schema


def test_the_old_columns_are_removed_from_public_users():
    schema = FIX_MIGRATION.read_text(encoding="utf-8")
    assert "alter table public.users" in schema
    for column in ("gd_nid", "gd_father_name", "gd_mother_name",
                   "gd_permanent_address", "gd_present_address"):
        assert f"drop column if exists {column}" in schema


def test_a_missing_profile_is_an_empty_profile_not_a_404():
    """
    A user who has never opened the profile screen has no row. That is not an
    error, and returning 404 took the whole General Diary screen down with it.
    """
    source = inspect.getsource(casework.get_gd_profile)
    assert "scalar_one_or_none" in source
    # The docstring explains the old 404, so look for the raise, not the number.
    assert "HTTP_404" not in source
    assert "HTTPException" not in source
    assert "is_complete" in source


def test_the_name_on_the_form_is_the_users_own_to_write():
    """
    It used to come from `users.full_name`, which holds whatever registration
    stored — one row reads `nakib1990saleh`, an email local part. A General
    Diary is signed by hand and the printed name has to match the signature.
    """
    from app.models.gd_profile import GdProfile as GdProfileRow
    from app.schemas.casework import GdProfile as GdProfileSchema

    assert "full_name" in GdProfileRow.REQUIRED
    assert "phone" in GdProfileRow.REQUIRED
    assert "full_name" in GdProfileSchema.model_fields
    assert "phone" in GdProfileSchema.model_fields
