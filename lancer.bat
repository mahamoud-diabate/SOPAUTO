@echo off
chcp 65001 >nul
title SODIPAC - Gestion Piece Auto
cd /d "%~dp0"

echo.
echo   ========================================
echo      SODIPAC - Gestion Piece Auto
echo   ========================================
echo.

set "PY_EXE=C:\Users\diaba\AppData\Local\Programs\Python\Python312\python.exe"
if not exist "%PY_EXE%" set "PY_EXE=python"

where python >nul 2>&1
if errorlevel 1 if not exist "%PY_EXE%" (
    echo   [ERREUR] Python n'est pas installe ou absent du PATH.
    echo   Telechargez-le sur https://www.python.org/downloads/
    echo   Cochez "Add Python to PATH" pendant l'installation.
    echo.
    pause
    exit /b 1
)

echo   Demarrage...
"%PY_EXE%" main.py
if errorlevel 1 (
    echo.
    echo   [ERREUR] Le logiciel s'est arrete de facon inattendue.
    echo   Copiez le message ci-dessus pour obtenir de l'aide.
    echo.
    pause
    exit /b 1
)
exit /b 0
