@echo off
title CEBIS to SharePoint Automation

REM Set the working directory to the script's location
cd /D "C:\Workspace\AUTOMATED_SCRIPTS\CEBIS"

REM Activate the virtual environment
if exist "C:\Users\b5edgr9b\.venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call "C:\Users\b5edgr9b\.venv\Scripts\activate.bat"
    
    REM Run the Python script using the venv's Python
    echo Running the CEBIS Python script...
    python cebis_to_sharepoint.py
    
    REM Deactivate is automatic when batch ends, but you can call it explicitly
    call deactivate
) else (
    echo Virtual environment not found!
    pause
    exit /b 1
)

echo Script completed.