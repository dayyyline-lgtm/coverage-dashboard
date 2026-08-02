@echo off
REM 작업 스케줄러가 매일 아침 호출하는 진입점.
REM 콘솔 출력은 data\run.log 에 누적된다 (스케줄러는 화면을 안 보여주므로).
cd /d "%~dp0"
echo. >> "data\run.log"
echo ===== %DATE% %TIME% ===== >> "data\run.log"
".venv\Scripts\python.exe" main.py >> "data\run.log" 2>&1
