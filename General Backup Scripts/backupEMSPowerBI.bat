@echo off
setlocal enabledelayedexpansion

echo ========================================
echo Power BI Backup Script
echo Started: %date% %time%
echo ========================================

REM Define common base paths
set "baseSource=\\mvrdfs.mvr.ds.usace.army.mil\EGIS\Work\Office\EC\EC"
set "baseDestT=T:\EMS\BACKUP_POWERBI"
set "baseDestOneDrive=C:\Users\b5edgr9b\OneDrive - US Army Corps of Engineers\A_BACKUPS\POWERBI"

REM ========================================
REM Backup Operations
REM ========================================

call :BackupFolder "EMS Power BI Dashboards" "EMS_PBI"
call :BackupFolder "INDC Power BI Dashboards" "INDC_PBI"
call :BackupFolder "GEOTECH Power BI Dashboards" "GEOTECH_PBI"
call :BackupFolder "General Power BI Dashboards" "GENERAL_PBI"

echo.
echo ========================================
echo Power BI backup complete!
echo Completed: %date% %time%
echo ========================================

exit /b 0

REM ========================================
REM Backup Function
REM ========================================
:BackupFolder
set "folderName=%~1"
set "shortName=%~2"

echo.
echo [%time%] Backing up %folderName%...

set "source=%baseSource%\%folderName%"
set "dest1=%baseDestT%\%folderName%"
set "dest2=%baseDestOneDrive%\%shortName%"

REM Robocopy to T: drive (local/network) - multi-threaded
robocopy "%source%" "%dest1%" /E /Z /R:2 /W:5 /MT:8 /XO /NFL /NDL /NP /NJH /NJS
set result1=!errorlevel!

REM Robocopy to OneDrive - fewer threads for cloud sync
robocopy "%source%" "%dest2%" /E /Z /R:2 /W:5 /MT:4 /XO /NFL /NDL /NP /NJH /NJS
set result2=!errorlevel!

REM Check results (Robocopy returns 0-7 for success, 8+ for errors)
if !result1! LSS 8 if !result2! LSS 8 (
    echo [SUCCESS] %folderName% backed up successfully
) else (
    echo [WARNING] %folderName% completed with warnings or errors
)

exit /b 0