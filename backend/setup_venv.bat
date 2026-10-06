@echo off
REM Meridian Backend - Quick Virtual Environment Setup
REM This is a simplified version - use setup_venv.ps1 for interactive setup

echo ============================================================
echo   Meridian Backend - Virtual Environment Setup
echo ============================================================
echo.

REM Check if we're in the right directory
if not exist "app" (
    echo ERROR: Please run this script from the backend directory
    echo Current directory: %CD%
    pause
    exit /b 1
)

echo Working directory: %CD%
echo.

REM Step 1: Create virtual environment
echo ============================================================
echo Step 1: Creating virtual environment...
echo ============================================================
python -m venv venv
if errorlevel 1 (
    echo ERROR: Failed to create virtual environment
    pause
    exit /b 1
)
echo SUCCESS: Virtual environment created!
echo.

REM Step 2: Activate and upgrade pip
echo ============================================================
echo Step 2: Upgrading pip...
echo ============================================================
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
echo SUCCESS: pip upgraded!
echo.

REM Step 3: Install all dependencies
echo ============================================================
echo Step 3: Installing all dependencies...
echo This will take 5-10 minutes. Please wait...
echo ============================================================
pip install --default-timeout=300 -r requirements.txt
if errorlevel 1 (
    echo WARNING: Some packages may have failed to install
    echo Please check the output above for errors
) else (
    echo SUCCESS: All packages installed!
)
echo.

REM Step 4: Verify
echo ============================================================
echo Step 4: Verifying installation...
echo ============================================================
python -c "import fastapi; print('FastAPI: OK')"
python -c "import torch; print('PyTorch: OK')"
python -c "import ultralytics; print('Ultralytics: OK')"
echo.

REM Final message
echo ============================================================
echo   Setup Complete!
echo ============================================================
echo.
echo Your virtual environment is ready!
echo.
echo Next steps:
echo 1. Activate: venv\Scripts\activate.bat
echo 2. Download models: python scripts\download_models.py
echo 3. Start server: uvicorn app.main:app --reload
echo 4. Test API: http://localhost:8000/docs
echo.
echo ============================================================
pause
