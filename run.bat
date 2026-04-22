@echo off
echo Starting the Finance App...
echo Access from this PC: http://localhost:8000
echo Access from phone (same WIFI): http://%COMPUTERNAME%:8000
echo.
cd /d "%~dp0"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
pause