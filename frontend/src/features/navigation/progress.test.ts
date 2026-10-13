/**
 * Route progress, tested against arranged geometry.
 *
 * Every test here corresponds to something that would be invisible on a phone
 * until it was embarrassing. The two that matter most are
 * `does not teleport across a route that loops back on itself` and `never lets the
 * route grow back` — those are the failures that make a naive implementation of
 * this feature unusable, and neither shows up in a straight-line walk test.
 */

import {
  ARRIVAL_M,
  MIN_USABLE_SPEED_MPS,
  etaSeconds,
  smoothSpeed,
  stepAt,
  type NavStep,
  BACKTRACK_TOLERANCE_M,
  LOOKAHEAD_M,
  OFF_ROUTE_M,
  advance,
  bearingBetween,
  bearingDelta,
  cumulativeDistances,
  formatDistance,
  formatDuration,
  hasArrived,
  initialProgress,
  locate,
  metresBetween,
  nextTurn,
  offRouteThreshold,
  projectOntoSegment,
  remainingPath,
  remainingSeconds,
  travelledPath,
  type LatLng,
} from './progress';

const METRES_PER_DEGREE = 111_320;

/** Dhaka, near Shahbagh. Latitude matters: longitude scaling is 0.92 here. */
const ORIGIN: LatLng = { latitude: 23.7383, longitude: 90.3947 };

/** A point `north` metres north and `east` metres east of ORIGIN. */
function at(north: number, east: number): LatLng {
  const scale = Math.cos((ORIGIN.latitude * Math.PI) / 180) * METRES_PER_DEGREE;
  return {
    latitude: ORIGIN.latitude + north / METRES_PER_DEGREE,
    longitude: ORIGIN.longitude + east / scale,
  };
}

/**
 * Advance through a sequence of positions, as a walker would.
 *
 * Needed because `advance` deliberately refuses a jump beyond `LOOKAHEAD_M` -- so a
 * test that teleports from the start to the destination is testing the gap
 * rejection, not arrival. Stepping is also what the hook does with real fixes.
 */
function walk(path: LatLng[], cumulative: number[], metres: number[]) {
  let progress = initialProgress(path, cumulative);
  for (const north of metres) {
    progress = advance(path, cumulative, at(north, 0), progress);
  }
  return progress;
}

/** A straight northward path, one vertex every `step` metres. */
function straightPath(lengthM: number, step = 100): LatLng[] {
  const path: LatLng[] = [];
  for (let d = 0; d <= lengthM; d += step) path.push(at(d, 0));
  return path;
}

describe('metresBetween', () => {
  it('measures a known northward offset', () => {
    expect(metresBetween(ORIGIN, at(100, 0))).toBeCloseTo(100, 0);
  });

  it('measures a known eastward offset, accounting for latitude', () => {
    // The point of the cos(lat) term. Without it this would read ~108 m.
    expect(metresBetween(ORIGIN, at(0, 100))).toBeCloseTo(100, 0);
  });

  it('is symmetric', () => {
    expect(metresBetween(ORIGIN, at(70, 40))).toBeCloseTo(
      metresBetween(at(70, 40), ORIGIN),
      6,
    );
  });
});

describe('bearings', () => {
  it('reads north as 0 and east as 90', () => {
    expect(bearingBetween(ORIGIN, at(100, 0))).toBeCloseTo(0, 0);
    expect(bearingBetween(ORIGIN, at(0, 100))).toBeCloseTo(90, 0);
    expect(bearingBetween(ORIGIN, at(-100, 0))).toBeCloseTo(180, 0);
    expect(bearingBetween(ORIGIN, at(0, -100))).toBeCloseTo(270, 0);
  });

  it('wraps a turn across north the short way', () => {
    // The bug the signed delta exists to avoid: 350 -> 10 is 20 right, not 340 left.
    expect(bearingDelta(350, 10)).toBe(20);
    expect(bearingDelta(10, 350)).toBe(-20);
  });

  it('is signed clockwise', () => {
    expect(bearingDelta(0, 90)).toBe(90);
    expect(bearingDelta(0, 270)).toBe(-90);
  });
});

describe('projectOntoSegment', () => {
  const a = at(0, 0);
  const b = at(100, 0);

  it('finds the perpendicular foot in the middle of a segment', () => {
    const projection = projectOntoSegment(at(50, 20), a, b);
    expect(projection.t).toBeCloseTo(0.5, 2);
    expect(projection.distanceM).toBeCloseTo(20, 0);
  });

  it('clamps past the end rather than extrapolating', () => {
    const projection = projectOntoSegment(at(500, 0), a, b);
    expect(projection.t).toBe(1);
    expect(projection.distanceM).toBeCloseTo(400, 0);
  });

  it('clamps before the start', () => {
    const projection = projectOntoSegment(at(-80, 0), a, b);
    expect(projection.t).toBe(0);
    expect(projection.distanceM).toBeCloseTo(80, 0);
  });

  it('survives a zero-length segment without producing NaN', () => {
    // OSRM does emit repeated vertices. A NaN here would poison every
    // comparison downstream and do it silently, which is why this is a test and
    // not a guard nobody checks.
    const projection = projectOntoSegment(at(10, 0), a, a);
    expect(Number.isNaN(projection.distanceM)).toBe(false);
    expect(projection.t).toBe(0);
    expect(projection.distanceM).toBeCloseTo(10, 0);
  });

  it('does not bias east-west, which raw lat/lon arithmetic would', () => {
    // 100 m east of the midpoint of a northward segment is 100 m off it. Done in
    // degrees without the cos(lat) scale, this reads about 92 m.
    const projection = projectOntoSegment(at(50, 100), a, b);
    expect(projection.distanceM).toBeCloseTo(100, 0);
  });
});

describe('cumulativeDistances', () => {
  it('starts at zero and totals the path', () => {
    const cumulative = cumulativeDistances(straightPath(500));
    expect(cumulative[0]).toBe(0);
    expect(cumulative[cumulative.length - 1]).toBeCloseTo(500, 0);
  });

  it('is monotonically non-decreasing', () => {
    const cumulative = cumulativeDistances(straightPath(900, 70));
    for (let i = 1; i < cumulative.length; i++) {
      expect(cumulative[i]).toBeGreaterThanOrEqual(cumulative[i - 1]);
    }
  });
});

describe('advance', () => {
  const path = straightPath(1000);
  const cumulative = cumulativeDistances(path);

  it('reports no progress before the first fix', () => {
    const progress = initialProgress(path, cumulative);
    expect(progress.alongM).toBe(0);
    expect(progress.remainingM).toBeCloseTo(1000, 0);
    expect(progress.snapped).toEqual(path[0]);
  });

  it('moves progress forward as the position moves along the route', () => {
    let progress = initialProgress(path, cumulative);
    progress = advance(path, cumulative, at(250, 0), progress);
    expect(progress.alongM).toBeCloseTo(250, 0);
    expect(progress.remainingM).toBeCloseTo(750, 0);
    expect(progress.offRouteM).toBeLessThan(1);
  });

  it('snaps a position beside the route onto it', () => {
    let progress = initialProgress(path, cumulative);
    progress = advance(path, cumulative, at(300, 12), progress);
    expect(progress.alongM).toBeCloseTo(300, 0);
    expect(progress.offRouteM).toBeCloseTo(12, 0);
    // The snapped point is on the line, not where the phone said.
    expect(metresBetween(progress.snapped, at(300, 0))).toBeLessThan(1);
  });

  it('never lets the route grow back', () => {
    // The visible symptom of allowing it: the line twitches longer and shorter
    // every other second while you stand still.
    let progress = initialProgress(path, cumulative);
    progress = advance(path, cumulative, at(400, 0), progress);
    const reached = progress.alongM;

    for (const jitter of [-8, 5, -15, 3, -20]) {
      progress = advance(path, cumulative, at(400 + jitter, 0), progress);
      expect(progress.alongM).toBeGreaterThanOrEqual(reached - BACKTRACK_TOLERANCE_M);
    }
  });

  it('pins progress when the position moves well backwards', () => {
    let progress = walk(path, cumulative, [200, 400, 500]);
    const reached = progress.alongM;

    progress = advance(path, cumulative, at(300, 0), progress);
    expect(progress.alongM).toBe(reached);
    // ...and says how far away you now are, which is the off-route signal.
    expect(progress.offRouteM).toBeGreaterThan(BACKTRACK_TOLERANCE_M);
  });

  it('accepts a small genuine shuffle backwards', () => {
    let progress = walk(path, cumulative, [200, 400, 500]);
    progress = advance(path, cumulative, at(490, 0), progress);
    expect(progress.alongM).toBeCloseTo(490, 0);
  });

  it('does not teleport across a route that loops back on itself', () => {
    // THE failure this module exists to prevent. An out-and-back: 1 km north,
    // then 1 km back south, 15 m to the east. Standing 200 m along the outbound
    // leg, the globally closest point is on the *return* leg, 1.8 km ahead.
    const outAndBack: LatLng[] = [
      ...straightPath(1000, 100),
      ...straightPath(1000, 100).reverse().map(p => ({
        latitude: p.latitude,
        longitude: at(0, 15).longitude + (p.longitude - ORIGIN.longitude),
      })),
    ];
    const cum = cumulativeDistances(outAndBack);

    let progress = initialProgress(outAndBack, cum);
    progress = advance(outAndBack, cum, at(200, 0), progress);

    // Correct: ~200 m in, with ~1.8 km to go. A global search gives ~1.8 km in.
    expect(progress.alongM).toBeCloseTo(200, -1);
    expect(progress.remainingM).toBeGreaterThan(1500);
  });

  it('does not search further ahead than the lookahead window', () => {
    // A fix that jumps 900 m forward is a dropped-signal gap, not progress, and
    // must not be believed past the window. Holding position is the safe answer:
    // the caller sees a large offRouteM and can offer to recompute.
    let progress = initialProgress(path, cumulative);
    progress = advance(path, cumulative, at(100, 0), progress);
    const before = progress.alongM;

    progress = advance(path, cumulative, at(100 + LOOKAHEAD_M + 300, 0), progress);
    expect(progress.alongM).toBeLessThanOrEqual(before + LOOKAHEAD_M + 1);
  });

  it('survives a single-vertex path without crashing', () => {
    const degenerate = [at(0, 0)];
    const cum = cumulativeDistances(degenerate);
    const progress = advance(degenerate, cum, at(30, 0), initialProgress(degenerate, cum));
    expect(Number.isNaN(progress.alongM)).toBe(false);
    expect(progress.offRouteM).toBeCloseTo(30, 0);
  });

  it('handles uneven vertex density, which is why the window is in metres', () => {
    // Two vertices across 600 m, then ten in the next 50 m — an OSRM geometry
    // around a junction. A window counted in vertices would be 600 m in one place
    // and 5 m in another.
    const uneven: LatLng[] = [at(0, 0), at(600, 0)];
    for (let d = 605; d <= 650; d += 5) uneven.push(at(d, 0));
    const cum = cumulativeDistances(uneven);

    let progress = initialProgress(uneven, cum);
    progress = advance(uneven, cum, at(300, 0), progress);
    expect(progress.alongM).toBeCloseTo(300, 0);
  });
});

describe('locate', () => {
  const path = straightPath(1000);
  const cumulative = cumulativeDistances(path);

  it('finds a position far along a route with no previous progress', () => {
    // The flow this exists for: routing from a searched source while standing
    // somewhere else. `advance` from `initialProgress` would refuse this as a gap
    // and leave the user permanently off their own route.
    const progress = locate(path, cumulative, at(700, 0));
    expect(progress.alongM).toBeCloseTo(700, 0);
    expect(progress.remainingM).toBeCloseTo(300, 0);
  });

  it('reports how far off the route the starting position is', () => {
    const progress = locate(path, cumulative, at(500, 120));
    expect(progress.alongM).toBeCloseTo(500, 0);
    expect(progress.offRouteM).toBeCloseTo(120, 0);
  });

  it('hands back progress that `advance` can continue from', () => {
    let progress = locate(path, cumulative, at(700, 0));
    progress = advance(path, cumulative, at(760, 0), progress);
    expect(progress.alongM).toBeCloseTo(760, 0);
  });

  it('does not crash on a single-vertex path', () => {
    const single = [at(0, 0)];
    const progress = locate(single, cumulativeDistances(single), at(40, 0));
    expect(Number.isNaN(progress.alongM)).toBe(false);
  });
});

describe('remainingPath and travelledPath', () => {
  const path = straightPath(500);
  const cumulative = cumulativeDistances(path);

  it('starts the remaining line exactly at the snapped point', () => {
    // Not at the next vertex. On a long straight that would leave a visible gap
    // between the marker and its own route.
    const progress = advance(path, cumulative, at(250, 0), initialProgress(path, cumulative));
    const remaining = remainingPath(path, progress);
    expect(remaining[0]).toEqual(progress.snapped);
  });

  it('ends the remaining line at the destination', () => {
    const progress = advance(path, cumulative, at(250, 0), initialProgress(path, cumulative));
    const remaining = remainingPath(path, progress);
    expect(remaining[remaining.length - 1]).toEqual(path[path.length - 1]);
  });

  it('ends the travelled line at the snapped point', () => {
    const progress = advance(path, cumulative, at(250, 0), initialProgress(path, cumulative));
    const travelled = travelledPath(path, progress);
    expect(travelled[travelled.length - 1]).toEqual(progress.snapped);
    expect(travelled[0]).toEqual(path[0]);
  });

  it('together they account for the whole route', () => {
    const progress = advance(path, cumulative, at(250, 0), initialProgress(path, cumulative));
    const travelled = travelledPath(path, progress);
    const remaining = remainingPath(path, progress);
    // The snapped point is in both, hence the -1.
    expect(travelled.length + remaining.length - 1).toBe(path.length + 1);
  });

  it('keeps the whole route remaining at the start', () => {
    // `path.length`, not `length + 1`: at the start the snapped point IS path[0],
    // so it replaces the first vertex rather than being prepended to it.
    const progress = initialProgress(path, cumulative);
    expect(remainingPath(path, progress).length).toBe(path.length);
  });

  it('always yields at least one point, so the Polyline still draws at the end', () => {
    const progress = walk(path, cumulative, [100, 200, 300, 400, 500]);
    expect(remainingPath(path, progress).length).toBeGreaterThanOrEqual(1);
  });
});

describe('remainingSeconds', () => {
  const path = straightPath(1000);
  const cumulative = cumulativeDistances(path);

  it('scales the route’s own duration by the fraction left', () => {
    const progress = advance(path, cumulative, at(250, 0), initialProgress(path, cumulative));
    expect(remainingSeconds(progress, 1000, 600)).toBeCloseTo(450, -1);
  });

  it('reaches zero at the destination', () => {
    const progress = walk(path, cumulative, [200, 400, 600, 800, 1000]);
    expect(remainingSeconds(progress, 1000, 600)).toBeLessThanOrEqual(1);
  });

  it('does not divide by zero on a zero-length route', () => {
    const progress = initialProgress(path, cumulative);
    expect(remainingSeconds(progress, 0, 600)).toBe(0);
  });
});

describe('offRouteThreshold', () => {
  it('uses the baseline for a good fix', () => {
    expect(offRouteThreshold(8)).toBe(OFF_ROUTE_M);
  });

  it('widens for a poor fix, so a bad fix cannot prove you left the route', () => {
    expect(offRouteThreshold(80)).toBeGreaterThan(OFF_ROUTE_M);
  });

  it('falls back to the baseline when accuracy is unknown or nonsense', () => {
    expect(offRouteThreshold(undefined)).toBe(OFF_ROUTE_M);
    expect(offRouteThreshold(0)).toBe(OFF_ROUTE_M);
    expect(offRouteThreshold(Number.NaN)).toBe(OFF_ROUTE_M);
  });
});

describe('nextTurn', () => {
  it('says straight on a straight route', () => {
    const path = straightPath(800);
    const cumulative = cumulativeDistances(path);
    const hint = nextTurn(path, cumulative, initialProgress(path, cumulative));
    expect(hint?.direction).toBe('straight');
  });

  it('names the side of a right-angle turn', () => {
    // North 300 m, then east.
    const path = [at(0, 0), at(150, 0), at(300, 0), at(300, 150), at(300, 300)];
    const cumulative = cumulativeDistances(path);
    const hint = nextTurn(path, cumulative, initialProgress(path, cumulative));
    expect(hint?.direction).toBe('right');
    expect(hint?.distanceM).toBeCloseTo(300, -1);
  });

  it('names the other side', () => {
    const path = [at(0, 0), at(150, 0), at(300, 0), at(300, -150), at(300, -300)];
    const cumulative = cumulativeDistances(path);
    expect(nextTurn(path, cumulative, initialProgress(path, cumulative))?.direction).toBe(
      'left',
    );
  });

  it('reports the first turn, not the sum of two corners', () => {
    // A tight double-right (effectively a U-turn) is two right turns, and
    // "turn right, then right again" is what a person needs to hear. Reporting
    // the 180-degree total would describe a manoeuvre that does not exist at
    // either corner.
    const path = [at(0, 0), at(200, 0), at(200, 10), at(0, 10)];
    const cumulative = cumulativeDistances(path);
    const hint = nextTurn(path, cumulative, initialProgress(path, cumulative));
    expect(hint?.direction).toBe('right');
    expect(hint?.distanceM).toBeCloseTo(200, -1);
  });

  it('calls a single hairpin sharp', () => {
    // One vertex, 150 degrees of bend -- a genuine hairpin rather than two
    // corners that happen to add up.
    const path = [at(0, 0), at(200, 0), at(130, 100)];
    const cumulative = cumulativeDistances(path);
    const hint = nextTurn(path, cumulative, initialProgress(path, cumulative));
    expect(hint?.direction).toBe('sharp right');
  });

  it('reports a sweeping bend once rather than as a series of nudges', () => {
    // Eight 10-degree steps. Each one alone is below TURN_ANGLE_DEGREES and would
    // be reported as "straight"; together they are an 80-degree turn.
    const path: LatLng[] = [at(0, 0)];
    let heading = 0;
    let north = 0;
    let east = 0;
    for (let i = 0; i < 8; i++) {
      heading += 10;
      north += 40 * Math.cos((heading * Math.PI) / 180);
      east += 40 * Math.sin((heading * Math.PI) / 180);
      path.push(at(north, east));
    }
    const cumulative = cumulativeDistances(path);
    const hint = nextTurn(path, cumulative, initialProgress(path, cumulative));
    expect(hint?.direction).not.toBe('straight');
    expect(hint?.direction).toContain('right');
  });

  it('gives a bearing to head on now', () => {
    const path = [at(0, 0), at(300, 0), at(300, 300)];
    const cumulative = cumulativeDistances(path);
    const hint = nextTurn(path, cumulative, initialProgress(path, cumulative));
    expect(hint?.bearing).toBeCloseTo(0, 0);
  });

  it('returns null only for a path with nothing in it', () => {
    const single = [at(0, 0)];
    expect(nextTurn(single, cumulativeDistances(single), initialProgress(single, [0]))).toBe(
      null,
    );
  });
});

describe('hasArrived', () => {
  const path = straightPath(500);
  const cumulative = cumulativeDistances(path);

  it('is false mid-route', () => {
    const progress = walk(path, cumulative, [250]);
    expect(hasArrived(progress)).toBe(false);
  });

  it('is true within the arrival radius of the end', () => {
    const progress = walk(path, cumulative, [200, 400, 500 - ARRIVAL_M / 2]);
    expect(hasArrived(progress)).toBe(true);
  });
});

describe('formatting', () => {
  it('rounds metres to ten, because a phone cannot tell you 237', () => {
    expect(formatDistance(237)).toBe('240 m');
    expect(formatDistance(4)).toBe('0 m');
  });

  it('switches to kilometres with one decimal, then none', () => {
    expect(formatDistance(1500)).toBe('1.5 km');
    expect(formatDistance(12_400)).toBe('12 km');
  });

  it('never prints a zero-minute duration', () => {
    expect(formatDuration(0)).toBe('<1 min');
    expect(formatDuration(30)).toBe('<1 min');
  });

  it('prints minutes, then hours and minutes', () => {
    expect(formatDuration(600)).toBe('10 min');
    expect(formatDuration(4500)).toBe('1 h 15 min');
  });
});


describe('stepAt', () => {
  const path = straightPath(1000);
  const cumulative = cumulativeDistances(path);

  const steps: NavStep[] = [
    { name: 'Mirpur Road', maneuver_type: 'depart', modifier: '', distance_m: 300, start_m: 0 },
    { name: '', maneuver_type: 'turn', modifier: 'left', distance_m: 400, start_m: 300 },
    { name: 'Green Road', maneuver_type: 'turn', modifier: 'right', distance_m: 300, start_m: 700 },
    { name: '', maneuver_type: 'arrive', modifier: '', distance_m: 0, start_m: 1000 },
  ];

  it('reports the first step and the first manoeuvre at the start', () => {
    const hint = stepAt(steps, initialProgress(path, cumulative));
    expect(hint.current?.name).toBe('Mirpur Road');
    expect(hint.next?.modifier).toBe('left');
    expect(hint.distanceM).toBeCloseTo(300, 0);
  });

  it('counts down to the next manoeuvre as you move', () => {
    const progress = walk(path, cumulative, [100, 200]);
    const hint = stepAt(steps, progress);
    expect(hint.next?.modifier).toBe('left');
    expect(hint.distanceM).toBeCloseTo(100, 0);
  });

  it('advances to the next step once the manoeuvre is passed', () => {
    const progress = walk(path, cumulative, [200, 350]);
    const hint = stepAt(steps, progress);
    expect(hint.current?.modifier).toBe('left');
    expect(hint.next?.name).toBe('Green Road');
    expect(hint.distanceM).toBeCloseTo(350, 0);
  });

  it('reaches the arrival step at the end', () => {
    const progress = walk(path, cumulative, [200, 400, 600, 750]);
    const hint = stepAt(steps, progress);
    expect(hint.next?.maneuver_type).toBe('arrive');
  });

  it('matches by distance along the route, so a doubled-back junction is safe', () => {
    // Two manoeuvres at the same place: 400 m out and 400 m back. Matching on
    // coordinates would announce whichever was nearest; `start_m` cannot confuse
    // them because `alongM` is monotonic.
    const doubled: NavStep[] = [
      { name: 'A', maneuver_type: 'depart', modifier: '', distance_m: 400, start_m: 0 },
      { name: 'B', maneuver_type: 'turn', modifier: 'left', distance_m: 100, start_m: 400 },
      { name: 'C', maneuver_type: 'turn', modifier: 'left', distance_m: 400, start_m: 500 },
      { name: '', maneuver_type: 'arrive', modifier: '', distance_m: 0, start_m: 900 },
    ];
    const early = stepAt(doubled, walk(path, cumulative, [100, 200]));
    expect(early.next?.name).toBe('B');

    const later = stepAt(doubled, walk(path, cumulative, [300, 450]));
    expect(later.next?.name).toBe('C');
  });

  it('falls back to the remaining distance with no steps at all', () => {
    const progress = walk(path, cumulative, [250]);
    const hint = stepAt([], progress);
    expect(hint.current).toBe(null);
    expect(hint.next).toBe(null);
    expect(hint.distanceM).toBeCloseTo(progress.remainingM, 0);
  });
});

describe('smoothSpeed', () => {
  it('takes the first usable reading as-is', () => {
    expect(smoothSpeed(null, 4)).toBe(4);
  });

  it('moves toward a new reading rather than jumping to it', () => {
    const next = smoothSpeed(4, 8);
    expect(next).toBeGreaterThan(4);
    expect(next).toBeLessThan(8);
  });

  it('discards null, undefined and the negative sentinel', () => {
    // `coords.speed` is null on Android when the provider has no estimate, and
    // occasionally -1. Averaging either in poisons the figure for ~30 seconds.
    expect(smoothSpeed(4, null)).toBe(4);
    expect(smoothSpeed(4, undefined)).toBe(4);
    expect(smoothSpeed(4, -1)).toBe(4);
    expect(smoothSpeed(4, Number.NaN)).toBe(4);
  });

  it('stays null while every reading is unusable', () => {
    expect(smoothSpeed(null, null)).toBe(null);
    expect(smoothSpeed(null, -1)).toBe(null);
  });

  it('accepts a genuine zero, which is a standstill rather than a bad reading', () => {
    expect(smoothSpeed(null, 0)).toBe(0);
  });

  it('converges on a steady pace', () => {
    let speed: number | null = null;
    for (let i = 0; i < 40; i++) speed = smoothSpeed(speed, 1.4);
    expect(speed).toBeCloseTo(1.4, 2);
  });
});

describe('etaSeconds', () => {
  const path = straightPath(1000);
  const cumulative = cumulativeDistances(path);
  const progress = () => walk(path, cumulative, [200, 400, 500]);

  it('uses the live speed when it is usable', () => {
    // 500 m left at 2 m/s is 250 s, regardless of what the route's pace was.
    expect(etaSeconds(progress(), 1000, 600, 2)).toBeCloseTo(250, -1);
  });

  it('is not the route pace when the two disagree', () => {
    // The route says 600 s for 1000 m, so half of it would be 300 s. Walking it at
    // 1 m/s is 500 s, and that is the number the user needs.
    const live = etaSeconds(progress(), 1000, 600, 1);
    expect(live).toBeCloseTo(500, -1);
    expect(live).not.toBeCloseTo(300, -1);
  });

  it('falls back to the route pace at a standstill rather than reading infinity', () => {
    const eta = etaSeconds(progress(), 1000, 600, 0);
    expect(Number.isFinite(eta)).toBe(true);
    expect(eta).toBeCloseTo(300, -1);
  });

  it('falls back below the usable-speed floor', () => {
    const eta = etaSeconds(progress(), 1000, 600, MIN_USABLE_SPEED_MPS - 0.01);
    expect(eta).toBeCloseTo(300, -1);
  });

  it('falls back when no speed has ever been read', () => {
    expect(etaSeconds(progress(), 1000, 600, null)).toBeCloseTo(300, -1);
  });

  it('reaches zero at the destination on either source', () => {
    const done = walk(path, cumulative, [200, 400, 600, 800, 1000]);
    expect(etaSeconds(done, 1000, 600, 2)).toBeLessThanOrEqual(1);
    expect(etaSeconds(done, 1000, 600, null)).toBeLessThanOrEqual(1);
  });
});
