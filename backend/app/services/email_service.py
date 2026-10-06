"""
Email service for sending emergency notifications
"""
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from typing import List, Optional
from pathlib import Path
from app.core.config import settings
from datetime import datetime

logger = logging.getLogger(__name__)


class EmailService:
    def __init__(self):
        self.smtp_server = settings.SMTP_SERVER
        self.smtp_port = settings.SMTP_PORT
        self.smtp_user = settings.SMTP_USER
        self.smtp_password = settings.SMTP_PASSWORD
        self.from_email = settings.FROM_EMAIL

    async def send_sos_alert(
        self,
        to_emails: List[str],
        user_name: str,
        location: dict,
        video_path: Optional[str] = None
    ) -> bool:
        """
        Send SOS alert email with optional video attachment
        """
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.from_email
            msg['To'] = ', '.join(to_emails)
            msg['Subject'] = f'🚨 EMERGENCY ALERT - {user_name} needs help!'

            # Email body
            # Email body
            body = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{
                        font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
                        line-height: 1.6;
                        color: #333333;
                        margin: 0;
                        padding: 0;
                        background-color: #f4f4f5;
                    }}
                    .container {{
                        max-width: 600px;
                        margin: 20px auto;
                        background-color: #ffffff;
                        border-radius: 8px;
                        overflow: hidden;
                        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
                    }}
                    .header {{
                        background-color: #991B1B; /* Classic Deep Red */
                        color: #ffffff;
                        padding: 30px 20px;
                        text-align: center;
                    }}
                    .header h1 {{
                        margin: 0;
                        font-size: 24px;
                        font-weight: 500;
                        text-transform: uppercase;
                        letter-spacing: 1px;
                    }}
                    .content {{
                        padding: 40px 30px;
                    }}
                    .alert-box {{
                        background-color: #FEF2F2;
                        border-left: 4px solid #991B1B;
                        padding: 15px;
                        margin-bottom: 25px;
                        color: #7F1D1D;
                    }}
                    .info-grid {{
                        display: grid;
                        grid-template-columns: 1fr;
                        gap: 15px;
                        margin-bottom: 30px;
                    }}
                    .info-item {{
                        background: #F8FAFC;
                        padding: 15px;
                        border-radius: 6px;
                    }}
                    .label {{
                        font-size: 12px;
                        text-transform: uppercase;
                        color: #64748B;
                        margin-bottom: 5px;
                        display: block;
                    }}
                    .value {{
                        font-size: 16px;
                        font-weight: 600;
                        color: #0F172A;
                    }}
                    .btn {{
                        display: inline-block;
                        background-color: #0F172A;
                        color: #ffffff;
                        padding: 12px 24px;
                        text-decoration: none;
                        border-radius: 4px;
                        font-weight: 500;
                        text-align: center;
                        margin-top: 10px;
                    }}
                    .footer {{
                        background-color: #F1F5F9;
                        padding: 20px;
                        text-align: center;
                        font-size: 12px;
                        color: #64748B;
                        border-top: 1px solid #E2E8F0;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>SOS Emergency Alert</h1>
                    </div>
                    
                    <div class="content">
                        <div class="alert-box">
                            <strong>{user_name}</strong> has triggered an emergency alert via Meridian.
                        </div>

                        <div class="info-grid">
                            <div class="info-item">
                                <span class="label">Time</span>
                                <span class="value">{datetime.now().strftime('%I:%M %p, %d %B %Y')}</span>
                            </div>
                            <div class="info-item">
                                <span class="label">Location Coordinates</span>
                                <span class="value">{location.get('latitude', 'N/A')}, {location.get('longitude', 'N/A')}</span>
                            </div>
                        </div>

                        <div style="text-align: center;">
                            <a href="https://www.google.com/maps?q={location.get('latitude')},{location.get('longitude')}" class="btn">
                                View Precise Location on Map
                            </a>
                        </div>
                        
                        {f'<p style="margin-top: 30px; font-style: italic; color: #4B5563;">📎 A video recording of the situation is attached to this email.</p>' if video_path else ''}
                    </div>

                    <div class="footer">
                        <p>This is an automated message from <strong>Meridian Safety System</strong>.</p>
                        <p>Please contact local emergency services if the situation warrants immediate professional intervention.</p>
                    </div>
                </div>
            </body>
            </html>
            """

            msg.attach(MIMEText(body, 'html'))

            # Attach video if provided
            if video_path and Path(video_path).exists():
                try:
                    with open(video_path, 'rb') as attachment:
                        part = MIMEBase('application', 'octet-stream')
                        part.set_payload(attachment.read())
                        encoders.encode_base64(part)
                        part.add_header(
                            'Content-Disposition',
                            f'attachment; filename=sos_video_{Path(video_path).name}'
                        )
                        msg.attach(part)
                        logger.info(f"Video attached: {video_path}")
                except Exception as e:
                    logger.error(f"Failed to attach video: {e}")

            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)

            logger.info(f"SOS alert sent to {len(to_emails)} recipients")
            return True

        except Exception as e:
            logger.error(f"Failed to send SOS email: {e}")
            return False


# Singleton instance
email_service = EmailService()
