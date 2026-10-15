"""
Models package

`User` is gone -- defect 9. It mapped `public.users`, a mirror of
`auth.users` + `public.profiles` that nothing referenced: every `user_id`
column in `migrations/supabase/SCHEMA.sql` targets `auth.users(id)` directly,
including `gd_drafts` since migration 20261010160000.

Deleting the class is what makes dropping the table **stick**. `init_db()`
calls `Base.metadata.create_all` on every API boot inside a try/except that
logs "Database not available" and continues -- so while `User` was in this
metadata, dropping `public.users` in Supabase would have silently recreated it
on the next restart, and the swallowed exception would have hidden why.

Identity is Supabase's. Display data is `public.profiles`, read where it is
needed (`endpoints/sos.py`) rather than mirrored into a table with its own
lifetime and its own chance of being stale.
"""
from app.models.crime import CrimeReport, CrimeCategory, CrimeSeverity
from app.models.emergency_contact import EmergencyContact
from app.models.sos import SOSIncident
from app.models.location import UserLocation
from app.models.gd_draft import GdDraft, STATE_DRAFT, STATE_READY
from app.models.gd_profile import GdProfile

__all__ = [
    "CrimeReport",
    "CrimeCategory",
    "CrimeSeverity",
    "EmergencyContact",
    "SOSIncident",
    "UserLocation",
    "GdDraft",
    "GdProfile",
    "STATE_DRAFT",
    "STATE_READY",
]
