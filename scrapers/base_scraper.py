from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from services.browser_manager import BrowserManager
from services.capsolver_service import CapsolverService
from services.email_otp_service import EmailOTPService
import logging
import asyncio

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    def __init__(
        self, 
        browser_manager: BrowserManager, 
        capsolver_service: Optional[CapsolverService] = None,
        email_otp_service: Optional[EmailOTPService] = None
    ):
        self.browser = browser_manager
        self.capsolver = capsolver_service
        self.email_otp = email_otp_service
        self.platform_name = self.__class__.__name__
    
    @abstractmethod
    async def login(self, username: str, password: str) -> bool:
        """Login to the platform with provided credentials"""
        pass
    
    @abstractmethod
    async def navigate_to_accounts(self) -> bool:
        """Navigate to the accounts/dashboard section"""
        pass
    
    @abstractmethod
    async def get_account_status(self, account_id: str) -> Dict[str, Any]:
        """Get current status of a specific account"""
        pass
    
    @abstractmethod
    async def update_password(self, account_id: str, new_password: str) -> bool:
        """Update password for a specific account"""
        pass
    
    @abstractmethod
    async def update_pin(self, account_id: str, new_pin: str) -> bool:
        """Update PIN for a specific account (if applicable)"""
        pass
    
    async def solve_captcha_if_present(self, captcha_type: str = "turnstile") -> Optional[str]:
        """Detect and solve captcha if present on the page"""
        try:
            if captcha_type == "turnstile":
                # Look for Cloudflare Turnstile
                turnstile_frame = await self.browser.page.query_selector("iframe[src*='challenges.cloudflare.com']")
                if turnstile_frame:
                    logger.info("Cloudflare Turnstile detected, solving with Capsolver...")
                    site_key = await turnstile_frame.get_attribute("data-sitekey")
                    page_url = self.browser.page.url
                    
                    if self.capsolver and site_key:
                        token = await self.capsolver.solve_turnstile(page_url, site_key)
                        if token:
                            # Inject the token
                            await self.browser.execute_script(f"""
                                document.querySelector('[name="cf-turnstile-response"]').value = '{token}';
                                if (typeof turnstile !== 'undefined') {{
                                    turnstile.execute();
                                }}
                            """)
                            logger.info("Turnstile token injected successfully")
                            return token
            
            elif captcha_type == "recaptcha_v2":
                # Look for reCAPTCHA v2
                recaptcha_frame = await self.browser.page.query_selector("iframe[src*='recaptcha']")
                if recaptcha_frame:
                    logger.info("reCAPTCHA v2 detected, solving with Capsolver...")
                    site_key = await recaptcha_frame.get_attribute("data-sitekey")
                    page_url = self.browser.page.url
                    
                    if self.capsolver and site_key:
                        token = await self.capsolver.solve_recaptcha_v2(page_url, site_key)
                        if token:
                            # Inject the token
                            await self.browser.execute_script(f"""
                                document.getElementById('g-recaptcha-response').innerHTML = '{token}';
                            """)
                            logger.info("reCAPTCHA v2 token injected successfully")
                            return token
            
            return None
            
        except Exception as e:
            logger.error(f"Error solving captcha: {e}")
            return None
    
    async def wait_for_page_load(self, timeout: int = 10000) -> bool:
        """Wait for page to fully load"""
        try:
            await self.browser.page.wait_for_load_state("networkidle", timeout=timeout)
            return True
        except Exception as e:
            logger.error(f"Error waiting for page load: {e}")
            return False
    
    async def take_screenshot(self, name: str) -> bool:
        """Take a screenshot for debugging"""
        try:
            import os
            screenshot_dir = "screenshots"
            os.makedirs(screenshot_dir, exist_ok=True)
            path = f"{screenshot_dir}/{self.platform_name}_{name}.png"
            return await self.browser.screenshot(path)
        except Exception as e:
            logger.error(f"Error taking screenshot: {e}")
            return False
    
    async def handle_otp_verification(
        self, 
        sender_filter: str, 
        subject_filter: Optional[str] = None,
        keyword: str = "verification",
        otp_input_selector: str = "input[type='text'], input[type='number'], input[name='otp'], input[name='code']",
        max_retries: int = 30,
        retry_interval: int = 10
    ) -> bool:
        """
        Handle OTP verification by reading code from email and entering it in the browser
        
        Args:
            sender_filter: Email sender to filter (e.g., 'netflix.com', 'disneyplus.com')
            subject_filter: Subject keyword filter
            keyword: Keyword to search in email body
            otp_input_selector: CSS selector for OTP input field
            max_retries: Maximum number of retries to find OTP code
            retry_interval: Seconds between retries
        
        Returns:
            True if OTP was successfully entered, False otherwise
        """
        if not self.email_otp:
            logger.warning("Email OTP service not available, skipping OTP handling")
            return False
        
        logger.info(f"Starting OTP verification process for sender: {sender_filter}")
        
        for attempt in range(max_retries):
            try:
                # Check if OTP input is present on page
                otp_input = await self.browser.page.query_selector(otp_input_selector)
                if not otp_input:
                    logger.debug(f"OTP input not found (attempt {attempt + 1}/{max_retries})")
                    await asyncio.sleep(retry_interval)
                    continue
                
                logger.info("OTP input field detected, fetching code from email...")
                
                # Get latest OTP code from email
                otp_data = self.email_otp.get_latest_otp_code(
                    sender_filter=sender_filter,
                    subject_filter=subject_filter,
                    keyword=keyword,
                    minutes_ago=5
                )
                
                if otp_data and otp_data.get('code'):
                    otp_code = otp_data['code']
                    logger.info(f"OTP code found: {otp_code}")
                    logger.info(f"Email from: {otp_data.get('from')}")
                    logger.info(f"Subject: {otp_data.get('subject')}")
                    
                    # Enter OTP code in the input field
                    await self.browser.fill(otp_input_selector, otp_code)
                    await asyncio.sleep(1)
                    
                    # Mark email as read
                    if otp_data.get('message_id'):
                        self.email_otp.mark_as_read(otp_data['message_id'])
                    
                    logger.info("OTP code entered successfully")
                    return True
                else:
                    logger.debug(f"No OTP code found yet (attempt {attempt + 1}/{max_retries})")
                    await asyncio.sleep(retry_interval)
                    
            except Exception as e:
                logger.error(f"Error during OTP verification (attempt {attempt + 1}/{max_retries}): {e}")
                await asyncio.sleep(retry_interval)
        
        logger.error("Failed to retrieve OTP code after maximum retries")
        await self.take_screenshot("otp_failed")
        return False
    
    async def wait_for_otp_prompt(
        self, 
        prompt_selector: str = ".otp-prompt, .verification-prompt, [data-otp], .code-verification",
        timeout: int = 60
    ) -> bool:
        """
        Wait for OTP prompt to appear on the page
        
        Args:
            prompt_selector: CSS selector for OTP prompt element
            timeout: Maximum time to wait in seconds
        
        Returns:
            True if OTP prompt appeared, False otherwise
        """
        try:
            logger.info("Waiting for OTP prompt...")
            await self.browser.wait_for_selector(prompt_selector, timeout=timeout * 1000)
            logger.info("OTP prompt detected")
            return True
        except Exception as e:
            logger.debug(f"OTP prompt not detected: {e}")
            return False
