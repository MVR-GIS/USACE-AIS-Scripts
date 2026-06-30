#.\.venv\Scripts\Activate.ps1
#Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
import json
import os
import pandas as pd
from playwright.sync_api import sync_playwright, TimeoutError, Download
import time  # Import the time module

def download_cebis_report(sharepoint_url, sharepoint_library_path, email_address):
    """Downloads the CEBIS NBI Open Inventory Search report and uploads it to SharePoint."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # Keep browser visible for authentication
        context = browser.new_context(accept_downloads=True, ignore_https_errors=True)
        page = context.new_page()

        # Set a very generous timeout for initial navigation (e.g., 10 minutes)
        initial_timeout = 600000  # 10 minutes in milliseconds

        # 1. Navigate to the CEBIS Applets Page
        cebis_url = "https://cebis.sec.usace.army.mil/ords/r/cebis/applets/"
        print(f"Navigating to: {cebis_url}")
        try:
            page.goto(cebis_url, timeout=initial_timeout)
            print("CEBIS Applets Page loaded successfully.")
        except TimeoutError as e:
            print(f"TimeoutError: Initial navigation to {cebis_url} timed out after {initial_timeout/1000} seconds. Please ensure you select a certificate promptly.  Restart the script after authenticating.")
            browser.close()
            return False
        except Exception as e:
            print(f"An unexpected error occurred during navigation: {e}")
            browser.close()
            return False

        # 2. Click the Log In Button
        print("Clicking the Log In button...")
        try:
            page.click("button[id='B3457977243511861']", timeout=60000) # Reverted to shorter timeout for actual clicks
            print("Log In button clicked")
        except Exception as e:
            print(f"Error clicking Log In button: {e}")
            browser.close()
            return False

        # 3. Click the Correct Card to Access the Report
        print("Clicking the CEBIS NBI Open Inventory Search card...")
        try:
            page.click("li.t-Cards-item div.t-Card a div.t-Card-titleWrap h3.t-Card-title:has-text('CEBIS NBI Open Inventory Search')", timeout=60000)
            print("CEBIS NBI Open Inventory Search card clicked")
        except Exception as e:
            print(f"Error clicking CEBIS NBI Open Inventory Search card: {e}")
            browser.close()
            return False

        # 4. Click the Actions Button
        print("Clicking the Actions button...")
        try:
            page.click("button[id='R21330164091369244_actions_button']", timeout=60000)
            print("Actions button clicked")
        except Exception as e:
            print(f"Error clicking Actions button: {e}")
            browser.close()
            return False

        # 5. Click the Download Option in the Actions Menu
        print("Clicking the Download option in the Actions menu...")
        try:
            page.click("button[id='R21330164091369244_actions_menu_14i']", timeout=60000)
            print("Download option clicked")
        except Exception as e:
            print(f"Error clicking Download option: {e}")
            browser.close()
            return False

        # 6. Click the Second Download Button
        print("Clicking the final Download button...")
        try:
            with page.expect_download() as download_info:
                page.click("button.ui-button--hot", timeout=60000, force=True)  # ADDED force=True HERE
            download = download_info.value
            print("Final Download button clicked")
        except Exception as e:
            print(f"Error clicking final Download button: {e}")
            browser.close()
            return False

        # 7. Wait for the Download to Complete and Rename File
        print("Waiting for download to complete...")
        try:
            file_path = download.path()
            new_file_path = "C:\\Workspace\\AUTOMATED_SCRIPTS\\CEBIS\\CEBIS_EXPORT.csv"
            # Check if the file exists, and remove it if it does
            if os.path.exists(new_file_path):
                os.remove(new_file_path)
                print(f"Existing file '{new_file_path}' removed.")
            os.rename(file_path, new_file_path)
            print(f"File downloaded and renamed to: {new_file_path}")
        except TimeoutError as te:
            print(f"Download timed out: {te}")
            browser.close()
            return False
        except Exception as e:
            print(f"Error during download: {e}")
            browser.close()
            return False
        finally:
            pass  # Removed dialog handler

        print("Beginning upload to Sharepoint")
        upload_successful = upload_to_sharepoint(new_file_path, sharepoint_url, sharepoint_library_path, email_address, p, browser)
        browser.close()
        if upload_successful:
            print("CEBIS report downloaded and uploaded to Sharepoint Successfully")
            # Also convert the CSV to GeoJSON for ArcGIS Portal upload
            try:
                geojson_path = upload_to_portal(new_file_path)
                if geojson_path:
                    print(f"GeoJSON created at: {geojson_path}")
                else:
                    print("GeoJSON creation failed.")
            except Exception as e:
                print(f"Error creating GeoJSON: {e}")
        return True

def upload_to_sharepoint(file_path, sharepoint_url, sharepoint_library_path, email_address, p, browser):
    """Uploads a file to a SharePoint document library using Playwright."""
    page = browser.new_page()  # Create new page for upload

    full_sharepoint_url = f"{sharepoint_url}{sharepoint_library_path}"
    print(f"Navigating to: {full_sharepoint_url} (upload)...")
    try:
        page.goto(full_sharepoint_url, timeout=60000) # increased timeout
    except Exception as e:
        print(f"Error Navigating to {full_sharepoint_url} (upload): {e}")
        page.close()
        return False

    # 2. **Attempt to Fill in Email (if on login page)**
    print("Attempting to fill in email address...")
    try:
        # Try to find the email input field. You might need to adjust the selector!
        page.wait_for_selector("input[type='email']", timeout=10000)  # Wait up to 10 seconds
        page.fill("input[type='email']", email_address)
        print(f"Email address '{email_address}' filled in.")

        # Try to click the "Next" button (if it exists)
        try:
            page.click("input[type='submit']", timeout=5000)
            print("Clicked 'Next' button.")
        except:
            print("No 'Next' button found, proceeding...")  # May auto redirect.

    except Exception as e:
        print(f"Email field not found or unable to fill. Possibly already logged in or different login page. Error: {e}")
        print("Assuming already logged in or different login flow.")
        # Continue with the upload process even if email filling fails

    # 3. Click the Upload Button
    print("Clicking the Upload button...")
    try:
        page.click("button[data-automationid='uploadCommand']", timeout=60000)
        print("Upload button clicked")
    except Exception as e:
        print(f"Error clicking Upload button: {e}")
        page.close()
        return False

    # 4. Click the "Files" Button in the Upload Popup
    print("Clicking the 'Files' button in the upload popup...")
    try:
        # Use more specific selector
        page.wait_for_selector("div.ms-ContextualMenu-linkContent span:has-text('Files')", timeout=60000)
        page.click("div.ms-ContextualMenu-linkContent span:has-text('Files')", timeout=60000)  # increased timeout, using text selector.
        print("'Files' button clicked")
    except Exception as e:
        print(f"Error clicking 'Files' button: {e}")
        page.close()
        return False

    # 5. Wait for the File Input Element to Appear
    print("Waiting for the file input element to appear...")
    try:
        page.wait_for_selector("input[type='file']", timeout=60000)  # increased timeout
        print("File input element found")
    except Exception as e:
        print(f"Error: File input element not found after clicking 'Files' button. Check selector. {e}")
        page.close()
        return False

    # 6. Upload the file
    print(f"Uploading file: {file_path}")
    try:
        page.set_input_files("input[type='file']", file_path)
        print("File uploaded successfully.")
    except Exception as e:
        print(f"Error setting file input: {e}")
        page.close()
        return False

    # 7. Click the "Replace" Button in the Confirmation Dialog
    print("Waiting for and clicking the 'Replace' button...")
    try:
        page.wait_for_selector("button[name='Replace'] span:has-text('Replace')", timeout=60000)
        page.click("button[name='Replace'] span:has-text('Replace')", timeout=60000)
        print("'Replace' button clicked")
    except Exception as e:
        print(f"Error clicking 'Replace' button: {e}")
        page.close()
        return False

    # 8. Optional: Wait for the upload to complete.
    print("Waiting for upload to complete (adjust timeout if needed)...")
    page.wait_for_timeout(5000)  # Adjust as necessary.
    print("File uploaded successfully (hopefully!).")
    page.close()
    return True


def upload_to_portal(csv_file_path, geojson_output_path=None):
    """Reads the CEBIS CSV, keeps and renames specific columns, computes Latitude/Longitude,
    and writes a GeoJSON FeatureCollection to `geojson_output_path` (or same name with .geojson).
    Returns the output path on success, or None on failure.
    """
    # Mapping of original columns -> new names (from user's RenamedColumns)
    rename_map = {
        "N90mn": "Inspection Month",
        "N90yr": "Inspection Year",
        "N91": "Inspection frequency (months)",
        "N236 Prj P2 No": "P2 No",
        "N27 Year": "Year Built",
        "N16d": "Latitude deg",
        "N16m": "Latitude Min",
        "N16s": "Latitude Sec",
        "N17d": "Longitude deg",
        "N17m": "Longitude min",
        "N17s": "Longitude sec",
        "N19": "Bypass detour length",
        "N9": "Location",
        "N21": "Maintenance Responsibility",
        "N22": "Owner",
        "N26": "Fucntional Class",
        "N45": "Number of Spans",
        "N92a1": "Critical Feature Inspection",
        "N92a2": "Critical Feature Inspection Months",
        "N92b1": "Underwater Inspection",
        "N92b2": "Other spec Inspection",
        "N92c1": "Critical Feature Inspection Date",
        "N93a1": "Critical Feature Inspection Month",
        "N93a2": "Critical Feature Inspection Year",
        "N93b1": "Underwater Inspection Date Month",
        "N93b2": "Underwater Inspection Date Year",
        "N93c1": "Other Inspection Date Month",
        "N93c2": "Other Inspection Date Year",
        "N97": "Year of Improvement",
        "N94": "Bridge Improvement Cost",
        "N95": "Roadway Improvement Cost",
        "N96": "Total Project Cost",
        "N106": "Year Reconstructed",
        "N200": "Division",
        "N201": "District",
        "N202": "COE No",
        "N203": "Inspection Office",
        "N204": "Inspection Team Leader",
        "N205": "Inspection Cost",
        "N216": "Seismic Category",
        "N230": "Bridge Name",
        "Sf": "SF Score",
        "Sr": "SR Score",
        "N7": "Facility Carried by Structure",
        "N231 Life Safety Score": "Life Safety Score",
        "N232 Mission Score": "Mission Score",
        "N233 Bus Ln": "Business Line",
    }

    try:
        df = pd.read_csv(csv_file_path, dtype=str, keep_default_na=False)
    except Exception as e:
        print(f"Error reading CSV '{csv_file_path}': {e}")
        return None

    # Filter rows where N201 == 'CEMVR' if that column exists
    if "N201" in df.columns:
        try:
            df = df[df["N201"].astype(str).str.strip().str.upper() == "CEMVR"]
            print(f"Filtered rows where N201 == CEMVR; remaining rows: {len(df)}")
        except Exception as e:
            print(f"Warning: error filtering N201 column: {e}")

    # Keep only columns that exist in the CSV (original names)
    available_columns = [c for c in rename_map.keys() if c in df.columns]
    if not available_columns:
        print("No expected CEBIS columns found in CSV. Aborting geojson creation.")
        return None

    df_sel = df[available_columns].copy()
    # Rename columns per mapping
    df_sel.rename(columns=rename_map, inplace=True)

    # Add landing page column for every row
    df_sel["CEBIS Landing Page"] = "https://cebis.cwbi.mil/ords/r/cebis/cebis/home"

    # Helper to convert DMS (deg, min, sec) to decimal degrees
    def dms_to_decimal(deg, minute, sec):
        try:
            d = float(deg) if deg not in (None, "") else 0.0
        except:
            d = 0.0
        try:
            m = float(minute) if minute not in (None, "") else 0.0
        except:
            m = 0.0
        try:
            s = float(sec) if sec not in (None, "") else 0.0
        except:
            s = 0.0
        sign = -1.0 if str(d).strip().startswith("-") else 1.0
        return sign * (abs(d) + (m / 60.0) + (s / 3600.0))

    # Compute Latitude and Longitude columns from the renamed DMS columns if present
    lat_cols = ("Latitude deg", "Latitude Min", "Latitude Sec")
    lon_cols = ("Longitude deg", "Longitude min", "Longitude sec")

    def compute_coord(row, cols):
        return dms_to_decimal(row.get(cols[0], ""), row.get(cols[1], ""), row.get(cols[2], ""))

    # Only compute if at least the degree column exists
    if lat_cols[0] in df_sel.columns:
        df_sel["Latitude"] = df_sel.apply(lambda r: compute_coord(r, lat_cols), axis=1)
    else:
        df_sel["Latitude"] = None

    if lon_cols[0] in df_sel.columns:
        # Longitude values should be negated to be western hemisphere
        df_sel["Longitude"] = df_sel.apply(lambda r: -1.0 * compute_coord(r, lon_cols), axis=1)
    else:
        df_sel["Longitude"] = None

    # Drop rows without valid numeric coordinates
    def is_valid_coord(v):
        try:
            return v is not None and v != "" and not pd.isna(float(v))
        except:
            return False

    df_sel = df_sel[df_sel["Latitude"].apply(is_valid_coord) & df_sel["Longitude"].apply(is_valid_coord)]
    # Filter out explicit 0,0 coordinates
    try:
        df_sel = df_sel[~((df_sel["Latitude"].astype(float) == 0.0) & (df_sel["Longitude"].astype(float) == 0.0))]
    except Exception:
        # if conversion fails, ignore and keep current df_sel
        pass

    # Overwrite the CSV with the cleaned, renamed CSV including the landing page and lat/lon
    try:
        df_sel.to_csv(csv_file_path, index=False, encoding="utf-8")
        print(f"Cleaned CSV written to: {csv_file_path}")
    except Exception as e:
        print(f"Warning: failed to overwrite CSV '{csv_file_path}': {e}")

    # Build GeoJSON FeatureCollection
    features = []
    for _, row in df_sel.iterrows():
        try:
            lat = float(row["Latitude"])
            lon = float(row["Longitude"])
        except Exception:
            continue
        props = row.drop(labels=["Latitude", "Longitude"]).to_dict()
        # Convert any numpy types to native Python types
        props = {k: (None if v == "" else (v if not pd.isna(v) else None)) for k, v in props.items()}
        feature = {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": props,
        }
        features.append(feature)

    geojson = {"type": "FeatureCollection", "features": features}

    if geojson_output_path is None:
        geojson_output_path = os.path.splitext(csv_file_path)[0] + ".geojson"

    try:
        with open(geojson_output_path, "w", encoding="utf-8") as fh:
            json.dump(geojson, fh, ensure_ascii=False, indent=2)
        print(f"GeoJSON written to: {geojson_output_path}")
        return geojson_output_path
    except Exception as e:
        print(f"Error writing GeoJSON '{geojson_output_path}': {e}")
        return None

# Configuration
SHAREPOINT_URL = ""
SHAREPOINT_LIBRARY_PATH = "/sites/TDL-CEMVR-EMSUsers/Shared%20Documents/DATASETS/CEBIS"  # Correct path
EMAIL_ADDRESS = ""  # Replace with your email

# Run process
download_cebis_report(SHAREPOINT_URL, SHAREPOINT_LIBRARY_PATH, EMAIL_ADDRESS)
