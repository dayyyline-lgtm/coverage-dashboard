@echo off
REM 작업 스케줄러가 매일 아침 호출하는 진입점.
REM 콘솔 출력은 data\run.log 에 누적된다 (스케줄러는 화면을 안 보여주므로).
cd /d "%~dp0"
REM 스케줄러가 stdout 을 파일로 넘기면 파이썬이 cp949 를 쓴다. cp949 에 없는
REM 글자(— 등)가 print 에 하나만 있어도 수집 전체가 죽는다(2026-08-05 실제 사고).
REM main.py 안에서도 stdout 을 UTF-8 로 고정해 두었지만, 여기서도 한 번 더 막는다.
set PYTHONIOENCODING=utf-8
echo. >> "data\run.log"
echo ===== %DATE% %TIME% ===== >> "data\run.log"
".venv\Scripts\python.exe" main.py >> "data\run.log" 2>&1
