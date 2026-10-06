import logging
import os
import tempfile
import csv
import math
from typing import List, Optional, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import UploadFile
from app.models.emergency_contact import EmergencyContact
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
        """Get emails of police stations within radius"""
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

            # Clean up temporary video file
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
                "police_stations_found": len(police_emails)
            }

        except Exception as e:
            logger.error(f"Error triggering SOS alert: {e}")
            return {
                "success": False,
                "message": str(e),
                "contacts_notified": 0
            }

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
