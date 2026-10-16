# Device walkthroughs

One file per demo sprint: `D01.md` … `D09.md`, then `FINALE.md`.

**Plus Track B, as it lands:** **[`GUARDIAN.md`](GUARDIAN.md)** is the live one — background geofencing, shout-to-SOS and shake-to-SOS, tested **entirely from the phone with no terminal**. `B6a.md` and `B8.md` describe the first reading of those two backlog items and are superseded in part; each says so at the top. These follow
the same rules with one difference stated at the top of each — **they are not yet signed off on a
device**, because both need a development build that this project has never made. Expo Go cannot
receive Android push (removed in SDK 53) and cannot load a native module like
`expo-speech-recognition`. `B6a.md` is therefore split so **Part 1 runs on Expo Go today** and only
delivery waits for the build. Track B walkthroughs are **not part of the finale** — nothing in the
demo script depends on them.

**Journey Guardian lands as `JG1.md` ... `JG7.md`**, one per phase, written as each phase is
finished. The phases are in [`../../JOURNEY_GUARDIAN.md`](../../JOURNEY_GUARDIAN.md) and indexed in
`DEMO_PLAN.md` §6. **Three exist — [`JG1.md`](JG1.md), [`JG2.md`](JG2.md) and [`JG3.md`](JG3.md) —
and the scope stops there before the finale**; JG4–JG7 should not be created ahead of the work,
because a walkthrough describes what was built, so writing it first guarantees it describes
something else.

| | Status |
|---|---|
| `JG1.md` | Signed off 15 Oct 2026 |
| `JG2.md` | Signed off 15 Oct 2026, **with step 9 recorded as failing** — the lock-screen button is usually not drawn, and the journey card answers instead |
| `JG3.md` | Signed off 16 Oct 2026 — guardian email reaches a real inbox. Steps B10–B11 were retired after the run: the rung that mailed every contact was removed |

**A walkthrough is a play-script you run on a phone, as the user, with no knowledge of the code.**
It is written by the sprint owner, at the end of the sprint, in the same commit as the work, and the
owner must have actually run it on a real device before pushing. `DEMO_PLAN.md` §0 makes this a
Prototype Gate item.

## Why these exist

Because of a specific failure: build everything, wire the interface last, and arrive at the demo
with a great deal working and nothing to point at. Work that is invisible on the device is
indistinguishable from work that does not exist.

A walkthrough forces the question *"what can I show tonight?"* into the sprint, where it can still
change what gets built, instead of on the 23rd, where it cannot.

They also compound. `FINALE.md` is **assembled** from D01–D09, not written from scratch under
pressure.

## Rules

1. **Write it for someone who has never seen the code.** Tap targets, screen names, literal strings
   to type. Not "create a flag" — *"tap the + button, bottom right."*
2. **Every step has an expected result.** If you cannot state what should appear, the step is not
   finished.
3. **If a step does not work, it goes under Rough edges, not into the steps.** A walkthrough that
   lies is worse than none, because the next person trusts it.
4. **Run it on a device before you push.** Emulator is not the gate; the phone is.
5. **State the fallback.** For every step that depends on the network, an LLM call, or a scraper, say
   what to do when it fails. This is what makes D10 cheap.
6. **Keep the previous walkthroughs passing.** If your sprint breaks `D02.md`, fix it or update it —
   same commit. These are the regression suite that matters, because they are the demo.

## Template

Copy this.

```markdown
# D<nn> — <what this sprint made showable>

**Ran on:** <device / OS> · **By:** <name> · **Date:** <YYYY-MM-DD> · **Takes:** <n> minutes

## What this proves
One or two sentences. Which demo beat in DEMO_PLAN.md §2 this covers, and what a judge would
conclude from watching it.

## Preconditions
- [ ] `.\scripts\run.ps1` is up; `/health` returns 200
- [ ] `./scripts/seed.sh --fresh` has been run
- [ ] `RISK_SURFACE_IMPL=<seeded|db>`
- [ ] Signed in as <account>
- [ ] <anything else: a cached ingestion run, a staged photo, a specific fixture>

## Steps

| # | Do this | You should see |
|---|---|---|
| 1 | Open the app. Wait for the splash to clear. | The map, centred on Dhaka. |
| 2 | … | … |

## Rough edges
What is visibly wrong, ugly, or slow, and whether it is scheduled. Be specific — "markers are grey"
not "styling needs work". An honest list here is what stops the same bug being rediscovered three
sprints later.

## Fallback if it fails live
Per fragile step: what to switch, what to say, what to show instead.

## Numbers
Any measurement this sprint produced (accuracy, latency, precision, counts). D10 collects these for
Q&A, so record them here even if they are unflattering.
```
