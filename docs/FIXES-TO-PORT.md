# Fixes to port off `feature/test-v`

`feature/test-v` was cut to shoot the demo video and **is not going to be merged.** Filming
exercised paths nobody had driven end to end before, and seven genuine defects fell out of it.
This file is the record of those seven, so they can be reapplied to `develop` without dragging
the demo scaffolding along.

Range audited: `5cdd9fa..725262c` (`git diff 5cdd9fa^..HEAD`).

Everything below was read off the diff and checked against the code at `725262c`, not recalled.

> **Status: all seven applied to `develop` on 2026-10-18.** None of the nine target files had
> diverged since the branch point, so each applied without conflict. Verified: `tsc --noEmit`
> clean, 557/557 frontend tests, 165/165 backend tests outside `tests/invariants`. The
> DB-backed invariants (fix 6) could not be run — Docker was not up — so they are checked
> against `is_confirmable` directly rather than against the table; **run
> `pytest tests/invariants` once the stack is up.** The `CHECK_IN_WINDOW` demo value was not
> ported and `deadline.py` is untouched.

## Contents

| # | Fix | Files | Severity | Risk to port |
|---|---|---|---|---|
| 1 | `addFeatureAt` overwrites instead of inserting | `react-native-maps` patch, `package.json` | **Critical** | Medium |
| 2 | Circle keys remount and churn the feature list | `MapScreen.tsx` | **Critical** | Low |
| 3 | Route lines coloured by score, so alternatives were indistinguishable | `MapScreen.tsx` | High | Low |
| 4 | A typed start was silently replaced by the GPS | `suggest.ts`, `MapScreen.tsx` | **Critical** | Medium |
| 5 | Forward geocode was a world query | `nominatim.py` | High | Low |
| 6 | Two stale invariants rejected single-source confirmation | 2 invariant tests | High | Low |
| 7 | The news screen listed rows no publisher published | `news.ts`, `NewsScreen.tsx`, `RiskFlagSheet.tsx` | Medium | Low |

Fixes 1, 2 and 3 are one bug family — the map overlay. Port them together or not at all; 2 and 3
are only safe *because* of each other.

---

## 1 · `addFeatureAt` overwrites instead of inserting

**Files:** `frontend/patches/react-native-maps+1.27.2.patch` (new),
`frontend/package.json` (`postinstall: patch-package`, `patch-package` devDependency)

This is an upstream bug in `react-native-maps@1.27.2`, not in our code.

### What is wrong

`MapView.java:addFeatureAt(View, int)` padded the list and then **overwrote** the slot:

```java
while (features.size() <= index) { features.add(null); }
features.set(index, mapFeature);
```

React's `addView(child, index)` means *insert at index, shift the rest right.* `set` replaces.
`removeFeatureAt` meanwhile removes with `features.remove(index)`, which shifts **left**. The two
operations therefore disagree about every index from the first change onwards.

### Before

An overwritten `MapFeature` is still drawn on the `GoogleMap`, but `MapView` has dropped its only
reference to it, so `removeFeatureAt` can never reach it again. Polylines, circles and markers
accumulate on the map and **cannot be removed by any means from JavaScript** — including
unmounting the component that created them. Observed: a deselected route stayed painted, and
survived leaving route mode entirely.

### After

```java
features.add(index, mapFeature);
```

`index <= features.size()` is guaranteed at that point — the guard above diverts anything larger
to `savedFeatures` — so the insert is always legal and the padding loop is unnecessary.

### Drawbacks

- **A patch against `node_modules` is a maintenance liability.** It is pinned to `1.27.2` by
  filename; a version bump silently stops applying it (`patch-package` warns, it does not fail
  the install). Any upgrade needs the patch re-cut and the map overlay re-tested.
- `postinstall` now runs on every `npm install`, including in CI. If CI installs with
  `--ignore-scripts`, the patch does not apply and fixes 2 and 3 stop being sufficient.
- It should go upstream. Worth filing against `react-native-maps` with the `set`/`remove`
  asymmetry spelled out; we would then carry the patch only until a release lands.

---

## 2 · Circle keys forced a remount on every route tab tap

**File:** `frontend/src/screens/Map/MapScreen.tsx:1738`

### What is wrong

The route-flag circles were keyed on their own selection state:

```tsx
key={`route-flag-${flag.flag_id}-${onSelected ? 'on' : 'off'}`}
```

A changing key is a remount, and a remount of a map child is a **remove plus an add** on
`MapView`'s feature list — which is exactly the operation fix 1 shows that list cannot survive.
Worse, the circles sit *after* the route polylines in that list, so churning them corrupted the
indices the polylines were holding.

The key carried the selection state in order to force the `lineDashPattern` to clear, because a
dash pattern cannot be cleared on a live polyline (see fix 3).

### Before

Every tap on a route tab remounted every route-flag circle, shifted the feature list underneath
the route polylines, and orphaned polylines onto the `GoogleMap` with nothing in JavaScript still
referencing them. **That is the root cause of "the previously selected route stays coloured on the
map", and of its surviving the exit from routing mode.**

### After

```tsx
key={`route-flag-${flag.flag_id}`}
```

Stable key, no remount. The dash pattern goes with it — the only thing it was remounting *for* —
and the selected/unselected distinction is carried by `strokeWidth` (3 vs 1), stroke alpha
(`CC` vs `44`) and fill alpha (`2E` vs `08`), all three of which apply directly to a live circle.

### Drawbacks

- The unselected circles are fainter than before (`44`/`08` against `55`/`0D`). On a pale basemap
  in daylight that is a real legibility cost; it was tuned by eye on a Pixel 7 Pro and has not
  been checked on a low-brightness or washed-out screen.
- Dashed outlines were a second, non-colour channel for "not selected". Losing it makes the
  distinction purely one of weight and opacity, which is weaker for anyone with low contrast
  sensitivity.

---

## 3 · Route lines were coloured by safety score

**File:** `frontend/src/screens/Map/MapScreen.tsx:1674` (and the `safetyColour` import at the top)

### What is wrong

D06 made the polylines read `safetyColour(route.safety_score, t)` so that the line and the
comparison card could not disagree about what a score looks like. The reasoning was sound and the
result was unusable: `safetyColour` **buckets**, so two alternatives scoring 65 and 63 drew in the
identical colour. Three returned routes looked like one line.

### Before

- Colour answered *how safe is this route* — a question the card already answers in words and
  numbers, directly beside it.
- Colour did **not** answer *which line am I looking at*, which is the only question the map is in
  a position to answer.
- `lineDashPattern={isSelected ? undefined : [10, 5]}` was the compensation, and it does not work:
  `MapPolyline.applyPattern` opens with `if (patternValues == null) return;`, so a dash pattern can
  be **set** on a live polyline and never **cleared**. That is what drove the remount in fix 2.
  (Separately, the default `lineCap` is `RoundCap` and `applyPattern` emits `Dot()` rather than
  `Dash()` for a round cap, so `[10, 5]` was drawing 5px-spaced dots and discarding the 10.)

### After

Colour and width carry the **selection**, and nothing else:

```tsx
strokeColor={isSelected ? t.brand : withAlpha(t.textSoft, '8C')}
strokeWidth={isSelected ? 7 : 3}
```

`lineDashPattern` is gone deliberately. The followed route's trimmed halves use `t.brand` too
(faint behind, full strength ahead). `safetyColour` stays exported from `RouteComparisonCard` and
the card remains the only thing that states a score.

### Drawbacks

- **The map no longer shows safety at a glance.** You now have to read the card to know which of
  the drawn lines is the safe one. That is a genuine loss and it is the right trade only because
  the card is on screen whenever routes are.
- Flag circles still colour by severity band. Two colour systems coexist on one map (brand = which
  line, danger = where the risk is). They answer different questions, but it is a thing a new
  reader has to be told.
- The reason `lineDashPattern` is absent is invisible at the call site. It is documented in the
  comment block above the polylines; delete that comment and someone re-adds the prop.

---

## 4 · A typed start was silently swapped for the GPS

**Files:** `frontend/src/features/search/suggest.ts` (`isUnboundPlace`, new),
`frontend/src/screens/Map/MapScreen.tsx` (lines 536, 553, 676, 748, and four call sites)

This is the most serious non-crash defect of the seven, because it produced a **confident wrong
answer** rather than a failure.

### What is wrong

The start field holds two things that look identical on screen and mean opposite things: text a
person typed, and a place they picked from the suggestion list. Only the second carries a
coordinate. `sourceLocation === null` is the field's way of saying *"use the GPS"* — correct while
the field reads `My Location`, a lie the moment someone types over it.

Every route call treated both as the GPS:

```tsx
calculateRouteTo(sourceLocation || currentLocation, loc);   // and inside: start || currentLocation
```

### Before

Type `Rampura` in the start field, do not pick the suggestion, then choose a destination. The app
routes from **wherever the phone physically is**, draws that route, scores it against the risk
surface, shows an ETA for it — and the start box reads `Rampura` throughout. Nothing errors. The
answer is simply to a different question than the one on screen. In use this is worse than an
error, because an error can be seen.

The destination had the mirror-image bug with a quieter symptom: an unbound destination means
`calculateRouteTo` is never reached, so typing `Gulshan 2` and picking nothing left the app inert,
and then picking a *start* ran `if (destination) …` against a null and returned silently.

### After

A predicate names the state, with its own unit tests:

```ts
export function isUnboundPlace(args: { query: string; location: unknown | null }): boolean {
  if (args.location) return false;
  const trimmed = args.query.trim();
  return trimmed.length > 0 && trimmed !== NOT_A_PLACE;
}
```

Four things hang off it:

1. **`startPoint()`** — three cases instead of two: a picked place is used; `My Location` means the
   GPS; typed text is **geocoded**, binds the coordinate, and rewrites the field to the resolved
   name. If it resolves to nothing it shows a dialog and returns `null`. Every one of the four
   route call sites now goes through it (suggestion picked, map tap, profile switch, destination
   chosen).
2. **The GPS fallback is structurally unavailable** while the start is unbound:
   `start || (sourceUnbound ? null : currentLocation)`. This is the line whose absence caused the
   defect; making it structural means a future call site cannot forget the convention.
3. **A stale route is cleared** when either field goes unbound, so the lines on screen never
   contradict the words in the box.
4. **The state is visible:** a hollow warn-coloured dot instead of a filled one, `Pick a start from
   the list` with a **Use my location** action, and `Pick a destination from the list, or tap the
   map`.

`selectDestination` also dropped its `!currentLocation` guard — with a start typed or picked, a map
tap is a complete instruction without the GPS having arrived.

### Drawbacks

- **`startPoint()` makes a network call on a path that used to be synchronous.** Picking a
  destination with typed text in the start field now waits on `/geo/search` with no spinner on that
  field. On a slow connection the tap appears to do nothing for a moment.
- It **auto-picks the first geocoder result** and rewrites the field to match. That is a guess
  presented as a resolution. It is visible (the field changes) and correctable, but it is a guess.
- The four `void startPoint().then(…)` call sites are unsequenced. Two fast taps can run two
  resolutions concurrently and the later `setCalculatedRoutes` wins by timing. Not observed in
  filming, but it is unguarded — worth an in-flight ref if this is ported.
- `isUnboundPlace` takes `location: unknown | null` so the helper stays free of the `Location`
  type. It costs type safety at the boundary for no real gain; tighten it on port.

---

## 5 · Forward geocoding was a world query

**File:** `backend/app/geo/nominatim.py:65`, `:82`, `:181-189`

### What is wrong

`search()` sent `q` to Nominatim with no geographic restriction at all.

### Before

Typing `Rampura` offered **Rampura, India** above Rampura in Dhaka, because the Indian one is the
more prominent place and Nominatim ranks by prominence when nothing says otherwise. `Seoul` was
reachable in the destination box.

This is not a cosmetic ranking problem. The destination feeds straight into `/routes/calculate`,
which scores a path against the **Dhaka** risk surface — so a cross-border destination yields a
route with zero flags on it for entirely the wrong reason, and the app reports it as safe.

### After

```python
"countrycodes": "bd",
"viewbox": "90.30,23.66,90.52,23.92",
"bounded": 0,
```

- `countrycodes=bd` is a hard filter. Meridian is a Bangladesh product; there is no case where a
  destination outside the country is the answer, so the restriction belongs on the request rather
  than on the ranking.
- The viewbox is used **unbounded** — with `bounded=0` it boosts greater Dhaka and still returns
  Chattogram or Sylhet when that is what was asked for. Bounded would have been wrong: travel
  outside Dhaka is a real case, and silently returning nothing for Cox's Bazar is a worse failure
  than ranking it second.
- The cache key became `search:bd:{q}`. Entries written before the change hold world results for a
  Bangladesh query and would otherwise outlive it by `NOMINATIM_CACHE_TTL_SECONDS`.

### Drawbacks

- The viewbox is a hardcoded literal. It encodes "this product is about Dhaka" in a geocoding
  module, where a second city would have to find it. Fine today, a rename away from being wrong.
- It covers roughly Tongi/Uttara down to Jatrabari/Keraniganj, chosen to match where the risk
  surface actually has flags. If the surface grows, this box is a thing someone must remember to
  grow with it.
- `countrycodes` closes a legitimate edge case outright: a cross-border journey can no longer be
  planned, even to say "no route".
- Only `search` is biased. `reverse` takes coordinates and needs none, but if another forward
  endpoint is added it will not inherit this.

---

## 6 · Two invariants restated rules that had been replaced

**Files:** `backend/tests/invariants/test_confirmation_requires_a_vetted_source.py:466`,
`backend/tests/invariants/test_surfaces_agree.py:243`

### What is wrong

`e7c4fa3` (2026-10-16, `20261016150000__a_vetted_newsroom_is_confirmation.sql`) made **one vetted
newsroom** sufficient for `status = 'confirmed'`, and renamed the DB constraint to
`risk_flags_confirmed_cites_a_source` with `source_count >= 1`. Two assertions were not updated
with it:

- `test_surfaces_agree.py` asserted `flag.source_count >= 2`, claiming to restate the schema CHECK
  — which by then read `>= 1`.
- `test_confirmation_requires_a_vetted_source.py` asserted two independent publishers over the
  whole table, contradicting the policy **the file is named after**.

### Before

Both passed, for one reason only: nothing confirmed on a single source had yet been served. The
first real Prothom Alo flag from live ingestion broke both. **A correct surface was being rejected
by a rule that no longer existed** — and it took a day and live news to surface, which is the
characteristic failure of an invariant that duplicates a rule instead of calling it.

### After

- `test_surfaces_agree.py` restates the schema and nothing more: `flag.source_count >= 1`.
- `test_confirmation_requires_a_vetted_source.py` calls the policy instead of re-deriving it:
  `is_confirmable(ids, minimum=settings.MIN_SOURCES_FOR_CONFIRMED)`, which is true on **either**
  ground — a vetted publisher, or `MIN_SOURCES_FOR_CONFIRMED` independent ones. The failure message
  changed with it ("neither cite a vetted publisher nor are corroborated by two independent ones").

The division of labour is now explicit: the schema test restates the CHECK; the policy test asks
`is_confirmable`. Neither copies the other's rule.

### Drawbacks

- The policy test now **shares an implementation with the code under test**. If `is_confirmable` is
  itself wrong, the invariant agrees with it. That is the accepted cost of not having two
  divergent copies, and it is why `is_confirmable` carries its own doctests — but it is a real
  reduction in independence and should be said out loud to a judge who asks.
- `test_surfaces_agree.py`'s assertion is now nearly vacuous: `source_count >= 1` is almost implied
  by `risk_flags_sources_match_count`. It is kept because it restates a named constraint at the
  point where the data is read.

### Adjacent, not fixed

`backend/migrations/supabase/` still refers to `risk_flags_confirmed_needs_two_sources` in comments
(`B13_APPLY_IN_SUPABASE.sql:109`, `:455`, `S30_APPLY_IN_SUPABASE.sql:207`). They are comments on
`community_clusters`, not a live constraint on `risk_flags`, so nothing is broken — but they name a
constraint that no longer exists and will mislead the next reader of the Supabase mirror.

---

## 7 · The news screen listed rows no publisher published

**Files:** `frontend/src/features/risk/news.ts` (`isNotFromThePress`, new),
`frontend/src/screens/Map/NewsScreen.tsx`, `frontend/src/components/RiskFlagSheet.tsx`

Two separate problems with one cause: the screen whose subject is *the press we read* was mixing
in things the press did not write.

### 7a · Seeded references were listed as articles

`newsFromFlags` skipped `isGeneratedPlaceholder` — fixture rows titled `Sample report …`. It did
not skip a **hand-written** fixture headline, which reads exactly like reporting but was published
by nobody and whose `sample:` link does not open.

**Before:** the list carried rows a reader would take for journalism, and the counter read
`n real of m · the rest is sample data` — honest at the time, but a ratio nobody can act on.

**After:** `isNotFromThePress(source) => !isWebLink(source.url)` — everything the seeder wrote,
not just the placeholders. The counter became
`{realCount} article(s) read from {n} outlet(s)`, and the footnote now says seeded flags and the
chronic layer are on the map with their own provenance on each flag.

`isGeneratedPlaceholder` is **kept**, because the two predicates answer different questions, and
there is a test that records the difference.

**Drawback:** this is where the `sample_` marking stops being load-bearing on screen. The old
guarantee was *a seeded day must not look like a busy day*; the replacement is that with no
articles the page is simply **empty**, which cannot be misread at all. `realCount` is kept as a
backstop so a non-web row slipping through reads as 0 rather than being counted silently. The
marking itself still exists everywhere else (`fixture.py` prefixes every generated publisher,
every seeded URL keeps the `sample:` scheme, each flag's sheet still shows its sources).

### 7b · Two `outletName` implementations disagreeing

`RiskFlagSheet.tsx` carried its own three-entry `OUTLET_NAMES` table with a raw-id fallback. The
shared `outletName` in `news.ts` maps nine publishers.

**Before:** a real Prothom Alo flag from live ingestion rendered as `prothom_alo` on the flag sheet
and as *Prothom Alo* on the news screen — in the same session.

**After:** the sheet imports the shared `outletName`. One implementation.

The local table existed deliberately, so that an unlisted id — `sample_jugantor` — showed raw and
kept a fixture visibly a fixture. That was the wrong trade: `sample_jugantor` on screen reads as a
bug rather than as a disclosure, and the marking is carried better by 7a (the news screen lists
only what a publisher published, and a `sample:` URL still does not open).

**Drawback:** a publisher id missing from the shared table now renders by its fallback rather than
being conspicuous on the sheet. Adding a source to `backend/app/ingestion/sources/__init__.py`
without adding it to `news.ts` is a mismatch nothing catches.

---

## Do **not** port

Demo scaffolding and demo-only edits, listed so nobody cherry-picks them by accident:

| Path | Why not |
|---|---|
| `backend/app/journeys/deadline.py` — `CHECK_IN_WINDOW` | **5 min → 1 min, for filming only.** The file says so, in a warning block. The product value is 5 minutes and the reasoning for it is unchanged underneath. Porting this quietly triples the escalation rate of the whole check-in ladder. |
| `backend/scripts/play_mock_track.py` | Mock-location driver over adb. Film kit. |
| `backend/scripts/arm_journey_checkin.py` | Forces the first rung of the ladder. Film kit — though its docstring is the best record we have of the heartbeat/leash arithmetic and the `journeys_leash_sane` bound, and is worth reading before anyone touches `_HEARTBEAT`. |
| `backend/scripts/export_route_track.py`, `capture_video_news.py`, `stage_video.py`, `verify_video_scenario.py` | Film kit. |
| `backend/scripts/seed_risk_flags.py` — `--fixture`, `--replay` | Added for the video scenario. Harmless, but it exists for one shoot. |
| `backend/data/video/*.gpx`, `backend/data/fixtures/video_scenario.json` | Film kit. |
| `backend/data/fixtures/live_replay.json` | Re-captured at 2026-10-17 for the shoot. Regenerate on `develop` with `python -m app.agents export-replay` rather than taking this one. |
| `docs/video/*` | Film kit. |

---

## Resolved loose end

`feature/test-v` left `ROUTE_LINE_SLOTS`, `NO_POINT` and `NO_LINE` in `MapScreen.tsx` with nothing
using them — the remains of an abandoned approach to fix 1: mount a fixed pool of eight polylines
for the life of the screen and swap their coordinates, so the feature list is never mutated at all.
Patching `MapView.java` solved it properly and the slots were never wired up. **They were deleted
rather than ported.**

Worth knowing that the approach existed. If the patch ever has to be dropped — a `react-native-maps`
upgrade, or a CI that installs with `--ignore-scripts` — a fixed slot pool is the fallback that
needs no native change.

---

## Why the patch survives a cloud build

Fix 1 only works if `patch-package` actually runs where the APK is built, which matters more now
that `eas.json` points release builds at the deployed backend. Checked on `develop`:

- `frontend/patches/react-native-maps+1.27.2.patch` is **tracked** and matched by no ignore rule,
  so EAS Build — which uploads the git repository — receives it.
- `patch-package` is in `devDependencies` and `postinstall` is in `scripts`.
- There is no `.easignore`, no `.npmrc`, and nothing sets `--ignore-scripts`, so `postinstall` runs
  on the EAS installer and the native source is patched before Gradle compiles it.

If a future build ships with overlays that cannot be removed, check these four things first.