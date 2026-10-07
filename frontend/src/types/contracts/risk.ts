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
  /** Severity at `observedAt`, 0-100. Not the severity now; D02 adds that. */
  severity0: number;
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
}
