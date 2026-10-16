/**
 * The journey the server is holding. JG1.
 *
 * Deliberately small. It owns one piece of state -- the caller's open journey,
 * or null -- and the four ways that changes: it is loaded on mount, written on
 * `Start`, closed on arrival, and closed on End. There is no timer in here, no
 * notification and no escalation; a journey that nobody is watching is still the
 * thing JG2 needs to exist.
 *
 * ## Why starting a journey never blocks following
 *
 * `start` resolves to the journey, or to the reason it could not be written, and
 * it never throws. The caller follows the route either way.
 *
 * That is a deliberate ordering choice. Writing the trip before following is
 * what makes the trip survive, so it goes first -- but a phone with no signal at
 * the moment someone presses Start is a phone whose owner still needs
 * directions. Refusing to navigate because we could not record the journey would
 * be the safety feature making the person less safe, which is the one outcome
 * this whole feature cannot afford. The screen says the journey was not
 * recorded; the route still works.
 *
 * ## Why there is no refresh loop
 *
 * Nothing on the server changes this row except this app. JG2 introduces the
 * first thing that does -- a deadline passing -- and that arrives as a push
 * notification, not as a poll. Polling now would be a battery cost with nothing
 * to find.
 */
import { useCallback, useEffect, useRef, useState } from 'react';

import { isAwaitingAnswer } from './deadline';
import {
  journeyService,
  type Journey,
  type JourneyPosition,
  type JourneyStart,
} from '../../services/journey.service';

/**
 * What `start` resolves to: the recorded journey, or the reason there isn't one.
 *
 * The reason comes back from the call rather than living in hook state, and that
 * is not tidiness. A failure message held in state is the *same string* the
 * second time it happens, so neither a `useEffect` keyed on it nor a render that
 * compares it to the last one it showed can tell "it failed again" from "it is
 * still failed" -- and the screen stays silent on the second press of Start,
 * which is exactly the press someone makes when the first one looked like it did
 * nothing. Returning it makes every failure its own event.
 */
export interface JourneyWrite {
  journey: Journey | null;
  /** Null when the journey was recorded. */
  error: string | null;
}

export interface UseJourney {
  /** The open journey, or null. Null while the first load is in flight. */
  journey: Journey | null;
  /** True until the launch read has answered, so the UI can stay quiet. */
  loading: boolean;
  /** Record a journey. Never throws -- see `JourneyWrite`. */
  start: (journey: JourneyStart) => Promise<JourneyWrite>;
  /** You got there. */
  arrive: () => Promise<void>;
  /** You stopped. */
  cancel: () => Promise<void>;

  // ---- JG2 -------------------------------------------------------------

  /**
   * "Still going, about this long left." Never throws, never surfaces a
   * failure, and intentionally does not update the journey on screen.
   *
   * The deadline is the server's to hold. Rendering the value a heartbeat
   * happened to return would make the card flicker between two sources of truth
   * once a minute, and a heartbeat that failed would silently leave the old one
   * showing -- so the card reads the journey it was given and nothing else.
   */
  heartbeat: (remainingSeconds: number, position?: JourneyPosition | null) => Promise<void>;

  /** "I'm fine." Returns false when there was nothing to answer. */
  checkIn: () => Promise<boolean>;

  /**
   * Re-read the open journey from the server.
   *
   * JG2 needs it because the escalation state changes *on the server* -- the
   * sweep sets `check_in_sent` with no request from this app -- so the only way
   * the card learns a question was asked is to look. There is still no polling
   * loop: this is called when the app comes back to the foreground and when a
   * check-in notification arrives, both of which are moments something has
   * plausibly changed.
   */
  refresh: () => Promise<void>;
}

export function useJourney(): UseJourney {
  const [journey, setJourney] = useState<Journey | null>(null);
  const [loading, setLoading] = useState(true);

  /**
   * The journey id the terminal calls read, rather than the state.
   *
   * `arrive` is called from an effect watching the navigator's phase, and
   * `cancel` from a button press; both can fire in the same tick as a state
   * update. Reading the ref means they act on the journey that exists now
   * rather than on whatever React had committed when the callback was created.
   */
  const current = useRef<Journey | null>(null);

  const remember = useCallback((next: Journey | null) => {
    current.current = next;
    setJourney(next);
  }, []);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const open = await journeyService.active();
      if (cancelled) return;
      remember(open);
      setLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, [remember]);

  const start = useCallback(
    async (next: JourneyStart): Promise<JourneyWrite> => {
      try {
        const created = await journeyService.start(next);
        remember(created);
        return { journey: created, error: null };
      } catch (e: any) {
        // Not rethrown. See the note at the top of this file: the route still
        // works, and the screen says the journey was not recorded.
        remember(null);
        return { journey: null, error: e?.message || 'Could not record this journey.' };
      }
    },
    [remember],
  );

  /**
   * Close the open journey one way or the other.
   *
   * The local state is cleared whatever the server says. A failed close leaves
   * a stale active row, and the next `Start` supersedes it -- which is exactly
   * why the server cancels an open journey on start rather than refusing. The
   * alternative, keeping a journey on screen that the user has already ended,
   * is the worse of the two wrongs.
   */
  const end = useCallback(
    async (close: (id: string) => Promise<Journey>) => {
      const open = current.current;
      remember(null);
      if (!open) return;
      try {
        await close(open.journey_id);
      } catch (e: any) {
        console.warn('Could not close journey', open.journey_id, e?.message);
      }
    },
    [remember],
  );

  const arrive = useCallback(
    () => end(id => journeyService.arrive(id)),
    [end],
  );

  const cancel = useCallback(
    () => end(id => journeyService.cancel(id)),
    [end],
  );

  const heartbeat = useCallback(
    async (remainingSeconds: number, position?: JourneyPosition | null) => {
      const open = current.current;
      if (!open) return;

      // JG3's privacy rule, at the point of collection: **no guardian, no
      // position.** The caller passes whatever fix the navigator has, and this
      // is where it is dropped, because the decision belongs to the journey
      // rather than to the screen -- a journey with nobody to show a position
      // to has no reason to send one, and the rule should not have to be
      // remembered at each call site.
      //
      // The server enforces the same thing in the `UPDATE` that writes the
      // heartbeat. Both halves on purpose: this one is what stops the position
      // ever leaving the phone, and that one is what holds when a stale build
      // or a future client sends it anyway.
      const share = open.guardian_contact_id ? position ?? null : null;

      // The result is discarded on purpose -- see the interface note. `heartbeat`
      // in the service already swallows its own errors.
      await journeyService.heartbeat(open.journey_id, remainingSeconds, share);
    },
    [],
  );

  const refresh = useCallback(async () => {
    const open = await journeyService.active();
    // `active()` returns null both for "no journey" and for "could not ask",
    // and those differ here in a way they do not at launch: a refresh that
    // failed must not wipe a journey that is on screen and running. So a null
    // is only believed when there was nothing open to begin with.
    if (open === null && current.current !== null) return;
    remember(open);
  }, [remember]);

  const checkIn = useCallback(async () => {
    const open = current.current;
    if (!open) return false;
    try {
      remember(await journeyService.checkIn(open.journey_id));
      return true;
    } catch (e: any) {
      // Not surfaced here. The two callers differ: the card shows its own
      // message, and the lock-screen handler has no screen to show one on.
      console.warn('Could not check in on', open.journey_id, e?.message);

      // A failure here is not the same as an unanswered question, and on a
      // device the difference is the common case rather than the edge one.
      // There are two ways to answer and they race: tapping the notification
      // wakes the app, `answerFromNotification` posts the answer, and the card
      // renders from state that predates that round trip -- so it is still
      // offering the button for a question the server has already closed.
      // Pressing it is then a second answer, which the endpoint correctly
      // refuses with a 409 because `escalation_state` is no longer
      // `check_in_sent`.
      //
      // The honest test is not "did my request succeed" but "is the question
      // still outstanding", and only the server knows. So ask it. A 409 that
      // comes back with the question closed means somebody answered, which is
      // the whole point, and reporting a failure there told the person their
      // safety check-in had not been recorded when it had -- the worst
      // available way to be wrong in this feature.
      await refresh();
      const after = current.current;
      // `isAwaitingAnswer` rather than a comparison, for the reason written in
      // that function: JG3 added three more states a question can be
      // outstanding in, and the one definition is what keeps this agreeing
      // with the card that renders the button.
      return !(after && isAwaitingAnswer(after));
    }
  }, [remember, refresh]);

  return { journey, loading, start, arrive, cancel, heartbeat, checkIn, refresh };
}
