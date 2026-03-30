@echo off
:: Pull latest code and refresh dependencies — servers keep running.
:: uvicorn --reload auto-detects Python changes; Vite HMR handles the UI.
setlocal
cd /d "%~dp0"

echo.
echo  SEO Blog Engine — Update
echo  ================================
echo.

echo [1/3] Pulling latest code...
git pull
if %errorlevel% neq 0 (
    echo ERROR: git pull failed.
    pause & exit /b 1
)

echo [2/3] Updating API dependencies...
pip install -r api/requirements.txt --quiet
if %errorlevel% neq 0 (
    echo ERROR: pip install failed.
    pause & exit /b 1
)

echo [3/3] Updating UI dependencies...
cd ui
npm install --silent
cd ..

echo.
echo  Done. uvicorn will auto-reload changed Python files.
echo  The UI hot-reloads automatically via Vite HMR.
echo  No server restart needed.
echo.
pause
