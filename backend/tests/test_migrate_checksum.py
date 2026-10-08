"""
The migration runner's drift check: line endings are not edits, edits still are.

Found in D04. The ledger held the CRLF hash of one committed migration and the LF hash
of another — same content, different checkouts — and `migrate.py up` refused to run.
"""

from __future__ import annotations

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
