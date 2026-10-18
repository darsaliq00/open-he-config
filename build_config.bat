@echo off
rem Builds release\M75Config.exe, the keyboard settings app (separate from Analog Drive)
cd /d "%~dp0"
set PY=.venv\Scripts\python.exe
%PY% -m pip install -q hidapi PySide6-Essentials pyinstaller || exit /b 1

%PY% -m PyInstaller --noconfirm --onefile --windowed --name M75Config --icon "%~dp0assets\icon.ico" ^
  --add-data "%~dp0assets;assets" --hidden-import hid --exclude-module tkinter --exclude-module vgamepad ^
  --distpath build\config --workpath build\work-config --specpath build run_config.py || exit /b 1

if not exist release mkdir release
copy /y build\config\M75Config.exe release\M75Config.exe >nul || (echo Quit the running M75Config.exe first, then build again. & exit /b 1)
echo.
echo Done: release\M75Config.exe
