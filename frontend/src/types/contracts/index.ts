/**
 * Hand-written mirrors of the backend's shared contracts.
 *
 * `backend/app/contracts/` is the source of truth. These files follow it. There
 * is no generator and no build step; a change on one side and a change on the
 * other belong in the same commit. IMPLEMENTATION_PLAN.md §6 is the spec, and a
 * CI drift check lands in Track B (B2).
 */

export * from './risk';
export * from './crime';
export * from './community';
