@echo off
echo =======================================================================
echo Adaptive MVCC-Based Transaction Management and Recovery Framework
echo For Asynchronous Federated Learning
echo =======================================================================
echo.

set SCRIPT_DIR=%~dp0
set BACKEND_DIR=%SCRIPT_DIR%backend
set FRONTEND_DIR=%SCRIPT_DIR%frontend
set PYTHON_EXE=%SCRIPT_DIR%venv\Scripts\python.exe

if not exist "%PYTHON_EXE%" (
    echo [ERROR] Virtual environment not found at %PYTHON_EXE%
    pause
    exit /b 1
)

echo [1/3] Starting Backend API Server (FastAPI + Custom DBMS Engine on :8000)...
start "Adaptive-MVCC-Backend" cmd /k "cd /d "%BACKEND_DIR%" && set PYTHONPATH=%BACKEND_DIR% && "%PYTHON_EXE%" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"

echo [2/3] Starting Frontend Dashboard (React + Vite on :5173)...
start "Adaptive-MVCC-Frontend" cmd /k "cd /d "%FRONTEND_DIR%" && npm run dev"

echo [3/3] Opening Browser...
timeout /t 3 /nobreak > nul
start http://localhost:5173

echo.
echo =======================================================================
echo System is running!
echo Frontend Dashboard: http://localhost:5173
echo Backend API Docs:   http://127.0.0.1:8000/docs
echo =======================================================================
pause
