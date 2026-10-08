/**
 * Mirror of `backend/app/contracts/risk.py`.
 *
 * HAND-MIRRORED, AND THAT IS DELIBERATE. There is no generator. The backend is
 * the source of truth; this file follows it, and changing one without the other
 * is the bug this comment exists to prevent. A drift check lands in Track B (B2);
 * until then the rule is social: a change to `app/contracts/risk.py` and a change
 * to this file go in the same commit.
 *
 * Only `RiskFlag` and the enums it needs are mirrored. `RawDocument` and
 * `ExtractedIncident` never reach the client — they are ingestion-internal — so
 * mirroring them would be surface area with no consumer.
 */

/** `IncidentKind` in Python. Values match the `risk_flags.kind` CHECK constraint. */
export const INCIDENT_KINDS = [
  'road_accident',
  'fire',
  'clash',
  'blockade',
  'procession',
  'waterlogging',
  'construction',
  'utility_outage',
  'chronic',
  'other',
] as const;

export type IncidentKind = (typeof INCIDENT_KINDS)[number];

/**
 * `MobilityImpact` in Python.
 *
 * Carried for completeness; the client renders `mobilityStatement` rather than
 * deriving its own wording from this. Concept document §9 — the words the user
 * sees are produced in exactly one place, and that place is on the server.
 */
export const MOBILITY_IMPACTS = [
  'road_blocked',
  'heavy_crowd',
  'delay_likely',
  'lane_closed',
  'impassable',
  'none',
] as const;

export type MobilityImpact = (typeof MOBILITY_IMPACTS)[number];

/**
 * `FlagStatus` in Python.
 *
 * `confirmed` means two or more independent sources agreed. D05 renders the two
 * live states differently on the map, because the distinction is an ethical
 * commitment and not a detail.
 */
export type FlagStatus = 'unconfirmed' | 'confirmed' | 'expired' | 'rejected';

/** `SourceRef` in Python. */
export interface SourceRef {
  sourceId: string;
  url: string;
  publishedAt: string | null;
  title: string | null;
  snippet: string | null;
}

/** `TimeProfile` in Python. Exactly 24 hour-of-day multipliers. */
export interface TimeProfile {
  multipliers: number[];
}

/**
 * `RiskFlag` in Python. One decaying, located claim about mobility.
 *
 * Field names are camelCase here and snake_case on the wire; `risk.service.ts`
 * does the conversion in one place so no screen ever sees `mobility_statement`.
 *
 * `mobilityStatement` is the only text to put in front of a user. Do not build a
 * label from `kind` — a `clash` is displayed as "Road blocked", and that mapping
 * belongs to `app/policy/framing.py`, never to a component.
 */
export interface RiskFlag {
  flagId: string;
  eventKey: string;
  kind: IncidentKind;
  status: FlagStatus;
  lat: number;
  lon: number;
  radiusM: number;
  /** Severity at `observedAt`, 0-100. Stored, and it never changes. */
  severity0: number;
  /**
   * Severity at the instant the surface was asked about, 0-100.
   *
   * Computed server-side on every read — the stored severity run down its half-life
   * curve, then multiplied by an hour-of-day factor (`app/scoring/decay.py`). This is
   * the number to colour a pin by and the number to show a user. `severity0` is
   * context: "74 when it was reported, 42 now" is the claim that the surface decays,
   * and one number cannot make it.
   *
   * Do not compute decay on the device. The arithmetic has exactly one home and a
   * phone is not it — a client that halved the severity itself would disagree with the
   * server about when a flag expires.
   */
  severityNow: number;
  halfLifeHours: number;
  observedAt: string;
  /** Derived server-side. Read-only in every sense. */
  expiresAt: string;
  sourceCount: number;
  sources: SourceRef[];
  mobilityStatement: string;
  timeProfile: TimeProfile | null;
  /** Set only on forward-dated flags from the Scheduled Risk Agent (D09). */
  validFrom: string | null;
  validTo: string | null;

  /**
   * When Rumour Guard promoted this flag to `confirmed` (D05).
   *
   * Null in three legitimate cases, and the UI must render the absence rather than
   * substituting `observedAt`: the flag is still unconfirmed; it was authored
   * confirmed in a fixture, so there was no moment of promotion; or it predates the
   * column. "Confirmed, time unknown" is true. "Confirmed at the moment the fire
   * started" is not.
   */
  confirmedAt: string | null;

  /**
   * How much of `severityNow` should count in a decision, 0-1.
   *
   * Derived server-side from `status` by `app/policy/independence.py` — 1.0 for
   * `confirmed`, 0.6 for `unconfirmed`. Mirrored here rather than re-derived from
   * `status` in TypeScript so that the weight is a server policy with one
   * definition; a copy of the 0.6 in this file is a second definition waiting to
   * drift.
   *
   * `severityNow` is deliberately NOT pre-multiplied by this. That value is the
   * decay story the flag sheet narrates ("74 when observed, 31 now, 42% remaining")
   * and damping it would make that arithmetic wrong. Anything *deciding* something
   * wants `severityNow * confidence`.
   */
  confidence: number;
}
