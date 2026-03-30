@echo off
setlocal

cd /d "%~dp0"

echo.
echo  SEO Blog Engine — Starting...
echo  ================================
echo.

:: Install API dependencies
echo [1/3] Installing API dependencies...
pip install -r api/requirements.txt --quiet
if %errorlevel% neq 0 (
    echo ERROR: pip install failed. Make sure Python is on PATH.
    pause
    exit /b 1
)

:: Install UI dependencies
echo [2/3] Installing UI dependencies...
cd ui
if not exist node_modules (
    echo      Running npm install...
    npm install --silent
    if %errorlevel% neq 0 (
        echo ERROR: npm install failed. Make sure Node.js is on PATH.
        pause
        exit /b 1
    )
) else (
    echo      node_modules exists, skipping install.
)
cd ..

:: Start both servers
echo [3/3] Starting servers...
echo.
echo  API server  →  http://localhost:8000
echo  UI  server  →  http://localhost:5173
echo  API docs    →  http://localhost:8000/docs
echo.
echo  Press Ctrl+C in either window to stop.
echo.

start "SEO Engine — API" cmd /k "cd /d "%~dp0" && uvicorn api.main:app --reload --reload-dir api --reload-dir publishers --port 8000"
timeout /t 2 /nobreak > nul
start "SEO Engine — UI" cmd /k "cd /d "%~dp0ui" && npm run dev"

echo Both servers are starting in separate windows.
pause
