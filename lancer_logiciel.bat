@echo off
cd /d "%~dp0"
set "PY_EXE=C:\Users\diaba\AppData\Local\Programs\Python\Python312\pythonw.exe"
if not exist "%PY_EXE%" set "PY_EXE=pythonw"
start "" "%PY_EXE%" main.py
exit
