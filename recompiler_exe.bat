@echo off
chcp 65001 >nul
title SOPAUTO - Recompilation de l'executable
cd /d "%~dp0"

echo.
echo   ========================================
echo      Recompilation de SOPAUTO.exe
echo   ========================================
echo.

set "PY_EXE=C:\Users\diaba\AppData\Local\Programs\Python\Python312\python.exe"
if not exist "%PY_EXE%" set "PY_EXE=python"

"%PY_EXE%" -m PyInstaller --noconfirm sopauto.spec
if errorlevel 1 (
    echo.
    echo   [ERREUR] La compilation a echoue. Verifiez le message ci-dessus.
    echo   Si PyInstaller est absent :  pip install pyinstaller
    echo.
    pause
    exit /b 1
)

echo.
echo   ========================================
echo      Termine : dist\SOPAUTO.exe
echo   ========================================
echo.
pause
