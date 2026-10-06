# Meridian Backend - FastAPI

Smart Safety Navigation System Backend API

## 🚀 Features

- **Crime Reporting System**: Submit and track crime reports with geolocation
- **Smart Routing**: Calculate safest routes based on crime data
- **Real-time Tracking**: Background GPS tracking with danger zone alerts
- **SOS Emergency System**: Voice-activated emergency response
- **AI Services**: Speech-to-Text using Google Cloud for voice commands
- **Push Notifications**: Real-time alerts via Firebase Cloud Messaging
- **SMS Integration**: CloudWaveBD SMS gateway for emergency contacts

## 📋 Prerequisites

- Python 3.11+
- PostgreSQL 16+ with PostGIS extension
- Redis 7+
- Docker & Docker Compose (optional but recommended)

## 🛠️ Installation

### Option 1: Using Docker (Recommended)

1. **Clone and navigate to backend directory**

```bash
cd backend
```

2. **Create .env file**

```bash
cp .env.example .env
# Edit .env with your configuration
```

3. **Start all services**

```bash
docker-compose up -d
```

4. **Check service status**

```bash
docker-compose ps
```

The API will be available at `http://localhost:8000`

### Option 2: Manual Setup

1. **Create virtual environment**

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

2. **Install dependencies**

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

3. **Setup PostgreSQL with PostGIS**

```sql
CREATE DATABASE Meridian_db;
\c Meridian_db
CREATE EXTENSION postgis;
CREATE EXTENSION postgis_topology;
```

4. **Setup Redis**

```bash
# Install Redis for your OS
# Windows: Use WSL or download from https://redis.io/download
# Linux: sudo apt-get install redis-server
# Mac: brew install redis
```

5. **Configure environment**

```bash
cp .env.example .env
# Edit .env with your database and API credentials
```

6. **Run database migrations**

```bash
alembic upgrade head
```

7. **Start the application**

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

8. **Start Celery worker (in another terminal)**

```bash
celery -A app.core.celery_app worker --loglevel=info
```

9. **Start Celery Beat (in another terminal)**

```bash
celery -A app.core.celery_app beat --loglevel=info
```

## 📁 Project Structure

```
backend/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── endpoints/
│   │       │   ├── auth.py          # Authentication endpoints
│   │       │   ├── crimes.py        # Crime reporting
│   │       │   ├── routes.py        # Route calculation
│   │       │   ├── tracking.py      # Location tracking
│   │       │   ├── sos.py           # Emergency SOS
│   │       │   └── users.py         # User management
│   │       └── api.py               # API router aggregation
│   ├── core/
│   │   ├── config.py                # Application settings
│   │   ├── database.py              # Database configuration
│   │   ├── security.py              # Auth & JWT utilities
│   │   ├── celery_app.py            # Celery configuration
│   │   └── redis.py                 # Redis client
│   ├── models/
│   │   ├── user.py                  # User model
│   │   ├── crime.py                 # Crime report model
│   │   ├── sos.py                   # SOS incident model
│   │   └── location.py              # Location tracking model
│   ├── schemas/
│   │   ├── auth.py                  # Auth schemas
│   │   ├── crime.py                 # Crime schemas
│   │   ├── route.py                 # Route schemas
│   │   └── user.py                  # User schemas
│   ├── services/
│   │   ├── crime_service.py         # Crime scoring logic
│   │   ├── route_service.py         # Route calculation
│   │   ├── sms_service.py           # SMS gateway integration
│   │   └── storage_service.py       # File upload/storage
│   ├── utils/
│   │   ├── geospatial.py            # Geospatial utilities
│   │   └── notifications.py         # Push notifications
│   └── main.py                      # Application entry point
├── tests/                           # Unit tests
├── alembic/                         # Database migrations
├── logs/                            # Application logs
├── requirements.txt                 # Python dependencies
├── Dockerfile                       # Docker configuration
├── docker-compose.yml               # Multi-container setup
└── .env.example                     # Environment variables template
```

## 🔌 API Endpoints

### Authentication

- `POST /api/v1/auth/register` - Register new user
- `POST /api/v1/auth/login` - User login
- `POST /api/v1/auth/refresh` - Refresh access token

### Crime Reporting

- `POST /api/v1/crimes/report` - Submit crime report
- `GET /api/v1/crimes/nearby` - Get nearby crimes
- `GET /api/v1/crimes/heatmap` - Get crime heatmap

### Routing

- `POST /api/v1/routes/calculate` - Calculate safe routes
- `GET /api/v1/routes/safest` - Get safest route

### Location Tracking

- `POST /api/v1/tracking/update-location` - Update user location
- `GET /api/v1/tracking/check-danger-zone` - Check danger zones

### SOS Emergency

- `POST /api/v1/sos/trigger` - Trigger emergency SOS
- `POST /api/v1/sos/upload-video` - Upload SOS video
- `GET /api/v1/sos/nearest-police` - Find nearest police station

### User Management

- `GET /api/v1/users/me` - Get current user info
- `PUT /api/v1/users/emergency-contacts` - Update emergency contacts

## 📚 API Documentation

Once the server is running, access:

- Swagger UI: `http://localhost:8000/api/docs`
- ReDoc: `http://localhost:8000/api/redoc`

## 🔧 Configuration

Key environment variables in `.env`:

```env
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/Meridian_db

# Redis
REDIS_URL=redis://localhost:6379/0

# JWT
JWT_SECRET_KEY=your-secret-key

# CloudWaveBD SMS
CLOUDWAVEBD_API_KEY=your-api-key
CLOUDWAVEBD_SENDER_ID=Meridian

# Firebase
FIREBASE_CREDENTIALS_PATH=./firebase-credentials.json

# AWS S3
AWS_ACCESS_KEY_ID=your-access-key
S3_BUCKET_NAME=Meridian-media
```

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app tests/

# Run specific test file
pytest tests/test_crimes.py
```

## 📊 Monitoring

### Celery Flower (Task Monitoring)

Access at `http://localhost:5555` when running with Docker Compose

### Database Monitoring

```bash
# Connect to PostgreSQL
docker exec -it Meridian-postgres psql -U Meridian_user -d Meridian_db

# Check PostGIS
SELECT PostGIS_version();
```

## 🚀 Deployment

### Production Checklist

- [ ] Update `SECRET_KEY` and `JWT_SECRET_KEY`
- [ ] Set `DEBUG=False`
- [ ] Configure production database
- [ ] Setup SSL/TLS certificates
- [ ] Configure CORS for production domains
- [ ] Enable Sentry for error tracking
- [ ] Setup backup strategy for database
- [ ] Configure CDN for media files
- [ ] Enable rate limiting
- [ ] Setup monitoring and alerting

### Docker Production Build

```bash
docker build -t Meridian-api:prod .
docker run -p 8000:8000 --env-file .env.prod Meridian-api:prod
```

## 📝 Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback migration
alembic downgrade -1
```

## 🔍 Troubleshooting

### PostgreSQL Connection Issues

```bash
# Check if PostgreSQL is running
docker ps | grep postgres

# View logs
docker logs Meridian-postgres
```

### Redis Connection Issues

```bash
# Test Redis connection
redis-cli ping

# Check Redis logs
docker logs Meridian-redis
```

### Import Errors

```bash
# Ensure you're in the backend directory
export PYTHONPATH="${PYTHONPATH}:${PWD}"
```

## 🤝 Contributing

1. Create a feature branch
2. Make changes
3. Write tests
4. Run linting: `black . && flake8`
5. Submit pull request

## 📄 License

MIT License - see LICENSE file

## 📞 Support

For issues and questions:

- GitHub Issues: [Create Issue]
- Email: support@Meridian.com
