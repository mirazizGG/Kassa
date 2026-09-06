@echo off
chcp 65001 >nul
title SmartKassa - do'kon serveriga o'rnatish
echo.
echo   ======================================================
echo    SmartKassa o'rnatuvchi
echo   ======================================================
echo.
echo   Hozir hamma narsa avtomatik o'rnatiladi:
echo     - Python va Git (yo'q bo'lsa)
echo     - Dastur kodi (GitHub'dan)
echo     - Kutubxonalar, sozlamalar, LAN rejimi
echo     - Ishga tushirish + kompyuter yonganda avtomat ishlash
echo.
echo   "Administrator huquqi kerak" oynasi chiqsa - "Ha" (Yes) deng.
echo.
pause
echo.
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; iex (irm https://raw.githubusercontent.com/mirazizGG/Kassa/main/deploy/install-smartkassa.ps1)"
echo.
echo   ======================================================
echo    Tugadi. Yuqoridagi manzil (http://...:8000) bilan kiring.
echo   ======================================================
echo.
pause
