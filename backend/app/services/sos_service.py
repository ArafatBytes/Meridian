import logging
import os
import tempfile
import csv
import json
import math
from typing import List, Optional, Dict
from geoalchemy2 import WKTElement
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import UploadFile
from app.models.emergency_contact import EmergencyContact
from app.models.sos import SOSIncident
from app.services.email_service import email_service
from app.core.config import settings

logger = logging.getLogger(__name__)


class SOSService:
    def __init__(self):
        self.max_video_size_mb = settings.SOS_VIDEO_MAX_SIZE_MB
        self.max_video_size_bytes = self.max_video_size_mb * 1024 * 1024
        
        # Load police stations into memory
        self.police_stations: List[Dict] = []
        self._load_police_stations()

    def _load_police_stations(self):
        """Load police stations from CSV file"""
        try:
            # Path to backend/police_stations.csv
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            csv_path = os.path.join(base_dir, "police_stations.csv")
            
            if os.path.exists(csv_path):
                with open(csv_path, mode='r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        try:
                            # Parse coordinates
                            row['latitude'] = float(row.get('latitude', 0))
                            row['longitude'] = float(row.get('longitude', 0))
                            self.police_stations.append(row)
                        except (ValueError, TypeError):
                            continue
                logger.info(f"✅ Loaded {len(self.police_stations)} police stations")
                # One distinct email across hundreds of stations means the
                # contact column is placeholder data, not real routing.
                distinct = {s.get("email", "") for s in self.police_stations if s.get("email")}
                if len(self.police_stations) > 10 and len(distinct) <= 1:
                    logger.warning(
                        "⚠️  All %d police stations share %d distinct email address(es) - "
                        "this is placeholder data. Keep POLICE_ROUTING_ENABLED=false "
                        "until it is replaced (defect 17).",
                        len(self.police_stations),
                        len(distinct),
                    )
            else:
                logger.warning(f"⚠️ Police stations file not found at {csv_path}")
        except Exception as e:
            logger.error(f"Failed to load police stations: {e}")

    def _haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two points in km"""
        R = 6371  # Earth radius in km
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat/2) * math.sin(dlat/2) + \
            math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * \
            math.sin(dlon/2) * math.sin(dlon/2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        return R * c

    def _get_nearby_police_emails(self, lat: float, lon: float, radius_km: float = 5.0) -> List[str]:
        """Get emails of police stations within radius."""
        # Off by default. police_stations.csv currently has one placeholder
        # address repeated across all 606 rows, so with this enabled an SOS
        # from anywhere in Dhaka emails a stranger. Enable once the CSV holds
        # real contacts (defect 17, S05).
        if not settings.POLICE_ROUTING_ENABLED:
            logger.info(
                "Police routing disabled (POLICE_ROUTING_ENABLED=false); "
                "alerting emergency contacts only"
            )
            return []

        emails = []
        for station in self.police_stations:
            s_lat = station['latitude']
            s_lon = station['longitude']
            s_email = station.get('email')
            
            if s_lat and s_lon and s_email:
                dist = self._haversine_distance(lat, lon, s_lat, s_lon)
                if dist <= radius_km:
                    emails.append(s_email)
        return emails

    async def trigger_sos_alert(
        self,
        user_id: str,
        user_name: str,
        location: dict,
        video_file: Optional[UploadFile],
        db: AsyncSession
    ) -> dict:
        """
        Trigger SOS alert:
        1. Get emergency contacts
        2. Get nearby police stations (within 5km)
        3. Save video if provided (and validate size)
        4. Send email alerts with video attachment
        """
        try:
            # 1. Get user's emergency contacts
            contacts = await self._get_emergency_contacts(user_id, db)
            
            # Extract email addresses from contacts
            recipient_emails = [c.email for c in contacts if c.email]
            
            # 2. Get nearby police station emails
            lat = float(location.get('latitude', 0))
            lon = float(location.get('longitude', 0))
            
            police_emails = self._get_nearby_police_emails(lat, lon, radius_km=5.0)
            if police_emails:
                logger.info(f"Found {len(police_emails)} police stations within 5km")
                recipient_emails.extend(police_emails)
            
            # Remove duplicates
            recipient_emails = list(set(recipient_emails))
            
            if not recipient_emails:
                logger.warning(f"No recipients found (contacts or police) for user {user_id}")
                return {
                    "success": False,
                    "message": "No email recipients found (add contacts or move closer to police station)",
                    "contacts_notified": 0
                }

            # 3. Handle video file if provided
            video_path = None
            if video_file:
                video_path = await self._save_video(video_file, user_id)
                if not video_path:
                    logger.error("Failed to save video, proceeding without it")

            # 4. Send email alerts
            success = await email_service.send_sos_alert(
                to_emails=recipient_emails,
                user_name=user_name,
                location=location,
                video_path=video_path
            )

            # 5. Record the incident -- defect 35.
            #
            # This used to be missing entirely: an SOS could be delivered, the
            # user told "emergency contacts have been notified", and
            # `sos_incidents` would still hold zero rows afterwards. The README's
            # claim that incidents are "logged in database" was simply false.
            #
            # Written whether or not delivery succeeded. An alert that failed to
            # send is precisely the event worth having a record of, and a table
            # that only contains successes cannot answer "did my SOS go out?".
            incident_id = await self._record_incident(
                db=db,
                user_id=user_id,
                location=location,
                contact_ids=[str(c.id) for c in contacts],
                recipient_count=len(recipient_emails),
                police_station_count=len(police_emails),
                delivered=success,
                video_attached=video_path is not None,
            )

            # Clean up the temporary video file.
            #
            # The clip is not retained. Keeping it would mean a storage bucket, a
            # retention window and an access policy for what is by definition
            # footage recorded under duress, none of which exists yet. Until it
            # does, deleting is correct behaviour rather than an oversight -- and
            # the incident row records that a video WAS attached to the alert.
            if video_path and os.path.exists(video_path):
                try:
                    os.remove(video_path)
                except Exception as e:
                    logger.error(f"Failed to delete temporary video: {e}")

            return {
                "success": success,
                "message": "SOS alert sent successfully" if success else "Failed to send SOS alert",
                "contacts_notified": len(recipient_emails) if success else 0,
                "video_attached": video_path is not None,
                "police_stations_found": len(police_emails),
                "incident_id": incident_id,
            }

        except Exception as e:
            logger.error(f"Error triggering SOS alert: {e}")
            return {
                "success": False,
                "message": str(e),
                "contacts_notified": 0
            }

    async def _record_incident(
        self,
        *,
        db: AsyncSession,
        user_id: str,
        location: dict,
        contact_ids: list[str],
        recipient_count: int,
        police_station_count: int,
        delivered: bool,
        video_attached: bool,
    ) -> str | None:
        """
        Write one row to `sos_incidents`. Returns its id, or None if the write
        failed.

        Committed immediately rather than left to the request session's cleanup.
        The endpoint wraps this whole call in a try/except that raises
        HTTPException, and a rollback there would take the audit row with it. An
        audit trail that disappears when something downstream goes wrong is not an
        audit trail.

        A failure to record is logged and swallowed. The alert has already gone out
        by this point, and failing the request would tell someone in an emergency
        that their SOS did not work when it did.

        ## What goes in `contacts_notified`

        A JSON object, not a list of email addresses:

            {"contact_ids": [...], "recipient_count": 2,
             "police_station_count": 0, "delivered": true, "video_attached": false}

        Contact **ids**, deliberately. The addresses already live in
        `emergency_contacts`; copying them here would duplicate personal data into
        a second table with its own lifetime for no gain, since the history screen
        (D09) needs to say "2 contacts notified" rather than list them. That is the
        data minimisation invariant applied where it happens to be cheap.
        """
        try:
            incident = SOSIncident(
                user_id=user_id,
                # geoalchemy2 wants WKT with an explicit SRID. Note the order:
                # POINT takes longitude first, the reverse of how the rest of this
                # service passes coordinates around.
                location=WKTElement(
                    f"POINT({float(location['longitude'])} {float(location['latitude'])})",
                    srid=4326,
                ),
                video_url=None,  # see the cleanup comment in trigger_sos_alert
                contacts_notified=json.dumps(
                    {
                        "contact_ids": contact_ids,
                        "recipient_count": recipient_count,
                        "police_station_count": police_station_count,
                        "delivered": delivered,
                        "video_attached": video_attached,
                    }
                ),
                voice_activated=False,  # the voice path sets this once S18 lands
                status="active",
            )
            db.add(incident)
            await db.commit()
            await db.refresh(incident)
            logger.info(
                "Recorded SOS incident %s for user %s (delivered=%s, recipients=%d)",
                incident.id,
                user_id,
                delivered,
                recipient_count,
            )
            return str(incident.id)
        except Exception as e:
            await db.rollback()
            logger.error(f"Failed to record SOS incident for user {user_id}: {e}")
            return None

    async def _get_emergency_contacts(self, user_id: str, db: AsyncSession) -> List[EmergencyContact]:
        """Fetch user's emergency contacts"""
        try:
            query = select(EmergencyContact).where(EmergencyContact.user_id == user_id)
            result = await db.execute(query)
            return result.scalars().all()
        except Exception as e:
            logger.error(f"Error fetching emergency contacts: {e}")
            return []

    async def _save_video(self, video_file: UploadFile, user_id: str) -> Optional[str]:
        """
        Save uploaded video to temporary file with size validation
        Returns path to saved file or None if failed
        """
        try:
            # Read file content
            content = await video_file.read()
            file_size = len(content)

            # Validate size
            if file_size > self.max_video_size_bytes:
                logger.error(
                    f"Video size ({file_size / 1024 / 1024:.2f}MB) exceeds "
                    f"maximum allowed size ({self.max_video_size_mb}MB)"
                )
                return None

            # Create temporary file
            suffix = os.path.splitext(video_file.filename)[1] if video_file.filename else '.mp4'
            temp_file = tempfile.NamedTemporaryFile(
                delete=False,
                suffix=suffix,
                prefix=f"sos_{user_id}_"
            )

            # Write content
            temp_file.write(content)
            temp_file.close()

            logger.info(
                f"Video saved: {temp_file.name} "
                f"(Size: {file_size / 1024 / 1024:.2f}MB)"
            )

            return temp_file.name

        except Exception as e:
            logger.error(f"Error saving video: {e}")
            return None


# Singleton instance
sos_service = SOSService()
