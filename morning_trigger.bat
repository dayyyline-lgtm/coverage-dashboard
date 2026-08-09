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

REM  events.yml COLLECTS ONLY since 2026-08-08. The daily letter is letter.yml,
REM  which now fires by itself when this run completes (workflow_run trigger).
REM  Do NOT relabel this line "daily-letter" again - that wrong label is exactly
REM  what hid the 2026-08-09 outage: the log said OK while no letter was sent.
%GH% workflow run events.yml --repo dayyyline-lgtm/coverage-dashboard --ref main >>"%LOG%" 2>&1
if errorlevel 1 (echo   FAIL collect ^(letter follows it^)>>"%LOG%") else (echo   OK   collect ^(letter follows it^)>>"%LOG%")

%GH% workflow run daily-briefing.yml --repo dayyyline-lgtm/news-bot --ref master >>"%LOG%" 2>&1
if errorlevel 1 (echo   FAIL news-bot>>"%LOG%") else (echo   OK   news-bot>>"%LOG%")

endlocal
