# `app/routing/` — conventions

Route generation, scoring and explanation. Built in D06 from S12, S13, and defects 6, 7,
8, 10 and 11.

---

## The five rules

**1. One scale. `safety_score`, 0–100, higher is safer.**

There is no `crime_score`, no 0–10 variant, no percentage. Defect 11 existed because there
were three scales — a 0–10 `RouteSegment.crime_score`, a 0–100 `safety_score`, and a UI
rendering the latter as `58.3% Safe` — and no two agreed on what a number meant. If you
need the inverse, write `100 - safety_score` at the point of use and do not name it.

The one exception is the request field `max_crime_score`, which is a public API parameter
that predates the rule. It is documented as a ceiling on `100 - safety_score` and
honoured; it is not a second scale, it is the same scale read backwards. Do not add more.

**2. Risk arrives through `RiskSurface`. Never query a table here.**

`flags_near_path` is the method; both surfaces implement it. This is what makes
`RISK_SURFACE_IMPL=seeded` work with zero changes in this package — S12's check, and the
offline demo path D10's failure drills switch to. A `select()` in this directory is a bug
even if it returns the right answer.

**3. Score with `effective_severity`, never with `severity_now`.**

```python
from app.scoring.decay import effective_severity
penalty = effective_severity(severity_now=flag.severity_now, confidence=flag.confidence)
```

`severity_now` is how bad the event is. `confidence` is how sure we are it happened —
1.0 confirmed, 0.6 unconfirmed. Using the raw value makes a single-source rumour bend a
route exactly as hard as a fact three publishers agree on, and D05's entire verification
tier becomes decoration. **The failure is invisible**: routes still look plausible. There
is a test asserting an unconfirmed flag moves a score less than an identical confirmed one.

**4. Flag prose comes from `app/policy/framing.py`. This package quotes, it does not
write.**

`explain.py` assembles sentences from `RiskFlag.mobility_statement` plus counting words.
It must never compose a description of a place or an event itself. The only prose this
package owns is connective tissue — *avoids*, *passes*, *minutes longer*, *sources* — and
`assert_mobility_safe` runs on the finished string, because concatenation is where a banned
term could be assembled from individually safe parts.

**5. No LLM in the request path.**

A route request sits in front of someone deciding which way to walk home. An LLM call adds
a p99 in seconds, a failure mode that returns no explanation, and a sentence nobody
reviewed. Explanations are templates, in `explain.py`, reviewable in one file.

---

## Tunables live in `settings`, not in functions

S12: *"a composite that is documented and tunable in settings, not a magic constant."* The
knobs are `ROUTE_CORRIDOR_RADIUS_M`, `ROUTE_SAFETY_WEIGHT`, `ROUTE_PENALTY_FALLOFF` and
`ROUTE_DETOUR_TOLERANCE`, each with its reasoning in `config.py` and the arithmetic in
`scorer.py`. A literal float in the middle of a scoring function is a value nobody can
find, review or change.

---

## Things already decided, so you do not have to re-derive them

- **Penalties combine with geometric falloff, not by summing or averaging.** Summing makes
  every long route score zero; averaging lets one severe flag be diluted by a dozen
  trivial ones. See `_combine`.
- **The duration axis is relative to the fastest candidate**, not absolute. "A long
  journey" has no fixed meaning — 40 minutes is ordinary across Dhaka and absurd for three
  streets. This is why `composite_score` cannot be computed inside `score_path`: a route
  does not know whether it is the fastest until the alternatives exist.
- **A filter that rejects every route is not applied.** `apply_filters` returns everything
  with `filter_relaxed=True` instead, and the caller tells the user. Answering "no
  acceptable route" to someone asking how to get home is the worst available answer.
- **`route_service._get_regional_risk()` was deleted, not fixed.** D02 moved the same
  police statistics into the surface as chronic flags, so applying them here again was a
  double count — and it independently took `max()` over overlapping police units including
  the ranges that contain them, so every point in Dhaka scored 100.0 from `Dhaka Range`
  rather than 58.9 from `DMP`.
- **The walking profile answers from a `car.lua` graph.** It will route a pedestrian down
  a flyover. `osrm.WALKING_GRAPH_CAVEAT` says so and logs on every `foot` request; the fix
  is a second graph and it is not demo-critical.
