@echo off
set "source=C:\Users\b5edgr9b\AppData\Local\Google\Chrome\User Data\Default"
set "destination=C:\Users\b5edgr9b\OneDrive - US Army Corps of Engineers\A_BACKUPS\BOOKMARKS"

REM Ensure destination directory exists
if not exist "%destination%" (
    mkdir "%destination%"
)

REM Copy only the Bookmarks and Bookmarks.bak files
copy "%source%\Bookmarks" "%destination%" /Y
copy "%source%\Bookmarks.bak" "%destination%" /Y

echo Bookmarks backed up to %destination%
echo Backup complete!