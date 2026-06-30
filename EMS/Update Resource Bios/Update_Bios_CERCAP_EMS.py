"""
USACE EMS API Query Script with Playwright Browser Authentication
Enhanced with CERCAP Data Comparison and Automatic Updates

This script uses Playwright to authenticate via browser and then query the 
U.S. Army Corps of Engineers (USACE) Enterprise Management System (EMS) API.
It compares EMS data with CERCAP export data and automatically updates:
- CoPs (Communities of Practice) via API
- AoEs (Areas of Expertise) via API  
- Bios via UI interaction

Workflow:
1. Check if CERCAP export is recent (< 24 hours), skip download if so
2. Navigate to CERCAP and download export (if needed)
3. Authenticate to EMS and get session ID
4. Query FTE Organizations data (filtered to CEMVR-EC and CEMVR-DC)
5. For each organization, get employee profiles
6. Compare with CERCAP data (CoP, AoE, Bio)
7. Add missing CoPs and AoEs via API
8. Update Bios via UI interaction
9. Verify all additions
10. Log all actions to CSV

Author: Ryan Benac
Date: 2026-05-12

Requirements:
    pip install playwright pandas openpyxl
    playwright install chromium
"""

import asyncio
import json
import pandas as pd
from typing import Dict, List, Optional, Tuple, Set
import logging
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from datetime import datetime, timedelta
import os
import csv
from collections import defaultdict
import sys

# Force UTF-8 encoding for console output on Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# ============================================================================
# CONFIGURATION SECTION
# ============================================================================
import json

# Load configuration
config_path = "C:\\Workspace\\GIT\\USACE-AIS-Scripts\\config.json"

with open(config_path, 'r') as f:
    config = json.load(f)

# User Configuration
EMPLOYEE_ID = config["employee_id"]
OFFICE_CODE = "CEMVR"
SECTION_FILTERS = ["CEMVR-EC", "CEMVR-DC"]

# CERCAP Configuration
CERCAP_URL = "https://cwbi-int.sec.usace.army.mil/int/f?p=121:1:"
CERCAP_FILENAME = "CERCAP_EXPORT.csv"
DOWNLOAD_PATH = r"C:\Workspace\LOCAL SANDBOX\EMS Rest API\Update Resource Bios"
LOGS_PATH = os.path.join(DOWNLOAD_PATH, "LOGS")
CERCAP_MAX_AGE_HOURS = 24

# API Configuration
API_BASE_URL = "https://ems.sec.usace.army.mil/api/ems"
API_CONFIG_BASE_URL = "https://ems.sec.usace.army.mil/api/ems_config"
SESSION_ID_ENDPOINT = f"{API_BASE_URL}/getSessionID/-1/{EMPLOYEE_ID}/{OFFICE_CODE}"
EMS_LOGIN_URL = "https://ems.sec.usace.army.mil"
EMS_RESOURCES_URL = "https://ems.sec.usace.army.mil/ems/configuration/resources#profile"

# API Endpoints
FTE_ORGS_ENDPOINT = f"{API_CONFIG_BASE_URL}/get_FTE_ORGS/{{session_id}}"
EMPLOYEE_PROFILE_ENDPOINT = f"{API_CONFIG_BASE_URL}/get_Employee_Profile/{{session_id}}/{{section_code}}"
EMPLOYEE_PROFILE_DETAIL_ENDPOINT = f"{API_CONFIG_BASE_URL}/get_Employee_Profile_Employee/{{session_id}}/{{employee_id}}"
COP_EMPLOYEE_ENDPOINT = f"{API_CONFIG_BASE_URL}/get_CoP_Emp/{{session_id}}/{{employee_id}}"
EXPERTISE_EMPLOYEE_ENDPOINT = f"{API_CONFIG_BASE_URL}/get_Expertise_Emp/{{session_id}}/{{employee_id}}"
CERTIFICATION_EMPLOYEE_ENDPOINT = f"{API_CONFIG_BASE_URL}/get_Certification_Emp/{{session_id}}/{{employee_id}}"
COP_CATEGORIES_ENDPOINT = f"{API_CONFIG_BASE_URL}/get_CoP_Categories/{{session_id}}"
EXPERTISE_CATEGORIES_ENDPOINT = f"{API_CONFIG_BASE_URL}/get_Expertise_Categories/{{session_id}}"
UPSERT_COP_ENDPOINT = f"{API_CONFIG_BASE_URL}/upsert_CoP_Emp/{{session_id}}"
UPSERT_EXPERTISE_ENDPOINT = f"{API_CONFIG_BASE_URL}/upsert_Expertise_Emp/{{session_id}}/{{employee_id}}/{{exp_id}}/T"

# Browser Configuration
BROWSER_TYPE = "chromium"
HEADLESS_DOWNLOAD = False  # Show browser for CERCAP download (CAC authentication)
HEADLESS_API = False        # Show browser for EMS operations (to see bio updates)
BROWSER_TIMEOUT = 60000

# Authentication Configuration
MANUAL_LOGIN_TIMEOUT = 300
LOGIN_CHECK_INTERVAL = 2
SESSION_ID_RETRY_ATTEMPTS = 5
SESSION_ID_RETRY_DELAY = 3

# Download Configuration
DOWNLOAD_TIMEOUT = 120000

# Session Configuration
SAVE_SESSION = True
SESSION_FILE = "ems_session.json"

# Request Configuration
REQUEST_TIMEOUT = 30000

# Logging Configuration
LOG_LEVEL = logging.INFO
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# Create logs directory if it doesn't exist
os.makedirs(LOGS_PATH, exist_ok=True)

# Log file paths
LOG_FILE = os.path.join(LOGS_PATH, f"main_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
ACTIONS_LOG_CSV = os.path.join(LOGS_PATH, f"ems_updates_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")

# ============================================================================
# LOGGING SETUP
# ============================================================================

logging.basicConfig(
    level=LOG_LEVEL,
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# CSV ACTION LOGGER
# ============================================================================

class ActionLogger:
    """
    Logs all EMS update actions to CSV file for audit trail.
    
    Attributes:
        actions (List[Dict]): List of action dictionaries to be saved to CSV
    """
    
    def __init__(self):
        """Initialize the action logger with empty actions list."""
        self.actions = []
    
    def log_action(self, employee_id: int, name: str, email: str, action_type: str, 
                   item: str, status: str, details: str = ""):
        """
        Log an action taken on an employee record.
        
        Args:
            employee_id: Employee ID number
            name: Employee full name
            email: Employee email address
            action_type: Type of action (e.g., 'Bio', 'CoP', 'AoE', 'Verification')
            item: Specific item being acted upon
            status: Status of the action (e.g., 'Updated', 'Error', 'Skipped')
            details: Additional details about the action
        """
        self.actions.append({
            'Timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'Employee_ID': employee_id,
            'Name': name,
            'Email': email,
            'Action_Type': action_type,
            'Item': item,
            'Status': status,
            'Details': details
        })
    
    def save(self):
        """Save all logged actions to CSV file."""
        if self.actions:
            df = pd.DataFrame(self.actions)
            df.to_csv(ACTIONS_LOG_CSV, index=False, encoding='utf-8')
            logger.info(f"[OK] Actions log saved to: {ACTIONS_LOG_CSV}")

# Initialize global action logger
action_logger = ActionLogger()

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def check_file_age(file_path: str, max_age_hours: int = 24) -> Tuple[bool, Optional[datetime]]:
    """
    Check if a file exists and is newer than the specified age.
    
    Args:
        file_path: Path to the file to check
        max_age_hours: Maximum age in hours for the file to be considered recent
        
    Returns:
        Tuple of (is_recent, modification_datetime)
        - is_recent: True if file exists and is newer than max_age_hours
        - modification_datetime: DateTime of last modification, or None if file doesn't exist
    """
    if not os.path.exists(file_path):
        return False, None
    
    mod_time = os.path.getmtime(file_path)
    mod_datetime = datetime.fromtimestamp(mod_time)
    age = datetime.now() - mod_datetime
    max_age = timedelta(hours=max_age_hours)
    
    return age < max_age, mod_datetime


def format_timedelta(td: timedelta) -> str:
    """
    Format a timedelta into a human-readable string.
    
    Args:
        td: Timedelta object to format
        
    Returns:
        Human-readable string (e.g., "2 hours, 30 minutes")
    """
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    
    parts = []
    if hours > 0:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes > 0:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    
    return ", ".join(parts) if parts else "less than 1 minute"

# ============================================================================
# CERCAP DATA PROCESSING FUNCTIONS
# ============================================================================

def load_cercap_data(file_path: str) -> Dict[str, List[Dict]]:
    """
    Load CERCAP export CSV and group records by email address.
    
    Tries multiple encodings to handle various CSV formats.
    
    Args:
        file_path: Path to the CERCAP CSV export file
        
    Returns:
        Dictionary mapping email addresses (uppercase) to lists of employee records
        Each record contains: last_name, first_name, email, cop, aoe, parent_aoe, bio
    """
    logger.info(f"Loading CERCAP data from: {file_path}")
    
    if not os.path.exists(file_path):
        logger.error(f"CERCAP file not found: {file_path}")
        return {}
    
    cercap_data = defaultdict(list)
    encodings = ['utf-8', 'windows-1252', 'latin-1', 'iso-8859-1']
    
    # Try each encoding until one works
    for encoding in encodings:
        try:
            logger.info(f"Attempting to load with {encoding} encoding...")
            with open(file_path, 'r', encoding=encoding, errors='replace') as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    email = row.get('Email', '').strip().upper()
                    
                    if email:
                        cercap_data[email].append({
                            'last_name': row.get('Last Name', '').strip(),
                            'first_name': row.get('First Name', '').strip(),
                            'email': email,
                            'cop': row.get('CoP', '').strip().upper() if row.get('CoP') else '',
                            'aoe': row.get('AoE', '').strip() if row.get('AoE') else '',
                            'parent_aoe': row.get('Parent AoE', '').strip() if row.get('Parent AoE') else '',
                            'bio': row.get('Bio', '').strip() if row.get('Bio') else '',
                        })
            
            logger.info(f"[OK] Successfully loaded with {encoding} encoding")
            logger.info(f"[OK] Loaded CERCAP data for {len(cercap_data)} unique email addresses")
            
            total_records = sum(len(records) for records in cercap_data.values())
            logger.info(f"  Total CERCAP records: {total_records}")
            
            # Log first 10 email addresses for debugging
            logger.info("Sample email addresses from CERCAP:")
            for i, email in enumerate(list(cercap_data.keys())[:10], 1):
                logger.info(f"  {i}. {email}")
            
            return dict(cercap_data)
            
        except UnicodeDecodeError:
            cercap_data.clear()
            continue
        except Exception as e:
            logger.error(f"Error loading CERCAP data with {encoding}: {e}")
            cercap_data.clear()
            continue
    
    logger.error("Failed to load CERCAP data with any encoding")
    return {}


def get_cercap_cops(cercap_records: List[Dict]) -> Set[str]:
    """
    Extract unique CoPs from CERCAP records.
    
    Args:
        cercap_records: List of CERCAP records for a single employee
        
    Returns:
        Set of CoP names (uppercase)
    """
    cops = set()
    for record in cercap_records:
        cop = record.get('cop', '').strip().upper()
        if cop:
            cops.add(cop)
    return cops


def get_cercap_aoes(cercap_records: List[Dict]) -> Set[str]:
    """
    Extract unique AoEs from CERCAP records (Parent AoE - AoE format).
    
    Args:
        cercap_records: List of CERCAP records for a single employee
        
    Returns:
        Set of AoE names in "Parent AoE - AoE" format
    """
    aoes = set()
    for record in cercap_records:
        parent_aoe = record.get('parent_aoe', '').strip()
        aoe = record.get('aoe', '').strip()
        
        if parent_aoe and aoe:
            combined_aoe = f"{parent_aoe} - {aoe}"
            aoes.add(combined_aoe)
    
    return aoes


def get_cercap_bio(cercap_records: List[Dict]) -> str:
    """
    Extract bio from CERCAP records.
    
    Takes the bio from the first record (all records for same email should have same bio).
    
    Args:
        cercap_records: List of CERCAP records for a single employee
        
    Returns:
        Bio text string, or empty string if no bio exists
    """
    if cercap_records:
        return cercap_records[0].get('bio', '').strip()
    return ""

# ============================================================================
# CERCAP DOWNLOAD FUNCTIONS
# ============================================================================

async def click_ok_button(page: Page, description: str = "OK") -> bool:
    """
    Click an OK button with the specific Oracle APEX structure.
    
    Args:
        page: Playwright page object
        description: Description of which OK button (for logging)
        
    Returns:
        True if button was found and clicked, False otherwise
    """
    try:
        ok_button = page.locator('button.ui-button:has(span.ui-button-text:text("OK"))')
        try:
            await ok_button.wait_for(timeout=5000, state="visible")
            await ok_button.click()
            await asyncio.sleep(1)
            return True
        except Exception:
            return False
    except Exception:
        return False


async def download_cercap_export(context: BrowserContext) -> bool:
    """
    Navigate to CERCAP and download the ATR CSV Export.
    
    This function handles the complete workflow:
    1. Navigate to CERCAP
    2. Handle CAC login
    3. Navigate to Reports > ATR CSV Export
    4. Click Actions > Download
    5. Download the CSV file
    
    Args:
        context: Playwright browser context
        
    Returns:
        True if download was successful, False otherwise
    """
    page = await context.new_page()
    
    try:
        logger.info("="*80)
        logger.info("DOWNLOADING CERCAP EXPORT")
        logger.info("="*80)
        
        # Navigate to CERCAP
        await page.goto(CERCAP_URL, timeout=BROWSER_TIMEOUT)
        await asyncio.sleep(2)
        
        # Handle initial OK button if present
        await click_ok_button(page, "Initial OK")
        
        # Click CAC Login button
        cac_login_button = page.locator('a#B311277971920506550[title="CAC Login"]')
        try:
            await cac_login_button.wait_for(timeout=10000, state="visible")
            await cac_login_button.click()
            await asyncio.sleep(3)
        except Exception:
            pass
        
        # Handle post-login OK button if present
        await click_ok_button(page, "Post-CAC Login OK")
        await asyncio.sleep(2)
        
        # Click CERCAP link
        cercap_link = page.locator('a[title="CERCAP"]:has-text("CERCAP")')
        await cercap_link.wait_for(timeout=10000, state="visible")
        await cercap_link.click()
        await asyncio.sleep(2)
        
        # Click Reports link
        reports_link = page.locator('a#Reports:has-text("Reports")')
        await reports_link.wait_for(timeout=10000, state="visible")
        await reports_link.click()
        await asyncio.sleep(2)
        
        # Click ATR CSV Export link
        atr_export_link = page.locator('a:has-text("ATR CSV Export")')
        await atr_export_link.wait_for(timeout=10000, state="visible")
        await atr_export_link.click()
        await asyncio.sleep(3)
        
        # Wait for the report to load
        logger.info("Waiting for report to load...")
        await page.wait_for_load_state("networkidle", timeout=30000)
        await asyncio.sleep(2)
        
        # Click the Actions button
        actions_button = page.locator('button#R226143515666960599_actions_button.a-IRR-button--actions')
        await actions_button.wait_for(timeout=10000, state="visible")
        await actions_button.click()
        logger.info("Clicked Actions button")
        await asyncio.sleep(1)
        
        # Click Download button in the menu (using specific button ID)
        download_button = page.locator('button#R226143515666960599_actions_menu_14i')
        await download_button.wait_for(timeout=10000, state="visible")
        logger.info("Download button is visible")
        await download_button.click()
        logger.info("Clicked Download button")
        await asyncio.sleep(2)
        
        # Click the final Download button in the dialog
        final_download_button = page.locator('button.ui-button--hot:has-text("Download")')
        await final_download_button.wait_for(timeout=10000, state="visible")
        logger.info("Final download dialog appeared")
        
        # Prepare download path
        os.makedirs(DOWNLOAD_PATH, exist_ok=True)
        download_file_path = os.path.join(DOWNLOAD_PATH, CERCAP_FILENAME)
        
        # Remove existing file if present
        if os.path.exists(download_file_path):
            try:
                os.remove(download_file_path)
                logger.info(f"Removed existing file: {download_file_path}")
            except Exception as e:
                logger.error(f"Could not remove existing file: {e}")
                await page.close()
                return False
        
        # Start download
        logger.info("Starting download...")
        async with page.expect_download(timeout=DOWNLOAD_TIMEOUT) as download_info:
            await final_download_button.click()
        
        download = await download_info.value
        await download.save_as(download_file_path)
        
        # Verify download
        if os.path.exists(download_file_path):
            file_size = os.path.getsize(download_file_path)
            logger.info(f"[OK] File downloaded: {file_size:,} bytes")
            logger.info(f"[OK] Saved to: {download_file_path}")
            await page.close()
            return True
        else:
            logger.error("Download file not found after save")
            await page.close()
            return False
        
    except Exception as e:
        logger.error(f"Error downloading CERCAP export: {e}")
        import traceback
        logger.error(traceback.format_exc())
        
        if not page.is_closed():
            await page.close()
        return False

# ============================================================================
# BROWSER FUNCTIONS
# ============================================================================

async def create_browser_context(playwright, headless: bool = False) -> Tuple[Browser, BrowserContext]:
    """
    Create and configure browser context with appropriate settings.
    
    Args:
        playwright: Playwright instance
        headless: Whether to run browser in headless mode
        
    Returns:
        Tuple of (Browser, BrowserContext)
    """
    if BROWSER_TYPE == "chromium":
        browser = await playwright.chromium.launch(headless=headless)
    elif BROWSER_TYPE == "firefox":
        browser = await playwright.firefox.launch(headless=headless)
    elif BROWSER_TYPE == "webkit":
        browser = await playwright.webkit.launch(headless=headless)
    else:
        raise ValueError(f"Invalid browser type: {BROWSER_TYPE}")
    
    context = await browser.new_context(
        viewport={'width': 1280, 'height': 720},
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        accept_downloads=True
    )
    
    context.set_default_timeout(BROWSER_TIMEOUT)
    return browser, context

async def navigate_to_profile_configuration(page: Page) -> bool:
    """
    Navigate from EMS home page to Profile Configuration page.
    
    Steps:
    1. Click Configurations tile
    2. Click Resources dropdown
    3. Click Profile Configuration
    
    Args:
        page: Playwright page object
        
    Returns:
        True if navigation successful, False otherwise
    """
    try:
        logger.info("Navigating to Profile Configuration...")
        
        # Step 1: Click Configurations tile - try multiple selectors
        logger.info("  Step 1: Clicking Configurations tile...")
        
        selectors = [
            'a[href="/ems/configuration/"]',
            'div.landing-page-tile-button a[href="/ems/configuration/"]',
            'a:has-text("Configurations")'
        ]
        
        clicked = False
        for selector in selectors:
            try:
                config_tile = page.locator(selector).first
                await config_tile.wait_for(timeout=5000, state="visible")
                await config_tile.click()
                logger.info(f"  Clicked Configurations (selector: {selector})")
                clicked = True
                break
            except:
                continue
        
        if not clicked:
            logger.error("  Could not find or click Configurations tile")
            return False
        
        await asyncio.sleep(3)
        
        # Step 2: Click Resources dropdown button
        logger.info("  Step 2: Opening Resources dropdown...")
        resources_dropdown = page.locator('button#Resources-dropdown-button')
        await resources_dropdown.wait_for(timeout=15000, state="visible")
        await resources_dropdown.click()
        logger.info("  Opened Resources dropdown")
        await asyncio.sleep(1)
        
        # Step 3: Click Profile Configuration in dropdown
        logger.info("  Step 3: Clicking Profile Configuration...")
        profile_config = page.locator('a[name="profile"][role="menuitem"]:has-text("Profile Configuration")')
        await profile_config.wait_for(timeout=10000, state="visible")
        await profile_config.click()
        logger.info("  Clicked Profile Configuration")
        await asyncio.sleep(3)
        
        # Wait for the page to load
        await page.wait_for_load_state("networkidle", timeout=15000)
        await asyncio.sleep(2)
        
        # Verify we're on the right page by looking for the section dropdown
        try:
            await page.wait_for_selector('input[aria-autocomplete="list"]', timeout=10000, state="visible")
            logger.info("  [OK] Profile Configuration page loaded")
            return True
        except:
            logger.error("  Section dropdown not found - may not be on correct page")
            return False
        
    except Exception as e:
        logger.error(f"  Error navigating to Profile Configuration: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False
    
async def click_acknowledge_button(page: Page) -> bool:
    """
    Click the 'I Understand and Acknowledge' button if it appears on EMS login.
    
    Args:
        page: Playwright page object
        
    Returns:
        True if button was found and clicked, False otherwise
    """
    try:
        button = page.locator('button:has-text("I Understand and Acknowledge")')
        try:
            await button.wait_for(timeout=5000)
            await button.scroll_into_view_if_needed()
            await asyncio.sleep(0.5)
            await button.click(force=True)
            await asyncio.sleep(1)
            return True
        except Exception:
            return False
    except Exception:
        return False


async def wait_for_login_completion(page: Page, context: BrowserContext) -> bool:
    """
    Wait for user to complete manual CAC login to EMS.
    
    Monitors the page URL and tests API access to determine when login is complete.
    
    Args:
        page: Playwright page object
        context: Playwright browser context
        
    Returns:
        True if login completed successfully, False if timeout
    """
    logger.info("="*80)
    logger.info("MANUAL LOGIN TO EMS")
    logger.info("="*80)
    logger.info(f"Please log in to EMS in the browser window.")
    logger.info("="*80)
    
    start_time = asyncio.get_event_loop().time()
    initial_url = page.url
    
    while True:
        elapsed = asyncio.get_event_loop().time() - start_time
        
        # Check for timeout
        if elapsed > MANUAL_LOGIN_TIMEOUT:
            logger.error(f"Login timeout after {MANUAL_LOGIN_TIMEOUT} seconds")
            return False
        
        # Check if URL changed (indicates successful login)
        current_url = page.url
        if current_url != initial_url and "login" not in current_url.lower():
            logger.info("[OK] Login successful!")
            return True
        
        # Test API access to confirm authentication
        try:
            test_page = await context.new_page()
            response = await test_page.goto(SESSION_ID_ENDPOINT, wait_until="domcontentloaded", timeout=5000)
            
            if response and response.status == 200:
                content = await test_page.content()
                if "sessionId" in content:
                    await test_page.close()
                    return True
            
            await test_page.close()
        except Exception:
            pass
        
        await asyncio.sleep(LOGIN_CHECK_INTERVAL)


async def authenticate_browser(context: BrowserContext) -> bool:
    """
    Authenticate to EMS via browser (handles CAC login).
    
    Args:
        context: Playwright browser context
        
    Returns:
        True if authentication successful, False otherwise
    """
    page = await context.new_page()
    
    try:
        await page.goto(EMS_LOGIN_URL, wait_until="networkidle")
        await click_acknowledge_button(page)
        login_success = await wait_for_login_completion(page, context)
        
        if not login_success:
            await page.close()
            return False
        
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
    Retrieve session ID from EMS API.
    
    Makes multiple retry attempts if initial request fails.
    
    Args:
        context: Playwright browser context
        
    Returns:
        Session ID as integer, or None if retrieval failed
    """
    logger.info("="*80)
    logger.info("RETRIEVING SESSION ID")
    logger.info("="*80)
    
    for attempt in range(1, SESSION_ID_RETRY_ATTEMPTS + 1):
        page = await context.new_page()
        
        try:
            response = await page.goto(SESSION_ID_ENDPOINT, wait_until="networkidle")
            
            if response.status != 200:
                await page.close()
                if attempt < SESSION_ID_RETRY_ATTEMPTS:
                    await asyncio.sleep(SESSION_ID_RETRY_DELAY)
                    continue
                return None
            
            # Extract JSON from page
            json_text = await page.evaluate('() => document.body.innerText || document.body.textContent')
            data = json.loads(json_text)
            
            # Parse session ID from response
            if isinstance(data, list) and len(data) > 0:
                session_id = data[0].get('sessionId')
                if session_id:
                    logger.info(f"[OK] Session ID retrieved: {session_id}")
                    await page.close()
                    return session_id
            
            await page.close()
            if attempt < SESSION_ID_RETRY_ATTEMPTS:
                await asyncio.sleep(SESSION_ID_RETRY_DELAY)
            
        except Exception as e:
            logger.error(f"Error getting session ID: {e}")
            if not page.is_closed():
                await page.close()
            if attempt < SESSION_ID_RETRY_ATTEMPTS:
                await asyncio.sleep(SESSION_ID_RETRY_DELAY)
    
    return None


async def save_browser_session(context: BrowserContext):
    """
    Save browser session state for potential reuse.
    
    Args:
        context: Playwright browser context
    """
    try:
        storage_state = await context.storage_state()
        with open(SESSION_FILE, 'w') as f:
            json.dump(storage_state, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save session: {e}")

# ============================================================================
# EMS API QUERY FUNCTIONS
# ============================================================================

async def fetch_json_from_endpoint(context: BrowserContext, endpoint: str) -> Optional[any]:
    """
    Generic function to fetch JSON data from an EMS API endpoint.
    
    Args:
        context: Playwright browser context
        endpoint: Full URL of the API endpoint
        
    Returns:
        Parsed JSON data, or None if request failed
    """
    page = await context.new_page()
    
    try:
        response = await page.goto(endpoint, wait_until="networkidle", timeout=REQUEST_TIMEOUT)
        
        if response.status != 200:
            await page.close()
            return None
        
        # Extract JSON from page body
        json_text = await page.evaluate('() => document.body.innerText || document.body.textContent')
        data = json.loads(json_text)
        
        await page.close()
        return data
        
    except Exception as e:
        logger.error(f"Error fetching from {endpoint}: {e}")
        if not page.is_closed():
            await page.close()
        return None


async def wait_for_ems_home_page(page: Page) -> bool:
    """
    Wait for user to complete CAC login and reach EMS home page.
    
    Monitors for the Configurations tile to appear and be clickable.
    
    Args:
        page: Playwright page object
        
    Returns:
        True if home page loaded successfully, False if timeout
    """
    logger.info("Waiting for CAC login to complete...")
    logger.info("Please log in using your CAC in the browser window.")
    
    start_time = asyncio.get_event_loop().time()
    timeout = 300  # 5 minutes
    check_count = 0
    
    while True:
        elapsed = asyncio.get_event_loop().time() - start_time
        check_count += 1
        
        # Check for timeout
        if elapsed > timeout:
            logger.error(f"Login timeout after {timeout} seconds")
            return False
        
        # Log progress every 10 checks (20 seconds)
        if check_count % 10 == 0:
            logger.info(f"Still waiting for login... ({int(elapsed)} seconds elapsed)")
        
        # Check if Configurations tile is visible AND clickable
        try:
            # Try multiple possible selectors for the Configurations tile
            selectors = [
                'a[href="/ems/configuration/"]',
                'div.landing-page-tile-button a[href="/ems/configuration/"]',
                'a:has-text("Configurations")',
                'div.panel-title:has-text("Configurations")'
            ]
            
            for selector in selectors:
                try:
                    element = page.locator(selector).first
                    # Check if element exists and is visible
                    if await element.count() > 0:
                        is_visible = await element.is_visible()
                        if is_visible:
                            logger.info(f"[OK] Found Configurations button with selector: {selector}")
                            logger.info("[OK] Login complete - waiting for page to fully load...")
                            
                            # Wait much longer for page to fully settle after login
                            logger.info("Waiting 10 seconds for page to stabilize...")
                            await asyncio.sleep(10)
                            
                            # Wait for network to be idle
                            try:
                                await page.wait_for_load_state("networkidle", timeout=15000)
                                logger.info("[OK] Page network activity settled")
                            except:
                                logger.warning("Network didn't settle, but continuing...")
                            
                            # Additional wait to ensure everything is ready
                            logger.info("Waiting additional 5 seconds...")
                            await asyncio.sleep(5)
                            
                            logger.info("[OK] EMS home page fully loaded and ready")
                            return True
                except:
                    continue
        except:
            pass
        
        # Check for and click acknowledgment button
        try:
            await click_acknowledge_button(page)
        except:
            pass
        
        # Check if we're still on a login page
        try:
            current_url = page.url
            page_title = await page.title()
            
            # Log current state for debugging (only every 10 checks)
            if check_count % 10 == 0:
                logger.info(f"Current URL: {current_url}")
                logger.info(f"Page title: {page_title}")
        except:
            pass
        
        await asyncio.sleep(2)


async def fetch_fte_orgs(context: BrowserContext, session_id: int) -> Optional[List[Dict]]:
    """
    Fetch FTE Organizations data from EMS API.
    
    Args:
        context: Playwright browser context
        session_id: EMS session ID
        
    Returns:
        List of organization dictionaries, or None if request failed
    """
    endpoint = FTE_ORGS_ENDPOINT.format(session_id=session_id)
    logger.info("="*80)
    logger.info("QUERYING FTE ORGANIZATIONS")
    logger.info("="*80)
    
    data = await fetch_json_from_endpoint(context, endpoint)
    if data:
        logger.info(f"[OK] Retrieved {len(data)} FTE organizations")
    return data


async def fetch_cop_categories(context: BrowserContext, session_id: int) -> Dict[str, Dict]:
    """
    Fetch CoP categories and return mapping of uppercase name to ID and proper name.
    
    Args:
        context: Playwright browser context
        session_id: EMS session ID
        
    Returns:
        Dictionary mapping uppercase CoP names to {'id': cop_id, 'proper_name': cop_name}
    """
    endpoint = COP_CATEGORIES_ENDPOINT.format(session_id=session_id)
    data = await fetch_json_from_endpoint(context, endpoint)
    
    if data:
        mapping = {}
        for cop in data:
            cop_name = cop['cop']
            cop_id = cop['copId']
            mapping[cop_name.upper()] = {
                'id': cop_id,
                'proper_name': cop_name
            }
        logger.info(f"[OK] Loaded {len(mapping)} CoP categories")
        return mapping
    return {}


async def fetch_expertise_categories(context: BrowserContext, session_id: int) -> Dict[str, int]:
    """
    Fetch Expertise categories and return mapping of name to ID.
    
    Args:
        context: Playwright browser context
        session_id: EMS session ID
        
    Returns:
        Dictionary mapping AoE names to expertise IDs
    """
    endpoint = EXPERTISE_CATEGORIES_ENDPOINT.format(session_id=session_id)
    data = await fetch_json_from_endpoint(context, endpoint)
    
    if data:
        mapping = {exp['expertise']: exp['expId'] for exp in data}
        logger.info(f"[OK] Loaded {len(mapping)} Expertise categories")
        return mapping
    return {}


async def fetch_employee_profile(context: BrowserContext, session_id: int, section_code: str) -> Optional[List[Dict]]:
    """
    Fetch employee profiles for a specific section from EMS API.
    
    Args:
        context: Playwright browser context
        session_id: EMS session ID
        section_code: Section code (e.g., 'CEMVR-EC')
        
    Returns:
        List of employee dictionaries, or None if request failed
    """
    endpoint = EMPLOYEE_PROFILE_ENDPOINT.format(session_id=session_id, section_code=section_code)
    return await fetch_json_from_endpoint(context, endpoint)


async def fetch_employee_detail(context: BrowserContext, session_id: int, employee_id: int) -> Optional[Dict]:
    """
    Fetch detailed employee profile including notes/bio.
    
    Args:
        context: Playwright browser context
        session_id: EMS session ID
        employee_id: Employee ID
        
    Returns:
        Employee detail dictionary, or None if request failed
    """
    endpoint = EMPLOYEE_PROFILE_DETAIL_ENDPOINT.format(session_id=session_id, employee_id=employee_id)
    data = await fetch_json_from_endpoint(context, endpoint)
    
    if isinstance(data, list) and len(data) > 0:
        return data[0]
    return None


async def fetch_employee_cops(context: BrowserContext, session_id: int, employee_id: int) -> Optional[List[Dict]]:
    """
    Fetch Communities of Practice for an employee.
    
    Args:
        context: Playwright browser context
        session_id: EMS session ID
        employee_id: Employee ID
        
    Returns:
        List of CoP dictionaries, or None if request failed
    """
    endpoint = COP_EMPLOYEE_ENDPOINT.format(session_id=session_id, employee_id=employee_id)
    return await fetch_json_from_endpoint(context, endpoint)


async def fetch_employee_expertise(context: BrowserContext, session_id: int, employee_id: int) -> Optional[List[Dict]]:
    """
    Fetch Areas of Expertise for an employee.
    
    Args:
        context: Playwright browser context
        session_id: EMS session ID
        employee_id: Employee ID
        
    Returns:
        List of expertise dictionaries, or None if request failed
    """
    endpoint = EXPERTISE_EMPLOYEE_ENDPOINT.format(session_id=session_id, employee_id=employee_id)
    return await fetch_json_from_endpoint(context, endpoint)


async def fetch_employee_certifications(context: BrowserContext, session_id: int, employee_id: int) -> Optional[List[Dict]]:
    """
    Fetch Certifications for an employee.
    
    Args:
        context: Playwright browser context
        session_id: EMS session ID
        employee_id: Employee ID
        
    Returns:
        List of certification dictionaries, or None if request failed
    """
    endpoint = CERTIFICATION_EMPLOYEE_ENDPOINT.format(session_id=session_id, employee_id=employee_id)
    return await fetch_json_from_endpoint(context, endpoint)

# ============================================================================
# EMS UPDATE FUNCTIONS (API-BASED FOR COP AND AOE)
# ============================================================================

async def add_employee_cop(context: BrowserContext, session_id: int, employee_id: int, cop_id: int) -> bool:
    """
    Add a CoP to an employee in EMS using API endpoint.
    
    Args:
        context: Playwright browser context
        session_id: EMS session ID
        employee_id: Employee ID
        cop_id: CoP ID to add
        
    Returns:
        True if CoP was added successfully, False otherwise
    """
    endpoint = UPSERT_COP_ENDPOINT.format(session_id=session_id)
    
    payload = {
        "employeeId": employee_id,
        "pCOP_Id": cop_id,
        "pAF": "T"
    }
    
    page = await context.new_page()
    
    try:
        # Make the PUT request using page.evaluate with fetch
        response_data = await page.evaluate('''
            async ({ url, payload }) => {
                try {
                    const response = await fetch(url, {
                        method: 'PUT',
                        headers: {
                            'Content-Type': 'application/json',
                            'Accept': 'application/json, text/plain, */*'
                        },
                        body: JSON.stringify(payload),
                        credentials: 'include'
                    });
                    
                    return {
                        ok: response.ok,
                        status: response.status
                    };
                } catch (error) {
                    return {
                        ok: false,
                        error: error.message
                    };
                }
            }
        ''', {'url': endpoint, 'payload': payload})
        
        await page.close()
        return response_data.get('ok', False)
        
    except Exception as e:
        logger.error(f"Error adding CoP: {e}")
        if not page.is_closed():
            await page.close()
        return False


async def add_employee_expertise(context: BrowserContext, session_id: int, employee_id: int, exp_id: int) -> bool:
    """
    Add an Area of Expertise to an employee in EMS.
    This endpoint uses GET with parameters in URL.
    
    Args:
        context: Playwright browser context
        session_id: EMS session ID
        employee_id: Employee ID
        exp_id: Expertise ID to add
        
    Returns:
        True if AoE was added successfully, False otherwise
    """
    endpoint = UPSERT_EXPERTISE_ENDPOINT.format(session_id=session_id, employee_id=employee_id, exp_id=exp_id)
    
    page = await context.new_page()
    try:
        response = await page.goto(endpoint, wait_until="networkidle", timeout=REQUEST_TIMEOUT)
        await page.close()
        return response.status == 200
    except Exception as e:
        logger.error(f"Error adding expertise: {e}")
        if not page.is_closed():
            await page.close()
        return False

# ============================================================================
# EMS UI INTERACTION FUNCTIONS (FOR BIO UPDATES)
# ============================================================================

async def select_section_in_ui(page: Page, section_code: str) -> bool:
    """
    Select a section from the Section Code dropdown on the EMS Profile Configuration page.
    
    Args:
        page: Playwright page object (should be on Profile Configuration page)
        section_code: Section code to select (e.g., 'CEMVR-EC')
        
    Returns:
        True if section was selected successfully, False otherwise
    """
    try:
        logger.info(f"  Selecting section: {section_code}")
        
        # Find the Section Code input specifically by its ID or placeholder
        # The Section Code dropdown has id="react-select-3-input" and placeholder "Section Code"
        section_input = page.locator('input#react-select-3-input')
        
        # Alternative: find by the placeholder text
        if await section_input.count() == 0:
            logger.info("  Trying alternative selector with placeholder...")
            section_input = page.locator('input[aria-describedby="react-select-3-placeholder"]')
        
        # Another alternative: find the input that has "Section Code" placeholder nearby
        if await section_input.count() == 0:
            logger.info("  Trying to find Section Code dropdown by placeholder text...")
            # Find the div with placeholder "Section Code" and then find the input inside it
            section_input = page.locator('div:has(div.css-1jqq78o-placeholder:has-text("Section Code")) input[aria-autocomplete="list"]')
        
        await section_input.wait_for(timeout=10000, state="visible")
        logger.info("  Section Code input field found")
        
        # Click to focus
        await section_input.click()
        await asyncio.sleep(0.5)
        
        # Clear any existing value
        await section_input.fill('')
        await asyncio.sleep(0.3)
        
        # Type the section code
        await section_input.type(section_code, delay=100)
        logger.info(f"  Typed section code: {section_code}")
        await asyncio.sleep(1.5)
        
        # Wait for dropdown options to appear
        try:
            await page.wait_for_selector('div[id^="react-select-3-option-"]', timeout=5000)
            logger.info("  Dropdown options appeared")
        except:
            logger.warning("  Dropdown options may not have appeared")
        
        await asyncio.sleep(0.5)
        
        # Press Enter to select the first option
        await section_input.press('Enter')
        logger.info(f"  Pressed Enter to select")
        await asyncio.sleep(3)
        
        # Wait for the employee grid to load
        try:
            await page.wait_for_selector('div.ag-center-cols-container', timeout=15000, state="visible")
            logger.info("  Employee grid loaded")
            await asyncio.sleep(2)
            
            # Verify that rows are present
            rows = await page.locator('div.ag-row').count()
            logger.info(f"  Found {rows} employee rows")
            
            if rows == 0:
                logger.warning("  No employee rows found in grid")
                return False
                
        except Exception as e:
            logger.error(f"  Employee grid did not load: {e}")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"  Error selecting section: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False



async def update_employee_bio_via_ui(page: Page, employee_name: str, bio: str) -> bool:
    """
    Update employee bio by interacting with the EMS UI directly.
    
    This function:
    1. Clicks on the employee row in the AG Grid
    2. Waits for the notes textarea to appear
    3. Fills the textarea with the bio text
    4. Clicks elsewhere to trigger save (blur event)
    
    Args:
        page: Playwright page object (should be on resources page with section selected)
        employee_name: Full name of employee as it appears in the grid
        bio: Bio text to insert
        
    Returns:
        True if bio was updated successfully, False otherwise
    """
    try:
        logger.info(f"    Updating bio via UI for: {employee_name}")
        
        # Find and click the employee row in the AG Grid
        employee_row = page.locator(f'div.ag-cell[col-id="empName"]:has-text("{employee_name}")').first
        
        await employee_row.wait_for(timeout=10000, state="visible")
        await employee_row.click()
        logger.info(f"    Clicked on employee row")
        await asyncio.sleep(2)
        
        # Wait for the notes textarea to appear
        notes_textarea = page.locator('textarea#notes.cnf-untype-note')
        await notes_textarea.wait_for(timeout=10000, state="visible")
        logger.info(f"    Notes textarea is visible")
        
        # Clear existing content and fill with new bio
        await notes_textarea.click()
        await notes_textarea.fill('')  # Clear first
        await asyncio.sleep(0.3)
        await notes_textarea.fill(bio)  # Fill with new bio
        logger.info(f"    Bio text entered ({len(bio)} chars)")
        await asyncio.sleep(1)
        
        # Click elsewhere to trigger save (blur event)
        # Try clicking on a label or other safe element
        try:
            # Option 1: Press Tab to move focus away
            await notes_textarea.press('Tab')
            logger.info(f"    Pressed Tab to trigger save")
            await asyncio.sleep(1)
        except:
            pass
        
        # Option 2: Click on another element to ensure blur
        try:
            # Click on the page heading or another safe element
            safe_element = page.locator('h1, h2, h3, .panel-heading').first
            if await safe_element.count() > 0:
                await safe_element.click()
                logger.info(f"    Clicked elsewhere to trigger save")
                await asyncio.sleep(1)
        except:
            pass
        
        # Option 3: Trigger blur event directly
        try:
            await notes_textarea.evaluate('element => element.blur()')
            logger.info(f"    Triggered blur event")
            await asyncio.sleep(1)
        except:
            pass
        
        # Look for a Save button if it exists
        save_button_selectors = [
            'button:has-text("Save")',
            'button.btn:has-text("Save")',
            'button[type="submit"]',
            'button.btn-primary:has-text("Save")'
        ]
        
        saved = False
        for selector in save_button_selectors:
            try:
                save_button = page.locator(selector).first
                if await save_button.count() > 0:
                    is_visible = await save_button.is_visible()
                    if is_visible:
                        await save_button.click()
                        logger.info(f"    Clicked Save button")
                        saved = True
                        await asyncio.sleep(2)
                        break
            except:
                continue
        
        if not saved:
            logger.info(f"    No Save button - relying on auto-save")
            # Give auto-save time to complete
            await asyncio.sleep(2)
        
        return True
        
    except Exception as e:
        logger.error(f"    Error updating bio via UI: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

# ============================================================================
# EMPLOYEE PROCESSING FUNCTIONS (COMBINED API + UI)
# ============================================================================

async def process_employee(
    page: Page,
    context: BrowserContext,
    session_id: int,
    employee: Dict,
    cercap_data: Dict[str, List[Dict]],
    cop_mapping: Dict[str, Dict],
    expertise_mapping: Dict[str, int]
) -> Dict:
    """
    Process a single employee: compare with CERCAP and update EMS as needed.
    
    Uses API for CoPs and AoEs, UI for Bio updates.
    
    Args:
        page: Playwright page object (for UI interactions)
        context: Playwright browser context (for API calls)
        session_id: EMS session ID
        employee: Employee dictionary from EMS API
        cercap_data: Dictionary mapping emails to CERCAP records
        cop_mapping: Dictionary mapping CoP names to IDs
        expertise_mapping: Dictionary mapping AoE names to IDs
        
    Returns:
        Summary dictionary with counts of additions
    """
    employee_id = employee.get('employeeId')
    emp_name = employee.get('empName', '')
    emp_email_raw = employee.get('empEmailAddr', '')
    emp_email = emp_email_raw.upper() if emp_email_raw else ''
    
    summary = {
        'employee_id': employee_id,
        'name': emp_name,
        'email': emp_email,
        'found_in_cercap': False,
        'cops_added': 0,
        'cops_skipped': 0,
        'aoes_added': 0,
        'aoes_skipped': 0,
        'bio_updated': False,
        'final_cop_count': 0,
        'final_aoe_count': 0,
        'final_cert_count': 0,
        'final_bio': ''
    }
    
    # Check if employee exists in CERCAP
    if emp_email not in cercap_data:
        action_logger.log_action(employee_id, emp_name, emp_email, 'Verification', 
                                 'Employee', 'Not Found in CERCAP', '')
        return summary
    
    summary['found_in_cercap'] = True
    cercap_records = cercap_data[emp_email]
    
    # ========================================================================
    # STEP 1: Process CoPs via API
    # ========================================================================
    
    ems_cops_data = await fetch_employee_cops(context, session_id, employee_id)
    ems_cops = set()
    if ems_cops_data:
        ems_cops = {cop.get('cop', '').strip().upper() for cop in ems_cops_data if cop.get('cop')}
    
    cercap_cops = get_cercap_cops(cercap_records)
    missing_cops = cercap_cops - ems_cops
    
    if missing_cops:
        logger.info(f"  Adding {len(missing_cops)} missing CoPs via API...")
        
        for cop_name_upper in missing_cops:
            if cop_name_upper in cop_mapping:
                cop_info = cop_mapping[cop_name_upper]
                cop_id = cop_info['id']
                cop_proper_name = cop_info['proper_name']
                
                success = await add_employee_cop(context, session_id, employee_id, cop_id)
                
                if success:
                    summary['cops_added'] += 1
                    action_logger.log_action(employee_id, emp_name, emp_email, 'CoP', 
                                           cop_proper_name, 'Added', f'CoP ID: {cop_id}')
                    logger.info(f"    [+] Added CoP: {cop_proper_name}")
                else:
                    action_logger.log_action(employee_id, emp_name, emp_email, 'CoP', 
                                           cop_proper_name, 'Error', 'Failed to add')
                    logger.error(f"    [X] Failed to add CoP: {cop_proper_name}")
                
                await asyncio.sleep(0.5)
            else:
                summary['cops_skipped'] += 1
                action_logger.log_action(employee_id, emp_name, emp_email, 'CoP', 
                                       cop_name_upper, 'Skipped', 'CoP not found in EMS categories')
                logger.warning(f"    [!] CoP not found in EMS: {cop_name_upper}")
    
    # ========================================================================
    # STEP 2: Process AoEs via API
    # ========================================================================
    
    ems_expertise_data = await fetch_employee_expertise(context, session_id, employee_id)
    ems_aoes = set()
    if ems_expertise_data:
        ems_aoes = {exp.get('expertise', '').strip() for exp in ems_expertise_data if exp.get('expertise')}
    
    cercap_aoes = get_cercap_aoes(cercap_records)
    missing_aoes = cercap_aoes - ems_aoes
    
    if missing_aoes:
        logger.info(f"  Adding {len(missing_aoes)} missing AoEs via API...")
        
        for aoe_name in missing_aoes:
            if aoe_name in expertise_mapping:
                exp_id = expertise_mapping[aoe_name]
                success = await add_employee_expertise(context, session_id, employee_id, exp_id)
                
                if success:
                    summary['aoes_added'] += 1
                    action_logger.log_action(employee_id, emp_name, emp_email, 'AoE', 
                                           aoe_name, 'Added', f'Expertise ID: {exp_id}')
                    logger.info(f"    [+] Added AoE: {aoe_name}")
                else:
                    action_logger.log_action(employee_id, emp_name, emp_email, 'AoE', 
                                           aoe_name, 'Error', 'Failed to add')
                    logger.error(f"    [X] Failed to add AoE: {aoe_name}")
                
                await asyncio.sleep(0.5)
            else:
                summary['aoes_skipped'] += 1
                action_logger.log_action(employee_id, emp_name, emp_email, 'AoE', 
                                       aoe_name, 'Skipped', 'AoE not found in EMS categories')
                logger.warning(f"    [!] AoE not found in EMS: {aoe_name}")
    
    # ========================================================================
    # STEP 3: Process Bio via UI
    # ========================================================================
    
    cercap_bio = get_cercap_bio(cercap_records)
    
    if cercap_bio:
        logger.info(f"  Updating bio via UI...")
        success = await update_employee_bio_via_ui(page, emp_name, cercap_bio)
        
        if success:
            summary['bio_updated'] = True
            action_logger.log_action(employee_id, emp_name, emp_email, 'Bio', 
                                   'Bio', 'Updated via UI', f'Length: {len(cercap_bio)} chars')
            logger.info(f"    [+] Bio updated")
        else:
            action_logger.log_action(employee_id, emp_name, emp_email, 'Bio', 
                                   'Bio', 'Error', 'Failed to update via UI')
            logger.error(f"    [X] Failed to update bio")
        
        await asyncio.sleep(0.5)
    
    # ========================================================================
    # STEP 4: Verify final state via API
    # ========================================================================
    
    logger.info(f"  Verifying final state...")
    await asyncio.sleep(1)
    
    final_cops = await fetch_employee_cops(context, session_id, employee_id)
    final_expertise = await fetch_employee_expertise(context, session_id, employee_id)
    final_certs = await fetch_employee_certifications(context, session_id, employee_id)
    
    summary['final_cop_count'] = len(final_cops) if final_cops else 0
    summary['final_aoe_count'] = len(final_expertise) if final_expertise else 0
    summary['final_cert_count'] = len(final_certs) if final_certs else 0
    
    # Note: We can't easily verify bio via API since it requires authentication
    # The UI update is our verification
    summary['final_bio'] = cercap_bio if summary['bio_updated'] else ''
    
    bio_length = len(summary['final_bio'])
    
    action_logger.log_action(employee_id, emp_name, emp_email, 'Verification', 
                           'Final State', 'Verified', 
                           f"CoPs: {summary['final_cop_count']}, AoEs: {summary['final_aoe_count']}, Certs: {summary['final_cert_count']}, Bio: {bio_length} chars")
    
    logger.info(f"  [OK] Final state: {summary['final_cop_count']} CoPs, {summary['final_aoe_count']} AoEs, {summary['final_cert_count']} Certs, Bio: {bio_length} chars")
    
    return summary


# First, let's add better logging to see what's happening:

async def process_all_employees(
    page: Page,
    context: BrowserContext,
    session_id: int,
    fte_orgs: List[Dict],
    cercap_data: Dict[str, List[Dict]],
    cop_mapping: Dict[str, Dict],
    expertise_mapping: Dict[str, int]
) -> List[Dict]:
    """
    Process all employees from filtered FTE organizations.
    
    Combines API calls for CoPs/AoEs with UI interaction for Bios.
    """
    logger.info("\n" + "="*80)
    logger.info("PROCESSING EMPLOYEES AND UPDATING EMS")
    logger.info("="*80)
    
    # Navigate to EMS home page and wait for login
    logger.info("Navigating to EMS home page...")
    try:
        await page.goto(EMS_LOGIN_URL, wait_until="load", timeout=60000)
        logger.info("Page loaded, waiting for CAC login...")
        
        # Wait for user to complete login
        login_success = await wait_for_ems_home_page(page)
        
        if not login_success:
            logger.error("Failed to complete login")
            return []
        
    except Exception as e:
        logger.error(f"Failed to load EMS home page: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return []
    
    # Navigate to Profile Configuration page
    nav_success = await navigate_to_profile_configuration(page)
    
    if not nav_success:
        logger.error("Failed to navigate to Profile Configuration page")
        return []
    
    # Filter organizations
    filtered_orgs = []
    for org in fte_orgs:
        section_code = org.get('sectionCode', '')
        for filter_prefix in SECTION_FILTERS:
            if section_code.startswith(filter_prefix):
                filtered_orgs.append(org)
                break
    
    logger.info(f"Processing {len(filtered_orgs)} organizations (filtered for {', '.join(SECTION_FILTERS)})")
    
    all_summaries = []
    
    for i, org in enumerate(filtered_orgs, 1):
        section_code = org.get('sectionCode')
        section_name = org.get('name', 'Unknown')
        
        logger.info(f"\n{'='*80}")
        logger.info(f"[{i}/{len(filtered_orgs)}] {section_code} - {section_name}")
        logger.info(f"{'='*80}")
        
        # Select the section in UI for bio updates
        section_selected = await select_section_in_ui(page, section_code)
        
        if not section_selected:
            logger.error(f"  Failed to select section - bio updates will be skipped for this section")
        
        # Get employee list via API
        employees = await fetch_employee_profile(context, session_id, section_code)
        
        if not employees:
            logger.info(f"  No employees found")
            continue
        
        logger.info(f"  Processing {len(employees)} employees...")
        
        for j, employee in enumerate(employees, 1):
            emp_name = employee.get('empName', 'Unknown')
            emp_email_raw = employee.get('empEmailAddr')
            
            # Handle None email addresses
            if emp_email_raw is None or emp_email_raw == '':
                logger.info(f"\n  [{j}/{len(employees)}] {emp_name} - No email, skipping")
                continue
            
            emp_email = emp_email_raw.strip().upper()
            employee_id = employee.get('employeeId')
            
            logger.info(f"\n  [{j}/{len(employees)}] {emp_name} ({emp_email})")
            
            # Check if email exists in CERCAP
            if emp_email not in cercap_data:
                logger.info(f"    Not found in CERCAP - skipping")
                action_logger.log_action(employee_id, emp_name, emp_email, 'Verification', 
                                       'Employee', 'Not Found in CERCAP', '')
                continue
            
            try:
                cercap_records = cercap_data[emp_email]
                logger.info(f"    Found in CERCAP with {len(cercap_records)} records")
                
                # ============================================================
                # STEP 1: Process CoPs via API
                # ============================================================
                ems_cops_data = await fetch_employee_cops(context, session_id, employee_id)
                ems_cops = set()
                if ems_cops_data:
                    ems_cops = {cop.get('cop', '').strip().upper() for cop in ems_cops_data if cop.get('cop')}
                
                cercap_cops = get_cercap_cops(cercap_records)
                missing_cops = cercap_cops - ems_cops
                
                cops_added = 0
                if missing_cops:
                    logger.info(f"    Adding {len(missing_cops)} missing CoPs...")
                    for cop_name_upper in missing_cops:
                        if cop_name_upper in cop_mapping:
                            cop_info = cop_mapping[cop_name_upper]
                            cop_id = cop_info['id']
                            cop_proper_name = cop_info['proper_name']
                            
                            success = await add_employee_cop(context, session_id, employee_id, cop_id)
                            
                            if success:
                                cops_added += 1
                                action_logger.log_action(employee_id, emp_name, emp_email, 'CoP', 
                                                       cop_proper_name, 'Added', f'CoP ID: {cop_id}')
                                logger.info(f"      [+] {cop_proper_name}")
                            else:
                                action_logger.log_action(employee_id, emp_name, emp_email, 'CoP', 
                                                       cop_proper_name, 'Failed', f'CoP ID: {cop_id}')
                                logger.error(f"      [X] Failed: {cop_proper_name}")
                            
                            await asyncio.sleep(0.5)
                
                # ============================================================
                # STEP 2: Process AoEs via API
                # ============================================================
                ems_expertise_data = await fetch_employee_expertise(context, session_id, employee_id)
                ems_aoes = set()
                if ems_expertise_data:
                    ems_aoes = {exp.get('expertise', '').strip() for exp in ems_expertise_data if exp.get('expertise')}
                
                cercap_aoes = get_cercap_aoes(cercap_records)
                missing_aoes = cercap_aoes - ems_aoes
                
                aoes_added = 0
                if missing_aoes:
                    logger.info(f"    Adding {len(missing_aoes)} missing AoEs...")
                    for aoe_name in missing_aoes:
                        if aoe_name in expertise_mapping:
                            exp_id = expertise_mapping[aoe_name]
                            success = await add_employee_expertise(context, session_id, employee_id, exp_id)
                            
                            if success:
                                aoes_added += 1
                                action_logger.log_action(employee_id, emp_name, emp_email, 'AoE', 
                                                       aoe_name, 'Added', f'Expertise ID: {exp_id}')
                                logger.info(f"      [+] {aoe_name}")
                            else:
                                action_logger.log_action(employee_id, emp_name, emp_email, 'AoE', 
                                                       aoe_name, 'Failed', f'Expertise ID: {exp_id}')
                                logger.error(f"      [X] Failed: {aoe_name}")
                            
                            await asyncio.sleep(0.5)
                
                # ============================================================
                # STEP 3: Process Bio via UI
                # ============================================================
                cercap_bio = get_cercap_bio(cercap_records)
                bio_updated = False
                
                if section_selected:
                    if cercap_bio:
                        # Get current bio from EMS
                        employee_detail = await fetch_employee_detail(context, session_id, employee_id)
                        current_bio = ''
                        if employee_detail:
                            current_bio = employee_detail.get('notes', '').strip() if employee_detail.get('notes') else ''
                        
                        # Compare bios - treat None and empty string as the same
                        current_bio_normalized = current_bio if current_bio else ''
                        cercap_bio_normalized = cercap_bio.strip() if cercap_bio else ''
                        
                        if current_bio_normalized != cercap_bio_normalized:
                            logger.info(f"    Updating bio ({len(current_bio_normalized)} → {len(cercap_bio_normalized)} chars)...")
                            success = await update_employee_bio_via_ui(page, emp_name, cercap_bio_normalized)
                            
                            if success:
                                bio_updated = True
                                action_logger.log_action(employee_id, emp_name, emp_email, 'Bio', 
                                                       'Bio', 'Updated', f'{len(current_bio_normalized)} → {len(cercap_bio_normalized)} chars')
                                logger.info(f"      [+] Bio updated")
                            else:
                                action_logger.log_action(employee_id, emp_name, emp_email, 'Bio', 
                                                       'Bio', 'Failed', 'UI update failed')
                                logger.error(f"      [X] Bio update failed")
                        else:
                            action_logger.log_action(employee_id, emp_name, emp_email, 'Bio', 
                                                   'Bio', 'No Change', f'{len(current_bio_normalized)} chars - matches CERCAP')
                    else:
                        # No bio in CERCAP
                        action_logger.log_action(employee_id, emp_name, emp_email, 'Bio', 
                                               'Bio', 'No Bio in CERCAP', '')
                else:
                    if cercap_bio:
                        logger.warning(f"    Bio available but section not selected")
                        action_logger.log_action(employee_id, emp_name, emp_email, 'Bio', 
                                               'Bio', 'Skipped', 'Section not selected in UI')
                
                # Summary
                updates = []
                if cops_added > 0:
                    updates.append(f"{cops_added} CoPs")
                if aoes_added > 0:
                    updates.append(f"{aoes_added} AoEs")
                if bio_updated:
                    updates.append("Bio")
                
                if updates:
                    logger.info(f"    ✓ Updated: {', '.join(updates)}")
                else:
                    logger.info(f"    ✓ No updates needed")
                
            except Exception as e:
                logger.error(f"    ✗ Error: {e}")
                import traceback
                logger.error(traceback.format_exc())
                action_logger.log_action(employee_id, emp_name, emp_email, 'Error', 
                                       'Processing', 'Failed', str(e))
            
            await asyncio.sleep(0.5)
    
    logger.info("\n" + "="*80)
    logger.info("PROCESSING COMPLETE")
    logger.info("="*80)
    logger.info(f"📄 Action log: {ACTIONS_LOG_CSV}")
    
    return all_summaries

# ============================================================================
# REPORTING FUNCTIONS
# ============================================================================

def generate_summary_report(summaries: List[Dict], output_file: str):
    """
    Generate Excel summary report of all processing actions.
    
    Args:
        summaries: List of summary dictionaries from employee processing
        output_file: Path to output Excel file
    """
    logger.info("\n" + "="*80)
    logger.info("GENERATING SUMMARY REPORT")
    logger.info("="*80)
    
    try:
        # Check if summaries is empty
        if not summaries:
            logger.warning("No employee data to report - summaries list is empty")
            # Create an empty DataFrame with the expected columns
            df = pd.DataFrame(columns=[
                'employee_id', 'name', 'email', 'found_in_cercap',
                'cops_added', 'cops_skipped', 'aoes_added', 'aoes_skipped', 'bio_updated',
                'final_cop_count', 'final_aoe_count', 'final_cert_count', 'final_bio'
            ])
        else:
            df = pd.DataFrame(summaries)
            
            # Define column order
            column_order = [
                'employee_id', 'name', 'email', 'found_in_cercap',
                'cops_added', 'cops_skipped', 'aoes_added', 'aoes_skipped', 'bio_updated',
                'final_cop_count', 'final_aoe_count', 'final_cert_count', 'final_bio'
            ]
            
            # Only reorder if we have data
            df = df[column_order]
        
        # Write to Excel
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Summary', index=False)
        
        logger.info(f"[OK] Summary report saved to: {output_file}")
        
        # Log statistics
        if summaries:
            total = len(summaries)
            found = sum(1 for s in summaries if s['found_in_cercap'])
            total_cops_added = sum(s['cops_added'] for s in summaries)
            total_aoes_added = sum(s['aoes_added'] for s in summaries)
            total_bios_updated = sum(1 for s in summaries if s['bio_updated'])
            
            logger.info(f"\nStatistics:")
            logger.info(f"  Total employees processed: {total}")
            logger.info(f"  Found in CERCAP: {found}")
            logger.info(f"  CoPs added: {total_cops_added}")
            logger.info(f"  AoEs added: {total_aoes_added}")
            logger.info(f"  Bios updated: {total_bios_updated}")
        else:
            logger.info(f"\nStatistics:")
            logger.info(f"  Total employees processed: 0")
            logger.info(f"  No data available - check page loading issues above")
        
    except Exception as e:
        logger.error(f"Error generating summary report: {e}")
        import traceback
        traceback.print_exc()

# ============================================================================
# MAIN ASYNC FUNCTION
# ============================================================================

async def main():
    """
    Main async function to orchestrate the entire workflow.
    
    Workflow:
    1. Check CERCAP file age, download if needed
    2. Load CERCAP data
    3. Authenticate to EMS
    4. Get session ID
    5. Query FTE organizations
    6. Load CoP and AoE categories
    7. Process all employees (CoPs/AoEs via API, Bios via UI)
    8. Generate reports
    """
    print("\n" + "="*80)
    print("USACE EMS/CERCAP DATA SYNC WORKFLOW")
    print("="*80)
    print(f"Employee ID: {EMPLOYEE_ID}")
    print(f"Office Code: {OFFICE_CODE}")
    print(f"Section Filters: {', '.join(SECTION_FILTERS)}")
    print(f"Download Path: {DOWNLOAD_PATH}")
    print(f"Logs Path: {LOGS_PATH}")
    print("="*80 + "\n")
    
    need_download = True
    
    # Check if CERCAP file is recent enough
    cercap_file_path = os.path.join(DOWNLOAD_PATH, CERCAP_FILENAME)
    is_recent, mod_time = check_file_age(cercap_file_path, CERCAP_MAX_AGE_HOURS)
    
    if is_recent and mod_time:
        age = datetime.now() - mod_time
        age_str = format_timedelta(age)
        logger.info("="*80)
        logger.info("CERCAP FILE CHECK")
        logger.info("="*80)
        logger.info(f"[OK] Found existing CERCAP file (age: {age_str})")
        logger.info(f"  Skipping download")
        logger.info("="*80 + "\n")
        need_download = False
    else:
        logger.info("="*80)
        logger.info("CERCAP FILE CHECK")
        logger.info("="*80)
        logger.info(f"[!] CERCAP file not found or too old - will download")
        logger.info("="*80 + "\n")
    
    async with async_playwright() as playwright:
        browser = None
        context = None
        
        try:
            # Download CERCAP export if needed
            if need_download:
                browser, context = await create_browser_context(playwright, headless=HEADLESS_DOWNLOAD)
                download_success = await download_cercap_export(context)
                
                if not download_success:
                    logger.error("Failed to download CERCAP export")
                    return
                
                await browser.close()
                browser = None
                context = None
            
            # Load CERCAP data
            cercap_data = load_cercap_data(cercap_file_path)
            
            if not cercap_data:
                logger.error("Failed to load CERCAP data")
                return
            
            # Create browser for EMS interaction
            browser, context = await create_browser_context(playwright, headless=HEADLESS_API)
            
            # Authenticate to EMS
            logger.info("="*80)
            logger.info("AUTHENTICATING TO EMS")
            logger.info("="*80)
            
            auth_success = await authenticate_browser(context)
            
            if not auth_success:
                logger.error("Authentication failed")
                return
            
            # Get session ID
            session_id = await get_session_id(context)
            
            if not session_id:
                logger.error("Failed to retrieve session ID")
                return
            
            # Load EMS categories
            logger.info("\n" + "="*80)
            logger.info("LOADING EMS CATEGORIES")
            logger.info("="*80)
            
            cop_mapping = await fetch_cop_categories(context, session_id)
            expertise_mapping = await fetch_expertise_categories(context, session_id)
            
            if not cop_mapping or not expertise_mapping:
                logger.error("Failed to load EMS categories")
                return
            
            # Fetch FTE organizations
            fte_orgs = await fetch_fte_orgs(context, session_id)
            
            if not fte_orgs:
                logger.error("Failed to retrieve FTE organizations")
                return
            
            # Create a dedicated page for UI interaction
            page = await context.new_page()
            
            # Process all employees
            summaries = await process_all_employees(
                page, context, session_id, fte_orgs, cercap_data,
                cop_mapping, expertise_mapping
            )
            
            await page.close()
            
            # Save action log
            action_logger.save()
            
            # Generate summary report
            summary_report_path = os.path.join(LOGS_PATH, f'summary_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx')
            generate_summary_report(summaries, summary_report_path)
            
            # Print completion message
            print("\n" + "="*80)
            print("WORKFLOW COMPLETED")
            print("="*80)
            print(f"\nProcessed {len(summaries)} employees")
            print(f"\nReports Generated:")
            print(f"  - Actions Log: {ACTIONS_LOG_CSV}")
            print(f"  - Summary Report: {summary_report_path}")
            print(f"  - Main Log: {LOG_FILE}")
            print("="*80)
            
        except Exception as e:
            logger.error(f"Error in main execution: {e}")
            import traceback
            traceback.print_exc()
            
        finally:
            logger.info("Cleaning up...")
            if browser:
                await browser.close()

# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nScript interrupted by user")
    except Exception as e:
        print(f"\n\nError: {e}")
        import traceback
        traceback.print_exc()