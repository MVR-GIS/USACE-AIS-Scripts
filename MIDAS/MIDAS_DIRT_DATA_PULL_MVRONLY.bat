@echo off
title MIDAS Portal DIRT Pull Automation

:: Full path to Rscript executable
set "rscriptPath=C:\Users\b5edgr9b\AppData\Local\Programs\R\R-4.5.0\bin\x64\Rscript.exe"

:: Full path for the R script to run
set "rScriptFile=C:\Workspace\AUTOMATED_SCRIPTS\MIDAS\MIDAS_Portal_DIRT_Pull_MVRONLY.R"

:: Run the R script
"%rscriptPath%" "%rScriptFile%"

:: Run the python script to upload to Portal
REM Set the working directory to the script's location
cd /D "C:\Workspace\AUTOMATED_SCRIPTS\MIDAS"

REM Activate the virtual environment (now using centralized location)
if exist "C:\Users\b5edgr9b\.venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call "C:\Users\b5edgr9b\.venv\Scripts\activate.bat"
    
    REM Run the Python script
    echo Running the Python script...
    python upload_MIDAS_to_Portal.py
    
    REM Deactivate the virtual environment
    call deactivate
) else (
    echo Virtual environment not found!
    pause
    exit /b 1
)