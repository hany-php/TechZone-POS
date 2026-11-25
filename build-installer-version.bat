@echo off
cd /d "%~dp0"
setlocal

python --version >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python not found.
    pause
    exit /b 1
)

rem --- Auto-increment version in version.txt ---
if not "%~1"=="" (
    echo %~1>version.txt
) else (
    python -c "import os, re; f='version.txt'; raw=open(f,encoding='utf-8').read().strip() if os.path.exists(f) else ''; m=re.search(r'(\d+)\.(\d+)\.(\d+)', raw); v=[int(x) for x in m.groups()] if m else [1,0,0]; v[-1]+=1; ver='.'.join(map(str,v)); open(f,'w',encoding='utf-8').write(ver+'\n')"
)
set /p APP_VERSION=<version.txt
echo [INFO] Building Version: %APP_VERSION%

python -c "import PyInstaller" 2>nul || python -m pip install pyinstaller
python -c "import webview" 2>nul || python -m pip install pywebview

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo [1/3] Building dist\TechZone.exe via PyInstaller...
python -m PyInstaller --noconfirm --clean --name TechZone --windowed --onefile --icon "icon.ico" --add-data "web;web" --add-data "icon.ico;." --add-data "version.txt;." app\main.py || (echo [ERROR] PyInstaller build failed & pause & exit /b 1)

set "ISCC="
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined ISCC (
    echo [ERROR] Inno Setup 6 ISCC.exe not found. Install Inno Setup 6 and retry.
    pause
    exit /b 1
)

echo [2/3] Compiling Inno Setup installer (v%APP_VERSION%)...
"%ISCC%" "/DMyAppVersion=%APP_VERSION%" "installer\TechZone.iss" || (echo [ERROR] Inno Setup compile failed & pause & exit /b 1)

echo [3/3] Generating SHA-256 checksums...
powershell -NoProfile -Command "Get-ChildItem 'dist\TechZone*.exe' | ForEach-Object { $h = (Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLower(); \"$h  $($_.Name)\" } | Set-Content -Encoding UTF8 'dist\SHA256SUMS.txt'"

echo.
echo Setup Ready: "%~dp0dist\TechZone-Setup-v%APP_VERSION%.exe"
pause