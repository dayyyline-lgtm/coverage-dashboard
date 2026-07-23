@echo off
cd /d "%~dp0"
title 트렌드 갱신 (네이버 + 구글)

echo.
echo ============================================
echo   검색 트렌드 갱신
echo   (구글 트렌드는 집/회사 PC에서 실행하세요)
echo ============================================
echo.

echo [1/4] 네이버 데이터랩 + 구글 트렌드 수집 중...
echo   구글이 막히면 자동 재시도합니다. 잠시 기다리세요.
python fetch_trends.py

echo.
echo [2/4] 변경분 저장 중...
git add -A
git diff --cached --quiet
if not errorlevel 1 goto NOCHANGE
git commit -q -m "트렌드 갱신 %date%"

echo.
echo [3/4] 최신 내용 받는 중...
git pull --rebase -q
if errorlevel 1 goto FAIL_PULL

echo.
echo [4/4] 업로드 중...
git push -q
if errorlevel 1 goto FAIL_PUSH

echo.
echo ============================================
echo   완료!  1~2분 뒤 사이트에 반영됩니다.
echo ============================================
echo.
pause
exit /b 0

:NOCHANGE
echo   트렌드 변동이 없습니다 (또는 수집 실패).
echo   구글이 계속 막히면 몇 분 뒤 다시 실행해 보세요.
echo.
pause
exit /b 0

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
