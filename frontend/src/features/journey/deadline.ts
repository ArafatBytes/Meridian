/**
 * The deadline the person picks before pressing Start. JG2.
 *
 * Four chips and a clock time. The whole interaction is: read the time, and
 * either accept it or tap a different one. No stepper, no picker, no arithmetic
 * — JOURNEY_GUARDIAN.md's note on how the deadline gets set is explicit that it
 * is neither fully automatic ("the router does not know she is stopping for
 * food") nor fully manual ("nobody wants to do arithmetic at 10pm").
 *
 * ## The numbers here are not the policy
 *
 * These are the *offers*. What they mean is decided by
 * `backend/app/journeys/deadline.py`, which clamps them and computes the instant
 * from the server's clock. Nothing in this file is trusted: a chip sends a
 * number of minutes and the server decides where that lands.
 *
 * The default chip sends nothing at all — `deadline_minutes: null` — rather than
 * sending its own computed value. The route's ETA plus the grace period is the
 * server's number, and a client that recomputed it would be a second definition
 * of the grace period that could drift from the first without anything noticing.
 */

/**
 * The server's grace period, in minutes, **for display only**.
 *
 * The default chip sends `null` and the server adds its own `GRACE` — this copy
 * exists purely so the row above the chips can say what time that will land on
 * before the journey is written. Nothing is computed from it and nothing is sent
 * with it.
 *
 * It is still a duplicated number, which is a thing worth being nervous about:
 * if the backend's `GRACE` moved and this did not, the planner would promise a
 * time the server then disagreed with, and the person would be told 10:40 and
 * asked at 10:55. `backend/tests/invariants/test_journey_deadline.py` reads this
 * file and fails if the two differ.
 */
export const SERVER_GRACE_MINUTES = 10;

/** What a chip offers. `minutes` of `null` is "accept the route's own ETA". */
export interface DeadlineChoice {
  /** The chip's label. Short enough to fit four across a phone. */
  label: string;
  /** Minutes from now, or null for the server's default. */
  minutes: number | null;
}

/**
 * Two minutes is the shortest the server will accept (`MIN_DEADLINE`).
 *
 * It is here as well as there so the chip row cannot offer something that will
 * be silently clamped — an offer the system quietly ignores is worse than no
 * offer, because the person believes they set something they did not.
 */
export const MIN_CHOICE_MINUTES = 2;

/**
 * The four offers, in the order they appear.
 *
 * `null` first and selected by default: accepting is the common case and the
 * leftmost chip is where the eye starts.
 *
 * `2 min` is last and is deliberately an odd thing to ship. It is what makes
 * this phase's walkthrough runnable without waiting out a real journey — but it
 * is also a real case, and the reason it earns its place rather than being a
 * debug flag: somebody walking the last stretch home with footsteps behind them
 * wants to be asked in two minutes, which is JOURNEY_GUARDIAN.md §6's short
 * leash arriving early.
 */
export const DEADLINE_CHOICES: readonly DeadlineChoice[] = [
  { label: 'Route ETA', minutes: null },
  { label: '1 hr', minutes: 60 },
  { label: '30 min', minutes: 30 },
  { label: '2 min', minutes: MIN_CHOICE_MINUTES },
];

/**
 * The clock time a choice lands on, for the line above the chips.
 *
 * `durationMinutes` is the route's own estimate and `graceMinutes` the server's
 * grace period, both needed only for the default chip. They are passed in rather
 * than imported so this stays a pure function of its arguments — the grace
 * period is a server number and this file must not become a second home for it.
 *
 * Returns an empty string for a time it cannot compute, which the caller renders
 * as nothing. A deadline row that says `Invalid Date` is worse than one that says
 * nothing: the first looks broken, the second looks absent, and the server is
 * going to pick a sane default either way.
 */
export function deadlineLabel(options: {
  now: number;
  minutes: number | null;
  durationMinutes: number;
  graceMinutes: number;
}): string {
  const { now, minutes, durationMinutes, graceMinutes } = options;
  const offset = minutes ?? durationMinutes + graceMinutes;
  if (!Number.isFinite(offset) || !Number.isFinite(now)) return '';

  const at = new Date(now + offset * 60_000);
  if (Number.isNaN(at.getTime())) return '';
  return at.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true });
}

/**
 * How often the phone reports in while following, in milliseconds.
 *
 * One minute, which is the same cadence as the sweep that reads the result.
 * Faster would spend battery and mobile data to refresh a number nothing looks
 * at more than once a minute; slower would mean a deadline that lags the phone's
 * own estimate by more than the sweep's own resolution, so a journey could be
 * asked about a minute of travel it had already reported.
 */
export const HEARTBEAT_INTERVAL_MS = 60_000;

/**
 * Whether a journey is currently being asked something.
 *
 * A function rather than a comparison at the call site because the answer is
 * not just the state: `answered_at` survives the return to `normal`, and JG3
 * adds states after `check_in_sent` that are also "outstanding". One definition
 * means the card and the tests cannot disagree about what "waiting" means.
 */
export function isAwaitingAnswer(journey: {
  state: string;
  escalation_state: string;
}): boolean {
  return journey.state === 'active' && journey.escalation_state === 'check_in_sent';
}
