/**
 * Turning risk flags into geofences the OS will watch. B6a / S17.
 *
 * Pure: no native modules, no storage, no permissions. Flags in, regions out.
 * That split is what lets the region-selection rules — which are where the
 * mistakes live — be tested without a phone.
 *
 * ## Why the OS watches, and not us
 *
 * `expo-location`'s `startGeofencingAsync` hands a list of circles to Android's
 * `GeofencingClient` (or iOS's `CLLocationManager`) and the **operating system**
 * does the detection, waking the app only on a crossing. That matters for three
 * reasons:
 *
 * 1. **It works with the app closed.** A JS loop polling GPS does not — Android
 *    suspends it, and on a phone with battery optimisation on it may never run
 *    again.
 * 2. **The battery cost is the OS's, not ours.** It fuses GPS with wifi and cell
 *    positioning and batches wake-ups across every app that asked. A 30-second
 *    `getCurrentPositionAsync` loop is the single fastest way to drain a phone.
 * 3. **No network, no auth, no token.** The regions are registered while the app
 *    is open; when a crossing fires, the handler needs nothing but the regions
 *    it was given. A background task that had to call an authenticated API would
 *    fail silently the first time a session expired, and nobody would know until
 *    an alert did not arrive.
 *
 * ## The approach ring
 *
 * The brief asks to alert *"when he/she enters near to any risk zone **or enters
 * into any road that will likely take him to any risk zone**"*.
 *
 * The second half, done properly, means projecting the user's route and asking
 * whether it passes a flag — which needs the routing engine and the user's
 * destination, and is a bigger piece of work than this. What is here instead is
 * honest and covers most of the same ground: each flag is watched at
 * **`radiusM + APPROACH_MARGIN_M`**, so the alert fires while the person is
 * still approaching rather than once they are inside. On foot that margin is
 * three to four minutes of warning; in traffic it is roughly a block.
 *
 * It also sidesteps a trap. Geofence radii below ~100 m are unreliable on
 * Android — the OS trades accuracy for battery and a small circle is routinely
 * missed entirely. A flag with a 150 m radius becomes a 400 m circle, which the
 * platform can actually detect.
 *
 * ## The region cap is a platform limit, not a preference
 *
 * iOS monitors at most **20** regions per app, and Android **100**. Exceeding it
 * does not error: the extras are silently dropped, which is the worst possible
 * failure for a safety feature. So the list is capped and sorted by what matters
 * most, and `selectZones` returns what it dropped so the UI can say so.
 */

import { Platform } from 'react-native';

import type { RiskFlag } from '../../types/contracts/risk';

/**
 * The extra distance at which a zone is announced, in metres.
 *
 * 250 m is about three minutes of walking and gives time to turn down a
 * different street — which is the only reason to send the alert at all. Much
 * larger and it fires while the person is nowhere near and has no decision to
 * make; much smaller and it fires once they are already in it.
 */
export const APPROACH_MARGIN_M = 250;

/**
 * Smallest circle worth registering, in metres.
 *
 * Android's geofencing is documented as unreliable below about 100 m, and in
 * practice a small circle is simply never reported. A radius that cannot be
 * detected is worse than no radius: the zone looks monitored and is not.
 */
export const MIN_GEOFENCE_RADIUS_M = 200;

/**
 * Largest circle worth registering, in metres.
 *
 * A chronic flag covers ~2 km, and `2000 + 250` would fire somewhere near
 * half of Dhaka and keep firing. Capped so that a huge zone does not become an
 * alert about being outdoors. (Chronic flags are excluded anyway — see
 * `isWatchable` — but the cap also guards an unusually large live flag.)
 */
export const MAX_GEOFENCE_RADIUS_M = 1200;

/** Platform region limits. Exceeding these drops regions *silently*. */
export const MAX_REGIONS = Platform.OS === 'ios' ? 20 : 100;

/**
 * Below this severity a zone is not worth interrupting someone about.
 *
 * Mirrors the server's default `min_severity` of 40 — the bottom of the
 * "moderate" band. Below it the honest message is "you may lose a few minutes",
 * which does not justify a notification, let alone a background wake-up.
 */
export const MIN_SEVERITY_TO_WATCH = 40;

/** What the task needs to know about a zone when it fires. */
export interface ZoneMeta {
  flagId: string;
  /** Server-framed text, forwarded verbatim. Never composed on the device. */
  statement: string;
  kind: string;
  status: string;
  sourceCount: number;
  severity: number;
  lat: number;
  lon: number;
  /** The flag's own radius, not the inflated geofence radius. */
  flagRadiusM: number;
  /** The radius actually registered with the OS. */
  geofenceRadiusM: number;
}

/** A region in the shape `expo-location` takes. Declared locally to keep this pure. */
export interface Region {
  identifier: string;
  latitude: number;
  longitude: number;
  radius: number;
  notifyOnEnter: boolean;
  notifyOnExit: boolean;
}

export interface ZoneSelection {
  regions: Region[];
  /** `identifier` → everything the alert needs. Persisted for the background task. */
  meta: Record<string, ZoneMeta>;
  /** How many watchable flags did not fit under `MAX_REGIONS`. */
  dropped: number;
  /** How many flags were skipped, and why — for the UI to be honest with. */
  skipped: { chronic: number; lowSeverity: number; expired: number };
}

/**
 * Whether a flag should be watched at all.
 *
 * Three exclusions, and the first is the important one.
 *
 * **Chronic flags are never geofenced.** They are D02's police-statistics
 * baseline: historical averages with ~2 km radii that cover most of Dhaka, never
 * move and never expire. A geofence on one fires every time its owner leaves the
 * house, forever. That is the "stale red zones" behaviour demo beat 5 exists to
 * disclaim, and concept document §9 commits to not labelling areas permanently —
 * a recurring background notification is the most permanent label there is.
 */
export function isWatchable(flag: RiskFlag, now: Date): boolean {
  if (flag.kind === 'chronic') return false;
  if (flag.severityNow < MIN_SEVERITY_TO_WATCH) return false;
  if (new Date(flag.expiresAt).getTime() <= now.getTime()) return false;
  return true;
}

/** The radius to register: the flag's own, plus the approach margin, clamped. */
export function geofenceRadiusFor(flag: RiskFlag): number {
  const wanted = flag.radiusM + APPROACH_MARGIN_M;
  return Math.max(MIN_GEOFENCE_RADIUS_M, Math.min(MAX_GEOFENCE_RADIUS_M, wanted));
}

/** Metres between two coordinates. Haversine, on a sphere — good to ~0.5%. */
export function distanceM(
  a: { lat: number; lon: number },
  b: { lat: number; lon: number },
): number {
  const R = 6_371_000;
  const toRad = (deg: number) => (deg * Math.PI) / 180;
  const dLat = toRad(b.lat - a.lat);
  const dLon = toRad(b.lon - a.lon);
  const lat1 = toRad(a.lat);
  const lat2 = toRad(b.lat);
  const h =
    Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.min(1, Math.sqrt(h)));
}

/**
 * The regions to register, and everything the task will need when one fires.
 *
 * `from` is the user's last known position, used only for ordering. When it is
 * null the flags are ordered by severity alone — correct for a cold start, where
 * "the worst zones in the city" is a better guess than an arbitrary slice.
 *
 * ## Why ordering is by distance before severity
 *
 * Under the region cap, the question is not "which zones are worst" but "which
 * zones could this person plausibly walk into". A severity-90 flag 14 km away is
 * useless to monitor; a severity-55 flag three streets over is the entire point.
 * So flags are bucketed by distance and sorted by severity inside each bucket —
 * near-and-bad first, near-and-moderate next, far-and-bad only if there is room.
 *
 * Buckets rather than a continuous score because a single weighted number would
 * need two weights nobody can justify, and would reorder unpredictably as the
 * person moved.
 */
export function selectZones(
  flags: readonly RiskFlag[],
  options: { from?: { lat: number; lon: number } | null; now?: Date; limit?: number } = {},
): ZoneSelection {
  const now = options.now ?? new Date();
  const limit = options.limit ?? MAX_REGIONS;

  const skipped = { chronic: 0, lowSeverity: 0, expired: 0 };
  const watchable: RiskFlag[] = [];

  for (const flag of flags) {
    if (flag.kind === 'chronic') {
      skipped.chronic += 1;
      continue;
    }
    if (new Date(flag.expiresAt).getTime() <= now.getTime()) {
      skipped.expired += 1;
      continue;
    }
    if (flag.severityNow < MIN_SEVERITY_TO_WATCH) {
      skipped.lowSeverity += 1;
      continue;
    }
    watchable.push(flag);
  }

  const from = options.from ?? null;
  // 2 km, 6 km, then everything. Roughly: this walk, this trip, the rest of the
  // city.
  const bucketOf = (flag: RiskFlag): number => {
    if (!from) return 0;
    const metres = distanceM(from, { lat: flag.lat, lon: flag.lon });
    if (metres <= 2_000) return 0;
    if (metres <= 6_000) return 1;
    return 2;
  };

  const ordered = [...watchable].sort((a, b) => {
    const bucketDiff = bucketOf(a) - bucketOf(b);
    if (bucketDiff !== 0) return bucketDiff;
    return b.severityNow - a.severityNow;
  });

  const chosen = ordered.slice(0, limit);
  const regions: Region[] = [];
  const meta: Record<string, ZoneMeta> = {};

  for (const flag of chosen) {
    // The flag id *is* the identifier. The OS hands it back on a crossing, and
    // it is the key into `meta`, so anything else would need a second lookup
    // table for no benefit.
    const identifier = flag.flagId;
    const radius = geofenceRadiusFor(flag);
    regions.push({
      identifier,
      latitude: flag.lat,
      longitude: flag.lon,
      radius,
      notifyOnEnter: true,
      // Exits are not alerted on. "You have left a risk area" is not actionable,
      // and registering for it doubles the wake-ups for no information.
      notifyOnExit: false,
    });
    meta[identifier] = {
      flagId: flag.flagId,
      statement: flag.mobilityStatement,
      kind: flag.kind,
      status: flag.status,
      sourceCount: flag.sourceCount,
      severity: flag.severityNow,
      lat: flag.lat,
      lon: flag.lon,
      flagRadiusM: flag.radiusM,
      geofenceRadiusM: radius,
    };
  }

  return {
    regions,
    meta,
    dropped: Math.max(0, ordered.length - chosen.length),
    skipped,
  };
}
