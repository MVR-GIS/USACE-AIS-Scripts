"""
CEBIS Data Download and Upload Script

This script automates the process of:
1. Downloading the CEBIS NBI Open Inventory Search report
2. Uploading the CSV report to SharePoint
3. Converting the CSV to GeoJSON format
4. Uploading the GeoJSON to an ESRI ArcGIS Portal feature layer

The script uses Playwright for browser automation and requires appropriate
credentials and permissions for all systems involved.

Author: Ryan Benac
Created: 3/10/2026
"""

import sys
import json
import os
import pandas as pd
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError, Page

# Add the A_MODULES directory to system path (portable - relative to script location)
SCRIPT_DIR = Path(__file__).parent
MODULES_PATH = SCRIPT_DIR.parent / 'A_MODULES'
if str(MODULES_PATH) not in sys.path:
    sys.path.insert(0, str(MODULES_PATH))

# Import the refactored upload functions
from SharePointUpload import upload_to_sharepoint # imported from another file
from PortalUpload import upload_to_esri_portal # imported from another file


# ==============================================================================
# FUNCTION DEFINITIONS
# ==============================================================================

def download_cebis_report(page: Page) -> str | None:
    """
    Navigates to the CEBIS portal, authenticates, and downloads the NBI Open Inventory Search report.
    
    Args:
        page (Page): A Playwright Page object.
    
    Returns:
        str | None: The file path to the downloaded CSV report, or None if it fails.
    """
    try:
        # 1. Navigate to the CEBIS Applets Page
        cebis_url = "https://cebis.sec.usace.army.mil/ords/r/cebis/applets/"
        print(f"Navigating to: {cebis_url}")
        page.goto(cebis_url, timeout=600000)  # 10-minute timeout for manual certificate selection
        print("CEBIS Applets Page loaded successfully.")

        # 2. Click the Log In Button
        print("Clicking the Log In button...")
        page.click("button[id='B3457977243511861']", timeout=60000)
        print("Log In button clicked.")

        # 3. Click the Correct Card to Access the Report
        print("Clicking the CEBIS NBI Open Inventory Search card...")
        page.click(
            "li.t-Cards-item div.t-Card a div.t-Card-titleWrap h3.t-Card-title:has-text('CEBIS NBI Open Inventory Search')",
            timeout=60000
        )
        print("CEBIS NBI Open Inventory Search card clicked.")

        # 4. Click the Actions Button
        print("Clicking the Actions button...")
        page.click("button[id='R21330164091369244_actions_button']", timeout=60000)
        print("Actions button clicked.")

        # 5. Click the Download Option in the Actions Menu
        print("Clicking the Download option in the Actions menu...")
        page.click("button[id='R21330164091369244_actions_menu_14i']", timeout=60000)
        print("Download option clicked.")

        # 6. Click the Second Download Button and wait for the download
        print("Clicking the final Download button...")
        with page.expect_download() as download_info:
            page.click("button.ui-button--hot", timeout=60000, force=True)
        download = download_info.value
        print("Final Download button clicked.")

        # 7. Wait for the Download to Complete and Rename File
        print("Waiting for download to complete...")
        temp_file_path = download.path()
        final_file_path = "C:\\Workspace\\AUTOMATED_SCRIPTS\\CEBIS\\CEBIS_EXPORT.csv"
        if os.path.exists(final_file_path):
            os.remove(final_file_path)
            print(f"Existing file '{final_file_path}' removed.")
        os.rename(temp_file_path, final_file_path)
        print(f"File downloaded and renamed to: {final_file_path}")
        return final_file_path
        
    except Exception as e:
        print(f"An error occurred during the CEBIS download process: {e}")
        return None


def create_geojson_from_csv(csv_file_path: str) -> str | None:
    """
    Reads a CSV, processes it, and converts it to a GeoJSON file.
    
    The function filters data for the CEMVR district, renames columns to more readable names,
    converts DMS coordinates to decimal degrees, and creates a GeoJSON FeatureCollection.
    The CSV is also re-saved with the cleaned and renamed columns.
    
    Args:
        csv_file_path (str): The path to the input CSV file.
    
    Returns:
        str | None: The path to the created GeoJSON file, or None on failure.
    """
    print(f"\nCreating GeoJSON from: {csv_file_path}")
    
    rename_map = {
        "N90mn": "Inspection Month", "N90yr": "Inspection Year", "N91": "Inspection frequency (months)",
        "N236 Prj P2 No": "P2 No", "N27 Year": "Year Built", "N16d": "Latitude deg",
        "N16m": "Latitude Min", "N16s": "Latitude Sec", "N17d": "Longitude deg",
        "N17m": "Longitude min", "N17s": "Longitude sec", "N19": "Bypass detour length",
        "N9": "Location", "N21": "Maintenance Responsibility", "N22": "Owner",
        "N26": "Fucntional Class", "N45": "Number of Spans", "N92a1": "Critical Feature Inspection",
        "N92a2": "Critical Feature Inspection Months", "N92b1": "Underwater Inspection",
        "N92b2": "Other spec Inspection", "N92c1": "Critical Feature Inspection Date",
        "N93a1": "Critical Feature Inspection Month", "N93a2": "Critical Feature Inspection Year",
        "N93b1": "Underwater Inspection Date Month", "N93b2": "Underwater Inspection Date Year",
        "N93c1": "Other Inspection Date Month", "N93c2": "Other Inspection Date Year",
        "N97": "Year of Improvement", "N94": "Bridge Improvement Cost", "N95": "Roadway Improvement Cost",
        "N96": "Total Project Cost", "N106": "Year Reconstructed", "N200": "Division",
        "N201": "District", "N202": "COE No", "N203": "Inspection Office",
        "N204": "Inspection Team Leader", "N205": "Inspection Cost", "N216": "Seismic Category",
        "N230": "Bridge Name", "Sf": "SF Score", "Sr": "SR Score",
        "N7": "Facility Carried by Structure", "N231 Life Safety Score": "Life Safety Score",
        "N232 Mission Score": "Mission Score", "N233 Bus Ln": "Business Line",
    }
    
    try:
        df = pd.read_csv(csv_file_path, dtype=str, keep_default_na=False)
        
        # Filter for CEMVR district
        if "N201" in df.columns:
            df = df[df["N201"].astype(str).str.strip().str.upper() == "CEMVR"]
        
        # Select and rename columns
        available_columns = [c for c in rename_map.keys() if c in df.columns]
        df_sel = df[available_columns].copy()
        df_sel.rename(columns=rename_map, inplace=True)
        df_sel["CEBIS Landing Page"] = "https://cebis.cwbi.mil/ords/r/cebis/cebis/home"

        def dms_to_decimal(deg, minute, sec):
            """Convert degrees, minutes, seconds to decimal degrees."""
            d = float(deg) if deg not in (None, "") else 0.0
            m = float(minute) if minute not in (None, "") else 0.0
            s = float(sec) if sec not in (None, "") else 0.0
            return (abs(d) + (m / 60.0) + (s / 3600.0)) * (-1.0 if str(d).strip().startswith("-") else 1.0)
        
        lat_cols = ("Latitude deg", "Latitude Min", "Latitude Sec")
        lon_cols = ("Longitude deg", "Longitude min", "Longitude sec")
        
        df_sel["Latitude"] = df_sel.apply(
            lambda r: dms_to_decimal(r.get(lat_cols[0]), r.get(lat_cols[1]), r.get(lat_cols[2])),
            axis=1
        )
        df_sel["Longitude"] = df_sel.apply(
            lambda r: -1.0 * dms_to_decimal(r.get(lon_cols[0]), r.get(lon_cols[1]), r.get(lon_cols[2])),
            axis=1
        )
        
        # Save a CSV with columns that match the GeoJSON properties (without geometry columns)
        columns_for_csv = [col for col in df_sel.columns if col not in ['Latitude', 'Longitude']]
        df_sel[columns_for_csv].to_csv(csv_file_path, index=False, encoding="utf-8")
        print(f"Cleaned CSV re-saved to: {csv_file_path}")

        # Create GeoJSON features
        features = []
        for _, row in df_sel.iterrows():
            try:
                lat, lon = float(row["Latitude"]), float(row["Longitude"])
                if lat == 0.0 and lon == 0.0:
                    continue
                props = row.drop(labels=["Latitude", "Longitude"]).to_dict()
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [lon, lat]},
                    "properties": props
                })
            except (ValueError, TypeError):
                continue
        
        geojson = {"type": "FeatureCollection", "features": features}
        geojson_output_path = os.path.splitext(csv_file_path)[0] + ".geojson"
        
        with open(geojson_output_path, "w", encoding="utf-8") as f:
            json.dump(geojson, f, indent=2)
        
        print(f"GeoJSON successfully created at: {geojson_output_path}")
        return geojson_output_path
        
    except Exception as e:
        print(f"Error creating GeoJSON: {e}")
        return None


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

def main():
    """Main function to orchestrate the entire download and upload process."""
    # --- Configuration ---
    import json

    # Load configuration
    config_path = "C:/Workspace/GIT/USACE-AIS-Scripts/config.json"

    with open(config_path, 'r') as f:
        config = json.load(f)


    SHAREPOINT_URL = config['sharepoint_base_url']
    SHAREPOINT_LIBRARY_PATH = "/sites/TDL-CEMVR-EMSUsers/Shared%20Documents/DATASETS/CEBIS"
    EMAIL_ADDRESS = config['sharepoint_username'] # "
    PORTAL_URL = "https://geoportal.mvr.usace.army.mil/b5portal/home/item.html?id=990906b45da840b29e9e125bb6452d18"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(accept_downloads=True, ignore_https_errors=True)
        page = context.new_page()
        
        try:
            # Step 1: Download the CEBIS report
            csv_file = download_cebis_report(page)
            if not csv_file:
                print("\nFailed to download CEBIS report. Aborting.")
                return

            # Step 2: Upload the original CSV to SharePoint
            page_sp = context.new_page()
            if not upload_to_sharepoint(
                page_sp,
                csv_file,
                SHAREPOINT_URL,
                SHAREPOINT_LIBRARY_PATH,
                EMAIL_ADDRESS
            ):
                print("\nFailed to upload to SharePoint. Aborting further uploads.")
                return
            page_sp.close()
            
            # Step 3: Create the GeoJSON file from the CSV
            geojson_file = create_geojson_from_csv(csv_file)
            if not geojson_file:
                print("\nFailed to create GeoJSON file. Aborting.")
                return

            # Step 4: Upload the new GeoJSON to ESRI Portal
            page_portal = context.new_page()
            if not upload_to_esri_portal(page_portal, geojson_file, PORTAL_URL):
                print("\nFailed to upload to ESRI Portal.")
            page_portal.close()
            
            print("\n--- All operations completed successfully! ---")
            
        except Exception as e:
            print(f"\nA critical error occurred in the main process: {e}")
            
        finally:
            print("\nClosing browser.")
            browser.close()


if __name__ == "__main__":
    main()