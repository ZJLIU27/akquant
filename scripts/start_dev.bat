@echo off
setlocal enabledelayedexpansion

set "ROOT_DIR=%~dp0.."
for %%i in ("%ROOT_DIR%") do set "ROOT_DIR=%%~fi"
set "BACKEND_DIR=%ROOT_DIR%\apps\akquant_platform\backend"
set "FRONTEND_DIR=%ROOT_DIR%\apps\akquant_platform\frontend"

where py >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python launcher "py" not found. Install Python 3 and make sure it is on PATH.
    exit /b 1
)

where npm >nul 2>nul
if errorlevel 1 (
    echo ERROR: npm not found. Install Node.js and make sure npm is on PATH.
    exit /b 1
)

echo === AKQuant Platform Dev Mode ===
echo   Frontend: http://localhost:3000
echo   Backend:  http://localhost:8000
echo.

REM Start backend
cd /d "%BACKEND_DIR%"
start "AKQuant Backend" cmd /k py -3 -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

REM Start frontend
cd /d "%FRONTEND_DIR%"
if not exist "node_modules" (
    echo Installing frontend dependencies...
    call npm install
)
start "AKQuant Frontend" cmd /k npm run dev -- --host

echo.
echo Both servers started. Close the terminal windows to stop.
