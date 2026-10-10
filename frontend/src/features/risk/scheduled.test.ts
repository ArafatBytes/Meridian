/**
 * Forward-dated flag presentation. D09, demo beat 8.
 *
 * These four functions are small, and they are the only part of beat 8 a test can
 * reach: the marker pulls in `react-native-maps` and `MapScreen` pulls in half the
 * app, so neither imports under jest. What is worth pinning here is the handful of
 * cases that would be embarrassing on stage — a window printed backwards, a count
 * that says "1 flags", or a label that still talks about decay while the map is
 * showing tomorrow.
 */
import {
  isScheduledFlag,
  windowText,
  asOfSummary,
  AS_OF_PRESETS,
} from './scheduled';
import type { RiskFlag } from '../../types/contracts/risk';

function flag(overrides: Partial<RiskFlag> = {}): RiskFlag {
  return {
    flagId: 'f1',
    eventKey: 'seed-x',
    kind: 'procession',
    status: 'unconfirmed',
    lat: 23.7389,
    lon: 90.3958,
    radiusM: 600,
    severity0: 55,
    severityNow: 40,
    halfLifeHours: 4,
    observedAt: '2026-10-10T12:00:00Z',
    expiresAt: '2026-10-11T20:00:00Z',
    validFrom: null,
    validTo: null,
    sourceCount: 1,
    sources: [],
    mobilityStatement: 'Heavy crowd near Shahbagh.',
    timeProfile: null,
    confirmedAt: null,
    confidence: 0.6,
    ...overrides,
  } as RiskFlag;
}

describe('isScheduledFlag', () => {
  it('is a flag carrying a window', () => {
    expect(isScheduledFlag(flag({ validFrom: '2026-10-11T04:00:00Z' }))).toBe(true);
  });

  it('is not an ordinary live flag', () => {
    expect(isScheduledFlag(flag())).toBe(false);
  });
});

describe('windowText', () => {
  it('shows both ends when the window is within one day', () => {
    const text = windowText('2026-10-11T04:00:00Z', '2026-10-11T10:00:00Z');
    // Rendered in the device locale, so the shape is asserted rather than the
    // digits — and the clock may be 12-hour, which is why AM/PM is optional here.
    expect(text).toMatch(/^\w{3} \d{1,2}:\d{2}( [AP]M)? – \d{1,2}:\d{2}( [AP]M)?$/);
  });

  it('names the second day when the window crosses one', () => {
    // Two days apart, so this crosses a date boundary in every timezone. Six hours
    // either side of midnight UTC would not: this runs on Dhaka time (UTC+6),
    // where 18:00Z and 06:00Z the next day are the same local day.
    const from = '2026-10-11T04:00:00Z';
    const to = '2026-10-13T04:00:00Z';
    const text = windowText(from, to);

    // The weekday names are computed the same way rather than written out: jest's
    // ICU build does not format them identically to node's, and the claim worth
    // testing is that the SECOND day is named at all, not how it is spelled.
    const label = (iso: string) =>
      new Date(iso).toLocaleDateString([], { weekday: 'short' });
    expect(label(from)).not.toBe(label(to));
    expect(text).toContain(label(from));
    expect(text).toContain(label(to));
    expect(text).toContain('–');
  });

  it('names the day only once when the window stays inside it', () => {
    const text = windowText('2026-10-11T04:00:00Z', '2026-10-11T10:00:00Z');
    const label = new Date('2026-10-11T04:00:00Z').toLocaleDateString([], {
      weekday: 'short',
    });
    expect(text.split(label).length - 1).toBe(1);
  });

  it('says "from" rather than inventing an end we were not given', () => {
    expect(windowText('2026-10-11T04:00:00Z', null)).toContain('from');
    expect(windowText('2026-10-11T04:00:00Z', null)).not.toContain('–');
  });

  it('separates the times with an en dash, not a hyphen', () => {
    // A hyphen between two clock times reads as a minus sign.
    const text = windowText('2026-10-11T04:00:00Z', '2026-10-11T10:00:00Z');
    expect(text).toContain('–');
    expect(text).not.toContain(' - ');
  });
});

describe('asOfSummary', () => {
  const now = Date.parse('2026-10-10T12:00:00Z');

  it('says "Live" at the present, with no instant to read', () => {
    expect(asOfSummary(0, [flag(), flag()], now)).toBe('Live · 2 flags');
  });

  it('counts one flag in the singular', () => {
    expect(asOfSummary(0, [flag()], now)).toBe('Live · 1 flag');
  });

  it('counts the scheduled ones once the map is looking forward', () => {
    const flags = [flag(), flag({ validFrom: '2026-10-11T04:00:00Z' })];
    expect(asOfSummary(24, flags, now)).toMatch(/2 flags, 1 scheduled$/);
  });

  it('does not mention scheduling when nothing ahead is scheduled', () => {
    expect(asOfSummary(6, [flag()], now)).not.toContain('scheduled');
  });

  it('names the instant being shown, so the map is never silently in the future', () => {
    expect(asOfSummary(24, [flag()], now)).toMatch(/^\w{3}/);
  });

  it('never says "flags left" — this control looks forward, not only backward', () => {
    const flags = [flag({ validFrom: '2026-10-11T04:00:00Z' })];
    for (const { hours } of AS_OF_PRESETS) {
      expect(asOfSummary(hours, flags, now)).not.toContain('left');
    }
  });
});

describe('AS_OF_PRESETS', () => {
  it('starts at now and reaches tomorrow, because tomorrow is the beat', () => {
    expect(AS_OF_PRESETS[0]).toEqual({ hours: 0, label: 'Now' });
    expect(AS_OF_PRESETS.find(p => p.hours === 24)?.label).toBe('Tomorrow');
  });

  it('is strictly increasing, so the row reads left to right as time', () => {
    const hours = AS_OF_PRESETS.map(p => p.hours);
    expect(hours).toEqual([...hours].sort((a, b) => a - b));
    expect(new Set(hours).size).toBe(hours.length);
  });
});
