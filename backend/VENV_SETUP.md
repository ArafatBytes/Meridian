# Virtual Environment Setup for Meridian Backend

## Windows PowerShell Commands

### Step 1: Create Virtual Environment

```powershell
# Navigate to backend directory
cd "d:\Meridian App\backend"

# Create virtual environment named 'venv'
python -m venv venv
```

### Step 2: Activate Virtual Environment

```powershell
# Activate the virtual environment
.\venv\Scripts\Activate.ps1

# If you get execution policy error, run this first:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Then activate again:
.\venv\Scripts\Activate.ps1
```

**You should see `(venv)` at the beginning of your prompt.**

### Step 3: Upgrade pip (Important!)

```powershell
python -m pip install --upgrade pip
```

### Step 4: Install Dependencies in Order

```powershell
# Install core dependencies first (these are stable)
pip install fastapi==0.109.0
pip install uvicorn[standard]==0.27.0
pip install pydantic==2.5.3
pip install pydantic-settings==2.1.0
pip install python-multipart==0.0.6

# Database packages
pip install sqlalchemy==2.0.25
pip install asyncpg==0.29.0
pip install psycopg2-binary==2.9.9
pip install alembic==1.13.1
pip install geoalchemy2==0.14.3

# Authentication & Security
pip install python-jose[cryptography]==3.3.0
pip install passlib[bcrypt]==1.7.4
pip install python-dotenv==1.0.0
pip install bcrypt==4.1.2

# Redis & Caching
pip install redis==5.0.1
pip install aioredis==2.0.1
pip install hiredis==2.3.2

# Celery
pip install celery==5.3.6
pip install flower==2.0.1

# HTTP & WebSocket
pip install httpx==0.26.0
pip install websockets==12.0
pip install python-socketio==5.11.0

# Geospatial
pip install shapely==2.0.2
pip install geopy==2.4.1
pip install pyproj==3.6.1

# SMS & Notifications
pip install twilio==8.11.1
pip install firebase-admin==6.4.0

# Image Processing
pip install pillow==10.2.0
pip install opencv-python==4.9.0.80

# Google Cloud Services
pip install google-cloud-speech==2.24.0
pip install google-cloud-storage==2.14.0
pip install pydub==0.25.1

# File Storage
pip install boto3==1.34.34
pip install python-magic==0.4.27

# AI & Machine Learning (Install last - these are large!)
pip install numpy==1.26.3
pip install --default-timeout=300 torch==2.1.2
pip install --default-timeout=300 torchvision==0.16.2
pip install onnxruntime==1.16.3
pip install ultralytics==8.1.34
```

### Step 5: Verify Installation

```powershell
# Check installed packages
pip list

# Verify critical packages
python -c "import fastapi; print('FastAPI:', fastapi.__version__)"
python -c "import torch; print('PyTorch:', torch.__version__)"
python -c "import ultralytics; print('Ultralytics installed!')"
```

### Step 6: Download AI Models

```powershell
# Still in venv (you should see (venv) in prompt)
python scripts/download_models.py
```

### Step 7: Run the Backend Server

```powershell
# Start the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## Quick One-Line Install (Alternative)

If you want to try installing everything at once after creating venv:

```powershell
cd "d:\Meridian App\backend"
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install --default-timeout=300 -r requirements.txt
```

---

## Deactivate Virtual Environment

When you're done working:

```powershell
deactivate
```

---

## Troubleshooting

### Issue: "Activate.ps1 cannot be loaded"

**Solution:**

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Issue: "torch download timeout"

**Solution:**

```powershell
pip install --default-timeout=300 torch==2.1.2
```

### Issue: "Module not found after install"

**Solution:**
Make sure venv is activated (you should see `(venv)` in prompt)

### Issue: "Conflicts between packages"

**Solution:**
Delete venv and recreate:

```powershell
deactivate
Remove-Item -Recurse -Force venv
python -m venv venv
.\venv\Scripts\Activate.ps1
# Then install again
```

---

## VSCode Integration

### Set Python Interpreter to Virtual Environment

1. Open Command Palette: `Ctrl+Shift+P`
2. Type: `Python: Select Interpreter`
3. Choose: `.\venv\Scripts\python.exe`

OR

Create `.vscode/settings.json` in backend folder:

```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/venv/Scripts/python.exe",
  "python.terminal.activateEnvironment": true
}
```

---

## Daily Workflow

```powershell
# Start of day
cd "d:\Meridian App\backend"
.\venv\Scripts\Activate.ps1

# Do your work...
uvicorn app.main:app --reload

# End of day
deactivate
```

---

## Verify Everything Works

```powershell
# 1. Check Python version
python --version

# 2. Check venv is active
where python
# Should show: d:\Meridian App\backend\venv\Scripts\python.exe

# 3. Test imports
python -c "from app.services.ai.crime_vision_service import CrimeVisionService; print('✅ All imports work!')"

# 4. Check API
uvicorn app.main:app --reload
# Open: http://localhost:8000/docs
```

---

**Status:** Ready to create clean virtual environment!
**Estimated Time:** 10-15 minutes (depending on internet speed)
**Space Required:** ~2 GB for all packages
