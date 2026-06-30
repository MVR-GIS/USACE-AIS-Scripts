@echo off
echo Running ems_to_sharepoint.py...

REM Set the working directory to the script's location
cd /d C:\Workspace\AUTOMATED_SCRIPTS\EMS

REM Set path to venv Python
set VENV_PYTHON="C:\Users\b5edgr9b\.venv\Scripts\python.exe"

REM Check if venv Python exists
if not exist %VENV_PYTHON% (
    echo ERROR: Virtual environment Python not found at %VENV_PYTHON%
    echo Please create the virtual environment first.
    pause
    exit /b 1
)

REM Run the Python script using venv Python
%VENV_PYTHON% ems_to_sharepoint.py

echo Script execution completed.