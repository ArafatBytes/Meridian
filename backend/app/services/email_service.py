"""
Email service for sending emergency notifications
"""
import asyncio
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from typing import List, Optional
from pathlib import Path
from app.core.config import settings
from datetime import datetime, UTC

from app.scoring.decay import DHAKA_TZ

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# The message
# -----------------------------------------------------------------------------
#
# Everything below is table layout with inline styles, and that is not a stylistic
# preference. The version this replaces put its rules in a `<style>` block and
# used `display: grid`. Gmail strips most of a `<style>` block and supports no
# grid at all, so the layout that survived to the inbox was whatever the stacked
# fallback happened to look like.
#
# The visible cost was the one element that mattered: the map button rendered as
# dark blue link text on a near-black box, effectively unreadable, because Gmail
# recolours `<a>` text and the class that said otherwise had been stripped.
#
# So: no stylesheet, no grid, nothing a mail client has to be talked into.

#: Bangladesh's national emergency number.
EMERGENCY_NUMBER = "999"

_SANS = "'Helvetica Neue', Helvetica, Arial, sans-serif"


def _dhaka_now() -> datetime:
    """
    Now, in Dhaka.

    The old template called `datetime.now()`, which in the API container is
    **UTC** -- the image sets no timezone -- and then printed it with no zone
    label at all. A contact in Dhaka opening an alert sent at 16:55 read
    "10:55 AM" and had every reason to think it was six hours stale. In an
    emergency message that is not a formatting detail.

    `DHAKA_TZ` comes from `scoring.decay`, where it is a fixed +06:00 offset
    rather than a `ZoneInfo` lookup, for the reason documented there: the lookup
    raises on a stock Windows box, and Bangladesh has not observed DST since
    2009.
    """
    return datetime.now(UTC).astimezone(DHAKA_TZ)


def _format_when(at: datetime) -> str:
    """
    "4:55 PM, Sat 11 Oct 2026 (Dhaka time)".

    Built by hand rather than with `%-I`/`%-d`, which strip the leading zero on
    glibc and raise `ValueError` on Windows. The API runs in a Linux container
    and the tests run on the developer's Windows box, so a platform-specific
    format string is a green suite and a broken alert.

    The zone is named, not implied. A bare clock time in an emergency message
    is a question, and the reader has no way to answer it.
    """
    hour = at.hour % 12 or 12
    return f"{hour}:{at:%M %p}, {at:%a} {at.day} {at:%b %Y} (Dhaka time)"


def _maps_url(lat, lon) -> str:
    """Full precision in the link, whatever is shown on screen."""
    return f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"


def _coords(lat, lon) -> str:
    """
    Coordinates as a person should read them.

    Five decimal places is about a metre. The seven the device reports is about
    a centimetre, which is a precision a phone does not have and digits a human
    has to read past to find the ones that matter.
    """
    try:
        return f"{float(lat):.5f}, {float(lon):.5f}"
    except (TypeError, ValueError):
        return "not available"


def _sos_text(user_name: str, when: str, lat, lon, has_video: bool) -> str:
    """
    The plain-text half.

    Not decoration: a `multipart/alternative` without it means any client that
    cannot render HTML shows the markup instead of the message, and some of the
    cheapest handsets in the country are exactly that client.
    """
    lines = [
        f"EMERGENCY ALERT - {user_name} needs help",
        "",
        f"Sent {when}",
        f"Location  {_coords(lat, lon)}",
    ]
    if lat is not None and lon is not None:
        lines.append(f"Map       {_maps_url(lat, lon)}")
    lines += [
        "",
        "WHAT TO DO NOW",
        f"1. Try calling {user_name}.",
        f"2. If you cannot reach them, call {EMERGENCY_NUMBER} -- the national",
        "   emergency number -- and read out the location above.",
        "3. Pass the map link to whoever is closest to them.",
        "",
    ]
    if has_video:
        lines.append("A video recorded at the moment of the alert is attached.")
        lines.append("")
    lines.append("Automated message from Meridian. You are receiving it because")
    lines.append(f"{user_name} listed you as an emergency contact.")
    return "\n".join(lines)


def _sos_html(user_name: str, when: str, lat, lon, has_video: bool) -> str:
    """The HTML half. Tables and inline styles only -- see the note above."""
    coords = _coords(lat, lon)
    locatable = lat is not None and lon is not None

    # The inbox preview line. Without one, the list shows whatever text comes
    # first, which was the words "SOS Emergency Alert" repeated back -- telling
    # somebody glancing at a notification nothing they did not already see.
    preheader = f"{coords} - sent {when}. Open the map, then call."

    button = ""
    if locatable:
        button = f"""
            <table role="presentation" cellpadding="0" cellspacing="0" border="0" align="center" style="margin:0 auto;">
              <tr>
                <td bgcolor="#B91C1C" style="border-radius:6px;">
                  <a href="{_maps_url(lat, lon)}"
                     style="display:block;padding:16px 32px;font-family:{_SANS};font-size:17px;font-weight:bold;color:#ffffff;text-decoration:none;border-radius:6px;">
                    <span style="color:#ffffff;">Open this location on a map</span>
                  </a>
                </td>
              </tr>
            </table>"""

    video_row = ""
    if has_video:
        video_row = f"""
              <tr>
                <td style="padding:0 32px 8px 32px;">
                  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
                         style="background-color:#F8FAFC;border:1px solid #E2E8F0;border-radius:6px;">
                    <tr>
                      <td style="padding:14px 16px;font-family:{_SANS};font-size:14px;color:#334155;">
                        A video recorded at the moment of the alert is attached to this email.
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>"""

    steps = [
        f"Try calling <strong>{user_name}</strong>.",
        f"If you cannot reach them, call <strong>{EMERGENCY_NUMBER}</strong> "
        "and read out the location above.",
        "Pass the map link to whoever is closest to them.",
    ]
    step_rows = "".join(
        f"""
                    <tr>
                      <td width="28" valign="top" style="padding:6px 0;font-family:{_SANS};font-size:15px;font-weight:bold;color:#B91C1C;">{i}.</td>
                      <td valign="top" style="padding:6px 0;font-family:{_SANS};font-size:15px;line-height:22px;color:#334155;">{step}</td>
                    </tr>"""
        for i, step in enumerate(steps, start=1)
    )

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background-color:#F1F5F9;">
  <div style="display:none;max-height:0;overflow:hidden;mso-hide:all;font-size:1px;line-height:1px;color:#F1F5F9;">{preheader}</div>

  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#F1F5F9;">
    <tr>
      <td align="center" style="padding:24px 12px;">

        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
               style="max-width:600px;background-color:#ffffff;border-radius:10px;overflow:hidden;">

          <!-- Who, and when. One block, because they are one fact. -->
          <tr>
            <td bgcolor="#991B1B" style="padding:28px 32px;">
              <div style="font-family:{_SANS};font-size:13px;font-weight:bold;letter-spacing:1.5px;color:#FCA5A5;text-transform:uppercase;">
                Emergency alert
              </div>
              <div style="font-family:{_SANS};font-size:26px;line-height:34px;font-weight:bold;color:#ffffff;padding-top:6px;">
                {user_name} needs help
              </div>
              <div style="font-family:{_SANS};font-size:14px;color:#FECACA;padding-top:8px;">
                Sent {when}
              </div>
            </td>
          </tr>

          <!-- The one action, first. It used to sit below a table of
               attributes, which is the wrong way round: nobody reading this
               needs the coordinates before they need the map. -->
          <tr>
            <td align="center" style="padding:28px 32px 20px 32px;">{button}
            </td>
          </tr>

          <tr>
            <td style="padding:0 32px 20px 32px;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
                     style="background-color:#F8FAFC;border-radius:6px;">
                <tr>
                  <td style="padding:16px;">
                    <div style="font-family:{_SANS};font-size:11px;font-weight:bold;letter-spacing:1px;color:#64748B;text-transform:uppercase;">
                      Location
                    </div>
                    <div style="font-family:{_SANS};font-size:17px;font-weight:bold;color:#0F172A;padding-top:4px;">
                      {coords}
                    </div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
{video_row}
          <tr>
            <td style="padding:12px 32px 8px 32px;">
              <div style="font-family:{_SANS};font-size:11px;font-weight:bold;letter-spacing:1px;color:#64748B;text-transform:uppercase;padding-bottom:4px;">
                What to do now
              </div>
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">{step_rows}
              </table>
            </td>
          </tr>

          <tr>
            <td style="padding:24px 32px 28px 32px;">
              <div style="border-top:1px solid #E2E8F0;padding-top:16px;font-family:{_SANS};font-size:12px;line-height:18px;color:#64748B;">
                Automated message from <strong style="color:#475569;">Meridian</strong>.
                You are receiving it because {user_name} listed you as an emergency contact.
              </div>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


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
            lat = location.get('latitude')
            lon = location.get('longitude')
            when = _format_when(_dhaka_now())
            has_video = bool(video_path)

            # mixed(alternative(plain, html), video) -- the structure a client
            # needs to pick the body it can render AND still see the attachment.
            # The old message was a bare `mixed` with one HTML part, so a client
            # without HTML had nothing to fall back to.
            msg = MIMEMultipart('mixed')
            msg['From'] = self.from_email
            # Was `msg['To'] = ', '.join(to_emails)`, which showed every
            # emergency contact's address to every other one. See `_address`.
            self._address(msg, to_emails)
            msg['Subject'] = f'EMERGENCY: {user_name} needs help - {when}'

            alternative = MIMEMultipart('alternative')
            # utf-8 on both parts: the default is us-ascii, which raises on a
            # Bangla name the moment somebody signs up with one.
            alternative.attach(
                MIMEText(_sos_text(user_name, when, lat, lon, has_video), 'plain', 'utf-8')
            )
            alternative.attach(
                MIMEText(_sos_html(user_name, when, lat, lon, has_video), 'html', 'utf-8')
            )
            msg.attach(alternative)

            # Attach the video, off the event loop.
            #
            # Same reason as the send below, smaller magnitude: reading ~16 MB from
            # disk and base64-encoding it to ~22 MB is I/O plus CPU on the single
            # thread every other request shares. Not the 2-minute freeze the SMTP
            # call caused, but not free either, and it is the same mistake.
            if video_path:
                part = await asyncio.to_thread(self._build_video_part, video_path)
                if part is not None:
                    msg.attach(part)
                    logger.info(f"Video attached: {video_path}")

            # Send email, off the event loop.
            #
            # `smtplib` is synchronous. Calling it directly inside an `async def`
            # blocks the single thread FastAPI's event loop runs on, which means
            # it does not block this request -- it blocks EVERY request. Measured
            # on a real SOS with a 16.45 MB video: 2 minutes 34 seconds during
            # which /health timed out and the map could not load risk flags. On
            # stage that is the demo freezing while beat 9 sends.
            #
            # `asyncio.to_thread` hands the blocking call to a worker thread. The
            # SOS still takes as long as the upload takes; everything else keeps
            # working while it does.
            await asyncio.to_thread(self._send_blocking, msg)

            logger.info(f"SOS alert sent to {len(to_emails)} recipients")
            return True

        except Exception as e:
            logger.error(f"Failed to send SOS email: {e}")
            return False

    async def send_guardian_message(
        self,
        to_emails: list[str],
        subject: str,
        body: str,
        html: str | None = None,
    ) -> bool:
        """
        One of JG3's journey messages, to a guardian or to every contact.

        Deliberately not `send_sos_alert` with different words. That method is
        subject-lined `EMERGENCY: {name} needs help`, builds its own template
        styled for an emergency, and carries an attachment -- all correct for
        somebody pressing the button, all wrong for *"Rina started her journey
        home"*. A guardian who gets two emergency-shaped emails a night filters
        them, and then the one that matters lands in a folder nobody opens.

        `multipart/alternative`, and the plain part is not a formality: a client
        that cannot render HTML shows the markup instead of the message, and
        some of the cheapest handsets in the country are exactly that client.
        The two parts carry the same sentences.

        The wording is not decided here -- `app/journeys/guardian.py` owns both
        halves and is unit-tested to the character, including the rule that only
        the escalation may carry a location. This takes rendered strings because
        a transport that knew which message it was carrying would be a second
        place for that rule to live.
        """
        try:
            msg = MIMEMultipart("alternative")
            msg["From"] = self.from_email
            # One line, always. `guardian.py` already collapses the names it
            # renders, and this is the second half of the same rule, here
            # because this is where a header is actually written: a newline in a
            # header value makes Python raise `HeaderParseError` when the
            # message is flattened, which this method would catch and report as
            # a failed send -- after the caller had already marked the notice as
            # sent. One stray newline in a display name would mean a guardian
            # silently never hears anything again.
            msg["Subject"] = " ".join(subject.split())
            self._address(msg, to_emails)
            # Plain first, then HTML. `multipart/alternative` is ordered
            # least-preferred to most, and a client that gets it the other way
            # round shows the text part to somebody whose phone could have
            # rendered the other one.
            msg.attach(MIMEText(body, "plain", "utf-8"))
            if html:
                msg.attach(MIMEText(html, "html", "utf-8"))

            # Off the event loop, for the reason `send_sos_alert` documents at
            # length: `smtplib` is synchronous and blocking it blocks every
            # request, not just this one.
            await asyncio.to_thread(self._send_blocking, msg)
            logger.info("Journey message sent to %d recipient(s)", len(to_emails))
            return True
        except Exception as e:
            # Returned, not raised. The caller is the minute sweep, and an
            # agent that dies on a bad address stops escalating every other
            # journey in the same run.
            logger.error(f"Failed to send journey message: {e}")
            return False

    def _address(self, msg: MIMEMultipart, to_emails: list[str]) -> None:
        """
        Put the recipients on the message without showing them to each other.

        One recipient goes in `To` -- it is their own address, and a message
        addressed to nobody looks like bulk mail to both the reader and the
        filter.

        **More than one goes in `Bcc`.** `send_sos_alert` has always done
        `msg['To'] = ', '.join(to_emails)`, which shows every emergency contact's
        address to every other one. It did not matter much while the only caller
        was an SOS to people who mostly know each other; it matters at JG3's
        `full_sos`, which mails somebody's whole contact list -- a brother, an
        employer and a neighbour learning each other's addresses because she was
        late home.

        `smtplib.send_message` reads `Bcc` to decide the envelope and strips the
        header before transmission, so this is sufficient and needs no separate
        recipient list.
        """
        if len(to_emails) == 1:
            msg["To"] = to_emails[0]
            return
        msg["To"] = self.from_email
        msg["Bcc"] = ", ".join(to_emails)

    def _build_video_part(self, video_path: str) -> MIMEBase | None:
        """
        Read a video from disk and wrap it as a base64 MIME attachment.

        **Synchronous. Only call through `asyncio.to_thread`.**

        Returns None rather than raising if the file is missing or unreadable: an
        SOS with no video attached still has to go out. Losing the evidence is bad;
        losing the alert is worse.
        """
        try:
            if not Path(video_path).exists():
                logger.warning(f"Video not found, sending alert without it: {video_path}")
                return None
            with open(video_path, 'rb') as attachment:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment.read())
            encoders.encode_base64(part)
            part.add_header(
                'Content-Disposition',
                f'attachment; filename=sos_video_{Path(video_path).name}'
            )
            return part
        except Exception as e:
            logger.error(f"Failed to attach video: {e}")
            return None

    def _send_blocking(self, msg: MIMEMultipart) -> None:
        """
        The actual SMTP conversation. **Synchronous, and must stay that way.**

        Separated out so there is exactly one blocking call and it is obvious. Only
        ever call this through `asyncio.to_thread` -- calling it directly from an
        async function reintroduces the freeze described above.

        A timeout is set deliberately. Without one, `smtplib` inherits the system
        default socket timeout, which on most hosts is none at all: an SMTP server
        that accepts the connection and then stalls would hold the thread forever,
        and the caller would wait forever with it. 120 seconds is generous for a
        25 MB attachment on a slow connection and still finite.
        """
        with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=120) as server:
            server.starttls()
            server.login(self.smtp_user, self.smtp_password)
            server.send_message(msg)


# Singleton instance
email_service = EmailService()
