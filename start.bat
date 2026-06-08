@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
title N블로그 자동화

echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo   N블로그 자동화 웹앱 시작 중...
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

cd /d "%~dp0"

REM ── 방화벽 자동 허용 (포트 5000) ────────────────────────────
netsh advfirewall firewall delete rule name="NaverBlogAuto-5000" >nul 2>&1
netsh advfirewall firewall add rule name="NaverBlogAuto-5000" ^
  dir=in action=allow protocol=TCP localport=5000 profile=any >nul 2>&1
netsh advfirewall firewall add rule name="NaverBlogAuto-5000-out" ^
  dir=out action=allow protocol=TCP localport=5000 profile=any >nul 2>&1
echo [OK] 방화벽 포트 5000 허용

REM ── 파이썬 패키지 확인 ──────────────────────────────────────
pip install -r requirements.txt -q >nul 2>&1
echo [OK] 패키지 확인 완료

REM ── IP 주소 표시 ────────────────────────────────────────────
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /C:"IPv4 Address"') do (
  set "RAW=%%a"
  set "IP=!RAW: =!"
)

echo.
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo   PC 접속:     http://localhost:5000
if defined IP echo   모바일 접속:  http://!IP!:5000
echo   (같은 WiFi 연결 필요)
echo ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
echo.

REM ── 앱 실행 ─────────────────────────────────────────────────
python -X utf8 app.py
pause
