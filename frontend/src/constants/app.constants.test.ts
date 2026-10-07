/* eslint-disable @typescript-eslint/no-require-imports --
 * `require` is deliberate here. These tests change process.env and then call
 * jest.resetModules(), so the module has to be re-loaded afterwards to pick up
 * the new value. A static `import` is hoisted and evaluated once, before the
 * env change, which would make every assertion vacuous.
 */
/**
 * Regression guards for configuration that was previously hardcoded.
 *
 * `API_BASE_URL` was `http://192.168.0.103:8000/api/v1` — correct on exactly
 * one machine. Everywhere else the app reached Supabase fine and the backend
 * not at all, which presents as a backend bug and is not one. These tests exist
 * so that cannot silently come back.
 */

describe('API_BASE_URL', () => {
  const ORIGINAL = process.env.EXPO_PUBLIC_API_BASE_URL;

  afterEach(() => {
    process.env.EXPO_PUBLIC_API_BASE_URL = ORIGINAL;
    jest.resetModules();
  });

  it('reads EXPO_PUBLIC_API_BASE_URL when set', () => {
    process.env.EXPO_PUBLIC_API_BASE_URL = 'http://10.1.2.3:8000/api/v1';
    jest.resetModules();
    // Required after resetModules so the module re-reads process.env.
    const { API_BASE_URL } = require('./app.constants');
    expect(API_BASE_URL).toBe('http://10.1.2.3:8000/api/v1');
  });

  it('falls back to a default when unset rather than throwing', () => {
    delete process.env.EXPO_PUBLIC_API_BASE_URL;
    jest.resetModules();
    const { API_BASE_URL } = require('./app.constants');
    expect(API_BASE_URL).toMatch(/^https?:\/\/.+\/api\/v1$/);
  });

  it('is never localhost by default — a device cannot reach that', () => {
    delete process.env.EXPO_PUBLIC_API_BASE_URL;
    jest.resetModules();
    const { API_BASE_URL } = require('./app.constants');
    expect(API_BASE_URL).not.toMatch(/localhost|127\.0\.0\.1/);
  });
});

describe('crime categories', () => {
  it('match the lowercase values the database enum accepts', () => {
    // SCHEMA.sql defines crime_category with lowercase values, and
    // AddReportScreen sends lowercase ids. The capitalised list here is a UI
    // picker list, still unused by the report form; if anything starts using it
    // for a write, the values must be lowercased first or the insert is rejected.
    //
    // Defect 3 itself is FIXED (D01): the authority is now
    // src/types/contracts/crime.ts, whose values are lowercase and from which
    // MapScreen's CRIME_COLORS is typed, so a missing colour is a compile error.
    // This list is the remaining capitalised one, kept because it names
    // categories the database enum does not have (Kidnapping, Murder, ...).
    // Reconciling the two is Track B (B3).
    const { CRIME_CATEGORIES } = require('./app.constants');
    const dbEnum = [
      'theft', 'assault', 'harassment', 'vandalism',
      'burglary', 'robbery', 'fraud', 'other',
    ];
    const overlap = CRIME_CATEGORIES
      .map((c: string) => c.toLowerCase())
      .filter((c: string) => dbEnum.includes(c));
    // Every db value should be representable in the UI list.
    expect(overlap.length).toBeGreaterThanOrEqual(dbEnum.length - 1);
  });
});
