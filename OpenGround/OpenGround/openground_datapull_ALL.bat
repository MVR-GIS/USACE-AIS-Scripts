@echo off

:: Ask the user if they are on the USACE network
set /p networkPrompt=Are you currently on the USACE network? (Y/N): 

:: Check the response
if /I "%networkPrompt%"=="N" (
    echo Program terminated. You are not on the USACE network.
    exit /b
) else if /I "%networkPrompt%"=="Y" (
    echo Continuing the script...
) else (
    echo Invalid input. Please run the script again and answer with Y or N.
    exit /b
)

:: Full path to Rscript executable
set "rscriptPath=C:\Program Files\R\R-4.2.0\bin\Rscript.exe"

:: Full path for the R script to run
set "rScriptFile=C:\Workspace\AUTOMATED_SCRIPTS\OpenGround\openGround_datapull.R"

:: Run the R script
"%rscriptPath%" "%rScriptFile%"

explorer "C:\Workspace\AUTOMATED_SCRIPTS\OpenGround\OUTPUT GEOJSON"

start chrome "https://geoportal.mvr.usace.army.mil/b5portal/home/item.html?id=9db89a1840e84611b9adcd27b1646eb8"

:: Keep the command prompt open to view output or errors
pause
