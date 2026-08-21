@echo off
title SOPAUTO — Gestion Piece Auto
cd /d "%~dp0"
set "PY_EXE=C:\Users\diaba\AppData\Local\Programs\Python\Python312\python.exe"
if not exist "%PY_EXE%" set "PY_EXE=python"
"%PY_EXE%" main.py
