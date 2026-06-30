@echo off
set "source=C:\Users\b5edgr9b\AppData\Local\Microsoft\BingWallpaperApp\WPImages"
set "destination=C:\Users\b5edgr9b\OneDrive - US Army Corps of Engineers\A_BACKUPS\BACKGROUNDS"
set "destinationTwo=P:\REFERENCE_BACKUP\BACKUP_BACKGROUNDS"

xcopy "%source%" "%destination%" /D /E /C /I /Y
xcopy "%destination%" "%destinationTwo%" /D /E /C /I /Y

set "source=C:\Users\b5edgr9b\AppData\Local\Packages\Microsoft.BingWallpaper_8wekyb3d8bbwe\LocalState\images\bing"
set "destination=C:\Users\b5edgr9b\OneDrive - US Army Corps of Engineers\A_BACKUPS\BACKGROUNDS"
set "destinationTwo=P:\REFERENCE_BACKUP\BACKUP_BACKGROUNDS"

xcopy "%source%" "%destination%" /D /E /C /I /Y
xcopy "%destination%" "%destinationTwo%" /D /E /C /I /Y

echo Backgrounds backed up to %destination% and %destinationTwo%
echo Background backup complete!
echo