@echo off
chcp 65001 >nul
title SOPAUTO - Gestion Piece Auto (PyQt6 Engine)
cd /d "%~dp0"

echo.
echo   ========================================
echo      SOPAUTO - Engine PyQt6 (C++ GPU)
echo   ========================================
echo.

set "PY_EXE=C:\Users\diaba\AppData\Local\Programs\Python\Python312\python.exe"
if not exist "%PY_EXE%" set "PY_EXE=python"

"%PY_EXE%" main_qt.py
if errorlevel 1 (
    echo.
    echo   [ERREUR] Le logiciel s'est arrete de facon inattendue.
    echo.
    pause
    exit /b 1
)
exit /b 0
