@echo off
setlocal
set "ROOT=%~dp0.."
if exist "%ROOT%\.venv\Scripts\python.exe" (
    set "PY_BIN=%ROOT%\.venv\Scripts\python.exe"
) else (
    set "PY_BIN=python"
)
"%PY_BIN%" "%ROOT%\renamer.py" %*
exit /b %ERRORLEVEL%
