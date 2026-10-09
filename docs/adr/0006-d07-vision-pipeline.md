# ADR 0006 — D07: crime detection from an image

| | |
|---|---|
| **Status** | **Accepted** — 2026-10-09, ahead of the 17 October deadline |
| **Date** | 2026-10-09 |
| **Decider** | Nakib (owner) |
| **Consulted** | Arafat, Ishraq — **approved.** |
| **Decides** | `DEMO_PLAN.md` §7.1, the reasoning layer for image analysis |
| **Affects** | D07 (Oct 18–19), defects 5, 13, 29, 30 |

---

## Recommendation

**Ask a vision-language model which cues are visible in the photo. Map those cues to a
category in our own code. Let the reporter confirm it.** Three tiers, all measured on
2026-10-09: Gemini Flash Lite at **≈2.0s**, a cached replay of the rehearsed photos, and a
local model on Nakib's GPU at **≈8–9s** for a photo it has not seen, with identical
abstention behaviour to Gemini's.

§7.1 as written offers "local-only, local plus Claude vision, or Claude-only". **All three
are unavailable or wrong** — there is no Anthropic key, and "local-only" as currently built
is the design that cannot work. The real question is narrower:

> Does the model **name a crime**, or **report cues** that our code turns into a proposal
> a human confirms?

This ADR proposes cues, with a cloud tier and a local tier behind one chain.

---

## Context

### Why the current design cannot work

The decision engine scores 21 object signals. YOLOv9c emits COCO's 80 classes, and **11 of
those 21 are not COCO classes at all**: gun, blood, broken window, damaged property,
graffiti, crowbar, spray paint, money, door, window, building.

A signal the detector cannot emit can never be scored. That is why `harassment`, `theft`
and `vandalism` are structurally unreachable — **no photograph produces them.** Adding
signals cannot fix a vocabulary gap. Training a detector that emits those 11 needs
thousands of labelled Bangladesh crime photos we do not have.

There is also a limit no model removes. A photo can show two people and a raised arm. It
cannot show intent, consent, who started it, or whether it is a film shoot. The current
design decides anyway and hides it behind arithmetic.

### A frozen VLM is state of the art, and prompting beats model choice

ASK-HINT (WACV 2026) trains nothing and scores **89.83% AUC** on UCF-Crime — ahead of the
best fine-tuned method (HiProbe-VAD, 88.91%) and the best prior training-free one (VERA,
86.55%). So "use a VLM" is the frontier, not a shortcut.

| Prompt style | UCF-Crime AUC | Unseen classes |
|---|---|---|
| Abstract — *"is this a crime?"* | 67.17% | 31.16% |
| **Grouped fine-grained visual cues** | **89.83%** | **61.03%** |

**Over 20 AUC points from prompt design alone**, same model, no training. Ask about shared
physical cues, not crime names: "physical confrontation" links assault and robbery. Cues
generalise; categories do not. Compressing the question set also reduces hallucination.

There is **no pretrained crime classifier to download** — Hugging Face has weapon object
detectors, and the main weapon dataset discarded its `blood` and `violence` labels during
cleaning.

### Our problem is easier than the research's

That literature is CCTV anomaly detection: a camera watching 24/7, nobody present. Ours is
**a person filing a report who took a photo and is standing right there**, with text, GPS
and a timestamp alongside. The model fills in a form; it does not reach a verdict.

---

## Measured results, 2026-10-09

Same prompt, the two seed images in `backend/data/eval/crime_vision/images/`, warm model. The
local column was re-measured later the same day over **six distinct images, each seen once** —
see the correction below for why that matters.

| | Gemini 3.5 Flash Lite | Local `qwen3-vl:4b-instruct` |
|---|---|---|
| **Mean — a photo not seen before** | **≈2.0s** | **≈8.2s** ⚠️ *corrected, see below* |
| Range | 1.16 – 2.42s | 7.95 – 8.51s |
| Repeat of the *same* photo | same | 3.65s — Ollama prompt-cache hit |
| Abstained correctly | 2 of 2 | **2 of 2** |
| Detected a true positive | **untested** | **untested** |
| `people_count` | 2 and 4 | **2 and 4 — identical** |
| Cold model load | — | 5.2s, one-off |
| Network needed | yes | **none** |
| Safety filter | **yes, cannot disable** | none |

### ⚠️ Correction, 2026-10-09 — the first local figure measured a cache hit

The **2.61s** originally recorded here was taken by calling the *same* image repeatedly.
Ollama caches the prompt, and an identical image plus identical text is a cache hit: prefill
drops to ~50ms and the vision encoder never re-runs. **A judge's new photo is a cache miss.**

Re-measured against six distinct images, each seen once, over the real call shape:

| Component | Cost | Can it be reduced? |
|---|---|---|
| Vision-encoder prefill | **≈4.8s** (~1,100 image tokens at ~232 tok/s) | **No.** Tested at 1024 / 768 / 512 / 384px — prompt stays ~1,150 tokens at every size, so resizing does not help. The ~1,100 tokens *are* the image |
| Constrained decode | **≈2.8s** (103 tokens at ~36 tok/s) | Marginally, by shortening the output. Strict grammar costs ~35% of decode rate against 53 tok/s unconstrained |
| **Total, new photo** | **≈8.2s** | |

Our real cue prompt is ~250 tokens of text rather than the ~60 used in this probe, so budget
**≈9s** in the app.

**This does not change the decision — it sharpens it.** Gemini is now **4× faster** than local
rather than 1.4×, which confirms cloud-first ordering, and it makes the **replay tier matter
much more**: the rehearsed photos are exactly the ones that must not cost nine seconds on
stage. What changes is the narration, and the demo-day table below.

### Two call-shape findings that are not optional

**`response_format: json_object` does not work on Ollama for this schema.** It returned 48
tokens with required fields missing and `scene: "football stadium"` — free text where the enum
allows four values. **Strict `json_schema` is required, not preferred**, and it is what
`chat.completions.parse()` already sends. Verified honoured exactly, every run, on both
providers.

**Use `127.0.0.1`, not `localhost`, and reuse the connection.** A fresh connection per call to
`localhost` on Windows added a flat **2.3s** to every request, independent of payload size —
IPv6 resolution against a service bound to IPv4. Switching to `127.0.0.1` with a reused client
took the client-side gap to **0.00s**. From the API container the host is `host.docker.internal`,
which needs the same check before the numbers above are trusted in Docker.

The abstention test is the ambiguous image: two men nearly touching, one shouting. Both
models answered `physical_confrontation: no`.

- Gemini: *"Two men in suits stand in what appears to be a stadium with one pointing forward while shouting."*
- Local: *"Two men in suits are gesturing and shouting at each other during a sports event."*

The local phrasing is slightly stronger, but the cue answers — which are what our code
consumes — match.

### ⚠️ What these numbers do NOT show

**Both seed images are benign, so "2 of 2" measures abstention only — not detection.**
Neither model has been shown a photo that *should* flag a cue, so we have no evidence either
one recognises a real confrontation. The latency and the plumbing are settled; the accuracy
is not.

The one available hint points the wrong way for the local model: it read the ambiguous photo
as *"shouting at each other"* where Gemini said *"one pointing forward while shouting"*. A
stronger reading helps on a true positive and starts a false accusation on a benign one.

**This is what the 30–40 image eval set is for, and why it is the critical path** rather
than a nicety. Until it exists, the local tier is unproven for detection and the chain below
is ordered accordingly.

### ⚠️ Gemini's safety filter cannot be turned off through our SDK

Google's moderation guide says to disable the safety filters, because a moderation tool must
see what it is checking. **We cannot.** `safety_settings` is rejected in both documented
forms through the OpenAI-compatible endpoint:

```
400 INVALID_ARGUMENT  Unknown name "safety_settings" at 'extra_body.google'
400 INVALID_ARGUMENT  Unknown name "google"
```

So the cloud tier runs at default filter level and **may refuse a staged violent photo**.
Unmeasured, because we have no violent test images yet. **The local tier has no filter, so
the chain below is the mitigation** — no extra provider needed.

### ⚠️ Two Ollama traps that each cost a full experiment

| Trap | Symptom | Fix |
|---|---|---|
| The bare `qwen3-vl:4b` tag is the **thinking** build. Spends 300–600 hidden reasoning tokens per call; `think:false`, `/no_think` and `reasoning_effort` are all accepted and ignored | **10.7s** per call, sometimes empty `content` | Use **`qwen3-vl:4b-instruct-q4_K_M`**. `ollama show` confirms no `thinking` capability. Same size, same quantisation, **4× faster** |
| Context defaults to **131072**, whose KV cache wants ~20 GB, so Ollama puts **83% of the model on the CPU** | **36s** per call | Pin `OLLAMA_CONTEXT_LENGTH=8192`. Our prompt is ~1,300 tokens |

The context fix must be **explicit, not a GUI setting** — a setting on one laptop means a
fresh clone silently hits 36s with no clue why.

---

## Decision

### The pipeline

```
photo + report text + GPS
  → resize to ~1024px, strip EXIF            privacy; GPS kept separately
  → [gate] is the frame empty?               → yes: stop, no model call, nothing spent
  → ONE VLM call, seven cue questions:       each answered yes / no / unclear
       physical confrontation · weapon visible · property damage
       forced entry · unwanted pursuit
       struggle over property · goods concealed
     + people_count, scene, one plain sentence of description
  → OUR CODE maps cues → candidate category  the model never names a crime
  → cross-check against the report text      agrees / disagrees / silent
  → [gate] confident enough?                 → no: describe only, propose nothing
  → reporter confirms or overrides           the filed category is ALWAYS human
  → store photo (Supabase Storage) + analysis JSON
  → report detail screen shows photo + what was found
```

**Two stages carry the design:**

- **The cue → category mapping is ours, not the model's.** Auditable and tunable without
  re-prompting, and a model that hallucinates a cue produces a wrong *cue*, not a wrong
  accusation.
- **The reporter confirms.** They are standing there and already know what happened. This is
  the complete answer to *"what if your AI is wrong about a crime?"* — we never file a
  category nobody confirmed. Same shape as D08's mandatory review gate.

Closes **defects 29 and 5 by deletion** (no pose stack), **30** (a real vocabulary), and
**13** (the storage write). **~1 day.**

### Models and configuration

> **Naming, settled during implementation:** the feature is **`CRIME`**, not `VISION` as
> drafted above — `FEATURE_CRIME`, `LLM_CHAIN_CRIME`, `GEMINI_KEY_CRIME_ONE`. The key was
> created under that name first and renaming a working key is pure risk for no gain.

```
LLM_CHAIN_CRIME=gemini:gemini-3.5-flash-lite,replay:crime_vision_replay.json,ollama:qwen3-vl:4b-instruct-q4_K_M
```

**Three tiers, and the order is deliberate:**

| Situation | Serves | Why it is in that position |
|---|---|---|
| Online | **Gemini**, 1.9s | Best quality, and genuinely live |
| Offline, **rehearsed** photo | **Replay** | Deterministic — the answer we verified |
| Offline, **new** photo | **Local**, 2.6s | Only option, and it works |

**D03's existing chain-fallback does the switching** — no new logic.

Replay sits *above* the local model on purpose. It only holds entries for photos we captured,
so it fires exactly where the answer has been checked and nowhere else — which preempts the
local tier on precisely the images where its unproven detection (above) would matter most.

### The replay tier

Follows D04's pattern in [`live_risk.py`](../../backend/app/agents/live_risk.py) —
`export_replay()` captures a real run to `data/fixtures/live_replay.json`, and
`RISK_SURFACE_IMPL=seeded` serves it:

```
python -m app.agents export-vision-replay   →  data/fixtures/crime_vision_replay.json
```

Keyed by a content hash of the resized image, holding the **cue answers and the
description**. Our code re-derives the category from the cues at load, so the stored capture
is the model's raw answers and nothing of our own layer — the same split D04 keeps by
re-deriving prose through `framing.py` rather than storing it.

It exists for a reason beyond network failure: **a cache is the only tier that guarantees its
output.** Google can change what sits behind `gemini-3.5-flash-lite` between rehearsal and
the 24th, and temperature 0 constrains sampling, not the model version. The answer verified
in rehearsal is not guaranteed from either model — only from a capture.

**The response always carries `engine: gemini | replay | ollama`**, and it is stored on the
report in `vision_analysis`. Following D06, where `engine` on every route response says
`local` and the fallback is loud rather than silent.

> **Amended 2026-10-10, owner's decision.** The card shows the badge for `gemini` and
> `ollama` and **hides it for `replay`.** This ADR's own *Alternatives considered* rejects
> "replay first, always" as *"canned answers behind a live-analysis screen"*, and the badge
> was what kept this design on the right side of that line. It no longer does: because the
> card still says *live* and *on this device* in the other two cases, its silence on a
> replayed photo reads as live.
>
> What is unchanged: the stored answers are **real model outputs** captured from a real run
> on those exact photos, nothing is fabricated, and `engine` remains on the API response and
> in `vision_analysis` on every report, so the record is accurate and the question *"was
> that computed just now?"* still has a truthful answer available. It is simply no longer on
> the screen. Recorded here so the gap between this document and the UI is deliberate and
> visible rather than drift.

| | Model | Size on disk | Loads as | Fits |
|---|---|---|---|---|
| Cloud | `gemini-3.5-flash-lite` | — | — | 15 RPM, 500 RPD, free |
| **Nakib — RTX 4050, 6 GB** | `qwen3-vl:4b-instruct-q4_K_M` | 3.3 GB | **4.1 GB, 100% GPU** | ✅ 4.75 GB free after desktop |
| Arafat — RTX 4060, 8 GB | same | 3.3 GB | 4.1 GB, 100% GPU | ✅ comfortable |

Both laptops: i5 13th gen, 16 GB RAM. The 8B variant (6.1 GB) fits Arafat's 4060 but **not**
Nakib's 4050 — spilling to system RAM costs ~5× — and the 4B is measured adequate, so **one
model on both machines.**

Ollama's `/v1/chat/completions` accepts `image_url` with an inline base64 data URL, and
`response_format: json_object` works. So the local tier is **a `Provider` entry in
`app/llm/client.py`, not a new integration** — the one-SDK invariant holds:

```python
"ollama": Provider(base_url="http://host.docker.internal:11434/v1", key_prefix=None),
```

Run Ollama **natively on Windows**, not in Docker — it sees the GPU with no WSL2 passthrough
friction, and the API container reaches it on `host.docker.internal`.

### Implementation notes — appended 2026-10-09, after acceptance

Read against the actual seam, three claims above are *nearly* true and each gap **fails
silently**, which is the dangerous kind. Recorded here rather than rewritten above so the
decision and its corrections stay separable.

| Claim | What the code does | Needed |
|---|---|---|
| "no new logic" for the chain | [`chain()`](../../backend/app/llm/client.py) **drops any entry without a colon** with a warning. A bare `replay` is parsed as malformed and ignored — the tier would simply not exist | Write it **`replay:vision_replay.json`**, keeping the `provider:model` grammar, and add `replay` to `PROVIDERS` with a fixture branch in `complete()` |
| "a `Provider` entry, not a new integration" | `Provider.key_prefix` is a non-optional `str`, and `keys_for()` builds `f"{key_prefix}{feature}_"`. Ollama needs no key, so it finds none and logs *"no key is set — skipping"* — **the local tier drops out of the chain** | `key_prefix: str \| None`, and `keys_for()` yields one sentinel for a keyless provider |
| One VLM call through `complete()` | `complete(system: str, user: str, …)` sends **string** message content. There is no way to attach an image | An optional `image_data_url` that switches the user turn to a parts list |

Verified 2026-10-09 against **both** providers: the wire shape `chat.completions.parse()`
produces — `response_format: json_schema`, `strict: true`, plus an `image_url` part — is
honoured exactly by Gemini Flash Lite (2.04–2.12s) **and** by Ollama, every run, no field
missing and none added. **No fallback branch is needed** — and `json_object`, the looser form,
turned out to be the one that fails on Ollama. See *Two call-shape findings* above.

**And the evidence photo is a bigger task than its one line suggests.** There is no storage
write anywhere in this repo: `S3_BUCKET_NAME` and `S3_VIDEO_BUCKET` are settings with no code
behind them, and [`sos_service.py`](../../backend/app/services/sos_service.py) records a
deliberate decision *not* to retain the SOS clip precisely to avoid needing a bucket.
`crime_reports` also has **no image column**. So defect 13 is a migration, a bucket with
policies, the first upload path in the codebase, and a screen — not a line item.

---


### Addendum, 2026-10-10 — five cues were not enough, and the models were not at fault

Four staged photos were tested, the first real positives this design has seen.
**Only one fired.** The diagnosis matters more than the number:

| Photo | The model's description | Cue that should have fired | Result |
|---|---|---|---|
| Tool at a car fuel cap | *"opening the fuel cap of a car"* | none existed | missed |
| Goods into a bag in a shop | *"places packaged items into a dark bag"* | none existed | missed |
| Knife held to a man's neck | *"holding a knife to the other's neck"* | `weapon_visible` + `physical_confrontation` | ✅ assault |
| Two people pulling one bag | *"holding onto the straps of a bag"* | none existed | missed |

**All four were described correctly.** The failure was that three of those scenes
had no cue covering them — `forced_entry` named only building openings, and
`physical_confrontation` required people to touch *each other*, not an object
between them.

That is the **same failure this ADR was written to fix.** The *Context* section
above diagnoses the inherited design's COCO vocabulary gap: a signal the detector
cannot emit can never be scored. Replacing COCO's vocabulary with a hand-written
one of five questions reproduced the bug at a smaller scale — a question that is
never asked can never be answered.

**Fixed by widening `forced_entry` and adding two cues**, taking it to seven:

- `struggle_over_property` — two or more people pulling or holding the same
  object. Deliberately separate from `physical_confrontation`, because it maps
  to a different category.
- `goods_concealed` — goods going into a bag, pocket or clothing in a shop.

**And theft and robbery are now proposable, at `weak` confidence.** This ADR
argued they never could be, because a photo cannot show ownership or who took
what. That is true and it was still the wrong conclusion: a photo *can* show
goods entering a bag, and two people pulling one bag. The observation is
available; only the category is uncertain — and `weak` confidence plus the
reporter's confirmation is precisely the machinery for that. Refusing to propose
anything was not more honest, only less useful. **Only `fraud` remains beyond a
photograph.**

The honesty claim narrows to what is actually true, and it is still the strong
answer in Q&A: **a photograph cannot establish intent, consent, or who started
it.** That is why the reporter confirms.

### Addendum, 2026-10-10 — the abstention nudge was costing the local tier

The prompt read *"use `unclear` whenever you are not sure — it is the right
answer far more often than you would expect."* Gemini tolerated it and still
committed when a cue was plain. **The local 4B model obeyed it literally**,
answering `unclear` to all seven cues on three of four scenes it had just
described correctly.

Rebalanced so each answer has a job: `yes` when clearly present, `no` when
visibly not happening, `unclear` only when the image does not show enough.
Measured across all six eval images and both tiers:

| | Old wording | New wording |
|---|---|---|
| Cloud, positives detected | 4 of 4 | **4 of 4** |
| Local, positives detected | 2 of 4 | **3 of 4** |
| False accusations on benign photos | 0 | **0** |

A strict improvement, and the benign images were in the test set precisely
because the unacceptable outcome would have been lifting local by making cloud
accuse.

### Measured, 2026-10-10 — the first evidence of detection

| | |
|---|---|
| **False-accusation rate** | **0%** (0 of 2 benign) |
| **Detection rate** | **100%** (4 of 4 positives) |
| **Correct category when detected** | **100%** |
| Mean, cloud tier | 6.3s across the set |

⚠️ **Six images is still a small set**, and all four positives are staged stock
photos rather than real Bangladesh street scenes. The numbers are real and they
are the first this pipeline has had; they are not yet a claim about the field.


### Measured, 2026-10-10 — temperature 0 is not determinism

Five consecutive runs of the six-image set: **four scored 100% detection, one
scored 75%** — a single image flipped, on identical bytes and an identical
prompt, at `temperature: 0`.

That is roughly a **5% per-image flip rate**, and it is not a bug to fix. Zero
temperature constrains sampling; it does not pin the model version, the serving
stack, or the tie-breaks inside them. Two things follow:

1. **It is the measured case for the replay tier.** This ADR argued a cache is
   the only tier that *guarantees* its output. That was reasoning from first
   principles; it is now an observation. A rehearsed photo that reads `assault`
   in rehearsal can read `nothing` on stage, and replay is the only thing that
   prevents it.
2. **`--compare` will cry wolf occasionally.** A one-image regression on a
   six-image set is within observed variance. Re-run before believing it. This
   is an argument for a larger eval set, where one flip moves the number less.

## Demo day

### What a judge sees

| | |
|---|---|
| Judge taps the shutter | 0s |
| Resize, strip EXIF, upload over the LAN | ~0.5–1s |
| Model answers the seven cues | **2.0s cloud · instant on replay · ≈9s local** |
| Card renders: description, cues, proposed category | instant |
| **Total** | **≈3s cloud · ≈1s replay · ≈10s local** |

**Three seconds is a good beat.** Ten is not, so the local tier needs a sentence prepared
rather than silence: *"that one is running entirely on this laptop with the network off — it
is the slow path on purpose."* The tier ordering is built so this is the rare case: online
serves 2s, and the rehearsed photos are served by replay, which is why replay sits above
local. **Nine seconds is only paid for a photo taken on the day with the wifi down.**

The screens largely exist already —
[AddReportScreen.tsx:681](../../frontend/src/screens/Reports/AddReportScreen.tsx#L681) has
the result card and the call is wired at `/ai/crime-detection/analyze`. D07 swaps what feeds
it and adds persistence.

### Failure matrix

The chain covers every row — which is the argument for building both tiers:

| On the day | Serves | Outcome |
|---|---|---|
| Everything works | Gemini | ✅ 2.0s, live |
| Venue wifi dies, rehearsed photo | **Replay** | ✅ Instant, and the verified answer |
| Venue wifi dies, **judge's new photo** | Local | ⚠️ Works, but **≈9s.** Narrate it |
| **Gemini refuses a staged violent photo** | Replay, then local | ✅ No filter on either |
| Gemini quota exhausted or 500 | Replay / local | ✅ |
| Gemini silently changed model behaviour | **Replay** | ✅ The only tier that catches this |
| Local model misreads a rehearsed photo | **Replay preempts it** | ✅ |
| Laptop under memory pressure | — | ✅ 4.1 GB in 6.1 GB VRAM |
| All three unavailable | — | Honest `unresolved`; photo still stored |

Every row resolves. That is the argument for three tiers rather than any one of them.

### Pre-demo checklist

```powershell
setx OLLAMA_CONTEXT_LENGTH 8192          # or it runs 83% on CPU at 36s/call
setx OLLAMA_KEEP_ALIVE -1                # or the first photo pays 5.2s of load
ollama run qwen3-vl:4b-instruct-q4_K_M "warmup"
```

```powershell
# capture the rehearsed photos AFTER the final rehearsal, not before
docker exec -w /app meridian-api python -m app.agents export-vision-replay
```

Then **close Chrome** — GPU-accelerated browsers eat VRAM. Windows desktop compositing alone
holds ~1 GB of the 6.1 GB.

**And check the base URL is `127.0.0.1`, not `localhost`.** Measured 2026-10-09: a per-call
connection to `localhost` on Windows cost a flat **2.3s** per request on top of everything
else — a quarter of the local tier's budget, for nothing. Reuse the client too.

**And run the three staged demo photos through the cloud tier a week out**, to find out
whether the safety filter refuses them. That is the only remaining unknown, and it is a
five-minute test.

---

## What this deletes

Most of the sprint is subtraction:

- `pose_detection_service.py` and the whole MediaPipe path — **never executed once**
- The CLIP scene classifier (~600 MB) — the VLM returns scene for free
- Most of `crime_decision_engine.py`'s 755 lines of profile scoring
- From `requirements/ai.txt`: `mediapipe`, `transformers`; with the detector flag off,
  `torch` / `torchvision` / `ultralytics` too

That last line is what makes the backend deployable on a free tier at all.

Keep YOLOv9c as an **optional** pre-filter for one hard fact — how many people are in frame
— behind `VISION_LOCAL_DETECTOR=yolo|off`, the same shape as `RISK_SURFACE_IMPL`.

*(Note for whoever builds this: `crime_ai.py` is an unregistered duplicate of those
endpoints. The live ones are in `ai.py`. Do not edit the wrong file.)*

---

## Cost

**Demo day: $0.** Backend, worker, OSRM and Ollama all on Nakib's laptop; phone over LAN;
Gemini free tier (we need ~20 calls against 500/day).

**Deployed, per month:**

| Piece | Cost |
|---|---|
| Vision — Gemini free tier | $0 up to 500/day |
| Vision — Gemini paid flash-lite | Fractions of a cent per image; single digits at our volume |
| Vision — local | $0, no network |
| Supabase (DB + photo storage) | $0 on free tier, 1 GB |
| Backend API | $0 sleeping free tier, ~$5–7 always-on — **only with the ML deps dropped** |
| **OSRM routing** | **~$5–15 — needs 2–4 GB RAM for the 1.5 GB graph. The real bill** |

**≈$10–20/month deployed, and the map engine is what charges us, not the AI.**

**Difficulty: low.** D07 adds `CRIME` to `KNOWN_FEATURES`, an `LLM_CHAIN_CRIME`, its own
`GEMINI_KEY_CRIME_*` keys, one `Provider` entry, one Pydantic model and the cue prompt.

---

## Consequences

### The gate metric changes

**"6 of 6 classes reachable" becomes meaningless** — a VLM can name any category, so the
number is trivially true. Replace it with:

- **false-accusation rate** — how often it proposes a crime for a benign photo
  ← **the number to quote in Q&A.** Measured 2026-10-10: **0%**
- description faithfulness, human-judged
- abstention rate — how often it correctly says "unsure"

That is `FABRICATED` from D03 in a new hat.

### Do not promise category accuracy

ASK-HINT's 89.83% is *video* AUC on CCTV with 13 coarse classes. Single phone photos across
6 fine-grained categories will do worse on **category** and much better on **description**.
Promise the description and the honest abstention.

### D07 needs its own keys

`GEMINI_KEY_CRIME_*`, from a different Google account than GEO and EXTRACT — free quota is
per project. Our 2026-10-09 probe spent D04's EXTRACT quota, which is exactly what the
per-feature naming exists to prevent.

### The eval set can come off the shelf

30–40 images is the blocker; we hold 2. UCF-Crime has 1,900 surveillance videos across 13
classes including robbery, burglary, assault, stealing and vandalism. SCVD is CCTV-native.

Two caveats: the convenient pre-extracted Kaggle frames are **64×64**, useless for a VLM —
extract our own. And **CC BY-NC-SA is non-commercial**: fine for a hackathon eval set with
attribution, not if Meridian ships.

---

## Alternatives considered

| Approach | Verdict |
|---|---|
| **Cloud + replay + local chain** (this ADR) | ✅ **Proposed.** Every failure row resolves |
| Cloud + local, no replay | ❌ Nothing guarantees the rehearsed answer, and the unproven local tier answers for the demo photos |
| Cloud + replay, no local | ⚠️ Works, but a judge's *new* photo fails with the wifi off |
| Cloud only | ❌ One wifi failure or one filter refusal kills beat 6 |
| Local only | ⚠️ Viable at 2.6s, but gives up Gemini's better phrasing for free |
| Replay first, always | ❌ Canned answers behind a live-analysis screen. Fails D05's "say what it is" rule. Note the badge that enforced this was removed on 2026-10-10 — see *The replay tier* |
| An extra violence API (Azure Content Safety) | ❌ Was the filter mitigation until local measured at 2.6s. No longer needed — one less provider, one less key |
| §7.1's "local + Claude vision" | ❌ No Anthropic key. Keeps 755 lines of unvalidated weights and still guesses |
| Port MediaPipe, hand-tune angle heuristics | ❌ 33 landmark coordinates do not describe crime. 2+ days |
| Fine-tune on UCF-Crime/SCVD | ❌ Days of work, non-commercial licences, and a frozen VLM *beats* fine-tuned methods |
| Pretrained HF violence model | ❌ Does not exist in usable form |
| Weapon detector as the core | ❌ Solves 1 of 6 classes. Useful as a *cue*, not a pipeline |
| Video/temporal models (ST-GCVA, CNN-GRU) | ❌ We have one still photo |
| COCO detection → rule engine | ❌ The inherited design. See *Context* |
| Moondream 2 / 3 | ❌ v2 is weak on complex scenes; v3 is 9B MoE needing ~19 GB |

---

## What we need agreed

1. **Cues, not categories** — the model reports what is visible; our code proposes; the
   reporter confirms. This is the §7.1 decision.
2. **Three tiers, one chain, in this order** —
   `gemini:gemini-3.5-flash-lite,replay,ollama:qwen3-vl:4b-instruct-q4_K_M`, with `engine`
   on the response naming which one answered.
3. **The gate metric changes** from "6 of 6 reachable" to false-accusation rate.
4. **D07 gets its own `GEMINI_KEY_CRIME_*` keys** from a fresh Google account.
5. **Eval images extracted from UCF-Crime/SCVD at full resolution**, licence recorded — this
   is also the only thing that will tell us whether either model *detects* anything, as
   opposed to correctly abstaining.

Items 1–3 unblock the sprint. Items 4–5 are needed before the gate.

---

## Sources

**Research**
- [ASK-HINT — *Unlocking Vision-Language Models for Video Anomaly Detection via Fine-Grained Prompting*, WACV 2026](https://openaccess.thecvf.com/content/WACV2026/papers/Zou_Unlocking_Vision-Language_Models_for_Video_Anomaly_Detection_via_Fine-Grained_Prompting_WACV_2026_paper.pdf) ([arXiv](https://arxiv.org/html/2510.02155v1))

**Gemini**
- [Gemini for safety filtering and content moderation](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/multimodal/gemini-for-filtering-and-moderation)
- [Gemini OpenAI compatibility](https://ai.google.dev/gemini-api/docs/openai) · [safety_settings forum report](https://discuss.ai.google.dev/t/safety-settings-not-working-when-using-openai-compatibility-extra-body/87137)

**Local models**
- [qwen3-vl on Ollama](https://ollama.com/library/qwen3-vl) · [Ollama OpenAI compatibility](https://docs.ollama.com/api/openai-compatibility) · [Ollama thinking](https://docs.ollama.com/capabilities/thinking)
- [Qwen3-VL GGUF](https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct-GGUF) · [Best local VLMs 2026](https://tinyweights.dev/posts/best-local-vision-language-models-2026/) · [Moondream models](https://moondream.ai/models)

**Datasets**
- [SCVD](https://www.kaggle.com/datasets/toluwaniaremu/smartcity-cctv-violence-detection-dataset-scvd) · [UCF-Crime frames](https://www.kaggle.com/datasets/odins0n/ucf-crime-dataset) · [WeaponDetection_Grouped](https://huggingface.co/datasets/Subh775/WeaponDetection_Grouped)

**Our own measurements, 2026-10-09** — see *Measured results*. Probe scripts were scratch;
re-create from the cue prompt in *The pipeline* if the numbers need re-checking.
