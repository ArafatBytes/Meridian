# Crime-vision eval set

A labelled image set and a baseline, so that changes to the AI pipeline can be
**measured** instead of guessed at.

```bash
# from the repo root
docker compose exec api python scripts/eval_crime_vision.py              # run
docker compose exec api python scripts/eval_crime_vision.py --save-baseline
docker compose exec api python scripts/eval_crime_vision.py --compare
```

---

## Why this exists before any pipeline change

"Detection is poor" was an accurate impression but an unmeasurable one. Without
a baseline there is no way to tell an improvement from a regression, and the
pipeline has four stages that can each be individually right or wrong.

The harness also prints a **capability report** — which object signals the
decision engine scores against versus which YOLOv9c can physically emit. On the
current build that reads:

```
21 object signals wanted, 10 reachable, 11 IMPOSSIBLE
  gun, blood, broken window, damaged property, graffiti,
  crowbar, spray paint, money, door, window, building
```

So a `vandalism` verdict is **structurally unreachable** — its cross-validation
gate requires damage evidence and all three forms are outside COCO's 80 classes.
Keep that in view when reading the numbers: some failures are not tuning, they
are the vocabulary.

---

## Adding images

1. Put the file in `images/`.
2. Add a row to `manifest.csv`.

```csv
image,expected,scene,source,notes
dhaka-street-night-01.jpg,none,street,own photo,hard negative: crowd at night
mirpur-snatch-01.jpg,theft,street,own photo,phone snatch, 2 people
```

| Column | Meaning |
|---|---|
| `image` | filename inside `images/` |
| `expected` | `theft` `assault` `harassment` `vandalism` `burglary` `robbery` `none` |
| `scene` | free text — `street`, `alley`, `market`, `indoor`, `transport` |
| `source` | provenance and licence. **Required.** `own photo`, `CC-BY <url>`, … |
| `notes` | what a human sees. Especially *why* a hard negative is hard. |

Images are committed. An eval set that is not shared is not a baseline — both
machines must score identically.

---

## What to collect, and in what proportions

This is where your judgement matters more than any code I can write.

### Roughly half should be negatives

A model that answers "no crime" to everything scores 50% on a balanced set and
90% on a set that is 90% negatives. Skew the set and you will flatter whatever
you build next.

### Hard negatives are the most valuable images in the set

Ordinary scenes that *look* alarming are what produce false positives, and a
false "crime detected" on a neighbourhood is a real harm — it is the same
concern the concept document raises in §9 about never labelling areas unfairly.

Collect specifically:

- a crowd at night (dense, poorly lit, entirely normal)
- construction with tools and debris
- people running — for a bus, in sport, in rain
- a market at dusk, lots of bags and hands
- someone crouching to fix a bike or tie a shoe
- two people arguing animatedly but harmlessly
- a kitchen or street-food stall with knives in plain view

### Positives: at least 10 per crime type you care about

Below ten, per-class precision and recall are noise. If you cannot reach ten for
a class, that is itself a finding — say so in the manifest and treat that class
as unmeasured rather than reporting a number for it.

### Bangladesh scenes, not stock photos

The scene classifier is CLIP zero-shot against a vocabulary including
`dark alley`, `public transport`, `residential area`. Whether those labels mean
anything for a Dhaka street, a CNG-filled intersection or a Mirpur footbridge is
exactly what this set should answer. A set of US suburban photos would measure
the wrong thing.

### Privacy

Do not add identifiable faces without consent. Blur them if needed — it will
not affect YOLO person detection, and if it does affect a verdict, that is worth
knowing. Staged photos of yourselves are fine and are often the fastest way to
get positives.

---

## Reading the output

Per class it reports precision, recall and F1, plus a confusion matrix and a
**failure breakdown** — which stage was responsible:

```
no_objects_detected        YOLO found nothing; never reached pose/scene/fusion
pose_missing               YOLO found people, MediaPipe returned no pose
validation_failed          fusion scored candidates, none passed its gate
wrong_class                a crime was detected, the wrong one
```

That breakdown is the point. "47% recall" is not actionable; "31 of 44 misses
never got past YOLO" is.

---

## Honest limits

- Scoring is **single-label**. A photo that is both theft and assault counts
  only against its `expected` value.
- `processing_time` is measured on CPU inside the container and is not a
  statement about production latency.
- The set will be small for a long time. Treat differences of a point or two as
  noise and look at the failure breakdown instead.
