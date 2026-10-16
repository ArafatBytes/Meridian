/**
 * What is happening to this journey, in words a person can read. JG3.
 *
 * The server holds five escalation states and seven timestamps. This file is
 * the only place that turns them into sentences, and it is pure: a `Journey` in,
 * strings out, no React, no clock of its own except for relative phrasing.
 *
 * ## Why the timeline is built from timestamps and not from events
 *
 * JG3 deliberately did not build an events table — `JG3_PLAN.md` §6 — so these
 * seven columns *are* the history. That has one consequence worth stating,
 * because it looks like a bug until you know it: **the timestamps describe the
 * current question, not the whole trip.** Asking a new check-in clears the
 * ladder's three stamps, so a journey that escalated, was answered, and is
 * being asked again shows one cycle, not two. The alternative was an events
 * table, which is a bigger feature than the thing it would be documenting.
 *
 * ## Why `answered_at` is never read to decide whether to ask
 *
 * It survives the return to `normal`, so a journey being asked its second
 * question carries an `answered_at` about the first. It is history here and
 * nothing else; `isAwaitingAnswer` in `deadline.ts` reads the state.
 */
import type { EscalationState, Journey } from '../../services/journey.service';

/**
 * The states where a question is outstanding — everything but `normal`.
 *
 * Named and exported rather than compared inline, because JG3 made the same
 * oversight twice in two languages: the backend's check-in endpoint and this
 * app's `isAwaitingAnswer` both tested `=== 'check_in_sent'`, which silently
 * became "the first rung only" the moment there were four. A journey on a
 * higher rung is one being asked *harder*, so a screen that stops offering the
 * button there hides it from the person who most needs it.
 */
export const ESCALATION_LADDER: readonly EscalationState[] = [
  'check_in_sent',
  'check_in_repeated',
  'contacts_notified',
  'full_sos',
];

/** How loud an entry or a status is, for the one colour decision a screen makes. */
export type Tone = 'calm' | 'waiting' | 'alarm';

export interface JourneyStatus {
  /** One short line. The whole state of the journey, as a sentence. */
  headline: string;
  /**
   * What happens next, or null when nothing does.
   *
   * Separate from the headline because the two answer different questions —
   * "what is going on" and "do I need to do something" — and someone reading
   * this screen at speed needs the first one to be short.
   */
  detail: string | null;
  tone: Tone;
}

/** Who this journey would tell, as one line, or null when nobody. */
export function guardianLine(journey: {
  guardian_name: string | null;
  guardian_contact_id: string | null;
}): string | null {
  const name = journey.guardian_name?.trim();
  if (name) return `Telling ${name}`;
  // A guardian with no name should not become "Telling". The id without a name
  // means the contact row was deleted after the journey started — the foreign
  // key is `on delete set null`, but this app may be holding a journey it read
  // before that happened.
  if (journey.guardian_contact_id) return 'Telling your guardian';
  return null;
}

/** The guardian's name for use mid-sentence, with a fallback that is never blank. */
function guardianName(journey: { guardian_name: string | null }): string {
  return journey.guardian_name?.trim() || 'your guardian';
}

/**
 * The journey's state as a headline and a next step.
 *
 * Written in the second person throughout, because the only person who sees
 * this screen is the one on the trip. The guardian gets email and has no screen
 * — JG3 has no guardian-side app, by choice.
 */
export function journeyStatus(journey: {
  state: string;
  escalation_state: string;
  guardian_name: string | null;
  guardian_contact_id: string | null;
}): JourneyStatus {
  if (journey.state === 'arrived') {
    return {
      headline: 'You arrived.',
      detail: journey.guardian_contact_id
        ? `${guardianName(journey)} was told you got there.`
        : null,
      tone: 'calm',
    };
  }

  if (journey.state === 'cancelled') {
    return {
      headline: 'This journey was ended.',
      // Deliberately does not claim the guardian was told. Cancelling tells
      // nobody — `_PENDING_ARRIVED_NOTICE` selects `arrived` only — because
      // "she stopped the journey" is not news and sending it would train people
      // to ignore these emails.
      detail: null,
      tone: 'calm',
    };
  }

  switch (journey.escalation_state) {
    case 'check_in_sent':
      return {
        headline: 'Meridian is waiting to hear from you.',
        detail: 'Tap "I\'m fine" and the clock moves on.',
        tone: 'waiting',
      };
    case 'check_in_repeated':
      return {
        headline: 'Asked twice, still no answer.',
        detail: journey.guardian_contact_id
          ? `If this stays unanswered, ${guardianName(journey)} will be emailed.`
          : 'Nobody will be told — this journey has no guardian.',
        tone: 'waiting',
      };
    // The two rungs that tell somebody else, and the two where this screen
    // could most easily lie.
    //
    // A journey with no guardian still climbs: the rungs are the record of what
    // was asked and ignored, and that record is worth keeping whether or not
    // anybody is listening. But nothing is sent, because every escalation email
    // starts from the guardian -- `_ESCALATION_RECIPIENTS` joins through
    // `guardian_contact_id`, so with no guardian there is no recipient list at
    // all, not even at the last ring.
    //
    // Found by a test asserting that no guardianless journey's status claims
    // anybody was emailed. The first version of this screen said "your guardian
    // has been emailed" on a journey that had told nobody -- which is exactly
    // the promise the picker makes, broken on the screen that reports on it.
    case 'contacts_notified':
      return journey.guardian_contact_id
        ? {
            headline: `${guardianName(journey)} has been emailed.`,
            // The end of the ladder. This said "your other contacts are next"
            // while a further rung existed that mailed all of them; that rung
            // was removed, and leaving the sentence would be a promise of help
            // that is not coming — the worst kind of copy on this screen.
            detail: 'Meridian has done everything it does automatically.',
            tone: 'alarm',
          }
        : {
            headline: 'Still no answer from you.',
            detail:
              'This journey has no guardian, so Meridian has not told anybody.',
            tone: 'waiting',
          };
    // Unreachable for any new journey: the rung that mailed everybody was
    // removed. Kept, and kept accurate, because journeys that reached it before
    // then are still in the database and still open on this screen — a state
    // the server can return is a state this screen has to render.
    case 'full_sos':
      return journey.guardian_contact_id
        ? {
            headline: 'All of your emergency contacts have been emailed.',
            // No police, no 999 (that is JG7), and saying so is better than
            // leaving somebody to assume help is already coming.
            detail: 'Meridian has done everything it does automatically.',
            tone: 'alarm',
          }
        : {
            headline: 'Still no answer from you.',
            detail:
              'This journey has no guardian, so Meridian has not told anybody.',
            tone: 'waiting',
          };
    default:
      return {
        headline: 'On your way.',
        detail: journey.guardian_contact_id
          ? `${guardianName(journey)} will hear if you go quiet.`
          : 'Nobody is being told about this journey.',
        tone: 'calm',
      };
  }
}

export interface TimelineEntry {
  /** ISO instant, as the server sent it. */
  at: string;
  label: string;
  tone: Tone;
}

/** Drop the nulls and the unparseable, keep the order of time. */
function entry(at: string | null, label: string, tone: Tone): TimelineEntry[] {
  if (!at) return [];
  if (Number.isNaN(new Date(at).getTime())) return [];
  return [{ at, label, tone }];
}

/**
 * Everything that has happened to this journey, oldest first.
 *
 * Only what the row actually records. In particular there is no "deadline
 * passed" entry: nothing stamps that, and inventing one from `deadline_at`
 * would put a line in the history for something that may not have happened yet
 * — the sweep runs once a minute, so for up to a minute a passed deadline has
 * had no consequence at all.
 */
export function journeyTimeline(journey: Journey): TimelineEntry[] {
  const name = guardianName(journey);
  const entries = [
    ...entry(journey.started_at, 'Journey started', 'calm'),
    ...entry(journey.started_notice_at, `${name} was told you set off`, 'calm'),
    ...entry(
      journey.check_in_sent_at,
      'Meridian asked if you were okay',
      'waiting',
    ),
    // `answered_at` sorts to its own place rather than being matched to a
    // question. It survives the return to `normal`, so on a journey asked twice
    // it belongs to the first — and a timeline is the one place where showing
    // it in time order is exactly right.
    ...entry(journey.answered_at, 'You said you were fine', 'calm'),
    ...entry(journey.unanswered_at, 'No answer by the deadline', 'waiting'),
    ...entry(journey.check_in_repeated_at, 'Meridian asked again', 'waiting'),
    ...entry(journey.contacts_notified_at, `${name} was emailed`, 'alarm'),
    ...entry(
      journey.full_sos_at,
      'All of your emergency contacts were emailed',
      'alarm',
    ),
    ...entry(journey.arrived_notice_at, `${name} was told you arrived`, 'calm'),
    ...entry(
      journey.ended_at,
      journey.state === 'arrived' ? 'You arrived' : 'Journey ended',
      'calm',
    ),
  ];
  return entries.sort(
    (a, b) => new Date(a.at).getTime() - new Date(b.at).getTime(),
  );
}

/** "8:45 PM", or '' for anything unparseable. The same shape as `deadline.ts`. */
export function clockTime(iso: string | null): string {
  if (!iso) return '';
  const at = new Date(iso);
  if (Number.isNaN(at.getTime())) return '';
  return at.toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  });
}
