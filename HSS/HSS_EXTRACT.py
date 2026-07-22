"""
HSS Metrics to SharePoint Sync Script

This script automates the process of extracting required inspection data from the HSS
(Hydraulic Steel Structures) web application and uploading it to SharePoint.

Process Flow:
1. Navigates to the HSS web application and authenticates via CAC
2. Extracts the Required Inspections metrics table from the HSS Queries page
3. Converts the extracted data to CSV format with structure details and inspection dates
4. Uploads the CSV file to a designated SharePoint document library
5. Replaces existing file if it already exists in SharePoint

The script uses Playwright for browser automation to handle both web scraping and
SharePoint authentication/upload operations.

Requirements:
- Playwright Python package
- Access to HSS web application (CAC authentication required)
- SharePoint permissions for the target document library
- Network access to USACE internal systems

Author: Ryan Benac CEMVR EC-D
Created: [Original Date]
Updated: 3/10/2026 - Refactored to use centralized SharePointUpload module, improved documentation

Usage:
    Activate virtual environment:
    .\.venv\Scripts\Activate.ps1
    
    Set execution policy if needed:
    Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
    
    Run script:
    python hss_to_sharepoint.py
"""

import sys
import json
import os
import csv
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError
import time

# Add the A_MODULES directory to system path for custom module imports
MODULES_PATH = r'C:\Workspace/GIT/USACE-AIS-Scripts/A_Modules'

if MODULES_PATH not in sys.path:
    sys.path.insert(0, MODULES_PATH)

# Import the refactored SharePoint upload function
from SharePointUpload import upload_to_sharepoint


def download_HSS_report(sharepoint_url, sharepoint_library_path, email_address):
    """
    Downloads the HSS Required Inspections report and uploads it to SharePoint.
    
    This function navigates to the HSS web application, authenticates via CAC,
    extracts the required inspections metrics table, saves it as a CSV file,
    and uploads it to SharePoint.
    
    Args:
        sharepoint_url (str): The base URL of the SharePoint site
        sharepoint_library_path (str): The path to the SharePoint document library
        email_address (str): The user's email address for authentication
    
    Returns:
        bool: True if the entire process succeeds, False otherwise
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # Keep browser visible for authentication
        context = browser.new_context(accept_downloads=True, ignore_https_errors=True)
        page = context.new_page()

        # Set a very generous timeout for initial navigation (10 minutes for CAC selection)
        initial_timeout = 600000  # 10 minutes in milliseconds

        # 1. Navigate to the HSS Application
        hss_url = "https://apps1.nww.ds.usace.army.mil/hss/"
        print(f"Navigating to: {hss_url}")
        print("Please select your CAC certificate when prompted...")
        
        try:
            page.goto(hss_url, timeout=initial_timeout)
            print("✓ HSS Page loaded successfully.")
        except TimeoutError as e:
            print(f"✗ TimeoutError: Initial navigation to {hss_url} timed out after {initial_timeout/1000} seconds.")
            print("Please ensure you select a certificate promptly. Restart the script after authenticating.")
            browser.close()
            return False
        except Exception as e:
            print(f"✗ An unexpected error occurred during navigation: {e}")
            browser.close()
            return False

        # 2. Navigate to the HSS Required Inspections Metrics page
        metrics_url = "https://apps1.nww.ds.usace.army.mil/hss/Queries/RequiredInspections"
        print(f"\nNavigating to HSS Required Inspections: {metrics_url}")
        
        try:
            page.goto(metrics_url, timeout=initial_timeout)
            # Wait for network idle to ensure page is fully loaded
            page.wait_for_load_state("networkidle", timeout=60000)
            page.wait_for_timeout(2000)  # Additional wait for dynamic content
            print("✓ Metrics page loaded successfully.")

            # 3. Extract metrics table rows into a CSV
            print("\nExtracting metrics table data...")
            try:
                containers = page.query_selector_all("div.table.table-borderless.table-striped")
                rows_out = []
                base_url = "https://apps1.nww.ds.usace.army.mil"
                
                for container in containers:
                    # Get project name from header
                    header = container.query_selector("div.row.alert.alert-info.mb-0 h3")
                    project = header.inner_text().strip() if header else ""

                    # Get all structure entries for this project
                    entry_rows = container.query_selector_all("div.row.p-1.mb-1")
                    for r in entry_rows:
                        a_id = r.query_selector("div.col-4 a.structure-link-text")
                        a_desc = r.query_selector("div.col-6 a.structure-link-text")
                        date_span = r.query_selector("div.col-2 span")
                        
                        if not a_id or not a_desc:
                            continue
                        
                        # Extract HSS ID (remove leading numbering like '1. ' or '10. ')
                        raw_hss = a_id.inner_text().strip()
                        if "." in raw_hss:
                            hss_id = raw_hss.split(".", 1)[1].strip()
                        else:
                            hss_id = raw_hss
                        
                        description = a_desc.inner_text().strip()
                        
                        # Build full URL
                        href = a_id.get_attribute("href") or ""
                        if href.startswith("/"):
                            url = base_url + href
                        else:
                            url = href
                        
                        inspection_date = date_span.inner_text().strip() if date_span else ""
                        
                        rows_out.append({
                            "project": project,
                            "hss_id": hss_id,
                            "description": description,
                            "inspection_date": inspection_date,
                            "url": url,
                        })

                print(f"✓ Extracted {len(rows_out)} inspection records")

                # 4. Write CSV to file
                new_file_path = "C:\\Workspace\\AUTOMATED_SCRIPTS\\HSS\\HSS_EXPORT.csv"
                
                # Remove existing file if present
                if os.path.exists(new_file_path):
                    os.remove(new_file_path)
                    print(f"Removed existing file: {new_file_path}")
                
                with open(new_file_path, "w", newline="", encoding="utf-8") as csvfile:
                    fieldnames = ["project", "hss_id", "description", "inspection_date", "url"]
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    writer.writeheader()
                    for out in rows_out:
                        writer.writerow(out)

                print(f"✓ Metrics exported to CSV: {new_file_path}")
                
            except Exception as e:
                print(f"✗ Error extracting metrics to CSV: {e}")
                browser.close()
                return False
            
            # 5. Upload the CSV to SharePoint
            try:
                print("\n" + "=" * 70)
                print("Uploading CSV to SharePoint...")
                print("=" * 70)
                
                # Create a new page for SharePoint upload
                sp_page = context.new_page()
                
                upload_successful = upload_to_sharepoint(
                    page=sp_page,
                    file_path=new_file_path,
                    sharepoint_url=sharepoint_url,
                    sharepoint_library_path=sharepoint_library_path,
                    email_address=email_address
                )
                
                sp_page.close()
                
                if upload_successful:
                    print("✓ HSS report uploaded to SharePoint successfully.")
                else:
                    print("✗ HSS report upload to SharePoint failed.")
                    browser.close()
                    return False
                    
            except Exception as e:
                print(f"✗ Error during upload step: {e}")
                browser.close()
                return False
                
        except TimeoutError:
            print(f"✗ Timeout navigating to {metrics_url}.")
            print("You may need to authenticate or the page selector needs adjustment.")
            browser.close()
            return False
        except Exception as e:
            print(f"✗ Error navigating to HSS Inspections: {e}")
            browser.close()
            return False
    
        browser.close()
        print("\n" + "=" * 70)
        print("✓ Process completed successfully!")
        print("=" * 70)
        return True


# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == "__main__":
    # Configuration
    import json

    # Load configuration
    config_path = "C:\\Workspace\\GIT\\USACE-AIS-Scripts\\config.json"

    with open(config_path, 'r') as f:
        config = json.load(f)

    SHAREPOINT_URL = config['sharepoint_base_url']
    SHAREPOINT_LIBRARY_PATH = "/sites/TDL-CEMVR-EMSUsers/Shared%20Documents/DATASETS/HSS"
    EMAIL_ADDRESS = config['sharepoint_username']

    print("=" * 70)
    print("HSS Metrics to SharePoint Sync")
    print("=" * 70)
    print(f"SharePoint URL: {SHAREPOINT_URL}")
    print(f"Library Path: {SHAREPOINT_LIBRARY_PATH}")
    print(f"Email: {EMAIL_ADDRESS}")
    print("=" * 70)
    print()

    # Run the download and upload process
    success = download_HSS_report(SHAREPOINT_URL, SHAREPOINT_LIBRARY_PATH, EMAIL_ADDRESS)
    
    if success:
        print("\n✓ Script completed successfully!")
    else:
        print("\n✗ Script completed with errors.")