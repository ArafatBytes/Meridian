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
    OSRM_BASE_URL: str = "http://localhost:5000"
    
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
