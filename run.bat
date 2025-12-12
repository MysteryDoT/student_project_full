@echo off
REM Run this file to create venv, install requirements and start the app.

if not exist venv (
    python -m venv venv
)

call venv\Scripts\activate.bat

echo Installing requirements...
pip install -r requirements.txt

echo Starting the app...
python app.py

pause
