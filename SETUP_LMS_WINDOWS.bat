@echo off
setlocal
cd /d "%~dp0"
echo ===============================================
echo LMS FaceID - Setup (Nam + Thanh)
echo ===============================================
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows_lms.ps1" -Action Setup
set "LMS_RC=%errorlevel%"
echo.
if not "%LMS_RC%"=="0" echo FAILED. Review the error messages above.
if "%LMS_RC%"=="0" echo Completed.
pause
exit /b %LMS_RC%
