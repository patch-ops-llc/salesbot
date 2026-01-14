import asyncio
import time
import re
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from threading import Event
from typing import Callable, Optional, List
from playwright.sync_api import sync_playwright, Browser, Page, BrowserContext, Playwright

from .models import (
    BotConfig, BotStatus, Executive, ConnectionRequest,
    ConnectionStatus, SearchConfig
)
from .crm_client import CRMClient

# Get absolute path for browser data
BROWSER_DATA_DIR = Path(__file__).parent.parent / "browser_data"

# Thread pool for running sync playwright
_executor = ThreadPoolExecutor(max_workers=1)


class LinkedInBot:
    """LinkedIn automation bot using Playwright (sync API for Windows compatibility)"""
    
    def __init__(
        self,
        config: BotConfig,
        crm_client: CRMClient,
        status_callback: Optional[Callable[[BotStatus], None]] = None
    ):
        self.config = config
        self.crm_client = crm_client
        self._status_callback = status_callback
        self.status = BotStatus()
        self.playwright: Optional[Playwright] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self._stop_event = Event()
        self._loop = None  # Store the asyncio event loop for callbacks
    
    def _log(self, message: str):
        """Add a log message and notify callback"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        self.status.log_messages.append(log_entry)
        # Keep only last 100 messages
        if len(self.status.log_messages) > 100:
            self.status.log_messages = self.status.log_messages[-100:]
        self._notify_status()
    
    def _notify_status(self):
        """Notify the callback of status change (thread-safe)"""
        if self._status_callback:
            if self._loop and self._loop.is_running():
                # Schedule the callback on the main event loop from any thread
                try:
                    self._loop.call_soon_threadsafe(self._do_notify)
                except Exception as e:
                    print(f"Notify error: {e}")
            else:
                # Fallback: try to call directly (may work if in same thread)
                try:
                    self._status_callback(self.status)
                except Exception:
                    pass  # Ignore if we can't notify yet
    
    def _do_notify(self):
        """Execute the notification on the event loop"""
        if self._status_callback:
            asyncio.ensure_future(self._async_broadcast())
    
    async def _async_broadcast(self):
        """Async wrapper for status notification"""
        if self._status_callback:
            self._status_callback(self.status)
    
    def _update_status(self, action: str, **kwargs):
        """Update bot status"""
        self.status.current_action = action
        for key, value in kwargs.items():
            if hasattr(self.status, key):
                setattr(self.status, key, value)
        self._notify_status()
    
    def _start_browser(self, headless: bool = False):
        """Start the browser with persistent context for LinkedIn login (sync)"""
        self._log("Starting browser...")
        self.status.is_running = True
        self._update_status("Starting browser")
        
        # Ensure browser data directory exists
        BROWSER_DATA_DIR.mkdir(parents=True, exist_ok=True)
        browser_data_path = str(BROWSER_DATA_DIR.absolute())
        self._log(f"Browser data path: {browser_data_path}")
        
        self.playwright = sync_playwright().start()
        
        # Use persistent context to maintain LinkedIn session
        self.context = self.playwright.chromium.launch_persistent_context(
            user_data_dir=browser_data_path,
            headless=headless,
            viewport={"width": 1280, "height": 800},
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ]
        )
        
        # Get the first page or create a new one
        if self.context.pages:
            self.page = self.context.pages[0]
        else:
            self.page = self.context.new_page()
        
        # Add stealth measures
        self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
        
        self._log("Browser started successfully")
    
    def _check_login(self) -> bool:
        """Check if user is logged into LinkedIn (sync)"""
        self._update_status("Checking LinkedIn login status")
        
        self.page.goto("https://www.linkedin.com/feed/", wait_until="networkidle")
        time.sleep(2)
        
        # Check if we're on the login page or feed
        current_url = self.page.url
        if "login" in current_url or "checkpoint" in current_url:
            self._log("[!] Not logged in to LinkedIn. Please log in manually.")
            return False
        
        self._log("[OK] LinkedIn login confirmed")
        return True
    
    def _search_jobs(self) -> List[dict]:
        """Search for jobs matching the criteria (sync)"""
        self._update_status("Searching for job postings")
        jobs = []
        
        search_config = self.config.search_config
        
        for job_title in search_config.job_titles:
            if self._stop_event.is_set():
                break
                
            self._log(f"Searching for: {job_title}")
            
            # Build LinkedIn jobs search URL
            search_url = f"https://www.linkedin.com/jobs/search/?keywords={job_title.replace(' ', '%20')}"
            
            if search_config.posted_within_days <= 1:
                search_url += "&f_TPR=r86400"  # Past 24 hours
            elif search_config.posted_within_days <= 7:
                search_url += "&f_TPR=r604800"  # Past week
            elif search_config.posted_within_days <= 30:
                search_url += "&f_TPR=r2592000"  # Past month
            
            self.page.goto(search_url, wait_until="networkidle")
            time.sleep(3)
            
            # Extract job listings
            job_cards = self.page.query_selector_all(".job-card-container")
            
            for card in job_cards[:10]:  # Limit to first 10 per search
                if self._stop_event.is_set():
                    break
                    
                try:
                    title_elem = card.query_selector(".job-card-list__title")
                    company_elem = card.query_selector(".job-card-container__primary-description")
                    link_elem = card.query_selector("a.job-card-container__link")
                    
                    if title_elem and company_elem and link_elem:
                        title = title_elem.inner_text()
                        company = company_elem.inner_text()
                        link = link_elem.get_attribute("href")
                        
                        jobs.append({
                            "title": title.strip(),
                            "company": company.strip(),
                            "link": link,
                            "search_term": job_title
                        })
                except Exception as e:
                    self._log(f"Error extracting job: {str(e)}")
            
            time.sleep(2)  # Rate limiting
        
        self._log(f"Found {len(jobs)} job postings")
        return jobs
    
    def _find_company_executives(self, company_name: str, job_title: str) -> List[Executive]:
        """Find executives at a company (sync)"""
        self._update_status(f"Finding executives at {company_name}")
        executives = []
        
        # Search for people at the company with executive titles
        executive_titles = ["CEO", "CTO", "COO", "CFO", "VP", "Director", "Head of", "Chief"]
        
        search_query = f"{company_name}"
        search_url = f"https://www.linkedin.com/search/results/people/?keywords={search_query.replace(' ', '%20')}&origin=GLOBAL_SEARCH_HEADER"
        
        self.page.goto(search_url, wait_until="networkidle")
        time.sleep(3)
        
        # Get people results
        person_cards = self.page.query_selector_all(".entity-result")
        
        for card in person_cards[:5]:  # Limit to first 5
            if self._stop_event.is_set():
                break
                
            try:
                name_elem = card.query_selector(".entity-result__title-text a span[aria-hidden='true']")
                title_elem = card.query_selector(".entity-result__primary-subtitle")
                link_elem = card.query_selector(".entity-result__title-text a")
                
                if name_elem and title_elem and link_elem:
                    name = name_elem.inner_text()
                    title = title_elem.inner_text()
                    link = link_elem.get_attribute("href")
                    
                    # Check if this is an executive
                    is_executive = any(
                        exec_title.lower() in title.lower() 
                        for exec_title in executive_titles
                    )
                    
                    if is_executive:
                        executive = Executive(
                            name=name.strip(),
                            title=title.strip(),
                            company=company_name,
                            linkedin_url=link,
                            company_job_title=job_title
                        )
                        executives.append(executive)
                        self._log(f"Found executive: {name} - {title}")
                        
            except Exception as e:
                self._log(f"Error extracting person: {str(e)}")
        
        return executives
    
    def _generate_custom_message(self, executive: Executive) -> str:
        """Generate a customized connection message"""
        template = self.config.message_template.template
        
        # Replace placeholders
        message = template.replace("{name}", executive.name.split()[0])  # First name
        message = message.replace("{company}", executive.company)
        message = message.replace("{title}", executive.title)
        message = message.replace("{job_title}", executive.company_job_title or "")
        
        # LinkedIn has a 300 character limit for connection messages
        if len(message) > 300:
            message = message[:297] + "..."
        
        return message
    
    def _send_connection_request(self, executive: Executive) -> ConnectionRequest:
        """Send a connection request to an executive (sync)"""
        self._update_status(f"Sending connection to {executive.name}", current_executive=executive)
        
        custom_message = self._generate_custom_message(executive)
        request = ConnectionRequest(
            executive=executive,
            custom_message=custom_message
        )
        
        try:
            # Navigate to the person's profile
            self.page.goto(executive.linkedin_url, wait_until="networkidle")
            time.sleep(2)
            
            # Look for the Connect button
            connect_button = self.page.query_selector("button:has-text('Connect')")
            
            if not connect_button:
                # Try the "More" dropdown
                more_button = self.page.query_selector("button:has-text('More')")
                if more_button:
                    more_button.click()
                    time.sleep(1)
                    connect_button = self.page.query_selector("div[role='menuitem']:has-text('Connect')")
            
            if connect_button:
                connect_button.click()
                time.sleep(1)
                
                # Click "Add a note" button
                add_note_button = self.page.query_selector("button:has-text('Add a note')")
                if add_note_button:
                    add_note_button.click()
                    time.sleep(1)
                
                # Fill in the message
                message_input = self.page.query_selector("textarea[name='message']")
                if message_input:
                    message_input.fill(custom_message)
                    time.sleep(1)
                
                # Click Send
                send_button = self.page.query_selector("button:has-text('Send')")
                if send_button:
                    send_button.click()
                    time.sleep(2)
                    
                    request.status = ConnectionStatus.sent
                    request.sent_at = datetime.now()
                    self._log(f"[OK] Connection sent to {executive.name}")
                    self.status.connections_sent += 1
                else:
                    raise Exception("Could not find Send button")
            else:
                # Might already be connected or pending
                self._log(f"[!] Connect button not found for {executive.name} - may already be connected")
                request.status = ConnectionStatus.failed
                request.error_message = "Connect button not found"
                self.status.connections_failed += 1
                
        except Exception as e:
            request.status = ConnectionStatus.failed
            request.error_message = str(e)
            self._log(f"[ERR] Failed to connect with {executive.name}: {str(e)}")
            self.status.connections_failed += 1
        
        self._notify_status()
        return request
    
    def _run_sync(self):
        """Main bot execution loop (sync version that runs in a thread)"""
        self._stop_event.clear()
        
        try:
            self._start_browser(headless=False)
            
            # Check if logged in
            if not self._check_login():
                self._log("Please log in to LinkedIn in the browser window, then restart the bot.")
                return
            
            # Search for jobs
            jobs = self._search_jobs()
            
            if not jobs:
                self._log("No jobs found matching criteria")
                return
            
            # Track processed companies to avoid duplicates
            processed_companies = set()
            connections_sent = 0
            
            for job in jobs:
                if self._stop_event.is_set():
                    self._log("Bot stopped by user")
                    break
                
                if connections_sent >= self.config.max_connections_per_session:
                    self._log(f"Reached max connections limit ({self.config.max_connections_per_session})")
                    break
                
                company = job["company"]
                
                if company in processed_companies:
                    continue
                
                processed_companies.add(company)
                
                # Find executives at this company
                executives = self._find_company_executives(company, job["title"])
                
                for executive in executives:
                    if self._stop_event.is_set():
                        break
                    
                    if connections_sent >= self.config.max_connections_per_session:
                        break
                    
                    # Send connection request
                    request = self._send_connection_request(executive)
                    
                    if request.status == ConnectionStatus.sent:
                        # Log to CRM (sync call via thread)
                        self._log_to_crm_sync(executive, request.custom_message)
                        connections_sent += 1
                    
                    # Wait between connections
                    if not self._stop_event.is_set():
                        delay = self.config.delay_between_connections
                        self._log(f"Waiting {delay} seconds before next connection...")
                        time.sleep(delay)
            
            self._log(f"Bot run completed. Sent {connections_sent} connections.")
            
        except Exception as e:
            error_details = traceback.format_exc()
            self._log(f"[ERR] Bot error: {str(e)}")
            self._log(f"[ERR] Details: {error_details}")
            print(f"Bot error: {error_details}")  # Also print to console
        finally:
            self.status.is_running = False
            self._update_status("Completed")
            self._close_sync()
    
    def _log_to_crm_sync(self, executive: Executive, message: str) -> bool:
        """Log the connection to the CRM (sync wrapper)"""
        self._update_status(f"Logging {executive.name} to CRM")
        
        try:
            # Use asyncio to run the async CRM call
            import httpx
            
            payload = {
                "name": executive.name,
                "stageId": self.config.crm_stage_id,
                "company": executive.company,
                "priority": "medium",
                "source": "LinkedIn Sales Robot",
                "nextSteps": "Follow up on LinkedIn connection acceptance",
                "notes": f"""LinkedIn Profile: {executive.linkedin_url}
Title: {executive.title}
Hiring for: {executive.company_job_title or 'N/A'}

Connection Message Sent:
{message}"""
            }
            
            headers = {"Content-Type": "application/json"}
            if self.crm_client.api_key:
                headers["Authorization"] = f"Bearer {self.crm_client.api_key}"
            
            with httpx.Client() as client:
                response = client.post(
                    f"{self.crm_client.BASE_URL}/api/leads",
                    json=payload,
                    headers=headers,
                    timeout=30.0
                )
                response.raise_for_status()
            
            self._log(f"[OK] Lead created in CRM: {executive.name}")
            self.status.leads_created += 1
            self._notify_status()
            return True
        except Exception as e:
            self._log(f"[ERR] Failed to create CRM lead: {str(e)}")
            return False
    
    def _close_sync(self):
        """Close the browser (sync)"""
        try:
            if self.context:
                self.context.close()
            if self.playwright:
                self.playwright.stop()
        except Exception as e:
            print(f"Error closing browser: {e}")
    
    async def run(self):
        """Main entry point - runs the sync bot in a thread pool"""
        self._loop = asyncio.get_running_loop()
        await self._loop.run_in_executor(_executor, self._run_sync)
    
    async def stop(self):
        """Stop the bot gracefully"""
        self._log("Stopping bot...")
        self._stop_event.set()
    
    async def close(self):
        """Close the browser"""
        self._stop_event.set()
        self.status.is_running = False
        self._update_status("Browser closed")
