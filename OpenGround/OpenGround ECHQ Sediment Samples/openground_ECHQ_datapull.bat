@echo off

:: Full path to Rscript executable
set "rscriptPath=C:\Users\b5edgr9b\AppData\Local\Programs\R\R-4.5.0\bin\x64\Rscript.exe"

:: Full path for the R script to run
set "rScriptFile=C:\Workspace\GIT\USACE-AIS-Scripts\OpenGround\OpenGround ECHQ Sediment Samples\openGround_ECHQ_datapull.R"

:: Run the R script
"%rscriptPath%" "%rScriptFile%"

:: Run the python script to upload to Portal
REM Set the path to your Python interpreter
set "PYTHON_PATH=C:\Users\b5edgr9b\AppData\Local\Programs\Python\Python313\python.exe"

REM Set the Python script path
set "PYTHON_SCRIPT=C:\Workspace\GIT\USACE-AIS-Scripts\OpenGround\OpenGround ECHQ Sediment Samples\upload_OpenGround_to_Portal.py"

REM Set the working directory to the script's location
cd /D "C:\Workspace\GIT\USACE-AIS-Scripts\OpenGround\OpenGround ECHQ Sediment Samples"

REM Activate the virtual environment (if you're using one)
if exist .\.venv\Scripts\activate.bat (
    call .\.venv\Scripts\activate.bat
)

REM Run the Python script
echo Running the Python script...
"%PYTHON_PATH%" "%PYTHON_SCRIPT%"

REM Deactivate the virtual environment (if you activated it)
if exist .\.venv\Scripts\deactivate.bat (
    call .\.venv\Scripts\deactivate.bat
)

pause