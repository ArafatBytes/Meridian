"""
General Diary draft. D08, ADR 0007.

Two states and no third. `draft` is editable; `ready_to_file` is frozen. There
is no `filed`, because filing happens at a thana counter that sends us nothing
-- what comes back is a number the user types in, which is a record and not a
state. The database carries the same constraints (see the D08 migration), so
the rule survives anything that writes to this table, including a future
endpoint nobody has written yet.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from app.core.database import Base
from app.models.columns import UUIDStr

STATE_DRAFT = "draft"
STATE_READY = "ready_to_file"


class GdDraft(Base):
    __tablename__ = "gd_drafts"

    id = Column(UUIDStr, primary_key=True, default=lambda: str(uuid.uuid4()))
    report_id = Column(UUIDStr, ForeignKey("crime_reports.id"), nullable=False, unique=True)
    # Defect 9: no ForeignKey. The real constraint is in SCHEMA.sql and targets
    # `auth.users(id)`, a schema this metadata does not map. See `models/crime.py`.
    user_id = Column(UUIDStr, nullable=False)

    state = Column(String, nullable=False, default=STATE_DRAFT)
    narrative_bn = Column(Text, nullable=False)
    summary_en = Column(Text, nullable=False)
    missing_details = Column(JSONB, nullable=False, default=list)

    thana_name = Column(Text, nullable=False)
    thana_district = Column(Text, nullable=False)

    engine = Column(String, nullable=False)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    gd_number = Column(Text, nullable=True)
    gd_filed_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    @property
    def is_approved(self) -> bool:
        return self.state == STATE_READY
