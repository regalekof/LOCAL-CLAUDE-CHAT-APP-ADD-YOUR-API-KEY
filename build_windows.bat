@echo off
setlocal
cd /d "%~dp0"

echo.
echo === 1/4  Building frontend ===
pushd frontend
call npm install
if errorlevel 1 goto fail
call npm run build
if errorlevel 1 goto fail
popd

echo.
echo === 2/4  Python build environment ===
if exist .venv-build goto venv_ready
python -m venv .venv-build
if errorlevel 1 goto fail
:venv_ready
call .venv-build\Scripts\activate.bat
python -m pip install -q --upgrade pip
pip install -q -r backend\requirements.txt -r packaging\requirements-desktop.txt
if errorlevel 1 goto fail

echo.
echo === 3/4  Building AgentChat.exe ===
pyinstaller --noconfirm --clean --distpath release\dist --workpath release\build packaging\AgentChat.spec
if errorlevel 1 goto fail

echo.
echo === Smoke test ===
start /wait "" release\dist\AgentChat.exe --selftest
if errorlevel 1 (
  echo Smoke test FAILED. See %APPDATA%\AgentChat\agentchat.log
  goto fail
)
echo Smoke test passed.

echo.
echo === 4/4  Installer (optional, needs Inno Setup 6) ===
set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" goto no_inno
set /p VER=<VERSION
"%ISCC%" /DAppVersion=%VER% packaging\AgentChat.iss
if errorlevel 1 goto fail
echo.
echo DONE.  Installer: release\AgentChat-Setup-%VER%.exe
echo        Portable:  release\dist\AgentChat.exe
goto end

:no_inno
echo Inno Setup not found, skipping the installer (get it free from jrsoftware.org/isdl.php).
echo.
echo DONE.  Portable app: release\dist\AgentChat.exe  (double-click it)
goto end

:fail
echo.
echo BUILD FAILED. Scroll up to see the error.
pause
exit /b 1

:end
pause
