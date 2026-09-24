@echo off
REM Task Scheduler entry point (AmazonBeautyTracker, daily 05:15, wake-to-run).
REM Console output is appended to data\run.log (the scheduler shows no window).
REM
REM ASCII ONLY in this file - cmd.exe reads .bat as cp949 on this PC and a
REM single non-ASCII byte silently breaks the whole line (verified 2026-08-05).
REM
REM 2026-09-24 (see the repo plan file, Phase 0):
REM   -u  : unbuffered stdout. When the process died mid-run the block-buffered
REM         log came back EMPTY (12 blank runs Aug-Sep) so nothing could be diagnosed.
REM   main.py itself now holds the system awake (SetThreadExecutionState) and waits
REM   for the network before the first request - the PC used to fall back asleep
REM   about 2 minutes after the timer wake and the Wi-Fi was not up yet.
REM   %1 is passed through: run.bat --skip-if-done  (second-chance task at 06:45).
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set PYTHONUNBUFFERED=1
echo. >> "data\run.log"
echo ===== %DATE% %TIME% ===== %* >> "data\run.log"
".venv\Scripts\python.exe" -u main.py %* >> "data\run.log" 2>&1
echo ===== exit %ERRORLEVEL% %TIME% >> "data\run.log"
