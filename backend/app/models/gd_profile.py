"""
The GD profile. D08, ADR 0007.

Keyed on `auth.users`, not `public.users`, because that is what
`crime_reports.user_id` references. `public.users` is a mirror that is not
reliably populated — anyone who can file a report must be able to draft a
General Diary from it, and hanging this off the mirror meant some accounts
could do the first and not the second.

`full_name` and `phone` live here rather than being read off the login. A
General Diary is signed by hand, and the name printed on it has to be the name
the complainant signs — not whatever registration happened to store.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, Text

from app.core.database import Base
from app.models.columns import UUIDStr


class GdProfile(Base):
    __tablename__ = "gd_profiles"

    user_id = Column(UUIDStr, primary_key=True)

    full_name = Column(Text, nullable=True)
    phone = Column(Text, nullable=True)
    gd_nid = Column(Text, nullable=True)
    gd_father_name = Column(Text, nullable=True)
    gd_mother_name = Column(Text, nullable=True)
    gd_permanent_address = Column(Text, nullable=True)
    gd_present_address = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow,
        nullable=False,
    )

    # Every field the printed form needs. The narrative is separate and comes
    # from the draft; these are the identity block above it.
    REQUIRED = (
        "full_name",
        "phone",
        "gd_nid",
        "gd_father_name",
        "gd_mother_name",
        "gd_permanent_address",
        "gd_present_address",
    )

    @property
    def missing(self) -> list[str]:
        return [
            field for field in self.REQUIRED
            if not (getattr(self, field, None) or "").strip()
        ]
