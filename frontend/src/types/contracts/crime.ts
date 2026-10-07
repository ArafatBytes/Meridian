/**
 * Crime report categories — the one authority on the client.
 *
 * Mirrors the Postgres enum `public.crime_category` in
 * `backend/migrations/supabase/SCHEMA.sql`. **The database values are lowercase**,
 * and `AddReportScreen` has always sent lowercase ids, so lowercase is simply what
 * a category is.
 *
 * ## Why this file exists (defect 3)
 *
 * `frontend/src/types/index.ts` declared `CrimeCategory` as a capitalised union
 * (`'Theft' | 'Robbery' | ...`) and `MapScreen`'s `CRIME_COLORS` was keyed by it.
 * Every lookup therefore missed: `CRIME_COLORS['theft']` is `undefined` when the
 * keys are `'Theft'`. The symptom was that **no crime marker on the map had a
 * colour** — not a styling oversight but a key mismatch, invisible because
 * `Record` lookups return `undefined` rather than failing.
 *
 * The fix is not just to lowercase the keys. It is to derive the type from one
 * list so the two cannot drift again: `CRIME_COLORS` is typed
 * `Record<CrimeCategory, string>`, so adding a value to `CRIME_CATEGORIES`
 * without giving it a colour is a compile error rather than a grey pin.
 */

/**
 * Every value `public.crime_category` accepts, in the order SCHEMA.sql declares
 * them. Adding one here without adding it to the database enum produces an insert
 * that Postgres rejects; adding it to the database without adding it here leaves
 * reports the map cannot colour.
 */
export const CRIME_CATEGORIES = [
  'theft',
  'assault',
  'harassment',
  'vandalism',
  'burglary',
  'robbery',
  'fraud',
  'other',
] as const;

export type CrimeCategory = (typeof CRIME_CATEGORIES)[number];

/**
 * Display text for a category.
 *
 * A lookup table rather than `category[0].toUpperCase() + ...`, so that a future
 * multi-word value ('drug related') gets a correct label instead of 'Drug
 * related', and so that Bangla localisation (Track B, B20) has one place to go.
 */
export const CRIME_CATEGORY_LABELS: Record<CrimeCategory, string> = {
  theft: 'Theft',
  assault: 'Assault',
  harassment: 'Harassment',
  vandalism: 'Vandalism',
  burglary: 'Burglary',
  robbery: 'Robbery',
  fraud: 'Fraud',
  other: 'Other',
};

/**
 * Label for a category that may have come from the database as an unexpected
 * value.
 *
 * Reports are read straight from Supabase with no validation step, so a row
 * written before an enum change — or by a tool that bypassed the app — can carry
 * anything. Falling back to the raw string shows the user something true instead
 * of 'undefined'.
 */
export function crimeCategoryLabel(category: string): string {
  return CRIME_CATEGORY_LABELS[category as CrimeCategory] ?? category;
}

/** Whether a string from the database is a category this client knows. */
export function isCrimeCategory(value: string): value is CrimeCategory {
  return (CRIME_CATEGORIES as readonly string[]).includes(value);
}
