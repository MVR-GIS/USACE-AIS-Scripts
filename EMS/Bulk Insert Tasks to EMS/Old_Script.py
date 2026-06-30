# Author: Ryan Benac CEMVR EC-D
# Last Update: 1/20/2026
# This script uses python playwright to upload data to EMS REST API from a spreadsheet
##################################################################################################################################
print(f"Importing modules...")
import pandas as pd # used to manage datatable
from playwright.sync_api import sync_playwright, TimeoutError # used to interact with EMS
        import requests, json
        from urllib.parse import quote

        # URL-encode task_name values up-front and store in a column
        if 'task_name' in df.columns:
            df['task_name_encoded'] = df['task_name'].apply(lambda x: quote(str(x)) if pd.notna(x) else '')
        else:
            df['task_name_encoded'] = ''

# variables
baseEMSURL = "https://ems-test.cwbi.us"
# The 'r' before the string treats backslashes as literal characters
file_path = r"C:\Workspace\LOCAL SANDBOX\EMS Rest API\Bulk Insert Tasks to EMS\TEST_DATASETS.xlsx" 
sheet_name = "compiled"

sessionID = "5672427"

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


unique_product_ids = df['product_id'].unique()
print(f"\nFound {len(unique_product_ids)} unique products to process.")
for product_id in unique_product_ids:
    sub_dataset = df[df['product_id'] == product_id]
    print(f"\nProcessing Product ID: {product_id} ({len(sub_dataset)} rows)")
    

    # Call the single SCOPE endpoint
    scope_url = f"{baseEMSURL}/api/SCOPE/SSB_SCOPE/{sessionID}/{product_id}"
    scope_data = None
    try:
        print(f"   - Requesting scope: {scope_url}")
        resp = requests.get(scope_url, timeout=10)
        if resp.status_code == 200:
            scope_data = resp.json()
            print(f"   - Success from {scope_url} (items={len(scope_data)})")
        else:
            print(f"   - Scope endpoint returned status {resp.status_code}: {scope_url}")
    except Exception as e:
        print(f"   - Error requesting {scope_url}: {e}")

    if scope_data is None:
        print(f"   - Failed to retrieve scope for product {product_id}; skipping this product.")
        continue

    # Save scope JSON to a file for inspection
    out_path = f"scope_{product_id}.json"
    with open(out_path, 'w', encoding='utf-8') as fh:
        json.dump(scope_data, fh, indent=2)
    print(f"   - Saved scope JSON to {out_path}")

    # Determine master task name from the dataframe (common candidate columns)
    possible_cols = ['master_task', 'mastertask', 'lineItem', 'line_item', 'master', 'task_name', 'task']
    master_name = None
    for col in possible_cols:
        if col in sub_dataset.columns:
            # take first row's value as master task name
            master_name = str(sub_dataset[col].iloc[0])
            break

    # Find entries where wbs == '1' — if none, skip this product entirely
    wbs1_entries = [s for s in scope_data if str(s.get('wbs')) == '1']
    if not wbs1_entries:
        print("   - No scope entries with wbs == '1' found. Skipping this product.")
        continue

    # Determine master task from the wbs==1 entries
    found = None
    if master_name:
        for e in wbs1_entries:
            line = e.get('lineItem') or e.get('line_item') or ''
            if line and master_name.strip().lower() == str(line).strip().lower():
                found = e
                break
    if found is None:
        found = wbs1_entries[0]
    master_task_id = found.get('id')
    print(f"   - Master task: id={master_task_id}, wbs={found.get('wbs')}, lineItem={found.get('lineItem')}")

    # Loop through rows in sub_dataset and process each row (placeholder)
    for index, row in sub_dataset.iterrows():
        try:
            # Use only the 'task_name' column from the spreadsheet (encoded version for URL)
            task_name = str(row['task_name']) if 'task_name' in row.index and pd.notna(row['task_name']) else None
            task_name_encoded = row.get('task_name_encoded', '') if 'task_name_encoded' in row.index else ''

            # wbs_sub_id column provides the trailing number; fallback to 1
            wbs_sub_id = None
            if 'wbs_sub_id' in row.index and pd.notna(row['wbs_sub_id']):
                wbs_sub_id = int(row['wbs_sub_id'])
            elif 'wbs_sub' in row.index and pd.notna(row['wbs_sub']):
                wbs_sub_id = int(row['wbs_sub'])
            else:
                wbs_sub_id = 1

            print(f"     - Row {index}: task='{task_name}', master_task_id={master_task_id}, sessionID={sessionID}, wbs_sub_id={wbs_sub_id}")

            # Build insert URL and call it
            if master_task_id is None:
                print("     - No master_task_id available; skipping insert for this row.")
            elif not task_name_encoded:
                print("     - task_name is empty; skipping insert for this row.")
            else:
                insert_url = f"{baseEMSURL}/api/ssb_wbs/insert/{sessionID}/{product_id}/{master_task_id}/{task_name_encoded}/{wbs_sub_id}"
                try:
                    resp = requests.get(insert_url, timeout=10)
                    print(f"     - Insert request to: {insert_url} -> status {resp.status_code}")
                    # Optionally print response body for debugging
                    print(resp.text)
                except Exception as e:
                    print(f"     - Insert request failed: {e}")
            # Build URLs with f-strings (avoid concat with &)
            # Example insert URL (uncomment and adapt when ready):
            # insert_url = f"{baseEMSURL}/api/ssb_wbs/insert/{sessionID}/{product_id}/{master_task_id}/{task_name}/1"
        except Exception as e:
            print(f"     - Error processing row {index}: {e}")




import sys, subprocess, traceback
print("Notebook Python executable:", sys.executable)
print("Python version:", sys.version)
try:
    import openpyxl
    print("openpyxl import OK, version:", openpyxl.__version__)
except Exception as e:
    print("openpyxl import failed:", e)
    print("Attempting to install openpyxl into the current Python environment...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "openpyxl"]) 
    except Exception as e2:
        print("Automatic install failed:")
        traceback.print_exc()
    try:
        import openpyxl
        print("openpyxl import after install, version:", openpyxl.__version__)
    except Exception as e3:
        print("Import still failing after install:")
        traceback.print_exc()

import pandas as pd
print("pandas version:", pd.__version__)
try:
    df = pd.read_excel(r"C:\Workspace\LOCAL SANDBOX\EMS Rest API\Bulk Insert Tasks to EMS\TEST_DATASETS.xlsx", sheet_name="compiled", engine="openpyxl")
    print(df.head())
except Exception as e:
    print("pd.read_excel error:")
    traceback.print_exc()