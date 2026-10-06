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
    SECRET_KEY: str
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # Database
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    DATABASE_URL: str
    
    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_URL: str
    
    # Celery
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str
    
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
    SMTP_SERVER: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    FROM_EMAIL: str = ""
    
    
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
