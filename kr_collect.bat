@echo off
REM Korean-IP collectors (game money + Olive Young) -> push. Task Scheduler: KrCollect.
REM ASCII ONLY - cmd.exe reads .bat as cp949 here; one non-ASCII byte breaks a line.
REM Runs from its OWN clone (C:\Users\dayline\Downloads\coverage-kr), not the main clone:
REM the Amazon tracker leaves the main clone dirty and kr_collect.py refuses dirty trees
REM (that is why GAMEMONEY sat at 2026-09-21 for two weeks - fixed 2026-10-04).
REM "python" on this PC is the Microsoft Store stub, so use the py launcher.
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
echo ===== %DATE% %TIME% >> kr_collect.log
py -3 -u kr_collect.py >> kr_collect.log 2>&1
echo ===== exit %ERRORLEVEL% %TIME% >> kr_collect.log
