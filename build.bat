@echo off
rem Builds release\OpenHEConfig-Portable.exe (single file) and release\OpenHEConfig-<version>-Setup.exe
rem VERSION defaults to 1.0.0; the release workflow sets it. PY picks the Python to build with.
cd /d "%~dp0"
if not defined VERSION set VERSION=1.0.0
if not defined PY set PY=.venv\Scripts\python.exe
"%PY%" -m pip install -q -r requirements.txt pyinstaller || exit /b 1

set COMMON=--noconfirm --windowed --name OpenHEConfig --icon "%~dp0assets\icon.ico" --add-data "%~dp0assets;assets" --hidden-import hid --exclude-module tkinter run_config.py

rem portable: one self-contained exe, keeps its data next to itself
"%PY%" -m PyInstaller --onefile --distpath build\portable --workpath build\work-portable --specpath build %COMMON% || exit /b 1
rem installer payload: folder build, starts faster than onefile
"%PY%" -m PyInstaller --onedir --distpath dist --workpath build\work-dir --specpath build %COMMON% || exit /b 1

if not exist release mkdir release
copy /y build\portable\OpenHEConfig.exe release\OpenHEConfig-Portable.exe >nul || (echo Quit the running OpenHEConfig-Portable.exe first, then build again. & exit /b 1)

set ISCC=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe
if not exist "%ISCC%" set ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe
"%ISCC%" /Q /DAppVersion=%VERSION% build_tools\installer.iss || exit /b 1
echo.
echo Done: release\OpenHEConfig-Portable.exe and release\OpenHEConfig-%VERSION%-Setup.exe
