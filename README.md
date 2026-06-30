# USACE-AIS-Scripts

## Overview

This repository contains automation scripts for extracting data from USACE systems and uploading the results to SharePoint libraries and ESRI Portal feature services. Most scripts use either API access or Playwright browser automation to authenticate, download or query data, and then save the extracted output to CSV, GeoJSON, or other formats.

The main focus areas are:
- EMS (Enterprise Management System)
- CEBIS
- HSS
- MIDAS
- OpenGround
- ProjNet / DrChecks

Additional work has been completed for NLD/NID data extraction and can be found in this organization repo for "projectwise".

Reusable helper modules support SharePoint uploads and ESRI Portal uploads across multiple scripts.

## Important Disclaimer

This repository does not include credentials, API secrets, or private login information. The scripts reference a local `config.json` file or other secret configuration, which must be supplied by the user.

> Do not commit credentials or sensitive configuration to source control.

## Repo Structure

- `A_Modules/`
  - `SharePointUpload.py` - helper for uploading files to SharePoint document libraries using Playwright.
  - `PortalUpload.py` - helper for uploading GeoJSON data to ESRI Portal items via Playwright.

- `CEBIS/`
  - `cebis_to_sharepoint.py` - download CEBIS report, upload CSV to SharePoint, convert to GeoJSON, and upload to ESRI Portal.
  - `CEBIS_to_SharePoint.bat` - likely batch wrapper for CEBIS automation.
  - `CEBIS_EXPORT.csv`, `CEBIS_EXPORT.geojson` - example output files.

- `EMS/`
  - `ems_api_cac.py`, `EMS_datapull.bat`, `ems_to_sharepoint.py` - scripts to pull EMS data and upload to SharePoint.
  - `update_EMS_BIO.py` - Playwright-based EMS authentication and query script for resource bios and sections.
  - `Update Resource Bios/` - contains support files and export logic for EMS bios.

- `HSS/`
  - `HSS_EXTRACT.py` - extracts HSS Required Inspections metrics and uploads output to SharePoint.
  - `HSS_to_SharePoint_ESRI.bat` - batch file to run the HSS extraction script.

- `MIDAS/`
  - `MIDAS_DIRT_DATA_PULL_ALL.bat`, `MIDAS_DIRT_DATA_PULL_MVRONLY.bat` - scripts for MIDAS DIRT data pulls.
  - `MIDAS_Portal_DIRT_Pull_ALL.R`, `MIDAS_Portal_DIRT_Pull_MVRONLY.R` - R scripts for MIDAS portal extraction.
  - `upload_MIDAS_to_Portal.py` - likely uploads MIDAS output to ESRI Portal.

- `OpenGround/`
  - `OpenGround/` - contains scripts and batch wrappers for OpenGround data extraction and portal upload.
  - `OpenGround ECHQ Sediment Samples/` - scripts specific to ECHQ sediment sample extraction.
  - `OpenGround Site Characterization Borings/` - scripts for drilling/boring data extraction.

- `ProjNet DrChecks/`
  - `prod_ExtractDrChecks.py` - automated ProjNet extraction and upload logic.
  - `drchecks_to_SharePoint.bat` - batch wrapper for the DrChecks automation.

- `Weekly_Extractions_Backups.bat`
  - orchestrates weekly backups, data pulls, and automation scripts across the repo.

## Configuration

Many scripts expect a `config.json` file in the repo root or use a local configuration path. That file typically contains:
- SharePoint URLs and user email
- USACE API settings
- OpenGround API credentials and instance IDs
- Local module path settings

Example values should be replaced with your own secure credentials. Do not share or store secret values in public or version-controlled repositories.

## Dependencies

Common dependencies used by the scripts include:
- Python 3.10+ (or compatible Python 3.x)
- `playwright`
- `pandas`
- `requests`
- `beautifulsoup4`
- `cryptography`
- `openpyxl`
- `bs4`
- `sf` / `httr` / `jsonlite` for R scripts

Additional dependencies may be required by individual scripts. Check the script headers and documentation comments for the exact requirements.

## Usage

### Python scripts

Run the Python scripts from the relevant folder after activating your Python environment:

```powershell
cd C:\Workspace\GIT\USACE-AIS-Scripts\HSS
python HSS_EXTRACT.py
```

```powershell
cd C:\Workspace\GIT\USACE-AIS-Scripts\CEBIS
python cebis_to_sharepoint.py
```

```powershell
cd C:\Workspace\GIT\USACE-AIS-Scripts\EMS
python update_EMS_BIO.py
```

### Batch workflows

Use the batch wrappers to run end-to-end automation flows and weekly pulls:

```powershell
C:\Workspace\GIT\USACE-AIS-Scripts\Weekly_Extractions_Backups.bat
```

```powershell
C:\Workspace\GIT\USACE-AIS-Scripts\HSS\HSS_to_SharePoint_ESRI.bat
```

## Notes

- The extraction scripts rely on browser automation and may require manual authentication for CAC, SSO, or MFA.
- Upload helpers in `A_Modules/` standardize SharePoint and ESRI Portal interactions across scripts.
- Some folders contain legacy or backup scripts; review current scripts before using them.
- Paths in the scripts are frequently hard-coded for local environment use. Update paths as needed for your own system.

## Security

- Credentials are not included in this README.
- Ensure `config.json` is stored securely and is excluded from shared repositories.
- If you want to store example configuration values, use a separate `config.example.json` template and never include real secrets.

## Recommended Workflow

1. Create or update your local `config.json` with secure values.
2. Install the required Python packages and Playwright browsers.
3. Run the relevant batch wrapper for the dataset you need.
4. Verify outputs in the target SharePoint library or ESRI Portal item.

## License and Ownership

This repo contains internal USACE automation scripts. Use and distribution should follow agency policies and security requirements.
