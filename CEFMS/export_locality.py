"""
CEFMS Locality Data Export Script - DOM Scraping Approach
==========================================================
Instead of replicating API calls, we'll just scrape the data
directly from the page as we paginate through it.
"""

import asyncio
import csv
import json
import re
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright, Page


# Configuration
BASE_URL = "https://cefmsii-chciprd.usace.army.mil/ords/portal/f?p=2000:1:31994143491620::::::"
OUTPUT_DIR = Path(r"C:\Workspace\LOCAL SANDBOX\CEFMS Locality Export\DATA")


def setup_output_directory():
    """Create the output directory if it doesn't exist."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"✓ Output directory ready: {OUTPUT_DIR}")


def generate_filename():
    """Generate a timestamped filename for the CSV export."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_CEFMS_LOCALITY_EXPORT.csv"
    return OUTPUT_DIR / filename


async def wait_for_cac_authentication(page: Page, timeout: int = 300000):
    """Wait for the user to complete CAC authentication manually."""
    print("\n" + "="*60)
    print("⏳ WAITING FOR CAC AUTHENTICATION")
    print("="*60)
    print("Please select your CAC certificate in the browser prompt.")
    print("The script will continue automatically once authenticated.")
    print("="*60 + "\n")
    
    try:
        await page.wait_for_selector('button:has-text("My Modules")', timeout=timeout)
        print("✓ CAC authentication successful!\n")
    except Exception as e:
        print(f"⚠ Timeout waiting for authentication: {e}")
        raise


async def find_page_with_dialog(context):
    """Find which page/frame has the locality dialog."""
    pages = context.pages
    
    print(f"\n🔍 Searching through {len(pages)} page(s) for the dialog...\n")
    
    for page_idx, page in enumerate(pages):
        try:
            title = await page.title()
            url = page.url
            print(f"  Page {page_idx + 1}: {title[:50]}")
            print(f"    URL: {url[:80]}...")
            
            # Check main page
            grid_count = await page.locator('#country_state_ig_grid_vc').count()
            dialog_count = await page.locator('div.t-Dialog-body').count()
            table_count = await page.locator('table.a-GV-table').count()
            
            print(f"    Main page - Grid: {grid_count}, Dialog: {dialog_count}, Table: {table_count}")
            
            if grid_count > 0:
                print(f"  ✓✓✓ Found grid on Page {page_idx + 1} (main content)")
                return page, None
            
            # Check iframes
            frames = page.frames
            print(f"    Checking {len(frames)} frame(s)...")
            
            for frame_idx, frame in enumerate(frames):
                try:
                    frame_url = frame.url
                    if frame_url != url:  # Skip main frame
                        print(f"      Frame {frame_idx}: {frame_url[:60]}...")
                        
                        grid_count = await frame.locator('#country_state_ig_grid_vc').count()
                        dialog_count = await frame.locator('div.t-Dialog-body').count()
                        table_count = await frame.locator('table.a-GV-table').count()
                        
                        print(f"        Grid: {grid_count}, Dialog: {dialog_count}, Table: {table_count}")
                        
                        if grid_count > 0:
                            print(f"  ✓✓✓ Found grid in Frame {frame_idx} of Page {page_idx + 1}")
                            return page, frame
                except Exception as e:
                    print(f"        Error checking frame: {e}")
            
            print()
            
        except Exception as e:
            print(f"    Error checking page: {e}\n")
    
    print("  ❌ Could not find the grid in any page or frame\n")
    return None, None


async def scrape_current_page_data(page_or_frame):
    """Scrape locality data from the current page by extracting the JavaScript data object."""
    records = []
    
    try:
        # Extract the JavaScript variable containing the data
        data_json = await page_or_frame.evaluate("""
            () => {
                // Try to find the data variable
                if (typeof gIg1058257856265600400data !== 'undefined') {
                    return gIg1058257856265600400data;
                }
                
                // Try to find it in window
                for (let key in window) {
                    if (key.includes('gIg') && key.includes('data')) {
                        return window[key];
                    }
                }
                
                return null;
            }
        """)
        
        if data_json and 'values' in data_json:
            values = data_json['values']
            
            # Each row is an array: [Locality, Code, Country/State, metadata_object]
            for row in values:
                if len(row) >= 3:
                    locality = row[0].strip()
                    code = row[1].strip()
                    country_state = row[2].strip()
                    records.append([code, country_state, locality])
            
            return records
        else:
            print("    ⚠ Could not find data object in JavaScript")
            
    except Exception as e:
        print(f"    ⚠ Error extracting data from JavaScript: {e}")
    
    # Fallback: Try scraping from visible table
    print("    Trying fallback: scraping visible table...")
    try:
        rows = page_or_frame.locator('table.a-GV-table tbody tr[role="row"]')
        row_count = await rows.count()
        
        print(f"    Found {row_count} table rows")
        
        if row_count > 0:
            for i in range(row_count):
                row = rows.nth(i)
                cells = row.locator('td[role="gridcell"]')
                cell_count = await cells.count()
                
                if cell_count >= 3:
                    code = await cells.nth(0).inner_text()
                    country_state = await cells.nth(1).inner_text()
                    locality = await cells.nth(2).inner_text()
                    
                    records.append([code.strip(), country_state.strip(), locality.strip()])
    except Exception as e:
        print(f"    ⚠ Fallback scraping failed: {e}")
    
    return records


async def navigate_to_locality_search_manual(page: Page, context):
    """Navigate to locality search with manual intervention."""
    print("🔄 Please complete the following steps manually:")
    print("="*70)
    print("1. Click 'My Modules' → 'Travel'")
    print("2. Click 'Orders' card")
    print("3. Click the 'In Process' travel order")
    print("4. Click 'Next' button")
    print("5. Click the search button (magnifying glass) next to")
    print("   'Depart Country/State' or 'Arrive Country/State'")
    print("6. Wait for the locality search dialog to appear")
    print("\nPress Enter when you're on the locality search page...")
    print("="*70 + "\n")
    
    await asyncio.to_thread(input, "Press Enter when ready: ")
    
    # Find the page/frame with the dialog
    return await find_page_with_dialog(context)


async def export_all_locality_data_by_scraping(page_or_frame, output_file: Path):
    """Export data by scraping each page."""
    print(f"\n📊 Starting data export by scraping pages...")
    print(f"Output file: {output_file.name}\n")
    
    if page_or_frame is None:
        print("❌ No valid page or frame found. Cannot continue.\n")
        return 0
    
    all_records = []
    page_number = 1
    seen_records = set()  # To avoid duplicates
    consecutive_failures = 0
    
    while True:
        print(f"  Scraping page {page_number}...")
        
        # Wait a moment for any loading to complete
        await asyncio.sleep(2)
        
        # Scrape current page
        page_data = await scrape_current_page_data(page_or_frame)
        
        if page_data:
            # Filter out duplicates
            new_records = []
            for record in page_data:
                record_key = tuple(record)
                if record_key not in seen_records:
                    seen_records.add(record_key)
                    new_records.append(record)
            
            all_records.extend(new_records)
            print(f"  ✓ Got {len(new_records)} new records (Total: {len(all_records)})\n")
            consecutive_failures = 0
        else:
            consecutive_failures += 1
            print(f"  ✗ No data found on this page (failure {consecutive_failures})")
            if consecutive_failures >= 3:
                print("\n❌ Failed to extract data 3 times in a row. Stopping.")
                break
        
        # Try to click "Next" button
        try:
            next_button = page_or_frame.locator('button.a-GV-pageButton.js-pg-next')
            
            # Check if button exists
            button_count = await next_button.count()
            if button_count == 0:
                print("  ⚠ Next button not found")
                break
            
            # Check if button is disabled
            is_disabled = await next_button.get_attribute('disabled')
            
            if is_disabled is not None:
                print("  ✓ Reached last page (Next button disabled)")
                break
            
            # Click next
            print(f"  → Clicking Next button...")
            await next_button.click()
            
            # Wait for new data to load
            await asyncio.sleep(2)
            
            # Extra wait every 50 pages for batch loading
            if page_number % 50 == 0:
                print("    ⏳ Waiting for data batch to load...")
                await asyncio.sleep(2)
            
            page_number += 1
            
        except Exception as e:
            print(f"  ⚠ Could not find/click next button: {e}")
            break
    
    # Write to CSV
    print(f"\n💾 Writing {len(all_records)} records to CSV...")
    
    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Code', 'Country/State', 'Locality'])
        writer.writerows(all_records)
    
    print(f"✓ Export complete! {len(all_records)} records saved.")
    print(f"📁 File location: {output_file}\n")
    
    return len(all_records)


async def main():
    """Main execution function."""
    print("\n" + "="*70)
    print("CEFMS LOCALITY DATA EXPORT TOOL - DOM SCRAPING")
    print("="*70 + "\n")
    
    setup_output_directory()
    output_file = generate_filename()
    
    async with async_playwright() as p:
        print("🌐 Launching browser...")
        browser = await p.chromium.launch(
            headless=False,
            slow_mo=500
        )
        
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            ignore_https_errors=True
        )
        
        page = await context.new_page()
        
        try:
            print(f"🔗 Navigating to: {BASE_URL}")
            await page.goto(BASE_URL, wait_until='domcontentloaded', timeout=60000)
            
            await wait_for_cac_authentication(page)
            
            # Manual navigation
            active_page_or_frame, frame = await navigate_to_locality_search_manual(page, context)
            
            # Use frame if found, otherwise use page
            target = frame if frame else active_page_or_frame
            
            # Scrape all pages
            total_records = await export_all_locality_data_by_scraping(target, output_file)
            
            print("="*70)
            print("✅ EXPORT COMPLETED SUCCESSFULLY!")
            print("="*70)
            print(f"Total records exported: {total_records}")
            print(f"File: {output_file}\n")
            
            print("\nBrowser will remain open. Press Ctrl+C to exit.")
            while True:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            print("\n\n👋 User requested exit.")
            
        except Exception as e:
            print(f"\n❌ An error occurred: {e}")
            import traceback
            traceback.print_exc()
            print("\nBrowser will remain open. Press Ctrl+C to exit.")
            while True:
                try:
                    await asyncio.sleep(1)
                except KeyboardInterrupt:
                    break
        
        finally:
            await browser.close()
            print("Browser closed. Goodbye!\n")


if __name__ == "__main__":
    asyncio.run(main())