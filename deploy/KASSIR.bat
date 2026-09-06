@echo off
chcp 65001 >nul
title SmartKassa - kassir kompyuteriga yorliq
echo.
echo   ======================================================
echo    SmartKassa - KASSIR kompyuteriga sozlash
echo   ======================================================
echo.
echo   Bu kompyuterga HECH NARSA o'rnatilmaydi.
echo   Faqat ish stoliga "SmartKassa" yorlig'i qo'yiladi -
echo   u brauzerni ochib, do'kon serveriga ulanadi.
echo.
echo   Tayyorlang: do'kon SERVER kompyuterining IP manzili
echo   (masalan  192.168.100.17 ).
echo.
pause
echo.
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; iex (irm https://raw.githubusercontent.com/mirazizGG/Kassa/main/deploy/scripts/kassir-setup.ps1)"
echo.
pause
