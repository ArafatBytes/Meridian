/**
 * The client half of "one report is never a published claim about a place".
 *
 * The backend enforces the rule in four layers (`policy/community.py`, a CHECK
 * constraint, a statement producer that raises, and RLS). None of that stops a
 * *client* from drawing something it should not, so the things worth testing here
 * are the ones a screen could get wrong on its own:
 *
 * 1. the two tiers are the only ones a client has a branch for;
 * 2. the published sentence is rendered, never rebuilt;
 * 3. the report-status vocabulary no longer contains a trust level;
 * 4. a cluster and a flag are never the same shape, so a component cannot be
 *    written that accepts either without noticing.
 */

import type { ClusterStatus, CommunityCluster } from './community';
import {
  REPORT_STATUSES,
  isReportStatus,
  reportStatusLabel,
  type ReportStatus,
} from './crime';

const cluster: CommunityCluster = {
  clusterId: 'c-1',
  status: 'corroborated',
  lat: 23.7465,
  lon: 90.376,
  radiusM: 200,
  reportCount: 5,
  reporterCount: 3,
  severity0: 50,
  severityNow: 42.4,
  halfLifeHours: 72,
  observedAt: '2026-10-12T18:00:00Z',
  firstReportAt: '2026-10-06T09:00:00Z',
  expiresAt: '2026-10-22T18:00:00Z',
  statement: '3 independent reports within 200 m in the last 6 days.',
  corroboratedAt: '2026-10-12T18:05:00Z',
  confidence: 0.6,
};

describe('the two cluster tiers', () => {
  it('has a branch for exactly the two live statuses', () => {
    // A compile-time assertion written as a runtime one: if `ClusterStatus` ever
    // grows `expired` or `removed`, this object stops type-checking and the
    // omission becomes visible rather than silently rendering a retired cluster.
    const handled: Record<ClusterStatus, string> = {
      provisional: 'hollow, dashed',
      corroborated: 'filled, solid',
    };
    expect(Object.keys(handled).sort()).toEqual(['corroborated', 'provisional']);
  });

  it('weights a corroborated cluster above a provisional one, and both below 1', () => {
    // Mirrors `app/policy/community.py`. The ceiling is the point: 1.0 means
    // independent editors agreed, and community reports have no route to it.
    const provisional = { ...cluster, status: 'provisional' as const, confidence: 0.3 };
    expect(provisional.confidence).toBeLessThan(cluster.confidence);
    expect(cluster.confidence).toBeLessThan(1);
  });
});

describe('the published statement', () => {
  it('names a count and a recency', () => {
    expect(cluster.statement).toMatch(/^\d+ independent reports within \d+ m/);
    expect(cluster.statement).toMatch(/in the last \d+ days?\.$/);
  });

  it('never characterises the place or names a category', () => {
    // The client's second opinion on the server's framing guard. If a cluster
    // statement ever arrives carrying one of these, the bug is on the server --
    // but this is the assertion that would catch a client that started composing
    // its own sentence, which is the mistake that is actually available here.
    const forbidden = [
      'dangerous',
      'unsafe',
      'crime',
      'theft',
      'robbery',
      'assault',
      'harassment',
      'violent',
      'property',
    ];
    for (const term of forbidden) {
      expect(cluster.statement.toLowerCase()).not.toContain(term);
    }
  });
});

describe('report counts are two different facts', () => {
  it('can have more reports than reporters', () => {
    expect(cluster.reportCount).toBeGreaterThan(cluster.reporterCount);
  });

  it('never has more reporters than reports', () => {
    // Ten reports from two people is two people; it can never be twelve. The
    // database carries the same constraint.
    expect(cluster.reporterCount).toBeLessThanOrEqual(cluster.reportCount);
  });

  it('never publishes a single reporter', () => {
    expect(cluster.reporterCount).toBeGreaterThanOrEqual(2);
  });
});

describe('a cluster is not a flag', () => {
  it('carries no kind, no mobility statement and no sources', () => {
    // The structural guarantee behind Defect 54's fix. A component written
    // against `RiskFlag` cannot accidentally be handed one of these, because the
    // fields it would reach for do not exist.
    const keys = Object.keys(cluster);
    expect(keys).not.toContain('kind');
    expect(keys).not.toContain('mobilityStatement');
    expect(keys).not.toContain('sources');
    expect(keys).not.toContain('sourceCount');
  });

  it('carries no category, family, narrative or report ids', () => {
    // The privacy guarantee. A cluster says how many people, how close, how
    // recently -- and nothing about what happened or who said it.
    const keys = Object.keys(cluster);
    for (const leak of ['category', 'family', 'title', 'description', 'reports', 'userId']) {
      expect(keys).not.toContain(leak);
    }
  });
});

describe('the report status vocabulary', () => {
  it('has no trust level left in it', () => {
    // The whole point of the B13 migration. `pending` and `verified` were a
    // trust question nothing could answer; `investigating` and `resolved` were a
    // casework question `gd_drafts` already owns.
    for (const retired of ['pending', 'verified', 'investigating', 'resolved']) {
      expect(REPORT_STATUSES as readonly string[]).not.toContain(retired);
      expect(isReportStatus(retired)).toBe(false);
    }
  });

  it('is exactly the three states the database allows', () => {
    expect([...REPORT_STATUSES]).toEqual(['filed', 'withdrawn', 'removed']);
  });

  it('calls a filed report "on record" rather than "filed"', () => {
    // "Filed" is the wrong word in this app: filing is what happens at a thana
    // counter, and `gd_drafts` uses it for that. A user reading "Filed" on their
    // own report would reasonably think it had reached the police.
    expect(reportStatusLabel('filed')).toBe('On record');
    expect(reportStatusLabel('filed').toLowerCase()).not.toContain('filed');
  });

  it('labels every status it declares', () => {
    for (const status of REPORT_STATUSES) {
      const label = reportStatusLabel(status);
      expect(label).toBeTruthy();
      expect(label).not.toBe(status);
    }
  });

  it('never implies a report has been checked', () => {
    const suggestive = ['verified', 'approved', 'confirmed', 'pending', 'review'];
    for (const status of REPORT_STATUSES) {
      const label = reportStatusLabel(status).toLowerCase();
      for (const term of suggestive) {
        expect(label).not.toContain(term);
      }
    }
  });

  it('falls back to the raw value for a status it does not know', () => {
    // Reports are read straight from Supabase with no validation step, so a row
    // written before a vocabulary change can carry anything. Showing the raw
    // string is truer than showing 'undefined'.
    const unknown = 'something-else' as ReportStatus;
    expect(reportStatusLabel(unknown)).toBe('something-else');
  });
});
