# ADR 0005 — Reordering the plan for the 24 October finale

| | |
|---|---|
| **Status** | Accepted |
| **Date** | 2026-10-07 |
| **Decider** | Nakib (owner) |
| **Consulted** | Arafat — **no.** See *Consequences*. |
| **Supersedes** | `IMPLEMENTATION_PLAN.md` line 6 ("No hackathon deadline governs this plan") and §11 (sprint sequence) |
| **Does not supersede** | Anything else in `IMPLEMENTATION_PLAN.md`. Its task specifications remain authoritative. |

---

## Context

`IMPLEMENTATION_PLAN.md` line 6 states: *"Target: production-grade public release. **No hackathon
deadline governs this plan.**"* That is a real decision and it was taken deliberately. It is also
incompatible with the schedule the project is actually on.

The facts as of today:

- `Meridian_Concept_Document.md` §11 puts **Round 3, the finale, on 24 October 2026** — live
  demonstration, impact presentation, judges' Q&A. That is **17 days away.**
- The plan is **39 sprints**, which its own Appendix C estimates at *"roughly nine to ten months
  part-time."*
- **Phase 0 alone** (S02–S04, 28 unticked boxes) would complete around **28 October** at the plan's
  stated pace of one sprint per person per week. Four days *after* the finale, and with no
  user-visible output.
- The concept document's own roadmap expected the ingestion pipeline (Oct 1–3) and the Geolocation
  Agent plus gazetteer (Oct 4–7) to be finished **by today**. Actual state: **0 of 8 agents**, no
  ingestion layer, no gazetteer, no LLM client.

Following the plan's existing order therefore means arriving at the finale able to demonstrate none
of the differentiators the concept document is built on. The inherited application works and demos
well, but it is a crime-reporting app with safety-weighted routing — which is the *starting point*
the plan was written to move away from.

Round 2 (prototype submission, closing 14 October) is explicitly **not** the target of this
decision; the owner has scoped the remaining effort to the finale.

## Decision

**Reorder the plan. Do not reduce it.**

1. A new document, **`DEMO_PLAN.md`**, becomes the authoritative *sequence* of work until
   24 October. It defines a demo track of ten sprints, `D01`–`D10`.
2. `IMPLEMENTATION_PLAN.md` remains the authoritative statement of *what each task means*. It is
   not edited except to tick boxes as they complete. **No task is deleted from it.**
3. Every unticked item in `IMPLEMENTATION_PLAN.md` lands in exactly one of two places, and
   `DEMO_PLAN.md` carries a coverage table proving it:
   - the **demo track** (`D01`–`D10`), if the finale needs it;
   - **Track B**, the continuation sequence, if it does not. Track B retains the original task text
     and runs in order once the demo track is finished or the finale has passed.
4. **Crime detection from image is in the demo.** This is an owner decision against the plan's own
   §12 (*"it does not rewrite the AI vision stack… not on the concept document's critical path"*).
   S06 is therefore promoted into the demo track as `D07`, not deferred. Defects 29, 30, 5 and 13
   are demo blockers rather than Phase 1 debt.
5. The relay rules in §2 stand. The Prototype Gate is relaxed, not suspended: **gate 1
   (`check.sh` green) and gate 4 (`PROGRESS.md` entry) remain mandatory at every handoff.** The
   per-sprint `smoke.sh` demo function and the §9 environment-variable bookkeeping drop to
   best-effort until 24 October.
6. **Every demo sprint must end in something demonstrable on a device**, and ships a device
   walkthrough (`docs/walkthroughs/D<nn>.md`) as a gate. A sprint that produces data also ships the
   screen that renders it, in the same sprint. *Added after review: the first draft of `DEMO_PLAN.md`
   put the map overlay in D06, which left D01–D05 — nine of the seventeen days — with nothing
   visible on a phone, and left demo beat 3 with no sprint building its search box at all. That is
   the exact failure this project has hit before.*
7. ADR numbering is unaffected. `0001` (data plane), `0002` (auth) and `0004` (migrations) remain
   owed as *documents* and move to Track B. `0003` (user identity) is **executed as a migration** in
   `D01`, because the `risk_flags` foreign keys depend on which user table is canonical; its written
   document also moves to Track B.

## Revisions

**2026-10-07, same day — dependency audit of `DEMO_PLAN.md`.** The owner asked for the reordering to
be re-checked for ordering conflicts before any code was written. Thirteen defects were found and
fixed. Three were blocking, and two of those predated this ADR — the original sprint order carried
them too; forcing "what runs on a device at the end of this sprint?" is what made them visible.

| | Defect | Resolution |
|---|---|---|
| **Blocker** | **D01 executed ADR 0003, dropping `public.users`, while `endpoints/sos.py` creates rows in it on every trigger and `endpoints/voice.py` imports the model.** SOS — the only feature working end to end, and demo beat 9 — would have broken on 8 Oct and surfaced on the 23rd. The stated justification was wrong: `risk_flags` has no `user_id`, so nothing in the demo track depended on it. *(Pre-existing: S02 carried the same hazard.)* | **ADR 0003 execution moved to Track B (B1)**, with the code changes it requires named there. |
| **Blocker** | **D03's Geolocation Agent needs its LLM fallback, but `app/llm/client.py` had been moved to D04.** *(Introduced by the showability rewrite — the client was moved out of D01 to make room for a UI slice without re-checking the first consumer.)* | **LLM client moved to D03**, its first consumer. |
| **Blocker** | **The hand-built 200-flag fixture conflicts with `RiskFlag.mobility_statement` being a stored field that "ONLY policy.framing writes"** (plan §6.1). The cheap escape would have been to weaken the D01 invariant test. *(Pre-existing: S03 + S04.)* | **Fixtures store structured fields only; the statement is derived through `framing.py` at load time.** Stated in both D01 and D02. |
| Serious | D01's flags endpoint had no defined data source and no stated relationship to D02's `RiskSurface`. | D01 ships the protocol **plus a minimal `DbRiskSurface`**; D02 fills it in behind the same seam. |
| Serious | D09's forward-dated flags needed `valid_from`/`valid_to` on the contract *and* the schema — a contract change, which per CONTRIBUTING.md means every consumer plus the TypeScript mirror, on a single-day sprint. | **Both columns added to D01's contract and migration**, nullable. |
| Serious | **D10 contradicted its own "no new features" rule** and held three code tasks plus three rehearsals, failure drills and the impact presentation, on the day before the finale. | **Push notifications and geofencing (S16, S17) cut to Track B as B6a.** D09 takes the SOS screen work; defect 35 moves forward to D01. **D10 now holds no feature work at all**, which also gives earlier sprints somewhere to overflow. |
| Serious | D05 was under-scoped at one day. | Its independence check is **pre-declared as the first cut**, with a named destination. |
| Serious | The local OSRM graph was unscheduled work sitting inside D06 — the compose service exists, the multi-gigabyte graph does not. | Moved to §9 background work, to be built during D01–D02. |

Six smaller fixes: the `as_of` parameter threaded from D01; a Bengali-glyph font named as a D08 task;
the native-speaker reviewer moved to §9 as a scheduled human dependency; `route_service._get_regional_risk()`
marked for deletion in D06 to prevent double-counting the chronic layer; one source of truth for
expiry stated in D02; and **"every previous walkthrough still passes" added as a handoff gate** — the
regression check that would have caught the `public.users` breakage.

**No feature was cut from the demo and the 24 October date did not move.** The coverage table was
re-verified after the changes.

## Consequences

**Arafat was not consulted.** Plan §2 gives the baton holder authority over a sprint's scope, not
over the plan's sequence, so this override is recorded here rather than left to be discovered in a
diff. That is the whole purpose of this file. The failure mode being avoided is the one already in
the repository's history: S01 expanded from 11 checkboxes to 53 across three self-authored addenda,
each individually justified, with the result that *"S01 ✅ closed"* is measured against a scope its
own author widened.

**Phase exit criteria no longer gate progress before 24 October.** They were the real milestones in
a nine-month plan. Until the finale, the demo script in `DEMO_PLAN.md` §2 is the milestone.

**Debt is deferred, not cancelled.** This is the load-bearing claim of the decision and the coverage
table is how it is kept honest. If an item cannot be found in either track, the reordering has a
hole and should be treated as a defect in this ADR.

**Schedule risk is real and accepted.** The demo track compresses roughly 130 checkboxes into 17
days. The original estimate of *"one sprint ≈ 3–6 Claude Code sessions, roughly a week of part-time
work"* assumed a throughput that coding agents change; that assumption is the entire basis for
believing this is achievable, and it is an assumption, not a measurement. The mitigation is the
seeded 200-flag fixture built in `D02`: it makes the scoring, decay, routing and explanation layers
demonstrable **without live ingestion**, so a slip in `D04`/`D05` degrades the demo rather than
ending it.

**One decision is still open and blocks `D07`:** the reasoning layer for image analysis —
local-only, local plus Claude vision, or Claude-only. `PROGRESS.md` records it as deliberately
deferred pending a conversation between Arafat and Nakib. It cannot stay deferred past `D07`.

## Alternatives considered

| Alternative | Rejected because |
|---|---|
| Follow `IMPLEMENTATION_PLAN.md` as written | Arrives at the finale with 0 of 8 agents and nothing from the concept document. |
| Aggressively cut features to a minimal slice | Rejected by the owner. Coding agents lower the cost of breadth, so the binding constraint is sequencing, not feature count. |
| Abandon the plan; build demo-only throwaway code | Discards the 41-defect register and the ethical invariants, both of which are genuine assets and both of which judges are likely to probe. |
| Keep the plan and extend the deadline | Not available. The finale date is external. |
