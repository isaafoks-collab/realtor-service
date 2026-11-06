@echo off
chcp 65001 >nul
title PRAYMO - podborka sobstvennikov
rem BOT: osnovnoi. Istochnik: okruzhenie (BOT_TOKEN) libo lokalnyi fail tokenty.txt.
rem Znacheniya ni v okno, ni v log ne vyvodyatsya.
if not defined BOT_TOKEN if exist "%~dp0токены.txt" (
    for /f "usebackq tokens=1,* delims== eol=#" %%a in ("%~dp0токены.txt") do set "%%a=%%b"
)
if not defined BOT_TOKEN (
    echo OSIBKA: ne zadan BOT_TOKEN.
    echo Zadayte peremennuyu okruzheniya: setx BOT_TOKEN "..." i otkroite okno zanovo,
    echo libo pomestite BOT_TOKEN=... v fail tokenty.txt ryadom s start_realtor.bat.
    pause
    exit /b 1
)
cd /d "%~dp0"
python bot.py
echo.
pause
