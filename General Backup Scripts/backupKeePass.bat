@echo off
set "source=C:\Users\b5edgr9b\OneDrive - US Army Corps of Engineers\KEEPASS"
set "destination=C:\Users\b5edgr9b\OneDrive - US Army Corps of Engineers\A_BACKUPS\KEEPASS"

xcopy "%source%" "%destination%" /D /E /C /I /Y

echo KeePass backed up to %destination% 
echo KeePass backup complete!
echo