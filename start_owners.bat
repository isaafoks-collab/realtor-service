@echo off
chcp 65001 >nul
title PRAYMO - dlya sobstvennikov
rem BOT: BOT_TOKEN_OWNERS. Istochnik: okruzhenie (BOT_TOKEN_OWNERS, 
rem dlya sovmestimosti — SECOND_TOKEN) libo lokalnyi fail tokenty.txt.
rem Znacheniya ni v okno, ni v log ne vyvodyatsya.
if not defined BOT_TOKEN_OWNERS if defined SECOND_TOKEN set "BOT_TOKEN_OWNERS=%SECOND_TOKEN%"
if not defined BOT_TOKEN_OWNERS if exist "%~dp0токены.txt" (
    for /f "usebackq tokens=1,* delims== eol=#" %%a in ("%~dp0токены.txt") do set "%%a=%%b"
)
if not defined BOT_TOKEN_OWNERS (
    echo OSIBKA: ne zadan BOT_TOKEN_OWNERS.
    echo Zadayte peremennuyu okruzheniya: setx BOT_TOKEN_OWNERS "..." i otkroite okno zanovo,
    echo libo pomestite BOT_TOKEN_OWNERS=... v fail tokenty.txt ryadom s start_owners.bat.
    pause
    exit /b 1
)
set "BOT_TOKEN=%BOT_TOKEN_OWNERS%"
set "BOT_TOKEN_OWNERS="
set "SECOND_TOKEN="
cd /d "%~dp0"
python bot.py
echo.
pause
