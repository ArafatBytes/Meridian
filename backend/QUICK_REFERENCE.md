# 🚀 QUICK REFERENCE CARD

## One-Command Setup

```powershell
# 1️⃣ Create .env file (copy from example and edit)
cd "d:\Meridian App\backend"
Copy-Item .env.example .env
notepad .env

# 2️⃣ Start services
docker-compose up -d

# 3️⃣ Start backend
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

## Essential Commands

### Backend

```powershell
# Activate venv
.\venv\Scripts\Activate.ps1

# Start server
uvicorn app.main:app --reload

# Run tests
pytest tests/test_crime_vision.py -v

# Check installed packages
pip list | Select-String -Pattern "torch|ultralytics|fastapi"

# Deactivate venv
deactivate
```

### Frontend

```powershell
# Install dependencies
npm install

# Start app
npm start

# Android
npm run android

# iOS
npm run ios
```

### Docker

```powershell
# Start all services
docker-compose up -d

# Stop all services
docker-compose down

# View logs
docker-compose logs -f

# Restart specific service
docker-compose restart postgres
```

## API Endpoints

### Base URL

```
http://localhost:8000
```

### Crime Detection

```http
POST /api/v1/ai/crime-detection/analyze
  - Upload image (multipart/form-data)
  - Returns: crime type, confidence, title, description

GET /api/v1/ai/crime-detection/status
  - Returns: model status, loaded/not loaded

GET /api/v1/ai/crime-detection/supported-crimes
  - Returns: list of 6 crime types
```

## Quick Test

### Test 1: Check API is running

```bash
curl http://localhost:8000/health
```

### Test 2: Check AI model status

```bash
curl http://localhost:8000/api/v1/ai/crime-detection/status
```

### Test 3: Test with Swagger UI

```
http://localhost:8000/docs
```

## File Locations

| Item           | Path                                      |
| -------------- | ----------------------------------------- |
| Virtual Env    | `d:\Meridian App\backend\venv`        |
| Python         | `.\venv\Scripts\python.exe`               |
| Pip            | `.\venv\Scripts\pip.exe`                  |
| AI Service     | `app/services/ai/crime_vision_service.py` |
| API Endpoints  | `app/api/v1/endpoints/ai.py`              |
| Tests          | `tests/test_crime_vision.py`              |
| Model Download | `scripts/download_models.py`              |
| Requirements   | `requirements.txt`                        |
| Config         | `.env`                                    |

## Supported Crime Types

1. **Assault** - Person + weapon/injury signs
2. **Theft** - Person + valuable objects
3. **Vandalism** - Damaged property/graffiti
4. **Robbery** - Multiple people + valuables
5. **Burglary** - Person + indoor objects
6. **Harassment** - Multiple people in close proximity

## Performance Metrics

| Metric          | Value       |
| --------------- | ----------- |
| Analysis Time   | 2-3 seconds |
| Model Size      | 49 MB       |
| Memory Usage    | ~500 MB     |
| Accuracy Target | 70-75%      |
| Cost            | $0/month    |

## Common Issues & Fixes

### Issue: "Validation Error"

```powershell
# Create .env file
Copy-Item .env.example .env
# Edit with your values
```

### Issue: "Module not found"

```powershell
# Make sure you're using venv Python
.\venv\Scripts\python.exe your_script.py
```

### Issue: "Database connection failed"

```powershell
# Start PostgreSQL
docker-compose up -d postgres
```

### Issue: "Redis connection failed"

```powershell
# Start Redis
docker-compose up -d redis
```

### Issue: "Model not loaded"

```powershell
# Download model
.\venv\Scripts\python.exe scripts/download_models.py
```

## Environment Variables (Minimal)

```env
SECRET_KEY=your-secret-key-min-32-chars
JWT_SECRET_KEY=your-jwt-secret-min-32-chars
POSTGRES_USER=postgres
POSTGRES_PASSWORD=yourpassword
POSTGRES_DB=meridian
DATABASE_URL=postgresql+asyncpg://postgres:yourpassword@localhost:5432/meridian
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

## VS Code Settings

```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/venv/Scripts/python.exe",
  "python.terminal.activateEnvironment": true
}
```

## Port Usage

| Service            | Port  |
| ------------------ | ----- |
| Backend API        | 8000  |
| Frontend (Expo)    | 19000 |
| PostgreSQL         | 5432  |
| Redis              | 6379  |
| Flower (Celery UI) | 5555  |

## Useful Python Checks

```python
# Check PyTorch
import torch
print(torch.__version__)  # Should be 2.1.2
print(torch.cuda.is_available())  # False (CPU-only)

# Check Ultralytics
import ultralytics
print(ultralytics.__version__)  # Should be 8.1.34

# Check service
from app.services.ai.crime_vision_service import CrimeVisionService
service = CrimeVisionService()
service.load_models()
print("✅ Service loaded!")
```

## Documentation Index

1. **SETUP_COMPLETE.md** ← **START HERE**
2. IMPLEMENTATION_COMPLETE.md - Full setup guide
3. QUICK_START_10MIN.md - Fast track guide
4. AI_CRIME_ANALYSIS_PLAN.md - Architecture & phases
5. TECHNICAL_DEEP_DIVE.md - Model comparisons
6. VENV_SETUP.md - Virtual environment guide
7. VENV_STATUS.md - Current venv status
8. PHASE_1_COMPLETE.md - Project summary

---

**Status:** ✅ ALL PACKAGES INSTALLED  
**Next Step:** Create `.env` file and start testing!

---

_Quick Reference v1.0 - December 16, 2025_
