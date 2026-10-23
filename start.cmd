@echo off
rem Startet das Board ohne Konsolenfenster. Adresse: http://127.0.0.1:8899
cd /d "%~dp0"
start "" pythonw server.py
