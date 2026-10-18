@echo off
REM Task Scheduler entry point (AmazonBeautyTracker, daily 05:15, wake-to-run) since 2026-10-18.
REM Only keeps the PC awake for the 05:30 Chrome collection (no Amazon requests).
REM The old tracker (run.bat / main.py) is retired - see CLAUDE.md.
REM ASCII ONLY in this file - cmd.exe reads .bat as cp949 on this PC.
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
echo. >> "data\run.log"
echo ===== %DATE% %TIME% ===== awake >> "data\run.log"
".venv\Scripts\python.exe" -u awake.py 110 >> "data\run.log" 2>&1
echo ===== exit %ERRORLEVEL% %TIME% >> "data\run.log"
