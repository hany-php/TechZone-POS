@echo off
rem TechZone build: double-click rebuilds dist\TechZone\TechZone.exe (run from repo root, any cwd ok)
cd /d "%~dp0"
where python >nul 2>nul || (echo [ERROR] python not found & pause & exit /b 1)
python -m pip --version >nul 2>nul || (echo [ERROR] pip not found & pause & exit /b 1)
python -c "import PyInstaller" 2>nul || python -m pip install pyinstaller
python -c "import webview" 2>nul || python -m pip install pywebview
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
python -m PyInstaller --noconfirm --clean --name TechZone --windowed --onefile --add-data "web;web" app\main.py
echo.
echo EXE: "%~dp0dist\TechZone\TechZone.exe"
pause
