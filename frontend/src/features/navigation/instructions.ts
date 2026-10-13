/**
 * Turning a manoeuvre into a sentence.
 *
 * Separate from `progress.ts` because it is not geometry, and separate from
 * `NavigationBanner.tsx` because it is the part worth testing: the whole value of
 * street names is lost if the phrasing is wrong, and the failure mode is a
 * sentence that trails off into nothing on roads OSM has no name for — which in
 * Dhaka is a large share of them.
 *
 * ## Two sources, one sentence
 *
 * The banner can narrate from either:
 *
 * * **OSRM steps** — a manoeuvre type, a modifier and an OSM road name. This is
 *   what gives "Turn left onto Mirpur Road".
 * * **Route geometry** — the bend angles of the polyline, from
 *   `progress.nextTurn`. A reliable side and distance, and no name.
 *
 * Steps are preferred and the geometry is the fallback, and the fallback is not
 * rare: the straight-line route has no steps at all, and a step on an unnamed lane
 * has a type and a modifier but `name === ""`. So the composition degrades in two
 * stages rather than one — named manoeuvre, then unnamed manoeuvre, then pure
 * geometry — and each stage is a sentence that is still true.
 *
 * ## What it will not do
 *
 * It never invents a name, and it never says "onto" without one. "Turn left onto"
 * followed by nothing is the single most likely bug here, and the reason `name` is
 * checked at every use rather than once at the top.
 */

import { formatDistance, type NavStep, type StepHint, type TurnHint } from './progress';

/**
 * Human phrasing for OSRM's modifiers.
 *
 * `uturn` is spelled out: "Make a U-turn" rather than "Turn uturn". `straight` maps
 * to nothing, because the manoeuvre phrase already carries it ("Continue", "Keep
 * going") and "Turn straight" is not a thing.
 */
const MODIFIER_PHRASE: Record<string, string> = {
  left: 'left',
  right: 'right',
  'slight left': 'slightly left',
  'slight right': 'slightly right',
  'sharp left': 'sharp left',
  'sharp right': 'sharp right',
  straight: '',
  uturn: 'around',
};

/**
 * The verb for each manoeuvre type.
 *
 * OSRM's full vocabulary is larger than this; anything unlisted falls back to the
 * generic turn phrasing, which is correct for every type that carries a modifier.
 * Adding a type here is a presentation improvement, never a correctness fix.
 */
function verbFor(step: NavStep): string {
  const side = MODIFIER_PHRASE[step.modifier] ?? '';

  switch (step.maneuver_type) {
    case 'arrive':
      return 'Arrive';
    case 'depart':
      return 'Set off';
    case 'roundabout':
    case 'rotary':
      return side ? `At the roundabout, go ${side}` : 'Take the roundabout';
    case 'roundabout turn':
      return side ? `At the roundabout, turn ${side}` : 'Take the roundabout';
    case 'fork':
      return side ? `Keep ${side}` : 'Keep going';
    case 'merge':
      return side ? `Merge ${side}` : 'Merge';
    case 'on ramp':
      return side ? `Take the ramp ${side}` : 'Take the ramp';
    case 'off ramp':
      return side ? `Exit ${side}` : 'Take the exit';
    case 'end of road':
      return side ? `At the end of the road, turn ${side}` : 'At the end of the road';
    case 'new name':
    case 'continue':
      return side && step.modifier !== 'straight' ? `Continue ${side}` : 'Continue';
    case 'turn':
    default:
      if (step.modifier === 'uturn') return 'Make a U-turn';
      return side ? `Turn ${side}` : 'Continue';
  }
}

/**
 * The instruction for a step, with its distance.
 *
 * Shape: `<verb> onto <name> in <distance>`, with each clause dropped when the
 * data for it is absent:
 *
 * ```
 *   Turn left onto Mirpur Road in 120 m     name present
 *   Turn left in 120 m                      name empty — most Dhaka lanes
 *   Turn left now                           within 20 m
 *   Arrive in 60 m                          the final step
 * ```
 *
 * Under 20 m the distance is inside the GPS error, so naming it is false precision
 * — "turn left in 10 m" while you are already standing at the corner.
 */
export function stepInstruction(hint: StepHint): string | null {
  const step = hint.next ?? hint.current;
  if (!step) return null;

  const verb = verbFor(step);
  const named = step.name ? `${verb} onto ${step.name}` : verb;

  if (step.maneuver_type === 'arrive') {
    return hint.distanceM < 20 ? 'Arrive at your destination' : `Arrive in ${formatDistance(hint.distanceM)}`;
  }

  if (hint.distanceM < 20) return `${named} now`;
  return `${named} in ${formatDistance(hint.distanceM)}`;
}

/**
 * The instruction from geometry alone. The fallback, and the only narration
 * available on a route with no steps.
 *
 * "Continue" rather than "Go straight" when there is no turn within the lookahead:
 * `nextTurn` returns `straight` both for a genuinely straight road and for "no turn
 * found in the next 500 m", and "continue for 1.2 km" is true in both cases where
 * "go straight for 1.2 km" implies the road does not bend at all.
 */
export function turnInstruction(turn: TurnHint | null): string {
  if (!turn) return 'Following your route';
  if (turn.direction === 'straight') return `Continue for ${formatDistance(turn.distanceM)}`;
  if (turn.distanceM < 20) {
    return `Turn ${turn.direction.replace('slight ', '').replace('sharp ', '')} now`;
  }
  const direction = `${turn.direction[0].toUpperCase()}${turn.direction.slice(1)}`;
  return `${direction} in ${formatDistance(turn.distanceM)}`;
}

/**
 * The instruction to show, from whichever source has one.
 *
 * Steps win when they exist. The geometry is not merely a fallback for a missing
 * router, though — it is what covers the straight-line estimate and a route whose
 * steps arrived empty, both of which are states this app really reaches.
 */
export function instructionFor(step: StepHint | null, turn: TurnHint | null): string {
  if (step) {
    const fromStep = stepInstruction(step);
    if (fromStep) return fromStep;
  }
  return turnInstruction(turn);
}

/**
 * The road currently being travelled, or null.
 *
 * Shown as a secondary line — "on Kazi Nazrul Islam Avenue" — which is what makes
 * a named route legible at a glance without the instruction having to carry two
 * names at once. Null when the current way is unnamed, which is the common case on
 * a lane.
 */
export function currentRoadName(step: StepHint | null): string | null {
  const name = step?.current?.name;
  return name ? name : null;
}
