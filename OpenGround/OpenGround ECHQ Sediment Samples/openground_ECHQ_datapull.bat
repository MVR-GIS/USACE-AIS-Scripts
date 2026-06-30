@echo off

:: Ask the user if they are on the USACE network
::set /p networkPrompt=Are you currently on the USACE network? (Y/N): 

:: Check the response
::if /I "%networkPrompt%"=="N" (
::   echo Program terminated. You are not on the USACE network.
::     exit /b
:: ) else if /I "%networkPrompt%"=="Y" (
::     echo Continuing the script...
:: ) else (
::     echo Invalid input. Please run the script again and answer with Y or N.
::     exit /b
:: )

:: Full path to Rscript executable
set "rscriptPath=C:\Users\b5edgr9b\AppData\Local\Programs\R\R-4.5.0\bin\x64\Rscript.exe"

:: Full path for the R script to run
set "rScriptFile=C:\Workspace\AUTOMATED_SCRIPTS\OpenGround ECHQ Sediment Samples\openGround_ECHQ_datapull.R"

:: Run the R script
"%rscriptPath%" "%rScriptFile%"

:: Run the python script to upload to Portal
REM Set the path to your Python interpreter (replace if needed)
set PYTHON_PATH="C:\Users\b5edgr9b\AppData\Local\Programs\Python\Python313\python.exe"

REM Set the working directory to the script's location
cd /D "C:\Workspace\AUTOMATED_SCRIPTS\OpenGround ECHQ Sediment Samples"

REM Activate the virtual environment (if you're using one)
if exist .\.venv\Scripts\activate.bat (
    call .\.venv\Scripts\activate.bat
)

REM Run the Python script
echo Running the Python script...
%PYTHON_PATH% upload_ECHQOpenGround_to_Portal.py

REM Deactivate the virtual environment (if you activated it)
if exist .\.venv\Scripts\deactivate.bat (
    call .\.venv\Scripts\deactivate.bat
)

::explorer "C:\Workspace\AUTOMATED_SCRIPTS\OpenGround ECHQ Sediment Samples\OUTPUT GEOJSON"
::start chrome "https://geoportal.mvr.usace.army.mil/b5portal/home/item.html?id=e1e5a69a45a9467f8798c721641c8f66"
