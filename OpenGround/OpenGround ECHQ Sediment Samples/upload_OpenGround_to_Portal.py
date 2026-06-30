import json
import os
from playwright.sync_api import sync_playwright, TimeoutError, Page, Browser, Playwright


def upload_to_esri_portal(page: Page, geojson_path: str, portal_url: str) -> bool:
    """
    Uploads a GeoJSON file to an ESRI Portal item, overwriting the existing layer.

    Args:
        page: A Playwright Page object.
        geojson_path: The path to the GeoJSON file to upload.
        portal_url: The URL of the ESRI Portal item.

    Returns:
        True on success, False on failure.
    """
    print(f"\nNavigating to ESRI Portal: {portal_url}")

    try:
        page.goto(portal_url, timeout=120000)
        page.wait_for_load_state("networkidle")

        # Close any open calcite modal if present
        if page.locator("calcite-modal[open]").count() > 0:
            page.locator("calcite-modal[open] calcite-button:has-text('Close')").click()

        # Wait for any blocking overlays to disappear
        page.wait_for_selector(".loading, .spinner, .calcite-scrim", state="detached", timeout=60000)

        # --- Update Data ---
        print("Clicking the 'Update Data' button...")
        page.get_by_role('button', name='Update Data' ).click()

        # --- Overwrite entire feature layer ---
        print("Selecting 'Overwrite entire feature layer'...")
        page.locator("calcite-tile-select:has-text('Overwrite entire feature layer')").click(timeout=60000)

        # --- Next ---
        print("Clicking 'Next'...")
        page.get_by_role("button", name="Next").click(timeout=60000)

        # --- Upload from device ---
        print(f"Uploading GEOJSON from device at {geojson_path}...")
        with page.expect_file_chooser() as fc_info:
            page.get_by_role("button", name="Your device").click()

        file_chooser = fc_info.value
        file_chooser.set_files(geojson_path)

        # After set_files
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

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

def main():
    """Main function to orchestrate the entire download and upload process."""
    # --- Configuration ---
    PORTAL_URL = "https://geoportal.mvr.usace.army.mil/b5portal/home/item.html?id=e1e5a69a45a9467f8798c721641c8f66"
    geojson_file = "C:\\Workspace\\AUTOMATED_SCRIPTS\\OpenGround ECHQ Sediment Samples\\OUTPUT GEOJSON\\openGround_ECHQ_sediment_data.geojson"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(accept_downloads=True, ignore_https_errors=True)
        page_portal = context.new_page()

        try:
                        
            # Step 1: Verify GeoJSON file exists
            if not geojson_file:
                print("\nFailed to create GeoJSON file. Aborting.")
                return

            # Step 2: Upload the GeoJSON to ESRI Portal
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