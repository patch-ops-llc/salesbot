import asyncio
import re
from datetime import datetime
from typing import AsyncGenerator, Callable, Optional, List
from playwright.async_api import async_playwright, Browser, Page, BrowserContext

from .models import (
    BotConfig, BotStatus, Executive, ConnectionRequest,
    ConnectionStatus, SearchConfig
)
from .crm_client import CRMClient


class LinkedInBot:
    """LinkedIn automation bot using Playwright"""
    
    def __init__(
        self,
        config: BotConfig,
        crm_client: CRMClient,
        status_callback: Optional[Callable[[BotStatus], None]] = None
    ):
        self.config = config
        self.crm_client = crm_client
        self.status_callback = status_callback
        self.status = BotStatus()
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self._stop_requested = False
    
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
        """Notify the callback of status change"""
        if self.status_callback:
            self.status_callback(self.status)
    
    def _update_status(self, action: str, **kwargs):
        """Update bot status"""
        self.status.current_action = action
        for key, value in kwargs.items():
            if hasattr(self.status, key):
                setattr(self.status, key, value)
        self._notify_status()
    
    async def start_browser(self, headless: bool = False):
        """Start the browser with persistent context for LinkedIn login"""
        self._log("Starting browser...")
        self.status.is_running = True
        self._update_status("Starting browser")
        
        playwright = await async_playwright().start()
        
        # Use persistent context to maintain LinkedIn session
        self.context = await playwright.chromium.launch_persistent_context(
            user_data_dir="./browser_data",
            headless=headless,
            viewport={"width": 1280, "height": 800},
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ]
        )
        
        self.page = await self.context.new_page()
        
        # Add stealth measures
        await self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
        
        self._log("Browser started successfully")
    
    async def check_login(self) -> bool:
        """Check if user is logged into LinkedIn"""
        self._update_status("Checking LinkedIn login status")
        
        await self.page.goto("https://www.linkedin.com/feed/", wait_until="networkidle")
        await asyncio.sleep(2)
        
        # Check if we're on the login page or feed
        current_url = self.page.url
        if "login" in current_url or "checkpoint" in current_url:
            self._log("⚠️ Not logged in to LinkedIn. Please log in manually.")
            return False
        
        self._log("✅ LinkedIn login confirmed")
        return True
    
    async def search_jobs(self) -> List[dict]:
        """Search for jobs matching the criteria"""
        self._update_status("Searching for job postings")
        jobs = []
        
        search_config = self.config.search_config
        
        for job_title in search_config.job_titles:
            self._log(f"Searching for: {job_title}")
            
            # Build LinkedIn jobs search URL
            search_url = f"https://www.linkedin.com/jobs/search/?keywords={job_title.replace(' ', '%20')}"
            
            if search_config.posted_within_days <= 1:
                search_url += "&f_TPR=r86400"  # Past 24 hours
            elif search_config.posted_within_days <= 7:
                search_url += "&f_TPR=r604800"  # Past week
            elif search_config.posted_within_days <= 30:
                search_url += "&f_TPR=r2592000"  # Past month
            
            await self.page.goto(search_url, wait_until="networkidle")
            await asyncio.sleep(3)
            
            # Extract job listings
            job_cards = await self.page.query_selector_all(".job-card-container")
            
            for card in job_cards[:10]:  # Limit to first 10 per search
                if self._stop_requested:
                    break
                    
                try:
                    title_elem = await card.query_selector(".job-card-list__title")
                    company_elem = await card.query_selector(".job-card-container__primary-description")
                    link_elem = await card.query_selector("a.job-card-container__link")
                    
                    if title_elem and company_elem and link_elem:
                        title = await title_elem.inner_text()
                        company = await company_elem.inner_text()
                        link = await link_elem.get_attribute("href")
                        
                        jobs.append({
                            "title": title.strip(),
                            "company": company.strip(),
                            "link": link,
                            "search_term": job_title
                        })
                except Exception as e:
                    self._log(f"Error extracting job: {str(e)}")
            
            await asyncio.sleep(2)  # Rate limiting
        
        self._log(f"Found {len(jobs)} job postings")
        return jobs
    
    async def find_company_executives(self, company_name: str, job_title: str) -> List[Executive]:
        """Find executives at a company"""
        self._update_status(f"Finding executives at {company_name}")
        executives = []
        
        # Search for people at the company with executive titles
        executive_titles = ["CEO", "CTO", "COO", "CFO", "VP", "Director", "Head of", "Chief"]
        
        search_query = f"{company_name}"
        search_url = f"https://www.linkedin.com/search/results/people/?keywords={search_query.replace(' ', '%20')}&origin=GLOBAL_SEARCH_HEADER"
        
        await self.page.goto(search_url, wait_until="networkidle")
        await asyncio.sleep(3)
        
        # Get people results
        person_cards = await self.page.query_selector_all(".entity-result")
        
        for card in person_cards[:5]:  # Limit to first 5
            if self._stop_requested:
                break
                
            try:
                name_elem = await card.query_selector(".entity-result__title-text a span[aria-hidden='true']")
                title_elem = await card.query_selector(".entity-result__primary-subtitle")
                link_elem = await card.query_selector(".entity-result__title-text a")
                
                if name_elem and title_elem and link_elem:
                    name = await name_elem.inner_text()
                    title = await title_elem.inner_text()
                    link = await link_elem.get_attribute("href")
                    
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
    
    def generate_custom_message(self, executive: Executive) -> str:
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
    
    async def send_connection_request(self, executive: Executive) -> ConnectionRequest:
        """Send a connection request to an executive"""
        self._update_status(f"Sending connection to {executive.name}", current_executive=executive)
        
        custom_message = self.generate_custom_message(executive)
        request = ConnectionRequest(
            executive=executive,
            custom_message=custom_message
        )
        
        try:
            # Navigate to the person's profile
            await self.page.goto(executive.linkedin_url, wait_until="networkidle")
            await asyncio.sleep(2)
            
            # Look for the Connect button
            connect_button = await self.page.query_selector("button:has-text('Connect')")
            
            if not connect_button:
                # Try the "More" dropdown
                more_button = await self.page.query_selector("button:has-text('More')")
                if more_button:
                    await more_button.click()
                    await asyncio.sleep(1)
                    connect_button = await self.page.query_selector("div[role='menuitem']:has-text('Connect')")
            
            if connect_button:
                await connect_button.click()
                await asyncio.sleep(1)
                
                # Click "Add a note" button
                add_note_button = await self.page.query_selector("button:has-text('Add a note')")
                if add_note_button:
                    await add_note_button.click()
                    await asyncio.sleep(1)
                
                # Fill in the message
                message_input = await self.page.query_selector("textarea[name='message']")
                if message_input:
                    await message_input.fill(custom_message)
                    await asyncio.sleep(1)
                
                # Click Send
                send_button = await self.page.query_selector("button:has-text('Send')")
                if send_button:
                    await send_button.click()
                    await asyncio.sleep(2)
                    
                    request.status = ConnectionStatus.sent
                    request.sent_at = datetime.now()
                    self._log(f"✅ Connection sent to {executive.name}")
                    self.status.connections_sent += 1
                else:
                    raise Exception("Could not find Send button")
            else:
                # Might already be connected or pending
                self._log(f"⚠️ Connect button not found for {executive.name} - may already be connected")
                request.status = ConnectionStatus.failed
                request.error_message = "Connect button not found"
                self.status.connections_failed += 1
                
        except Exception as e:
            request.status = ConnectionStatus.failed
            request.error_message = str(e)
            self._log(f"❌ Failed to connect with {executive.name}: {str(e)}")
            self.status.connections_failed += 1
        
        self._notify_status()
        return request
    
    async def log_to_crm(self, executive: Executive, message: str) -> bool:
        """Log the connection to the CRM"""
        self._update_status(f"Logging {executive.name} to CRM")
        
        try:
            result = await self.crm_client.create_lead_from_executive(
                executive=executive,
                stage_id=self.config.crm_stage_id,
                custom_message=message
            )
            self._log(f"✅ Lead created in CRM: {executive.name}")
            self.status.leads_created += 1
            self._notify_status()
            return True
        except Exception as e:
            self._log(f"❌ Failed to create CRM lead: {str(e)}")
            return False
    
    async def run(self):
        """Main bot execution loop"""
        self._stop_requested = False
        
        try:
            await self.start_browser(headless=False)
            
            # Check if logged in
            if not await self.check_login():
                self._log("Please log in to LinkedIn in the browser window, then restart the bot.")
                return
            
            # Search for jobs
            jobs = await self.search_jobs()
            
            if not jobs:
                self._log("No jobs found matching criteria")
                return
            
            # Track processed companies to avoid duplicates
            processed_companies = set()
            connections_sent = 0
            
            for job in jobs:
                if self._stop_requested:
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
                executives = await self.find_company_executives(company, job["title"])
                
                for executive in executives:
                    if self._stop_requested:
                        break
                    
                    if connections_sent >= self.config.max_connections_per_session:
                        break
                    
                    # Send connection request
                    request = await self.send_connection_request(executive)
                    
                    if request.status == ConnectionStatus.sent:
                        # Log to CRM
                        await self.log_to_crm(executive, request.custom_message)
                        connections_sent += 1
                    
                    # Wait between connections
                    if not self._stop_requested:
                        delay = self.config.delay_between_connections
                        self._log(f"Waiting {delay} seconds before next connection...")
                        await asyncio.sleep(delay)
            
            self._log(f"Bot run completed. Sent {connections_sent} connections.")
            
        except Exception as e:
            self._log(f"❌ Bot error: {str(e)}")
            raise
        finally:
            self.status.is_running = False
            self._update_status("Completed")
    
    async def stop(self):
        """Stop the bot gracefully"""
        self._log("Stopping bot...")
        self._stop_requested = True
    
    async def close(self):
        """Close the browser"""
        if self.context:
            await self.context.close()
        self.status.is_running = False
        self._update_status("Browser closed")

