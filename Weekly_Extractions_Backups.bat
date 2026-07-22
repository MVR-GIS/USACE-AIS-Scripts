@echo off
title Weekly Data Collection & Backup Script

REM ============================================================================
REM                    WEEKLY DATA COLLECTION & BACKUP SCRIPT
REM ============================================================================
REM Purpose: Map drives, launch login sites, backup files, and pull data
REM Last Updated: [Date]
REM ============================================================================

echo.
echo ============================================================================
echo                         NETWORK DRIVE MAPPING
echo ============================================================================
echo.
call "C:\Workspace\GIT\USACE-AIS-Scripts\Map Network Drives.lnk"
echo [SUCCESS] Network drives mapped
echo.
echo.


echo ============================================================================
echo                         LAUNCHING LOGIN SITES
echo ============================================================================
echo.
echo Opening ArcGIS Portal (UCOP)...
start chrome "https://arcportal-ucop-corps.usace.army.mil/s0portal/home/content.html#my"

echo Opening Bentley OpenGround Portal...
start chrome "https://portal.openground.bentley.com/clouds/eastus/570c1f2b-aed1-4791-a20b-4b8ac8cdd2c8"

echo Opening ArcGIS Portal (Partners)...
start chrome "https://arcportal-ucop-partners.usace.army.mil/usaceportal/home/"

echo.
echo [INFO] Please log in to all sites before continuing...
timeout /t 10 /nobreak >nul
echo.
echo.


echo ============================================================================
echo                            FILE BACKUPS
echo ============================================================================
echo.
echo [1/4] Backing up Desktop Backgrounds...
call "C:\Workspace\GIT\USACE-AIS-Scripts\General Backup Scripts\backupBackgrounds.bat"

echo [2/4] Backing up Power BI Files...
call "C:\Workspace\GIT\USACE-AIS-Scripts\General Backup Scripts\backupPowerBI.bat"

echo [3/4] Backing up Chrome Bookmarks...
call "C:\Workspace\GIT\USACE-AIS-Scripts\General Backup Scripts\backupChromeBookmarks.bat"

echo [4/4] Backing up KeePass Database...
call "C:\Workspace\GIT\USACE-AIS-Scripts\General Backup Scripts\backupKeePass.bat"

echo.
echo [SUCCESS] All file backups completed
echo.
echo.


echo ============================================================================
echo                         WEEKLY DATA COLLECTION
echo ============================================================================
echo.

REM ----------------------------------------------------------------------------
echo [1/9] EMS Data Collection
REM ----------------------------------------------------------------------------
call "C:\Workspace\GIT\USACE-AIS-Scripts\EMS\EMS_datapull.bat"
echo.

REM ----------------------------------------------------------------------------
echo [2/9] CEBIS Data Collection
REM ----------------------------------------------------------------------------
call "C:\Workspace\GIT\USACE-AIS-Scripts\CEBIS\CEBIS_to_SharePoint.bat"
echo.

REM ----------------------------------------------------------------------------
echo [3/9] HSS Data Collection
REM ----------------------------------------------------------------------------
call "C:\Workspace\GIT\USACE-AIS-Scripts\HSS\HSS_to_SharePoint_ESRI.bat"
echo.

REM ----------------------------------------------------------------------------
echo [4/9] DrChecks (ProjNet) Data Collection
REM ----------------------------------------------------------------------------
call "C:\Workspace\GIT\USACE-AIS-Scripts\ProjNet DrChecks\drchecks_to_SharePoint.bat"
echo.

REM ----------------------------------------------------------------------------
echo [5/9] MIDAS Data Collection
REM ----------------------------------------------------------------------------
call "C:\Workspace\GIT\USACE-AIS-Scripts\MIDAS\MIDAS_DIRT_DATA_PULL_MVRONLY.bat"
echo.

REM ----------------------------------------------------------------------------
echo [6/9] OpenGround Data Collection (MVR Only)
REM ----------------------------------------------------------------------------
call "C:\Workspace\GIT\USACE-AIS-Scripts\OpenGround\OpenGround\openground_datapull_MVRONLY.bat"
echo.

REM ----------------------------------------------------------------------------
echo [7/9] OpenGround ECHQ Sediment Samples
REM ----------------------------------------------------------------------------
call "C:\Workspace\GIT\USACE-AIS-Scripts\OpenGround\OpenGround ECHQ Sediment Samples\openground_ECHQ_datapull.bat"
echo.

REM ----------------------------------------------------------------------------
echo [8/9] OpenGround Site Characterization Borings
REM ----------------------------------------------------------------------------
echo [SKIPPED] Site Characterization Borings export is currently disabled
REM Uncomment below to enable:
REM call "C:\Workspace\AUTOMATED_SCRIPTS\OpenGround Site Characterization Borings\openground_3D_borings.bat"
echo.

REM ----------------------------------------------------------------------------
echo [9/9] ProjectWise Authoritative Name Verification
REM ----------------------------------------------------------------------------
call "C:\Workspace\GIT\projectwise\Location Authorities\PW_Authoratative_Names.bat"
echo.


echo ============================================================================
echo                         PROCESS COMPLETE
echo ============================================================================
echo.
echo All data collection and backup tasks have been completed successfully.
echo Completed at: %date% %time%
echo.

REM Display completion message
echo msgbox "Data source updates and weekly backups have been completed.", 0, "Data Reminder and Backups" > "%temp%\reminder.vbs"
cscript /nologo "%temp%\reminder.vbs" >nul
del "%temp%\reminder.vbs"

echo.
echo Press any key to exit...
pause >nul
exit