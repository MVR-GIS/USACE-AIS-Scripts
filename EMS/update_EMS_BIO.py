"""
USACE EMS API Query Script with Playwright Browser Authentication

This script uses Playwright to authenticate via browser and then query the 
U.S. Army Corps of Engineers (USACE) Enterprise Management System (EMS) API.

Workflow:
1. Navigate to SharePoint and download CERCAP_EXPORT.csv
2. Authenticate to EMS and get session ID
3. Query sections data (filtered)
4. Navigate to resources configuration page

Author: [Your Name]
Date: 2026-04-10

Requirements:
    pip install playwright pandas requests
    playwright install chromium
"""

import asyncio
import json
import pandas as pd
from typing import Dict, List, Optional, Tuple
import logging
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Download
from datetime import datetime
import os
from pathlib import Path
import json

# Load configuration
config_path = "C:\\Workspace\\GIT\\USACE-AIS-Scripts\\config.json"

with open(config_path, 'r') as f:
    config = json.load(f)

# ============================================================================
# CONFIGURATION SECTION
# ============================================================================

# User Configuration
EMPLOYEE_ID = config["employee_id"]  # Your employee ID
OFFICE_CODE = "CEMVR"     # Your office code
SECTION_FILTER = "CEMVR"  # Filter sections containing this string
EMAIL_ADDRESS = config['sharepoint_username']  # Your email for SharePoint login

# SharePoint Configuration
SHAREPOINT_URL = "https://usace.dps.mil/sites/TDL-CEMVR-EMSUsers/Shared%20Documents/Forms/AllItems.aspx?id=%2Fsites%2FTDL%2DCEMVR%2DEMSUsers%2FShared%20Documents%2FDATASETS%2FCERCAP&viewid=710f3e85%2D8e87%2D4dc8%2D8355%2D3bb24dc9a99b"
CERCAP_FILENAME = "CERCAP_EXPORT.csv"
DOWNLOAD_PATH = r"C:\Workspace\LOCAL SANDBOX\EMS Rest API\Update Resource Bios"

# API Configuration
API_BASE_URL = "https://ems.sec.usace.army.mil/api/ems"
SECTIONS_ENDPOINT = f"{API_BASE_URL}/get_sections/"
SESSION_ID_ENDPOINT = f"{API_BASE_URL}/getSessionID/-1/{EMPLOYEE_ID}/{OFFICE_CODE}"
EMS_LOGIN_URL = "https://ems.sec.usace.army.mil"
EMS_RESOURCES_URL = "https://ems.sec.usace.army.mil/ems/configuration/resources#profile"

# Browser Configuration
BROWSER_TYPE = "chromium"  # Options: "chromium", "firefox", "webkit"
HEADLESS = False  # Set to True to run browser in background (no GUI)
BROWSER_TIMEOUT = 60000  # milliseconds (60 seconds)

# Authentication Configuration
MANUAL_LOGIN_TIMEOUT = 300  # seconds (5 minutes) - max time to wait for login
LOGIN_CHECK_INTERVAL = 2  # seconds - how often to check if login completed
SESSION_ID_RETRY_ATTEMPTS = 5  # Number of times to retry getting session ID
SESSION_ID_RETRY_DELAY = 3  # seconds between retries

# Download Configuration
DOWNLOAD_TIMEOUT = 60000  # milliseconds (60 seconds)
WAIT_FOR_DOWNLOAD = 30  # seconds to wait for download to complete

# Session Configuration
SAVE_SESSION = True  # Save browser session for reuse
SESSION_FILE = "ems_session.json"  # File to store session data

# Request Configuration
REQUEST_TIMEOUT = 30000  # milliseconds

# Logging Configuration
LOG_LEVEL = logging.INFO
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# DataFrame Configuration
COLUMN_NAMES = {
    'sectionCode': 'Section Code',
    'orgCode': 'Organization Code'
}

# Output Configuration
OUTPUT_CSV = f'usace_sections_{SECTION_FILTER}.csv'
OUTPUT_EXCEL = f'usace_sections_{SECTION_FILTER}.xlsx'

# ============================================================================
# LOGGING SETUP
# ============================================================================

logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)
logger = logging.getLogger(__name__)

# ============================================================================
# SHAREPOINT FUNCTIONS
# ============================================================================

async def handle_sharepoint_login(page: Page, email: str) -> bool:
    """
    Handle SharePoint login if prompted.
    
    Args:
        page (Page): Playwright page object
        email (str): Email address for login
        
    Returns:
        bool: True if login handled or not needed
    """
    try:
        logger.info("Checking for SharePoint login prompt...")
        
        # Wait for email input field with a reasonable timeout
        try:
            await page.wait_for_selector("input[type='email']", timeout=10000)
            logger.info("Login prompt detected!")
            
            # Fill in the email
            await page.fill("input[type='email']", email)
            logger.info(f"✓ Email address '{email}' filled in")
            
            # Wait a moment for the field to register
            await asyncio.sleep(0.5)
            
            # Click Next/Submit button
            try:
                # Try multiple selector strategies for the submit button
                submit_clicked = False
                
                # Strategy 1: input[type='submit']
                submit_button = page.locator("input[type='submit']")
                if await submit_button.count() > 0:
                    await submit_button.click()
                    submit_clicked = True
                    logger.info("✓ Clicked 'Next' button (Strategy 1)")
                
                # Strategy 2: button with specific text
                if not submit_clicked:
                    next_button = page.locator("button:has-text('Next')")
                    if await next_button.count() > 0:
                        await next_button.click()
                        submit_clicked = True
                        logger.info("✓ Clicked 'Next' button (Strategy 2)")
                
                # Strategy 3: Any submit button
                if not submit_clicked:
                    any_submit = page.locator("button[type='submit']")
                    if await any_submit.count() > 0:
                        await any_submit.click()
                        submit_clicked = True
                        logger.info("✓ Clicked 'Next' button (Strategy 3)")
                
                if submit_clicked:
                    # Wait for authentication to complete
                    logger.info("Waiting for authentication to complete...")
                    await asyncio.sleep(3)
                    
                    # Wait for page to load after authentication
                    try:
                        await page.wait_for_load_state("networkidle", timeout=60000)
                        logger.info("✓ Authentication completed")
                    except:
                        logger.warning("Page didn't reach networkidle, but continuing...")
                    
                    return True
                else:
                    logger.warning("Could not find submit button")
                    return False
                    
            except Exception as e:
                logger.error(f"Error clicking submit button: {e}")
                return False
                
        except Exception as e:
            logger.info("No login prompt found - already authenticated or different auth method")
            return True
            
    except Exception as e:
        logger.warning(f"Error in login handler: {e}")
        logger.info("Proceeding anyway - may already be logged in")
        return True


async def download_cercap_file(context: BrowserContext, email: str) -> bool:
    """
    Navigate to SharePoint and download CERCAP_EXPORT.csv file.
    
    Args:
        context (BrowserContext): Browser context
        email (str): Email address for authentication
        
    Returns:
        bool: True if download successful
    """
    page = await context.new_page()
    
    try:
        logger.info("="*80)
        logger.info("STEP 1: DOWNLOADING CERCAP FILE FROM SHAREPOINT")
        logger.info("="*80)
        logger.info(f"Navigating to SharePoint: {SHAREPOINT_URL}")
        
        # Navigate to SharePoint
        await page.goto(SHAREPOINT_URL, timeout=BROWSER_TIMEOUT)
        
        # Wait a moment for page to start loading
        await asyncio.sleep(2)
        
        # Handle login if prompted
        login_handled = await handle_sharepoint_login(page, email)
        
        if not login_handled:
            logger.warning("Login may not have completed successfully")
        
        # Wait for page to fully load
        logger.info("Waiting for SharePoint page to fully load...")
        try:
            await page.wait_for_load_state("networkidle", timeout=60000)
        except:
            logger.warning("Page didn't reach networkidle, but continuing...")
        
        # Additional wait for dynamic content
        await asyncio.sleep(3)
        
        # Wait for document library to be visible
        try:
            await page.wait_for_selector("[data-automationid='FieldRenderer-name']", timeout=30000)
            logger.info("✓ Document library loaded successfully")
        except:
            logger.warning("Document library selector not found, but continuing...")
        
        logger.info(f"Looking for file: {CERCAP_FILENAME}")
        
        # Find the file by its title/name - try multiple strategies
        file_element = None
        
        # Strategy 1: Exact title match
        file_element = page.locator(f'span[title="{CERCAP_FILENAME}"]').first
        if await file_element.count() == 0:
            # Strategy 2: Text content match
            file_element = page.locator(f'span:has-text("{CERCAP_FILENAME}")').first
        
        if await file_element.count() == 0:
            # Strategy 3: Partial match
            file_element = page.locator(f'span:text-is("{CERCAP_FILENAME}")').first
        
        # Check if file exists
        if await file_element.count() == 0:
            logger.error(f"Could not find file: {CERCAP_FILENAME}")
            
            # Debug: List available files
            logger.info("Available files in library:")
            try:
                file_spans = page.locator('[data-automationid="field-LinkFilename"] span[role="button"]')
                count = await file_spans.count()
                for i in range(min(count, 10)):  # Show first 10 files
                    text = await file_spans.nth(i).text_content()
                    logger.info(f"  - {text}")
            except:
                pass
            
            await page.close()
            return False
        
        logger.info(f"✓ Found file: {CERCAP_FILENAME}")
        
        # Right-click on the file to open context menu
        logger.info("Right-clicking file to open context menu...")
        await file_element.click(button="right")
        
        # Wait for context menu to appear
        await asyncio.sleep(1.5)
        
        # Click the Download option
        logger.info("Looking for 'Download' option...")
        
        # Try multiple strategies for finding Download button
        download_button = None
        
        # Strategy 1: Exact text match in span
        download_button = page.locator('span.ms-ContextualMenu-itemText:has-text("Download")').first
        
        if await download_button.count() == 0:
            # Strategy 2: Any element with Download text
            download_button = page.locator('text=Download').first
        
        if await download_button.count() == 0:
            logger.error("Could not find Download option in context menu")
            
            # Debug: Show available menu items
            logger.info("Available menu items:")
            try:
                menu_items = page.locator('.ms-ContextualMenu-itemText')
                count = await menu_items.count()
                for i in range(count):
                    text = await menu_items.nth(i).text_content()
                    logger.info(f"  - {text}")
            except:
                pass
            
            await page.close()
            return False
        
        logger.info("Clicking 'Download' option...")
        
        # Set up download handler
        async with page.expect_download(timeout=DOWNLOAD_TIMEOUT) as download_info:
            await download_button.click()
        
        download = await download_info.value
        
        # Ensure download directory exists
        os.makedirs(DOWNLOAD_PATH, exist_ok=True)
        
        # Save the file
        download_file_path = os.path.join(DOWNLOAD_PATH, CERCAP_FILENAME)
        await download.save_as(download_file_path)
        
        logger.info(f"✓ File downloaded successfully to: {download_file_path}")
        
        # Verify file exists
        if os.path.exists(download_file_path):
            file_size = os.path.getsize(download_file_path)
            logger.info(f"✓ File verified: {file_size:,} bytes")
            await page.close()
            return True
        else:
            logger.error("Download completed but file not found")
            await page.close()
            return False
        
    except Exception as e:
        logger.error(f"Error downloading CERCAP file: {e}")
        import traceback
        traceback.print_exc()
        
        # Take debug screenshot
        try:
            screenshot_path = os.path.join(DOWNLOAD_PATH, "sharepoint_error.png")
            await page.screenshot(path=screenshot_path)
            logger.info(f"Debug screenshot saved as '{screenshot_path}'")
        except:
            pass
        
        if not page.is_closed():
            await page.close()
        return False

# ============================================================================
# PLAYWRIGHT BROWSER FUNCTIONS
# ============================================================================

async def create_browser_context(playwright) -> Tuple[Browser, BrowserContext]:
    """
    Create and configure browser context with download settings.
    
    Args:
        playwright: Playwright instance
        
    Returns:
        Tuple[Browser, BrowserContext]: Browser and context objects
    """
    logger.info(f"Launching {BROWSER_TYPE} browser (headless={HEADLESS})")
    
    # Launch browser
    if BROWSER_TYPE == "chromium":
        browser = await playwright.chromium.launch(headless=HEADLESS)
    elif BROWSER_TYPE == "firefox":
        browser = await playwright.firefox.launch(headless=HEADLESS)
    elif BROWSER_TYPE == "webkit":
        browser = await playwright.webkit.launch(headless=HEADLESS)
    else:
        raise ValueError(f"Invalid browser type: {BROWSER_TYPE}")
    
    # Create context with session persistence and download path
    context = await browser.new_context(
        viewport={'width': 1280, 'height': 720},
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        accept_downloads=True
    )
    
    # Set default timeout
    context.set_default_timeout(BROWSER_TIMEOUT)
    
    return browser, context


async def click_acknowledge_button(page: Page) -> bool:
    """
    Click the "I Understand and Acknowledge" button if it appears.
    Handles cases where button is out of viewport by scrolling it into view.
    
    Args:
        page (Page): Playwright page object
        
    Returns:
        bool: True if button was found and clicked
    """
    try:
        logger.info("Looking for 'I Understand and Acknowledge' button...")
        
        # Wait for button with the specific text
        button = page.locator('button:has-text("I Understand and Acknowledge")')
        
        # Check if button exists with a short timeout
        try:
            await button.wait_for(timeout=5000)
            logger.info("Found acknowledgment button")
            
            # Scroll the button into view before clicking
            logger.info("Scrolling button into view...")
            await button.scroll_into_view_if_needed()
            
            # Wait a moment for scroll to complete
            await asyncio.sleep(0.5)
            
            # Alternative: Use JavaScript to scroll to the button
            await page.evaluate('''() => {
                const button = document.querySelector('button');
                const buttons = Array.from(document.querySelectorAll('button'));
                const targetButton = buttons.find(btn => btn.textContent.includes('I Understand and Acknowledge'));
                if (targetButton) {
                    targetButton.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }
            }''')
            
            # Wait for scroll animation
            await asyncio.sleep(1)
            
            # Try clicking with force option (clicks even if obscured)
            logger.info("Clicking acknowledgment button...")
            await button.click(force=True)
            
            # Wait for any modal/dialog to close
            await asyncio.sleep(1)
            
            logger.info("✓ Acknowledgment button clicked")
            return True
            
        except Exception as e:
            logger.info(f"No acknowledgment button found or already dismissed: {e}")
            return False
            
    except Exception as e:
        logger.warning(f"Could not click acknowledgment button: {e}")
        return False


async def wait_for_login_completion(page: Page, context: BrowserContext) -> bool:
    """
    Wait for user to complete manual login by checking for URL change or session validity.
    
    Args:
        page (Page): Playwright page object
        context (BrowserContext): Browser context
        
    Returns:
        bool: True if login appears successful
    """
    logger.info("="*80)
    logger.info("STEP 2: MANUAL LOGIN TO EMS")
    logger.info("="*80)
    logger.info(f"Please log in to EMS in the browser window.")
    logger.info(f"Maximum wait time: {MANUAL_LOGIN_TIMEOUT} seconds")
    logger.info(f"Checking for login completion every {LOGIN_CHECK_INTERVAL} seconds...")
    logger.info("="*80)
    
    start_time = asyncio.get_event_loop().time()
    initial_url = page.url
    
    while True:
        elapsed = asyncio.get_event_loop().time() - start_time
        
        if elapsed > MANUAL_LOGIN_TIMEOUT:
            logger.error(f"Login timeout after {MANUAL_LOGIN_TIMEOUT} seconds")
            return False
        
        # Check if URL has changed (indicating navigation after login)
        current_url = page.url
        if current_url != initial_url and "login" not in current_url.lower():
            logger.info(f"✓ URL changed to: {current_url}")
            logger.info("Login appears successful!")
            return True
        
        # Try to check session endpoint
        try:
            test_page = await context.new_page()
            response = await test_page.goto(SESSION_ID_ENDPOINT, wait_until="domcontentloaded", timeout=5000)
            
            if response and response.status == 200:
                content = await test_page.content()
                if "sessionId" in content:
                    logger.info("✓ Session endpoint accessible - login successful!")
                    await test_page.close()
                    return True
            
            await test_page.close()
        except Exception:
            pass  # Silently continue checking
        
        # Wait before next check
        await asyncio.sleep(LOGIN_CHECK_INTERVAL)
        
        # Show progress
        if int(elapsed) % 10 == 0:  # Log every 10 seconds
            logger.info(f"Still waiting for login... ({int(elapsed)}s elapsed)")


async def authenticate_browser(context: BrowserContext) -> bool:
    """
    Authenticate in the browser (manual login with acknowledgment).
    
    Args:
        context (BrowserContext): Browser context
        
    Returns:
        bool: True if authentication successful
    """
    page = await context.new_page()
    
    try:
        logger.info(f"Navigating to EMS login page: {EMS_LOGIN_URL}")
        await page.goto(EMS_LOGIN_URL, wait_until="networkidle")
        
        # Click the acknowledgment button if present
        await click_acknowledge_button(page)
        
        # Wait for manual login completion
        login_success = await wait_for_login_completion(page, context)
        
        if not login_success:
            await page.close()
            return False
        
        # Save session if configured
        if SAVE_SESSION:
            await save_browser_session(context)
        
        await page.close()
        return True
        
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        if not page.is_closed():
            await page.close()
        return False


async def get_session_id(context: BrowserContext) -> Optional[int]:
    """
    Retrieve session ID from EMS API with retry logic.
    
    Args:
        context (BrowserContext): Authenticated browser context
        
    Returns:
        Optional[int]: Session ID or None if failed
    """
    logger.info("="*80)
    logger.info("STEP 3: RETRIEVING SESSION ID")
    logger.info("="*80)
    logger.info(f"Endpoint: {SESSION_ID_ENDPOINT}")
    
    for attempt in range(1, SESSION_ID_RETRY_ATTEMPTS + 1):
        page = await context.new_page()
        
        try:
            logger.info(f"Attempt {attempt}/{SESSION_ID_RETRY_ATTEMPTS}")
            
            # Navigate to session ID endpoint
            response = await page.goto(SESSION_ID_ENDPOINT, wait_until="networkidle")
            
            if response.status != 200:
                logger.warning(f"HTTP {response.status}: {response.status_text}")
                await page.close()
                
                if attempt < SESSION_ID_RETRY_ATTEMPTS:
                    logger.info(f"Retrying in {SESSION_ID_RETRY_DELAY} seconds...")
                    await asyncio.sleep(SESSION_ID_RETRY_DELAY)
                    continue
                else:
                    return None
            
            # Extract JSON from page
            json_text = await page.evaluate('''() => {
                return document.body.innerText || document.body.textContent;
            }''')
            
            # Parse JSON
            data = json.loads(json_text)
            
            # Extract session ID
            if isinstance(data, list) and len(data) > 0:
                session_id = data[0].get('sessionId')
                if session_id:
                    logger.info(f"✓ Session ID retrieved: {session_id}")
                    logger.info(f"Session details:")
                    logger.info(f"  - Employee ID: {data[0].get('employeeId')}")
                    logger.info(f"  - Office Code: {data[0].get('officeCode')}")
                    logger.info(f"  - Last Login: {data[0].get('lastLogIn')}")
                    
                    await page.close()
                    return session_id
            
            logger.warning("Session ID not found in response")
            await page.close()
            
            if attempt < SESSION_ID_RETRY_ATTEMPTS:
                logger.info(f"Retrying in {SESSION_ID_RETRY_DELAY} seconds...")
                await asyncio.sleep(SESSION_ID_RETRY_DELAY)
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            await page.close()
            
            if attempt < SESSION_ID_RETRY_ATTEMPTS:
                await asyncio.sleep(SESSION_ID_RETRY_DELAY)
            
        except Exception as e:
            logger.error(f"Error getting session ID: {e}")
            if not page.is_closed():
                await page.close()
            
            if attempt < SESSION_ID_RETRY_ATTEMPTS:
                await asyncio.sleep(SESSION_ID_RETRY_DELAY)
    
    logger.error("Failed to retrieve session ID after all attempts")
    return None


async def save_browser_session(context: BrowserContext):
    """
    Save browser session (cookies, storage) for reuse.
    
    Args:
        context (BrowserContext): Browser context to save
    """
    try:
        storage_state = await context.storage_state()
        with open(SESSION_FILE, 'w') as f:
            json.dump(storage_state, f, indent=2)
        logger.info(f"Browser session saved to {SESSION_FILE}")
    except Exception as e:
        logger.error(f"Failed to save session: {e}")


async def fetch_sections_with_browser(context: BrowserContext) -> Optional[List[Dict]]:
    """
    Fetch sections data using authenticated browser context.
    
    Args:
        context (BrowserContext): Authenticated browser context
        
    Returns:
        Optional[List[Dict]]: List of section dictionaries or None if request fails
    """
    page = await context.new_page()
    
    try:
        logger.info("="*80)
        logger.info("STEP 4: QUERYING SECTIONS DATA")
        logger.info("="*80)
        logger.info(f"Endpoint: {SECTIONS_ENDPOINT}")
        
        # Navigate to API endpoint
        response = await page.goto(SECTIONS_ENDPOINT, wait_until="networkidle")
        
        if response.status != 200:
            logger.error(f"HTTP {response.status}: {response.status_text}")
            await page.close()
            return None
        
        # Extract JSON from page
        json_text = await page.evaluate('''() => {
            return document.body.innerText || document.body.textContent;
        }''')
        
        # Parse JSON
        data = json.loads(json_text)
        
        logger.info(f"✓ Successfully retrieved {len(data)} total sections")
        
        await page.close()
        return data
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON response: {e}")
        
    except Exception as e:
        logger.error(f"Error fetching data: {e}")
        
    finally:
        if not page.is_closed():
            await page.close()
    
    return None


async def navigate_to_resources_page(context: BrowserContext) -> bool:
    """
    Navigate to the EMS resources configuration page.
    
    Args:
        context (BrowserContext): Authenticated browser context
        
    Returns:
        bool: True if navigation successful
    """
    page = await context.new_page()
    
    try:
        logger.info("="*80)
        logger.info("STEP 5: NAVIGATING TO RESOURCES PAGE")
        logger.info("="*80)
        logger.info(f"URL: {EMS_RESOURCES_URL}")
        
        await page.goto(EMS_RESOURCES_URL, wait_until="networkidle")
        
        logger.info(f"✓ Successfully navigated to resources page")
        logger.info(f"Current URL: {page.url}")
        
        # Keep the page open for user interaction
        logger.info("\nResources page is now open. Browser will remain open for your use.")
        
        # Don't close the page - let it stay open
        return True
        
    except Exception as e:
        logger.error(f"Error navigating to resources page: {e}")
        if not page.is_closed():
            await page.close()
        return False


# ============================================================================
# DATA PROCESSING FUNCTIONS
# ============================================================================

def filter_sections_by_code(df: pd.DataFrame, filter_text: str) -> pd.DataFrame:
    """
    Filter DataFrame to only include sections containing the filter text.
    
    Args:
        df (pd.DataFrame): DataFrame to filter
        filter_text (str): Text to search for in Section Code
        
    Returns:
        pd.DataFrame: Filtered DataFrame
    """
    if df.empty:
        return df
    
    original_count = len(df)
    
    # Filter where Section Code contains the filter text (case-insensitive)
    filtered_df = df[df['Section Code'].str.contains(filter_text, case=False, na=False)]
    
    filtered_count = len(filtered_df)
    logger.info(f"Filtered sections: {original_count} → {filtered_count} (containing '{filter_text}')")
    
    return filtered_df.reset_index(drop=True)


def create_sections_dataframe(data: List[Dict], apply_filter: bool = True) -> pd.DataFrame:
    """
    Convert sections data to a pandas DataFrame.
    
    Args:
        data (List[Dict]): List of section dictionaries from API
        apply_filter (bool): Whether to apply section filter
        
    Returns:
        pd.DataFrame: DataFrame containing sections data with renamed columns
    """
    if not data:
        logger.warning("No data provided to create DataFrame")
        return pd.DataFrame()
    
    # Create DataFrame from list of dictionaries
    df = pd.DataFrame(data)
    
    # Rename columns for better readability
    df = df.rename(columns=COLUMN_NAMES)
    
    # Apply filter if requested
    if apply_filter and SECTION_FILTER:
        df = filter_sections_by_code(df, SECTION_FILTER)
    
    # Sort by Section Code for easier navigation
    if not df.empty:
        df = df.sort_values('Section Code').reset_index(drop=True)
    
    logger.info(f"Created DataFrame with {len(df)} rows and {len(df.columns)} columns")
    
    return df


def get_sections_summary(df: pd.DataFrame) -> Dict:
    """
    Generate summary statistics for the sections DataFrame.
    
    Args:
        df (pd.DataFrame): Sections DataFrame
        
    Returns:
        Dict: Dictionary containing summary statistics
    """
    summary = {
        'total_sections': len(df),
        'unique_org_codes': df['Organization Code'].nunique() if not df.empty else 0,
        'columns': list(df.columns),
    }
    
    return summary


def save_to_csv(df: pd.DataFrame, filename: str = OUTPUT_CSV) -> bool:
    """
    Save DataFrame to CSV file.
    
    Args:
        df (pd.DataFrame): DataFrame to save
        filename (str): Output filename
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        df.to_csv(filename, index=False)
        logger.info(f"✓ Data saved to {filename}")
        return True
    except Exception as e:
        logger.error(f"Failed to save CSV: {e}")
        return False


def save_to_excel(df: pd.DataFrame, filename: str = OUTPUT_EXCEL) -> bool:
    """
    Save DataFrame to Excel file.
    
    Args:
        df (pd.DataFrame): DataFrame to save
        filename (str): Output filename
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        df.to_excel(filename, index=False, engine='openpyxl')
        logger.info(f"✓ Data saved to {filename}")
        return True
    except Exception as e:
        logger.error(f"Failed to save Excel: {e}")
        return False


# ============================================================================
# MAIN ASYNC FUNCTION
# ============================================================================

async def main():
    """
    Main async function to orchestrate the data retrieval process.
    """
    print("\n" + "="*80)
    print("USACE EMS DATA RETRIEVAL WORKFLOW")
    print("="*80)
    print(f"Employee ID: {EMPLOYEE_ID}")
    print(f"Office Code: {OFFICE_CODE}")
    print(f"Section Filter: {SECTION_FILTER}")
    print(f"Email: {EMAIL_ADDRESS}")
    print(f"Download Path: {DOWNLOAD_PATH}")
    print("="*80 + "\n")
    
    sections_df = pd.DataFrame()
    session_id = None
    
    async with async_playwright() as playwright:
        browser = None
        context = None
        
        try:
            # Create browser and context
            browser, context = await create_browser_context(playwright)
            
            # Step 1: Download CERCAP file from SharePoint
            download_success = await download_cercap_file(context, EMAIL_ADDRESS)
            
            if not download_success:
                logger.warning("Failed to download CERCAP file, continuing with EMS login...")
            
            # Step 2: Authenticate to EMS
            auth_success = await authenticate_browser(context)
            
            if not auth_success:
                logger.error("Authentication failed")
                return sections_df, session_id
            
            # Step 3: Get session ID
            session_id = await get_session_id(context)
            
            if not session_id:
                logger.error("Failed to retrieve session ID")
                return sections_df, session_id
            
            # Step 4: Fetch sections data
            sections_data = await fetch_sections_with_browser(context)
            
            if sections_data:
                # Create DataFrame with filter applied
                sections_df = create_sections_dataframe(sections_data, apply_filter=True)
                
                # Display summary information (no detailed data)
                print("\n" + "="*80)
                print("DATA SUMMARY")
                print("="*80)
                
                summary = get_sections_summary(sections_df)
                print(f"\nTotal Sections (filtered for '{SECTION_FILTER}'): {summary['total_sections']}")
                print(f"Unique Organization Codes: {summary['unique_org_codes']}")
                print(f"Columns: {', '.join(summary['columns'])}")
                
                if not sections_df.empty:
                    # Save to files
                    save_to_csv(sections_df)
                    save_to_excel(sections_df)
                else:
                    print(f"\n⚠️  No sections found containing '{SECTION_FILTER}'")
                
            else:
                logger.error("Failed to retrieve sections data")
            
            # Step 5: Navigate to resources page
            await navigate_to_resources_page(context)
            
            # Keep browser open
            logger.info("\n" + "="*80)
            logger.info("Browser will remain open. Close manually when done.")
            logger.info("="*80)
            
            # Wait indefinitely (until user closes browser)
            await asyncio.sleep(3600)  # Wait 1 hour or until interrupted
                
        except Exception as e:
            logger.error(f"Error in main execution: {e}")
            import traceback
            traceback.print_exc()
            
        finally:
            # Cleanup (only if not keeping browser open)
            logger.info("Cleaning up...")
    
    return sections_df, session_id


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    try:
        # Run the async main function
        sections_df, session_id = asyncio.run(main())
        
        print("\n" + "="*80)
        print("WORKFLOW COMPLETED")
        print("="*80)
        
        if session_id:
            print(f"\n✓ Session ID: {session_id}")
        
        if not sections_df.empty:
            print(f"✓ Successfully retrieved {len(sections_df)} sections (filtered for '{SECTION_FILTER}')")
            print(f"✓ Data saved to {OUTPUT_CSV}")
            print(f"✓ Data saved to {OUTPUT_EXCEL}")
        
        cercap_path = os.path.join(DOWNLOAD_PATH, CERCAP_FILENAME)
        if os.path.exists(cercap_path):
            print(f"✓ CERCAP file downloaded to {cercap_path}")
        
    except KeyboardInterrupt:
        print("\n\nScript interrupted by user")
    except Exception as e:
        print(f"\n\nError: {e}")
        import traceback
        traceback.print_exc()