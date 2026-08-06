@echo off
REM ============================================================
REM  Morning trigger - fires the daily letter and the news bot.
REM  Windows Task Scheduler calls this at 05:35 (CoverageMorningTrigger).
REM
REM  ASCII ONLY. cmd.exe reads .bat in cp949 on this machine; UTF-8 Korean
REM  breaks whole lines (verified 2026-08-06 - the file silently did nothing
REM  and still exited 0). Korean notes live in morning_trigger.md instead.
REM ============================================================
setlocal
set GH="C:\Program Files\GitHub CLI\gh.exe"
set LOG=%~dp0morning_trigger.log

echo.>>"%LOG%"
echo ===== %DATE% %TIME% =====>>"%LOG%"

%GH% workflow run events.yml --repo dayyyline-lgtm/coverage-dashboard --ref main >>"%LOG%" 2>&1
if errorlevel 1 (echo   FAIL daily-letter>>"%LOG%") else (echo   OK   daily-letter>>"%LOG%")

%GH% workflow run daily-briefing.yml --repo dayyyline-lgtm/news-bot --ref master >>"%LOG%" 2>&1
if errorlevel 1 (echo   FAIL news-bot>>"%LOG%") else (echo   OK   news-bot>>"%LOG%")

endlocal
