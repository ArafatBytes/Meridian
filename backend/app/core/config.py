"""
Application configuration using Pydantic Settings
"""
from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Meridian"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = "development"
    DEBUG: bool = True

    # Declared since the beginning and read by nothing — JWT_SECRET_KEY is what
    # actually signs and validates tokens. It had no default, so a .env without
    # it crashed the app at import with a pydantic ValidationError. Given a
    # default rather than removed, because .env.example has always shipped it.
    # S04 drops it when config moves to app/config/.
    SECRET_KEY: str = "unused-see-JWT_SECRET_KEY"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Database
    #
    # DATABASE_URL is the only one that matters: database.py builds the engine
    # from it directly and nothing reads the POSTGRES_* parts. They are kept as
    # optional hints for a local-Postgres setup; with Supabase they stay empty.
    # Requiring them meant six dead values in every .env just to boot.
    POSTGRES_USER: str = ""
    POSTGRES_PASSWORD: str = ""
    POSTGRES_DB: str = ""
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    DATABASE_URL: str

    # Supabase
    #
    # SUPABASE_URL is REQUIRED for authentication: app/core/jwks.py fetches the
    # project's JWT signing keys from
    # {SUPABASE_URL}/auth/v1/.well-known/jwks.json. Supabase signs access
    # tokens with ES256 by default, so there is no shared secret to verify
    # against -- see docs/adr/0002-auth.md.
    #
    # These were added to .env.example in S01b but not declared here, and
    # pydantic-settings is configured with extra="ignore", so the values sat in
    # .env and were silently dropped. The symptom was
    # AttributeError: 'Settings' object has no attribute 'SUPABASE_URL'.
    SUPABASE_URL: str = ""

    # Server-side only; bypasses Row Level Security. Never expose to the app.
    SUPABASE_SERVICE_ROLE_KEY: str = ""

    # Redis
    # Defaults target a local install; docker-compose overrides the host to
    # `redis`. Redis is unused until the geo-proxy cache lands in S05.
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_URL: str = "redis://localhost:6379/0"

    # Celery
    # No tasks are defined yet and the beat schedule still points at two modules
    # that do not exist, so the worker is deliberately left out of
    # docker-compose. S04 replaces this with the agent schedule registry.
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/0"
    
    # JWT
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # CORS
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000"]
    
    # SMS Gateways
    CLOUDWAVEBD_API_KEY: str = ""
    CLOUDWAVEBD_SENDER_ID: str = "Meridian"
    CLOUDWAVEBD_API_URL: str = ""
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_PHONE_NUMBER: str = ""
    
    # Firebase
    FIREBASE_CREDENTIALS_PATH: str = "./firebase-credentials.json"
    FIREBASE_PROJECT_ID: str = ""
    
    # AWS S3
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"
    S3_BUCKET_NAME: str = "Meridian-media"
    S3_VIDEO_BUCKET: str = "Meridian-sos-videos"
    
    # Google Maps
    GOOGLE_MAPS_API_KEY: str = ""
    
    # Google Cloud AI Services
    GOOGLE_CLOUD_PROJECT_ID: str = ""
    GOOGLE_CLOUD_CREDENTIALS_PATH: str = "./google-cloud-credentials.json"
    GOOGLE_CLOUD_REGION: str = "us-central1"
    
    # Speech-to-Text Settings
    SPEECH_RECOGNITION_LANGUAGE: str = "en-US"
    SPEECH_MAX_DURATION_SECONDS: int = 30
    SPEECH_SAMPLE_RATE: int = 16000
    
    # Which RiskSurface GET /api/v1/risk/flags reads from: "db" or "seeded".
    #
    # "db" reads the risk_flags table. "seeded" reads
    # data/fixtures/risk_flags.json and never touches the database at all -- the
    # offline demo path (DEMO_PLAN.md D10), and what to switch to if Postgres or
    # the venue network dies mid-script.
    #
    # Chosen in app/scoring/__init__.py :: get_risk_surface(). An unknown value
    # raises on the first request rather than falling back, because the seeded
    # surface looks entirely plausible and `sample_` in the source strip is the
    # only tell that you are showing the fixture.
    RISK_SURFACE_IMPL: str = "db"

    # Rumour Guard (D05) -- see app/agents/rumour_guard.py for the reasoning.
    #
    # DEDUP_SIMILARITY_THRESHOLD is MEASURED, not chosen, and it is NOT plan section
    # 9's declared 0.82. Run `python scripts/eval_dedup.py` to reproduce:
    #
    #   threshold   true duplicates merged   false merges
    #     0.70            13/18 (0.72)            2
    #     0.72            10/18 (0.56)            0     <-- here
    #     0.82             1/18 (0.06)            0
    #
    # At the plan's 0.82 the Rumour Guard merges essentially nothing, so D05 would be
    # a no-op that looked implemented: four outlets would still make four unconfirmed
    # pins. The declared value was written before anything measured this model on this
    # text, and 0.82 is simply not where MiniLM puts paraphrases of a one-line summary.
    #
    # 0.72 is the highest threshold with ZERO false merges on the labelled set, and
    # that is the right side to err on: a missed merge costs a duplicate pin, a false
    # merge puts a `confirmed` badge on an event that did not happen.
    #
    # ⚠️ The classes are NOT linearly separable here -- lowest true duplicate 0.503,
    # highest false pair 0.718 -- so 0.72 clears the worst negative by 0.002. That is
    # not a margin, it is a coincidence, and it is why `find_duplicate()` declines
    # rather than guesses whenever any other gate is unsatisfied. Recall is 56% by
    # choice. Improving this needs a better signal, not a different number: embed the
    # location alongside the summary, or use a cross-encoder. Re-run the eval after
    # ANY change to DEDUP_MODEL or to what gets embedded; the number is a property of
    # the pair, not of the problem.
    DEDUP_SIMILARITY_THRESHOLD: float = 0.72

    # Independent publishers required before a flag may be `confirmed`. Two is the
    # concept document's commitment and the database CHECK enforces the same number;
    # raising it here without changing that constraint is safe, lowering it to 1 is
    # not -- the insert would be rejected, which is the layering working.
    MIN_SOURCES_FOR_CONFIRMED: int = 2

    # How far apart in time two accounts of one event may be observed. Outlets follow
    # each other within hours; a day apart is a different incident at the same corner.
    DEDUP_WINDOW_HOURS: float = 6.0

    # English-only and ~90 MB, because what gets embedded is the extraction model's
    # own `summary_en`, not the Bangla headline. Swap for
    # paraphrase-multilingual-MiniLM-L12-v2 (~470 MB) if Bangla text ever goes
    # through the comparison; nothing else changes.
    DEDUP_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"

    # OSRM
    #
    # `http://osrm:5000` inside the compose network, which is where `api` runs. The
    # localhost default is for a backend started natively against a port-mapped
    # container. **An unset or empty value falls back to the public demo server and
    # logs a warning on every request** -- that is defect 7, and it is loud rather
    # than silent because a rate-limited third party answering routes mid-demo is
    # exactly the failure that looks like "the app is slow".
    OSRM_BASE_URL: str = "http://localhost:5000"

    # Route scoring (D06) -- S12 asks for a composite that is "documented and tunable
    # in settings, not a magic constant". The reasoning for each lives in
    # app/routing/scorer.py; these are the knobs.

    # How far from the road a flag still counts as "on this route", in metres. 150 m is
    # about the width of a Dhaka intersection plus its approaches: wide enough that a
    # flag beside the carriageway counts, narrow enough that one on a parallel street
    # two blocks over does not.
    ROUTE_CORRIDOR_RADIUS_M: int = 150

    # Share of the ranking that is safety; the rest is duration. 0.7 so safety
    # dominates without winning outright -- a route marginally safer and twice as long
    # is not the one to recommend, and an app that always returns the longest route
    # stops being used.
    ROUTE_SAFETY_WEIGHT: float = 0.7

    # Geometric falloff applied to each additional flag's penalty, worst first. Summing
    # penalties makes every long route score zero (ten minor flags over 12 km exceed any
    # threshold, and the ranking then carries no information); averaging lets one severe
    # flag be diluted by a dozen trivial ones. 0.5 means the worst counts in full, the
    # second half, the third a quarter.
    ROUTE_PENALTY_FALLOFF: float = 0.5

    # How much slower than the fastest option a route may be before it scores zero on
    # the duration axis. 1.0 = twice as long. Relative rather than absolute because
    # "a long journey" has no fixed meaning: 40 minutes is ordinary across Dhaka and
    # absurd for three streets.
    ROUTE_DETOUR_TOLERANCE: float = 1.0

    # OSRM's duration multiplied by this, for driving only. **A calibration, not a
    # measurement**, and the number that decides what the app tells someone about their
    # journey -- so the reasoning is here in full.
    #
    # THE PROBLEM. OSRM answers "how long on an empty road", because that is the only
    # question the graph can answer: `car.lua` speeds come from `maxspeed` tags and road
    # class defaults. Measured on the Bangshal -> Mirpur-10 route, 2026-10-09:
    #
    #     12.61 km in 13.8 min  =>  54.8 km/h average
    #     segment speeds: min 10, median 56, max 106 km/h   (n=324)
    #
    # 54.8 km/h across central Dhaka is not a slightly optimistic estimate, it is
    # physically absurd. The graph is not wrong -- it has no traffic data, and nothing in
    # it ever will. **This cannot be fixed "from the road graph".**
    #
    # THE PROPER FIX is OSRM's own mechanism for exactly this:
    # `osrm-customize --segment-speed-file`, fed per-segment observed speeds. That needs
    # a traffic data source this project does not have, and it is Track B work.
    #
    # THE INTERIM FIX is this multiplier. Crude, but it has two properties worth having:
    # it preserves the *relative* differences between roads (a flyover segment still beats
    # an alley, which is what makes the ranking meaningful), and it is one number in one
    # place with its derivation attached.
    #
    # 0.35 puts that route at roughly 19 km/h and ~40 minutes. ⚠️ **Calibrate this against
    # a journey you actually know** before quoting any duration on stage -- it is a guess
    # scaled from one measurement, and nobody has checked it against a real trip. Walking
    # is unaffected: pedestrians do not sit in traffic, and walking durations are computed
    # from distance at _ASSUMED_WALK_KMH instead.
    ROUTE_CONGESTION_FACTOR: float = 0.35

    # What a CHRONIC flag's penalty is multiplied by. Measured, not guessed -- see
    # app/routing/scorer.py :: _penalty_for.
    #
    # The chronic layer is D02's police-statistics baseline: historical averages with
    # 2 km radii, covering most of Dhaka. At full weight a 12.6 km crossing passing
    # three of them scored 16.7/100, every route in the city scored similarly, and
    # `max_crime_score` therefore rejected all of them -- so defect 6's filter was
    # meaningless and the ranking was dominated by historical coverage rather than by
    # what is happening today.
    #
    # Worse than useless: that is the "stale red zones" failure demo beat 5 exists to
    # say this product does not have, and concept document section 9 commits to not
    # labelling areas permanently. A historical average must nudge a tie-break, not
    # decide the route.
    #
    # At 0.35 the same crossing scores 68.6, and a live fire on it moves the number
    # visibly. Raise it only with a measurement; a chronic blackspot outranking a fire
    # is the thing to watch for.
    ROUTE_CHRONIC_WEIGHT: float = 0.35

    # Nominatim proxy (D06, defect 10)
    #
    # Nominatim's usage policy requires a genuine identifying User-Agent and no more
    # than one request per second. The app was calling it directly from four screens
    # with React Native's default agent, which is both a policy violation and an
    # invitation to be blocked mid-demo.
    NOMINATIM_BASE_URL: str = "https://nominatim.openstreetmap.org"
    NOMINATIM_USER_AGENT: str = "Meridian/1.0 (+https://github.com/ArafatBytes/Meridian)"
    NOMINATIM_CACHE_TTL_SECONDS: int = 86_400
    
    # Crime Score Settings
    CRIME_SCORE_UPDATE_INTERVAL: int = 1800
    CRIME_ZONE_GRID_SIZE: int = 500
    CRIME_TIME_DECAY_DAYS: int = 90
    
    # Geofencing
    DANGER_ZONE_THRESHOLD: int = 75
    LOCATION_UPDATE_INTERVAL: int = 60
    
    # SOS Settings
    SOS_VIDEO_MAX_DURATION: int = 300
    SOS_VIDEO_MAX_SIZE_MB: int = 25  # Changed to 25MB as per requirement
    EMERGENCY_RESPONSE_RADIUS_KM: int = 10
    
    # Email Configuration (SMTP)
    #
    # REQUIRED FOR SOS. email_service.py is the only alert channel, so with
    # SMTP_USER/SMTP_PASSWORD/FROM_EMAIL empty an SOS trigger reports success to
    # the user and delivers nothing. Gmail needs an App Password, not the
    # account password.
    SMTP_SERVER: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    FROM_EMAIL: str = ""

    # Whether SOS also emails nearby police stations.
    #
    # Default OFF, and that matters: every one of the 606 rows in
    # police_stations.csv carries the same placeholder address
    # (noorlabib@iut-dhaka.edu). With this on and no real data, an SOS from
    # anywhere in Dhaka emails a stranger -- once per test.
    #
    # This flag was documented in .env.example and docs/ from S01b but never
    # declared here and never checked by sos_service, so it did nothing. Both
    # are fixed now. Turn it on when the CSV has real contacts (defect 17, S05).
    POLICE_ROUTING_ENABLED: bool = False

    # Anthropic (first used in S04; declared now so the values are not silently
    # dropped by extra="ignore" the way SUPABASE_URL was)
    #
    # Unused as of D03: this project has no Anthropic key. The LLM tier runs on
    # the free Gemini and Groq endpoints instead, both of which speak the OpenAI
    # wire format — see LLM_CHAIN below and app/llm/client.py. Kept declared so a
    # key can be dropped in later without a code change.
    ANTHROPIC_API_KEY: str = ""
    LLM_MODEL_JUDGMENT: str = "claude-opus-5-5"
    LLM_MODEL_BULK: str = "claude-sonnet-5-5"

    # Which models answer, in order, as `provider:model` pairs. The first that
    # returns a validated response wins; a rate limit moves to the next key for
    # that provider and then to the next pair. Providers are the keys of
    # app.llm.client.PROVIDERS, and their API keys are discovered from every
    # variable named GEMINI_KEY_* / GROQ_KEY_*, so adding a second account's key
    # widens the quota with no code change.
    #
    # This default was measured, not guessed — a six-case probe of real Dhaka
    # place names on 2026-10-07. gemini-3.5-flash-lite answered 6/6 and refused
    # both fabricated places. gpt-oss-120b is second because it is a *different
    # provider*: a same-provider fallback shares the rate limit and so fails at
    # the same moment as the primary. gemini-3.1-flash-lite is deliberately
    # absent despite scoring 5/6 — it invented coordinates for a place that does
    # not exist, reproducibly, at 0.95 confidence.
    # Named per FEATURE, not globally. A feature is one job that needs a model:
    # GEO here, and later EXTRACT (D04), VISION (D07), CASEWORK (D08). Two reasons
    # the split is worth a longer variable name:
    #
    #   Different jobs want different models. openai/gpt-oss-120b is a sound
    #   fallback for place names and is NOT multimodal, so the same chain would
    #   simply fail for D07's images — behind a name that gave no hint of it.
    #
    #   Keys are per-feature too (GEMINI_KEY_GEO_ONE, GROQ_KEY_GEO_ONE, ...). On
    #   this project multiple keys belong to different accounts, so their quotas
    #   are independent: D04's ingestion loop cannot exhaust the daily budget
    #   D03's search box needs. Sharing one pool hides that until a rehearsal.
    #
    # Add a feature by declaring LLM_CHAIN_<NAME> here and adding <NAME> to
    # app.llm.client.KNOWN_FEATURES. An unknown feature raises at the call site.
    LLM_CHAIN_GEO: str = "gemini:gemini-3.5-flash-lite,groq:openai/gpt-oss-120b"

    # D04: reading news articles into incidents. Gemini only, on its own keys
    # (GEMINI_KEY_EXTRACT_*) from a separate Google project, so an ingestion loop
    # can never spend the search box's quota. No Groq fallback: gpt-oss-120b
    # scored 15.6% on Dhaka place names in D03, and extraction is mostly a
    # place-name task. A rate-limited run leaves articles unread and the next run
    # picks them up — nothing is lost by waiting.
    LLM_CHAIN_EXTRACT: str = "gemini:gemini-3.5-flash-lite"

    # D07: reading cues out of a report photo. Three tiers, and the order is the
    # decision (ADR 0006):
    #
    #   gemini  — ~2s, best phrasing, needs network, and its safety filter
    #             cannot be disabled through the OpenAI-compatible endpoint, so
    #             it may refuse a staged violent photo.
    #   replay  — the rehearsed photos, captured after the final rehearsal. The
    #             only tier that *guarantees* its answer: Google can change what
    #             sits behind a model name, and temperature 0 constrains
    #             sampling, not the model version. Sits above local on purpose.
    #   ollama  — offline, no filter, ~8-9s on a photo it has not seen (4.8s of
    #             that is vision-encoder prefill and does not shrink when you
    #             shrink the image). The only tier that answers a new photo with
    #             the network down.
    LLM_CHAIN_CRIME: str = (
        "gemini:gemini-3.5-flash-lite"
        ",replay:crime_vision_replay.json"
        ",ollama:qwen3-vl:4b-instruct-q4_K_M"
    )

    # Where the local tier lives. 127.0.0.1 rather than localhost is deliberate:
    # measured 2026-10-09, resolving "localhost" on Windows against an
    # IPv4-bound Ollama cost a flat 2.3s per call. From inside Docker the host
    # is host.docker.internal, which is what .env sets.
    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434/v1"


    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_PER_HOUR: int = 1000
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/app.log"
    
    # Monitoring
    SENTRY_DSN: str = ""
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


settings = Settings()
