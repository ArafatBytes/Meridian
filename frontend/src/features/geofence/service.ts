/**
 * Turning zone monitoring on, keeping it current, turning it off. B6a / S17.
 *
 * The foreground half of geofencing: it asks for permissions, fetches the risk
 * surface, picks the regions, writes the table the background task reads, and
 * hands the regions to the OS. Everything after that happens in `task.ts`,
 * hours later, with the app closed.
 *
 * ## Background location permission is a two-step grant, and the order matters
 *
 * Android will not grant `ACCESS_BACKGROUND_LOCATION` unless foreground location
 * is already granted — the request simply returns denied. On Android 11+ it also
 * stops showing a dialog at all: the user has to be sent to system settings and
 * choose "Allow all the time" themselves.
 *
 * So `requestPermissions` asks in order, reports exactly which step failed, and
 * never pretends a foreground-only grant is enough. A geofence registered
 * without background permission fires only while the app is open, which is the
 * one case the feature is not for.
 */

import * as Location from 'expo-location';

import { riskService } from '../../services/risk.service';
import { ZONE_REALERT_AFTER_MS, composeZoneAlert, presentZoneAlert } from './alert';
import { GEOFENCE_TASK } from './task';
import {
  appendZoneEvent,
  claimZoneAlert,
  clearZones,
  isZoneWatchEnabled,
  loadZones,
  resetDebounce,
  saveZones,
  setZoneWatchEnabled,
} from './storage';
import { MAX_REGIONS, distanceM, selectZones, type ZoneSelection } from './zones';

/**
 * How wide an area of flags to load, in degrees.
 *
 * ~0.35° is about 39 km — the whole of Dhaka and its approaches. Deliberately
 * much wider than the map's viewport: the regions are registered once while the
 * app is open and then watched for hours while the person moves, so fetching
 * only what is currently on screen would mean walking out of the monitored set.
 */
const ZONE_FETCH_SPAN_DEGREES = 0.35;

/**
 * Whether the OS is currently watching our regions. **Never throws.**
 *
 * `Location.hasStartedGeofencingAsync` reads like a harmless query and is not:
 * on Android it **rejects** when the background location permission has not been
 * granted —
 *
 *     Error: Call to function 'ExpoLocation.hasStartedGeofencingAsync' has been
 *     rejected. Caused by: Not authorized to use background location services
 *
 * — which is the state every user is in *before* they turn zone alerts on. The
 * Guardian screen calls this on mount to render its status block, so the first
 * visit to that screen produced an unhandled promise rejection.
 *
 * `false` is not a fallback here, it is the correct answer: if we are not
 * authorised, nothing is being monitored. Swallowing the rejection and saying so
 * is exactly right, and it keeps the status block honest — it shows "Not running"
 * rather than crashing or claiming to be active.
 */
async function isMonitoring(): Promise<boolean> {
  try {
    return await Location.hasStartedGeofencingAsync(GEOFENCE_TASK);
  } catch {
    return false;
  }
}

/** Stop monitoring, if we are allowed to ask and anything is running. Never throws. */
async function stopMonitoring(): Promise<void> {
  try {
    if (await Location.hasStartedGeofencingAsync(GEOFENCE_TASK)) {
      await Location.stopGeofencingAsync(GEOFENCE_TASK);
    }
  } catch {
    // Not authorised, or nothing registered. Either way there is nothing running
    // to stop, which is the outcome the caller wanted.
  }
}

export type PermissionStep = 'granted' | 'no-foreground' | 'no-background' | 'no-services';

export interface ZonePermissionResult {
  step: PermissionStep;
  /** One sentence for the user. Null when granted. */
  problem: string | null;
  /** True when the only way forward is the system settings app. */
  needsSettings: boolean;
}

const PROBLEMS: Record<Exclude<PermissionStep, 'granted'>, string> = {
  'no-services':
    'Location is switched off on this phone. Turn it on, then try again.',
  'no-foreground':
    'Meridian needs location access to know when you are near a flagged road.',
  // The one that cannot be fixed from inside the app on Android 11+.
  'no-background':
    'Zone alerts need location access "all the time". Android only offers that in ' +
    'system settings — open Meridian\'s permissions and choose "Allow all the time".',
};

/**
 * Ask for what background geofencing needs, in the order Android requires.
 *
 * Returns the first step that failed rather than a bare boolean, because each one
 * has a different remedy and only one of them is a dialog.
 */
export async function requestZonePermissions(): Promise<ZonePermissionResult> {
  const enabled = await Location.hasServicesEnabledAsync();
  if (!enabled) {
    return { step: 'no-services', problem: PROBLEMS['no-services'], needsSettings: true };
  }

  const foreground = await Location.requestForegroundPermissionsAsync();
  if (!foreground.granted) {
    return {
      step: 'no-foreground',
      problem: PROBLEMS['no-foreground'],
      needsSettings: !foreground.canAskAgain,
    };
  }

  const background = await Location.requestBackgroundPermissionsAsync();
  if (!background.granted) {
    return {
      step: 'no-background',
      problem: PROBLEMS['no-background'],
      // Effectively always true on Android 11+: the OS shows no dialog for
      // "Allow all the time" and the request resolves denied immediately.
      needsSettings: true,
    };
  }

  return { step: 'granted', problem: null, needsSettings: false };
}

export interface ZoneWatchStatus {
  /** What the user asked for, from our own storage. */
  requested: boolean;
  /** What the OS says is actually running. The one that matters. */
  monitoring: boolean;
  regionCount: number;
  dropped: number;
  skipped: ZoneSelection['skipped'];
  lastRefreshedAt: string | null;
  permission: PermissionStep;
}

let lastSelection: ZoneSelection | null = null;
let lastRefreshedAt: string | null = null;

/**
 * Register the current risk surface as geofences.
 *
 * Called when the user turns zone alerts on, and again on every app foreground —
 * flags decay, expire and appear, and a region set from yesterday is monitoring
 * roads that are now clear while ignoring the one that is blocked today.
 *
 * `startGeofencingAsync` **replaces** the whole set rather than adding to it, so
 * there is no accumulation to clean up and no diffing to get wrong.
 */
export async function refreshZones(from?: {
  lat: number;
  lon: number;
} | null): Promise<ZoneWatchStatus> {
  const permission = await requestZonePermissions();
  if (permission.step !== 'granted') {
    // Deliberately does not stop existing monitoring. Permission can be revoked
    // and restored; tearing down the registration on a transient denial would
    // turn a recoverable state into one needing a manual re-arm.
    return {
      requested: await isZoneWatchEnabled(),
      monitoring: await isMonitoring(),
      regionCount: lastSelection?.regions.length ?? 0,
      dropped: lastSelection?.dropped ?? 0,
      skipped: lastSelection?.skipped ?? { chronic: 0, lowSeverity: 0, expired: 0 },
      lastRefreshedAt,
      permission: permission.step,
    };
  }

  const centre = from ?? (await currentPosition());
  const half = ZONE_FETCH_SPAN_DEGREES / 2;
  const { flags } = await riskService.getFlagsInRegion({
    latitude: centre.lat,
    longitude: centre.lon,
    latitudeDelta: half * 2,
    longitudeDelta: half * 2,
  });

  const selection = selectZones(flags, { from: centre, limit: MAX_REGIONS });
  lastSelection = selection;

  // The table goes to disk BEFORE the regions go to the OS. A crossing can be
  // reported within a second of registration, and a task that woke to find no
  // zone table would return silently — the user walking into a flagged road and
  // hearing nothing, with the feature reporting itself as on.
  await saveZones(selection.meta);

  if (selection.regions.length === 0) {
    // Nothing worth watching. Stop rather than registering an empty set, which
    // some Android versions treat as an error.
    await stopMonitoring();
  } else {
    await Location.startGeofencingAsync(GEOFENCE_TASK, selection.regions);
  }

  await setZoneWatchEnabled(true);
  lastRefreshedAt = new Date().toISOString();

  return {
    requested: true,
    monitoring: await isMonitoring(),
    regionCount: selection.regions.length,
    dropped: selection.dropped,
    skipped: selection.skipped,
    lastRefreshedAt,
    permission: 'granted',
  };
}

export async function stopZones(): Promise<void> {
  await setZoneWatchEnabled(false);
  await stopMonitoring();
  // The zone table and the debounce go too. Leaving them would mean a stale
  // alert on the next crossing after re-arming, about a flag that has since
  // expired.
  await clearZones();
  await resetDebounce();
  lastSelection = null;
  lastRefreshedAt = null;
}

/**
 * The current state, for the screen.
 *
 * Reports `requested` and `monitoring` separately on purpose: the user can
 * revoke background location in system settings, which stops the crossings
 * **without telling the app**. Showing only our own flag would leave the screen
 * saying "on" while nothing was being watched.
 */
export async function zoneWatchStatus(): Promise<ZoneWatchStatus> {
  // Every read here is guarded, because this is the Guardian screen's mount
  // path. `hasStartedGeofencingAsync` already taught the lesson the hard way:
  // it looks like a query and rejects outright when background location has not
  // been granted, which is the state every user is in before switching zone
  // alerts on. The permission getters below ought to be safe, but "ought to be"
  // is what produced a red error box on first open, so they are wrapped too.
  // Reporting "not granted" is the right answer when we cannot find out.
  let permission: PermissionStep = 'no-foreground';
  try {
    const foreground = await Location.getForegroundPermissionsAsync();
    const background = await Location.getBackgroundPermissionsAsync();
    permission = !foreground.granted
      ? 'no-foreground'
      : !background.granted
        ? 'no-background'
        : 'granted';
  } catch (problem) {
    console.warn('Could not read location permissions:', problem);
  }

  return {
    requested: await isZoneWatchEnabled(),
    monitoring: await isMonitoring(),
    regionCount: lastSelection?.regions.length ?? 0,
    dropped: lastSelection?.dropped ?? 0,
    skipped: lastSelection?.skipped ?? { chronic: 0, lowSeverity: 0, expired: 0 },
    lastRefreshedAt,
    permission,
  };
}

/**
 * Run the zone-alert path for the nearest watched zone, right now.
 *
 * **A simulation of the crossing, not of the alert.** It calls exactly what
 * `task.ts` calls on a real boundary crossing — the same stored zone table, the
 * same debounce, the same `presentZoneAlert` — so everything downstream of the
 * OS reporting a crossing is genuinely exercised. The only thing it stands in for
 * is Android deciding you moved.
 *
 * It exists because the feature is otherwise undemonstrable indoors. Geofencing
 * only fires when the person physically crosses a boundary several hundred metres
 * wide, which cannot be done in a room, and "walk to Jatrabari" is not a step
 * anybody can run in front of an audience. Without this, a demo could show the
 * region count and nothing else.
 *
 * Deliberately honest in two ways: the log entry it writes is marked as a test,
 * and it respects the debounce — so pressing it twice shows the debounce working
 * rather than quietly bypassing it.
 */
export async function simulateNearestZoneCrossing(): Promise<{
  ok: boolean;
  detail: string;
}> {
  const zones = await loadZones();
  const entries = Object.values(zones);
  if (entries.length === 0) {
    return {
      ok: false,
      detail:
        'No zones are being watched. Turn zone alerts on first — if it still says 0, ' +
        'there are no live risk flags near you that cleared the threshold.',
    };
  }

  const centre = await currentPosition();
  const nearest = entries.reduce((best, zone) =>
    distanceM(centre, { lat: zone.lat, lon: zone.lon }) <
    distanceM(centre, { lat: best.lat, lon: best.lon })
      ? zone
      : best,
  );

  const now = Date.now();
  const text = composeZoneAlert(nearest);
  const mayAlert = await claimZoneAlert(nearest.flagId, now, ZONE_REALERT_AFTER_MS);

  if (!mayAlert) {
    await appendZoneEvent({
      flagId: nearest.flagId,
      statement: nearest.statement,
      title: text.title,
      body: text.body,
      at: new Date(now).toISOString(),
      notified: false,
      reason: 'test crossing — already alerted in the last 6 hours',
    });
    return {
      ok: false,
      detail:
        'Suppressed: this zone already alerted in the last 6 hours. That is the ' +
        'debounce working — it is what stops somebody who lives beside a flagged ' +
        'road being notified every time they walk to the shop.',
    };
  }

  await presentZoneAlert(nearest);
  await appendZoneEvent({
    flagId: nearest.flagId,
    statement: nearest.statement,
    title: text.title,
    body: text.body,
    at: new Date(now).toISOString(),
    notified: true,
    reason: 'test crossing',
  });

  const metres = Math.round(distanceM(centre, { lat: nearest.lat, lon: nearest.lon }));
  return {
    ok: true,
    detail: `Alerted for the nearest watched zone, about ${metres} m away.`,
  };
}

/** The last known position, or Dhaka's centre as a fallback for the fetch box. */
async function currentPosition(): Promise<{ lat: number; lon: number }> {
  try {
    const last = await Location.getLastKnownPositionAsync({ maxAge: 10 * 60 * 1000 });
    const fix = last ?? (await Location.getCurrentPositionAsync({}));
    return { lat: fix.coords.latitude, lon: fix.coords.longitude };
  } catch {
    // Only used to centre the flag fetch and order the regions, so a wrong
    // centre costs relevance, not correctness. Shahbagh.
    return { lat: 23.7381, lon: 90.3954 };
  }
}

/**
 * Re-register zones if the user has them on. Safe to call on every foreground.
 *
 * Returns null when zone alerts are off, so the caller does not have to ask
 * first.
 */
export async function refreshZonesIfEnabled(): Promise<ZoneWatchStatus | null> {
  if (!(await isZoneWatchEnabled())) return null;
  try {
    return await refreshZones();
  } catch (problem) {
    console.warn('Zone refresh failed:', problem);
    return null;
  }
}
