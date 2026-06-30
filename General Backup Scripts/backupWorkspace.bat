@echo off
echo Backing up Automated Scripts
set "source=C:\Workspace\LOCAL SANDBOX"
set "destination=C:\Users\b5edgr9b\OneDrive - US Army Corps of Engineers\A_BACKUPS\WORKSPACE"
set "destination_two=\\mvrdfs.mvr.ds.usace.army.mil\EGIS\Work\Office\EC\EC\BENAC BACKUP\WORKSPACE"

xcopy "%source%" "%destination%" /D /E /C /I /Y
xcopy "%source%" "%destination_two%" /D /E /C /I /Y

echo Automated script backed up to %destination% and %destination_two%
echo Automated script backup complete!
echo