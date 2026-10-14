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

import {
  journeyService,
  type Journey,
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

  return { journey, loading, start, arrive, cancel };
}
