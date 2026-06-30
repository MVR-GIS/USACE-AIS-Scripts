"""
EMS to SharePoint Data Sync Script

This script automates the process of downloading data from the EMS (Enterprise Management System)
REST API and uploading the resulting JSON files to a SharePoint document library.

Process Flow:
1. Fetches data from specified EMS REST API endpoints
2. Saves the data as JSON files locally
3. Uploads each JSON file to the designated SharePoint library
4. Replaces existing files if they already exist in SharePoint

The script uses Playwright for browser automation to handle both API requests and
SharePoint authentication/upload operations.

Requirements:
- Playwright Python package
- Access to EMS REST API
- SharePoint permissions for the target document library
- CAC authentication for SharePoint access

Author: Ryan Benac CEMVR EC-D
Created: 8/14/2025
Updated: 3/10/2026 - Refactored to use centralized SharePointUpload module, fixed async conflict
"""

import sys
import json
from pathlib import Path
from playwright.sync_api import sync_playwright
import requests

import json

# Load configuration
config_path = "C:/Workspace/GIT/projectwise/config.json"

with open(config_path, 'r') as f:
    config = json.load(f)

    
# Connection parameters
MODULES_PATH = config["modules_path"]

# Add the A_MODULES directory to system path for custom module imports
if MODULES_PATH not in sys.path:
    sys.path.insert(0, MODULES_PATH)

# Import the refactored SharePoint upload function
from SharePointUpload import upload_to_sharepoint


def fetch_and_save(url, file_path, timeout=300):
    """
    Fetches data from a URL and saves it as JSON or raw text.
    
    Uses the requests library instead of Playwright to avoid async conflicts.
    
    Args:
        url (str): The URL to fetch data from
        file_path (str): The local file path where data should be saved
        timeout (int): Request timeout in seconds (default: 300)
    
    Returns:
        str | None: The file path if successful, None if failed
    """
    print(f"Requesting data from {url}")
    print(f"Saving to: {file_path}")
    
    try:
        response = requests.get(url, timeout=timeout, verify=False)
        response.raise_for_status()
        
        # Try to parse as JSON
        try:
            data = response.json()
            with open(file_path, "w", encoding='utf-8') as f:
                json.dump(data, f, indent=4)
            print(f"Successfully saved JSON to {file_path}")
        except json.JSONDecodeError:
            # If not JSON, save as raw text
            print(f"Response from {url} is not valid JSON. Saving raw text.")
            with open(file_path, "w", encoding='utf-8') as f:
                f.write(response.text)
            print(f"Successfully saved raw text to {file_path}")
        
        return file_path
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from {url}: {e}")
        return None
    except Exception as e:
        print(f"Unexpected error saving data: {e}")
        return None


# Configuration
SHAREPOINT_URL = config['sharepoint_base_url']
SHAREPOINT_LIBRARY_PATH = "/sites/TDL-CEMVR-EMSUsers/Shared%20Documents/DATASETS"
EMAIL_ADDRESS = config['sharepoint_username']

# Define URLs and file paths
urls_and_paths = [
    ("https://ems.sec.usace.army.mil/api/rest/CHIEFS/CEMVR", "C:\\Workspace\\AUTOMATED_SCRIPTS\\EMS\\chief.json"),
    ("https://ems.sec.usace.army.mil/api/rest/PEP_DATA/CEMVR", "C:\\Workspace\\AUTOMATED_SCRIPTS\\EMS\\pep.json"),
    # ("https://ems.sec.usace.army.mil/api/REST/PERCENT_STATUS/CEMVR", "C:\\Workspace\\AUTOMATED_SCRIPTS\\EMS\\percent_complete.json"),
]

# Define a timeout for the slow URL (in seconds) - 10 minutes
percent_status_timeout = 600

# Create a single browser context for all SharePoint uploads
print("Starting EMS to SharePoint sync process...")
print("=" * 70)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)  # Visible browser for authentication
    context = browser.new_context(ignore_https_errors=True)
    
    # Process each URL, save the data, and upload to SharePoint
    for url, file_path in urls_and_paths:
        print(f"\nProcessing: {url}")
        print("-" * 70)
        
        # Fetch and save data
        if url == "https://ems.sec.usace.army.mil/api/REST/PERCENT_STATUS/CEMVR":
            saved_file_path = fetch_and_save(url, file_path, timeout=percent_status_timeout)
        else:
            saved_file_path = fetch_and_save(url, file_path)

        # Upload to SharePoint if fetch was successful
        if saved_file_path:
            print(f"\nUploading to SharePoint...")
            
            # Create a new page for each upload
            page = context.new_page()
            
            upload_successful = upload_to_sharepoint(
                page=page,
                file_path=saved_file_path,
                sharepoint_url=SHAREPOINT_URL,
                sharepoint_library_path=SHAREPOINT_LIBRARY_PATH,
                email_address=EMAIL_ADDRESS
            )
            
            if upload_successful:
                print(f"✓ Successfully uploaded {file_path} to SharePoint.")
            else:
                print(f"✗ Failed to upload {file_path} to SharePoint.")
            
            page.close()
        else:
            print(f"✗ Failed to save data for {url}. Skipping upload.")
        
        print()
    
    print("=" * 70)
    print("Closing browser...")
    browser.close()

print("\n✓ Script completed successfully!")