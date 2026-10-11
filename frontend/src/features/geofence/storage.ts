/**
 * What the background task is allowed to know. B6a / S17.
 *
 * The geofence handler runs in a **headless JS context**: Android wakes the app
 * with no UI, no navigation, no zustand store and no React tree. Whatever it
 * needs has to be on disk before it runs.
 *
 * So the contract is: while the app is open it writes the zone table and the
 * alert log here; when a crossing fires, the task reads here and nothing else.
 *
 * ## Why not call the API from the task
 *
 * It was the first design and it is wrong in a way that fails quietly. A task
 * that fetched the flag would need the Supabase session, and a background
 * wake-up hours later is exactly when an access token has expired. The refresh
 * might work; it might not, on a phone with no data. Either way the user would
 * walk into a flagged road and get nothing, with no error anywhere — the task
 * would simply return.
 *
 * Writing the text ahead of time means an alert needs no network, no token and
 * no server. The cost is staleness: the statement is as fresh as the last time
 * the app was open, which is stated in the UI and is the right trade for a
 * warning that has to arrive.
 *
 * ## AsyncStorage, not SecureStore
 *
 * None of this is secret — the statements are published on a public map. It is
 * also read from a background task, and `expo-secure-store` on Android is backed
 * by the keystore, which is not reliably available before first unlock. A zone
 * alert that worked only after the phone had been unlocked once would be a
 * strange bug to chase.
 */

import AsyncStorage from '@react-native-async-storage/async-storage';

import type { ZoneMeta } from './zones';

const ZONES_KEY = 'geofence.zones.v1';
const LAST_ALERTED_KEY = 'geofence.lastAlerted.v1';
const LOG_KEY = 'geofence.log.v1';
const ENABLED_KEY = 'geofence.enabled.v1';

/** Entries kept in the visible alert log. */
const LOG_LIMIT = 50;

/** One line of the user-visible history. */
export interface ZoneEvent {
  flagId: string;
  statement: string;
  title: string;
  body: string;
  at: string;
  /** False when the crossing was seen but suppressed by the debounce. */
  notified: boolean;
  reason?: string;
}

// ---------------------------------------------------------------------------
// The zone table
// ---------------------------------------------------------------------------

export async function saveZones(meta: Record<string, ZoneMeta>): Promise<void> {
  await AsyncStorage.setItem(ZONES_KEY, JSON.stringify(meta));
}

/**
 * The zone table, or `{}`.
 *
 * Every read is defensive. This is parsed inside a background task where a throw
 * has nowhere to go: an unhandled rejection there is an alert that silently did
 * not happen, and the only symptom is a user not being warned.
 */
export async function loadZones(): Promise<Record<string, ZoneMeta>> {
  try {
    const raw = await AsyncStorage.getItem(ZONES_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch {
    return {};
  }
}

export async function clearZones(): Promise<void> {
  await AsyncStorage.multiRemove([ZONES_KEY, LAST_ALERTED_KEY]);
}

// ---------------------------------------------------------------------------
// The debounce
// ---------------------------------------------------------------------------

async function loadLastAlerted(): Promise<Record<string, number>> {
  try {
    const raw = await AsyncStorage.getItem(LAST_ALERTED_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch {
    return {};
  }
}

/**
 * Whether this zone may alert now, recording the decision if it may.
 *
 * Read-and-write in one function on purpose. Two geofence events for the same
 * zone can arrive close together — Android re-reports a crossing when its
 * location fix improves — and a caller that checked, then posted, then recorded
 * would send both. There is no lock available in a headless task, so the window
 * is made as small as it can be.
 */
export async function claimZoneAlert(
  flagId: string,
  now: number,
  realertAfterMs: number,
): Promise<boolean> {
  const seen = await loadLastAlerted();
  const last = seen[flagId];
  if (typeof last === 'number' && now - last < realertAfterMs) return false;
  seen[flagId] = now;
  try {
    await AsyncStorage.setItem(LAST_ALERTED_KEY, JSON.stringify(seen));
  } catch {
    // If the write fails the alert still goes out. Alerting twice is better than
    // not alerting, which is the whole bias of this feature.
  }
  return true;
}

export async function resetDebounce(): Promise<void> {
  await AsyncStorage.removeItem(LAST_ALERTED_KEY);
}

// ---------------------------------------------------------------------------
// The visible log
// ---------------------------------------------------------------------------

/**
 * Append to the history the user can read.
 *
 * This exists because background geofencing is otherwise completely invisible.
 * "I walked past the zone and got nothing" has at least four causes — permission
 * not granted, the zone not registered, the debounce, the OS not reporting the
 * crossing — and without a log there is no way to tell them apart. Suppressed
 * crossings are recorded too, with the reason, which is what makes the debounce
 * demonstrable rather than indistinguishable from a bug.
 */
export async function appendZoneEvent(event: ZoneEvent): Promise<void> {
  try {
    const raw = await AsyncStorage.getItem(LOG_KEY);
    const existing: ZoneEvent[] = raw ? JSON.parse(raw) : [];
    const next = [event, ...(Array.isArray(existing) ? existing : [])].slice(0, LOG_LIMIT);
    await AsyncStorage.setItem(LOG_KEY, JSON.stringify(next));
  } catch {
    // The log is a convenience. Losing a line must never cost the alert.
  }
}

export async function loadZoneLog(): Promise<ZoneEvent[]> {
  try {
    const raw = await AsyncStorage.getItem(LOG_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export async function clearZoneLog(): Promise<void> {
  await AsyncStorage.removeItem(LOG_KEY);
}

// ---------------------------------------------------------------------------
// The on/off flag
// ---------------------------------------------------------------------------
//
// Persisted separately from the OS's own geofencing state because the two can
// disagree: the user may revoke background location in system settings, which
// stops the crossings without telling the app. The screen shows both — what was
// asked for, and what `hasStartedGeofencingAsync` reports — so a silent
// revocation is visible rather than looking like a broken feature.

export async function setZoneWatchEnabled(enabled: boolean): Promise<void> {
  await AsyncStorage.setItem(ENABLED_KEY, enabled ? '1' : '0');
}

export async function isZoneWatchEnabled(): Promise<boolean> {
  try {
    return (await AsyncStorage.getItem(ENABLED_KEY)) === '1';
  } catch {
    return false;
  }
}
