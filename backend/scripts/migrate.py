#!/usr/bin/env python3
"""
Forward-only migration runner.

    python backend/scripts/migrate.py status            what is applied, what is pending
    python backend/scripts/migrate.py up                apply everything pending
    python backend/scripts/migrate.py up --dry-run      say what would run, change nothing
    python backend/scripts/migrate.py sql               print pending SQL, paste-ready
    python backend/scripts/migrate.py sql --out f.sql   ... into a file instead

Why this exists and not Alembic
------------------------------
Alembic's autogenerate compares SQLAlchemy models against the database, and this
project's database is not described by its models: PostGIS geography columns,
partial indexes, CHECK constraints carrying ethical invariants, RLS policies and
triggers are all things Alembic either cannot see or renders badly. Hand-written
forward-only SQL is honest about what is actually being run, and the thing a
reviewer reads is the thing the database executes.

Forward-only means there are no `down` migrations. Rolling back a schema change
on a live database is a fiction most of the time; correcting it with a new
migration is what actually happens. `RESET.sql` exists for the development case
where you genuinely want to start over.

How a migration is identified
-----------------------------
`migrations/versions/<utc-timestamp>__<slug>.sql`, applied in filename order. The
runner records a sha256 of each file, so editing an applied migration is an error
rather than a silent divergence between two developers' databases.

Connectivity
------------
Needs `DATABASE_URL`, from the environment or from `backend/.env`. It is read
directly rather than through `app.core.config` so this script works regardless of
the working directory and without the application's dependencies installed.

`sql` needs no database at all, which is the point: when a direct connection is
blocked — a managed Postgres that only accepts pooled
connections, a network that filters 5432 — `sql` produces something you paste
into the Supabase SQL Editor, and the ledger insert is included so the applied
state is still recorded.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

# Windows consoles default to cp1252, and both the migrations and the fixture
# contain em dashes, section signs and Bangla place names. Printing them to an
# unreconfigured stdout raises UnicodeEncodeError and the command dies having done
# nothing useful -- which is a particularly bad failure for a tool whose whole job
# is to hand you text to paste. Writing to a file was always fine (those use
# encoding="utf-8" explicitly); this fixes the stdout path.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except (AttributeError, OSError):
        pass  # not a real console, or already UTF-8

BACKEND_DIR = Path(__file__).resolve().parent.parent
VERSIONS_DIR = BACKEND_DIR / "migrations" / "versions"
ENV_FILE = BACKEND_DIR / ".env"

LEDGER_DDL = """\
-- The migration ledger. Created by scripts/migrate.py on first run.
create table if not exists public.schema_migrations (
    version    text        primary key,
    name       text        not null,
    checksum   text        not null,
    applied_at timestamptz not null default now(),
    applied_by text
);

comment on table public.schema_migrations is
    'Applied migrations, one row per file in backend/migrations/versions/. '
    'checksum is sha256 of the file; a mismatch means an applied migration was edited.';
"""

FILENAME_RE = re.compile(r"^(?P<version>\d{8,14})__(?P<slug>[a-z0-9_]+)\.sql$")


# ---------------------------------------------------------------------------
# Migrations on disk
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Migration:
    version: str
    name: str
    path: Path
    sql: str
    checksum: str

    @property
    def label(self) -> str:
        return f"{self.version}__{self.name}"


def load_migrations() -> list[Migration]:
    """Every migration on disk, in application order. Rejects bad filenames."""
    if not VERSIONS_DIR.is_dir():
        die(f"no migrations directory at {VERSIONS_DIR}")

    found: list[Migration] = []
    for path in sorted(VERSIONS_DIR.glob("*.sql")):
        match = FILENAME_RE.match(path.name)
        if not match:
            die(
                f"migration filename not understood: {path.name}\n"
                "    expected <utc-timestamp>__<lower_snake_slug>.sql, "
                "e.g. 20261007120000__risk_flags.sql"
            )
        raw = path.read_bytes()
        found.append(
            Migration(
                version=match.group("version"),
                name=match.group("slug"),
                path=path,
                sql=raw.decode("utf-8"),
                checksum=hashlib.sha256(raw).hexdigest(),
            )
        )

    versions = [m.version for m in found]
    duplicates = {v for v in versions if versions.count(v) > 1}
    if duplicates:
        die(f"two migrations share a version: {', '.join(sorted(duplicates))}")

    return found


def ledger_insert(migration: Migration) -> str:
    """
    The SQL that records a migration as applied.

    Included in `sql` output so that pasting into a SQL editor leaves the ledger
    correct, rather than the database running ahead of its own records. It is why
    there is no separate "mark this as applied" command.
    """
    return (
        "insert into public.schema_migrations (version, name, checksum, applied_by)\n"
        f"values ('{migration.version}', '{migration.name}', "
        f"'{migration.checksum}', 'manual')\n"
        "on conflict (version) do update\n"
        "    set checksum = excluded.checksum,\n"
        "        applied_at = now(),\n"
        "        applied_by = excluded.applied_by;"
    )


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------


def read_database_url() -> str | None:
    """
    DATABASE_URL from the environment, else parsed out of backend/.env.

    The .env file is parsed rather than sourced: it holds values containing
    spaces, '#' and '=', and a naive shell source mangles them.
    """
    from_env = os.environ.get("DATABASE_URL")
    if from_env:
        return from_env.strip()

    if not ENV_FILE.is_file():
        return None

    for line in ENV_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line.startswith("DATABASE_URL="):
            continue
        value = line.split("=", 1)[1].strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        return value or None
    return None


def to_asyncpg_dsn(url: str) -> tuple[str, dict[str, Any]]:
    """
    Turn a SQLAlchemy URL into something asyncpg accepts.

    Two adjustments:

    * `postgresql+asyncpg://` -> `postgresql://`. The driver suffix is
      SQLAlchemy's notation and asyncpg rejects it.
    * `sslmode=` / `ssl=` are stripped from the query string and translated into
      a connect keyword. asyncpg does not read libpq's sslmode, and managed
      Postgres almost always requires TLS, so dropping it silently would turn
      into a confusing connection error.
    """
    dsn = url.replace("+asyncpg", "").replace("+psycopg2", "")
    kwargs: dict[str, Any] = {}

    split = urlsplit(dsn)
    if split.query:
        kept: list[str] = []
        for part in split.query.split("&"):
            if not part:
                continue
            key, _, value = part.partition("=")
            if key.lower() in {"sslmode", "ssl"}:
                kwargs["ssl"] = "require" if value.lower() in {"require", "true", "1"} else value
            elif key.lower() in {"pgbouncer", "application_name", "options"}:
                continue  # meaningless or unsupported here
            else:
                kept.append(part)
        dsn = split._replace(query="&".join(kept)).geturl()

    return dsn, kwargs


def redact(url: str) -> str:
    return re.sub(r"//[^@/]*@", "//***@", url)


async def connect() -> Any:
    """Connect, or exit with something actionable."""
    try:
        import asyncpg  # imported lazily: `sql` mode needs no database driver
    except ModuleNotFoundError:
        die(
            "asyncpg is not installed.\n"
            "    Install the backend dependencies, or use "
            "`migrate.py sql` and paste the output into your SQL editor."
        )

    url = read_database_url()
    if not url:
        die(
            "DATABASE_URL is not set (checked the environment and backend/.env).\n"
            "    Or use `migrate.py sql` and paste the output into your SQL editor."
        )

    dsn, kwargs = to_asyncpg_dsn(url)
    try:
        return await asyncpg.connect(dsn, **kwargs)
    except Exception as exc:  # noqa: BLE001 - the message is the whole point
        die(
            f"could not connect to {redact(dsn)}\n"
            f"    {type(exc).__name__}: {exc}\n"
            "    If this database only accepts pooled or web connections, run\n"
            "    `migrate.py sql --out pending.sql` and paste that instead."
        )


async def fetch_applied(conn: Any) -> dict[str, str]:
    """version -> checksum, for everything the ledger says is applied."""
    await conn.execute(LEDGER_DDL)
    rows = await conn.fetch("select version, checksum from public.schema_migrations")
    return {row["version"]: row["checksum"] for row in rows}


# ---------------------------------------------------------------------------
# Drift
# ---------------------------------------------------------------------------


def report_drift(migrations: list[Migration], applied: dict[str, str]) -> list[str]:
    """
    Applied migrations whose file no longer matches what was run.

    This is the check that catches the most expensive class of mistake: two
    developers whose databases disagree because one of them edited a migration
    that had already run.
    """
    drifted: list[str] = []
    by_version = {m.version: m for m in migrations}
    for version, checksum in applied.items():
        migration = by_version.get(version)
        if migration is None:
            drifted.append(f"{version}: applied, but no file on disk")
        elif migration.checksum != checksum:
            drifted.append(f"{migration.label}: file changed since it was applied")
    return drifted


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


async def cmd_status(_: argparse.Namespace) -> int:
    migrations = load_migrations()
    conn = await connect()
    try:
        applied = await fetch_applied(conn)
    finally:
        await conn.close()

    print("\nmigrations")
    for migration in migrations:
        if migration.version in applied:
            mark = "applied "
            if applied[migration.version] != migration.checksum:
                mark = "CHANGED "
        else:
            mark = "pending "
        print(f"  {mark} {migration.label}")

    drift = report_drift(migrations, applied)
    pending = [m for m in migrations if m.version not in applied]

    print()
    if drift:
        print("  drift detected:")
        for line in drift:
            print(f"    - {line}")
        print()
        return 1

    print(f"  {len(applied)} applied, {len(pending)} pending\n")
    return 0


async def cmd_up(args: argparse.Namespace) -> int:
    migrations = load_migrations()
    conn = await connect()
    try:
        applied = await fetch_applied(conn)

        drift = report_drift(migrations, applied)
        if drift:
            print("\n  refusing to run: applied migrations have changed on disk")
            for line in drift:
                print(f"    - {line}")
            print("\n  A migration that has run is history. Correct it with a new migration.\n")
            return 1

        pending = [m for m in migrations if m.version not in applied]
        if not pending:
            print("\n  nothing to do — schema is up to date\n")
            return 0

        print(f"\napplying {len(pending)} migration(s)")
        for migration in pending:
            if args.dry_run:
                print(f"  would run {migration.label}")
                continue

            print(f"  running {migration.label} ... ", end="", flush=True)
            # One transaction per migration: a failure leaves the database at a
            # migration boundary rather than halfway through one.
            try:
                async with conn.transaction():
                    await conn.execute(migration.sql)
                    await conn.execute(
                        "insert into public.schema_migrations "
                        "(version, name, checksum, applied_by) values ($1, $2, $3, $4)",
                        migration.version,
                        migration.name,
                        migration.checksum,
                        os.environ.get("USER") or os.environ.get("USERNAME") or "unknown",
                    )
            except Exception as exc:  # noqa: BLE001
                print("FAILED")
                print(f"\n    {type(exc).__name__}: {exc}\n")
                return 1
            print("ok")
    finally:
        await conn.close()

    print()
    return 0


def cmd_sql(args: argparse.Namespace) -> int:
    """
    Emit pending SQL for manual application. No database connection.

    Without a connection the runner cannot know what is already applied, so this
    emits everything and relies on each migration being idempotent (`create table
    if not exists`, `create or replace function`, guarded triggers). The ledger
    insert uses `on conflict do update`, so pasting twice is harmless.
    """
    migrations = load_migrations()
    if args.version:
        migrations = [m for m in migrations if m.version == args.version]
        if not migrations:
            die(f"no migration with version {args.version}")

    chunks: list[str] = [
        "-- ===========================================================================",
        "-- Meridian — schema migrations, for manual application",
        "-- ===========================================================================",
        "-- Generated by backend/scripts/migrate.py. Paste the whole file into the",
        "-- Supabase SQL Editor and run it once.",
        "--",
        "-- Safe to run more than once: every statement is idempotent and the ledger",
        "-- insert upserts. After running, `migrate.py status` will report these as",
        "-- applied.",
        "-- ===========================================================================",
        "",
        LEDGER_DDL,
        "",
    ]
    for migration in migrations:
        chunks += [
            "",
            "-- ===========================================================================",
            f"-- {migration.label}",
            "-- ===========================================================================",
            "",
            migration.sql.rstrip(),
            "",
            f"-- record {migration.label} as applied",
            ledger_insert(migration),
            "",
        ]

    output = "\n".join(chunks)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output, encoding="utf-8")
        print(f"\n  wrote {len(migrations)} migration(s) to {out_path}")
        print("  paste it into the Supabase SQL Editor and run it once\n")
    else:
        print(output)
    return 0


def die(message: str) -> Any:
    print(f"\n  error: {message}\n", file=sys.stderr)
    raise SystemExit(2)


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="migrate.py",
        description="Forward-only SQL migrations for Meridian.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="show applied and pending migrations")

    up = sub.add_parser("up", help="apply pending migrations")
    up.add_argument("--dry-run", action="store_true", help="list what would run")

    emit = sub.add_parser("sql", help="print SQL for manual application")
    emit.add_argument("--out", metavar="PATH", help="write to a file instead of stdout")
    emit.add_argument("--version", metavar="VERSION", help="just this one migration")

    args = parser.parse_args()

    if args.command == "sql":
        return cmd_sql(args)

    handlers = {"status": cmd_status, "up": cmd_up}
    return asyncio.run(handlers[args.command](args))


if __name__ == "__main__":
    raise SystemExit(main())
