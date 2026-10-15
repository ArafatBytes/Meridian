"""
Crime report model
"""
from sqlalchemy import Column, String, DateTime, Text, Enum as SQLEnum
from datetime import datetime
import uuid
import enum
from app.core.database import Base
from app.models.columns import UUIDStr


class CrimeCategory(str, enum.Enum):
    THEFT = "theft"
    ASSAULT = "assault"
    HARASSMENT = "harassment"
    VANDALISM = "vandalism"
    BURGLARY = "burglary"
    ROBBERY = "robbery"
    FRAUD = "fraud"
    OTHER = "other"


class CrimeSeverity(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CrimeReport(Base):
    __tablename__ = "crime_reports"
    
    id = Column(UUIDStr, primary_key=True, default=lambda: str(uuid.uuid4()))
    # Defect 9. No `ForeignKey` here, deliberately.
    #
    # This said `ForeignKey("users.id")` and that was **wrong about the
    # database**: `migrations/supabase/SCHEMA.sql` points every user_id column
    # at `auth.users(id)`, and has since the file was first committed. The
    # mistake was not harmless -- it is what three separate documents read when
    # they recorded that `sos_incidents` depended on the `public.users` mirror,
    # and it is why dropping that mirror looked like it would break SOS.
    #
    # It cannot be corrected by retargeting: `auth.users` lives in Supabase's
    # own schema, which this metadata does not and should not map. So the
    # constraint is declared in SCHEMA.sql only, and this column is a plain
    # value. `Base.metadata` is a client of that schema, not its source --
    # `init_db()` runs `create_all` on every boot, which is exactly why a
    # half-true model here is a liability.
    user_id = Column(UUIDStr, nullable=False)
    # `values_callable` is load-bearing, not a style choice. Without it
    # SQLAlchemy maps this column by the enum's *member names* (THEFT, ASSAULT)
    # while every row in the database holds its *value* ('theft', 'assault') --
    # the frontend writes reports straight to Supabase, in lowercase, and the
    # Postgres enum's labels are lowercase too. Reading any existing report
    # through the ORM then raises
    #   LookupError: 'other' is not among the defined enum values
    # which stayed invisible until D08 became the first code to read a report
    # back through SQLAlchemy at all (the handlers in endpoints/crimes.py are
    # still stubs).
    category = Column(
        SQLEnum(
            CrimeCategory,
            name="crime_category",
            values_callable=lambda enum: [member.value for member in enum],
        ),
        nullable=False,
    )
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    incident_date_time = Column(DateTime, nullable=False, index=True)
    latitude = Column(String, nullable=False)
    longitude = Column(String, nullable=False)
    location_name = Column(String, nullable=True)
    # filed | withdrawn | removed. NOT a trust level: a report is never approved.
    #
    # It used to allow ('pending', 'verified', 'investigating', 'resolved'), which
    # mixed a trust question with a casework one and could answer neither -- nothing
    # ever wrote any value but the default, there was no role column to gate an
    # admin on, and the casework half duplicated `gd_drafts`, which owns that
    # lifecycle properly. The `verified` boolean is gone for the same reason: this
    # product cannot establish that an incident happened, so there was no honest way
    # to set it.
    #
    # What replaced it is corroboration over several independent reports --
    # `app/agents/report_corroboration.py`, publishing to `community_clusters`. See
    # migrations/versions/20261013120000__report_trust.sql for the whole argument.
    #
    # Not writable by `authenticated`: the column-level UPDATE grant omits it, and
    # withdrawal goes through public.withdraw_crime_report().
    status = Column(String, default='filed')
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # No `user` relationship. It pointed at `models/user.py`'s `User`, the ORM
    # half of the `public.users` mirror deleted in defect 9; nothing ever
    # navigated it. The owner is `auth.users`, which this package does not map.
