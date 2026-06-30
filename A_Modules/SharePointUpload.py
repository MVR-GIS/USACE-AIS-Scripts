"""
SharePointUpload.py

This module provides functionality for uploading files to SharePoint document libraries
using Playwright for browser automation. It handles authentication and file replacement
operations.

Author: Ryan Benac
Created: 3/10/2026
Updated: 4/3/2026 - Added improved timing and waits for batch file execution
"""

import time
from playwright.sync_api import Page, TimeoutError


def upload_to_sharepoint(
    page: Page,
    file_path: str,
    sharepoint_url: str,
    sharepoint_library_path: str,
    email_address: str
) -> bool:
    """
    Uploads a file to a SharePoint document library, replacing any existing file with the same name.
    
    This function navigates to a SharePoint document library, handles authentication if needed,
    and uploads a file using the SharePoint web interface. If a file with the same name exists,
    it will be replaced.
    
    Args:
        page (Page): A Playwright Page object for browser automation.
        file_path (str): The local file system path to the file to upload.
        sharepoint_url (str): The base URL of the SharePoint site (e.g., "https://usace.dps.mil").
        sharepoint_library_path (str): The path to the document library relative to the base URL
                                      (e.g., "/sites/MySite/Shared%20Documents/MyFolder").
        email_address (str): The user's email address for authentication if login prompt appears.
    
    Returns:
        bool: True if the upload is successful, False otherwise.
    
    Raises:
        No exceptions are raised; errors are caught and logged, returning False.
    
    Example:
        >>> from playwright.sync_api import sync_playwright
        >>> with sync_playwright() as p:
        ...     browser = p.chromium.launch()
        ...     context = browser.new_context()
        ...     page = context.new_page()
        ...     success = upload_to_sharepoint(
        ...         page=page,
        ...         file_path="C:\\data\\report.csv",
        ...         sharepoint_url="https://usace.dps.mil",
        ...         sharepoint_library_path="/sites/MySite/Shared%20Documents",
        ...         email_address="user@usace.army.mil"
        ...     )
        ...     browser.close()
    
    Notes:
        - The function assumes the user has appropriate permissions to upload to the library.
        - The function attempts to handle login prompts automatically but may require
          manual intervention for multi-factor authentication.
        - Updated for new SharePoint UI (March 2026).
        - Improved timing for batch file execution (April 2026).
    """
    full_sharepoint_url = f"{sharepoint_url}{sharepoint_library_path}"
    print(f"\nNavigating to SharePoint: {full_sharepoint_url}...")
    
    try:
        page.goto(full_sharepoint_url, timeout=60000)
        
        # Attempt to fill in email if login page appears
        try:
            page.wait_for_selector("input[type='email']", timeout=10000)
            page.fill("input[type='email']", email_address)
            print(f"Email address '{email_address}' filled in.")
            page.click("input[type='submit']", timeout=5000)
            print("Clicked 'Next' button.")
            
            # Wait for authentication to complete
            time.sleep(3)
            
        except TimeoutError:
            print("Email field not found. Assuming already logged in.")
        except Exception as e:
            print(f"Could not fill email, proceeding. Error: {e}")
        
        # Wait for page to fully load after authentication
        print("Waiting for SharePoint page to fully load...")
        page.wait_for_load_state("networkidle", timeout=60000)
        
        # Additional wait for dynamic content and UI rendering
        time.sleep(3)
        
        # Wait for the document library to be visible
        try:
            page.wait_for_selector("[data-automationid='FieldRenderer-name']", timeout=30000)
            print("Document library loaded successfully.")
        except:
            print("Document library selector not found, but continuing...")
        
        # Upload process - Try multiple selector strategies for "Create or upload" button
        print("Looking for 'Create or upload' button...")
        
        # Wait for the button to be available
        try:
            page.wait_for_selector("*:has-text('Create or upload')", timeout=30000)
            print("'Create or upload' button found.")
        except TimeoutError:
            print("WARNING: 'Create or upload' button not found within timeout.")
            # Take a screenshot for debugging
            try:
                page.screenshot(path="sharepoint_debug.png")
                print("Debug screenshot saved as 'sharepoint_debug.png'")
            except:
                pass
        
        # Additional buffer before clicking
        time.sleep(2)
        
        print("Clicking the 'Create or upload' button...")
        
        # Strategy 1: Try the span with specific classes
        try:
            page.click("span.text_3f702703.textWithoutSubMenu_3f702703:has-text('Create or upload')", timeout=10000)
            print("Clicked using Strategy 1 (span with classes)")
        except:
            # Strategy 2: Try broader text match
            try:
                page.click("text=Create or upload", timeout=10000)
                print("Clicked using Strategy 2 (text match)")
            except:
                # Strategy 3: Try button containing the text
                try:
                    page.click("button:has-text('Create or upload')", timeout=10000)
                    print("Clicked using Strategy 3 (button with text)")
                except:
                    # Strategy 4: Try any element with the text
                    page.locator("*:has-text('Create or upload')").first.click(timeout=10000)
                    print("Clicked using Strategy 4 (any element)")
        
        # Wait for menu to appear
        time.sleep(2)
        
        print("Clicking 'Files upload' option...")
        
        # Wait for the upload menu to appear
        page.wait_for_selector("*:has-text('Files upload')", timeout=10000)
        
        # Try multiple strategies for "Files upload"
        try:
            page.click("span.ms-ContextualMenu-itemText.label-220:has-text('Files upload')", timeout=10000)
            print("Clicked using specific selector")
        except:
            try:
                page.click("text=Files upload", timeout=10000)
                print("Clicked using text match")
            except:
                page.click("span:has-text('Files upload')", timeout=10000)
                print("Clicked using span text match")
        
        # Wait for file input to be ready
        time.sleep(1)
        
        print("Uploading file...")
        page.set_input_files("input[type='file']", file_path, timeout=60000)
        
        # Wait for upload dialog to process
        time.sleep(2)
        
        # Check if Replace button appears (file already exists)
        try:
            print("Checking for 'Replace' button...")
            page.wait_for_selector("button[name='Replace']", timeout=5000)
            print("Clicking the 'Replace' button...")
            page.click("button[name='Replace']", timeout=10000)
            print("File replaced successfully.")
        except TimeoutError:
            print("No 'Replace' button found - file uploaded as new.")
        
        # Wait for upload to finalize
        print("Waiting for upload to complete...")
        time.sleep(5)
        
        print("File successfully uploaded to SharePoint.")
        return True
        
    except Exception as e:
        print(f"Error uploading to SharePoint: {e}")
        import traceback
        traceback.print_exc()
        
        # Debug: Take screenshot
        try:
            page.screenshot(path="sharepoint_error.png")
            print("Error screenshot saved as 'sharepoint_error.png'")
        except:
            pass
        
        # Debug: Print available elements
        print("\n--- DEBUG: Looking for 'Create or upload' button ---")
        try:
            elements = page.locator("*:has-text('Create')").all()
            print(f"Found {len(elements)} elements containing 'Create'")
            for i, elem in enumerate(elements[:5]):  # Show first 5
                try:
                    html = elem.evaluate('el => el.outerHTML')
                    print(f"  {i+1}. {html[:200]}")
                except:
                    print(f"  {i+1}. [Could not get HTML]")
        except Exception as debug_error:
            print(f"Debug error: {debug_error}")
        
        return False