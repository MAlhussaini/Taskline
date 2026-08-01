@echo off
net session >nul 2>&1
if %errorlevel% neq 0 (
  powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
  exit /b
)

netsh advfirewall firewall delete rule name="Taskline - Local Network" >nul 2>&1
netsh advfirewall firewall add rule name="Taskline - Local Network" dir=in action=allow protocol=TCP localport=8000 remoteip=LocalSubnet profile=any

echo.
echo Taskline network access is enabled.
echo You may close this window.
pause
