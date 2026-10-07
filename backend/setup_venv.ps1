# Meridian Backend - Virtual Environment Setup Script
# Run this script to automatically create and configure your Python virtual environment

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Meridian Backend - Virtual Environment Setup" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Check if we're in the right directory
if (-not (Test-Path "app")) {
    Write-Host "[x] Error: Please run this script from the backend directory" -ForegroundColor Red
    Write-Host "   Current directory: $PWD" -ForegroundColor Yellow
    Write-Host "   Expected: d:\Meridian App\backend" -ForegroundColor Yellow
    exit 1
}

Write-Host "[dir] Working directory: $PWD" -ForegroundColor Green
Write-Host ""

# Step 1: Check if venv exists
if (Test-Path "venv") {
    Write-Host "[!]  Virtual environment already exists!" -ForegroundColor Yellow
    $response = Read-Host "Do you want to delete and recreate it? (y/n)"
    if ($response -eq "y" -or $response -eq "Y") {
        Write-Host "[del]  Removing old virtual environment..." -ForegroundColor Yellow
        Remove-Item -Recurse -Force venv
        Write-Host "[ok] Old environment removed" -ForegroundColor Green
    } else {
        Write-Host "[x] Setup cancelled" -ForegroundColor Red
        exit 0
    }
}

# Step 2: Create virtual environment
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Step 1/6: Creating virtual environment..." -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
python -m venv venv

if ($LASTEXITCODE -ne 0) {
    Write-Host "[x] Failed to create virtual environment" -ForegroundColor Red
    exit 1
}
Write-Host "[ok] Virtual environment created successfully!" -ForegroundColor Green

# Step 3: Activate virtual environment
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Step 2/6: Activating virtual environment..." -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# Check execution policy
$policy = Get-ExecutionPolicy -Scope CurrentUser
if ($policy -eq "Restricted") {
    Write-Host "[!]  Execution policy is Restricted. Updating..." -ForegroundColor Yellow
    Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser -Force
    Write-Host "[ok] Execution policy updated" -ForegroundColor Green
}

# Activate
& .\venv\Scripts\Activate.ps1
Write-Host "[ok] Virtual environment activated!" -ForegroundColor Green

# Step 4: Upgrade pip
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Step 3/6: Upgrading pip..." -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
python -m pip install --upgrade pip --quiet
Write-Host "[ok] pip upgraded!" -ForegroundColor Green

# Step 5: Install dependencies
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Step 4/6: Installing dependencies..." -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "This will take 5-10 minutes. Please be patient..." -ForegroundColor Yellow
Write-Host ""

Write-Host "[pkg] Installing FastAPI and core packages..." -ForegroundColor Cyan
pip install --quiet fastapi==0.109.0 uvicorn[standard]==0.27.0 pydantic==2.5.3 pydantic-settings==2.1.0 python-multipart==0.0.6

Write-Host "[pkg] Installing database packages..." -ForegroundColor Cyan
pip install --quiet sqlalchemy==2.0.25 asyncpg==0.29.0 psycopg2-binary==2.9.9 alembic==1.13.1 geoalchemy2==0.14.3

Write-Host "[pkg] Installing authentication packages..." -ForegroundColor Cyan
pip install --quiet python-jose[cryptography]==3.3.0 passlib[bcrypt]==1.7.4 python-dotenv==1.0.0 bcrypt==4.1.2

Write-Host "[pkg] Installing Redis and Celery..." -ForegroundColor Cyan
pip install --quiet redis==5.0.1 aioredis==2.0.1 hiredis==2.3.2 celery==5.3.6 flower==2.0.1

Write-Host "[pkg] Installing HTTP and WebSocket packages..." -ForegroundColor Cyan
pip install --quiet httpx==0.26.0 websockets==12.0 python-socketio==5.11.0

Write-Host "[pkg] Installing geospatial libraries..." -ForegroundColor Cyan
pip install --quiet shapely==2.0.2 geopy==2.4.1 pyproj==3.6.1

Write-Host "[pkg] Installing notification services..." -ForegroundColor Cyan
pip install --quiet twilio==8.11.1 firebase-admin==6.4.0

Write-Host "[pkg] Installing image processing..." -ForegroundColor Cyan
pip install --quiet pillow==10.2.0 opencv-python==4.9.0.80

Write-Host "[pkg] Installing Google Cloud services..." -ForegroundColor Cyan
pip install --quiet google-cloud-speech==2.24.0 google-cloud-storage==2.14.0 pydub==0.25.1

Write-Host "[pkg] Installing file storage..." -ForegroundColor Cyan
pip install --quiet boto3==1.34.34 python-magic==0.4.27

Write-Host "[pkg] Installing AI packages (this takes the longest)..." -ForegroundColor Yellow
Write-Host "   - NumPy..." -ForegroundColor Gray
pip install --quiet numpy==1.26.3

Write-Host "   - PyTorch (large download ~200MB)..." -ForegroundColor Gray
pip install --default-timeout=300 torch==2.1.2

Write-Host "   - TorchVision..." -ForegroundColor Gray
pip install --default-timeout=300 torchvision==0.16.2

Write-Host "   - ONNX Runtime..." -ForegroundColor Gray
pip install --quiet onnxruntime==1.16.3

Write-Host "   - Ultralytics (YOLOv9)..." -ForegroundColor Gray
pip install --quiet ultralytics==8.1.34

Write-Host ""
Write-Host "[ok] All packages installed successfully!" -ForegroundColor Green

# Step 6: Verify installation
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Step 5/6: Verifying installation..." -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

$verificationPassed = $true

try {
    python -c "import fastapi; print('[ok] FastAPI:', fastapi.__version__)"
    python -c "import sqlalchemy; print('[ok] SQLAlchemy:', sqlalchemy.__version__)"
    python -c "import torch; print('[ok] PyTorch:', torch.__version__)"
    python -c "import ultralytics; print('[ok] Ultralytics: installed')"
    python -c "import cv2; print('[ok] OpenCV: installed')"
} catch {
    Write-Host "[x] Verification failed!" -ForegroundColor Red
    $verificationPassed = $false
}

if ($verificationPassed) {
    Write-Host ""
    Write-Host "[ok] All critical packages verified!" -ForegroundColor Green
}

# Step 7: Download AI models
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Step 6/6: Download AI models?" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
$downloadModels = Read-Host "Do you want to download YOLOv9 model now? (y/n)"

if ($downloadModels -eq "y" -or $downloadModels -eq "Y") {
    Write-Host ""
    Write-Host "[get] Downloading YOLOv9 model (~12 MB)..." -ForegroundColor Cyan
    python scripts/download_models.py
} else {
    Write-Host ">>  Skipped model download. Run 'python scripts/download_models.py' later." -ForegroundColor Yellow
}

# Final summary
Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "  [done] Setup Complete!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Your virtual environment is ready at:" -ForegroundColor White
Write-Host "  $PWD\venv" -ForegroundColor Cyan
Write-Host ""
Write-Host "[info] Next Steps:" -ForegroundColor Yellow
Write-Host ""
Write-Host "1. Activate the environment:" -ForegroundColor White
Write-Host "   .\venv\Scripts\Activate.ps1" -ForegroundColor Cyan
Write-Host ""
Write-Host "2. Start the server:" -ForegroundColor White
Write-Host "   uvicorn app.main:app --reload" -ForegroundColor Cyan
Write-Host ""
Write-Host "3. Test the API:" -ForegroundColor White
Write-Host "   http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "4. Download models (if you skipped):" -ForegroundColor White
Write-Host "   python scripts/download_models.py" -ForegroundColor Cyan
Write-Host ""
Write-Host "[tip] Tip: In VSCode, select Python interpreter:" -ForegroundColor Yellow
Write-Host "   Ctrl+Shift+P -> Python: Select Interpreter -> .\venv\Scripts\python.exe" -ForegroundColor Gray
Write-Host ""
Write-Host "============================================================" -ForegroundColor Green

# Keep window open
Write-Host ""
Write-Host "Press any key to exit..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
