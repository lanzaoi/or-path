@echo off
chcp 65001 >nul
echo ============================================================================
echo   Stopping OR-Path Ralph Pi Autonomous Loop...
echo ============================================================================
wsl.exe -d archlinux -- bash -lc "systemctl --user stop orpath-pi-loop.service 2>/dev/null; systemctl --user reset-failed orpath-pi-loop.service 2>/dev/null; pkill -f run_pi_plan_loop.py 2>/dev/null; echo '[OK] All background Pi loop processes stopped.'"
pause
