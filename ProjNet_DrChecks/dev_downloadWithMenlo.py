"""
================================================================================
ProjNet Data Extraction Script - MULTI-TAB VERSION
================================================================================
Uses threading with single browser session (multiple tabs)
================================================================================
"""

import os
import json
import sys
import csv
import base64
import platform
import subprocess
from pathlib import Path
from getpass import getpass
from datetime import datetime
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
import threading
import warnings

# Suppress openpyxl warning about default styles
warnings.filterwarnings('ignore', category=UserWarning, module='openpyxl')

# Third-party imports
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import pandas as pd

# Cryptography imports
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

# Load configuration
config_path = "C:/Workspace/GIT/USACE-AIS-Scripts/config.json"

with open(config_path, 'r') as f:
    config = json.load(f)

# Add the A_MODULES directory to system path
MODULES_PATH = config['modules_path']
if MODULES_PATH not in sys.path:
    sys.path.insert(0, MODULES_PATH)

from SharePointUpload import upload_to_sharepoint

# ============================================================================
# CONFIGURATION
# ============================================================================

# Define working directory and file paths
WORKING_DIR = r"C:\Workspace\GIT\USACE-AIS-Scripts\ProjNet_DrChecks"
CREDS_FILE = os.path.join(WORKING_DIR, ".credentials.enc")
KEY_FILE = os.path.join(WORKING_DIR, ".key.enc")
DOWNLOAD_FOLDER = os.path.join(WORKING_DIR, "downloads")
COMMENTS_FOLDER = os.path.join(WORKING_DIR, "comments")
LOGS_FOLDER = os.path.join(WORKING_DIR, "logs")

# ProjNet URLs
LOGIN_URL = "https://www.projnet.org/projnet/binKornHome/index.cfm"
ALL_PROJECTS_REPORT_URL = "https://www.projnet.org/report/AllProjectsReviewsReport.cfm?Site=1107"
ALL_PROJECTS_LIST_URL = "https://www.projnet.org/report/AllProjectsReport.cfm?Site=1107"
SITE_ADMIN_REPORT_URL = "https://www.projnet.org/projnet/binKornHome/index.cfm?strKornCob=PNetSiteAdminReport"
ALL_COMMENTS_REPORT_URL = "https://www.projnet.org/projnet/binKornHome/index.cfm?strKornCob=SiteAdminAllCommentsReport"

# Site configuration
SITE_OFFICE_VALUE = "1107"
SITE_OFFICE_NAME = "MVR Rock Island District"

# Performance configuration
MAX_PARALLEL_TABS = 1  # Number of parallel tabs in same browser
DOWNLOAD_TIMEOUT = 180000  # 180 seconds (3 minutes) for downloads
PAGE_LOAD_TIMEOUT = 120000  # 120 seconds (2 minutes) for page loads
TAB_STARTUP_DELAY = 2  # 2 seconds between starting each tab
INTER_REQUEST_DELAY = 1  # 1 second between requests within a tab
AVG_SECONDS_PER_PROJECT = 3  # Average time to download one project (for estimates)
MAX_RETRIES = 1  # Maximum number of retry attempts for failed downloads
RETRY_DELAY = 5  # Seconds to wait between retries


# Output configuration
VERBOSE_OUTPUT = True  # Set to True to see every project download
PROGRESS_INTERVAL = 10  # Show progress every N projects (when VERBOSE_OUTPUT is False)

# Browser display configuration
HEADLESS_INITIAL_DOWNLOADS = False  # Set to False to see browser for initial downloads
HEADLESS_COMMENTS_DOWNLOAD = False  # Set to False to see browser for comment downloads

# Testing configuration
# True = skip Phase 1 and use files already present in the downloads folder.
# Phase 2 requires downloads/ALL_PROJECTS.csv to already exist.
SKIP_INITIAL_DOWNLOADS = True

# Date filtering configuration
YEARS_TO_INCLUDE = 10  # Number of years to look back for projects

# SharePoint configuration
SHAREPOINT_URL = config['sharepoint_base_url']
SHAREPOINT_LIBRARY_PATH = "/sites/TDL-CEMVR-EMSUsers/Shared%20Documents/DATASETS/PROJNET_DRCHECKS"
EMAIL_ADDRESS = config['sharepoint_username']

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def timestamp():
    """Get current timestamp string for logging."""
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def log(message, force=False):
    """Print message with timestamp."""
    if force or VERBOSE_OUTPUT:
        print(f"[{timestamp()}] {message}")

def format_time_estimate(seconds):
    """Format seconds into human-readable time estimate."""
    if seconds < 60:
        return f"{seconds:.0f} seconds"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f} minutes"
    else:
        hours = seconds / 3600
        return f"{hours:.1f} hours"

def format_elapsed_time(seconds):
    """Format elapsed time into human-readable format."""
    if seconds < 60:
        return f"{seconds:.1f} seconds"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f} minutes ({seconds:.0f} seconds)"
    else:
        hours = seconds / 3600
        minutes = (seconds % 3600) / 60
        return f"{hours:.1f} hours ({minutes:.0f} minutes)"

# ============================================================================
# ENCRYPTION UTILITIES
# ============================================================================

def get_machine_id():
    """Get a unique identifier for this machine."""
    try:
        if platform.system() == "Windows":
            try:
                result = subprocess.check_output(
                    ['powershell', '-Command', '(Get-CimInstance -Class Win32_ComputerSystemProduct).UUID'],
                    shell=True,
                    stderr=subprocess.DEVNULL
                ).decode().strip()
                machine_id = result
            except:
                try:
                    result = subprocess.check_output(
                        'wmic csproduct get uuid',
                        shell=True,
                        stderr=subprocess.DEVNULL
                    ).decode()
                    lines = [line.strip() for line in result.split('\n') if line.strip()]
                    machine_id = lines[1] if len(lines) > 1 else lines[0]
                except:
                    machine_id = f"{platform.node()}-{os.getenv('COMPUTERNAME', 'unknown')}"
        elif platform.system() == "Linux":
            with open('/etc/machine-id', 'r') as f:
                machine_id = f.read().strip()
        elif platform.system() == "Darwin":
            result = subprocess.check_output(
                ['ioreg', '-rd1', '-c', 'IOPlatformExpertDevice']
            ).decode()
            for line in result.split('\n'):
                if 'IOPlatformUUID' in line:
                    machine_id = line.split('"')[3]
                    break
        else:
            machine_id = f"{platform.node()}-{os.getlogin()}"
    except Exception:
        try:
            machine_id = f"{platform.node()}-{platform.system()}-{os.getlogin()}"
        except:
            machine_id = f"{platform.node()}-{platform.system()}-default"
    
    return machine_id

def generate_key():
    """Generate an encryption key based on machine-specific information."""
    machine_id = get_machine_id()
    salt = b'projnet_ryan_benac_2026'
    
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
        backend=default_backend()
    )
    
    key = base64.urlsafe_b64encode(kdf.derive(machine_id.encode()))
    return key

def encrypt_data(data):
    """Encrypt data using Fernet symmetric encryption."""
    key = generate_key()
    fernet = Fernet(key)
    encrypted = fernet.encrypt(data.encode())
    return encrypted

def decrypt_data(encrypted_data):
    """Decrypt data using Fernet symmetric encryption."""
    key = generate_key()
    fernet = Fernet(key)
    try:
        decrypted = fernet.decrypt(encrypted_data)
        return decrypted.decode()
    except Exception:
        raise Exception(
            "Failed to decrypt credentials. This file may have been created "
            "on a different machine or the file is corrupted."
        )

def get_credentials():
    """Retrieve encrypted credentials from file or prompt user to create them."""
    if os.path.exists(CREDS_FILE):
        log("✓ Loading existing credentials...", force=True)
        try:
            with open(CREDS_FILE, 'rb') as f:
                encrypted_data = f.read()
            
            decrypted_json = decrypt_data(encrypted_data)
            creds = json.loads(decrypted_json)
            
            log("✓ Credentials decrypted successfully", force=True)
            return creds['username'], creds['password']
            
        except Exception as e:
            log(f"✗ Error loading credentials: {e}", force=True)
            log("You will need to re-enter your credentials.", force=True)
            os.remove(CREDS_FILE)
            return get_credentials()
    else:
        print("=" * 80)
        print("FIRST TIME SETUP - CREDENTIALS REQUIRED")
        print("=" * 80)
        print("No credentials file found. Please enter your ProjNet credentials.")
        print("These will be encrypted and stored securely for future use.\n")
        
        username = input("Username (email): ")
        password = getpass("Password (hidden): ")
        
        creds_json = json.dumps({
            'username': username,
            'password': password
        })
        
        encrypted_data = encrypt_data(creds_json)
        
        with open(CREDS_FILE, 'wb') as f:
            f.write(encrypted_data)
        
        try:
            os.chmod(CREDS_FILE, 0o600)
        except Exception as e:
            log(f"Warning: Could not set file permissions: {e}", force=True)
        
        log(f"✓ Credentials encrypted and saved to {CREDS_FILE}", force=True)
        log("✓ Credentials can only be decrypted on this machine", force=True)
        print("=" * 80 + "\n")
        
        return username, password

def reset_credentials():
    """Delete stored credentials and prompt for new ones."""
    if os.path.exists(CREDS_FILE):
        os.remove(CREDS_FILE)
        log("✓ Existing credentials deleted", force=True)
    return get_credentials()

# ============================================================================
# FILE CONVERSION UTILITIES
# ============================================================================

def convert_xlsx_to_csv(xlsx_path, csv_path):
    """Convert an Excel file to CSV format and delete the original Excel file."""
    try:
        df = pd.read_excel(xlsx_path, engine='openpyxl')
        df.to_csv(csv_path, index=False, encoding='utf-8')
        os.remove(xlsx_path)
        return True
    except Exception as e:
        log(f"✗ Error converting Excel to CSV: {e}", force=True)
        return False

# ============================================================================
# DATE UTILITIES
# ============================================================================

def parse_date(date_str):
    """Parse a date string to datetime object."""
    if pd.isna(date_str) or date_str == '' or date_str is None:
        return None
    try:
        return pd.to_datetime(date_str)
    except:
        return None

def get_latest_date(design_end, construction_end):
    """Get the later of two dates."""
    design_date = parse_date(design_end)
    construction_date = parse_date(construction_end)
    
    if design_date is None and construction_date is None:
        return None
    elif design_date is None:
        return construction_date
    elif construction_date is None:
        return design_date
    else:
        return max(design_date, construction_date)

def should_download_comments(pkey_project, latest_date):
    """Determine if comments should be downloaded for a project."""
    csv_path = os.path.join(COMMENTS_FOLDER, f"{pkey_project}.csv")
    file_exists = os.path.exists(csv_path)
    today = datetime.now()
    cutoff_date = today - pd.DateOffset(years=YEARS_TO_INCLUDE)
    
    if latest_date is None:
        return (True, "No valid end date")
    
    if isinstance(latest_date, str):
        latest_date = parse_date(latest_date)
    
    if latest_date.tzinfo is not None:
        latest_date = latest_date.replace(tzinfo=None)
    
    if latest_date >= cutoff_date:
        if file_exists:
            return (True, f"Within {YEARS_TO_INCLUDE} years - updating existing file")
        else:
            return (True, f"Within {YEARS_TO_INCLUDE} years - new download")
    else:
        if file_exists:
            return (False, f"Older than {YEARS_TO_INCLUDE} years - file exists, skipping")
        else:
            return (True, f"Older than {YEARS_TO_INCLUDE} years - file missing, downloading")

# ============================================================================
# PROGRESS TRACKER
# ============================================================================

class ProgressTracker:
    """Thread-safe progress tracker for async downloads."""
    def __init__(self, total, start_time):
        self.total = total
        self.completed = 0
        self.successful = 0
        self.failed = 0
        self.start_time = start_time
        self.lock = threading.Lock()
    
    def increment(self, success=True):
        """Increment completed count and return progress info."""
        with self.lock:
            self.completed += 1
            if success:
                self.successful += 1
            else:
                self.failed += 1
            
            elapsed = (datetime.now() - self.start_time).total_seconds()
            
            if self.completed > 0:
                avg_time = elapsed / self.completed
                remaining = self.total - self.completed
                eta_seconds = remaining * avg_time
                
                return {
                    'completed': self.completed,
                    'successful': self.successful,
                    'failed': self.failed,
                    'total': self.total,
                    'elapsed': elapsed,
                    'eta_seconds': eta_seconds,
                    'avg_time': avg_time
                }
            else:
                return {
                    'completed': self.completed,
                    'successful': self.successful,
                    'failed': self.failed,
                    'total': self.total,
                    'elapsed': elapsed,
                    'eta_seconds': 0,
                    'avg_time': 0
                }

# ============================================================================
# ASYNC WORKER FUNCTION FOR MULTI-TAB DOWNLOADS WITH RETRY
# ============================================================================

import urllib.parse

def normalize_comments_download_url(raw_href):
    """
    ProjNet may generate a relative download href that browsers resolve under
    /projnet/binKornHome/. The actual download handler is under /binReport/.
    """
    if not raw_href:
        raise ValueError("Generated report link did not contain an href.")

    parsed = urllib.parse.urlsplit(raw_href)

    if not parsed.query:
        raise ValueError(
            f"Generated report link did not contain query parameters: {raw_href}"
        )

    query_values = urllib.parse.parse_qs(parsed.query)

    if "file" not in query_values:
        raise ValueError(
            f"Generated report link did not contain a file parameter: {raw_href}"
        )

    # Keep the exact query string ProjNet generated, but force the correct
    # ProjNet report-download path.
    return urllib.parse.urlunsplit((
        "https",
        "www.projnet.org",
        "/projnet/binReport/ATO_Reports/downloadReport.cfm",
        parsed.query,
        ""
    ))

async def fetch_report_bytes(page, report_link, download_url, pkey_project):
    """Fetch the report directly, falling back to Menlo's original download."""
    fetch_result = await page.evaluate(
        """async (url) => {
            const response = await fetch(url, {
                credentials: "include"
            });

            const contentType = response.headers.get(
                "content-type"
            ) || "";

            if (!response.ok) {
                return {
                    ok: false,
                    status: response.status,
                    contentType: contentType
                };
            }

            const bytes = new Uint8Array(await response.arrayBuffer());
            let binary = "";
            const chunkSize = 0x8000;

            for (let offset = 0; offset < bytes.length; offset += chunkSize) {
                binary += String.fromCharCode(
                    ...bytes.subarray(offset, offset + chunkSize)
                );
            }

            return {
                ok: true,
                status: response.status,
                contentType: contentType,
                body: btoa(binary)
            };
        }""",
        download_url
    )

    if fetch_result.get("ok"):
        return base64.b64decode(fetch_result["body"])

    log(
        f"    [{pkey_project}] Direct fetch returned "
        f"{fetch_result.get('status')} ({fetch_result.get('contentType', 'unknown')}); "
        "using Menlo original download...",
        force=True
    )

    async with page.expect_popup(timeout=30000) as popup_info:
        await report_link.click()

    popup_page = await popup_info.value
    try:
        await popup_page.wait_for_load_state(
            "domcontentloaded",
            timeout=60000
        )

        async with popup_page.expect_download(timeout=60000) as download_info:
            await popup_page.locator("#download-menu-btn").click()
            await popup_page.locator("#ori-download").click()

        download_event = await download_info.value
        download_path = await download_event.path()

        if not download_path:
            raise Exception("Menlo original download did not provide a file path.")

        with open(download_path, "rb") as report_file:
            report_bytes = report_file.read()

        if not report_bytes:
            raise Exception("Menlo original download returned an empty file.")

        return report_bytes
    finally:
        await popup_page.close()

async def download_single_project_async(
    context,
    project,
    tab_id,
    semaphore,
    progress_tracker
):
    """
    Download comments for one ProjNet project.

    This uses normal browser link behavior after the project report is generated.

    Outcomes:
      - In-page fetch:
          Read the generated XLSX response before browser navigation can be
          intercepted by Menlo, convert it to CSV, mark success.
      - Native browser download event:
          Save XLSX, convert to CSV, mark success.
      - Popup/new tab:
          Save diagnostic HTML and screenshot, then mark the attempt failed.
      - No link:
          Treat as an empty report if the page says there is no data;
          otherwise fail with the report-generation error.

    This intentionally does not use the separate Playwright API request method
    that returned IIS 404 for dynamic downloadReport.cfm report files.
    """
    pkey_project = str(project["PKEYPROJECT"])
    project_id = str(project["PROJECTID"])
    project_name = str(project["PROJECTNAME"])

    # Preserve original staggered startup behavior.
    await asyncio.sleep(tab_id * TAB_STARTUP_DELAY)

    async with semaphore:
        for attempt in range(MAX_RETRIES):
            page = None
            popup_page = None
            temp_xlsx_path = None

            try:
                # ============================================================
                # 1. Open the ProjNet All Comments Report page.
                # ============================================================
                page = await context.new_page()
                page.set_default_timeout(PAGE_LOAD_TIMEOUT)

                await page.goto(
                    ALL_COMMENTS_REPORT_URL,
                    wait_until="domcontentloaded",
                    timeout=PAGE_LOAD_TIMEOUT
                )

                project_dropdown = page.locator(
                    'select[name="selectProject"]'
                )

                await project_dropdown.wait_for(
                    state="visible",
                    timeout=60000
                )

                # ============================================================
                # 2. Select the project and generate its report.
                # ============================================================
                await project_dropdown.select_option(
                    value=pkey_project,
                    timeout=30000
                )

                # Retain original short wait for page event processing.
                await page.wait_for_timeout(500)

                run_report_button = page.locator(
                    'input[name="SubmitReport"][value="Run Report"]'
                )

                await run_report_button.wait_for(
                    state="visible",
                    timeout=30000
                )

                await run_report_button.click(timeout=30000)

                # ============================================================
                # 3. Wait for the report download link.
                # ============================================================
                download_selector = 'a[href*="downloadReport.cfm"]'

                try:
                    await page.wait_for_function(
                        """() => {
                            const link = document.querySelector(
                                'a[href*="downloadReport.cfm"]'
                            );

                            if (!link) {
                                return false;
                            }

                            const href = link.getAttribute("href") || "";

                            return (
                                href.includes("downloadReport.cfm") &&
                                href.includes("file=")
                            );
                        }""",
                        timeout=90000
                    )

                except Exception:
                    page_html = (await page.content()).lower()

                    no_data_messages = [
                        "no records found",
                        "no comments found",
                        "no data found",
                        "0 records"
                    ]

                    if any(
                        message in page_html
                        for message in no_data_messages
                    ):
                        csv_path = os.path.join(
                            COMMENTS_FOLDER,
                            f"{pkey_project}.csv"
                        )

                        # Preserve empty-project behavior.
                        with open(
                            csv_path,
                            "w",
                            newline="",
                            encoding="utf-8"
                        ):
                            pass

                        progress = progress_tracker.increment(success=True)

                        if (
                            VERBOSE_OUTPUT or
                            progress["completed"] % PROGRESS_INTERVAL == 0
                        ):
                            eta_str = format_time_estimate(
                                progress["eta_seconds"]
                            )

                            log(
                                f"  ✓ [{progress['completed']}/"
                                f"{progress['total']}] "
                                f"{pkey_project}: "
                                f"{project_name[:40]} "
                                f"(No comments; ETA: {eta_str})",
                                force=True
                            )

                        return {
                            "PKEYPROJECT": pkey_project,
                            "PROJECTID": project_id,
                            "PROJECTNAME": project_name,
                            "STATUS": "SUCCESS",
                            "MESSAGE": "No comments found (Empty project)",
                            "ATTEMPTS": attempt + 1,
                            "TIMESTAMP": datetime.now().strftime(
                                "%Y-%m-%d %H:%M:%S"
                            )
                        }

                    # Save diagnostics if the report link never appears.
                    timeout_html_path = os.path.join(
                        LOGS_FOLDER,
                        f"comments_link_timeout_{pkey_project}.html"
                    )

                    timeout_screenshot_path = os.path.join(
                        LOGS_FOLDER,
                        f"comments_link_timeout_{pkey_project}.png"
                    )

                    try:
                        with open(
                            timeout_html_path,
                            "w",
                            encoding="utf-8"
                        ) as debug_file:
                            debug_file.write(await page.content())

                        await page.screenshot(
                            path=timeout_screenshot_path,
                            full_page=True
                        )
                    except Exception:
                        pass

                    raise Exception(
                        "Timed out waiting for ProjNet to display the "
                        "comments-report download link."
                    )

                # ============================================================
                # 4. Capture details of the generated link.
                # ============================================================
                report_link = page.locator(download_selector).first

                raw_href = await report_link.get_attribute("href")

                link_html = await report_link.evaluate(
                    "(element) => element.outerHTML"
                )

                if not raw_href:
                    raise Exception(
                        "ProjNet displayed a report link, but it did not "
                        "contain an href."
                    )

                download_url = normalize_comments_download_url(raw_href)

                link_html_path = os.path.join(
                    LOGS_FOLDER,
                    f"comments_download_link_{pkey_project}.html"
                )

                try:
                    with open(
                        link_html_path,
                        "w",
                        encoding="utf-8"
                    ) as debug_file:
                        debug_file.write(link_html)
                except Exception:
                    pass

                log(
                    f"    [{pkey_project}] Raw href: {raw_href}",
                    force=True
                )

                log(
                    f"    [{pkey_project}] Download URL: {download_url}",
                    force=True
                )

                log(
                    f"    [{pkey_project}] Link HTML saved: "
                    f"{link_html_path}",
                    force=True
                )

                # ============================================================
                # 5. Fetch the file from the authenticated report page.
                #
                # A request made by the page retains the browser session and
                # report-page context, while avoiding top-level navigation that
                # Menlo turns into a preview tab.
                # ============================================================
                temp_xlsx_path = os.path.join(
                    COMMENTS_FOLDER,
                    f"{pkey_project}_temp.xlsx"
                )

                csv_path = os.path.join(
                    COMMENTS_FOLDER,
                    f"{pkey_project}.csv"
                )

                log(
                    f"    [{pkey_project}] Fetching generated report "
                    "before browser navigation...",
                    force=True
                )

                report_bytes = await fetch_report_bytes(
                    page,
                    report_link,
                    download_url,
                    pkey_project
                )

                if not report_bytes:
                    raise Exception("In-page report fetch returned an empty file.")

                with open(temp_xlsx_path, "wb") as report_file:
                    report_file.write(report_bytes)

                downloaded_size = os.path.getsize(temp_xlsx_path)

                log(
                    f"    [{pkey_project}] Report fetched before Menlo "
                    f"preview ({downloaded_size:,} bytes)",
                    force=True
                )

                success = convert_xlsx_to_csv(
                    temp_xlsx_path,
                    csv_path
                )

                if not success:
                    raise Exception(
                        "In-page report fetch completed, but XLSX-to-CSV "
                        "conversion failed."
                    )

                progress = progress_tracker.increment(success=True)

                if (
                    VERBOSE_OUTPUT or
                    progress["completed"] % PROGRESS_INTERVAL == 0
                ):
                    eta_str = format_time_estimate(progress["eta_seconds"])

                    log(
                        f"  ✓ [{progress['completed']}/"
                        f"{progress['total']}] "
                        f"{pkey_project}: "
                        f"{project_name[:40]} "
                        f"(ETA: {eta_str})",
                        force=True
                    )

                return {
                    "PKEYPROJECT": pkey_project,
                    "PROJECTID": project_id,
                    "PROJECTNAME": project_name,
                    "STATUS": "SUCCESS",
                    "MESSAGE": "Fetched report before Menlo preview",
                    "ATTEMPTS": attempt + 1,
                    "TIMESTAMP": datetime.now().strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                }

                # ============================================================
                # 6. Fallback browser click diagnostics.
                # ============================================================
                log(
                    f"    [{pkey_project}] Clicking generated report link "
                    "using normal browser behavior...",
                    force=True
                )

                download_event = None
                initial_page_count = len(context.pages)

                try:
                    async with page.expect_download(timeout=15000) as download_info:
                        await report_link.click()

                    download_event = await download_info.value

                except Exception:
                    # This is expected when the link opens a preview/new tab
                    # rather than triggering Chromium's native download event.
                    pass

                # Allow a popup/new tab to finish opening after the click.
                await page.wait_for_timeout(3000)

                # ============================================================
                # 7. Handle a normal browser download.
                # ============================================================
                if download_event:
                    temp_xlsx_path = os.path.join(
                        COMMENTS_FOLDER,
                        f"{pkey_project}_temp.xlsx"
                    )

                    csv_path = os.path.join(
                        COMMENTS_FOLDER,
                        f"{pkey_project}.csv"
                    )

                    await download_event.save_as(temp_xlsx_path)

                    if not os.path.exists(temp_xlsx_path):
                        raise Exception(
                            "Playwright reported a browser download, but the "
                            "temporary XLSX file was not created."
                        )

                    downloaded_size = os.path.getsize(temp_xlsx_path)

                    if downloaded_size == 0:
                        raise Exception(
                            "The browser download completed but the XLSX file "
                            "was empty."
                        )

                    log(
                        f"    [{pkey_project}] Browser download received: "
                        f"{download_event.suggested_filename} "
                        f"({downloaded_size:,} bytes)",
                        force=True
                    )

                    success = convert_xlsx_to_csv(
                        temp_xlsx_path,
                        csv_path
                    )

                    if not success:
                        raise Exception(
                            "Browser download completed, but XLSX-to-CSV "
                            "conversion failed."
                        )

                    progress = progress_tracker.increment(success=True)

                    if (
                        VERBOSE_OUTPUT or
                        progress["completed"] % PROGRESS_INTERVAL == 0
                    ):
                        eta_str = format_time_estimate(
                            progress["eta_seconds"]
                        )

                        log(
                            f"  ✓ [{progress['completed']}/"
                            f"{progress['total']}] "
                            f"{pkey_project}: "
                            f"{project_name[:40]} "
                            f"(ETA: {eta_str})",
                            force=True
                        )

                    return {
                        "PKEYPROJECT": pkey_project,
                        "PROJECTID": project_id,
                        "PROJECTNAME": project_name,
                        "STATUS": "SUCCESS",
                        "MESSAGE": (
                            "Downloaded through normal browser download event"
                        ),
                        "ATTEMPTS": attempt + 1,
                        "TIMESTAMP": datetime.now().strftime(
                            "%Y-%m-%d %H:%M:%S"
                        )
                    }

                # ============================================================
                # 8. Find and document any tab/window created by the click.
                # ============================================================
                current_pages = context.pages

                other_pages = [
                    current_page
                    for current_page in current_pages
                    if current_page != page
                ]

                if other_pages:
                    popup_page = other_pages[-1]

                    # Wait briefly for Menlo/preview content and redirects.
                    try:
                        await popup_page.wait_for_timeout(3000)
                    except Exception:
                        pass

                    popup_url = popup_page.url

                    try:
                        popup_title = await popup_page.title()
                    except Exception:
                        popup_title = "(Unable to read popup title)"

                    popup_html_path = os.path.join(
                        LOGS_FOLDER,
                        f"comments_download_popup_{pkey_project}.html"
                    )

                    popup_screenshot_path = os.path.join(
                        LOGS_FOLDER,
                        f"comments_download_popup_{pkey_project}.png"
                    )

                    popup_diagnostic_path = os.path.join(
                        LOGS_FOLDER,
                        f"comments_download_popup_{pkey_project}.json"
                    )

                    try:
                        with open(
                            popup_html_path,
                            "w",
                            encoding="utf-8"
                        ) as debug_file:
                            debug_file.write(await popup_page.content())
                    except Exception:
                        pass

                    try:
                        await popup_page.screenshot(
                            path=popup_screenshot_path,
                            full_page=True
                        )
                    except Exception:
                        pass

                    try:
                        with open(
                            popup_diagnostic_path,
                            "w",
                            encoding="utf-8"
                        ) as debug_file:
                            json.dump(
                                {
                                    "pkey_project": pkey_project,
                                    "project_id": project_id,
                                    "project_name": project_name,
                                    "raw_href": raw_href,
                                    "normalized_download_url": download_url,
                                    "popup_url": popup_url,
                                    "popup_title": popup_title,
                                    "source_page_url": page.url,
                                    "initial_page_count": initial_page_count,
                                    "current_page_count": len(current_pages)
                                },
                                debug_file,
                                indent=2
                            )
                    except Exception:
                        pass

                    log(
                        f"    [{pkey_project}] Browser click opened another "
                        "tab/window instead of a native download.",
                        force=True
                    )

                    log(
                        f"    [{pkey_project}] Popup URL: {popup_url}",
                        force=True
                    )

                    log(
                        f"    [{pkey_project}] Popup Title: {popup_title}",
                        force=True
                    )

                    log(
                        f"    [{pkey_project}] Popup HTML saved: "
                        f"{popup_html_path}",
                        force=True
                    )

                    log(
                        f"    [{pkey_project}] Popup screenshot saved: "
                        f"{popup_screenshot_path}",
                        force=True
                    )

                    raise Exception(
                        "Generated report link opened another browser tab/window "
                        "instead of producing a Chromium download event. "
                        f"Popup URL: {popup_url}"
                    )

                # ============================================================
                # 9. No native download and no popup.
                # ============================================================
                source_page_html_path = os.path.join(
                    LOGS_FOLDER,
                    f"comments_download_no_event_{pkey_project}.html"
                )

                source_page_screenshot_path = os.path.join(
                    LOGS_FOLDER,
                    f"comments_download_no_event_{pkey_project}.png"
                )

                try:
                    with open(
                        source_page_html_path,
                        "w",
                        encoding="utf-8"
                    ) as debug_file:
                        debug_file.write(await page.content())

                    await page.screenshot(
                        path=source_page_screenshot_path,
                        full_page=True
                    )
                except Exception:
                    pass

                raise Exception(
                    "Generated report link click produced neither a browser "
                    "download event nor another tab/window. "
                    f"Page HTML saved to: {source_page_html_path}"
                )

            except Exception as e:
                error_msg = str(e)

                # If a partial XLSX was created, remove it before retrying.
                if temp_xlsx_path and os.path.exists(temp_xlsx_path):
                    try:
                        os.remove(temp_xlsx_path)
                    except Exception:
                        pass

                if attempt == MAX_RETRIES - 1:
                    progress = progress_tracker.increment(success=False)

                    eta_str = format_time_estimate(
                        progress["eta_seconds"]
                    )

                    log(
                        f"  ✗ [{progress['completed']}/"
                        f"{progress['total']}] "
                        f"{pkey_project}: FAILED after "
                        f"{MAX_RETRIES} attempts - "
                        f"{error_msg[:300]} "
                        f"(ETA: {eta_str})",
                        force=True
                    )

                    return {
                        "PKEYPROJECT": pkey_project,
                        "PROJECTID": project_id,
                        "PROJECTNAME": project_name,
                        "STATUS": "ERROR",
                        "MESSAGE": (
                            f"Failed after {MAX_RETRIES} attempts: "
                            f"{error_msg}"
                        ),
                        "ATTEMPTS": MAX_RETRIES,
                        "TIMESTAMP": datetime.now().strftime(
                            "%Y-%m-%d %H:%M:%S"
                        )
                    }

                if VERBOSE_OUTPUT:
                    log(
                        f"    ⚠ [{pkey_project}] Attempt "
                        f"{attempt + 1}/{MAX_RETRIES} failed: "
                        f"{error_msg[:300]}. "
                        f"Retrying in {RETRY_DELAY} seconds...",
                        force=True
                    )

                await asyncio.sleep(RETRY_DELAY)

            finally:
                if popup_page:
                    try:
                        await popup_page.close()
                    except Exception:
                        pass

                if page:
                    try:
                        await page.close()
                    except Exception:
                        pass




# ============================================================================
# ASYNC MAIN FUNCTION FOR MULTI-TAB DOWNLOADS
# ============================================================================

async def download_all_comments_async(browser, projects_to_download, start_time):
    """Download all comments using multiple tabs in the same browser."""
    contexts = browser.contexts
    if len(contexts) == 0:
        raise Exception("No browser context found")
    
    context = contexts[0]
    semaphore = asyncio.Semaphore(MAX_PARALLEL_TABS)
    progress_tracker = ProgressTracker(len(projects_to_download), start_time)
    
    tasks = []
    for idx, project in enumerate(projects_to_download):
        tab_id = idx % MAX_PARALLEL_TABS
        task = download_single_project_async(context, project, tab_id, semaphore, progress_tracker)
        tasks.append(task)
    
    results = await asyncio.gather(*tasks)
    return results

# ============================================================================
# SYNCHRONOUS WRAPPER FOR INITIAL DOWNLOADS
# ============================================================================

from playwright.sync_api import sync_playwright as sync_pw

def login_sync(page, username, password):
    """Authenticate user on ProjNet website (sync version)."""
    log("\n" + "=" * 80, force=True)
    log("LOGGING IN TO PROJNET", force=True)
    log("=" * 80, force=True)
    
    log("→ Navigating to login page...", force=True)
    page.goto(LOGIN_URL, timeout=PAGE_LOAD_TIMEOUT)
    
    log("→ WAITING FOR CAC/ADFS AUTHENTICATION...", force=True)
    log("  Please select your certificate and enter your PIN in the browser window.", force=True)
    
    try:
        page.wait_for_selector("#email", timeout=300000)
        log("✓ Authentication detected, proceeding with login...", force=True)
    except Exception as e:
        log("✗ Timeout waiting for login page. Did CAC authentication fail?", force=True)
        raise e

    log("→ Entering username...", force=True)
    page.fill("#email", username)
    
    log("→ Entering password...", force=True)
    page.fill("#password", password)
    
    log("→ Accepting terms and conditions...", force=True)
    if not page.is_checked("#terms0"):
        page.click("#terms0")
    
    log("→ Clicking sign in button...", force=True)
    page.click("#signin_submit")
    
    page.wait_for_load_state("networkidle", timeout=PAGE_LOAD_TIMEOUT)
    log("✓ Login successful!", force=True)
    log("=" * 80 + "\n", force=True)

def download_all_projects_report_sync(page):
    log("\n" + "=" * 80, force=True)
    log("DOWNLOADING ALL PROJECTS/REVIEWS REPORT (MENLO BYPASS)", force=True)
    log("=" * 80, force=True)
    
    log("→ Navigating to report page...", force=True)
    page.goto(ALL_PROJECTS_REPORT_URL, timeout=PAGE_LOAD_TIMEOUT)
    
    selector = 'a[href*="AllProjects_AllReviews"]'
    page.wait_for_selector(selector, state="visible", timeout=60000)
    
    full_url = page.evaluate(f'document.querySelector(\'{selector}\').href')
    log(f"→ Fetching from: {full_url}", force=True)
    log("→ Downloading file via API to bypass Menlo Preview...", force=True)
    
    response = page.request.get(full_url)
    if response.status == 200:
        xlsx_path = os.path.join(DOWNLOAD_FOLDER, "ALL_PROJ_ALL_REVIEW.xlsx")
        with open(xlsx_path, "wb") as f:
            f.write(response.body())
        
        log("✓ File downloaded successfully", force=True)
        csv_path = os.path.join(DOWNLOAD_FOLDER, "ALL_PROJ_ALL_REVIEW.csv")
        convert_xlsx_to_csv(xlsx_path, csv_path)
        log("✓ Converted to CSV", force=True)
    else:
        log(f"✗ API Download failed with status: {response.status}", force=True)
        raise Exception(f"Failed to download report via API (Status {response.status})")

def download_users_report_sync(page):
    """Extract and save the Users report as CSV (sync version)."""
    log("\n" + "=" * 80, force=True)
    log("DOWNLOADING USERS REPORT", force=True)
    log("=" * 80, force=True)
    
    log("→ Navigating to Site Admin Report page...", force=True)
    page.goto(SITE_ADMIN_REPORT_URL, timeout=PAGE_LOAD_TIMEOUT)
    page.wait_for_load_state("networkidle")
    
    log(f"→ Selecting '{SITE_OFFICE_NAME}' from dropdown...", force=True)
    page.select_option('select[name="intPKeySiteOffice"]', value=SITE_OFFICE_VALUE)
    page.wait_for_timeout(1500)
    
    log("→ Selecting 'Users In Site' report type...", force=True)
    radio_selector = 'input[name="strSiteOfficeReportType"][value="SiteUsers"]'
    
    try:
        page.wait_for_selector(radio_selector, state="visible", timeout=30000)
        page.click(radio_selector)
        page.evaluate(f"document.querySelector('{radio_selector}').checked = true")
    except Exception as e:
        log(f"  ⚠ Radio selection warning: {e}", force=True)
    
    page.wait_for_timeout(1500)
    log("→ Clicking Go button to generate report...", force=True)
    
    # Targeting the second "Go" button for generating the report
    try:
        go_buttons = page.locator('input[value="Go"]')
        count = go_buttons.count()
        
        if count >= 2:
            log(f"  → Found {count} 'Go' buttons. Clicking button #2 (Report Generator)...", force=True)
            go_buttons.nth(1).click()
        elif count == 1:
            log("  → Found 1 'Go' button. Clicking it...", force=True)
            go_buttons.nth(0).click()
        else:
            log("  → Attempting JavaScript fallback for second Go button...", force=True)
            page.evaluate("""() => {
                const btns = document.querySelectorAll('input[value="Go"]');
                if (btns.length >= 2) btns[1].click();
                else if (btns.length === 1) btns[0].click();
                else {
                    const submitBtn = document.querySelector('input[value="Go"][onclick*="doFormSubmit"]');
                    if (submitBtn) submitBtn.click();
                }
            }""")
    except Exception as e:
        log(f"  ✗ Error clicking Go button: {e}", force=True)
        page.keyboard.press("Enter")

    log("→ Waiting for report table to load...", force=True)
    try:
        page.wait_for_selector('table.report_table', timeout=90000)
    except Exception as e:
        log(f"  ⚠ Table not found via selector: {e}. Checking page content...", force=True)
    
    page.wait_for_load_state("networkidle")
    log("→ Parsing user data from HTML table...", force=True)
    
    content = page.content()
    soup = BeautifulSoup(content, 'html.parser')
    
    users_data = []
    table = soup.find('table', class_='report_table')
    
    if not table:
        log("✗ Error: Could not find report_table on page. The report may have failed to generate.", force=True)
        page.screenshot(path=os.path.join(LOGS_FOLDER, "debug_users_report_fail.png"))
        return
    
    rows = table.find_all('tr')
    log(f"→ Found {len(rows)} rows in table", force=True)
    
    for idx, row in enumerate(rows):
        cells = row.find_all('td')
        if len(cells) >= 7:
            try:
                id_cell = cells[0]
                id_link = id_cell.find('a')
                user_id = id_link.text.strip() if id_link else id_cell.text.strip()
                
                if user_id.lower() == 'id' or not user_id:
                    continue
                    
                name = cells[1].text.strip()
                email_cell = cells[3]
                email_link = email_cell.find('a')
                email = email_link.text.strip() if email_link else email_cell.text.strip()
                email = email.replace('\xa0', '').strip()
                
                office = cells[4].text.strip()
                site = cells[5].text.strip()
                status = cells[6].text.strip()
                
                users_data.append({
                    'Id': user_id,
                    'Name': name,
                    'Email': email,
                    'Office': office,
                    'Site': site,
                    'Status': status
                })
            except Exception:
                continue
    
    if not users_data:
        log("✗ No user records were extracted.", force=True)
        return

    log(f"→ Successfully extracted {len(users_data)} user records", force=True)
    csv_path = os.path.join(DOWNLOAD_FOLDER, "USERS.csv")
    
    with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['Id', 'Name', 'Email', 'Office', 'Site', 'Status']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(users_data)
    
    log(f"✓ Users report saved to: {csv_path}", force=True)
    log("=" * 80 + "\n", force=True)

def download_all_projects_list_sync(page):
    log("\n" + "=" * 80, force=True)
    log("DOWNLOADING ALL PROJECTS LIST (MENLO BYPASS)", force=True)
    log("=" * 80, force=True)
    
    log("→ Navigating to All Projects report page...", force=True)
    page.goto(ALL_PROJECTS_LIST_URL, timeout=PAGE_LOAD_TIMEOUT)
    
    selector = 'a[href*="USACE-ProjNet_AllProjects_SiteID1107.xls"]'
    page.wait_for_selector(selector, state="visible", timeout=60000)
    
    full_url = page.evaluate(f'document.querySelector(\'{selector}\').href')
    log(f"→ Fetching from: {full_url}", force=True)
    response = page.request.get(full_url)
    
    if response.status == 200:
        xls_path = os.path.join(DOWNLOAD_FOLDER, "ALL_PROJECTS.xls")
        with open(xls_path, "wb") as f:
            f.write(response.body())
        
        file_modified_time = datetime.fromtimestamp(os.path.getmtime(xls_path))
        file_modified_str = file_modified_time.strftime('%Y-%m-%d %H:%M:%S')
        
        csv_path = os.path.join(DOWNLOAD_FOLDER, "ALL_PROJECTS.csv")
        try:
            df = pd.read_excel(xls_path)
            df.insert(0, 'FILE_LAST_MODIFIED', file_modified_str)
            df.to_csv(csv_path, index=False, encoding='utf-8')
            os.remove(xls_path)
            log("✓ CSV file created and original deleted", force=True)
            return True
        except Exception as e:
            log(f"✗ Error converting Excel to CSV: {e}", force=True)
            return False
    else:
        log(f"✗ API Download failed with status: {response.status}", force=True)
        return False

# ============================================================================
# CONSOLIDATION
# ============================================================================

def consolidate_all_comments():
    """Consolidate all individual comment CSV files into a single ALL_COMMENTS.csv file."""
    log("\n" + "=" * 80, force=True)
    log("CONSOLIDATING ALL COMMENTS INTO SINGLE FILE", force=True)
    log("=" * 80, force=True)
    
    comment_files = [f for f in os.listdir(COMMENTS_FOLDER) if f.endswith('.csv')]
    
    if len(comment_files) == 0:
        log("✗ No comment files found in comments folder", force=True)
        log("=" * 80 + "\n", force=True)
        return
    
    log(f"→ Found {len(comment_files)} comment files to process", force=True)
    
    all_data = []
    expected_columns = None
    processed_count = 0
    empty_count = 0
    error_count = 0
    column_mismatch_count = 0
    consolidation_log = []
    
    for idx, filename in enumerate(comment_files):
        pkeyproject = filename.replace('.csv', '')
        file_path = os.path.join(COMMENTS_FOLDER, filename)
        progress = f"[{idx + 1}/{len(comment_files)}]"
        show_progress = VERBOSE_OUTPUT or ((idx + 1) % 100 == 0) or (idx + 1 == len(comment_files))
        
        try:
            df = pd.read_csv(file_path, encoding='utf-8')
            
            if len(df) == 0:
                if show_progress:
                    log(f"{progress} Processing {filename}... ⚠ EMPTY", force=True)
                empty_count += 1
                
                consolidation_log.append({
                    'PKEYPROJECT': pkeyproject,
                    'STATUS': 'EMPTY',
                    'MESSAGE': 'File contains no data rows',
                    'TIMESTAMP': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
                
                if expected_columns is not None:
                    blank_row = {col: None for col in expected_columns}
                    blank_row['PKEYPROJECT'] = pkeyproject
                    all_data.append(blank_row)
                else:
                    all_data.append({'PKEYPROJECT': pkeyproject})
                continue
            
            current_columns = list(df.columns)
            
            if expected_columns is None:
                expected_columns = current_columns
                log(f"{progress} Processing {filename}... ✓ SET BASELINE ({len(current_columns)} columns)", force=True)
            else:
                if current_columns != expected_columns:
                    log(f"{progress} Processing {filename}... ⚠ COLUMN MISMATCH", force=True)
                    column_mismatch_count += 1
                    
                    missing_cols = set(expected_columns) - set(current_columns)
                    extra_cols = set(current_columns) - set(expected_columns)
                    
                    mismatch_msg = []
                    if missing_cols:
                        mismatch_msg.append(f"Missing: {', '.join(missing_cols)}")
                    if extra_cols:
                        mismatch_msg.append(f"Extra: {', '.join(extra_cols)}")
                    
                    consolidation_log.append({
                        'PKEYPROJECT': pkeyproject,
                        'STATUS': 'COLUMN_MISMATCH',
                        'MESSAGE': '; '.join(mismatch_msg),
                        'TIMESTAMP': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    })
                    continue
            
            df.insert(0, 'PKEYPROJECT', pkeyproject)
            all_data.extend(df.to_dict('records'))
            processed_count += 1
            
            if show_progress:
                log(f"{progress} Processing {filename}... ✓ OK ({len(df)} rows)", force=True)
            
            consolidation_log.append({
                'PKEYPROJECT': pkeyproject,
                'STATUS': 'SUCCESS',
                'MESSAGE': f'Processed {len(df)} rows',
                'TIMESTAMP': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
            
        except Exception as e:
            log(f"{progress} Processing {filename}... ✗ ERROR", force=True)
            error_count += 1
            error_msg = str(e)
            
            consolidation_log.append({
                'PKEYPROJECT': pkeyproject,
                'STATUS': 'ERROR',
                'MESSAGE': error_msg,
                'TIMESTAMP': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
            continue
    
    if len(all_data) == 0:
        log("\n✗ No data to consolidate - all files were empty or had errors", force=True)
        log("=" * 80 + "\n", force=True)
        return
    
    log("\n→ Creating consolidated DataFrame...", force=True)
    df_consolidated = pd.DataFrame(all_data)
    
    cols = df_consolidated.columns.tolist()
    if 'PKEYPROJECT' in cols:
        cols.remove('PKEYPROJECT')
        cols.insert(0, 'PKEYPROJECT')
        df_consolidated = df_consolidated[cols]
    
    output_path = os.path.join(DOWNLOAD_FOLDER, 'ALL_COMMENTS.csv')
    log("→ Saving consolidated file...", force=True)
    df_consolidated.to_csv(output_path, index=False, encoding='utf-8')
    
    log(f"✓ Consolidated file saved: {output_path}", force=True)
    log(f"✓ Total rows in consolidated file: {len(df_consolidated)}", force=True)
    
    if len(consolidation_log) > 0:
        timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_filename = f"consolidation_log_{timestamp_str}.csv"
        log_path = os.path.join(LOGS_FOLDER, log_filename)
        
        log("→ Saving consolidation log...", force=True)
        df_log = pd.DataFrame(consolidation_log)
        df_log.to_csv(log_path, index=False, encoding='utf-8')
        log(f"✓ Consolidation log saved: {log_path}", force=True)
    
    log("\n" + "=" * 80, force=True)
    log("CONSOLIDATION SUMMARY", force=True)
    log("=" * 80, force=True)
    log(f"Total files found: {len(comment_files)}", force=True)
    log(f"  ✓ Successfully processed: {processed_count}", force=True)
    log(f"  ⚠ Empty files: {empty_count}", force=True)
    log(f"  ⚠ Column mismatches: {column_mismatch_count}", force=True)
    log(f"  ✗ Errors: {error_count}", force=True)
    log(f"\nConsolidated file: {output_path}", force=True)
    log(f"Total rows: {len(df_consolidated)}", force=True)
    if expected_columns:
        log(f"Total columns: {len(df_consolidated.columns)} (including PKEYPROJECT)", force=True)
    if len(consolidation_log) > 0:
        log(f"Log file: {log_path}", force=True)
    log("=" * 80 + "\n", force=True)

# ============================================================================
# SHAREPOINT UPLOAD
# ============================================================================

def upload_files_to_sharepoint(context):
    """Upload all CSV files to SharePoint using existing browser context."""
    log("\n" + "=" * 80, force=True)
    log("UPLOADING FILES TO SHAREPOINT", force=True)
    log("=" * 80, force=True)
    log("→ Browser window is VISIBLE for authentication if needed", force=True)
    
    files_to_upload = [
        "USERS.csv",
        "ALL_PROJECTS.csv",
        "ALL_COMMENTS.csv",
        "ALL_PROJ_ALL_REVIEW.csv"
    ]
    
    upload_results = []
    successful_uploads = 0
    failed_uploads = 0
    
    sp_page = context.new_page()
    
    try:
        for idx, filename in enumerate(files_to_upload):
            file_path = os.path.join(DOWNLOAD_FOLDER, filename)
            
            if not os.path.exists(file_path):
                log(f"\n[{idx + 1}/{len(files_to_upload)}] ✗ File not found: {filename}", force=True)
                upload_results.append({
                    'filename': filename,
                    'status': 'NOT_FOUND',
                    'message': 'File does not exist'
                })
                failed_uploads += 1
                continue
            
            file_size = os.path.getsize(file_path)
            file_size_mb = file_size / (1024 * 1024)
            log(f"\n[{idx + 1}/{len(files_to_upload)}] Uploading {filename} ({file_size_mb:.2f} MB)...", force=True)
            
            if file_size_mb > 100:
                log("  ⚠ Large file detected - this may take several minutes...", force=True)
            
            try:
                upload_successful = upload_to_sharepoint(
                    page=sp_page,
                    file_path=file_path,
                    sharepoint_url=SHAREPOINT_URL,
                    sharepoint_library_path=SHAREPOINT_LIBRARY_PATH,
                    email_address=EMAIL_ADDRESS
                )
                
                if upload_successful:
                    log(f"  ✓ {filename} uploaded successfully", force=True)
                    upload_results.append({
                        'filename': filename,
                        'status': 'SUCCESS',
                        'message': 'Uploaded successfully'
                    })
                    successful_uploads += 1
                    if file_size_mb > 100:
                        sp_page.wait_for_timeout(10000)
                else:
                    log(f"  ✗ {filename} upload failed", force=True)
                    upload_results.append({
                        'filename': filename,
                        'status': 'FAILED',
                        'message': 'Upload function returned False'
                    })
                    failed_uploads += 1
                    
            except Exception as upload_error:
                log(f"  ✗ Error uploading {filename}: {str(upload_error)}", force=True)
                upload_results.append({
                    'filename': filename,
                    'status': 'ERROR',
                    'message': str(upload_error)
                })
                failed_uploads += 1
        
        sp_page.wait_for_timeout(15000)
        
    finally:
        sp_page.close()
    
    log("\n" + "=" * 80, force=True)
    log("SHAREPOINT UPLOAD SUMMARY", force=True)
    log("=" * 80, force=True)
    log(f"Total files: {len(files_to_upload)}", force=True)
    log(f"  ✓ Successfully uploaded: {successful_uploads}", force=True)
    log(f"  ✗ Failed uploads: {failed_uploads}", force=True)
    log("\nUpload Details:", force=True)
    for result in upload_results:
        status_symbol = "✓" if result['status'] == 'SUCCESS' else "✗"
        log(f"  {status_symbol} {result['filename']}: {result['message']}", force=True)
    log(f"\nSharePoint Location: {SHAREPOINT_URL}{SHAREPOINT_LIBRARY_PATH}", force=True)
    log("=" * 80 + "\n", force=True)
    
    if len(upload_results) > 0:
        timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_filename = f"sharepoint_upload_{timestamp_str}.csv"
        log_path = os.path.join(LOGS_FOLDER, log_filename)
        
        df_upload_log = pd.DataFrame(upload_results)
        df_upload_log['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        df_upload_log.to_csv(log_path, index=False, encoding='utf-8')
        log(f"✓ Upload log saved: {log_path}", force=True)
    
    return {
        'total': len(files_to_upload),
        'successful': successful_uploads,
        'failed': failed_uploads,
        'results': upload_results
    }

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main execution function."""
    log("\n" + "=" * 80, force=True)
    log("PROJNET DATA EXTRACTION SCRIPT - MULTI-TAB VERSION", force=True)
    log("Author: Ryan Benac", force=True)
    log(f"Parallel Tabs: {MAX_PARALLEL_TABS} (in same browser session)", force=True)
    log(f"Max Retries: {MAX_RETRIES} attempts per project", force=True)
    log(f"Verbose Output: {'ENABLED' if VERBOSE_OUTPUT else f'DISABLED (showing every {PROGRESS_INTERVAL} projects)'}", force=True)
    log(f"Headless Mode (initial downloads): {'ENABLED' if HEADLESS_INITIAL_DOWNLOADS else 'DISABLED'}", force=True)
    log(f"Headless Mode (comments download): {'ENABLED' if HEADLESS_COMMENTS_DOWNLOAD else 'DISABLED'}", force=True)
    log(f"Initial Downloads: " f"{'SKIPPED - using existing files' if SKIP_INITIAL_DOWNLOADS else 'ENABLED'}",    force=True)
    log(f"SharePoint Upload: ALWAYS VISIBLE (not configurable)", force=True)
    log(f"Date Filter: Projects within last {YEARS_TO_INCLUDE} years", force=True)
    log("=" * 80, force=True)
    
    log(f"\n→ Setting up working directory: {WORKING_DIR}", force=True)
    os.makedirs(WORKING_DIR, exist_ok=True)
    os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
    os.makedirs(COMMENTS_FOLDER, exist_ok=True)
    os.makedirs(LOGS_FOLDER, exist_ok=True)
    
    username, password = get_credentials()
    
       # PHASE 1: Initial downloads using sync API
    #
    # During comments-download testing, this can be skipped. Phase 2 uses the
    # previously downloaded ALL_PROJECTS.csv already in DOWNLOAD_FOLDER.
    all_projects_csv = os.path.join(DOWNLOAD_FOLDER, "ALL_PROJECTS.csv")

    if SKIP_INITIAL_DOWNLOADS:
        log(
            "→ Phase 1: SKIPPED - using existing initial download files",
            force=True
        )

        if not os.path.exists(all_projects_csv):
            raise FileNotFoundError(
                "SKIP_INITIAL_DOWNLOADS is True, but the required file was "
                f"not found:\n{all_projects_csv}\n\n"
                "Set SKIP_INITIAL_DOWNLOADS = False to regenerate it, or "
                "place a valid ALL_PROJECTS.csv in the downloads folder."
            )

        file_modified_time = datetime.fromtimestamp(
            os.path.getmtime(all_projects_csv)
        ).strftime("%Y-%m-%d %H:%M:%S")

        log(
            f"✓ Found existing ALL_PROJECTS.csv "
            f"(last modified: {file_modified_time})",
            force=True
        )

    else:
        initial_start = datetime.now()

        log(
            "→ Phase 1: Initial downloads (estimated: ~2 minutes)",
            force=True
        )

        with sync_pw() as p:
            log(
                f"→ Launching browser "
                f"(headless={HEADLESS_INITIAL_DOWNLOADS}) "
                f"for initial downloads...",
                force=True
            )

            browser = p.chromium.launch(
                headless=HEADLESS_INITIAL_DOWNLOADS
            )

            context = browser.new_context(accept_downloads=True)
            page = context.new_page()

            try:
                login_sync(page, username, password)
                download_all_projects_report_sync(page)
                download_users_report_sync(page)
                download_all_projects_list_sync(page)

                page.close()
                browser.close()

                initial_elapsed = (
                    datetime.now() - initial_start
                ).total_seconds()

                log(
                    f"✓ Phase 1 completed in "
                    f"{format_elapsed_time(initial_elapsed)}",
                    force=True
                )

            except Exception as e:
                log(
                    f"✗ Error in initial downloads: {e}",
                    force=True
                )

                browser.close()
                raise
    
    # PHASE 2: Analyze projects
    df_projects = pd.read_csv(all_projects_csv)
    
    # Map column names
    column_mapping = {}
    for col in df_projects.columns:
        col_upper = col.upper().strip()
        if 'PKEY' in col_upper and 'PROJECT' in col_upper:
            column_mapping['PKEYPROJECT'] = col
        elif col_upper == 'PROJECTCODE':
            column_mapping['PKEYPROJECT'] = col
        elif col_upper == 'PROJECTID':
            column_mapping['PROJECTID'] = col
        elif col_upper == 'PROJECTNAME':
            column_mapping['PROJECTNAME'] = col
        elif 'DESIGN' in col_upper and 'END' in col_upper:
            column_mapping['DESIGNEND'] = col
        elif 'CONSTRUCTION' in col_upper and 'END' in col_upper:
            column_mapping['CONSTRUCTIONEND'] = col
    
    log(f"✓ Found {len(df_projects)} total projects", force=True)
    log(f"→ Using date filter: Projects within last {YEARS_TO_INCLUDE} years", force=True)
    log("→ Analyzing which projects need comments downloaded...", force=True)
    
    projects_to_download = []
    projects_to_skip = []
    
    for idx, row in df_projects.iterrows():
        pkey_project = str(int(row[column_mapping['PKEYPROJECT']]))
        project_id = str(row[column_mapping['PROJECTID']])
        project_name = str(row[column_mapping['PROJECTNAME']])
        
        design_end = row.get(column_mapping.get('DESIGNEND'), None) if 'DESIGNEND' in column_mapping else None
        construction_end = row.get(column_mapping.get('CONSTRUCTIONEND'), None) if 'CONSTRUCTIONEND' in column_mapping else None
        
        latest_date = get_latest_date(design_end, construction_end)
        should_download, reason = should_download_comments(pkey_project, latest_date)
        
        if should_download:
            projects_to_download.append({
                'PKEYPROJECT': pkey_project,
                'PROJECTID': project_id,
                'PROJECTNAME': project_name,
                'LATEST_DATE': latest_date,
                'REASON': reason
            })
        else:
            projects_to_skip.append({
                'PKEYPROJECT': pkey_project,
                'PROJECTID': project_id,
                'PROJECTNAME': project_name,
                'LATEST_DATE': latest_date,
                'REASON': reason
            })
    
    log(f"✓ Projects to download: {len(projects_to_download)}", force=True)
    log(f"✓ Projects to skip: {len(projects_to_skip)}", force=True)
    
    # PHASE 3: Multi-tab downloads using async API
    if len(projects_to_download) > 0:
        estimated_seconds = (len(projects_to_download) / MAX_PARALLEL_TABS) * AVG_SECONDS_PER_PROJECT
        estimated_str = format_time_estimate(estimated_seconds)
        
        log("\n" + "=" * 80, force=True)
        log("DOWNLOADING ALL COMMENTS REPORTS (MULTI-TAB MODE)", force=True)
        log("=" * 80, force=True)
        log(f"→ Using {MAX_PARALLEL_TABS} parallel tabs in same browser session", force=True)
        log(f"→ Headless mode: {'ENABLED' if HEADLESS_COMMENTS_DOWNLOAD else 'DISABLED'}", force=True)
        log(f"→ Phase 2: Downloading {len(projects_to_download)} projects", force=True)
        log(f"→ Estimated time: {estimated_str}", force=True)
        log(f"→ Progress updates: Every {PROGRESS_INTERVAL} projects", force=True)
        
        start_time = datetime.now()
        
        async def run_async_downloads():
            async with async_playwright() as p:
                log(f"→ Launching browser (headless={HEADLESS_COMMENTS_DOWNLOAD})...", force=True)
                browser = await p.chromium.launch(headless=HEADLESS_COMMENTS_DOWNLOAD)
                context = await browser.new_context(accept_downloads=True)
                page = await context.new_page()
                
                log("→ Logging in...", force=True)
                await page.goto(LOGIN_URL, timeout=PAGE_LOAD_TIMEOUT)
                
                log("→ WAITING FOR CAC/ADFS AUTHENTICATION...", force=True)
                await page.wait_for_selector("#email", timeout=300000)
                
                await page.fill("#email", username)
                await page.fill("#password", password)
                
                if not await page.is_checked("#terms0"):
                    await page.click("#terms0")
                    
                await page.click("#signin_submit")
                await page.wait_for_load_state("networkidle", timeout=PAGE_LOAD_TIMEOUT)
                await page.close()
                
                log("✓ Login successful - session established", force=True)
                log(f"→ Starting download of {len(projects_to_download)} projects...", force=True)
                log("=" * 80, force=True)
                
                results = await download_all_comments_async(browser, projects_to_download, start_time)
                await browser.close()
                return results
        
        log_data = asyncio.run(run_async_downloads())
        
        end_time = datetime.now()
        elapsed_time = (end_time - start_time).total_seconds()
        
        downloaded_count = sum(1 for r in log_data if r['STATUS'] == 'SUCCESS')
        error_count = sum(1 for r in log_data if r['STATUS'] == 'ERROR')
        
        for project in projects_to_skip:
            log_data.append({
                'PKEYPROJECT': project['PKEYPROJECT'],
                'PROJECTID': project['PROJECTID'],
                'PROJECTNAME': project['PROJECTNAME'],
                'STATUS': 'SKIPPED',
                'MESSAGE': project['REASON'],
                'ATTEMPTS': 0,
                'TIMESTAMP': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
        
        timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_filename = f"comments_download_{timestamp_str}.csv"
        log_path = os.path.join(LOGS_FOLDER, log_filename)
        
        df_log = pd.DataFrame(log_data)
        df_log.to_csv(log_path, index=False, encoding='utf-8')
        
        log("\n" + "=" * 80, force=True)
        log("COMMENTS DOWNLOAD SUMMARY", force=True)
        log("=" * 80, force=True)
        log(f"Total projects processed: {len(df_projects)}", force=True)
        log(f"  ✓ Successfully downloaded: {downloaded_count}", force=True)
        log(f"  → Skipped (up to date): {len(projects_to_skip)}", force=True)
        log(f"  ✗ Failed (after {MAX_RETRIES} attempts): {error_count}", force=True)
        log("\nPerformance:", force=True)
        log(f"  Total time: {format_elapsed_time(elapsed_time)}", force=True)
        log(f"  Average time per project: {elapsed_time / len(projects_to_download):.2f} seconds", force=True)
        log(f"  Parallel tabs used: {MAX_PARALLEL_TABS}", force=True)
        log(f"\nLog file: {log_path}", force=True)
        
        if error_count > 0:
            log(f"\n⚠ WARNING: {error_count} projects failed after {MAX_RETRIES} retry attempts", force=True)
            log(f"  Check log file for details: {log_path}", force=True)
        
        log("=" * 80 + "\n", force=True)
        
        if downloaded_count > 0:
            log("→ Phase 3: Consolidating comment files...", force=True)
            consolidate_all_comments()
    else:
        log("✓ No projects need downloading. All comments are up to date!", force=True)
    
    # PHASE 4: SharePoint upload
    log("→ Phase 4: SharePoint upload (estimated: ~2 minutes)", force=True)
    
    with sync_pw() as p:
        log("→ Launching browser (VISIBLE) for SharePoint upload...", force=True)
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(accept_downloads=True)
        
        try:
            upload_files_to_sharepoint(context)
            log("\n" + "=" * 80, force=True)
            log("✓ ALL TASKS COMPLETED SUCCESSFULLY!", force=True)
            log("=" * 80 + "\n", force=True)
        finally:
            browser.close()

# ============================================================================
# SCRIPT ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--reset-credentials":
        print("Resetting credentials...")
        reset_credentials()
        print("Credentials reset complete. Run the script again to use new credentials.")
    else:
        main()