@echo off
echo Backing up primary EMS Power BI Dashboards
set "source=\\mvrdfs.mvr.ds.usace.army.mil\EGIS\Work\Office\EC\EC\EMS Power BI Dashboards"
set "destination=T:\EMS\BACKUP_POWERBI\EMS Power BI Dashboards"
set "destinationEMS=C:\Users\b5edgr9b\OneDrive - US Army Corps of Engineers\A_BACKUPS\POWERBI\EMS_PBI"

xcopy "%source%" "%destination%" /D /E /C /I /Y
xcopy "%source%" "%destinationEMS%" /D /E /C /I /Y
echo EMS Power BI files backed up to %destination% and %destinationEMS%

echo Backing up INDC EMS Power BI Dashboards
set "source=\\mvrdfs.mvr.ds.usace.army.mil\EGIS\Work\Office\EC\EC\INDC Power BI Dashboards"
set "destination=T:\EMS\BACKUP_POWERBI\INDC Power BI Dashboards"
set "destinationINDC=C:\Users\b5edgr9b\OneDrive - US Army Corps of Engineers\A_BACKUPS\POWERBI\INDC_PBI"

xcopy "%source%" "%destination%" /D /E /C /I /Y
xcopy "%source%" "%destinationINDC%" /D /E /C /I /Y
echo INDC Power BI files backed up to %destination% and %destinationINDC%


echo Backing up Geotech Power BI Dashboards
set "source=\\mvrdfs.mvr.ds.usace.army.mil\EGIS\Work\Office\EC\EC\GEOTECH Power BI Dashboards"
set "destination=T:\EMS\BACKUP_POWERBI\GEOTECH Power BI Dashboards"
set "destinationGeotech=C:\Users\b5edgr9b\OneDrive - US Army Corps of Engineers\A_BACKUPS\POWERBI\GEOTECH_PBI"

xcopy "%source%" "%destination%" /D /E /C /I /Y
xcopy "%source%" "%destinationGeotech%" /D /E /C /I /Y
echo Geotech Power BI files backed up to %destination% and %destinationGeotech%


echo Backing up General Power BI Dashboards
set "source=\\mvrdfs.mvr.ds.usace.army.mil\EGIS\Work\Office\EC\EC\General Power BI Dashboards"
set "destination=T:\EMS\BACKUP_POWERBI\General Power BI Dashboards"
set "destinationGeneral=C:\Users\b5edgr9b\OneDrive - US Army Corps of Engineers\A_BACKUPS\POWERBI\GENERL_PBI"

xcopy "%source%" "%destination%" /D /E /C /I /Y
xcopy "%source%" "%destinationGeneral%" /D /E /C /I /Y
echo General Power BI files backed up to %destination% and %destinationGeneral%

echo Power BI backup complete!