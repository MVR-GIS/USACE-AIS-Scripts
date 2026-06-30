"""
PortalUpload.py

This module provides functionality for uploading GeoJSON files to ESRI ArcGIS Portal/Online
items. It uses Playwright for browser automation to overwrite existing feature layers with
new data.

Author: Ryan Benac
Created: 3/10/2026
"""

from playwright.sync_api import Page


def upload_to_esri_portal(
    page: Page,
    geojson_path: str,
    portal_url: str
) -> bool:
    """
    Uploads a GeoJSON file to an ESRI Portal item, overwriting the existing feature layer.
    
    This function navigates to an ESRI ArcGIS Portal (or ArcGIS Online) item page and
    performs an overwrite operation to replace the existing feature layer data with
    new data from a GeoJSON file.
    
    Args:
        page (Page): A Playwright Page object for browser automation.
        geojson_path (str): The local file system path to the GeoJSON file to upload.
        portal_url (str): The full URL of the ESRI Portal item page, including the item ID
                         (e.g., "https://geoportal.example.com/portal/home/item.html?id=abc123").
    
    Returns:
        bool: True if the upload and overwrite operation is successful, False otherwise.
    
    Raises:
        No exceptions are raised; errors are caught and logged, returning False.
    
    Example:
        >>> from playwright.sync_api import sync_playwright
        >>> with sync_playwright() as p:
        ...     browser = p.chromium.launch()
        ...     context = browser.new_context()
        ...     page = context.new_page()
        ...     success = upload_to_esri_portal(
        ...         page=page,
        ...         geojson_path="C:\\data\\features.geojson",
        ...         portal_url="https://geoportal.mvr.usace.army.mil/portal/home/item.html?id=990906b45da840b29e9e125bb6452d18"
        ...     )
        ...     browser.close()
    
    Notes:
        - The function assumes the user is already authenticated to the Portal.
        - The operation performs a complete overwrite of the feature layer, not an append.
        - The function includes extensive timeouts (up to 100 minutes) to handle large
          file uploads and processing times.
        - Any open calcite modals are automatically closed before beginning the upload.
        - The function waits for the page to fully reload after the overwrite completes.
    """
    print(f"\nNavigating to ESRI Portal: {portal_url}")
    
    try:
        page.goto(portal_url, timeout=120000)
        page.wait_for_load_state("networkidle")
        
        # Close any open calcite modal if present
        if page.locator("calcite-modal[open]").count() > 0:
            page.locator("calcite-modal[open] calcite-button:has-text('Close')").click()
        
        # Wait for any blocking overlays to disappear
        page.wait_for_selector(
            ".loading, .spinner, .calcite-scrim",
            state="detached",
            timeout=60000
        )

        # --- Update Data ---
        print("Clicking the 'Update Data' button...")
        page.get_by_role('button', name='Update Data').click()

        # --- Overwrite entire feature layer ---
        print("Selecting 'Overwrite entire feature layer'...")
        page.locator("calcite-tile-select:has-text('Overwrite entire feature layer')").click(
            timeout=60000
        )

        # --- Next ---
        print("Clicking 'Next'...")
        page.get_by_role("button", name="Next").click(timeout=60000)

        # --- Upload from device ---
        print("Uploading GeoJSON from device...")
        with page.expect_file_chooser() as fc_info:
            page.get_by_role("button", name="Your device").click()
        file_chooser = fc_info.value
        file_chooser.set_files(geojson_path)

        # Wait for overwrite and page refresh to complete
        print("Waiting for overwrite and page refresh to complete...")
        
        # Wait for the modal to disappear if it exists
        overwrite_modal = page.locator("calcite-modal[open]")
        if overwrite_modal.count() > 0:
            overwrite_modal.wait_for(state="detached", timeout=6000000)
        
        # Wait for the page to reload and Update Data button to become available
        page.get_by_role("button", name="Update Data").wait_for(timeout=6000000)
        
        print("Overwrite complete, page refreshed and ready.")
        return True
        
    except Exception as e:
        print(f"Error uploading to ESRI Portal: {e}")
        return False