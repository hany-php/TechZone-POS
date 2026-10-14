@echo off
chcp 65001 >nul
rem TechZone POS — رفع التعديلات إلى GitHub بضغطة واحدة
cd /d "%~dp0"

where git >nul 2>nul || (
    echo [ERROR] برنامج Git غير مثبت على جهازك. حمّله من https://git-scm.com
    pause
    exit /b 1
)

if not exist .git (
    echo [*] جاري تهيئة مستودع Git المحلي...
    git init
    git branch -M main
)

git add -A
git commit -m "Complete TechZone POS: customer debt ledger, vouchers, custom permissions, tax toggle, wallet ref, Egypt settings" 2>nul || echo [*] لا توجد تغييرات جديدة غير محفوظة.

for /f "delims=" %%i in ('git remote 2^>nul') do set HAS_REMOTE=1
if not defined HAS_REMOTE (
    echo.
    set /p REPO_URL="أدخل رابط مستودع GitHub (مثال https://github.com/username/TechZone-POS.git): "
    if not defined REPO_URL (
        echo [!] لم يتم إدخال الرابط. تم حفظ التعديلات محلياً في Git.
        pause
        exit /b 0
    )
    git remote add origin "%REPO_URL%"
)

echo.
echo [*] جاري رفع التعديلات إلى GitHub (فرع main)...
git push -u origin main
echo.
pause
