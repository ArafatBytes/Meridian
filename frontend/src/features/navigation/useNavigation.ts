/**
 * Live navigation: the location subscription, the state machine, and nothing else.
 *
 * The geometry lives in `progress.ts` and is pure. This file is the part that talks
 * to the GPS and to time, which is exactly why the two are separate — the maths is
 * testable and the plumbing is small.
 *
 * ## It owns its own subscription, deliberately
 *
 * `LocationService` keeps a single `watchSubscription` field, so a second
 * `watchPosition()` call silently replaces the first. `locationStore.startTracking`
 * is built on it and is currently dead code; the constants it would use are
 * `LOCATION_UPDATE_INTERVAL = 60000` and `LOCATION_DISTANCE_FILTER = 10`.
 *
 * Sixty seconds is right for "roughly where is this phone" and useless for
 * navigation: at walking pace that is a fix every 80 m, so the route would jump a
 * block at a time. Navigation needs `NAV_INTERVAL_MS`, which is thirty times
 * faster, and it must not impose that on anything else — a background consumer
 * suddenly getting high-accuracy fixes every two seconds is a battery bug nobody
 * would attribute to this screen.
 *
 * So this hook calls `expo-location` directly, holds its own subscription, and
 * removes it on stop and on unmount. Nothing else in the app is affected either
 * way.
 *
 * ## It re-routes on its own, slowly and on purpose
 *
 * It did not, once, and the argument against was this product's central claim: the
 * route being followed was *chosen*, from a comparison with a safety score and a
 * sentence explaining what it avoids, and silently swapping it discards the only
 * thing separating this from a maps app — at the moment the user is least able to
 * look at the screen. A recalculation also costs an OSRM call plus flag and cluster
 * scoring, which on a venue network can take seconds and fail.
 *
 * The owner asked for it anyway, and the delay and the cooldown now carry that
 * argument instead of a refusal: `AUTO_REROUTE_AFTER_MS` on top of
 * `OFF_ROUTE_STRIKES` fixes is roughly fourteen seconds of genuinely being
 * elsewhere before anything is replaced, and `AUTO_REROUTE_COOLDOWN_MS` keeps a
 * disagreement between the GPS and the road geometry from becoming a request loop.
 * The banner says what is happening before it happens, and the user can tap the
 * button rather than wait.
 *
 * ## It does announce streets, where OSM has a name
 *
 * The backend asks OSRM for `steps`, so a manoeuvre arrives with a type, a
 * modifier and a road name. `instructions.ts` is where that becomes a sentence, and
 * the part worth knowing is what happens when the name is missing — which on a
 * Dhaka lane is most of the time. The phrasing degrades in two stages, named
 * manoeuvre to unnamed manoeuvre to pure geometry, and never says "onto" with
 * nothing after it.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import * as Location from 'expo-location';

import {
  advance,
  cumulativeDistances,
  etaSeconds,
  hasArrived,
  locate,
  nextTurn,
  offRouteThreshold,
  remainingPath,
  smoothSpeed,
  stepAt,
  travelledPath,
  type LatLng,
  type NavStep,
  type RouteProgress,
  type StepHint,
  type TurnHint,
} from './progress';

export const NAV_INTERVAL_MS = 2_000;
/**
 * How often to ask for a fix while navigating.
 *
 * Two seconds. At Dhaka traffic speed that is roughly every 15 m, which keeps the
 * line trimming smoothly without the GPS running flat out. One second buys nothing
 * — the hardware rarely produces genuinely new positions faster than that, and the
 * extra fixes are mostly noise that the monotonic clamp then has to absorb.
 */

export const NAV_DISTANCE_M = 5;
/**
 * Minimum movement before the OS bothers to deliver a fix.
 *
 * Standing still is the common case — a traffic light, a conversation, waiting to
 * cross — and without this the subscription fires every two seconds forever,
 * re-rendering a heavy map screen for a position that has not changed.
 */

export const MAX_ACCURACY_M = 100;
/**
 * Fixes worse than this are discarded entirely rather than used.
 *
 * Distinct from `offRouteThreshold`, which *widens* the off-route distance for a
 * merely poor fix. This is for a useless one: a 300 m-accuracy fix carries no
 * information about which street you are on, and snapping it to the route produces
 * a confident, wrong answer. Holding the last good position is better, and is what
 * the hardware itself does while it reacquires.
 */

export const OFF_ROUTE_STRIKES = 3;
/**
 * Consecutive bad fixes before declaring off-route, and good ones before clearing.
 *
 * Hysteresis, because a single fix beyond the threshold is routine — under a
 * flyover, between tall buildings, the moment a bus passes. A banner that appears
 * and vanishes every few seconds is worse than no banner: it trains the user to
 * ignore the one time it matters.
 */

export const AUTO_REROUTE_AFTER_MS = 8_000;
/**
 * How long off-route before a new route is fetched automatically.
 *
 * Eight seconds, on top of the `OFF_ROUTE_STRIKES` fixes it already takes to enter
 * the off-route state at all — so roughly fourteen seconds of genuinely being
 * elsewhere before anything is replaced. That delay is the whole safety margin: a
 * route in this app was *chosen* from a comparison that explained what it avoids,
 * and the cost of replacing it too eagerly is that the user loses the route they
 * picked because they stepped around a parked car.
 *
 * The off-route banner appears immediately regardless, so the user knows what is
 * happening before it happens, and can tap the button rather than wait.
 */

export const AUTO_REROUTE_COOLDOWN_MS = 25_000;
/**
 * Minimum gap between automatic re-routes.
 *
 * Without it, an area where the road geometry and the GPS disagree — under a
 * flyover, in a narrow lane between tall buildings — produces a new route every
 * few seconds, each one immediately off-route again. That is a request loop with a
 * user attached: it burns the OSRM backend, re-scores flags and clusters each time,
 * and leaves the screen unreadable because the route changes under it.
 *
 * Long enough that a failing recalculation cannot queue behind itself either; the
 * cooldown starts when the attempt is made, not when it succeeds.
 */

export type NavigationPhase = 'idle' | 'locating' | 'following' | 'off-route' | 'arrived';

export interface NavigationState {
  phase: NavigationPhase;
  /** Null until the first usable fix. */
  progress: RouteProgress | null;
  /** The route still ahead, for the map. Empty when idle. */
  ahead: LatLng[];
  /** The route already behind, for the map to draw faintly. */
  behind: LatLng[];
  remainingM: number;
  remainingSeconds: number;
  /** Geometric turn, from the polyline. Always present; the fallback narration. */
  turn: TurnHint | null;
  /**
   * The manoeuvre from OSRM, when the route carries steps. Null when it does not,
   * which is when `turn` is the only thing to narrate from.
   */
  step: StepHint | null;
  /** Smoothed speed in m/s, or null before a usable reading. Drives the ETA. */
  speedMps: number | null;
  /** True while an automatic re-route is in flight. */
  rerouting: boolean;
  /** The raw fix, unsnapped. For the camera and the accuracy readout. */
  position: LatLng | null;
  accuracyM: number | null;
  /** Set when the subscription could not start at all. */
  error: string | null;
}

const IDLE: NavigationState = {
  phase: 'idle',
  progress: null,
  ahead: [],
  behind: [],
  remainingM: 0,
  remainingSeconds: 0,
  turn: null,
  step: null,
  speedMps: null,
  rerouting: false,
  position: null,
  accuracyM: null,
  error: null,
};

export interface UseNavigationOptions {
  /** The selected route's path, or null when there is nothing to follow. */
  path: LatLng[] | null;
  /** The route's own total duration in seconds, for the ETA fallback. */
  totalSeconds: number;
  /**
   * The route's manoeuvres, or an empty array when the router supplied none.
   *
   * Empty is a supported state, not a degraded one to guard against: the
   * straight-line fallback has no manoeuvres, and OSM has no name for a great many
   * Dhaka lanes. The banner narrates from the geometry in that case.
   */
  steps?: NavStep[];
  /**
   * Fetch a new route starting from `from`. Called automatically after
   * `AUTO_REROUTE_AFTER_MS` off-route, and by the banner's button.
   *
   * **It is handed the position rather than reading it**, and that is what breaks a
   * circular dependency rather than a stylistic preference: a handler that read
   * `follow.position` would have to be declared after the hook that returns it, and
   * the hook needs the handler as an option. Passing it in also means the re-route
   * uses the fix that actually triggered it, not whatever had reached React state
   * by the time the callback ran.
   *
   * Omit it and automatic re-routing simply does not happen -- which is what makes
   * this hook usable from a screen that has no router.
   */
  onReroute?: (from: LatLng) => void | Promise<void>;
}

export interface UseNavigationResult extends NavigationState {
  /** True while a route is being followed. */
  active: boolean;
  start: () => Promise<void>;
  stop: () => void;
}

/**
 * Follow `path`, reporting where the user is on it.
 *
 * Nothing happens until `start()`. That is deliberate: this screen is a map first
 * and a navigator second, and acquiring high-accuracy fixes because a route
 * happens to be drawn would drain a battery for a user who was only comparing
 * options.
 */
export function useNavigation({
  path,
  totalSeconds,
  steps = [],
  onReroute,
}: UseNavigationOptions): UseNavigationResult {
  const [state, setState] = useState<NavigationState>(IDLE);
  const [active, setActive] = useState(false);

  const subscription = useRef<Location.LocationSubscription | null>(null);
  /**
   * The current fix handler, so the running subscription always calls the latest one.
   *
   * `watchPositionAsync` captures the callback it is given and keeps calling it for
   * the life of the subscription. `onFix` is rebuilt whenever the path changes, so
   * without this indirection a recalculation mid-walk would leave the subscription
   * holding the handler that closes over the OLD path -- and since the recalculation
   * also resets progress, every subsequent fix would be located on a route that is
   * no longer on screen. The banner would count down a route the user is not on,
   * confidently.
   */
  const onFixRef = useRef<(fix: Location.LocationObject) => void>(() => {});
  // Progress in a ref as well as in state: the next fix must be compared against
  // the previous progress, and reading it from `state` inside the subscription
  // callback would close over whatever it was when the subscription was created.
  // That is the classic stale-closure bug, and here its symptom would be a route
  // that never advances past the first fix.
  const progressRef = useRef<RouteProgress | null>(null);
  const strikes = useRef(0);
  const goodFixes = useRef(0);
  /** Smoothed speed, in a ref for the same stale-closure reason as `progressRef`. */
  const speedRef = useRef<number | null>(null);
  /** When the current off-route episode began, or null while on route. */
  const offRouteSince = useRef<number | null>(null);
  /** When the last automatic re-route was *attempted*. Drives the cooldown. */
  const lastRerouteAt = useRef(0);
  // `onReroute` through a ref for the same reason as `onFix`: the running
  // subscription captures its callback, and the handler that calls this is rebuilt
  // whenever the path changes.
  const rerouteRef = useRef<UseNavigationOptions['onReroute']>(onReroute);

  // Recomputed only when the path identity changes, which is once per route.
  // Several hundred haversines, so not something to do per fix.
  const cumulative = useMemo(
    () => (path && path.length > 1 ? cumulativeDistances(path) : null),
    [path],
  );
  const totalM = cumulative ? cumulative[cumulative.length - 1] : 0;

  const stop = useCallback(() => {
    subscription.current?.remove();
    subscription.current = null;
    progressRef.current = null;
    strikes.current = 0;
    goodFixes.current = 0;
    speedRef.current = null;
    offRouteSince.current = null;
    setActive(false);
    setState(IDLE);
  }, []);

  const onFix = useCallback(
    (fix: Location.LocationObject) => {
      if (!path || !cumulative || path.length < 2) return;

      const accuracyM = fix.coords.accuracy ?? null;
      // A useless fix is dropped before it can move anything. See MAX_ACCURACY_M.
      if (accuracyM !== null && accuracyM > MAX_ACCURACY_M) return;

      const position: LatLng = {
        latitude: fix.coords.latitude,
        longitude: fix.coords.longitude,
      };

      // Smoothed before anything uses it. `coords.speed` is null on Android when
      // the provider has no estimate and occasionally a negative sentinel; both are
      // discarded rather than averaged in. See `smoothSpeed`.
      speedRef.current = smoothSpeed(speedRef.current, fix.coords.speed);

      // The first usable fix is located globally; every later one is windowed.
      // See `locate` for why those have to be different functions.
      const previous = progressRef.current;
      const next = previous
        ? advance(path, cumulative, position, previous)
        : locate(path, cumulative, position);
      progressRef.current = next;

      const threshold = offRouteThreshold(accuracyM ?? undefined);
      if (next.offRouteM > threshold) {
        strikes.current += 1;
        goodFixes.current = 0;
      } else {
        goodFixes.current += 1;
        if (goodFixes.current >= OFF_ROUTE_STRIKES) strikes.current = 0;
      }

      const arrived = hasArrived(next);
      const off = strikes.current >= OFF_ROUTE_STRIKES;

      // Automatic re-routing, and every guard on it matters:
      //
      // * only while off-route and not yet arrived -- arriving 40 m from the pin is
      //   not a navigation failure and must not trigger a new route;
      // * only after `AUTO_REROUTE_AFTER_MS` of *continuous* off-route, measured
      //   from when the episode began rather than counting fixes, so a slow GPS
      //   does not shorten the delay;
      // * only once per `AUTO_REROUTE_COOLDOWN_MS`, from the ATTEMPT, so a failing
      //   recalculation cannot queue behind itself;
      // * only when a handler was supplied.
      let rerouting = false;
      if (off && !arrived) {
        const now = Date.now();
        offRouteSince.current ??= now;
        const sustained = now - offRouteSince.current >= AUTO_REROUTE_AFTER_MS;
        const cooledDown = now - lastRerouteAt.current >= AUTO_REROUTE_COOLDOWN_MS;
        if (sustained && cooledDown && rerouteRef.current) {
          lastRerouteAt.current = now;
          rerouting = true;
          // Fire and forget: the new route arrives as a `path` change, which resets
          // progress through the effect below. Awaiting here would block the fix
          // handler on a network call.
          //
          // `finally` is what makes a FAILED attempt recoverable, and without it
          // this was a trap. `rerouting` is sticky, and the only thing that cleared
          // it was a new path arriving -- so when the recalculation came back with
          // nothing (no signal, the router down, no route found), the route list
          // never changed, the flag never cleared, and the banner read "Finding a
          // new route..." for the rest of the walk. The manual button is disabled
          // while that flag is set, so the user could not retry by hand either, at
          // the one moment they most needed to.
          //
          // It fires on success too, where it is redundant: the path change has
          // already cleared the flag. Both paths agree on false, so the order they
          // run in does not matter.
          void Promise.resolve(rerouteRef.current(position))
            .catch(() => {})
            .finally(() => setState(current => ({ ...current, rerouting: false })));
        }
      } else {
        offRouteSince.current = null;
      }

      setState(previousState => ({
        phase: arrived ? 'arrived' : off ? 'off-route' : 'following',
        progress: next,
        ahead: remainingPath(path, next),
        behind: travelledPath(path, next),
        remainingM: next.remainingM,
        remainingSeconds: etaSeconds(next, totalM, totalSeconds, speedRef.current),
        turn: arrived ? null : nextTurn(path, cumulative, next),
        step: arrived || steps.length === 0 ? null : stepAt(steps, next),
        speedMps: speedRef.current,
        // Sticky until the path changes: the request is in flight for a second or
        // two and the banner needs to keep saying so for all of it, not just on
        // the one fix that started it.
        rerouting: rerouting || previousState.rerouting,
        position,
        accuracyM,
        error: null,
      }));

      if (arrived) {
        // Nothing left to follow. Releasing the subscription here rather than
        // waiting for the user matters: an arrived navigator that keeps polling
        // high-accuracy GPS is a battery drain with no output.
        subscription.current?.remove();
        subscription.current = null;
      }
    },
    [path, cumulative, totalM, totalSeconds, steps],
  );

  // Kept current on every render, so the subscription's indirection always lands
  // on the handler built for the path that is actually being followed.
  useEffect(() => {
    onFixRef.current = onFix;
  }, [onFix]);

  useEffect(() => {
    rerouteRef.current = onReroute;
  }, [onReroute]);

  const start = useCallback(async () => {
    if (!path || path.length < 2) return;

    subscription.current?.remove();
    subscription.current = null;
    progressRef.current = null;
    strikes.current = 0;
    goodFixes.current = 0;

    setActive(true);
    setState({ ...IDLE, phase: 'locating' });

    try {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') {
        setState({
          ...IDLE,
          phase: 'idle',
          error: 'Location permission is needed to follow a route.',
        });
        setActive(false);
        return;
      }

      subscription.current = await Location.watchPositionAsync(
        {
          accuracy: Location.Accuracy.High,
          timeInterval: NAV_INTERVAL_MS,
          distanceInterval: NAV_DISTANCE_M,
        },
        // Through the ref, never `onFix` directly. See `onFixRef`.
        fix => onFixRef.current(fix),
      );
    } catch (error: any) {
      setState({
        ...IDLE,
        phase: 'idle',
        error: error?.message ?? 'Could not start following this route.',
      });
      setActive(false);
    }
    // `onFix` is deliberately NOT a dependency: it is reached through `onFixRef`,
    // so `start` does not need to be rebuilt -- and if it were, every path change
    // would hand MapScreen a new `start` identity for no reason.
  }, [path]);

  // The route changed under an active navigator -- the user picked a different
  // candidate, or recalculated. Progress on the old path means nothing on the new
  // one, so it is reset and the next fix re-locates globally.
  useEffect(() => {
    if (!active) return;
    progressRef.current = null;
    strikes.current = 0;
    goodFixes.current = 0;
    offRouteSince.current = null;
    // Speed survives a reroute deliberately: you are still moving at the pace you
    // were a second ago, and throwing the average away would blank the ETA for the
    // next ten seconds at exactly the moment the user is checking it.
    setState(current => ({
      ...current,
      phase: 'locating',
      progress: null,
      ahead: [],
      behind: [],
      step: null,
      // The new path IS the completed reroute.
      rerouting: false,
    }));
  }, [path, active]);

  // Leaving the screen must not leave the GPS running. This is the one cleanup
  // that cannot be skipped: a subscription that outlives the screen keeps the
  // radio awake with nothing reading it.
  useEffect(() => () => {
    subscription.current?.remove();
    subscription.current = null;
  }, []);

  return { ...state, active, start, stop };
}
