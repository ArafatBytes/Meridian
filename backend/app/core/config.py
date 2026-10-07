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
    ANTHROPIC_API_KEY: str = ""
    LLM_MODEL_JUDGMENT: str = "claude-opus-5-5"
    LLM_MODEL_BULK: str = "claude-sonnet-5-5"
    
    
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
