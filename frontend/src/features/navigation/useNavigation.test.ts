/**
 * The navigation hook's contract, read out of its source.
 *
 * There is no React test renderer in this project, so these are source scans
 * rather than behavioural tests — the same approach `theme.ui.test.ts` and
 * `features/risk/clusters.test.ts` take. That is a real limit and worth stating:
 * they prove the *shape* of the hook, not that it runs. The arithmetic it runs on
 * is covered properly in `progress.test.ts`, which is where the failures that
 * matter actually live.
 *
 * What they do cover is five properties that are invisible until they bite, and
 * three of them were bugs in the first version of this file:
 *
 * 1. the subscription reaches its handler through a ref, or a mid-route
 *    recalculation snaps fixes onto the route that is no longer on screen;
 * 2. it is removed on unmount, or the GPS outlives the screen;
 * 3. it never re-routes on its own;
 * 4. the camera follows through `mapRef`, never through `setRegion`, or every fix
 *    refetches the risk layer;
 * 5. navigation does not start just because a route exists.
 */

import fs from 'fs';
import path from 'path';

const HERE = __dirname;
const SRC = path.join(HERE, '..', '..');

function read(...segments: string[]): string {
  return fs.readFileSync(path.join(...segments), 'utf8');
}

/**
 * Source with comments stripped.
 *
 * Load-bearing for the same reason it is in `features/risk/clusters.test.ts`:
 * every rule below is explained in a comment at the site it governs, so a scanner
 * that reads comments fails on the documentation of the rule it is checking.
 */
function codeOnly(source: string): string {
  return source
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/^[ \t]*\/\/.*$/gm, '');
}

const hook = codeOnly(read(HERE, 'useNavigation.ts'));
const mapScreen = codeOnly(read(SRC, 'screens', 'Map', 'MapScreen.tsx'));
const banner = codeOnly(read(HERE, 'NavigationBanner.tsx'));

describe('the location subscription', () => {
  it('calls its handler through a ref, not directly', () => {
    // `watchPositionAsync` captures the callback for the life of the
    // subscription. Passing `onFix` directly means a recalculation mid-walk
    // leaves the subscription holding a handler closed over the OLD path, and
    // since recalculation also resets progress, every later fix is located on a
    // route that is no longer displayed.
    const call = hook.split('watchPositionAsync(')[1] ?? '';
    expect(call).toContain('onFixRef.current(fix)');
    expect(call).not.toMatch(/\n\s*onFix,/);
  });

  it('keeps that ref current', () => {
    expect(hook).toMatch(/onFixRef\.current\s*=\s*onFix/);
  });

  it('is removed on unmount', () => {
    // The one cleanup that cannot be skipped: a subscription outliving the screen
    // keeps the radio awake with nothing reading it.
    const cleanup = hook.split('useEffect(() => () =>')[1] ?? '';
    expect(cleanup).toContain('subscription.current?.remove()');
  });

  it('is removed on stop and replaced rather than stacked on start', () => {
    const stop = hook.split('const stop = useCallback(')[1]?.split('}, [])')[0] ?? '';
    expect(stop).toContain('subscription.current?.remove()');

    const start = hook.split('const start = useCallback(')[1] ?? '';
    // A second `start()` must not leave the first watcher running.
    expect(start).toContain('subscription.current?.remove()');
  });

  it('is released on arrival', () => {
    // An arrived navigator still polling high-accuracy GPS is a battery drain
    // with no output.
    const arrival = hook.split('if (arrived) {')[1] ?? '';
    expect(arrival).toContain('subscription.current?.remove()');
  });

  it('asks for a navigation-rate fix, not the app-wide one', () => {
    // LOCATION_UPDATE_INTERVAL is 60 s — a fix every 80 m at walking pace, so the
    // route would jump a block at a time.
    expect(hook).toContain('timeInterval: NAV_INTERVAL_MS');
    expect(hook).not.toContain('LOCATION_UPDATE_INTERVAL');
  });

  it('does not go through the shared LocationService singleton', () => {
    // That singleton holds ONE subscription field, so using it here would
    // silently replace any other watcher — and would impose a 2-second
    // high-accuracy cadence on whatever else was using it.
    expect(hook).not.toContain('LocationService');
    expect(hook).not.toContain('locationStore');
  });
});

describe('automatic re-routing', () => {
  it('does not decide WHAT to call -- only when', () => {
    // The hook holds no router. It calls an injected `onReroute`, so the decision
    // of what a new route is stays in MapScreen next to the rest of the routing,
    // and this file stays testable without a backend.
    expect(hook).not.toContain('routeService');
    expect(hook).not.toContain('calculateRoutes');
    expect(hook).toContain('onReroute');
  });

  it('waits for a sustained period off-route rather than firing on one fix', () => {
    // On top of the OFF_ROUTE_STRIKES fixes it takes to enter the off-route state
    // at all, so roughly fourteen seconds of genuinely being elsewhere before a
    // chosen route is replaced.
    expect(hook).toContain('AUTO_REROUTE_AFTER_MS');
    expect(hook).toContain('offRouteSince');
    expect(hook).toMatch(/sustained\s*=\s*now - offRouteSince\.current >= AUTO_REROUTE_AFTER_MS/);
  });

  it('is rate limited, measured from the attempt', () => {
    // Where the road geometry and the GPS disagree -- under a flyover, in a narrow
    // lane -- an unlimited version produces a new route every few seconds, each
    // immediately off-route again. From the ATTEMPT, so a failing recalculation
    // cannot queue behind itself.
    expect(hook).toContain('AUTO_REROUTE_COOLDOWN_MS');
    expect(hook).toMatch(/lastRerouteAt\.current = now/);
    const guard = hook.split('const cooledDown')[1]?.split(';')[0] ?? '';
    expect(guard).toContain('AUTO_REROUTE_COOLDOWN_MS');
  });

  it('never fires on arrival', () => {
    // Arriving 40 m from the pin is not a navigation failure, and re-routing there
    // would hand the user a fresh route to a place they have reached.
    expect(hook).toContain('if (off && !arrived)');
  });

  it('clears the off-route clock as soon as the route is regained', () => {
    const elseBranch = hook.split('if (off && !arrived)')[1]?.split('} else {')[1] ?? '';
    expect(elseBranch).toContain('offRouteSince.current = null');
  });

  it('hands the triggering position to the handler', () => {
    // Rather than letting the handler read `follow.position`, which would have to
    // be declared after the hook that supplies it -- and would route from whatever
    // had reached React state rather than from the fix that triggered it.
    expect(hook).toContain('rerouteRef.current(position)');
    expect(mapScreen).toContain('onReroute: recalculateFrom');
  });

  it('does not block the fix handler on the network', () => {
    // Awaiting inside the subscription callback would stall position updates for
    // the length of an OSRM round trip.
    expect(hook).toMatch(/void Promise\.resolve\(rerouteRef\.current\(position\)\)/);
  });

  it('still offers the manual button', () => {
    // The automatic path has a deliberate delay, so there is a real window in
    // which the user can act faster than it will.
    expect(banner).toContain('onRecalculate');
    expect(mapScreen).toContain('recalculateFrom(follow.position)');
  });

  it('clears the flag when the attempt settles, not only when it succeeds', () => {
    // `rerouting` is sticky, and the arrival of a new path used to be the only
    // thing that cleared it. So a recalculation that came back with nothing -- no
    // signal, the router down, no route found -- left the banner reading "Finding
    // a new route..." for the rest of the walk, with the manual button disabled
    // because that flag disables it. The user could not retry by hand at the one
    // moment they most needed to.
    expect(hook).toMatch(/\.finally\(\(\) => setState\(current => \(\{ \.\.\.current, rerouting: false \}\)\)\)/);
  });

  it('treats the arrival of a new path as the completed re-route', () => {
    const reset = hook.split('if (!active) return;')[1] ?? '';
    expect(reset).toContain('rerouting: false');
  });
});

describe('the snapped-position marker', () => {
  const marker = codeOnly(read(HERE, 'FollowMarker.tsx'));

  it('does not start with tracking off', () => {
    // A Marker with React children takes its bitmap from the child on a native
    // draw pass. Tracking off from the first render lets that snapshot happen
    // before the child has drawn, and what freezes is a blank circle.
    //
    // Worse here than on a flag marker: there is one of these, its content never
    // changes, and nothing in a key forces a remount -- so a blank snapshot stays
    // blank for the whole walk, and the symptom is the route trimming perfectly
    // with no dot on it. That is a bug this file is here to keep fixed.
    expect(marker).not.toContain('tracksViewChanges={false}');
    expect(marker).toContain('useState(true)');
    expect(marker).toContain('tracksViewChanges={tracking}');
  });

  it('stops tracking two frames after layout, like the flag marker', () => {
    // One frame is not enough: `onLayout` fires when React Native has measured the
    // view, and the native marker copies it on the following draw.
    expect(marker).toMatch(
      /requestAnimationFrame\(\(\) => requestAnimationFrame\(\(\) => setTracking\(false\)\)\)/,
    );
    expect(marker).toContain('onLayout={settle}');
  });

  it('has a backstop so it cannot track forever', () => {
    // If `onLayout` never arrives, re-rasterising on every fix for the length of a
    // walk is the cost this prop exists to avoid.
    expect(marker).toContain('setTimeout(settle, 1_000)');
    expect(marker).toContain('clearTimeout(timer)');
  });

  it('is used by the map rather than inlined there', () => {
    expect(mapScreen).toContain('<FollowMarker coordinate={follow.progress.snapped} />');
    expect(mapScreen).not.toContain('followDotOuter');
  });
});

describe('street names', () => {
  const instructions = codeOnly(read(HERE, 'instructions.ts'));

  it('never says "onto" without a name', () => {
    // The single most likely bug here: "Turn left onto" trailing off into nothing
    // on the many Dhaka ways OSM has no name tag for.
    expect(instructions).toMatch(/step\.name\s*\?/);
  });

  it('keeps the geometric fallback for routes with no steps', () => {
    // The straight-line estimate has none, and a route whose steps came back empty
    // is the same case.
    expect(instructions).toContain('turnInstruction');
    expect(hook).toContain('steps.length === 0 ? null : stepAt(steps, next)');
  });

  it('matches the current step by distance along the route, not by proximity', () => {
    // A route passing one junction twice has two manoeuvres metres apart, and a
    // nearest-coordinate match would announce the wrong one.
    const progress = codeOnly(read(HERE, 'progress.ts'));
    const stepAt =
      progress.split('export function stepAt')[1]?.split('export ')[0] ?? '';
    expect(stepAt).toContain('start_m');
    expect(stepAt).not.toContain('metresBetween');
  });
});

describe('the ETA', () => {
  const progress = codeOnly(read(HERE, 'progress.ts'));

  it('comes from the live smoothed speed when that is usable', () => {
    expect(progress).toContain('export function etaSeconds');
    expect(progress).toMatch(/progress\.remainingM \/ speedMps/);
  });

  it('smooths the speed rather than using the raw reading', () => {
    // Raw phone speed spikes on a bad fix and drops to zero between satellites, so
    // an unsmoothed ETA swings by minutes between updates.
    expect(progress).toContain('SPEED_SMOOTHING');
    expect(hook).toContain('smoothSpeed(speedRef.current, fix.coords.speed)');
  });

  it('discards a null or negative speed instead of averaging it in', () => {
    // `coords.speed` is null on Android when the provider has no estimate and
    // occasionally a negative sentinel. Feeding -1 into an average poisons it.
    const smooth =
      progress.split('export function smoothSpeed')[1]?.split('export ')[0] ?? '';
    expect(smooth).toContain('reading < 0');
    expect(smooth).toContain('return previous');
  });

  it('falls back to the route pace below a usable speed, not to infinity', () => {
    // `remaining / 0` is infinity, so a naive live-speed ETA reads nonsense at
    // every traffic light.
    expect(progress).toContain('MIN_USABLE_SPEED_MPS');
    expect(progress).toContain('return remainingSeconds(progress, totalM, totalSeconds)');
  });
});

describe('poor fixes', () => {
  it('discards a useless fix instead of snapping it', () => {
    // A 300 m-accuracy fix carries no information about which street you are on,
    // and snapping it produces a confident wrong answer.
    expect(hook).toContain('MAX_ACCURACY_M');
    const guard = hook.split('accuracyM > MAX_ACCURACY_M')[1] ?? '';
    expect(guard).toContain('return');
  });

  it('requires several consecutive bad fixes before declaring off-route', () => {
    // A banner that appears and vanishes every few seconds trains the user to
    // ignore the one time it matters.
    expect(hook).toContain('OFF_ROUTE_STRIKES');
    expect(hook).toContain('strikes.current >= OFF_ROUTE_STRIKES');
  });

  it('widens the off-route distance for a poor fix', () => {
    expect(hook).toContain('offRouteThreshold(');
  });
});

describe('the map screen wiring', () => {
  it('follows the camera through the ref, never through setRegion', () => {
    // MapScreen refetches the risk layer whenever `region` changes, so following
    // by state would fire a flags-and-clusters request every two seconds for the
    // whole walk.
    const effect = mapScreen.split('if (!follow.active || !followCamera')[1] ?? '';
    const body = effect.split('}, [')[0];
    expect(body).toContain('mapRef.current?.animateCamera');
    expect(body).not.toContain('setRegion');
  });

  it('does not start following just because a route exists', () => {
    // Acquiring high-accuracy fixes because a route happens to be drawn would
    // flatten a battery for someone who was only comparing options.
    expect(mapScreen).toContain('void follow.start()');
    const autoStart = /useEffect\([^)]*\{\s*(void\s+)?follow\.start\(\)/.test(mapScreen);
    expect(autoStart).toBe(false);
  });

  it('puts Start inside the route card rather than floating beside it', () => {
    // The card's height is a percentage of the screen and changes when it
    // expands, so an independently positioned button either overlaps it -- which
    // the first version of this did, on the bottom-right corner -- or has to
    // guess its height.
    expect(mapScreen).toContain('onStart={');
    expect(mapScreen).not.toContain('styles.startButton');
    const card = codeOnly(read(SRC, 'components', 'RouteComparisonCard.tsx'));
    expect(card).toContain('onPress={onStart}');
  });

  it('releases the camera when the user points the map north', () => {
    // While following, the camera turns toward the direction of travel on every
    // fix, so without this the map swings back within two seconds and the north
    // button looks broken.
    const north = mapScreen.split('const faceNorth')[1]?.split('};')[0] ?? '';
    expect(north).toContain('setFollowCamera(false)');
  });

  it('stops following when route mode is left', () => {
    expect(mapScreen).toMatch(/!routeMode && follow\.active.*follow\.stop\(\)/s);
  });

  it('does not let a map tap re-route while following', () => {
    // `handleMapPress` sets a new destination and recalculates, so an accidental
    // touch mid-walk would silently replace the route being followed.
    //
    // Ordering is checked by absolute index in the whole file rather than inside a
    // sliced handler: an earlier version of this test cut the slice at `};`, which
    // lands in the middle of the `dest` object literal, so `setDestination` fell
    // outside it and the assertion compared against -1.
    // Anchored on `selectDestination`, which is where the guard and the write
    // both live now: `handleMapPress` and `handlePoiPress` are two one-line
    // callers of it, because a labelled place on the map arrives as `onPoiClick`
    // and never as `onPress`.
    const start = mapScreen.indexOf('const selectDestination');
    expect(start).toBeGreaterThan(-1);
    const guard = mapScreen.indexOf('follow.active', start);
    const setDestination = mapScreen.indexOf('setDestination(dest)', start);
    expect(guard).toBeGreaterThan(-1);
    expect(setDestination).toBeGreaterThan(-1);
    expect(guard).toBeLessThan(setDestination);
  });

  it('shows the comparison card and the banner exclusively', () => {
    expect(mapScreen).toContain('calculatedRoutes.length > 0 && !follow.active');
    expect(mapScreen).toContain('routeMode && follow.active');
  });

  it('trims the followed route by the travelled part, not the remaining part', () => {
    // At the end `ahead` collapses to one point, and keying off it would make the
    // whole untrimmed line reappear at the moment of arrival.
    expect(mapScreen).toContain('follow.behind.length > 1');
  });
});

describe('the banner says only what the data supports', () => {
  it('never claims a street name', () => {
    // The backend does not request OSRM `steps`, so nothing here knows what a
    // road is called. A fabricated street name in a navigation instruction would
    // be the worst place in this app to start inventing things.
    for (const source of [banner, hook, codeOnly(read(HERE, 'progress.ts'))]) {
      expect(source).not.toMatch(/\bonto\s+\$\{/);
      expect(source).not.toContain('street_name');
      expect(source).not.toContain('road_name');
    }
  });

  it('does not claim to be recalculating when nothing is', () => {
    // The LAST occurrence: `phase === 'off-route'` appears twice, once in the tone
    // ternary at the top and once as the block guard. Taking [1] lands between
    // them, which is the empty stretch in the middle.
    const parts = banner.split("phase === 'off-route'");
    const offRoute = parts[parts.length - 1];
    expect(offRoute).toContain('left on the route you chose');
    // "Recalculating..." before the button is pressed would be a lie.
    const beforeButton = offRoute.split('onPress={onRecalculate}')[0];
    expect(beforeButton.toLowerCase()).not.toContain('recalculating');
  });

  it('shows accuracy only when it is poor enough to explain a wandering marker', () => {
    expect(banner).toMatch(/accuracyM\s*>\s*30/);
  });
});
