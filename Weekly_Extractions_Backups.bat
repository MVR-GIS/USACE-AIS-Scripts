@echo off
echo Mapping network drives
call "C:\Workspace\GIT\USACE-AIS-Scripts\Map Network Drives.lnk"
echo Available network drives have been mapped
echo


echo Launching sites to log in to
start chrome "https://arcportal-ucop-corps.usace.army.mil/s0portal/home/content.html#my"
start chrome "https://portal.openground.bentley.com/clouds/eastus/570c1f2b-aed1-4791-a20b-4b8ac8cdd2c8"
start chrome "https://arcportal-ucop-partners.usace.army.mil/usaceportal/home/"


echo Starting file backups

call "C:\Workspace\GIT\USACE-AIS-Scripts\General Backup Scripts\backupBackgrounds.bat"
call "C:\Workspace\GIT\USACE-AIS-Scripts\General Backup Scripts\backupPowerBI.bat"
call "C:\Workspace\GIT\USACE-AIS-Scripts\General Backup Scripts\backupChromeBookmarks.bat"
call "C:\Workspace\GIT\USACE-AIS-Scripts\General Backup Scripts\backupKeePass.bat"


echo Starting weekly data pulls

:: start pulling data
echo Starting data collection for: EMS
call "C:\Workspace\GIT\USACE-AIS-Scripts\EMS\EMS_datapull.bat"

echo Starting data collection for: CEBIS
call "C:\Workspace\GIT\USACE-AIS-Scripts\CEBIS\CEBIS_to_SharePoint.bat"

echo Starting data collection for: HSS
call "C:\Workspace\GIT\USACE-AIS-Scripts\HSS\HSS_to_SharePoint_ESRI.bat"

echo Starting data collection for: DrChecks (ProjNet)
call "C:\Workspace\GIT\USACE-AIS-Scripts\ProjNet DrChecks\drchecks_to_SharePoint.bat"

echo Starting data collection for: MIDAS
call "C:\Workspace\GIT\USACE-AIS-Scripts\MIDAS\MIDAS_DIRT_DATA_PULL_MVRONLY.bat"

echo Starting data collection for: OpenGround
call "C:\Workspace\GIT\USACE-AIS-Scripts\OpenGround\OpenGround\openground_datapull_MVRONLY.bat"

echo Starting data collection for: ECHQ OpenGround
call "C:\Workspace\GIT\USACE-AIS-Scripts\OpenGround\OpenGround ECHQ Sediment Samples\openground_ECHQ_datapull.bat"

echo OpenGround Site Characterization Borings export is currently turned off. Moving on...
::echo Starting data collection for: OpenGround Site Characterization Borings
::call "C:\Workspace\AUTOMATED_SCRIPTS\OpenGround Site Characterization Borings\openground_3D_borings.bat"

echo Starting ProjectWise Authoratative Name Verification
call "C:\Workspace\GIT\projectwise\Location Authorities\PW_Authoratative_Names.bat"

:: Pop-up message with title and simple OK button
echo msgbox "Data source updates and weekly backups have been completed.", 0, "Data Reminder and Backups" > "%temp%\reminder.vbs"
cscript /nologo "%temp%\reminder.vbs" >nul

:: Clean up the temporary VBScript
del "%temp%\reminder.vbs"
exit
