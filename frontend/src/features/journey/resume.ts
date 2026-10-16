/**
 * The two decisions involved in putting a held journey back on the screen. JG1.
 *
 * Pure, and out of `MapScreen` for that reason: both are small rules with a
 * wrong answer that is invisible on the screen, which is the kind of thing worth
 * testing directly rather than by eye on a phone.
 */
import type { Journey } from '../../services/journey.service';

/** How close two destinations have to be to count as the same one. */
export const TOLERANCE_DEGREES = 5e-4;

/**
 * Whether an open journey is the one this route goes to.
 *
 * `Start` records a journey on the server, and pressing it again must not record
 * a second one for a journey already in progress -- that would move `started_at`
 * to now, and from JG2 onward `started_at` is what the deadline is measured
 * from. So resuming goes through the same `Start` button, and this is what tells
 * the two cases apart.
 *
 * `5e-4` degrees is about 55 m of latitude, and about 55 m of longitude at
 * Dhaka's. The comparison is against the destination the user picked, not
 * against a GPS fix, so this is really an identity check with slack -- the slack
 * exists because a resumed journey's destination makes the round trip through
 * the database as a PostGIS geography and back, and an exact float match is not
 * a thing to depend on across that.
 *
 * The slack is deliberately small. Two cafés on opposite sides of one road are
 * different destinations, and treating them as the same would silently keep the
 * old journey -- and from JG3 onward tell a guardian the wrong place.
 */
export function goesTo(
  journey: Pick<Journey, 'destination_latitude' | 'destination_longitude'>,
  destination: { latitude: number; longitude: number },
): boolean {
  return (
    Math.abs(journey.destination_latitude - destination.latitude) < TOLERANCE_DEGREES &&
    Math.abs(journey.destination_longitude - destination.longitude) < TOLERANCE_DEGREES
  );
}

/**
 * "10:04 pm" — when a journey was started, for the resume card.
 *
 * A clock time rather than "22 minutes ago", for two reasons. The relative form
 * needs `Date.now()` during render, which `react-hooks/purity` flags and which
 * this project has one standing lint error for already. And it would be wrong
 * the moment the card stopped re-rendering, whereas an absolute time is true
 * whenever it is read.
 *
 * Empty string for anything unparseable, so the caller can drop the clause
 * rather than print "Invalid Date" next to a destination.
 */
export function startedAtLabel(startedAt: string): string {
  const at = new Date(startedAt);
  if (Number.isNaN(at.getTime())) return '';
  return at.toLocaleTimeString('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true,
  });
}
