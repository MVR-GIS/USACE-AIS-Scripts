@echo off
title ProjNet (DrChecks) to SharePoint Automation

REM Set the working directory to the script's location
cd /D C:\Workspace\GIT\USACE-AIS-Scripts\ProjNet_DrChecks

REM Activate the virtual environment
if exist "C:\Users\b5edgr9b\.venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call "C:\Users\b5edgr9b\.venv\Scripts\activate.bat"
    
    REM Run the Python script using the venv's Python
    echo Running the DrChecks Python script...
    python prod_ExtractDrChecks.py
    
    REM Deactivate is automatic when batch ends, but you can call it explicitly
    call deactivate
) else (
    echo Virtual environment not found!
    pause
    exit /b 1
)

echo Script completed.
pause