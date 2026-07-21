@echo off
cd /d "%~dp0"
title 커버리지 대시보드 업데이트

echo.
echo ============================================
echo   커버리지 대시보드 업데이트
echo ============================================
echo.

echo [1/5] 유니버스 엑셀 반영 중...
python rebuild_from_excel.py
if errorlevel 1 goto FAIL_XLSX

echo.
echo [2/5] 시세 리포트 수집 중...
python refresh_live.py

echo.
echo [3/5] 변경분 저장 중...
git add -A
git diff --cached --quiet
if not errorlevel 1 goto NOCHANGE
git commit -q -m "대시보드 업데이트 %date%"

echo.
echo [4/5] 최신 내용 받는 중...
git pull --rebase -q
if errorlevel 1 goto FAIL_PULL

echo.
echo [5/5] 업로드 중...
git push -q
if errorlevel 1 goto FAIL_PUSH

echo.
echo ============================================
echo   완료!  1~2분 뒤 사이트에 반영됩니다.
echo   https://coverage-dashboard.pages.dev
echo ============================================
echo.
pause
exit /b 0

:NOCHANGE
echo   변경된 내용이 없습니다.
echo.
echo ============================================
echo   완료 - 업데이트할 내용 없음
echo ============================================
echo.
pause
exit /b 0

:FAIL_XLSX
echo.
echo   [실패] 엑셀을 읽지 못했습니다.
echo   엑셀 파일이 열려 있으면 닫고 다시 실행하세요.
echo.
pause
exit /b 1

:FAIL_PULL
echo.
echo   [실패] 충돌이 발생했습니다. 이 화면을 캡처해서 문의하세요.
echo.
pause
exit /b 1

:FAIL_PUSH
echo.
echo   [실패] 업로드 실패. 로그인 정보가 만료됐을 수 있습니다.
echo.
pause
exit /b 1
