import logging
import os
import tempfile
import csv
import json
from typing import List, Optional, Dict
from geoalchemy2 import WKTElement
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import UploadFile
from app.casework.thana import DHAKA_CITY_DISTRICT, MAX_PLAUSIBLE_KM, nearest_thana
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
        # Dhaka city station name -> email, for routing an SOS to the thana that
        # owns the caller's location. Built by _load_police_stations.
        self._dhaka_station_emails: dict[str, str] = {}
        # Defect 17. Whether the CSV's contact columns are per-station data or
        # one value repeated. This is logged, not enforced: see
        # _check_contacts_are_per_station.
        self._contacts_are_per_station: bool = False
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
                self._contacts_are_per_station = self._check_contacts_are_per_station()
                self._dhaka_station_emails = self._build_dhaka_email_map()
            else:
                logger.warning(f"⚠️ Police stations file not found at {csv_path}")
        except Exception as e:
            logger.error(f"Failed to load police stations: {e}")

    def _check_contacts_are_per_station(self) -> bool:
        """
        Does the CSV hold a contact *per station*, or one value repeated? Defect 17.

        **This reports; it does not refuse.** It used to refuse, which was wrong:
        the owner had deliberately put their own address in every row *in order to
        test police routing end to end*, and a gate that cannot be opened by the
        person who owns the data is not a safety feature, it is a bug. The gate is
        `POLICE_ROUTING_ENABLED`, which is one explicit setting, owned by whoever
        runs the deployment.

        What this still buys is that the log says which situation you are in. The
        failure worth naming is defect 31's: routing was once unconditionally on
        while every row held `noorlabib@iut-dhaka.edu`, so every SOS test emailed
        an uninvolved third party. One shared address plus routing on is exactly
        that shape -- so when it happens, `_nearest_police_station` logs the
        address it is about to use and says it is a test value. Loud is the right
        answer there; silent refusal was not.
        """
        with_email = [s for s in self.police_stations if (s.get("email") or "").strip()]
        if len(with_email) <= 1:
            return False

        distinct = {(s.get("email") or "").strip().lower() for s in with_email}
        if len(distinct) > 1:
            logger.info(
                "Police contacts look per-station: %d distinct address(es) across "
                "%d rows.",
                len(distinct),
                len(with_email),
            )
            return True

        logger.warning(
            "⚠️  All %d police station rows share ONE email address (%s). Police "
            "routing will still work if POLICE_ROUTING_ENABLED is on -- every SOS "
            "in Dhaka reaches that one inbox, whichever thana is nearest. Fine for "
            "testing with your own address; replace it with real per-thana "
            "contacts before anyone else depends on it (defect 17).",
            len(with_email),
            next(iter(distinct)),
        )
        return False

    def _build_dhaka_email_map(self) -> dict[str, str]:
        """
        Dhaka city station name -> email.

        **Dhaka rows only, and that is correctness rather than scoping taste.**
        Station names repeat across districts -- the CSV has a `Kotwali Police
        Station` in Dhaka, another in Chattogram and another in Rajshahi -- while
        `nearest_thana` only ever returns a Dhaka city name. A map built from all
        607 rows would hand back whichever Kotwali `csv.DictReader` reached last,
        and the bug would be invisible because the name would look right.
        """
        emails: dict[str, str] = {}
        for station in self.police_stations:
            if (station.get("district") or "").strip() != DHAKA_CITY_DISTRICT:
                continue
            name = (station.get("name") or "").strip()
            email = (station.get("email") or "").strip()
            if name and email and name not in emails:
                emails[name] = email
        logger.info("Police routing: %d Dhaka city stations have an email", len(emails))
        return emails

    # `_haversine_distance` lived here and is gone. It was the second copy of the
    # same formula in this repo -- `casework/thana.py` has the other -- and the
    # one place that called it now asks `thana.nearest_thana` instead, so the
    # station emailed and the station printed on the GD cannot disagree.

    def _nearest_police_station(self, lat: float, lon: float) -> dict | None:
        """
        The one thana an SOS from this location should reach, or None.

        Returns `{"name", "email", "distance_km"}`. Gated on
        `POLICE_ROUTING_ENABLED` and nothing else.

        **One station, not every station within a radius.** The old version
        collected every email inside 5 km, which in central Dhaka is six or seven
        thanas: an incident has exactly one officer-in-charge with jurisdiction,
        and six thanas each assuming another is responding is a worse outcome than
        one being told. "Nearest" is also what the owner asked for.

        **The station is chosen by `casework.thana.nearest_thana`, deliberately.**
        That function already carries the three refusals this needs -- outside
        Bangladesh, outside Dhaka city by more than `MAX_PLAUSIBLE_KM`, and the
        five rows whose coordinates the CSV itself marks `legacy -- unverified`
        (`Turag`'s sits 1.7 km from Rampura) -- and duplicating distance logic here
        is how the GD's printed thana and the emailed thana drift apart. Sharing it
        means they are the same station by construction, which is the property that
        matters: the alert reaches the thana the victim will later walk into.

        What this does *not* do is claim the police will act on it. DEMO_PLAN 7.2
        still stands on the substance -- there is no police API, and a cognizable
        offence needs the applicant at the thana in person. An email to a thana
        inbox is a notification, not a filing, and §7.2's point was about filing.
        """
        if not settings.POLICE_ROUTING_ENABLED:
            logger.info(
                "Police routing disabled (POLICE_ROUTING_ENABLED=false); "
                "alerting emergency contacts only"
            )
            return None

        thana = nearest_thana(lat, lon)
        if thana is None:
            logger.info(
                "No Dhaka city thana within %.0f km of (%s, %s) -- SOS goes to "
                "emergency contacts only. The station list is Dhaka city, so an "
                "SOS from elsewhere in Bangladesh has no thana to route to.",
                MAX_PLAUSIBLE_KM,
                lat,
                lon,
            )
            return None

        email = self._dhaka_station_emails.get(thana.name)
        if not email:
            logger.warning(
                "Nearest thana is %s (%.1f km) but it has no email in "
                "police_stations.csv -- SOS goes to emergency contacts only.",
                thana.name,
                thana.distance_km,
            )
            return None

        if not self._contacts_are_per_station:
            logger.warning(
                "⚠️  Police routing is ON and every CSV row shares one address, so "
                "this SOS for %s goes to %s. That is a test address, not the "
                "thana's (defect 17). Real per-thana contacts are a data change.",
                thana.name,
                email,
            )

        logger.info(
            "SOS police routing: nearest thana is %s, %.1f km away -- alerting %s",
            thana.name,
            thana.distance_km,
            email,
        )
        return {"name": thana.name, "email": email, "distance_km": thana.distance_km}

    async def trigger_sos_alert(
        self,
        user_id: str,
        user_name: str,
        location: dict,
        video_file: Optional[UploadFile],
        db: AsyncSession,
        voice_activated: bool = False,
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
            
            # 2. Route to the thana whose jurisdiction this location falls in.
            #
            # Defect 17. One station, from the caller's live coordinates -- the
            # same station `casework/thana.py` prints on their General Diary.
            lat = float(location.get('latitude', 0))
            lon = float(location.get('longitude', 0))

            station = self._nearest_police_station(lat, lon)
            police_emails = [station["email"]] if station else []
            if police_emails:
                recipient_emails.extend(police_emails)

            # Remove duplicates. Worth keeping even with one station: while the
            # CSV's contact column is the owner's own test address, the station
            # and one of the emergency contacts can be the same inbox, and
            # sending the same alert twice reads as a bug to whoever receives it.
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
                voice_activated=voice_activated,
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
                # The thana's name, so the app can say *which* station was told
                # rather than only how many. A count of 1 is not reassuring; a
                # name is. None when no station was notified.
                "police_station": station["name"] if station else None,
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
        voice_activated: bool = False,
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
                # B8 / S18. Passed through from the client rather than inferred:
                # a hot-word trigger and a button press are the same request
                # otherwise, and nothing server-side can tell them apart.
                #
                # It is the client's claim about its own behaviour, which is worth
                # being explicit about -- a modified client could assert it
                # falsely. That is acceptable because nothing is authorised on
                # this flag: it changes one boolean in the history screen, not
                # who gets emailed. Treat it as provenance, not as a credential.
                voice_activated=voice_activated,
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
