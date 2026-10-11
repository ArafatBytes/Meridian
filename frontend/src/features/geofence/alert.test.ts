/**
 * Invariant: **a zone alert says no more about a place than the map does.**
 *
 * B6a / S17. Concept document §9 commits the product to describing effects on
 * movement and never characterising a place, and this is the hardest place in
 * the app to keep that — because the obvious sentence writes itself:
 *
 *     "You are entering a dangerous area"
 *
 * It is helpful, it is what a user would expect, and it is precisely what the
 * product must not say. There is no server in this path to stop it either: the
 * notification is composed **on the device**, in the background, by
 * `composeZoneAlert`.
 *
 * So the same residue check the backend uses on its own notifications is applied
 * here: compose an alert for every zone shape the app can produce, delete the
 * forwarded statement, and assert the remainder is **byte-identical**. Fixed
 * boilerplate plus one forwarded string is the only shape that survives it. Add
 * a place name, a distance, a severity word, anything derived from the zone
 * other than its verification tier, and the residues differ and this fails.
 */

import {
  ZONE_ALERT_TITLE,
  ZONE_REALERT_AFTER_MS,
  composeZoneAlert,
  sourceClause,
} from './alert';
import type { ZoneMeta } from './zones';

function meta(overrides: Partial<ZoneMeta> = {}): ZoneMeta {
  return {
    flagId: 'flag-1',
    statement: 'Road blocked near Bangshal.',
    kind: 'fire',
    status: 'confirmed',
    sourceCount: 3,
    severity: 72.4,
    lat: 23.71,
    lon: 90.42,
    flagRadiusM: 300,
    geofenceRadiusM: 550,
    ...overrides,
  };
}

/** Every statement `framing.py` can produce, in shape if not in full. */
const STATEMENTS = [
  'Road blocked near Bangshal.',
  'Heavy crowd near Shahbagh.',
  'Road impassable in this area.',
  'Delay likely near Mirpur 10 golchattar, ongoing works.',
  'Lane closed near গোলচত্বর, standing water.',
];

const TIERS: { status: string; sourceCount: number }[] = [
  { status: 'confirmed', sourceCount: 2 },
  { status: 'confirmed', sourceCount: 7 },
  { status: 'unconfirmed', sourceCount: 1 },
];

describe('composeZoneAlert', () => {
  it('forwards the statement verbatim', () => {
    const alert = composeZoneAlert(meta({ statement: 'Heavy crowd near Shahbagh.' }));
    expect(alert.body).toContain('Heavy crowd near Shahbagh.');
    expect(alert.title).toBe(ZONE_ALERT_TITLE);
  });

  /**
   * The residue test. The one that catches new prose.
   *
   * Grouped by `(status, sourceCount)` because the corroboration clause
   * legitimately varies with those two and with nothing else.
   */
  it('is boilerplate plus one forwarded string', () => {
    const residues: Record<string, Set<string>> = {};

    for (const statement of STATEMENTS) {
      for (const tier of TIERS) {
        for (const kind of ['fire', 'blockade', 'waterlogging']) {
          for (const severity of [41, 72.4, 99]) {
            const alert = composeZoneAlert(
              meta({ statement, kind, severity, ...tier }),
            );
            expect(alert.body).toContain(statement);
            const residue = alert.body.replace(statement, '<STATEMENT>');
            const key = `${tier.status}/${tier.sourceCount}`;
            (residues[key] ??= new Set()).add(residue);
          }
        }
      }
    }

    const varying = Object.entries(residues).filter(([, set]) => set.size > 1);
    expect(varying.map(([key, set]) => [key, [...set]])).toEqual([]);
  });

  /**
   * No safety vocabulary, in any combination.
   *
   * A short, deliberately blunt list — the point is not to be exhaustive (the
   * residue test above is what catches *new* text) but to pin the handful of
   * words somebody would reach for first when "improving" a zone alert.
   */
  it('never characterises the place', () => {
    const banned = [
      'danger',
      'dangerous',
      'unsafe',
      'risky',
      'crime',
      'avoid',
      'warning',
      'severe',
      'critical',
      'urgent',
    ];
    for (const statement of STATEMENTS) {
      for (const tier of TIERS) {
        const alert = composeZoneAlert(meta({ statement, ...tier }));
        const text = `${alert.title} ${alert.body}`.toLowerCase();
        for (const word of banned) {
          expect(text).not.toContain(word);
        }
      }
    }
  });

  it('does not put the severity number in the text', () => {
    const alert = composeZoneAlert(meta({ severity: 87.4 }));
    expect(alert.body).not.toContain('87');
  });

  /**
   * An empty statement must not drop the alert.
   *
   * It should not happen — `framing.py` never emits one — but a row edited by
   * hand in the Supabase console is a real thing on this project. The person is
   * near something flagged; saying so without the detail beats saying nothing.
   */
  it('still alerts when the statement is missing', () => {
    const alert = composeZoneAlert(meta({ statement: '' }));
    expect(alert.body.length).toBeGreaterThan(10);
    expect(alert.body).toContain('approaching');
  });
});

describe('sourceClause', () => {
  it('states the count only when it corroborates', () => {
    expect(sourceClause({ status: 'confirmed', sourceCount: 3 })).toContain('3');
    const single = sourceClause({ status: 'unconfirmed', sourceCount: 1 });
    // "1 source" invites the reader to weigh a number; "unconfirmed" tells them
    // the thing that matters. D05's tiering, in the one sentence they may read.
    expect(single).not.toContain('1');
    expect(single.toLowerCase()).toContain('unconfirmed');
  });
});

describe('the re-alert window', () => {
  /**
   * Six hours, and the number is the feature.
   *
   * Android reports a geofence entry on **every** boundary crossing, and somebody
   * who lives or works beside a flagged corridor crosses it repeatedly — walking
   * to a shop and back is two. Without a debounce this is the reason they turn
   * notifications off. Not "once ever", because severity and corroboration both
   * change over a day: a road that was a delay at noon can be impassable by
   * evening.
   */
  it('is six hours', () => {
    expect(ZONE_REALERT_AFTER_MS).toBe(6 * 60 * 60 * 1000);
  });
});
