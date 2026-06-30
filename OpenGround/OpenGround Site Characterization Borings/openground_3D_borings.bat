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
set "rScriptFile=C:\Workspace\AUTOMATED_SCRIPTS\OpenGround Site Characterization Borings\openGround_3D_borings.R"

:: Run the R script
"%rscriptPath%" "%rScriptFile%"

explorer "C:\Workspace\AUTOMATED_SCRIPTS\OpenGround Site Characterization Borings\OUTPUT_GEOJSON"

start chrome "https://geoportal.mvr.usace.army.mil/b5portal/home/item.html?id=0ae10dfe677743b5a312b439dd55954d"