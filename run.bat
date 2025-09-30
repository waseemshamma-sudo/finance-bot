@echo off
chcp 65001 > nul
title 🤖 بوت إدارة الحسابات المالية الحديث
echo ========================================
echo   🤖  تشغيل بوت إدارة الحسابات المالية الحديث
echo ========================================
echo.

cd /d "C:\Users\Admin\finance"

REM التحقق من وجود ملف البيئة
if not exist ".env" (
    echo ❌ ملف .env غير موجود!
    echo 📋 يرجى إنشاء ملف .env وإضافة التوكن
    echo.
    pause
    exit
)

REM التحقق من تثبيت بايثون
python --version > nul 2>&1
if errorlevel 1 (
    echo ❌ بايثون غير مثبت أو غير مضاف إلى PATH
    echo 📋 يرجى تثبيت بايثون من python.org
    echo.
    pause
    exit
)

REM التحقق من تثبيت المتطلبات
python -c "import telegram" > nul 2>&1
if errorlevel 1 (
    echo 📦 جاري تثبيت المتطلبات...
    pip install python-telegram-bot pandas openpyxl python-dotenv
    echo.
)

echo 🚀 جاري تشغيل البوت...
echo 📋 اضغط Ctrl+C لإيقاف البوت
echo.

REM تشغيل البوت مباشرة (بدون main.py)
python finance.py

echo.
echo ========================================
echo   ⏹️  تم إيقاف البوت
echo ========================================
pause