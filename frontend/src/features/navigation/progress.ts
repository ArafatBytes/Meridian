/**
 * Where you are on a route, and what is left of it.
 *
 * Pure functions over a polyline and a position. No React, no location
 * subscription, no map — all of that is `useNavigation.ts`. This is here on its
 * own because it is the part that is easy to get subtly, invisibly wrong, and the
 * only way to know it is right is to test it against arranged geometry rather
 * than by walking around Dhaka with a phone.
 *
 * ---
 *
 * ## The failure this module is mostly about
 *
 * The obvious implementation of "where am I on the route" is: find the closest
 * point on the whole polyline. It works perfectly in a straight-line test and
 * breaks the moment a route comes near itself — which in Dhaka is most routes.
 * An out-and-back on the same road, a loop around a block, a flyover crossing the
 * road it later joins: all of them put two very different points on the route
 * within a few metres of each other.
 *
 * A global search then teleports. You are 300 m in, the GPS wobbles 15 m sideways
 * onto the return leg, and the closest point on the polyline is suddenly 4 km
 * ahead. The route collapses to nothing, the remaining distance reads 200 m, and
 * the app says you have nearly arrived. One bad fix, and the screen is lying.
 *
 * So the search is **windowed**: it only looks at the stretch of route from a
 * little behind where you were to `LOOKAHEAD_M` in front of it. The window is
 * measured in **metres along the route**, not in vertices, because an OSRM
 * `overview=full` geometry has wildly uneven vertex density — dozens of points
 * around a roundabout and two across a long straight — so "the next 20 vertices"
 * is somewhere between 30 m and 3 km depending on where you happen to be.
 *
 * ## And the second one: progress must not run backwards
 *
 * Even inside the window, consecutive fixes jitter. If progress is allowed to
 * decrease, the trimmed route grows back by a few metres every other second and
 * the line visibly twitches. Google's never does. `advance()` therefore takes the
 * previous progress and refuses to go backwards past `BACKTRACK_TOLERANCE_M`,
 * which is the only intentional-reversal case worth honouring (you genuinely
 * turned around within a few metres of where you were).
 *
 * Real reversals past that tolerance show up as *off-route*, which is the correct
 * reading: you are no longer following this route, and the answer is to recompute
 * it, not to redraw it backwards.
 */

export interface LatLng {
  latitude: number;
  longitude: number;
}

/**
 * Metres per degree of latitude. Constant enough: the WGS84 meridian varies from
 * about 110 574 m at the equator to 111 694 m at the poles, and at Dhaka's 23.8°N
 * the error from using one value is well under 0.2% — a metre in every 500. Every
 * threshold in this file is tens of metres, so that is noise.
 *
 * The honest alternative is a full geodesic, and it would be slower per fix for an
 * answer no user could perceive.
 */
const METRES_PER_DEGREE = 111_320;

export const LOOKAHEAD_M = 400;
/**
 * How far ahead of the last known progress to look for the current position.
 *
 * Large enough to survive a gap — a tunnel, a flyover, the app backgrounded at a
 * traffic light, a dropped fix on a bad network — at the speeds this app sees.
 * 400 m is about four minutes of walking or forty seconds of Dhaka traffic.
 *
 * Small enough that it cannot span a loop back onto the same road, which is the
 * whole reason the window exists. Raising this trades the correctness this module
 * is about for tolerance of longer outages, and the right fix for a long outage is
 * to notice it and recompute, not to search further.
 */

export const LOOKBEHIND_M = 60;
/**
 * How far behind the last known progress to look.
 *
 * Non-zero because the first fix after `start()` has no previous progress to speak
 * of, and because a position 20 m *before* the snapped point is a perfectly normal
 * consequence of GPS noise at a standstill. Short, because anything further back
 * is a reversal rather than noise.
 */

export const BACKTRACK_TOLERANCE_M = 25;
/**
 * How far progress may slip backwards between fixes before it is pinned.
 *
 * Within this, backwards movement is accepted — you shuffled, or the fix jittered.
 * Beyond it, progress holds its best value and the position is simply further from
 * the route, which the off-route logic in `useNavigation.ts` then sees.
 */

export const ARRIVAL_M = 30;
/** Within this of the end, you have arrived. About the width of a street. */

export const OFF_ROUTE_M = 50;
/**
 * Baseline perpendicular distance from the route that counts as off it.
 *
 * Deliberately generous. A phone between buildings on a Dhaka street reports 15-30
 * m accuracy routinely, and the route follows a road *centreline* — so a
 * pedestrian correctly walking on the pavement is already 5-10 m off it before any
 * error. A tight threshold produces an off-route banner that cries wolf, and a
 * banner that cries wolf is one the user learns to ignore.
 *
 * `offRouteThreshold()` widens it further when the fix itself is poor.
 */

export const TURN_ANGLE_DEGREES = 25;
/**
 * How much the route must bend to be worth calling a turn.
 *
 * Below this it is a road curving, and announcing it would mean announcing
 * something every fifty metres. Accumulated across consecutive vertices, so a long
 * sweeping bend totalling 60° is reported once rather than as four 15° nudges that
 * each fail the test on their own.
 */

export const TURN_LOOKAHEAD_M = 500;
/** How far ahead to look for the next turn before answering "straight on". */

export const TURN_NOISE_DEGREES = 5;
/**
 * A bend smaller than this is not a change of direction.
 *
 * Only used to decide whether an *opposing* bend interrupts an accumulating turn.
 * Without a floor the test was `Math.sign(delta) !== Math.sign(accumulated)`, and
 * `Math.sign` of a tiny negative number is `-1` — so a segment that is straight to
 * within a ten-thousandth of a degree counted as a reversal and discarded
 * everything accumulated before it. A bend measured across a dead-straight stretch
 * of arranged geometry comes out as -4.8e-5°, which is how that was found.
 *
 * Real data is noisier than that, not cleaner: an `overview=full` polyline is
 * quantised to about a metre, so a 5 m segment carries over a degree of apparent
 * jitter from the rounding alone. Five degrees sits above all of it and far below
 * any corner — a slight turn starts at `TURN_ANGLE_DEGREES`, five times this.
 */

/**
 * The perpendicular distance at which to call this position off-route, widened for
 * a poor fix.
 *
 * A fix that only claims 80 m accuracy cannot be used to prove you are 60 m from
 * the road. Scaling the threshold by the reported accuracy is what stops a bad fix
 * from generating a false off-route — the alternative, discarding the fix outright,
 * is handled separately in `useNavigation.ts` for fixes that are useless entirely.
 */
export function offRouteThreshold(accuracyM?: number): number {
  if (accuracyM === undefined || !Number.isFinite(accuracyM) || accuracyM <= 0) {
    return OFF_ROUTE_M;
  }
  return Math.max(OFF_ROUTE_M, accuracyM * 1.5);
}

/** Great-circle distance in metres. */
export function metresBetween(a: LatLng, b: LatLng): number {
  const latitudeMid = ((a.latitude + b.latitude) / 2) * (Math.PI / 180);
  const dLat = (b.latitude - a.latitude) * METRES_PER_DEGREE;
  const dLon = (b.longitude - a.longitude) * METRES_PER_DEGREE * Math.cos(latitudeMid);
  return Math.hypot(dLat, dLon);
}

/**
 * Initial bearing from `a` to `b`, in degrees clockwise from north.
 *
 * Used for the direction arrow and for the turn detector. The flat-earth form is
 * fine over the tens of metres between two route vertices and avoids the
 * trigonometry of the spherical formula on every fix.
 */
export function bearingBetween(a: LatLng, b: LatLng): number {
  const latitudeMid = ((a.latitude + b.latitude) / 2) * (Math.PI / 180);
  const north = (b.latitude - a.latitude) * METRES_PER_DEGREE;
  const east = (b.longitude - a.longitude) * METRES_PER_DEGREE * Math.cos(latitudeMid);
  const degrees = (Math.atan2(east, north) * 180) / Math.PI;
  return (degrees + 360) % 360;
}

/**
 * The signed difference between two bearings, in (-180, 180].
 *
 * Positive is clockwise, i.e. a right turn. The wrap matters: a turn from 350° to
 * 10° is 20° right, not 340° left, and the naive subtraction gets it backwards.
 */
export function bearingDelta(from: number, to: number): number {
  let delta = ((to - from + 540) % 360) - 180;
  // `-180` and `180` are the same turn; normalise so the sign is stable.
  if (delta === -180) delta = 180;
  return delta;
}

/**
 * Distance from the start of the path to each vertex, in metres.
 *
 * Computed **once per route** and threaded through everything else. Recomputing it
 * per fix would be O(n) haversines a second for a path that has not changed, and a
 * Dhaka crossing is several hundred vertices.
 */
export function cumulativeDistances(path: LatLng[]): number[] {
  const cumulative = new Array<number>(path.length);
  cumulative[0] = 0;
  for (let i = 1; i < path.length; i++) {
    cumulative[i] = cumulative[i - 1] + metresBetween(path[i - 1], path[i]);
  }
  return cumulative;
}

export interface Projection {
  /** 0-1 along the segment. Clamped, so the result is always on the segment. */
  t: number;
  point: LatLng;
  /** Perpendicular distance from the position to the segment, in metres. */
  distanceM: number;
}

/**
 * The closest point on segment `a`→`b` to `p`.
 *
 * Projected into local metres with `a` as the origin, so the dot product is in a
 * metric space rather than in degrees. Doing this in raw lat/lon is a real bug and
 * not a pedantic one: a degree of longitude at Dhaka is 92% of a degree of
 * latitude, so an unprojected calculation biases every snap east-west and the
 * error is largest exactly where it matters, on the diagonal.
 */
export function projectOntoSegment(p: LatLng, a: LatLng, b: LatLng): Projection {
  const scale = Math.cos((a.latitude * Math.PI) / 180) * METRES_PER_DEGREE;
  const ax = 0;
  const ay = 0;
  const bx = (b.longitude - a.longitude) * scale;
  const by = (b.latitude - a.latitude) * METRES_PER_DEGREE;
  const px = (p.longitude - a.longitude) * scale;
  const py = (p.latitude - a.latitude) * METRES_PER_DEGREE;

  const dx = bx - ax;
  const dy = by - ay;
  const lengthSquared = dx * dx + dy * dy;

  // A zero-length segment: OSRM does emit repeated vertices. Treat it as the
  // point itself rather than dividing by zero and producing NaN, which would
  // poison every comparison downstream silently.
  const t = lengthSquared === 0 ? 0 : Math.max(0, Math.min(1, (px * dx + py * dy) / lengthSquared));

  const point: LatLng = {
    latitude: a.latitude + (b.latitude - a.latitude) * t,
    longitude: a.longitude + (b.longitude - a.longitude) * t,
  };

  return { t, point, distanceM: Math.hypot(px - dx * t, py - dy * t) };
}

export interface RouteProgress {
  /** Index of the vertex that starts the segment you are on. */
  index: number;
  /** How far along that segment, 0-1. */
  t: number;
  /** Your position projected onto the route. What the map draws from. */
  snapped: LatLng;
  /** Distance from the route's start to `snapped`, in metres. Never decreases. */
  alongM: number;
  /** Distance from `snapped` to the route's end, in metres. */
  remainingM: number;
  /** Perpendicular distance from your actual position to the route, in metres. */
  offRouteM: number;
}

/** Progress at the very start of a route, before any fix has arrived. */
export function initialProgress(path: LatLng[], cumulative: number[]): RouteProgress {
  return {
    index: 0,
    t: 0,
    snapped: path[0],
    alongM: 0,
    remainingM: cumulative[cumulative.length - 1],
    offRouteM: 0,
  };
}

/**
 * Progress from a position with **no previous progress** — an unwindowed, global
 * search for the closest point on the whole route.
 *
 * Called once, when navigation starts, and never again. The distinction is the
 * point: `advance()` is windowed because it has a previous position to protect, and
 * a global search would let one bad fix teleport across a route that loops back on
 * itself. The first fix has nothing to protect, so the nearest point on the route
 * is the best available guess and a window would be arbitrary.
 *
 * This is what makes the case where the route does **not** start where you are
 * work at all. That is a real flow here, not a corner: the map has a source field,
 * so a user can route from Shahbagh to Mirpur while standing in Dhanmondi. Seeding
 * with `initialProgress` would put them 4 km from their own route, permanently
 * off-route and unable to do anything but recalculate.
 *
 * The honest limitation: on a route that overlaps itself, a global search can pick
 * the wrong leg — the very failure `advance()` guards against. There is no better
 * answer with no history to go on, and it self-corrects, because the next fix is
 * windowed and the user will see the off-route banner if it chose wrongly.
 */
export function locate(
  path: LatLng[],
  cumulative: number[],
  position: LatLng,
): RouteProgress {
  const total = cumulative[cumulative.length - 1];
  let best: { index: number; projection: Projection } | null = null;

  for (let i = 0; i < path.length - 1; i++) {
    const projection = projectOntoSegment(position, path[i], path[i + 1]);
    if (best === null || projection.distanceM < best.projection.distanceM) {
      best = { index: i, projection };
    }
  }

  if (best === null) {
    return { ...initialProgress(path, cumulative), offRouteM: metresBetween(position, path[0]) };
  }

  const alongM =
    cumulative[best.index] +
    best.projection.t * (cumulative[best.index + 1] - cumulative[best.index]);

  return {
    index: best.index,
    t: best.projection.t,
    snapped: best.projection.point,
    alongM,
    remainingM: Math.max(0, total - alongM),
    offRouteM: best.projection.distanceM,
  };
}

/**
 * The next progress, given the previous one and a new position.
 *
 * **Windowed and monotonic** — the two properties the module docstring is about.
 * `previous` is not an optimisation here; it is what makes the answer correct.
 *
 * Returns the previous progress unchanged (with `offRouteM` updated, because that
 * is still true and the caller needs it) when the new position would move progress
 * backwards beyond `BACKTRACK_TOLERANCE_M`. The caller sees a stalled `alongM` and
 * a growing `offRouteM`, which together are exactly the off-route signal.
 */
export function advance(
  path: LatLng[],
  cumulative: number[],
  position: LatLng,
  previous: RouteProgress,
): RouteProgress {
  const total = cumulative[cumulative.length - 1];
  const windowStart = previous.alongM - LOOKBEHIND_M;
  const windowEnd = previous.alongM + LOOKAHEAD_M;

  let best: { index: number; projection: Projection } | null = null;

  for (let i = 0; i < path.length - 1; i++) {
    // Segment `i` spans cumulative[i]..cumulative[i+1]. Skip it unless it
    // overlaps the window at all. Cheap, and it is the whole correctness story.
    if (cumulative[i + 1] < windowStart) continue;
    if (cumulative[i] > windowEnd) break;

    const projection = projectOntoSegment(position, path[i], path[i + 1]);
    if (best === null || projection.distanceM < best.projection.distanceM) {
      best = { index: i, projection };
    }
  }

  // The window contained no segment at all. Only reachable on a degenerate path
  // (a single point), because the window always spans `previous.alongM`.
  if (best === null) {
    return { ...previous, offRouteM: metresBetween(position, previous.snapped) };
  }

  const alongM = cumulative[best.index] + best.projection.t *
    (cumulative[best.index + 1] - cumulative[best.index]);

  if (alongM > windowEnd) {
    // The window admits any segment that *starts* inside it, so the best match can
    // land past the far edge — by one segment length, which on a long straight is
    // hundreds of metres. Without this the effective lookahead is
    // `LOOKAHEAD_M + whatever OSRM's vertex spacing happens to be here`, which is
    // precisely the "window measured in vertices" failure the window was supposed
    // to avoid, reintroduced at its boundary.
    //
    // Holding position is the safe answer. A fix implying progress beyond the
    // window is a dropped-signal gap rather than travel, and the caller sees the
    // stalled `alongM` plus a large `offRouteM` and can offer to recompute.
    return { ...previous, offRouteM: best.projection.distanceM };
  }

  if (alongM < previous.alongM - BACKTRACK_TOLERANCE_M) {
    // Refusing to run backwards. See the module docstring: the line must not grow
    // back, and a real reversal is an off-route event rather than a redraw.
    return { ...previous, offRouteM: best.projection.distanceM };
  }

  return {
    index: best.index,
    t: best.projection.t,
    snapped: best.projection.point,
    alongM,
    remainingM: Math.max(0, total - alongM),
    offRouteM: best.projection.distanceM,
  };
}

/**
 * The part of the route still ahead of you, for the map to draw.
 *
 * Starts at the snapped point rather than at the next vertex, so the line begins
 * exactly where the marker is instead of up to a vertex-length away from it. On a
 * long straight — where OSRM may put 200 m between vertices — snapping to the next
 * vertex instead would leave a visible gap between you and your route.
 */
export function remainingPath(path: LatLng[], progress: RouteProgress): LatLng[] {
  return [progress.snapped, ...path.slice(progress.index + 1)];
}

/**
 * The part already behind you.
 *
 * Returned separately so the map can draw it faintly rather than discarding it.
 * Google removes it entirely; keeping a ghost of it is better here, because this
 * app's whole claim is about *which* route you are on and why — being able to see
 * the line you have actually followed is part of that.
 */
export function travelledPath(path: LatLng[], progress: RouteProgress): LatLng[] {
  return [...path.slice(0, progress.index + 1), progress.snapped];
}

/**
 * Seconds left, from the route's own average pace.
 *
 * **The fallback half of the ETA, not the whole of it.** `etaSeconds` below is what
 * the hook calls; it prefers the live smoothed speed and lands here whenever that
 * speed is unusable, which is every traffic light. Raw instantaneous speed from a
 * phone reads zero at a standstill and spikes on a bad fix, and `remaining / 0` is
 * infinity, so something has to answer when it cannot.
 *
 * The route's own duration is already corrected for the profile by the backend
 * (`_ASSUMED_WALK_KMH` for walking, a traffic factor for driving), so scaling it by
 * the fraction remaining inherits that correction. It is wrong in a predictable
 * direction — it does not know you are stuck — and predictable beats precise here.
 */
export function remainingSeconds(
  progress: RouteProgress,
  totalM: number,
  totalSeconds: number,
): number {
  if (totalM <= 0) return 0;
  return Math.max(0, Math.round(totalSeconds * (progress.remainingM / totalM)));
}

export type TurnDirection =
  | 'straight'
  | 'slight left'
  | 'left'
  | 'sharp left'
  | 'slight right'
  | 'right'
  | 'sharp right';

export interface TurnHint {
  direction: TurnDirection;
  /** Metres from your snapped position to the turn. */
  distanceM: number;
  /** Bearing to head on *now*, degrees from north. Drives the arrow. */
  bearing: number;
}

function describeTurn(delta: number): TurnDirection {
  const magnitude = Math.abs(delta);
  const side = delta > 0 ? 'right' : 'left';
  if (magnitude < TURN_ANGLE_DEGREES) return 'straight';
  if (magnitude < 45) return `slight ${side}` as TurnDirection;
  if (magnitude < 110) return side as TurnDirection;
  return `sharp ${side}` as TurnDirection;
}

/**
 * The next turn worth mentioning, and the direction to head right now.
 *
 * Derived from the route **geometry**, not from routing instructions, and that is
 * what makes it the fallback rather than the main narration: the backend does ask
 * OSRM for `steps` now, so a manoeuvre usually arrives with a road name attached —
 * see `stepAt` below and `instructions.ts`. But a route can still have no steps at
 * all. The straight-line estimate has none, and a malformed manoeuvre is skipped
 * rather than raising.
 *
 * So this says only what a polyline can support: a side and a distance, never a
 * street name and never "turn onto". Claiming more than the data supports is the
 * thing this codebase keeps refusing to do, and a fabricated street name in a
 * navigation instruction is about the worst version of it.
 *
 * Turns are accumulated across vertices so a sweeping bend reads as one turn. The
 * bearing returned is from the snapped position toward a point far enough ahead to
 * be stable — taking it to the very next vertex makes the arrow spin wildly
 * whenever you are standing a metre from one.
 */
export function nextTurn(
  path: LatLng[],
  cumulative: number[],
  progress: RouteProgress,
): TurnHint | null {
  if (path.length < 2) return null;

  const from = progress.snapped;
  const limit = progress.alongM + TURN_LOOKAHEAD_M;

  // The heading to follow now: toward the first vertex at least 25 m ahead, or the
  // end of the route. Anything closer and the bearing is dominated by GPS noise.
  let headingIndex = progress.index + 1;
  while (
    headingIndex < path.length - 1 &&
    cumulative[headingIndex] - progress.alongM < 25
  ) {
    headingIndex++;
  }
  const bearing = bearingBetween(from, path[headingIndex]);

  let accumulated = 0;
  let reference = bearing;

  for (let i = headingIndex; i < path.length - 1; i++) {
    if (cumulative[i] > limit) break;
    const segmentBearing = bearingBetween(path[i], path[i + 1]);
    const delta = bearingDelta(reference, segmentBearing);

    // Same-signed deltas accumulate into one turn; a sign change restarts the
    // accumulation, because a left then a right is not one 0° turn.
    //
    // The noise floor is load-bearing, and `delta !== 0` is not enough: a
    // straight stretch does not produce a delta of exactly zero, it produces
    // -4.8e-5, and `Math.sign` of that is -1. So a bend interrupted by a segment
    // that runs true -- a flyover approach, a road straightening briefly between
    // two curves -- counted as a reversal and threw away everything accumulated
    // before it. The curve then came out as "straight" and the turn was never
    // announced. See `TURN_NOISE_DEGREES`.
    if (
      accumulated !== 0 &&
      Math.abs(delta) > TURN_NOISE_DEGREES &&
      Math.sign(delta) !== Math.sign(accumulated)
    ) {
      accumulated = delta;
    } else {
      accumulated += delta;
    }
    reference = segmentBearing;

    if (Math.abs(accumulated) >= TURN_ANGLE_DEGREES) {
      return {
        direction: describeTurn(accumulated),
        distanceM: Math.max(0, cumulative[i] - progress.alongM),
        bearing,
      };
    }
  }

  return { direction: 'straight', distanceM: progress.remainingM, bearing };
}

/**
 * A manoeuvre, reduced to what this module needs. Structurally compatible with
 * `RouteStep` from `route.service.ts`, declared locally so the pure geometry does
 * not import the service layer.
 */
export interface NavStep {
  name: string;
  maneuver_type: string;
  modifier: string;
  distance_m: number;
  start_m: number;
}

export interface StepHint {
  /** The step being travelled along now. */
  current: NavStep | null;
  /** The step whose manoeuvre is coming up -- what to announce. */
  next: NavStep | null;
  /** Metres from the snapped position to that manoeuvre. */
  distanceM: number;
}

/**
 * Which manoeuvre is next, by distance along the route.
 *
 * Matched on `start_m` rather than by proximity to the manoeuvre's coordinates,
 * and the difference matters on exactly the geometry this app runs on: a route
 * that passes the same junction twice has two manoeuvres metres apart, and a
 * nearest-coordinate match would announce the wrong one. `alongM` is monotonic and
 * already windowed, so it cannot confuse them.
 *
 * `next` is the step whose *start* is still ahead — a step's `start_m` is where its
 * manoeuvre happens, so "the next manoeuvre" is the next step's start, not the
 * current step's. Returning the final `arrive` step is correct: its distance is the
 * distance to the destination.
 */
export function stepAt(steps: NavStep[], progress: RouteProgress): StepHint {
  if (steps.length === 0) {
    return { current: null, next: null, distanceM: progress.remainingM };
  }

  let currentIndex = 0;
  for (let i = 0; i < steps.length; i++) {
    if (steps[i].start_m <= progress.alongM + 1) currentIndex = i;
    else break;
  }

  const current = steps[currentIndex];
  const next = currentIndex + 1 < steps.length ? steps[currentIndex + 1] : null;
  const distanceM = next
    ? Math.max(0, next.start_m - progress.alongM)
    : progress.remainingM;

  return { current, next, distanceM };
}

export const MIN_USABLE_SPEED_MPS = 0.5;
/**
 * Below this, the live speed is not usable for an ETA.
 *
 * 0.5 m/s is 1.8 km/h — slower than any travel. Standing at a light reads about
 * zero, and `remaining / 0` is infinity, so an ETA built naively on live speed
 * shows "∞ min" at every junction. Below the floor the estimate falls back to the
 * route's own pace, which is a number that at least means something.
 */

export const SPEED_SMOOTHING = 0.25;
/**
 * How much of each new speed reading to believe, 0-1.
 *
 * An exponential moving average with α=0.25 and a fix every two seconds gives a
 * time constant of about eight seconds. Raw phone speed is extremely noisy — it
 * spikes on a bad fix and drops to zero between satellites — so an unsmoothed ETA
 * swings by minutes between updates, and a number that jumps around is one nobody
 * can plan with.
 *
 * Lower is steadier and slower to react; higher tracks a genuine change in pace
 * faster and reintroduces the jitter. This is the knob to turn if the ETA feels
 * either sluggish or twitchy on a real walk.
 */

/**
 * The next smoothed speed, in m/s, or null when there is nothing usable yet.
 *
 * `reading` is `coords.speed` from the fix, which is **null on Android when the
 * provider has no estimate and sometimes a negative sentinel** — both are discarded
 * rather than smoothed in, because feeding -1 into an average poisons it for the
 * next thirty seconds.
 */
export function smoothSpeed(previous: number | null, reading: number | null | undefined): number | null {
  if (reading === null || reading === undefined || !Number.isFinite(reading) || reading < 0) {
    return previous;
  }
  if (previous === null) return reading;
  return previous + SPEED_SMOOTHING * (reading - previous);
}

/**
 * Seconds left, from the live smoothed speed where it is usable and from the
 * route's own pace where it is not.
 *
 * The live figure is what makes the ETA respond to how you are actually moving: a
 * route scored for driving, walked, would otherwise count down four times too fast.
 * The fallback is what stops it reading infinity at a red light.
 *
 * Both are estimates. The live one is right about your pace and knows nothing about
 * the traffic ahead; the route's is right about the road and knows nothing about
 * you. Neither is a promise, which is why the banner labels the number "left"
 * rather than "arrival".
 */
export function etaSeconds(
  progress: RouteProgress,
  totalM: number,
  totalSeconds: number,
  speedMps: number | null,
): number {
  if (speedMps !== null && speedMps >= MIN_USABLE_SPEED_MPS) {
    return Math.max(0, Math.round(progress.remainingM / speedMps));
  }
  return remainingSeconds(progress, totalM, totalSeconds);
}

/** Whether this progress counts as having arrived. */
export function hasArrived(progress: RouteProgress): boolean {
  return progress.remainingM <= ARRIVAL_M;
}

/**
 * Distance for a user, in the shortest honest form.
 *
 * Rounded to 10 m below a kilometre: a phone cannot tell you it is 237 m, and
 * printing that implies a precision the fix does not have.
 */
export function formatDistance(metres: number): string {
  if (metres < 1000) return `${Math.max(0, Math.round(metres / 10) * 10)} m`;
  return `${(metres / 1000).toFixed(metres < 10_000 ? 1 : 0)} km`;
}

/** Duration for a user. "<1 min" rather than "0 min", which reads as broken. */
export function formatDuration(seconds: number): string {
  if (seconds < 60) return '<1 min';
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  return `${hours} h ${minutes % 60} min`;
}
