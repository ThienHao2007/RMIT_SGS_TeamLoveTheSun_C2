@echo off
setlocal
pushd "%~dp0"
if errorlevel 1 exit /b 1

echo =========================================================
echo   QUORUM-GOVERNED API GUARD - SETUP
echo =========================================================
echo Requires Python 3.12+ and Node.js 22.12+ with npm on PATH.
echo Existing administrator keys and databases are preserved.
echo.

python -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 'Python 3.12+ is required.')"
if errorlevel 1 goto failed
node -e "const [major, minor] = process.versions.node.split('.').map(Number); if (major < 22 || (major === 22 && minor < 12)) { console.error('Node.js 22.12+ is required.'); process.exit(1); }"
if errorlevel 1 goto failed

echo [1/4] Creating the local Python environment...
python -m venv .venv
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 'The .venv environment requires Python 3.12+.')"
if errorlevel 1 goto failed

echo [2/4] Installing Python dependencies...
".venv\Scripts\python.exe" -m pip install -r requirements-dev.txt
if errorlevel 1 goto failed

echo [3/4] Installing and building the UI...
call npm --prefix ui ci
if errorlevel 1 goto failed
call npm --prefix ui run build
if errorlevel 1 goto failed

echo [4/4] Generating missing administrator keypairs...
".venv\Scripts\python.exe" scripts\gen_keys.py
if errorlevel 1 goto failed

echo.
echo Setup completed. Run these commands from any directory:
echo   "%CD%\.venv\Scripts\python.exe" "%CD%\run.py"
echo   "%CD%\.venv\Scripts\python.exe" "%CD%\demo.py"
popd
exit /b 0

:failed
echo.
echo ERROR: Setup stopped because a required step failed. See the error above.
echo Install Python 3.12+ and Node.js 22.12+ if missing, then rerun setup.
popd
exit /b 1
