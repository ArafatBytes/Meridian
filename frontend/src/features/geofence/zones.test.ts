/**
 * Which risk flags become geofences, and which must not. B6a / S17.
 *
 * The region list is the whole feature: a flag that is not in it is a road the
 * user walks into with no warning, and a flag that should not be in it is a
 * notification every time they leave the house. Both failures are invisible on a
 * phone — you cannot tell "no alert because nothing was registered" from "no
 * alert because I did not cross the boundary" without walking the city twice.
 *
 * So the selection rules are tested here, where they are plain data.
 */

import {
  APPROACH_MARGIN_M,
  MAX_GEOFENCE_RADIUS_M,
  MIN_GEOFENCE_RADIUS_M,
  MIN_SEVERITY_TO_WATCH,
  distanceM,
  geofenceRadiusFor,
  isWatchable,
  selectZones,
} from './zones';
import type { RiskFlag } from '../../types/contracts/risk';

const NOW = new Date('2026-10-11T09:00:00Z');
const LATER = new Date('2026-10-11T18:00:00Z').toISOString();
const EARLIER = new Date('2026-10-11T06:00:00Z').toISOString();

/** Shahbagh, near enough. */
const HERE = { lat: 23.7381, lon: 90.3954 };

function flag(overrides: Partial<RiskFlag> = {}): RiskFlag {
  return {
    flagId: Math.random().toString(36).slice(2),
    eventKey: 'test',
    kind: 'fire',
    status: 'confirmed',
    lat: HERE.lat,
    lon: HERE.lon,
    radiusM: 300,
    severity0: 70,
    severityNow: 70,
    halfLifeHours: 3,
    observedAt: EARLIER,
    expiresAt: LATER,
    sourceCount: 3,
    sources: [],
    mobilityStatement: 'Road blocked near Shahbagh.',
    confidence: 1,
    ...overrides,
  } as RiskFlag;
}

describe('isWatchable', () => {
  it('watches a live, serious, non-chronic flag', () => {
    expect(isWatchable(flag(), NOW)).toBe(true);
  });

  /**
   * The single most important exclusion in the feature.
   *
   * A chronic flag is D02's police-statistics baseline — a historical average
   * with a ~2 km radius that never moves and never expires. A geofence on one
   * fires every time its owner leaves the house, forever. That is the "stale red
   * zones" behaviour demo beat 5 exists to disclaim, and a recurring background
   * notification is the most permanent label a product can put on a place
   * (concept document §9).
   */
  it('never watches a chronic flag, however severe', () => {
    expect(isWatchable(flag({ kind: 'chronic', severityNow: 100 }), NOW)).toBe(false);
  });

  it('does not watch a flag too minor to interrupt someone', () => {
    expect(isWatchable(flag({ severityNow: MIN_SEVERITY_TO_WATCH - 0.1 }), NOW)).toBe(false);
    expect(isWatchable(flag({ severityNow: MIN_SEVERITY_TO_WATCH }), NOW)).toBe(true);
  });

  it('does not watch an expired flag', () => {
    expect(isWatchable(flag({ expiresAt: EARLIER }), NOW)).toBe(false);
  });
});

describe('geofenceRadiusFor', () => {
  /**
   * The approach margin is what makes the alert useful rather than a commentary.
   *
   * Firing as somebody enters a flagged area tells them something they are about
   * to see for themselves. Firing 250 m out gives them a junction at which to
   * turn, which is the only reason to send it.
   */
  it('adds the approach margin to the flag radius', () => {
    expect(geofenceRadiusFor(flag({ radiusM: 400 }))).toBe(400 + APPROACH_MARGIN_M);
  });

  /**
   * Android's geofencing is unreliable below ~100 m — the OS trades accuracy for
   * battery and simply never reports a small circle. A radius that cannot be
   * detected is worse than none: the zone looks monitored and is not.
   */
  it('never registers a circle too small for the OS to detect', () => {
    expect(geofenceRadiusFor(flag({ radiusM: 10 }))).toBeGreaterThanOrEqual(
      MIN_GEOFENCE_RADIUS_M,
    );
  });

  it('caps a huge radius so an alert is not just "you are outdoors"', () => {
    expect(geofenceRadiusFor(flag({ radiusM: 5000 }))).toBe(MAX_GEOFENCE_RADIUS_M);
  });
});

describe('selectZones', () => {
  it('returns one region per watchable flag, carrying its framed text', () => {
    const live = flag({ mobilityStatement: 'Road blocked near Bangshal.' });
    const selection = selectZones([live], { from: HERE, now: NOW });

    expect(selection.regions).toHaveLength(1);
    expect(selection.regions[0]).toMatchObject({
      identifier: live.flagId,
      latitude: live.lat,
      longitude: live.lon,
      notifyOnEnter: true,
      // Exits are never registered: "you have left a risk area" is not
      // actionable and doubles the wake-ups for no information.
      notifyOnExit: false,
    });
    expect(selection.meta[live.flagId].statement).toBe('Road blocked near Bangshal.');
  });

  it('counts what it skipped, and why', () => {
    const selection = selectZones(
      [
        flag(),
        flag({ kind: 'chronic' }),
        flag({ kind: 'chronic' }),
        flag({ severityNow: 10 }),
        flag({ expiresAt: EARLIER }),
      ],
      { from: HERE, now: NOW },
    );
    expect(selection.regions).toHaveLength(1);
    expect(selection.skipped).toEqual({ chronic: 2, lowSeverity: 1, expired: 1 });
  });

  /**
   * The platform caps monitoring at 20 regions on iOS and 100 on Android, and
   * **exceeding it does not error** — the extras are silently dropped. For a
   * safety feature that is the worst available failure, so the list is capped
   * deliberately and `dropped` is reported so the UI can say so.
   */
  it('respects the region limit and reports the overflow', () => {
    const many = Array.from({ length: 8 }, (_, index) =>
      flag({ severityNow: 50 + index }),
    );
    const selection = selectZones(many, { from: HERE, now: NOW, limit: 5 });
    expect(selection.regions).toHaveLength(5);
    expect(selection.dropped).toBe(3);
  });

  /**
   * Under the cap, the question is not "which zones are worst" but "which could
   * this person plausibly walk into".
   *
   * A severity-95 flag 14 km away is useless to monitor; a severity-55 flag three
   * streets over is the entire point. So flags are bucketed by distance and
   * sorted by severity inside the bucket — and this test fails if that is ever
   * flattened into a single severity sort, which is the obvious "simplification".
   */
  it('prefers a nearby moderate zone over a distant severe one', () => {
    const near = flag({ severityNow: 55, lat: HERE.lat + 0.004, lon: HERE.lon });
    // ~0.2 degrees of latitude is roughly 22 km.
    const farButWorse = flag({ severityNow: 95, lat: HERE.lat + 0.2, lon: HERE.lon });

    const selection = selectZones([farButWorse, near], { from: HERE, now: NOW, limit: 1 });
    expect(selection.regions[0].identifier).toBe(near.flagId);
  });

  it('orders by severity among zones that are equally close', () => {
    const mild = flag({ severityNow: 50, lat: HERE.lat + 0.001, lon: HERE.lon });
    const bad = flag({ severityNow: 90, lat: HERE.lat + 0.001, lon: HERE.lon + 0.001 });
    const selection = selectZones([mild, bad], { from: HERE, now: NOW, limit: 1 });
    expect(selection.regions[0].identifier).toBe(bad.flagId);
  });

  /**
   * No position yet is a normal cold start, not an error.
   *
   * Ordering by severity alone is the right fallback: "the worst zones in the
   * city" is a better guess than an arbitrary slice, and the set is replaced on
   * the next refresh once a fix exists.
   */
  it('works with no known position', () => {
    const selection = selectZones([flag({ severityNow: 80 }), flag({ severityNow: 50 })], {
      from: null,
      now: NOW,
      limit: 1,
    });
    expect(selection.regions).toHaveLength(1);
    expect(selection.meta[selection.regions[0].identifier].severity).toBe(80);
  });

  it('returns nothing, without throwing, when there is nothing to watch', () => {
    const selection = selectZones([], { from: HERE, now: NOW });
    expect(selection.regions).toEqual([]);
    expect(selection.meta).toEqual({});
    expect(selection.dropped).toBe(0);
  });
});

describe('distanceM', () => {
  it('is zero for the same point', () => {
    expect(distanceM(HERE, HERE)).toBeCloseTo(0, 5);
  });

  /** ~0.01° of latitude is about 1.11 km anywhere on Earth. */
  it('measures a known latitude step', () => {
    const metres = distanceM(HERE, { lat: HERE.lat + 0.01, lon: HERE.lon });
    expect(metres).toBeGreaterThan(1050);
    expect(metres).toBeLessThan(1170);
  });

  it('is symmetric', () => {
    const a = { lat: 23.7, lon: 90.4 };
    const b = { lat: 23.8, lon: 90.5 };
    expect(distanceM(a, b)).toBeCloseTo(distanceM(b, a), 6);
  });
});
