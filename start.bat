@echo off
chcp 65001 >nul
title Praymo bots launcher
echo === ZAPUSK DVOCH BOTOV PRAYMO ===
rem Tokeny berutsya iz okruzheniya (BOT_TOKEN, BOT_TOKEN_OWNERS),
rem esli ne zadany — iz lokalnogo faila tokenty.txt (v git ne vhodit).
rem Znacheniya ni v okno, ni v log ne vyvodyatsya.
if not defined BOT_TOKEN if exist "%~dp0токены.txt" (
    for /f "usebackq tokens=1,* delims== eol=#" %%a in ("%~dp0токены.txt") do set "%%a=%%b"
)
if not defined BOT_TOKEN (
    echo OSIBKA: ne zadan BOT_TOKEN.
    echo Zadayte peremennuyu okruzheniya: setx BOT_TOKEN "..." i otkroite okno zanovo,
    echo libo pomestite BOT_TOKEN=... v fail tokenty.txt ryadom s start.bat.
    pause
    exit /b 1
)
start "PRAYMO - podborka sobstvennikov" cmd /k "cd /d "%~dp0" && python bot.py"
timeout /t 2 >nul
if not defined BOT_TOKEN_OWNERS (
    echo OSIBKA: ne zadan BOT_TOKEN_OWNERS.
    echo Zadayte setx BOT_TOKEN_OWNERS "..." libo vnesite v tokenty.txt.
    pause
    exit /b 1
)
set "BOT_TOKEN=%BOT_TOKEN_OWNERS%"
set "BOT_TOKEN_OWNERS="
start "PRAYMO - dlya sobstvennikov" cmd /k "cd /d "%~dp0" && python bot.py"
echo.
echo Oba bota zapushcheny v otdelnyh oknah.
echo Okna mozhno svernut - boty prodolzhat rabotu.
timeout /t 5 >nul
