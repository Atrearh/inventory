@echo off
cd /d C:\Users\semen\inv
call C:\Users\semen\inv\.venv\Scripts\activate.bat
C:\Users\semen\inv\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 >> C:\Users\semen\inv\logs\uvicorn.log 2>&1