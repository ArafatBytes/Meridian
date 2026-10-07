/**
 * Hand-mirrored from `backend/app/contracts/risk.py::GeoResolution`.
 *
 * Per CONTRIBUTING.md, this file is written by hand and kept in step with the
 * Python contract deliberately — a generated mirror hides a contract change
 * behind a build step, and a contract change is supposed to be noticed.
 */

/**
 * How a place was resolved. This is shown to the user, not just logged.
 *
 * - `gazetteer`     matched the hand-reviewed Dhaka gazetteer. The reliable path.
 * - `llm_gazetteer` the gazetteer missed and a language model answered, inside
 *                   the pilot bounding box.
 * - `nominatim`     reserved for D06's geocoding proxy. Not produced in D03.
 * - `unresolved`    we do not know. **Draw no pin.**
 */
export type GeoMethod = 'gazetteer' | 'llm_gazetteer' | 'nominatim' | 'unresolved';

export interface GeoResolution {
  lat: number;
  lon: number;
  radiusM: number;
  resolvedName: string;
  method: GeoMethod;
  confidence: number;
  adminArea: string | null;
}

/**
 * `unresolved` is a successful answer meaning "we will not guess", and the
 * coordinates on it are meaningless placeholders. Branch on this, never on
 * whether lat/lon look plausible.
 */
export function isResolved(resolution: GeoResolution): boolean {
  return resolution.method !== 'unresolved';
}
