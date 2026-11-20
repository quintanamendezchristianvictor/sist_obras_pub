@echo off
rem Copia de respaldo periodica (RNF-18). Para programarla todos los dias a las 23:00,
rem ejecute una sola vez, como administrador y en la carpeta del proyecto:
rem   schtasks /Create /SC DAILY /ST 23:00 /TN "SIGOP respaldo" /TR "%CD%\scripts\respaldo_programado.bat"
cd /d "%~dp0.."
venv\Scripts\python.exe manage.py respaldar_bd
