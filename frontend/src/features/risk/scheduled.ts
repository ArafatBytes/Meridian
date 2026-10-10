/**
 * Forward-dated flags, as the UI presents them. D09, demo beat 8.
 *
 * A scheduled flag is a claim about a *window* rather than about now: a procession
 * announced this evening for tomorrow morning. The server serves one only inside
 * its window, so the map at `Now` and the map at `Tomorrow` genuinely differ —
 * which is the beat.
 *
 * This module exists because the predicate had been written three times in one
 * afternoon — in the marker, in the sheet and in the map screen — and three copies
 * of a definition is how two of them end up disagreeing. It is pure and imports
 * nothing from React, so it is also the only part of this that a test can reach:
 * `MapScreen` cannot be imported under jest, and neither can anything that pulls
 * in `react-native-maps`.
 */
import type { RiskFlag } from '../../types/contracts/risk';

/**
 * The one place that decides what "scheduled" means.
 *
 * `validFrom` rather than comparing times: the server has already decided whether
 * the window is open — it would not have served the flag otherwise — so the device
 * does not re-derive it. Keeping clock arithmetic off the device is the same rule
 * that keeps `severityNow` server-side.
 */
export const isScheduledFlag = (flag: RiskFlag): boolean => flag.validFrom !== null;

/** "14:31" in the device's own timezone, which for this demo is Dhaka. */
export function clockTime(iso: string): string {
  return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

/**
 * A scheduled flag's window: "Sat 10:00 – 16:00", or with both days when it spans
 * more than one.
 *
 * This is the one fact a forward-dated flag has that a live one does not, and
 * without it the "Scheduled" badge says a procession is coming without saying when
 * — which is most of the information. The dash is an en dash because a hyphen
 * between two clock times reads as a minus sign.
 */
export function windowText(validFrom: string, validTo: string | null): string {
  const from = new Date(validFrom);
  const day = (d: Date) => d.toLocaleDateString([], { weekday: 'short' });
  if (!validTo) return `${day(from)} from ${clockTime(validFrom)}`;

  const to = new Date(validTo);
  const sameDay = from.toDateString() === to.toDateString();
  return sameDay
    ? `${day(from)} ${clockTime(validFrom)} – ${clockTime(validTo)}`
    : `${day(from)} ${clockTime(validFrom)} – ${day(to)} ${clockTime(validTo)}`;
}

/**
 * The time control's stops.
 *
 * The near ones are the decay story (beat 5): a flag fading and then going. The far
 * ones are the forward story (beat 8), and they are labelled in words rather than
 * hours because "Tomorrow" is the claim being made — "+24h" reads like a debug
 * affordance, which is what this control was until D09 took `__DEV__` off it.
 */
export const AS_OF_PRESETS: { hours: number; label: string }[] = [
  { hours: 0, label: 'Now' },
  { hours: 3, label: '+3h' },
  { hours: 6, label: '+6h' },
  { hours: 12, label: '+12h' },
  { hours: 24, label: 'Tomorrow' },
  { hours: 48, label: '+2 days' },
];

/**
 * What the time control says above its buttons.
 *
 * At Now it is a plain count. Ahead of now it names the instant in the device's own
 * locale and then says how many of those flags are *scheduled* — the number beat 8
 * is about, and the one that is zero on every other product. The dev-only label
 * this replaces said "N flags left", a decay framing that had the direction of the
 * control backwards once it started looking forward.
 *
 * `now` is a parameter rather than a call to `Date.now()` so this is a pure
 * function of its inputs: a component that reads the clock in its body is not, and
 * `react-hooks/purity` is right to say so.
 */
export function asOfSummary(offsetHours: number, flags: RiskFlag[], now: number): string {
  const plural = (n: number) => `${n} ${n === 1 ? 'flag' : 'flags'}`;
  if (offsetHours === 0) return `Live · ${plural(flags.length)}`;

  const at = new Date(now + offsetHours * 3600 * 1000);
  const when = at.toLocaleString(undefined, {
    weekday: 'short',
    hour: '2-digit',
    minute: '2-digit',
  });
  const scheduled = flags.filter(isScheduledFlag).length;
  return scheduled > 0
    ? `${when} · ${flags.length} flags, ${scheduled} scheduled`
    : `${when} · ${plural(flags.length)}`;
}
