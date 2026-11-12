@echo off
setlocal
cd /d "%~dp0"
echo ===============================================
echo LMS FaceID V3.3 - Test HTTP, MySQL, login, FaceID
echo ===============================================
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\windows_lms.ps1" -Action Test
set "LMS_RC=%errorlevel%"
echo.
if not "%LMS_RC%"=="0" echo TEST FAILED: see LMS_V33_LAST_RUN.log and DIAGNOSE_LMS_WINDOWS.bat
if "%LMS_RC%"=="0" echo TEST PASSED: see detail above
pause
exit /b %LMS_RC%
