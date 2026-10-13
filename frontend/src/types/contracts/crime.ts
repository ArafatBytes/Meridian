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

/**
 * Every value `crime_reports.status` accepts, after B13.
 *
 * Mirrors the `crime_reports_status_check` constraint in
 * `backend/migrations/versions/20261013120000__report_trust.sql`.
 *
 * ## What this replaced, and why
 *
 * It used to be `('pending', 'verified', 'investigating', 'resolved')`, which mixed
 * two unrelated questions and could answer neither:
 *
 * - a **trust** question (`pending` -> `verified`), which nothing could ever answer,
 *   because nothing wrote the column and there was no role to gate an approver on;
 * - a **casework** question (`investigating` -> `resolved`), which `gd_drafts`
 *   already owns properly.
 *
 * So both report screens showed every user "Pending" forever, beside a `✓` no code
 * path could produce.
 *
 * **A report is no longer approved at all.** A moderator cannot verify that a crime
 * occurred — only that the prose looks plausible — and a badge meaning "someone
 * thought this looked fine" is worse than no badge, because users trust it. Trust is
 * decided over *several independent reports* instead, which is how this system
 * already decides what to believe about news. See `contracts/community.ts`.
 *
 * What is left is three states that are each reachable by code that exists.
 */
export const REPORT_STATUSES = ['filed', 'withdrawn', 'removed'] as const;

export type ReportStatus = (typeof REPORT_STATUSES)[number];

/**
 * What each status is called on screen.
 *
 * `filed` is **"On record"**, not "Filed". "Filed" is the wrong word in this app
 * specifically: filing is what happens at a thana counter, and `gd_drafts` uses it
 * for exactly that. A user reading "Filed" on their own report would reasonably
 * think it had reached the police, which is the one thing this product is careful
 * never to imply (see `test_gd_is_never_filed_for_you.py`).
 *
 * None of the three says anything about whether the report is believed, because the
 * app has no basis for saying it.
 */
const REPORT_STATUS_LABELS: Record<ReportStatus, string> = {
  filed: 'On record',
  withdrawn: 'Withdrawn',
  removed: 'Removed',
};

export function reportStatusLabel(status: string): string {
  return REPORT_STATUS_LABELS[status as ReportStatus] ?? status;
}

/** Whether a string from the database is a status this client knows. */
export function isReportStatus(value: string): value is ReportStatus {
  return (REPORT_STATUSES as readonly string[]).includes(value);
}
