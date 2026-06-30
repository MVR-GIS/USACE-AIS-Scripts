# Author: Ryan Benac CEMVR EC-D
# Last Update: 1/20/2026
# This script uses python playwright to upload data to EMS REST API from a spreadsheet
##################################################################################################################################
print(f"Importing modules...")
import pandas as pd # used to manage datatable
from playwright.sync_api import sync_playwright, TimeoutError # used to interact with EMS

# variables
baseEMSURL = "https://ems-test.cwbi.us"
# The 'r' before the string treats backslashes as literal characters
file_path = r"C:\Workspace\LOCAL SANDBOX\EMS Rest API\Bulk Insert Tasks to EMS\TEST_DATASETS.xlsx" 
sheet_name = "compiled"


##################################################################################################################################
# STEP 1: import spreadsheet as datatable
print(f"Importing spreadsheet at {file_path}...")
try:
    # Read the specified sheet from the Excel file into a pandas DataFrame
    # The 'engine='openpyxl'' is required for .xlsx files
    df = pd.read_excel(file_path, sheet_name=sheet_name, engine='openpyxl')

    # Print a success message
    print(f"Successfully imported data from sheet '{sheet_name}'.")

except FileNotFoundError:
    print(f"Error: The file was not found at the path: {file_path}")
except Exception as e:
    # Catch other potential errors, such as the sheet not existing
    print(f"An error occurred: {e}")

# format dates as yyyy-mm-dd
# Convert date columns to datetime objects, coercing errors to NaT (Not a Time)
df['start_date'] = pd.to_datetime(df['start_date'], errors='coerce')
df['end_date'] = pd.to_datetime(df['end_date'], errors='coerce')

# Format the datetime objects into the desired 'yyyy-mm-dd' string format
df['start_date'] = df['start_date'].dt.strftime('%Y-%m-%d')
df['end_date'] = df['end_date'].dt.strftime('%Y-%m-%d')

# Display the first 5 rows of the imported data to verify
print("First 5 rows of the DataTable:")
print(df.head())


##################################################################################################################################
# STEP 2: Authenticate
# Define URLs and settings
ems_product_url = baseEMSURL + "/ssb"
navigation_timeout = 600000  # 10 minutes

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context(ignore_https_errors=True)
    page = context.new_page()

    try:
        # Navigate to the EMS page
        print(f"\nNavigating to: {ems_product_url}")
        print("Please complete any required authentication in the browser window...")
        page.goto(ems_product_url, timeout=navigation_timeout)
        print("Successfully navigated to the EMS scheduling page.")

        # Handle the initial "I Understand and Acknowledge" popup
        try:
            
            # 1. Wait for the modal container to become visible.
            modal_selector = "div.modal-content"
            print("Waiting for the modal popup to become visible...")
            page.wait_for_selector(modal_selector, state='visible', timeout=30000)
            print("Modal is visible.")

            # 2. THE LITERAL DRAG: Simulate your "click and drag" action.
            print("Locating the modal content area for dragging...")
            modal_element = page.locator(modal_selector)

            # Get the size and position of the modal to calculate coordinates.
            box = modal_element.bounding_box()
            if not box:
                raise Exception("Could not find the modal on the page to begin the drag.")
            
            # Define the start and end points for the drag action.
            # We'll start in the middle of the modal and drag straight up.
            start_x = box['x'] + box['width'] / 2
            start_y = box['y'] + box['height'] / 2
            end_y = start_y - 300  # Drag upwards by 300 pixels

            print(f"Simulating mouse drag from ({start_x:.0f}, {start_y:.0f}) to ({start_x:.0f}, {end_y:.0f})...")
            
            # Execute the drag: move to start, press button, move to end, release.
            page.mouse.move(start_x, start_y)
            page.mouse.down()
            page.mouse.move(start_x, end_y, steps=5) # Using 'steps' creates a smoother motion
            page.mouse.up()
            
            print("Drag action completed.")
            
            # 3. Now that the content is dragged up, click the button.
            print("Locating and clicking the 'I Understand and Acknowledge' button...")
            ack_button = page.get_by_role("button", name="I Understand and Acknowledge")
            
            # The button should be visible now.
            ack_button.click(timeout=10000)

            # 4. Verify the modal disappears to confirm success.
            print("Verifying that the modal has closed...")
            page.wait_for_selector(modal_selector, state='hidden', timeout=10000)
            
            print("\n--- SUCCESS: Dragged modal, clicked, and verified button. ---")



        except TimeoutError:
            print("Acknowledgement popup not found or was already dismissed. Continuing...")

        page.goto(ems_product_url, timeout=navigation_timeout)

        # --- STEP 3: LOOP THROUGH PRODUCTS ---
        unique_product_ids = df['product_id'].unique()
        print(f"\nFound {len(unique_product_ids)} unique products to process.")

        for product_id in unique_product_ids:
            sub_dataset = df[df['product_id'] == product_id]
            print(f"\nProcessing Product ID: {product_id} ({len(sub_dataset)} rows)")
            try:
                # 1. Change search type to "Product Id"
                print("   - Setting search type to 'Product Id'...")
                # First try the original simple selector behavior (restores previous logic)
                try:
                    page.locator("#react-select-6-input").locator("..").locator("..").click()
                    page.get_by_text("Product Id", exact=True).click()
                    page.wait_for_timeout(200)
                except Exception:
                    # If that fails, use the more robust approach
                    try:
                        # Try opening the dropdown using the outer control if available, else the input
                        control = page.locator("div[id^='react-select-6']").first
                        try:
                            if control.count() and control.is_visible():
                                control.click()
                            else:
                                page.locator("#react-select-6-input").click()
                        except Exception:
                            page.locator("#react-select-6-input").click()

                        # Wait for options to appear
                        option_locator = page.locator("div[role='option']:has-text(\"Product Id\")")
                        page.wait_for_selector("div[role='option']", timeout=5000)

                        # Scroll the option into view then attempt to click it. Use JS click as a fallback.
                        option = option_locator.first
                        option.scroll_into_view_if_needed()
                        try:
                            option.click(timeout=3000)
                        except Exception:
                            print("   - Regular click failed; attempting JS click as fallback.")
                            option.evaluate("el => el.click()")

                        # Small pause to allow the selection to register
                        page.wait_for_timeout(200)

                    except TimeoutError:
                        # Final fallback: type the label and press Enter
                        print("   - Dropdown not found; falling back to typing and pressing Enter.")
                        page.locator("#react-select-6-input").fill("Product Id")
                        page.locator("#react-select-6-input").press("Enter")

                # 2. Search for the product (target the correct react-select instance)
                print(f"   - Searching for product '{product_id}' in the 'Search existing products.' control...")
                try:
                    container = page.locator("div[title='Search existing products.']").first
                    # The actual text input for react-select lives inside this container
                    search_input = container.locator("input[type='text']").first
                    search_input.click()
                    search_input.fill(str(product_id))
                    # Small pause to allow suggestions to render
                    page.wait_for_timeout(300)

                    # Wait for the suggestion specific to this control, then click it.
                    suggestion_selector = "div[title='Search existing products.'] div[role='option']"
                    page.wait_for_selector(suggestion_selector, timeout=5000)
                    suggestion = page.locator(suggestion_selector).first
                    suggestion.scroll_into_view_if_needed()
                    try:
                        suggestion.click(timeout=3000)
                    except Exception:
                        # JS click fallback
                        suggestion.evaluate("el => el.click()")

                    # give the UI a moment to register the selection
                    page.wait_for_timeout(200)

                except TimeoutError:
                    print(f"   - No suggestion appeared for product {product_id}; skipping.")
                    continue
                except Exception as e:
                    print(f"   - Product search failed for product {product_id}: {e}")
                    raise
                
                # 4. Click the "Yes" confirmation button to load the product
                #    !!! IMPORTANT: You will need to inspect the 'Yes' button and get a reliable selector.
                #    The selector below is a guess and may need to be corrected.
                print("   - Clicking 'Yes' to confirm product selection...")
                page.get_by_role("button", name="Yes").click() 
                print(f"   - Product {product_id} loaded successfully.")

                # 6. Get session id by clicking the EMS DB status button which fires
                #    a request to /api/ems/rds_test_session/<session_id>
                session_id = None
                try:
                    print("   - Retrieving session id from EMS DB status button...")
                    db_button = page.locator("button[title^='EMS Database connection status']").first
                    # simplify visibility check; is_visible() returns False if not found
                    if db_button.is_visible():
                        with page.expect_response(lambda r: 'rds_test_session' in r.url, timeout=5000) as resp_info:
                            db_button.click()
                        resp = resp_info.value
                        session_url = resp.url
                        session_id = session_url.rstrip('/').split('/')[-1]
                        print(f"   - Retrieved session id: {session_id} (status {resp.status})")
                    else:
                        # Try alternative selector and a generic wait_for_response fallback
                        print("   - DB status button not visible with primary selector; trying alternate selector.")
                        with page.expect_response(lambda r: 'rds_test_session' in r.url, timeout=5000) as resp_info:
                            page.click("button.btn.btn-sm.btn-success")
                        resp = resp_info.value
                        session_url = resp.url
                        session_id = session_url.rstrip('/').split('/')[-1]
                        print(f"   - Retrieved session id (alternate): {session_id} (status {resp.status})")
                except TimeoutError:
                    print("   - Timed out waiting for rds_test_session response; session id not retrieved.")
                except Exception as e:
                    print(f"   - Failed to retrieve session id: {e}")

                # 7. Call getScope API for this product and save the results
                scope_data = None
                try:
                    print(f"   - Calling getScope API for product {product_id}...")
                    # Use the Playwright APIRequestContext attached to the page so cookies/auth are preserved
                    scope_url = f"{baseEMSURL}/api/ssb_wbs/scope/{product_id}"
                    resp = page.request.get(scope_url)
                    if resp.ok:
                        scope_data = resp.json()
                        print(f"   - getScope returned {len(scope_data)} items for product {product_id}.")
                    else:
                        # Try alternate endpoint name
                        alt_url = f"{baseEMSURL}/api/ssb_wbs/getScope/{product_id}"
                        print(f"   - Primary scope URL failed ({resp.status}). Trying alternate: {alt_url}")
                        resp2 = page.request.get(alt_url)
                        if resp2.ok:
                            scope_data = resp2.json()
                            print(f"   - getScope (alternate) returned {len(scope_data)} items.")
                        else:
                            print(f"   - Both scope endpoints failed: {resp.status}, {resp2.status}")

                    # Save scope JSON to file for inspection
                    if scope_data is not None:
                        out_path = f"scope_{product_id}.json"
                        import json
                        with open(out_path, 'w', encoding='utf-8') as f:
                            json.dump(scope_data, f, indent=2)
                        print(f"   - Saved scope JSON to {out_path}")

                except Exception as e:
                    print(f"   - Error calling getScope for product {product_id}: {e}")

                # 8. Check for master task in the scope (wbs == '1') using master task name from dataframe
                master_task_id = None
                try:
                    # Attempt to find a master task name column in the dataframe
                    possible_cols = ['master_task', 'mastertask', 'lineItem', 'line_item', 'master']
                    master_name = None
                    for col in possible_cols:
                        if col in sub_dataset.columns:
                            master_name = str(sub_dataset[col].iloc[0])
                            break

                    # If not found, try to use a 'task' column or fallback to first row 'lineItem'
                    if not master_name and 'task' in sub_dataset.columns:
                        master_name = str(sub_dataset['task'].iloc[0])

                    if not master_name:
                        print("   - Could not determine master task name from dataframe columns. Skipping master lookup.")
                    elif scope_data is None:
                        print("   - No scope data available to search for master task.")
                    else:
                        # Find any scope entry where wbs == '1' and lineItem matches master_name
                        matches = [s for s in scope_data if str(s.get('wbs')) == '1']
                        if not matches:
                            print("   - No entries in scope with wbs == '1'.")
                        else:
                            # If master_name present, try to match by lineItem
                            found = None
                            for m in matches:
                                line = m.get('lineItem') or m.get('line_item') or ''
                                if master_name and line and master_name.strip().lower() == str(line).strip().lower():
                                    found = m
                                    break
                            if found is None:
                                # If no exact name match, pick the first wbs==1 entry
                                found = matches[0]

                            master_task_id = found.get('id')
                            print(f"   - Master task determined: id={master_task_id}, wbs={found.get('wbs')}, lineItem={found.get('lineItem')}")

                except Exception as e:
                    print(f"   - Error while locating master task in scope data: {e}")

                # 9. Loop through the rows for this product and perform per-row logic
                for index, row in sub_dataset.iterrows():
                    try:
                        # Example per-row access
                        task_name = row.get('task_name') if 'task_name' in row else row.get('lineItem') if 'lineItem' in row else None
                        # Here you can create tasks, update dates, etc., using `session_id` and `master_task_id` as needed
                        print(f"     - Row {index}: will process task '{task_name}' (master_task_id={master_task_id}, session_id={session_id})")
                        # NOTE: Use f-strings to build any URLs to avoid concat issues
                        # Example: insert_url = f"{baseEMSURL}/api/ssb_wbs/insert/{session_id}/{product_id}/{master_task_id}/{task_name}/1"
                    except Exception as e:
                        print(f"     - Error processing row {index}: {e}")

                # ----
                # ADD YOUR LOGIC HERE: Now you can loop through `sub_dataset` and make API calls
                # for index, row in sub_dataset.iterrows():
                #   your_api_call_function(product_id, row)
                # ----
                
                # 5. Clear the search to prepare for the next loop
                print("   - Clearing product search for next loop...")
                clear_button_selector = "div.css-ig1pve-indicatorContainer"
                # Check if the clear button is visible before clicking
                if page.locator(clear_button_selector).is_visible():
                    page.locator(clear_button_selector).click()
                else:
                    print("   - Clear button not found, reloading page to reset state.")
                    page.reload() # Reload the page as a fallback to reset

            except TimeoutError as e:
                print(f"   - A step timed out for product {product_id}. The page might be slow or an element is missing.")
                print("   - Reloading page and skipping to next product.")
                page.reload()
                continue
            except Exception as e:
                print(f"   - An unexpected error occurred for product {product_id}: {e}")
                print("   - Reloading page and skipping to next product.")
                page.reload()
                continue
        
        print("\nAll products processed.")

    except TimeoutError:
        print(f"Navigation timed out after {navigation_timeout/1000} seconds. Please authenticate faster or check the URL.")
    except Exception as e:
        print(f"A critical error occurred: {e}")
    finally:
        print("Closing browser.")
        browser.close()


# verify that the master task exists, if it does, get the unique task id. add a column to the datatable for mastertask id (should be same for all rows)


# Add a new task for each row for that product 
# https://ems-test.cwbi.us/api/ssb_wbs/insert/5672380/422479/6871039/Test%20sub/1


# get task id and save to variable and column in datatable


# update the start date for the newly created task
# https://ems-test.cwbi.us/api/ssb_task_overrides/updateSTARTDATE/5672380/422479/6871040/2026-01-22


# update the end date for the newly created task
# https://ems-test.cwbi.us/api/ssb_task_overrides/updateENDDATE/5672380/422479/6871040/2026-01-24
