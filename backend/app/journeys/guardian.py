"""
What the second person is told, and what they are not. JG3.

Three messages, and the difference between them is the whole privacy design of
this phase. `JOURNEY_GUARDIAN.md` §2 states the promise in one sentence:

    He only learns *where* she is if something actually goes wrong. She gets
    watched over without being surveilled.

This module is that sentence made into types. `started_message` and
`arrived_message` **have no parameter that can carry a position** -- not "do not
pass one", but *cannot*, so the rule cannot be broken by a later edit that adds
a helpful detail to an email template. Only `escalation_message` accepts a
`Position`, and the caller has to have one to pass.

## Why pure, and why here rather than in the email service

`email_service.py` owns SMTP: connections, MIME parts, attachments, retries. It
is untestable without a mail server and it should stay that way. What goes *in*
the message is a product decision with a privacy rule attached, and that is
testable to the character -- so it lives here, returns plain text, and
`tests/invariants/test_journey_guardian.py` asserts on the rendered strings.

The split also means the rule survives a change of channel. JG3 ships email
because the SOS pipeline already has it; `JOURNEY_GUARDIAN.md` says SMS is what
a guardian actually reads at 10pm. When that happens, the transport changes and
this file does not.

## On the tone of the first two

A message that says *"EMERGENCY: Rina needs help"* is correct for an SOS and
wrong for somebody leaving the house. `email_service.py` has exactly one
template today and that is its subject line. Two notices a night that read like
emergencies will be filtered, muted, or will teach the guardian that Meridian
cries wolf -- and then the one that matters arrives in a folder nobody opens.

So: the first two are deliberately dull, and only the third looks urgent.

## Two halves, one set of sentences

Each message renders as plain text *and* as HTML. The HTML exists because the
plain-text notices looked like a system log next to the SOS mail, and a guardian
decides in about a second whether an email is worth reading. The plain text
stays because `multipart/alternative` without it means a client that cannot
render HTML shows the markup instead of the message, and some of the cheapest
handsets in the country are exactly that client.

The two halves carry **the same sentences**. The HTML is a layout of the facts
the text already states, never an extra fact -- which is what keeps the privacy
rule above testable: `test_neither_calm_notice_renders_a_coordinate` reads both.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from html import escape
from typing import Final
from zoneinfo import ZoneInfo

__all__ = [
    "GuardianMessage",
    "Position",
    "arrived_message",
    "escalation_message",
    "started_message",
]


DHAKA: Final = ZoneInfo("Asia/Dhaka")
"""
Every time in a guardian's message is Dhaka local.

The server's clock is UTC and the guardian is a person in Bangladesh reading
their phone. A deadline shown six hours early is not a formatting nit: it is the
difference between "she is an hour late" and "she is fine", read by somebody
deciding whether to get in a car. `email_service.py::_dhaka_now` already does
this for the SOS mail, for the same reason.
"""


@dataclass(frozen=True, slots=True)
class Position:
    """
    A point the phone reported, and when it reported it.

    The timestamp is **not optional**, which is the point of the type. A
    coordinate with no time is the half-truth that sends somebody to where
    she was forty minutes ago believing it is where she is now, and
    `journeys_position_paired` enforces the same pairing in the table.
    """

    latitude: float
    longitude: float
    at: datetime


@dataclass(frozen=True, slots=True)
class GuardianMessage:
    """
    One rendered message. Subject and body, and nothing about delivery.

    `urgent` is carried rather than inferred from the subject, so the transport
    can decide what to do with it -- a header, a different template, eventually
    an SMS instead of an email -- without parsing English.

    `html` is the same message laid out, never a different one. A transport that
    has no HTML channel (SMS, a push payload) ignores it and loses no facts.
    """

    subject: str
    body: str
    html: str = ""
    urgent: bool = False


def _when(at: datetime) -> str:
    """A time a person reads, in their own timezone."""
    return at.astimezone(DHAKA).strftime("%-I:%M %p") if _supports_dash() else (
        at.astimezone(DHAKA).strftime("%I:%M %p").lstrip("0")
    )


def _supports_dash() -> bool:
    """
    `%-I` is a glibc extension and raises on Windows.

    The backend runs in Linux containers and the tests run on a Windows laptop,
    which is exactly the split that makes this worth handling rather than
    assuming. Checked once per call and not cached: this is three emails a
    journey, not a hot path.
    """
    try:
        datetime(2026, 1, 1, 9, 0).strftime("%-I")
    except ValueError:
        return False
    return True


def _coords(position: Position) -> str:
    """
    Five decimal places, about a metre.

    Matching `email_service.py::_coords` deliberately: the seven a device
    reports is about a centimetre, a precision no phone has, and digits a
    worried person has to read past to find the ones that matter.
    """
    return f"{position.latitude:.5f}, {position.longitude:.5f}"


def _maps_url(position: Position) -> str:
    """Full precision in the link, whatever is shown in the text."""
    return (
        "https://www.google.com/maps/search/?api=1&query="
        f"{position.latitude},{position.longitude}"
    )


def _oneline(text: str, *, limit: int) -> str:
    """
    One line, collapsed and capped. Every name and place name goes through this.

    Found by rendering a real row rather than a fixture. A destination tapped
    from the map carries whatever the POI is called, and the one on that journey
    was::

        National Museum of
        Science and Technology
        জাতীয় বিজ্ঞান ও
        প্রযুক্তি জাদুঘর

    — four lines, which turned the most important sentence in the escalation email
    into something that reads as broken software at the moment a guardian most
    needs to trust it.

    The cap matters for the same reason: these strings reach a **subject line**
    (the traveller's name does), and `destination_label` is only bounded at 200
    characters by the schema.

    And there is a failure mode behind the tidiness. A newline in a header is
    not an injection — Python raises `HeaderParseError` rather than flattening it
    — but raising is worse than it sounds here: `send_guardian_message` catches,
    returns False, and the notice has **already been marked sent** (mark before
    send, so a crash sends nothing rather than sending twice). So one newline in
    a display name would mean that person's guardian is silently never told
    anything, for every journey, for ever. Collapsing here is what makes that
    unreachable, and the transport strips its subject as well.
    """
    collapsed = " ".join(text.split())
    if len(collapsed) <= limit:
        return collapsed
    # Cut on a word boundary where there is one close enough, so a truncated
    # place name reads as a place name rather than as a corrupted string.
    head = collapsed[: limit - 1]
    space = head.rfind(" ")
    if space >= limit - 20:
        head = head[:space]
    return head.rstrip() + "…"


#: A person's name, as it reaches a subject line.
NAME_LIMIT: Final = 60

#: A place name, as it reaches a sentence. `destination_label` is capped at 200
#: by the wire schema, which is a sane bound for a database column and far too
#: long for "they were heading for X".
PLACE_LIMIT: Final = 90


# ---------------------------------------------------------------------------
# The HTML half
# ---------------------------------------------------------------------------
#
# Tables and inline styles only. The rules come from `email_service.py`, which
# learned them the expensive way: Gmail strips most of a `<style>` block and
# supports no `display:grid`, so a stylesheet that works in a browser preview
# arrives in the inbox as whatever the stacked fallback happens to look like.
# The visible cost there was the map button rendering as dark blue link text on
# a near-black box, which is the one element in an emergency mail that has to
# work.
#
# Not shared with `_sos_html`. That template is a single fixed message with an
# attachment and a different palette; factoring one shell out of both would mean
# editing the SOS mail -- the one thing in this product that is already proven
# on a real phone -- to make a cosmetic change to these three. The shared part
# is a dozen lines of table chrome, and the comment above is the thing that
# actually needed to be in one place.

_SANS: Final = "'Helvetica Neue', Helvetica, Arial, sans-serif"


@dataclass(frozen=True, slots=True)
class _Palette:
    """
    The colours of one message's header, and the one accent used below it.

    Carried as data because the palette *is* the tone, and the tone is the
    product decision this module exists to protect: the first two notices must
    not look like the third. A guardian who gets a red-banded email about
    somebody leaving the house learns to ignore red-banded emails.
    """

    band: str
    eyebrow: str
    subtitle: str
    accent: str


#: Slate. "This is information." Nothing here is wrong.
_CALM: Final = _Palette(band="#1E293B", eyebrow="#94A3B8", subtitle="#CBD5E1", accent="#475569")

#: Green, and the only message in the set that is good news.
_SAFE: Final = _Palette(band="#166534", eyebrow="#86EFAC", subtitle="#BBF7D0", accent="#15803D")

#: The SOS mail's reds, deliberately. By the time this is sent, the reader
#: should recognise the shape of it.
_ALERT: Final = _Palette(band="#991B1B", eyebrow="#FCA5A5", subtitle="#FECACA", accent="#B91C1C")


def _fact(label: str, value: str, note: str = "") -> str:
    """The grey box: one labelled fact, large enough to read at a glance."""
    extra = (
        f"""
                    <div style="font-family:{_SANS};font-size:13px;line-height:19px;color:#475569;padding-top:6px;">{note}</div>"""
        if note
        else ""
    )
    return f"""
          <tr>
            <td style="padding:0 32px 20px 32px;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
                     style="background-color:#F8FAFC;border-radius:6px;">
                <tr>
                  <td style="padding:16px;">
                    <div style="font-family:{_SANS};font-size:11px;font-weight:bold;letter-spacing:1px;color:#64748B;text-transform:uppercase;">
                      {label}
                    </div>
                    <div style="font-family:{_SANS};font-size:17px;font-weight:bold;color:#0F172A;padding-top:4px;">
                      {value}
                    </div>{extra}
                  </td>
                </tr>
              </table>
            </td>
          </tr>"""


def _note(text: str) -> str:
    """A bordered aside. Used for the sentence that qualifies the fact above it."""
    return f"""
          <tr>
            <td style="padding:0 32px 20px 32px;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
                     style="background-color:#F8FAFC;border:1px solid #E2E8F0;border-radius:6px;">
                <tr>
                  <td style="padding:14px 16px;font-family:{_SANS};font-size:14px;line-height:21px;color:#334155;">
                    {text}
                  </td>
                </tr>
              </table>
            </td>
          </tr>"""


def _points(heading: str, items: list[str], palette: _Palette) -> str:
    """A short list under a small-caps heading. Dots, not numbers."""
    rows = "".join(
        f"""
                    <tr>
                      <td width="20" valign="top" style="padding:6px 0;font-family:{_SANS};font-size:15px;font-weight:bold;color:{palette.accent};">&bull;</td>
                      <td valign="top" style="padding:6px 0;font-family:{_SANS};font-size:15px;line-height:22px;color:#334155;">{item}</td>
                    </tr>"""
        for item in items
    )
    return f"""
          <tr>
            <td style="padding:4px 32px 8px 32px;">
              <div style="font-family:{_SANS};font-size:11px;font-weight:bold;letter-spacing:1px;color:#64748B;text-transform:uppercase;padding-bottom:4px;">
                {heading}
              </div>
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">{rows}
              </table>
            </td>
          </tr>"""


def _button(url: str, label: str, palette: _Palette) -> str:
    """
    The one action, and it goes first.

    `<span>` inside the `<a>` for the reason `email_service.py` documents:
    Gmail recolours link text, and the colour has to be stated on an element it
    will not override or the button is unreadable.
    """
    return f"""
          <tr>
            <td align="center" style="padding:28px 32px 20px 32px;">
              <table role="presentation" cellpadding="0" cellspacing="0" border="0" align="center" style="margin:0 auto;">
                <tr>
                  <td bgcolor="{palette.accent}" style="border-radius:6px;">
                    <a href="{url}"
                       style="display:block;padding:16px 32px;font-family:{_SANS};font-size:17px;font-weight:bold;color:#ffffff;text-decoration:none;border-radius:6px;">
                      <span style="color:#ffffff;">{label}</span>
                    </a>
                  </td>
                </tr>
              </table>
            </td>
          </tr>"""


def _shell(
    *,
    palette: _Palette,
    eyebrow: str,
    headline: str,
    subtitle: str,
    preheader: str,
    blocks: str,
    footer: str,
) -> str:
    """
    The card. Header band, then whatever the message is, then who sent it.

    `preheader` is the hidden line mail clients show beside the subject in the
    list. Without one they show whatever text comes first, which is how a
    notification can take up two lines to repeat the subject back.
    """
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

          <tr>
            <td bgcolor="{palette.band}" style="padding:28px 32px;">
              <div style="font-family:{_SANS};font-size:13px;font-weight:bold;letter-spacing:1.5px;color:{palette.eyebrow};text-transform:uppercase;">
                {eyebrow}
              </div>
              <div style="font-family:{_SANS};font-size:24px;line-height:32px;font-weight:bold;color:#ffffff;padding-top:6px;">
                {headline}
              </div>
              <div style="font-family:{_SANS};font-size:14px;line-height:20px;color:{palette.subtitle};padding-top:8px;">
                {subtitle}
              </div>
            </td>
          </tr>
{blocks}
          <tr>
            <td style="padding:20px 32px 28px 32px;">
              <div style="border-top:1px solid #E2E8F0;padding-top:16px;font-family:{_SANS};font-size:12px;line-height:18px;color:#64748B;">
                {footer}
              </div>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def _why_you(traveller: str) -> str:
    """The footer. A guardian who does not know why they were emailed is not one."""
    return (
        f"Automated message from <strong style=\"color:#475569;\">Meridian</strong>. "
        f"You are receiving it because {traveller} asked Meridian to tell you "
        f"about this journey."
    )


def started_message(*, traveller: str, destination: str, due_by: datetime) -> GuardianMessage:
    """
    "She has set off." No location, and no parameter that could carry one.

    `due_by` rather than a duration, for the reason JG2 put an instant on the
    journey card: an instant stays true while nobody is looking at it and a
    duration does not. An email saying "due in 25 minutes", read forty minutes
    later, is actively misleading.

    It says what will happen if she does not arrive, because a guardian who does
    not know they are a guardian is not one. This is also the only message many
    guardians will ever read twice, so it is where the explaining belongs.
    """
    # Collapsed and capped before anything is built from them. See `_oneline`:
    # a POI name tapped from the map arrives with newlines in it, and this one
    # also reaches a subject line.
    traveller = _oneline(traveller, limit=NAME_LIMIT)
    destination = _oneline(destination, limit=PLACE_LIMIT)
    who, where = escape(traveller), escape(destination)
    return GuardianMessage(
        subject=f"{traveller} has started a journey",
        body=(
            f"{traveller} started a journey to {destination} and asked Meridian "
            f"to let you know.\n\n"
            f"They should arrive by about {_when(due_by)}. You will get one more "
            f"message when they do.\n\n"
            f"If they do not arrive and do not answer when Meridian asks, you "
            f"will be told -- and only then will you be told where they were "
            f"last.\n\n"
            f"There is nothing you need to do now."
        ),
        html=_shell(
            palette=_CALM,
            eyebrow="Journey started",
            headline=f"{who} has started a journey",
            subtitle=f"Heading for {where}",
            preheader=f"Due by about {_when(due_by)}. Nothing to do now.",
            blocks=(
                _fact("Due to arrive by", f"about {_when(due_by)}", "Dhaka time")
                + _points(
                    "What happens next",
                    [
                        "You will get one more message when they arrive.",
                        "If they do not arrive and do not answer when Meridian asks, "
                        "you will be told &mdash; and only then will you be told where "
                        "they were last.",
                        "There is nothing you need to do now.",
                    ],
                    _CALM,
                )
            ),
            footer=_why_you(who),
        ),
    )


def arrived_message(*, traveller: str, at: datetime) -> GuardianMessage:
    """
    "She got there." The message that makes the feature worth having.

    Short on purpose. The whole value is in the subject line, because that is
    all a guardian needs to read, and often all they will see on a lock screen.
    """
    traveller = _oneline(traveller, limit=NAME_LIMIT)
    who = escape(traveller)
    return GuardianMessage(
        subject=f"{traveller} arrived safely",
        body=(
            f"{traveller} arrived at {_when(at)}.\n\n"
            f"Nothing else is needed. Meridian has stopped watching this journey."
        ),
        html=_shell(
            palette=_SAFE,
            eyebrow="Arrived safely",
            headline=f"{who} arrived safely",
            subtitle=f"At {_when(at)}, Dhaka time",
            preheader=f"{who} arrived at {_when(at)}. Nothing else is needed.",
            blocks=_note(
                "Nothing else is needed. Meridian has stopped watching this journey."
            ),
            footer=_why_you(who),
        ),
    )


def escalation_message(
    *,
    traveller: str,
    destination: str,
    started_at: datetime,
    last_seen: Position | None,
    started_from: Position | None = None,
) -> GuardianMessage:
    """
    "She has not arrived and is not answering." The only one with a location.

    Three branches, in order of how much they are worth to somebody reading
    this at 10pm, and each one says plainly which it is:

    1. **A real fix.** "The last place their phone reported from was X."
    2. **No fix, but a start point** -- `started_from`, which is the journey's
       own `origin` and needs no collecting because the route was planned from
       it. "They started from X" and *"that is the start of the journey, not a
       sighting"*. Added after the first device run, where a journey heartbeated
       for twenty minutes and stored nothing: the navigator drops fixes worse
       than 100 m accuracy, which indoors is all of them, so the most important
       message this product sends had no point in it at all.
    3. **Neither**, which stays because this function is pure and the caller may
       genuinely have nothing.

    The second is **never dressed as the first.** A reader skims for "where was
    she last" and acts on the answer; a start point an hour stale under that
    heading sends somebody to the wrong end of a route, which is worse than
    saying there is no sighting. Two sentences, two claims.

    `last_seen` is optional and the `None` branch is not a degenerate case: a
    journey with no guardian collects no position (see the migration), and a
    phone that died before its first heartbeat has none to report. A message
    that silently omitted the location would read as though none was ever taken;
    this one says so, because "we do not know where she is" is itself the most
    important fact in that email.

    **One reader.** This used to take an `everyone` flag for a further rung
    that mailed the traveller's whole contact list; that rung was removed, so
    the message always addresses the one person who was named. It says so, in
    as many words, because a reader who thinks four other people got this will
    wait for one of them to act.

    **No instruction to call the police.** JG7 owns 999 and the thana record,
    and `JOURNEY_GUARDIAN.md` is explicit that reaching full escalation from an
    unanswered check-in and then contacting police would be the most damaging
    false positive this product can produce. What this says is what is true:
    she has not answered, here is when and where she last was, you decide.
    """
    traveller = _oneline(traveller, limit=NAME_LIMIT)
    destination = _oneline(destination, limit=PLACE_LIMIT)

    lines = [
        f"{traveller} started a journey to {destination} at {_when(started_at)} "
        f"and has not confirmed arriving.",
        "",
        "Meridian asked twice and got no answer.",
        "",
    ]

    if last_seen is not None:
        lines += [
            f"The last place their phone reported from was {_coords(last_seen)}, "
            f"at {_when(last_seen.at)}.",
            "",
            f"Map: {_maps_url(last_seen)}",
            "",
            "That is where the phone last spoke to us, not necessarily where "
            "they are now.",
            "",
        ]
    elif started_from is not None:
        # Deliberately a different sentence, not the same one with an older
        # time in it. A reader skims for "where was she last" and acts on the
        # answer; handing them the start of the trip under that heading would
        # send somebody to the wrong end of a route. So this says what it is.
        lines += [
            "Their phone has not reported a location since the journey began, so "
            "the only place to point you is where they set off from.",
            "",
            f"They started from {_coords(started_from)} at {_when(started_from.at)}.",
            "",
            f"Map: {_maps_url(started_from)}",
            "",
            "That is the start of the journey, not a sighting -- they were "
            f"heading for {destination}.",
            "",
        ]
    else:
        lines += [
            "Their phone has not reported a location on this journey, so there is "
            "nowhere to point you. That usually means the app was closed or the "
            "phone lost signal early.",
            "",
        ]

    who_else = "You are the only person who has been told."
    lines.append(who_else)
    lines += ["", "If they get in touch, no further action is needed."]

    # The same three branches again, as layout. Nothing is added here: a fact in
    # the HTML that is not in the text above would be a second place for the
    # privacy rule to live, and the tests read both halves for exactly that.
    who, where = escape(traveller), escape(destination)
    point = last_seen if last_seen is not None else started_from
    if last_seen is not None:
        blocks = (
            _button(_maps_url(last_seen), "Open this location on a map", _ALERT)
            + _fact(
                "Last reported position",
                _coords(last_seen),
                f"at {_when(last_seen.at)}, Dhaka time",
            )
            + _note(
                "That is where the phone last spoke to us, not necessarily where "
                "they are now."
            )
        )
    elif started_from is not None:
        blocks = (
            _button(_maps_url(started_from), "Open this location on a map", _ALERT)
            + _fact(
                "Started from",
                _coords(started_from),
                f"at {_when(started_from.at)}, Dhaka time",
            )
            + _note(
                "Their phone has not reported a location since the journey began, "
                "so the only place to point you is where they set off from. "
                "<strong>That is the start of the journey, not a sighting</strong> "
                f"&mdash; they were heading for {where}."
            )
        )
    else:
        blocks = _note(
            "Their phone has not reported a location on this journey, so there is "
            "nowhere to point you. That usually means the app was closed or the "
            "phone lost signal early."
        )

    blocks += _points(
        "What we know",
        [
            "Meridian asked twice and got no answer.",
            escape(who_else),
            "If they get in touch, no further action is needed.",
        ],
        _ALERT,
    )

    return GuardianMessage(
        subject=f"{traveller} has not arrived and is not answering",
        body="\n".join(lines),
        html=_shell(
            palette=_ALERT,
            eyebrow="No answer",
            headline=f"{who} has not arrived and is not answering",
            subtitle=(
                f"Set off for {where} at {_when(started_at)}, Dhaka time"
            ),
            preheader=(
                f"{_coords(point)} &mdash; asked twice, no answer."
                if point is not None
                else "Asked twice, no answer, and no location to give."
            ),
            blocks=blocks,
            footer=_why_you(who),
        ),
        urgent=True,
    )
