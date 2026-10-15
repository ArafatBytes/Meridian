"""
The migration runner's drift check: line endings are not edits, edits still are.

Found in D04. The ledger held the CRLF hash of one committed migration and the LF hash
of another — same content, different checkouts — and `migrate.py up` refused to run.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import migrate  # noqa: E402

VERSION = "20260101000000"
LF = b"create table a (id int);\n-- a comment\n"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@pytest.fixture
def migration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> migrate.Migration:
    (tmp_path / f"{VERSION}__example.sql").write_bytes(LF)
    monkeypatch.setattr(migrate, "VERSIONS_DIR", tmp_path)
    [loaded] = migrate.load_migrations()
    return loaded


def test_a_crlf_checkout_of_an_applied_file_is_not_drift(migration: migrate.Migration) -> None:
    for recorded in (sha(LF), sha(LF.replace(b"\n", b"\r\n"))):
        assert migrate.report_drift([migration], {VERSION: recorded}) == []


def test_an_edited_statement_is_still_drift(migration: migrate.Migration) -> None:
    edited = sha(b"create table a (id bigint);\n-- a comment\n")
    assert migrate.report_drift([migration], {VERSION: edited})


def test_new_rows_record_the_lf_form(migration: migrate.Migration) -> None:
    assert migration.checksum == sha(LF)


# ---------------------------------------------------------------------------
# `mark` — defect 55
# ---------------------------------------------------------------------------
# Two of D08's migrations were applied by pasting their DDL into the Supabase SQL
# editor and not the ledger insert on the last line of that paste, so `status`
# reported them `pending` for five days while the tables existed. `up` was the
# only recovery and it would have re-run them.
#
# These tests cover the refusals rather than the insert. The insert needs a
# database; the refusals are where the damage would be, because marking a
# migration that did NOT run is worse than the false `pending` it fixes -- the
# schema change is then skipped forever and the ledger claims otherwise.


def test_mark_refuses_a_version_with_no_file(migration: migrate.Migration) -> None:
    """
    The checksum a ledger row records comes from the file. With no file there is
    nothing honest to record, so this must fail rather than invent one.
    """
    args = argparse.Namespace(version="29991231000000", yes=True)
    with pytest.raises(SystemExit) as refusal:
        asyncio.run(migrate.cmd_mark(args))
    assert refusal.value.code == 2


def test_mark_without_yes_does_not_touch_the_database(
    migration: migrate.Migration, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Without `--yes` the command reports and exits non-zero. It must not connect:
    the operator has not yet confirmed the objects exist, and this is the one
    command here that can lie to the ledger.
    """

    def refuse_to_connect() -> None:
        raise AssertionError("cmd_mark connected before --yes was given")

    monkeypatch.setattr(migrate, "connect", refuse_to_connect)
    args = argparse.Namespace(version=VERSION, yes=False)
    assert asyncio.run(migrate.cmd_mark(args)) == 1


def test_mark_is_wired_into_the_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    The subcommand exists and takes a positional version. A handler that argparse
    never reaches is the same as no fix at all.
    """
    monkeypatch.setattr(sys, "argv", ["migrate.py", "mark", VERSION, "--yes"])
    seen: dict[str, object] = {}

    async def capture(args: argparse.Namespace) -> int:
        seen["version"] = args.version
        seen["yes"] = args.yes
        return 0

    monkeypatch.setattr(migrate, "cmd_mark", capture)
    assert migrate.main() == 0
    assert seen == {"version": VERSION, "yes": True}
