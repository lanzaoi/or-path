@echo off
REM Double-click friendly starter for OR-Path (keep window open).
setlocal EnableExtensions
cd /d "%~dp0"
if errorlevel 1 (
  echo [ERROR] cannot cd to install root
  pause
  exit /b 1
)
title OR-Path
chcp 65001 >nul 2>&1
echo.
echo  OR-Path 启动器
echo  Folder: %CD%
echo.
echo  [1] 菜单（完整控制台）
echo  [2] 实时过程台 Watch（默认圆管 live-btube）← 推荐一键看脸
echo  [3] 退出
echo.
set /p CHOICE=请选择 1/2/3（直接回车=2）: 
if "%CHOICE%"=="" set "CHOICE=2"
if "%CHOICE%"=="1" goto :menu
if "%CHOICE%"=="3" exit /b 0
if not "%CHOICE%"=="2" if not "%CHOICE%"=="1" (
  echo 无效选择，默认打开 Watch
)
goto :watch

:menu
call "%~dp0orpath.bat" menu
set "EC=%ERRORLEVEL%"
echo.
if not "%EC%"=="0" (
  echo [ERROR] exit code %EC%
  pause
  exit /b %EC%
)
pause
exit /b 0

:watch
call "%~dp0START-WATCH.bat"
exit /b %ERRORLEVEL%

