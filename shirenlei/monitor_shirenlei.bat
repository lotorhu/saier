@echo off
setlocal

set "processName=python.exe"
set "pythonScript=E:\Saier\saier\shirenlei.py"

:check_process
tasklist | findstr /i "%processName%" >nul
if errorlevel 1 (
    echo %processName% not exist...
    start "" /B cmd /c "python %pythonScript%"
)

timeout /t 5 /nobreak >nul
goto check_process