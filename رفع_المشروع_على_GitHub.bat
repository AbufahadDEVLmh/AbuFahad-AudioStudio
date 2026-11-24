@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ========================================================
echo   جاري رفع مشروع كرت الصوت إلى GitHub (@tolld597)...
echo ========================================================
python upload_to_github.py
if errorlevel 1 (
    echo [خطأ] حدث خطأ أثناء الرفع!
    pause
    exit /b 1
)
echo.
echo تم الرفع بنجاح! اضغط أي زر للإغلاق.
pause >nul
