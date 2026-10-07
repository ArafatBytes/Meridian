"""
Shared column types for the ORM models.

Added in S01, when the fresh Supabase schema was created. The models declared
`Column(String)` for every id and foreign key, but the schema stores them as
`uuid` so they can carry a real `ON DELETE CASCADE` reference to `auth.users`.
Those two do not meet in the middle:

* On a query, `select(User).where(User.id == "<str>")` renders as
  `uuid = varchar`, and Postgres has no such operator — it raises
  `operator does not exist: uuid = character varying`.
* On an insert, asyncpg refuses a `str` for a `uuid` parameter with
  `invalid input for query argument: expected uuid.UUID, got str`.

Both failures land squarely on the SOS path (`endpoints/sos.py` and
`services/sos_service.py` both look users up by a string id taken from the JWT),
so without this the one feature that uses the backend database does not work.

`as_uuid=False` keeps every attribute a `str` in Python, which is what the
existing code already assumes, while binding and returning `uuid` at the
database boundary.
"""

from sqlalchemy.dialects.postgresql import UUID

#: Primary keys and foreign keys. `str` in Python, `uuid` in Postgres.
UUIDStr = UUID(as_uuid=False)

# Named columns.py, not types.py, on purpose: a module called `types.py` inside
# a directory that ends up on sys.path shadows the standard library's `types`,
# and `import enum` then fails with a traceback that points nowhere useful.
