@echo off
title Vigia Vila Velha - Andre
cd /d C:\vigia

:loop
cls
echo ======================================================
echo   VIGIANDO ULTIMO DIARIO OFICIAL
necho   MODO: MONITOR LOCAL
necho   FREQUENCIA: 30 MINUTOS
echo   LOCAL: C:\vigia
echo ======================================================

if not exist monitor.py (
    echo [X] ERRO: monitor.py nao encontrado em C:\vigia
    pause
    exit
)

"C:\Users\andre.silva\AppData\Local\Microsoft\WindowsApps\python.exe" monitor.py

echo.
echo [%%time%%] Proxima verificacao em 30 minutos...
echo Pressione Ctrl+C para encerrar.

timeout /t 1800 /nobreak
goto loop
