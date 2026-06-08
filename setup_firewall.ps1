# ============================================================
# setup_firewall.ps1 - Flask 앱 포트 5000 방화벽 자동 허용
# 관리자 권한으로 한 번만 실행: 우클릭 → PowerShell로 실행
# ============================================================

$AppName = "NaverBlogAuto"
$Port    = 5000
$PythonPath = (Get-Command python -ErrorAction SilentlyContinue).Source

Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "  N블로그 자동화 - 방화벽 자동 설정"   -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan

# 기존 규칙 제거 후 재등록
Remove-NetFirewallRule -DisplayName "$AppName*" -ErrorAction SilentlyContinue

# TCP 포트 5000 인바운드 허용
New-NetFirewallRule `
  -DisplayName "$AppName-Port-$Port" `
  -Direction Inbound `
  -Action Allow `
  -Protocol TCP `
  -LocalPort $Port `
  -Profile Any `
  -Description "N블로그 자동화 Flask 웹앱 - 모바일 WiFi 접속용" `
  | Out-Null

# Python.exe 자체 허용 (인바운드)
if ($PythonPath) {
  New-NetFirewallRule `
    -DisplayName "$AppName-Python-In" `
    -Direction Inbound `
    -Action Allow `
    -Program $PythonPath `
    -Profile Any `
    | Out-Null
  Write-Host "✅ Python 실행파일 방화벽 허용: $PythonPath" -ForegroundColor Green
}

# 아웃바운드도 허용
New-NetFirewallRule `
  -DisplayName "$AppName-Port-Out" `
  -Direction Outbound `
  -Action Allow `
  -Protocol TCP `
  -LocalPort $Port `
  -Profile Any `
  | Out-Null

Write-Host "✅ TCP 포트 $Port 인바운드 허용 완료" -ForegroundColor Green
Write-Host "✅ TCP 포트 $Port 아웃바운드 허용 완료" -ForegroundColor Green
Write-Host ""
Write-Host "📱 이제 같은 WiFi의 모바일에서 아래 주소로 접속하세요:" -ForegroundColor Yellow

# IP 자동 표시
$IP = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -like "192.*" -or $_.IPAddress -like "10.*" } | Select-Object -First 1).IPAddress
if ($IP) {
  Write-Host "   http://$($IP):$Port" -ForegroundColor White
} else {
  Write-Host "   http://[PC의 IP]:$Port" -ForegroundColor White
}

Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "  설정 완료! 이 창을 닫으셔도 됩니다." -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Read-Host "엔터를 누르면 종료"
