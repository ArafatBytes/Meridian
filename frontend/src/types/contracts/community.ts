/**
 * Mirror of `backend/app/contracts/community.py`.
 *
 * HAND-MIRRORED, like `risk.ts`, and for the same reason: the backend is the
 * source of truth and there is no generator. A change to
 * `app/contracts/community.py` and a change to this file go in the same commit.
 *
 * ## A cluster is not a flag
 *
 * It is tempting to treat these as the same object with a different badge. They
 * are not, and the whole point of a separate file is that a screen has to decide
 * which one it is holding.
 *
 * | | `RiskFlag` | `CommunityCluster` |
 * |---|---|---|
 * | where it comes from | edited news, police statistics | app users' own reports |
 * | what it claims | a road is blocked | several people reported something here |
 * | who wrote the text | `app/policy/framing.py` | `app/policy/community.py` |
 * | best confidence | 1.0 | 0.6 — there is no route to 1.0 |
 *
 * `Defect 54` is the log of what happens when a surface forgets the difference:
 * the map drew reports and flags as the same pin, *"which makes them look
 * interchangeable"*. Rendering them differently is not decoration.
 *
 * ## What is deliberately absent
 *
 * No category, no family, no report ids, no narrative, no photo. A cluster has
 * nothing to say about *what happened* — only that several people independently
 * said something did. The server has no field for any of it, so this is not a
 * client-side omission that a later screen could undo.
 */

/**
 * `ClusterStatusWire` in Python — the two tiers a client can be served.
 *
 * - `provisional`: two independent reporters. Published, and weighted at 0.3.
 * - `corroborated`: three or more. Weighted at 0.6, the same as an *unconfirmed*
 *   news flag.
 *
 * `expired` and `removed` exist in the database and are never served, so there is
 * no branch for them here. Two app accounts are not two newspapers: that is why
 * the bar is three where a news flag's is two, and why the ceiling is 0.6 where a
 * news flag's is 1.0.
 */
export type ClusterStatus = 'provisional' | 'corroborated';

/**
 * `CommunityCluster` in Python. A decaying, located count of independent reports.
 *
 * Field names are camelCase here and snake_case on the wire; `risk.service.ts`
 * converts in one place so no screen sees `reporter_count`.
 */
export interface CommunityCluster {
  clusterId: string;
  status: ClusterStatus;
  lat: number;
  lon: number;
  radiusM: number;

  /**
   * How many reports are behind this cluster, and how many distinct people filed
   * them. Both, because the difference is the honest part: ten reports from two
   * accounts is two people, and showing only `reportCount` would imply ten
   * witnesses.
   *
   * `reporterCount` is the one that decided the tier. It is never below 2 — the
   * database will not store a cluster with fewer
   * (`community_clusters_needs_two_reporters`).
   */
  reportCount: number;
  reporterCount: number;

  /** Severity at `observedAt`, 0-100. Stored, and it never changes. */
  severity0: number;
  /**
   * Severity at the instant asked about, 0-100. Computed server-side.
   *
   * Decayed on a 72-hour half-life and then modulated by the same night-weighted
   * hour-of-day curve the chronic layer uses — a cluster reads heavier at 2 a.m.
   * than at 2 p.m., which for a product that tells someone whether to walk down a
   * street is the modulation that matters most.
   *
   * Do not compute decay on the device. Same rule as `RiskFlag.severityNow`.
   */
  severityNow: number;
  halfLifeHours: number;

  /** The most recent contributing report. */
  observedAt: string;
  /** The oldest, which is where the statement's "in the last N days" comes from. */
  firstReportAt: string;
  /** Derived server-side by a trigger. Read-only in every sense. */
  expiresAt: string;

  /**
   * The only text to put in front of a user, e.g.
   * *"3 independent reports within 200 m in the last 6 days."*
   *
   * Produced by `app/policy/community.py::to_cluster_statement` and checked by the
   * same banned-vocabulary guard that flag statements pass. **Render it as-is.**
   * Do not build your own sentence from `reporterCount` and `firstReportAt`: the
   * published wording is a product commitment, not a formatting choice, and a
   * client that composed its own would be free to call a place dangerous.
   */
  statement: string;

  /**
   * When `reporterCount` first reached the corroboration threshold, or null on a
   * provisional cluster.
   *
   * A claim about our own process — "when did you decide to believe this?" — not
   * about the reports. The analogue of `RiskFlag.confirmedAt`, and like that field
   * the UI must render its absence rather than substituting `observedAt`.
   */
  corroboratedAt: string | null;

  /**
   * How much of `severityNow` counts in a decision, 0-1.
   *
   * Derived server-side from `status` by `app/policy/community.py` — 0.3 for
   * `provisional`, 0.6 for `corroborated`. Mirrored rather than re-derived here so
   * the weight has one definition; a copy of 0.3 in this file is a second
   * definition waiting to drift.
   *
   * As with flags, `severityNow` is NOT pre-multiplied by it.
   */
  confidence: number;
}
