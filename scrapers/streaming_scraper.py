from typing import Dict, Any, Optional
from scrapers.base_scraper import BaseScraper
import logging

logger = logging.getLogger(__name__)


class StreamingScraper(BaseScraper):
    def __init__(self, browser_manager, capsolver_service=None, email_otp_service=None, platform: str = "netflix"):
        super().__init__(browser_manager, capsolver_service, email_otp_service)
        self.platform = platform.lower()
        
        if self.platform == "netflix":
            self.base_url = "https://netflix.com"
            self.login_url = f"{self.base_url}/login"
            self.profile_url = f"{self.base_url}/YourAccount"
            self.otp_sender = "netflix.com"
        elif self.platform == "disney":
            self.base_url = "https://disneyplus.com"
            self.login_url = f"{self.base_url}/login"
            self.profile_url = f"{self.base_url}/account"
            self.otp_sender = "disneyplus.com"
        else:
            raise ValueError(f"Unsupported platform: {platform}")
    
    async def login(self, username: str, password: str) -> bool:
        try:
            logger.info(f"Attempting login to {self.platform.capitalize()} for user: {username}")
            
            await self.browser.navigate(self.login_url)
            await self.browser.wait_for_selector('input[type="email"], input[name="email"]', timeout=10000)
            
            # Fill login form
            await self.browser.fill('input[type="email"], input[name="email"]', username)
            await self.browser.wait(500)
            
            # Click continue/next button
            await self.browser.click('button[type="submit"], .btn-submit, .continue-btn')
            await self.browser.wait(1000)
            
            # Fill password
            await self.browser.wait_for_selector('input[type="password"], input[name="password"]', timeout=10000)
            await self.browser.fill('input[type="password"], input[name="password"]', password)
            await self.browser.wait(500)
            
            # Check for captcha and solve if present
            await self.solve_captcha_if_present("recaptcha_v2")
            
            # Submit login
            await self.browser.click('button[type="submit"], .btn-submit, .sign-in-btn')
            await self.wait_for_page_load()
            
            # Verify successful login
            current_url = self.browser.page.url
            if "login" not in current_url or "profile" in current_url or "account" in current_url:
                logger.info(f"{self.platform.capitalize()} login successful")
                await self.take_screenshot("login_success")
                return True
            else:
                logger.error(f"{self.platform.capitalize()} login failed - still on login page")
                await self.take_screenshot("login_failed")
                return False
                
        except Exception as e:
            logger.error(f"Error during {self.platform.capitalize()} login: {e}")
            await self.take_screenshot("login_error")
            return False
    
    async def navigate_to_accounts(self) -> bool:
        try:
            logger.info(f"Navigating to {self.platform.capitalize()} profiles section")
            
            await self.browser.navigate(self.profile_url)
            await self.wait_for_page_load()
            
            # Wait for profiles list to load
            await self.browser.wait_for_selector('.profile, .account-profile, .user-profile', timeout=10000)
            
            logger.info("Successfully navigated to profiles section")
            await self.take_screenshot("profiles_page")
            return True
            
        except Exception as e:
            logger.error(f"Error navigating to profiles: {e}")
            return False
    
    async def get_account_status(self, profile_id: str) -> Dict[str, Any]:
        try:
            logger.info(f"Getting status for {self.platform.capitalize()} profile: {profile_id}")
            
            # Navigate to profile settings
            profile_url = f"{self.profile_url}/{profile_id}"
            await self.browser.navigate(profile_url)
            await self.wait_for_page_load()
            
            # Extract profile information
            status = {
                "profile_id": profile_id,
                "platform": self.platform,
                "status": "unknown",
                "subscription_end": None,
                "is_active": False,
                "profile_name": None,
                "profile_type": None
            }
            
            # Try to extract profile name
            name_selectors = [
                '.profile-name', '.profile-title', 'h1, h2', '[data-profile-name]'
            ]
            
            for selector in name_selectors:
                name_text = await self.browser.get_text(selector)
                if name_text:
                    status["profile_name"] = name_text
                    break
            
            # Try to extract subscription status
            status_selectors = [
                '.subscription-status', '.account-status', '.membership-status', '[data-status]'
            ]
            
            for selector in status_selectors:
                status_text = await self.browser.get_text(selector)
                if status_text:
                    status["status"] = status_text.lower()
                    status["is_active"] = "active" in status_text.lower()
                    break
            
            # Try to extract subscription end date
            date_selectors = [
                '.end-date', .subscription-end', '.membership-end', '[data-end-date]'
            ]
            
            for selector in date_selectors:
                date_text = await self.browser.get_text(selector)
                if date_text:
                    status["subscription_end"] = date_text
                    break
            
            # Try to extract profile type (kids, standard, etc.)
            type_selectors = [
                '.profile-type', '.profile-tier', '[data-profile-type]'
            ]
            
            for selector in type_selectors:
                type_text = await self.browser.get_text(selector)
                if type_text:
                    status["profile_type"] = type_text
                    break
            
            logger.info(f"Profile status retrieved: {status}")
            return status
            
        except Exception as e:
            logger.error(f"Error getting profile status: {e}")
            return {"profile_id": profile_id, "platform": self.platform, "error": str(e)}
    
    async def update_password(self, profile_id: str, new_password: str) -> bool:
        try:
            logger.info(f"Updating password for {self.platform.capitalize()} profile: {profile_id}")
            
            # Navigate to account security settings
            security_url = f"{self.profile_url}/security"
            await self.browser.navigate(security_url)
            await self.wait_for_page_load()
            
            # Find password change form
            await self.browser.wait_for_selector('input[type="password"], input[name="password"]', timeout=10000)
            
            # Fill current password (might be required)
            current_password_field = await self.browser.page.query_selector('input[name="current_password"], input[type="password"]:first-of-type')
            if current_password_field:
                # This would need to be provided separately
                logger.warning("Current password field detected - may require additional credentials")
            
            # Fill new password
            await self.browser.fill('input[name="new_password"], input[type="password"]:nth-of-type(2)', new_password)
            await self.browser.wait(500)
            
            # Confirm password
            await self.browser.fill('input[name="confirm_password"], input[type="password"]:nth-of-type(3)', new_password)
            await self.browser.wait(500)
            
            # Submit password change
            await self.browser.click('button[type="submit"], .save-password-btn, .update-security-btn')
            await self.browser.wait(2000)
            
            # Check if OTP verification is required
            if await self.wait_for_otp_prompt(timeout=10):
                logger.info("OTP verification required, handling automatically...")
                otp_success = await self.handle_otp_verification(
                    sender_filter=self.otp_sender,
                    subject_filter="verification",
                    keyword="code",
                    max_retries=30,
                    retry_interval=10
                )
                
                if not otp_success:
                    logger.error("OTP verification failed")
                    await self.take_screenshot("otp_verification_failed")
                    return False
                
                # Submit OTP form if needed
                submit_button = await self.browser.page.query_selector('button[type="submit"], .verify-btn, .submit-otp')
                if submit_button:
                    await self.browser.click('button[type="submit"], .verify-btn, .submit-otp')
                    await self.wait_for_page_load()
            
            # Verify success
            success_message = await self.browser.get_text('.success-message, .alert-success, .notification, .toast')
            if success_message and ("success" in success_message.lower() or "updated" in success_message.lower()):
                logger.info("Password updated successfully")
                await self.take_screenshot("password_update_success")
                return True
            else:
                logger.error("Password update failed")
                await self.take_screenshot("password_update_failed")
                return False
                
        except Exception as e:
            logger.error(f"Error updating password: {e}")
            await self.take_screenshot("password_update_error")
            return False
    
    async def update_pin(self, profile_id: str, new_pin: str) -> bool:
        try:
            logger.info(f"Updating PIN for {self.platform.capitalize()} profile: {profile_id}")
            
            # Navigate to profile PIN settings
            pin_url = f"{self.profile_url}/pin"
            await self.browser.navigate(pin_url)
            await self.wait_for_page_load()
            
            # Find PIN change form
            await self.browser.wait_for_selector('input[name="pin"], input[type="text"][maxlength="4"], input[type="number"]', timeout=10000)
            
            # Fill new PIN
            await self.browser.fill('input[name="new_pin"], input[type="text"]:first-of-type', new_pin)
            await self.browser.wait(500)
            
            # Confirm PIN
            await self.browser.fill('input[name="confirm_pin"], input[type="text"]:nth-of-type(2)', new_pin)
            await self.browser.wait(500)
            
            # Submit PIN change
            await self.browser.click('button[type="submit"], .save-pin-btn, .update-pin-btn')
            await self.wait_for_page_load()
            
            # Verify success
            success_message = await self.browser.get_text('.success-message, .alert-success, .notification, .toast')
            if success_message and ("success" in success_message.lower() or "updated" in success_message.lower()):
                logger.info("PIN updated successfully")
                await self.take_screenshot("pin_update_success")
                return True
            else:
                logger.error("PIN update failed")
                await self.take_screenshot("pin_update_failed")
                return False
                
        except Exception as e:
            logger.error(f"Error updating PIN: {e}")
            await self.take_screenshot("pin_update_error")
            return False
    
    async def get_all_profiles(self) -> list:
        try:
            logger.info(f"Getting all {self.platform.capitalize()} profiles")
            
            await self.navigate_to_accounts()
            
            profiles = []
            profile_items = await self.browser.page.query_selector_all('.profile, .account-profile, .user-profile')
            
            for item in profile_items:
                try:
                    profile_id = await item.get_attribute("data-id") or await item.get_attribute("id")
                    profile_name = await item.query_selector('.profile-name, .name')
                    
                    if profile_name:
                        name_text = await profile_name.inner_text()
                    else:
                        name_text = "Unknown"
                    
                    profiles.append({
                        "id": profile_id,
                        "name": name_text,
                        "platform": self.platform
                    })
                except Exception as e:
                    logger.error(f"Error parsing profile item: {e}")
                    continue
            
            logger.info(f"Found {len(profiles)} profiles")
            return profiles
            
        except Exception as e:
            logger.error(f"Error getting all profiles: {e}")
            return []
