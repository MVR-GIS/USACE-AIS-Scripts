"""
OpenGround to ESRI Portal Upload Script

This script automates the process of uploading OpenGround boring data to an ESRI ArcGIS 
Portal feature layer.

Process Flow:
1. Verifies that the OpenGround GeoJSON file exists locally
2. Navigates to the specified ESRI Portal item page
3. Initiates the "Update Data" workflow to overwrite the existing feature layer
4. Uploads the GeoJSON file from the local device
5. Waits for the overwrite operation to complete and the portal to refresh

The script uses Playwright for browser automation to handle the ESRI Portal interface
and file upload operations. The overwrite operation replaces all existing features in
the layer with the new boring data from the GeoJSON file.

Requirements:
- Playwright Python package
- Access to ESRI ArcGIS Portal (authentication required)
- Valid GeoJSON file with OpenGround boring data
- Portal permissions to update the target feature layer

Author: Ryan Benac CEMVR EC-D
Created: [Original Date]
Updated: 3/10/2026 - Refactored to use centralized PortalUpload module, improved documentation

Usage:
    Activate virtual environment:
    .\.venv\Scripts\Activate.ps1
    
    Run script:
    python openground_to_portal.py
"""

import sys
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError, Page

# Add the A_MODULES directory to system path for custom module imports
MODULES_PATH = r'C:\Workspace\GIT\USACE-AIS-Scripts\A_Modules'
if MODULES_PATH not in sys.path:
    sys.path.insert(0, MODULES_PATH)

# Import the refactored Portal upload function
from PortalUpload import upload_to_esri_portal


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

def main():
    """
    Main function to orchestrate the OpenGround GeoJSON upload to ESRI Portal.
    
    This function verifies the existence of the OpenGround borings GeoJSON file and 
    uploads it to the configured ESRI Portal feature layer, overwriting existing data.
    """
    # --- Configuration ---
    PORTAL_URL = "https://geoportal.mvr.usace.army.mil/b5portal/home/item.html?id=1d30a71e4357409a96afb8e9695b0db7"
    GEOJSON_FILE = r"C:\Workspace\AUTOMATED_SCRIPTS\OpenGround\OUTPUT GEOJSON\openGround_MVR_borings.geojson"

    print("=" * 70)
    print("OpenGround to ESRI Portal Upload")
    print("=" * 70)
    print(f"Portal URL: {PORTAL_URL}")
    print(f"GeoJSON File: {GEOJSON_FILE}")
    print("=" * 70)
    print()

    # Step 1: Verify GeoJSON file exists
    print("Verifying GeoJSON file exists...")
    if not os.path.exists(GEOJSON_FILE):
        print(f"✗ Error: GeoJSON file not found at: {GEOJSON_FILE}")
        print("Please ensure the OpenGround data has been processed and the GeoJSON file exists.")
        return False

    file_size = os.path.getsize(GEOJSON_FILE)
    print(f"✓ GeoJSON file found ({file_size:,} bytes)")
    
    # Optional: Count features in GeoJSON
    try:
        with open(GEOJSON_FILE, 'r', encoding='utf-8') as f:
            geojson_data = json.load(f)
            feature_count = len(geojson_data.get('features', []))
            print(f"✓ GeoJSON contains {feature_count:,} boring records")
    except Exception as e:
        print(f"⚠ Could not read feature count: {e}")
    
    print()

    # Step 2: Upload to ESRI Portal
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # Visible for authentication
        context = browser.new_context(accept_downloads=True, ignore_https_errors=True)
        page_portal = context.new_page()

        try:
            print("=" * 70)
            print("Starting upload to ESRI Portal...")
            print("=" * 70)
            
            upload_success = upload_to_esri_portal(
                page=page_portal,
                geojson_path=GEOJSON_FILE,
                portal_url=PORTAL_URL
            )
            
            if upload_success:
                print("\n" + "=" * 70)
                print("✓ OpenGround boring data successfully uploaded to ESRI Portal!")
                print("=" * 70)
            else:
                print("\n" + "=" * 70)
                print("✗ Failed to upload OpenGround data to ESRI Portal.")
                print("=" * 70)
                return False
            
        except Exception as e:
            print(f"\n✗ A critical error occurred in the main process: {e}")
            import traceback
            traceback.print_exc()
            return False
            
        finally:
            print("\nClosing browser...")
            page_portal.close()
            browser.close()

    print("\n✓ Script completed successfully!")
    return True


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)