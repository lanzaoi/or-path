#!/usr/bin/env bash
systemctl --user stop orpath-pi-loop.service 2>/dev/null || true
systemctl --user reset-failed orpath-pi-loop.service 2>/dev/null || true
pkill -f run_pi_plan_loop.py 2>/dev/null || true
echo "[OK] All background Pi loop processes stopped."
