@echo off
REM 한국 IP 전용 수집(게임머니·올리브영) — 작업 스케줄러 진입점. 로그는 kr_collect.log 에 누적.
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
python kr_collect.py >> kr_collect.log 2>&1
