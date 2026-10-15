"""
Invariant: **the SOS alert identifies the person, and never invents the name.**

Defect 9. `email_service` prints one name in the emergency email -- in the
subject (`EMERGENCY: {user_name} needs help`) and five more times in the body,
including the instruction *"Try calling {user_name}."* It is the only name the
alert carries and the only identifier a stranger acts on.

For most of this project's life that string was `email.split("@")[0]`, invented
by a block in `endpoints/sos.py` that auto-provisioned a mirror row into
`public.users` on a user's first SOS. Emergency contacts were told to call
`nakib1990saleh`. The mirror row was not supplying referential integrity -- every
`user_id` column in the schema references `auth.users(id)` and always has -- it
was supplying a display name, badly, and it never self-healed: the block only ran
when the row was missing, so editing your name in the app updated `profiles` and
left the alert saying the derived string for good.

**Why this is an invariant and not a unit test.** The fix is four lines and could
be undone in one. What makes it stay fixed is a test that fails on the *shape* of
the mistake: a name derived from an address rather than read from the place the
user typed it. Layer 1 tests the function, layer 2 tests that the dead mirror
cannot come back -- including through `Base.metadata`, which is how it would.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final

import pytest

from app.api.v1.endpoints.sos import _display_name
from app.core.database import Base

pytestmark = pytest.mark.invariant

_BACKEND: Final = Path(__file__).resolve().parent.parent.parent
_SOS_ENDPOINT: Final = _BACKEND / "app" / "api" / "v1" / "endpoints" / "sos.py"
_MODELS: Final = _BACKEND / "app" / "models"


class _FakeResult:
    def __init__(self, row: tuple[Any, ...] | None) -> None:
        self._row = row

    def first(self) -> tuple[Any, ...] | None:
        return self._row


class _FakeSession:
    """
    Records what was asked for, so "did it read `profiles`?" is assertable rather
    than inferred from the answer being right. A stub that returns the correct
    name while querying the wrong table would pass a value-only test.
    """

    def __init__(self, row: tuple[Any, ...] | None) -> None:
        self._row = row
        self.statements: list[str] = []
        self.params: list[dict[str, Any] | None] = []

    async def execute(
        self, statement: Any, params: dict[str, Any] | None = None
    ) -> _FakeResult:
        self.statements.append(str(statement))
        self.params.append(params)
        return _FakeResult(self._row)


# ---------------------------------------------------------------------------
# 1. The name comes from where the user typed it
# ---------------------------------------------------------------------------


async def test_the_name_comes_from_profiles() -> None:
    db = _FakeSession(("Md Arafat",))

    name = await _display_name(db, "abc-123", "mdarafat1661@gmail.com")

    assert name == "Md Arafat"
    assert len(db.statements) == 1
    statement = db.statements[0].lower()
    assert "public.profiles" in statement, (
        f"the display name must be read from public.profiles; read: {statement!r}"
    )
    assert "public.users" not in statement, (
        "read the dropped mirror table instead of profiles -- see defect 9"
    )
    assert db.params[0] == {"uid": "abc-123"}


async def test_the_user_id_is_passed_as_a_string() -> None:
    """
    `current_user["user_id"]` comes out of a JWT claim and is a `str`, but an
    `asyncpg` bind of a non-string against a `uuid` column raises rather than
    coercing. `_display_name` calls `str()` on it so a UUID object -- which is
    what a caller holding a model instance would pass -- cannot break an SOS.
    """
    import uuid as uuid_module

    user_id = uuid_module.uuid4()
    db = _FakeSession(("Md Arafat",))

    await _display_name(db, user_id, None)

    assert db.params[0] == {"uid": str(user_id)}


async def test_surrounding_whitespace_is_trimmed() -> None:
    db = _FakeSession(("  Md Arafat \n",))
    assert await _display_name(db, "abc-123", None) == "Md Arafat"


@pytest.mark.parametrize("stored", [None, "", "   ", "\n"])
async def test_a_blank_stored_name_is_not_used(stored: str | None) -> None:
    """
    `profiles.name` is NOT NULL in the schema, but an empty string satisfies that
    and `EMERGENCY:  needs help` is worse than an address.
    """
    db = _FakeSession((stored,))
    assert await _display_name(db, "abc-123", "a@b.com") == "a@b.com"


# ---------------------------------------------------------------------------
# 2. The fallback is honest: a whole address, never a name-shaped guess
# ---------------------------------------------------------------------------


async def test_without_a_profile_the_whole_email_is_used() -> None:
    db = _FakeSession(None)

    name = await _display_name(db, "abc-123", "mdarafat1661@gmail.com")

    assert name == "mdarafat1661@gmail.com"


async def test_the_fallback_is_never_the_email_local_part() -> None:
    """
    **The regression.** `nakib1990saleh` is the value this defect actually put in
    front of an emergency contact -- recorded in migration 20261010160000, which
    found it while fixing the GD form for the same reason.

    An address is a true and complete identifier that a contact may recognise, and
    it is visibly an address rather than something shaped like a name. The local
    part alone is neither: it reads as a name and is not one.
    """
    db = _FakeSession(None)

    name = await _display_name(db, "abc-123", "nakib1990saleh@gmail.com")

    assert name != "nakib1990saleh"
    assert "@" in name, (
        "the fallback must stay recognisable as an email address, not be reshaped "
        "into something that reads like a name"
    )


async def test_with_neither_profile_nor_email_it_does_not_raise() -> None:
    """
    An SOS is not the moment to refuse to send an alert over a display string.
    The alert still goes out; `email_service` just has nobody to name.
    """
    db = _FakeSession(None)

    name = await _display_name(db, "abc-123", None)

    assert name
    assert "@" not in name


async def test_a_missing_profile_is_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    No `profiles` row means registration did not complete normally. The alert
    degrades silently to the user, so the signal has to go somewhere.
    """
    db = _FakeSession(None)

    with caplog.at_level("WARNING"):
        await _display_name(db, "abc-123", "a@b.com")

    assert any("profiles" in record.message for record in caplog.records), (
        "falling back to an address should say why in the log"
    )


# ---------------------------------------------------------------------------
# 3. The mirror table cannot come back
# ---------------------------------------------------------------------------


def test_the_endpoint_derives_no_name_from_an_address() -> None:
    """
    Source-level, because this is the shape of the mistake rather than one value
    of it. Any `split("@")` in this file is either the defect returning or
    something close enough to it to want a second opinion.
    """
    source = _SOS_ENDPOINT.read_text(encoding="utf-8")
    offenders = [
        line.strip()
        for line in source.splitlines()
        if 'split("@")' in line or "split('@')" in line
        if not line.strip().startswith("#")
    ]
    assert offenders == [], (
        "endpoints/sos.py derives a name from an email address again (defect 9): "
        f"{offenders}"
    )


def test_the_user_model_is_gone() -> None:
    assert not (_MODELS / "user.py").exists(), (
        "app/models/user.py is back. It mapped public.users, which defect 9 "
        "dropped; identity is auth.users and display data is public.profiles."
    )

    from app import models

    assert not hasattr(models, "User"), "models.User is back -- see defect 9"
    assert "User" not in getattr(models, "__all__", [])


def test_create_all_cannot_recreate_the_mirror() -> None:
    """
    **The one that guards the trap.** `core/database.py:init_db()` runs
    `Base.metadata.create_all` on **every API start**, wrapped in a try/except
    that logs "Database not available" and continues.

    So while a `users` table was in this metadata, dropping it in Supabase would
    have been undone by the next restart, and the swallowed exception would have
    hidden the reason. Deleting the model is what makes the drop stick, and this
    asserts the metadata agrees.
    """
    assert "users" not in Base.metadata.tables, (
        "a `users` table is in Base.metadata, so init_db()'s create_all will "
        "recreate the mirror on the next API boot. See defect 9."
    )


def test_no_model_declares_a_foreign_key_to_the_mirror() -> None:
    """
    These declarations were wrong about the database -- `SCHEMA.sql` points every
    `user_id` at `auth.users(id)` -- and the error was not harmless: it is what
    three separate documents read when they recorded that SOS depended on the
    mirror, which is why dropping it looked dangerous for months.

    They cannot be corrected by retargeting, because `auth.users` lives in a
    schema this metadata does not map. So the right number of them is zero.
    """
    offenders: list[str] = []
    for path in sorted(_MODELS.glob("*.py")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if 'ForeignKey("users.id")' in line or "ForeignKey('users.id')" in line:
                offenders.append(f"{path.name}:{number}")
    assert offenders == [], (
        "ORM foreign keys pointing at the dropped public.users mirror: "
        f"{offenders}. The real constraint is in SCHEMA.sql and targets "
        "auth.users(id)."
    )


def test_the_drop_migration_exists_and_is_not_destructive_by_surprise() -> None:
    """
    The migration is the half the owner applies by hand against Supabase, so it
    is the half most likely to drift from the code. This checks it is still there
    and still refuses to cascade -- `drop table ... cascade` on a table whose
    whole premise is "nothing references it" could only ever destroy something
    that appeared after the premise was checked.
    """
    migration = (
        _BACKEND
        / "migrations"
        / "versions"
        / "20261015160000__drop_public_users_mirror.sql"
    )
    assert migration.exists(), "the public.users drop migration is missing"

    sql = migration.read_text(encoding="utf-8").lower()
    assert "drop table if exists public.users restrict" in sql
    assert "cascade" not in sql.split("drop table")[-1], (
        "the drop must stay RESTRICT: cascading would silently destroy a "
        "dependent that appeared after the migration was written"
    )
