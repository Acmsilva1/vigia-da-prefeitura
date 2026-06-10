@echo off
title Vigia Vila Velha - Andre
setlocal
cd /d "%~dp0"

:loop
cls
echo ======================================================
echo   VIGIANDO ULTIMO DIARIO OFICIAL
echo   MODO: MONITOR LOCAL
echo   FREQUENCIA: 6 HORAS
echo   LOCAL: %cd%
echo ======================================================

if not exist monitor.py (
    echo [X] ERRO: monitor.py nao encontrado neste diretorio
    pause
    exit
)

python -B monitor.py

echo.
echo [%time%] Proxima verificacao em 6 horas...
echo Pressione Ctrl+C para encerrar.

timeout /t 21600 /nobreak
goto loop
